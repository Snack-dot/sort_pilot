from __future__ import annotations

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Load ONNX Runtime before Qt. On Windows, loading Qt's native libraries first can
# prevent onnxruntime_pybind11_state from initializing when FastEmbed is imported
# later by a classification worker.
import onnxruntime  # noqa: F401
from PyQt6.QtCore import QObject, QStandardPaths, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog, QSystemTrayIcon

from .analysis_queue import BatchAnalysisController
from .calibration import (
    CalibrationSampler,
    CalibrationService,
    learn_correction,
    merge_profile_evidence,
)
from .calibration_dialog import CalibrationDialog, ensure_local_model, ensure_semantic_vectors
from .classification import (
    ConstrainedGemmaFallback,
    EducationalClassificationInput,
    EducationalClassificationOutput,
    EducationalClassificationService,
    FastEmbedE5Encoder,
    GemmaFallbackCache,
    GemmaFallbackCancelled,
    PersonalExampleStore,
    load_calibrated_policy,
    load_personal_example_policy,
    load_subject_profiles,
    load_template_profiles,
)
from .classifier_engine.config import data_dir
from .classifier_engine.hierarchy import TYPE_FAMILIES, UNSORTED_TOPIC
from .classifier_engine.topics import (
    AnalysisRecord,
    TopicClassifier,
    TopicProfile,
    TopicProfileStore,
)
from .curriculum import StudentProfile, StudentProfileStore
from .educational_preview import EducationalPreviewDialog
from .embeddings_installer import EmbeddingsInstaller
from .history import HistoryStore
from .instance_lock import SingleInstanceLock
from .local_tagger import LocalModelInstaller, LocalTagger
from .migration import MigrationCandidate, collect_migration_candidates
from .models import FileSuggestion
from .onboarding import StudentOnboardingDialog
from .organizer import (
    build_operation,
    execute_batch,
    execute_organization_plans,
    undo_latest,
)
from .preview import PreviewDialog
from .scanner import collect_candidates
from .topic_dialogs import ProfileEditRequest, TopicManagerDialog
from .tray import TrayIcon


class AppController(QObject):
    """Coordinate the student subject/template workflow, exact moves, and Undo."""

    def __init__(self, app: QApplication) -> None:
        """Initialize application services without starting file analysis."""
        super().__init__()
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.history = HistoryStore(app_data / "history.json", app_data / "history.db")
        self.student_profile_store = StudentProfileStore(app_data / "student_profile.json")
        self.personal_examples = PersonalExampleStore(app_data / "personal_examples.json")
        self.profile_store = TopicProfileStore(data_dir() / "topic_profiles.json")
        self.topic_classifier = TopicClassifier()
        self.calibration = CalibrationService(self.topic_classifier, self.profile_store)
        self.calibration_sampler = CalibrationSampler(data_dir() / "calibration_state.json", per_family=20)
        self.model_installer = LocalModelInstaller(data_dir() / "local_ai")
        self.gemma_fallback = ConstrainedGemmaFallback(
            self.model_installer,
            GemmaFallbackCache(app_data / "gemma_fallback_cache.json"),
        )
        self.e5_cache_dir = Path(__file__).resolve().parents[1] / "data" / "models" / "fastembed"
        self.local_tagger = LocalTagger(self.model_installer)
        self.embeddings_installer = EmbeddingsInstaller(data_dir() / "local_ai")
        self.downloads_folder = Path.home() / "Downloads"
        self.analysis = BatchAnalysisController(self)
        self.analysis.progress.connect(self._update_progress)
        self.analysis.completed.connect(self._analysis_completed)
        self.analysis.cancelled.connect(self._analysis_cancelled)
        self.analysis.busy_changed.connect(self._set_busy)
        self.progress_dialog: QProgressDialog | None = None
        self._analysis_mode = "organize"
        self._profile_snapshot: list[TopicProfile] = []
        self._pending_profile_request: ProfileEditRequest | None = None
        self._pending_organize: tuple[list[Path], str] | None = None
        self._migration_candidates: dict[str, MigrationCandidate] = {}
        self._classification_cancel_event: threading.Event | None = None
        self.tray = TrayIcon(
            self.organize_all,
            self.organize_desktop,
            self.organize_downloads,
            self.manage_student_profile,
            self.undo,
            self.quit,
        )

    def start(self) -> None:
        """Show the tray icon and schedule onboarding before other first-run work."""
        self.tray.show()
        if self.history.migrated_legacy_batch:
            self.tray.notify("Sort Pilot", "기존 실행 취소 기록을 JSON 형식으로 이전했습니다.")
        QTimer.singleShot(0, self._start_initial_workflow)

    def _start_initial_workflow(self) -> None:
        """Require the saved student profile without starting an older topic flow."""
        self._require_student_profile()

    def _require_student_profile(self) -> bool:
        """Require a valid saved student profile before classification or organization."""
        try:
            current = self.student_profile_store.load()
        except RuntimeError as exc:
            QMessageBox.critical(None, "학생 설정 읽기 실패", str(exc))
            return False
        return current is not None or self.manage_student_profile()

    def manage_student_profile(self) -> bool:
        """Create or edit the local student onboarding profile atomically."""
        try:
            current = self.student_profile_store.load()
        except RuntimeError as exc:
            QMessageBox.critical(None, "학생 설정 읽기 실패", str(exc))
            return False
        dialog = StudentOnboardingDialog(current)
        if dialog.exec() != StudentOnboardingDialog.DialogCode.Accepted or dialog.profile is None:
            return False
        try:
            self.student_profile_store.save(dialog.profile)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(None, "학생 설정 저장 실패", str(exc))
            return False
        self.tray.notify("Sort Pilot", "학생 유형, 학년, 학기 설정을 저장했습니다.")
        return True

    def calibrate_topics(self) -> None:
        """Analyze a bounded random sample without moving files."""
        if self.analysis.busy:
            return
        if not self._require_student_profile():
            return
        if self._pending_organize is None:
            self._pending_organize = (
                [self._desktop_folder(), self.downloads_folder],
                "바탕화면과 다운로드 폴더",
            )
        try:
            roots = self._pending_organize[0]
            paths = self.calibration_sampler.select(roots)
        except (OSError, NotADirectoryError) as exc:
            QMessageBox.critical(None, "표본 파일 읽기 실패", str(exc))
            return
        if not paths:
            QMessageBox.information(None, "Sort Pilot", "주제를 보정할 표본 파일이 없습니다.")
            return
        self._start_analysis(paths, "calibration", "주제 보정 표본 분석")

    def organize_desktop(self) -> None:
        """Analyze safe top-level files on the Desktop."""
        self._organize_existing_files([self._desktop_folder()], "바탕화면")

    def organize_downloads(self) -> None:
        """Analyze safe top-level files in Downloads."""
        self._organize_existing_files([self.downloads_folder], "다운로드 폴더")

    def organize_all(self) -> None:
        """Analyze Desktop and Downloads together in one deduplicated session."""
        self._organize_existing_files(
            [self._desktop_folder(), self.downloads_folder],
            "바탕화면과 다운로드 폴더",
        )

    def manage_topics(self) -> None:
        """Open profile management and asynchronously learn any selected examples."""
        dialog = TopicManagerDialog(self.profile_store)
        if dialog.exec() != TopicManagerDialog.DialogCode.Accepted or dialog.request is None:
            return
        request = dialog.request
        if request.example_paths:
            self._pending_profile_request = request
            self._start_analysis(request.example_paths, "profile", "예시 파일 학습")
            return
        self.profile_store.upsert(request.profile)
        self.tray.notify("Sort Pilot", f"'{request.profile.name}' 주제 프로필을 저장했습니다.")

    def migrate_folders(self) -> None:
        """Analyze existing flat folders and prepare a separate approval-based migration."""
        if not self._require_student_profile():
            return
        candidates: list[MigrationCandidate] = []
        try:
            for root in (self._desktop_folder(), self.downloads_folder):
                candidates.extend(collect_migration_candidates(root))
        except (OSError, NotADirectoryError) as exc:
            QMessageBox.critical(None, "기존 폴더 읽기 실패", str(exc))
            return
        if not candidates:
            QMessageBox.information(None, "Sort Pilot", "계층화할 기존 폴더 파일이 없습니다.")
            return
        self._migration_candidates = {self._path_key(item.source): item for item in candidates}
        self._start_analysis((item.source for item in candidates), "migration", "기존 폴더 분석")

    @staticmethod
    def _desktop_folder() -> Path:
        """Resolve the platform Desktop folder through Qt."""
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation))

    def _organize_existing_files(self, folders: list[Path], label: str) -> None:
        """Collect candidates and start the educational subject/template analysis."""
        if not self._require_student_profile():
            return
        paths: list[Path] = []
        try:
            for folder in folders:
                paths.extend(collect_candidates(folder))
        except (OSError, NotADirectoryError) as exc:
            QMessageBox.critical(None, "폴더 읽기 실패", str(exc))
            return
        if not paths:
            QMessageBox.information(None, "Sort Pilot", f"{label}에 정리할 파일이 없습니다.")
            return
        self._start_analysis(paths, "organize", "교육 자료 분석")

    def _start_analysis(self, paths, mode: str, label: str) -> None:
        """Start one queue session with an explicit completion mode and progress label."""
        if not self._require_student_profile():
            return
        self._analysis_mode = mode
        total = self.analysis.start(paths)
        if total:
            self._show_progress(total, label)

    def _show_progress(self, total: int, label: str) -> None:
        """Display the cancellable modal progress window for the active batch."""
        dialog = QProgressDialog(f"{label} 중입니다.", "취소", 0, total)
        dialog.setWindowTitle("Sort Pilot - AI 분석")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setProperty("task_label", label)
        dialog.canceled.connect(self.analysis.cancel)
        self.progress_dialog = dialog
        dialog.show()

    def _update_progress(self, completed: int, total: int) -> None:
        """Reflect worker completion on the Qt main thread."""
        if self.progress_dialog is not None:
            label = self.progress_dialog.property("task_label") or "AI 분석"
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(completed)
            self.progress_dialog.setLabelText(f"{label}: {completed}/{total}")

    def _analysis_completed(self, results: list, errors: list[tuple[str, str]]) -> None:
        """Dispatch completed extraction records to their requested workflow."""
        self._close_progress()
        self._report_analysis_errors(errors)
        records = [result for result in results if isinstance(result, AnalysisRecord)]
        if self._analysis_mode == "profile":
            self._complete_profile_learning(records)
        elif self._analysis_mode == "calibration":
            self._complete_calibration(records)
        elif self._analysis_mode == "migration":
            self._complete_migration(records)
        else:
            self._complete_organization(records)

    def _complete_organization(self, records: list[AnalysisRecord]) -> None:
        """Classify both educational axes, review them, then execute frozen paths."""
        if not self._require_student_profile():
            return
        if not records:
            QMessageBox.information(None, "Sort Pilot", "분석 결과가 없습니다.")
            return
        try:
            student = self.student_profile_store.load()
        except RuntimeError as exc:
            QMessageBox.critical(None, "학생 설정 읽기 실패", str(exc))
            return
        if student is None:
            return
        outputs = self._classify_educational_records(records, student)
        if outputs is None:
            return
        dialog = EducationalPreviewDialog(
            outputs,
            self._desktop_folder(),
            self.downloads_folder,
        )
        if dialog.exec() != EducationalPreviewDialog.DialogCode.Accepted:
            return
        approved = dialog.frozen_plans
        examples = tuple(
            example
            for item in approved
            for example in (item.personal_example(),)
            if example is not None
        )
        completed = []
        try:
            completed = execute_organization_plans(
                [item.plan for item in approved],
                self.history,
            )
            self.personal_examples.add(examples)
        except (OSError, ValueError, RuntimeError) as exc:
            if completed:
                undo_latest(self.history)
                detail = "\n이동한 파일은 원래 위치로 되돌렸습니다."
            else:
                detail = ""
            QMessageBox.critical(None, "정리 실패", f"{exc}{detail}")
            return
        QMessageBox.information(None, "정리 완료", f"{len(completed)}개 파일을 정리했습니다.")

    @staticmethod
    def _educational_input(record: AnalysisRecord) -> EducationalClassificationInput:
        """Convert one extraction record without persisting its source text."""
        return EducationalClassificationInput(
            source=record.source,
            fingerprint=record.fingerprint,
            file_name=record.file_name,
            natural_text=record.natural_text,
            template_natural_text=record.template_natural_text,
            lexical_evidence=record.lexical_evidence,
            pmi_collocations=record.pmi_collocations,
            ocr_layout_evidence=record.ocr_layout_evidence,
            visual_evidence=record.visual_evidence,
        )

    def _classify_educational_records(
        self,
        records: list[AnalysisRecord],
        student: StudentProfile,
    ) -> tuple[EducationalClassificationOutput, ...] | None:
        """Run local-cache-only educational classification with cancellation."""
        try:
            inputs = tuple(self._educational_input(record) for record in records)
        except ValueError as exc:
            QMessageBox.critical(None, "교육 분류 입력 실패", str(exc))
            return None
        cancel_event = threading.Event()
        self._classification_cancel_event = cancel_event
        completed_count = [0]
        dialog = QProgressDialog("과목과 템플릿을 분류하고 있습니다.", "취소", 0, len(inputs))
        dialog.setWindowTitle("Sort Pilot - 교육 분류")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)

        def cancel() -> None:
            cancel_event.set()
            self.gemma_fallback.cancel()

        def work() -> tuple[EducationalClassificationOutput, ...]:
            encoder = FastEmbedE5Encoder(self.e5_cache_dir, allow_download=False)
            service = EducationalClassificationService(
                encoder=encoder,
                subject_profiles=load_subject_profiles(),
                template_profiles=load_template_profiles(),
                calibrated_policy=load_calibrated_policy(),
                personal_policy=load_personal_example_policy(),
                personal_examples=self.personal_examples,
                gemma=self.gemma_fallback,
            )
            return service.classify_many(
                inputs,
                student,
                progress=lambda completed, _total: completed_count.__setitem__(0, completed),
                cancelled=cancel_event.is_set,
            )

        dialog.canceled.connect(cancel)
        self._set_busy(True)
        dialog.show()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(work)
                while not future.done():
                    QApplication.processEvents()
                    dialog.setValue(completed_count[0])
                    time.sleep(0.05)
                return future.result()
        except GemmaFallbackCancelled:
            self.tray.notify("Sort Pilot", "교육 분류를 취소했습니다.")
            return None
        except Exception as exc:
            QMessageBox.critical(None, "교육 분류 실패", str(exc))
            return None
        finally:
            self._classification_cancel_event = None
            dialog.close()
            dialog.deleteLater()
            self._set_busy(False)

    def _complete_calibration(self, records: list[AnalysisRecord]) -> None:
        """Generate local labels, review the sample, then persist approved topics."""
        content_records = [record for record in records if record.terms]
        if not content_records:
            QMessageBox.information(
                None,
                "Sort Pilot",
                "표본에서 읽을 수 있는 본문·OCR 내용을 찾지 못했습니다. 파일은 이동하지 않았습니다.",
            )
            self._pending_organize = None
            return
        ensure_semantic_vectors(None, self.embeddings_installer)
        proposals = self.topic_classifier.discover(content_records)
        suggestions = {}
        if proposals and ensure_local_model(None, self.model_installer):
            progress = QProgressDialog("로컬 AI가 주제와 태그를 제안하고 있습니다.", "", 0, 0)
            progress.setWindowTitle("Sort Pilot")
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setCancelButton(None)
            progress.show()
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.local_tagger.propose, proposals)
                    while not future.done():
                        QApplication.processEvents()
                        time.sleep(0.05)
                    suggestions = future.result()
            except Exception as exc:
                QMessageBox.warning(
                    None,
                    "로컬 AI 제안 실패",
                    f"TF-IDF 핵심 단어 제안으로 계속합니다.\n{exc}",
                )
            finally:
                progress.close()
        draft = self.calibration.build_draft(content_records, suggestions, min_cluster_size=2)
        if not draft.clusters:
            QMessageBox.information(
                None,
                "Sort Pilot",
                "표본에서 서로 연관된 주제 묶음을 찾지 못했습니다. 나중에 더 많은 파일과 함께 다시 시도합니다.",
            )
            self._pending_organize = None
            return
        dialog = CalibrationDialog(draft, self.profile_store.load())
        if dialog.exec() != CalibrationDialog.DialogCode.Accepted:
            self._pending_organize = None
            return
        try:
            fingerprints = [
                self.calibration_sampler.fingerprint(record.source)
                for record in draft.surfaced_records()
            ]
            profiles = self.calibration.profiles_from_draft(draft)
            changes = self.calibration.seed_changes(
                draft, self._desktop_folder(), self.downloads_folder
            )
            operations = [
                build_operation(
                    change,
                    self._destination_root(change.destination_root, change.suggestion.source),
                )
                for change in changes
            ]
            completed = execute_batch(operations, self.history)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(None, "보정 시드 이동 실패", str(exc))
            self._pending_organize = None
            return
        try:
            self.profile_store.save(profiles)
        except (OSError, ValueError, RuntimeError) as exc:
            if completed:
                undo_latest(self.history)
            QMessageBox.critical(
                None,
                "주제 보정 저장 실패",
                f"시드 이동을 되돌렸습니다.\n{exc}",
            )
            self._pending_organize = None
            return
        try:
            self.calibration_sampler.remember_fingerprints(fingerprints)
        except OSError:
            self.tray.notify("Sort Pilot", "주제는 저장했지만 표본 사용 기록을 저장하지 못했습니다.")
        self.tray.notify(
            "Sort Pilot",
            f"시드 {len(completed)}개를 주제 폴더로 이동하고 어휘 프로필을 저장했습니다.",
        )
        pending = self._pending_organize
        self._pending_organize = None
        if pending is not None:
            QTimer.singleShot(0, lambda: self._organize_existing_files(*pending))

    def _complete_profile_learning(self, records: list[AnalysisRecord]) -> None:
        """Merge same-family example features into a pending profile without moves."""
        request = self._pending_profile_request
        self._pending_profile_request = None
        if request is None:
            return
        matching = [
            record for record in records
            if record.family == request.profile.family and record.terms
        ]
        profile = self._merge_examples(request.profile, matching)
        self.profile_store.upsert(profile)
        skipped = len(records) - len(matching)
        message = f"'{profile.name}' 프로필에 예시 {len(matching)}개를 학습했습니다."
        if skipped:
            message += f" 다른 유형 {skipped}개는 제외했습니다."
        QMessageBox.information(None, "주제 프로필 저장", message)

    def _complete_migration(self, records: list[AnalysisRecord]) -> None:
        """Apply prescribed hierarchical targets and show the standard move preview."""
        suggestions: list[FileSuggestion] = []
        record_map: dict[str, AnalysisRecord] = {}
        for record in records:
            candidate = self._migration_candidates.get(self._path_key(record.source))
            if candidate is None:
                continue
            record.family = candidate.family
            record.topic = candidate.topic
            record.reason = "기존 최상위 폴더 이름을 주제로 보존한 계층화 제안"
            suggestions.append(
                FileSuggestion(
                    record.file_path,
                    record.file_name,
                    record.suggested_name,
                    candidate.folder,
                    record.reason,
                )
            )
            record_map[self._path_key(record.source)] = record
        self._migration_candidates = {}
        if not suggestions:
            QMessageBox.information(None, "Sort Pilot", "계층화할 분석 결과가 없습니다.")
            return
        self._show_preview(suggestions, record_map)

    def _report_analysis_errors(self, errors: list[tuple[str, str]]) -> None:
        """Report bounded per-file extraction failures without losing successful results."""
        if not errors:
            return
        examples = "\n".join(f"- {Path(path).name}: {message}" for path, message in errors[:5])
        suffix = f"\n외 {len(errors) - 5}개" if len(errors) > 5 else ""
        QMessageBox.warning(None, "일부 분석 실패", f"{len(errors)}개 파일을 분석하지 못했습니다.\n{examples}{suffix}")

    def _analysis_cancelled(self) -> None:
        """Close progress and discard pending workflow context after cancellation."""
        self._close_progress()
        if self._analysis_mode == "calibration":
            self._pending_organize = None
        self._pending_profile_request = None
        self._migration_candidates = {}
        self.tray.notify("Sort Pilot", "파일 분석을 취소했습니다.")

    def _close_progress(self) -> None:
        """Detach and close the active progress dialog safely."""
        dialog = self.progress_dialog
        self.progress_dialog = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def _set_busy(self, busy: bool) -> None:
        """Prevent profile edits, migration, overlapping analysis, and Undo while busy."""
        self.tray.set_busy(busy)

    def undo(self) -> None:
        """Ask for confirmation and restore the latest recorded move batch."""
        if QMessageBox.question(None, "실행 취소", "마지막 정리 작업을 원래 위치로 되돌릴까요?") != QMessageBox.StandardButton.Yes:
            return
        restored = undo_latest(self.history)
        message = f"{len(restored)}개 파일을 원래 위치로 되돌렸습니다." if restored else "실행 취소할 작업이 없습니다."
        QMessageBox.information(None, "Sort Pilot", message)

    def quit(self) -> None:
        """Confirm exit, cancel queued work, and wait for active workers."""
        if QMessageBox.question(None, "프로그램 종료", "Sort Pilot을 종료할까요?") != QMessageBox.StandardButton.Yes:
            return
        self._close_progress()
        if self._classification_cancel_event is not None:
            self._classification_cancel_event.set()
        self.gemma_fallback.cancel()
        self.analysis.shutdown(-1)
        self.tray.hide()
        self.app.quit()

    def _show_preview(
        self,
        suggestions: list[FileSuggestion],
        learning_records: dict[str, AnalysisRecord] | None = None,
    ) -> None:
        """Show editable destinations, execute approved moves, and learn feedback."""
        if not self._require_student_profile():
            return
        dialog = PreviewDialog(
            suggestions,
            self._desktop_folder(),
            self.downloads_folder,
            self.profile_store.load(),
        )
        if dialog.exec() != PreviewDialog.DialogCode.Accepted:
            return
        changes = dialog.approved_changes()
        operations = [
            build_operation(item, self._destination_root(item.destination_root, item.suggestion.source))
            for item in changes
        ]
        try:
            completed = execute_batch(operations, self.history)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(None, "정리 실패", str(exc))
            return
        if learning_records:
            completed_sources = {self._path_key(operation.source_path) for operation in completed}
            self._learn_approved_moves(changes, learning_records, completed_sources)
        QMessageBox.information(None, "정리 완료", f"{len(completed)}개 파일을 정리했습니다.")

    def _learn_approved_moves(self, changes, records, completed_sources: set[str]) -> None:
        """Learn signed profile evidence only from successfully moved files."""
        profiles = self.profile_store.load()
        for change in changes:
            key = self._path_key(change.suggestion.source)
            if key not in completed_sources or key not in records:
                continue
            parts = Path(change.folder).parts
            if len(parts) < 2 or parts[0] not in TYPE_FAMILIES or parts[1] == UNSORTED_TOPIC:
                continue
            record = records[key]
            family, topic = parts[0], parts[1]
            profile = next(
                (item for item in profiles if item.family == family and item.name.casefold() == topic.casefold()),
                None,
            )
            if profile is None:
                profile = self.profile_store.new_profile(family, topic, origin="discovered")
                profiles.append(profile)
            profiles = learn_correction(profiles, record, record.topic, topic)
        self.profile_store.save(profiles)

    def _merge_examples(self, profile: TopicProfile, records: list[AnalysisRecord]) -> TopicProfile:
        """Merge averaged record terms with a profile using example-count weighting."""
        return merge_profile_evidence(profile, records)

    @staticmethod
    def _record_suggestion(record: AnalysisRecord) -> FileSuggestion:
        """Convert a completed hierarchical record into the stable preview model."""
        reason = record.reason or f"{record.family} 유형에서 일치하는 주제가 없어 '{UNSORTED_TOPIC}'로 제안"
        return FileSuggestion(
            record.file_path,
            record.file_name,
            record.suggested_name,
            record.folder,
            reason,
        )

    def _destination_root(self, choice: str, source: Path) -> Path:
        """Resolve a preview destination identifier to an allowed root path."""
        roots = {
            "current": source.parent,
            "desktop": self._desktop_folder(),
            "downloads": self.downloads_folder,
        }
        return roots.get(choice, source.parent)

    @staticmethod
    def _path_key(path: Path) -> str:
        """Normalize resolved paths for cross-workflow lookups on Windows."""
        return os.path.normcase(str(path.resolve()))


def run() -> int:
    """Start one tray application instance and release its lock on exit."""
    app = QApplication(sys.argv)
    app.setApplicationName("Sort Pilot")
    app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    instance_lock = SingleInstanceLock(app_data / "sort-pilot.lock")
    if not instance_lock.acquire():
        QMessageBox.information(None, "Sort Pilot", "Sort Pilot이 이미 실행 중입니다.")
        return 0
    try:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "Sort Pilot", "이 시스템에서는 트레이 아이콘을 사용할 수 없습니다.")
            return 1
        controller = AppController(app)
        controller.start()
        return app.exec()
    finally:
        instance_lock.release()
