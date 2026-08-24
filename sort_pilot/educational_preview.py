from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
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


class _ClickOnlyComboList(QListView):
    """Keep combo-box options clickable without drag-to-select behavior."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Configure an option list that never starts or accepts a drag."""
        super().__init__(parent)
        self._dragged = False
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start a fresh click gesture."""
        self._dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Consume left-button movement instead of changing an option."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._dragged = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Ignore the release that completes a drag gesture."""
        if self._dragged:
            self._dragged = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ClickOnlyComboBox(QComboBox):
    """Allow value changes by click only, never by drag or mouse wheel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Install the click-only popup list for this selector."""
        super().__init__(parent)
        self._dragged = False
        self.setView(_ClickOnlyComboList(self))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start a fresh click gesture."""
        self._dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Consume left-button movement instead of drag-selecting an option."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._dragged = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Ignore the release that completes a drag gesture."""
        if self._dragged:
            self._dragged = False
            self.hidePopup()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Prevent accidental value changes while scrolling the dialog."""
        event.ignore()


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


REVIEW_GROUP_KEY = "__needs_review__"


@dataclass(frozen=True, slots=True)
class PreviewGroup:
    """One destination summary row and the source rows represented by it."""

    key: str
    title: str
    row_indexes: tuple[int, ...]
    representative_file: str
    needs_review: bool = False

    @property
    def count(self) -> int:
        """Return the number of files represented by the summary."""
        return len(self.row_indexes)

    @property
    def file_preview(self) -> str:
        """Render one representative filename and the remaining count."""
        remainder = self.count - 1
        return (
            self.representative_file
            if remainder == 0
            else f"{self.representative_file} 외 {remainder}개"
        )


def build_preview_groups(
    outputs: tuple[EducationalClassificationOutput, ...],
) -> tuple[PreviewGroup, ...]:
    """Group initial AI results by relative destination and review state."""
    grouped_rows: dict[str, list[int]] = {}
    titles: dict[str, str] = {}
    for row, output in enumerate(outputs):
        classification = output.classification
        if classification.needs_review:
            key = REVIEW_GROUP_KEY
            title = "확인이 필요한 파일"
        else:
            key = classification.folder
            title = classification.folder
        grouped_rows.setdefault(key, []).append(row)
        titles[key] = title

    keys = sorted(
        grouped_rows,
        key=lambda key: (key == REVIEW_GROUP_KEY, titles[key].casefold()),
    )
    groups: list[PreviewGroup] = []
    for key in keys:
        rows = tuple(
            sorted(
                grouped_rows[key],
                key=lambda row: outputs[row].source.name.casefold(),
            )
        )
        groups.append(
            PreviewGroup(
                key=key,
                title=titles[key],
                row_indexes=rows,
                representative_file=outputs[rows[0]].source.name,
                needs_review=key == REVIEW_GROUP_KEY,
            )
        )
    return tuple(groups)


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


def _confirmation_message(
    approved: tuple[ApprovedEducationalPlan, ...],
    *,
    test_mode: bool = False,
) -> str:
    """Show grouped destinations with one exact representative per folder."""
    if not approved:
        raise ValueError("최종 승인할 교육 조직 계획이 없습니다.")
    groups: dict[Path, list[Path]] = {}
    for item in approved:
        groups.setdefault(item.plan.destination.parent, []).append(item.plan.destination)
    displayed_groups: list[str] = []
    for parent, destinations in sorted(groups.items(), key=lambda item: str(item[0]).casefold()):
        destinations.sort(key=lambda path: path.name.casefold())
        representative = destinations[0]
        remainder = len(destinations) - 1
        preview = (
            str(representative)
            if remainder == 0
            else f"{representative} 외 {remainder}개"
        )
        displayed_groups.append(
            f"{parent}  ·  파일 {len(destinations)}개\n  {preview}"
        )
    action = f"다음 확정 경로대로 {len(approved)}개 파일을 이동할까요?"
    return f"{action}\n\n" + "\n\n".join(displayed_groups)


class EducationalPreviewDialog(QDialog):
    """Edit subject/template axes and freeze exact approved educational paths."""

    SUMMARY_DESTINATION_COLUMN_WIDTH = 240
    SUMMARY_COUNT_COLUMN_WIDTH = 180

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
        *,
        test_mode: bool = False,
    ) -> None:
        """Build the two-axis preview without moving or learning from any file."""
        super().__init__(parent)
        self.outputs = outputs
        self.desktop_folder = desktop_folder
        self.downloads_folder = downloads_folder
        self.test_mode = test_mode
        self.groups = build_preview_groups(outputs)
        self._groups_by_key = {group.key: group for group in self.groups}
        self._group_destination_selectors: dict[str, QComboBox] = {}
        self._approved: tuple[ApprovedEducationalPlan, ...] = ()
        self.setWindowTitle("Sort Pilot - 과목 및 템플릿 검토")
        self.resize(900, min(680, 220 + 58 * max(1, len(self.groups))))
        self.setStyleSheet(
            "QDialog { background: #f5f5f5; color: #171717; }"
            "QLabel#previewTitle { font-size: 24px; font-weight: 700; color: #000000; }"
            "QLabel#previewSubtitle { color: #525252; font-size: 13px; }"
            "QFrame#bulkDestinationCard { background: #ffffff; border: 1px solid #d4d4d4; "
            "border-radius: 12px; }"
            "QLabel#bulkDestinationTitle { font-size: 14px; font-weight: 700; color: #171717; }"
            "QLabel#bulkDestinationHint { color: #737373; font-size: 12px; }"
            "QLabel#summaryPath { color: #171717; font-size: 13px; font-weight: 700; }"
            "QLabel#summaryFilePreview { color: #8a8a8a; font-size: 12px; font-weight: 400; }"
            "QLabel#summaryPath[review=\"true\"] { color: #dc2626; }"
            "QLabel#summaryFilePreview[review=\"true\"] { color: #ef4444; }"
            "QComboBox { background: #ffffff; border: 1px solid #a3a3a3; border-radius: 8px; "
            "padding: 7px 30px 7px 10px; min-height: 22px; color: #171717; }"
            "QComboBox:hover { border-color: #525252; }"
            "QComboBox:focus { border: 2px solid #000000; padding: 6px 29px 6px 9px; }"
            "QComboBox::drop-down { border: 0; width: 28px; }"
            "QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #a3a3a3; "
            "selection-background-color: #e5e5e5; selection-color: #000000; outline: 0; }"
            "QTreeWidget#destinationSummary { background: #ffffff; border: 1px solid #d4d4d4; "
            "border-radius: 12px; outline: 0; }"
            "QTreeWidget#destinationSummary::item { padding: 8px; border-bottom: 1px solid #eeeeee; }"
            "QTreeWidget#destinationSummary::item:hover { background: #fafafa; }"
            "QTreeWidget#destinationSummary::item:selected { background: #e5e5e5; color: #000000; }"
            "QHeaderView::section { background: #f5f5f5; color: #404040; border: 0; "
            "border-bottom: 1px solid #d4d4d4; padding: 9px 10px; font-weight: 600; }"
            "QTableWidget#groupDetailTable { background: #ffffff; border: 1px solid #d4d4d4; "
            "border-radius: 10px; gridline-color: #eeeeee; outline: 0; }"
            "QTableWidget#groupDetailTable::item { padding: 6px 8px; border-bottom: 1px solid #eeeeee; }"
            "QTableWidget#groupDetailTable::item:selected { background: #e5e5e5; color: #000000; }"
            "QPushButton { background: #ffffff; color: #171717; border: 1px solid #a3a3a3; "
            "border-radius: 8px; padding: 8px 16px; min-width: 72px; font-weight: 600; }"
            "QPushButton:hover { background: #f5f5f5; border-color: #525252; }"
            "QPushButton:pressed { background: #e5e5e5; }"
            "QPushButton#primaryAction { background: #000000; color: #ffffff; border: 1px solid #000000; }"
            "QPushButton#primaryAction:hover { background: #262626; border-color: #262626; }"
            "QPushButton#primaryAction:pressed { background: #404040; border-color: #404040; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("정리 결과 미리보기")
        title.setObjectName("previewTitle")
        layout.addWidget(title)
        review_count = sum(group.count for group in self.groups if group.needs_review)
        description = (
            f"{len(outputs)}개 파일을 {len(self.groups) - (1 if review_count else 0)}개 경로로 정리합니다. "
            "전체 옮길 위치를 한 번 선택하고, 필요한 경로만 다르게 지정할 수 있습니다. "
            "경로 행을 누르면 포함 파일을 확인할 수 있습니다."
        )
        if review_count:
            description += f" 확인이 필요한 파일은 {review_count}개입니다."
        subtitle = QLabel(description)
        subtitle.setObjectName("previewSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        bulk_destination_card = QFrame()
        bulk_destination_card.setObjectName("bulkDestinationCard")
        bulk_destination_row = QHBoxLayout(bulk_destination_card)
        bulk_destination_row.setContentsMargins(16, 12, 16, 12)
        bulk_destination_text = QVBoxLayout()
        bulk_destination_text.setSpacing(2)
        bulk_destination_title = QLabel("전체 옮길 위치")
        bulk_destination_title.setObjectName("bulkDestinationTitle")
        bulk_destination_hint = QLabel(
            "확인이 필요한 파일을 제외한 모든 정리 경로에 적용됩니다."
        )
        bulk_destination_hint.setObjectName("bulkDestinationHint")
        bulk_destination_text.addWidget(bulk_destination_title)
        bulk_destination_text.addWidget(bulk_destination_hint)
        bulk_destination_row.addLayout(bulk_destination_text)
        bulk_destination_row.addStretch(1)
        self.bulk_destination_selector = ClickOnlyComboBox()
        self.bulk_destination_selector.setMinimumWidth(
            self.SUMMARY_DESTINATION_COLUMN_WIDTH
        )
        self.bulk_destination_selector.addItem("전체 옮길 위치 선택", None)
        for label, value in self.DESTINATION_OPTIONS:
            self.bulk_destination_selector.addItem(label, value)
        self.bulk_destination_selector.currentIndexChanged.connect(
            self._apply_bulk_destination
        )
        bulk_destination_row.addWidget(self.bulk_destination_selector)
        layout.addWidget(bulk_destination_card)

        self.summary = QTreeWidget()
        self.summary.setObjectName("destinationSummary")
        self.summary.setHeaderLabels(
            ["정리 경로 / 파일 미리보기", "옮길 위치", "파일 수"]
        )
        self.summary.setRootIsDecorated(False)
        self.summary.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.summary.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary.header().setStretchLastSection(False)
        self.summary.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.summary.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.summary.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.summary.setColumnWidth(1, self.SUMMARY_DESTINATION_COLUMN_WIDTH)
        self.summary.setColumnWidth(2, self.SUMMARY_COUNT_COLUMN_WIDTH)
        self.summary.headerItem().setTextAlignment(
            2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.summary.setMinimumHeight(min(320, 34 + 64 * max(1, len(self.groups))))
        self.summary.setMaximumHeight(320)
        for group in self.groups:
            item = QTreeWidgetItem()
            item.setData(0, Qt.ItemDataRole.UserRole, group.key)
            item.setToolTip(0, f"{group.title}\n{group.file_preview}")
            item.setText(2, f"파일 {group.count}개  ›")
            item.setTextAlignment(
                2,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            item.setSizeHint(0, QSize(0, 64))
            if group.needs_review:
                warning_color = QColor("#dc2626")
                item.setForeground(0, warning_color)
                item.setForeground(2, warning_color)
                warning_font = QFont(item.font(0))
                warning_font.setBold(True)
                item.setFont(0, warning_font)
            self.summary.addTopLevelItem(item)
            summary_text = QWidget()
            summary_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            summary_text.setAccessibleName(f"{group.title}, {group.file_preview}")
            summary_text_layout = QVBoxLayout(summary_text)
            summary_text_layout.setContentsMargins(8, 4, 8, 4)
            summary_text_layout.setSpacing(2)
            path_label = QLabel(group.title)
            path_label.setObjectName("summaryPath")
            path_label.setProperty("review", group.needs_review)
            path_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            file_preview_label = QLabel(group.file_preview)
            file_preview_label.setObjectName("summaryFilePreview")
            file_preview_label.setProperty("review", group.needs_review)
            file_preview_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            summary_text_layout.addWidget(path_label)
            summary_text_layout.addWidget(file_preview_label)
            self.summary.setItemWidget(item, 0, summary_text)
            destination = ClickOnlyComboBox()
            destination.setMinimumWidth(self.SUMMARY_DESTINATION_COLUMN_WIDTH)
            destination.addItem("옮길 위치 선택", None)
            for label, value in self.DESTINATION_OPTIONS:
                destination.addItem(label, value)
            destination.currentIndexChanged.connect(
                lambda _index, key=group.key: self._apply_group_destination(key)
            )
            self._group_destination_selectors[group.key] = destination
            self.summary.setItemWidget(item, 1, destination)
        self.summary.itemClicked.connect(self._open_group_details)
        layout.addWidget(self.summary)

        self.table = QTableWidget(len(outputs), 7)
        self.table.setHorizontalHeaderLabels(
            ["파일명", "현재 위치", "기준 위치", "과목", "템플릿", "확정 목적지", "이동"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
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
            destination = ClickOnlyComboBox()
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

        self.table.hide()
        buttons = QDialogButtonBox()
        self.organize_button = buttons.addButton(
            "정리 승인",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.organize_button.setObjectName("primaryAction")
        cancel_button = buttons.addButton(
            "취소",
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        cancel_button.setObjectName("secondaryAction")
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.table.itemChanged.connect(self._refresh_destinations)
        self._refresh_destinations()
        if self.groups:
            self.summary.setCurrentItem(self.summary.topLevelItem(0))

    def _open_group_details(self, item: QTreeWidgetItem, _column: int) -> None:
        """Open per-file controls only after the user selects one summary row."""
        if _column == 1:
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        group = self._groups_by_key.get(key)
        if group is None:
            return
        dialog = QDialog(self)
        dialog.setObjectName("groupDetailDialog")
        dialog.setWindowTitle(f"{group.title} - 포함 파일")
        dialog.resize(940, min(680, 190 + group.count * 46))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        heading = QLabel(f"{group.title} · 파일 {group.count}개")
        heading.setObjectName("groupDetailHeading")
        heading.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(heading)
        details = QTableWidget(group.count, 5)
        details.setObjectName("groupDetailTable")
        details.setHorizontalHeaderLabels(
            ["파일명", "현재 위치", "과목", "템플릿", "이동"]
        )
        details.verticalHeader().setVisible(False)
        details.verticalHeader().setDefaultSectionSize(46)
        details.verticalHeader().setMinimumSectionSize(46)
        details.setShowGrid(False)
        details.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        details.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        details.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        details.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        details.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column, width in ((2, 150), (3, 150), (4, 72)):
            details.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.Fixed
            )
            details.setColumnWidth(column, width)

        editors: list[tuple[int, QComboBox, QComboBox, QTableWidgetItem]] = []
        sorted_rows = sorted(
            group.row_indexes,
            key=lambda row: (
                self.table.item(row, 0).text().casefold(),
                self.table.item(row, 1).text().casefold(),
            ),
        )
        for detail_row, source_row in enumerate(sorted_rows):
            for column in (0, 1):
                source_item = self.table.item(source_row, column)
                copied = QTableWidgetItem(source_item.text())
                copied.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                copied.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                details.setItem(detail_row, column, copied)

            cloned_selectors: list[QComboBox] = []
            for detail_column, source_column in ((2, 3), (3, 4)):
                source_selector = self.table.cellWidget(source_row, source_column)
                clone = ClickOnlyComboBox()
                if isinstance(source_selector, QComboBox):
                    for option in range(source_selector.count()):
                        clone.addItem(
                            source_selector.itemText(option),
                            source_selector.itemData(option),
                        )
                    clone.setCurrentIndex(clone.findData(source_selector.currentData()))
                details.setCellWidget(detail_row, detail_column, clone)
                cloned_selectors.append(clone)

            source_move = self.table.item(source_row, 6)
            move = QTableWidgetItem()
            move.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            move.setCheckState(source_move.checkState())
            move.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            details.setItem(detail_row, 4, move)
            editors.append(
                (
                    source_row,
                    cloned_selectors[0],
                    cloned_selectors[1],
                    move,
                )
            )

        layout.addWidget(details)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("적용")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        for source_row, subject, template, move in editors:
            for column, editor in ((3, subject), (4, template)):
                target = self.table.cellWidget(source_row, column)
                if isinstance(target, QComboBox):
                    target.setCurrentIndex(target.findData(editor.currentData()))
            self.table.item(source_row, 6).setCheckState(move.checkState())
        self._refresh_destinations()

    def _apply_group_destination(self, key: str) -> None:
        """Apply one Desktop/Downloads choice to every file in a summary group."""
        group = self._groups_by_key.get(key)
        selector = self._group_destination_selectors.get(key)
        if group is None or selector is None:
            return
        destination = selector.currentData()
        if isinstance(destination, str):
            for row in group.row_indexes:
                target = self.table.cellWidget(row, 2)
                if isinstance(target, QComboBox):
                    target.setCurrentIndex(target.findData(destination))
            self._refresh_destinations()
        self._sync_bulk_destination()

    def _apply_bulk_destination(self, _index: int) -> None:
        """Apply one root to resolved groups while leaving Needs Review untouched."""
        destination = self.bulk_destination_selector.currentData()
        if not isinstance(destination, str):
            return
        for group in self.groups:
            if group.needs_review:
                continue
            selector = self._group_destination_selectors[group.key]
            selector.blockSignals(True)
            selector.setCurrentIndex(selector.findData(destination))
            selector.blockSignals(False)
            for row in group.row_indexes:
                row_selector = self.table.cellWidget(row, 2)
                if isinstance(row_selector, QComboBox):
                    row_selector.blockSignals(True)
                    row_selector.setCurrentIndex(row_selector.findData(destination))
                    row_selector.blockSignals(False)
        self._refresh_destinations()

    def _sync_bulk_destination(self) -> None:
        """Show the shared group destination or the unresolved mixed state."""
        destinations = {
            self._group_destination_selectors[group.key].currentData()
            for group in self.groups
            if not group.needs_review
        }
        destination = next(iter(destinations)) if len(destinations) == 1 else None
        index = self.bulk_destination_selector.findData(destination)
        self.bulk_destination_selector.blockSignals(True)
        self.bulk_destination_selector.setCurrentIndex(max(0, index))
        self.bulk_destination_selector.blockSignals(False)

    def _update_approve_button(self) -> None:
        """Keep the primary action explicit about how many files will move."""
        count = sum(
            self.table.item(row, 6).checkState() == Qt.CheckState.Checked
            for row in range(self.table.rowCount())
        )
        self.organize_button.setText(f"{count}개 파일 이동")

    def _set_read_only(self, row: int, column: int, value: str) -> None:
        """Set one enabled, selectable, non-editable table cell."""
        item = QTableWidgetItem(value)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, column, item)

    @staticmethod
    def _axis_selector(values: tuple[str, ...], selected: str | None) -> QComboBox:
        """Build one fixed-choice axis selector with explicit unresolved state."""
        selector = ClickOnlyComboBox()
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
        self._update_approve_button()

    def _confirm(self) -> None:
        """Require resolved checked rows and freeze their exact paths once."""
        missing_destinations = [
            group.title
            for group in self.groups
            if any(
                self.table.item(row, 6).checkState() == Qt.CheckState.Checked
                for row in group.row_indexes
            )
            and not isinstance(
                self._group_destination_selectors[group.key].currentData(),
                str,
            )
        ]
        if missing_destinations:
            QMessageBox.warning(
                self,
                "옮길 위치 선택",
                "각 경로에서 바탕화면 또는 다운로드 폴더를 선택하세요.",
            )
            return
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
            _confirmation_message(approved, test_mode=self.test_mode),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._approved = approved
            self.accept()

    @property
    def frozen_plans(self) -> tuple[ApprovedEducationalPlan, ...]:
        """Return only the plans frozen by the accepted final confirmation."""
        return self._approved
