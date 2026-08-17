from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .classification import (
    AxisDecision,
    CandidateScore,
    DecisionSource,
    E5_MODEL_ID,
    EducationalClassificationOutput,
    EducationalClassificationResult,
    EvidenceContribution,
    OrganizationPlan,
    OriginalPrediction,
    PersonalExample,
    PersonalExampleVersions,
    Template,
)


@dataclass(frozen=True, slots=True)
class ApprovedEducationalPlan:
    """One frozen organization plan and its preview-correction evidence."""

    plan: OrganizationPlan
    original: EducationalClassificationResult
    fingerprint: str
    embedding: tuple[float, ...]
    lexical_evidence: tuple[str, ...]

    @property
    def subject_corrected(self) -> bool:
        """Return whether preview changed or resolved the subject label."""
        return self.original.subject.label != self.plan.classification.subject.label

    @property
    def template_corrected(self) -> bool:
        """Return whether preview changed or resolved the template label."""
        return self.original.template.label != self.plan.classification.template.label

    def personal_example(self) -> PersonalExample | None:
        """Build a separate local example only when preview corrected an axis."""
        if not self.subject_corrected and not self.template_corrected:
            return None
        final = self.plan.classification
        if final.subject.label is None or final.template.label is None:
            raise ValueError("개인 예시는 과목과 템플릿이 모두 승인되어야 합니다.")
        return PersonalExample(
            fingerprint=self.fingerprint,
            embedding=self.embedding,
            approved_subject=final.subject.label,
            approved_template=final.template.label,
            original_prediction=OriginalPrediction(
                self.original.subject.label,
                self.original.template.label,
            ),
            lexical_evidence=self.lexical_evidence,
            versions=PersonalExampleVersions(
                catalog_version=final.student.catalog_version,
                embedding_model_version=E5_MODEL_ID,
                subject_profile_version=self.original.subject.profile_version,
                template_profile_version=self.original.template.profile_version,
                subject_policy_version=self.original.subject.policy_version,
                template_policy_version=self.original.template.policy_version,
            ),
        )


def _user_decision(
    original: AxisDecision,
    selected: str,
    axis_name: str,
) -> AxisDecision:
    """Apply one exact preview selection while retaining the prior evidence."""
    if original.label == selected and not original.needs_review:
        return original
    candidate = next((item for item in original.candidates if item.label == selected), None)
    if candidate is None:
        raise ValueError(f"선택한 {axis_name}이 공급된 후보에 없습니다.")
    return AxisDecision(
        label=selected,
        raw_score=candidate.raw_score,
        calibrated_confidence=None,
        margin=original.margin,
        candidates=original.candidates,
        evidence=(
            *original.evidence,
            EvidenceContribution("user", 1.0, f"preview selected {axis_name}"),
        ),
        source=DecisionSource.USER,
        model_version=original.model_version,
        profile_version=original.profile_version,
        policy_version=original.policy_version,
        needs_review=False,
    )


def apply_preview_selection(
    original: EducationalClassificationResult,
    subject: str,
    template: str,
) -> EducationalClassificationResult:
    """Resolve or correct both axes using exact preview selections."""
    if subject not in original.student.allowed_subjects:
        raise ValueError("선택한 과목이 학생의 과목 카탈로그에 없습니다.")
    if template not in {item.value for item in Template}:
        raise ValueError("선택한 템플릿이 고정된 다섯 템플릿에 없습니다.")
    return EducationalClassificationResult(
        student=original.student,
        subject=_user_decision(original.subject, subject, "subject"),
        template=_user_decision(original.template, template, "template"),
    )


def _available_destination(
    destination: Path,
    source: Path,
    reserved: set[Path],
) -> Path:
    """Freeze the existing underscore-number collision choice before execution."""
    if destination.resolve() == source.resolve():
        return source
    if not destination.exists() and destination not in reserved:
        return destination
    counter = 1
    while True:
        candidate = destination.with_name(
            f"{destination.stem}_{counter}{destination.suffix}"
        )
        if not candidate.exists() and candidate not in reserved:
            return candidate
        counter += 1


def freeze_organization_plan(
    output: EducationalClassificationOutput,
    destination_root: Path,
    subject: str,
    template: str,
    reserved: set[Path] | None = None,
) -> ApprovedEducationalPlan:
    """Freeze exact source/destination paths after both preview axes resolve."""
    if not isinstance(output, EducationalClassificationOutput):
        raise ValueError("교육 미리보기 출력이 올바르지 않습니다.")
    classification = apply_preview_selection(output.classification, subject, template)
    base = OrganizationPlan.from_classification(
        output.source,
        destination_root,
        classification,
    )
    reserved_paths = reserved if reserved is not None else set()
    destination = _available_destination(base.destination, base.source, reserved_paths)
    reserved_paths.add(destination)
    return ApprovedEducationalPlan(
        plan=OrganizationPlan(base.source, destination, classification),
        original=output.classification,
        fingerprint=output.fingerprint,
        embedding=output.embedding,
        lexical_evidence=output.lexical_evidence,
    )


def _confirmation_message(approved: tuple[ApprovedEducationalPlan, ...]) -> str:
    """Show the exact frozen destinations in the final approval question."""
    if not approved:
        raise ValueError("최종 승인할 교육 조직 계획이 없습니다.")
    displayed = "\n".join(str(item.plan.destination) for item in approved[:10])
    remainder = f"\n외 {len(approved) - 10}개" if len(approved) > 10 else ""
    return (
        f"다음 확정 경로대로 {len(approved)}개 파일을 이동할까요?\n\n"
        f"{displayed}{remainder}"
    )


class EducationalPreviewDialog(QDialog):
    """Edit subject/template axes and freeze exact approved educational paths."""

    DESTINATION_OPTIONS = (
        ("바탕화면", "desktop"),
        ("다운로드 폴더", "downloads"),
    )

    def __init__(
        self,
        outputs: tuple[EducationalClassificationOutput, ...],
        desktop_folder: Path,
        downloads_folder: Path,
        parent=None,
    ) -> None:
        """Build the two-axis preview without moving or learning from any file."""
        super().__init__(parent)
        self.outputs = outputs
        self.desktop_folder = desktop_folder
        self.downloads_folder = downloads_folder
        self._approved: tuple[ApprovedEducationalPlan, ...] = ()
        self.setWindowTitle("Sort Pilot - 과목 및 템플릿 검토")
        self.resize(1120, 480)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Needs Review 항목의 과목과 템플릿을 선택하고 모든 목적지를 확인하세요.")
        )
        self.table = QTableWidget(len(outputs), 7)
        self.table.setHorizontalHeaderLabels(
            ["파일명", "현재 위치", "기준 위치", "과목", "템플릿", "확정 목적지", "이동"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        for row, output in enumerate(outputs):
            self._set_read_only(row, 0, output.source.name)
            self._set_read_only(row, 1, str(output.source.parent))
            destination = QComboBox()
            for label, value in self.DESTINATION_OPTIONS:
                destination.addItem(label, value)
            default = (
                "desktop"
                if output.source.resolve().is_relative_to(desktop_folder.resolve())
                else "downloads"
            )
            destination.setCurrentIndex(destination.findData(default))
            destination.currentIndexChanged.connect(self._refresh_destinations)
            self.table.setCellWidget(row, 2, destination)
            subject = self._axis_selector(
                output.classification.student.allowed_subjects,
                output.classification.subject.label,
            )
            template = self._axis_selector(
                tuple(item.value for item in Template),
                output.classification.template.label,
            )
            subject.currentIndexChanged.connect(self._refresh_destinations)
            template.currentIndexChanged.connect(self._refresh_destinations)
            self.table.setCellWidget(row, 3, subject)
            self.table.setCellWidget(row, 4, template)
            self._set_read_only(row, 5, "Needs Review")
            checked = QTableWidgetItem()
            checked.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            checked.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 6, checked)

        layout.addWidget(self.table)
        buttons = QDialogButtonBox()
        buttons.addButton("승인하고 적용", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.table.itemChanged.connect(self._refresh_destinations)
        self._refresh_destinations()

    def _set_read_only(self, row: int, column: int, value: str) -> None:
        """Set one enabled, selectable, non-editable table cell."""
        item = QTableWidgetItem(value)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, column, item)

    @staticmethod
    def _axis_selector(values: tuple[str, ...], selected: str | None) -> QComboBox:
        """Build one fixed-choice axis selector with explicit unresolved state."""
        selector = QComboBox()
        selector.addItem("선택 필요", None)
        for value in values:
            selector.addItem(value, value)
        selector.setCurrentIndex(selector.findData(selected) if selected is not None else 0)
        return selector

    def approved_plans(self) -> tuple[ApprovedEducationalPlan, ...]:
        """Return exact collision-resolved plans for every checked resolved row."""
        approved: list[ApprovedEducationalPlan] = []
        reserved: set[Path] = set()
        for row, output in enumerate(self.outputs):
            if self.table.item(row, 6).checkState() != Qt.CheckState.Checked:
                continue
            subject_selector = self.table.cellWidget(row, 3)
            template_selector = self.table.cellWidget(row, 4)
            destination_selector = self.table.cellWidget(row, 2)
            if not all(
                isinstance(item, QComboBox)
                for item in (subject_selector, template_selector, destination_selector)
            ):
                raise ValueError("교육 미리보기 선택 항목을 읽을 수 없습니다.")
            subject = subject_selector.currentData()
            template = template_selector.currentData()
            if not isinstance(subject, str) or not isinstance(template, str):
                raise ValueError("이동할 모든 파일의 과목과 템플릿을 선택하세요.")
            root = (
                self.desktop_folder
                if destination_selector.currentData() == "desktop"
                else self.downloads_folder
            )
            approved.append(
                freeze_organization_plan(output, root, subject, template, reserved)
            )
        return tuple(approved)

    def _refresh_destinations(self) -> None:
        """Show collision-resolved paths or unresolved state for checked rows."""
        reserved: set[Path] = set()
        was_blocked = self.table.blockSignals(True)
        try:
            for row, output in enumerate(self.outputs):
                move_item = self.table.item(row, 6)
                if move_item is None or move_item.checkState() != Qt.CheckState.Checked:
                    self.table.item(row, 5).setText("이동 안 함")
                    continue
                subject_selector = self.table.cellWidget(row, 3)
                template_selector = self.table.cellWidget(row, 4)
                destination_selector = self.table.cellWidget(row, 2)
                subject = (
                    subject_selector.currentData()
                    if isinstance(subject_selector, QComboBox)
                    else None
                )
                template = (
                    template_selector.currentData()
                    if isinstance(template_selector, QComboBox)
                    else None
                )
                if not isinstance(subject, str) or not isinstance(template, str):
                    self.table.item(row, 5).setText("Needs Review")
                    continue
                root = (
                    self.desktop_folder
                    if isinstance(destination_selector, QComboBox)
                    and destination_selector.currentData() == "desktop"
                    else self.downloads_folder
                )
                classification = apply_preview_selection(
                    output.classification,
                    subject,
                    template,
                )
                destination = root.joinpath(
                    *classification.folder.split("/"),
                    output.source.name,
                )
                exact = _available_destination(destination, output.source, reserved)
                reserved.add(exact)
                self.table.item(row, 5).setText(str(exact))
        finally:
            self.table.blockSignals(was_blocked)

    def _confirm(self) -> None:
        """Require resolved checked rows and freeze their exact paths once."""
        try:
            approved = self.approved_plans()
        except ValueError as exc:
            QMessageBox.warning(self, "Needs Review", str(exc))
            return
        if not approved:
            QMessageBox.information(self, "Sort Pilot", "적용할 파일을 하나 이상 선택하세요.")
            return
        approved_iterator = iter(approved)
        for row in range(self.table.rowCount()):
            if self.table.item(row, 6).checkState() == Qt.CheckState.Checked:
                self.table.item(row, 5).setText(str(next(approved_iterator).plan.destination))
        answer = QMessageBox.question(
            self,
            "최종 승인",
            _confirmation_message(approved),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._approved = approved
            self.accept()

    @property
    def frozen_plans(self) -> tuple[ApprovedEducationalPlan, ...]:
        """Return only the plans frozen by the accepted final confirmation."""
        return self._approved
