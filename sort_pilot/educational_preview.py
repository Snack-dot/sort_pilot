from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
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


def _confirmation_message(approved: tuple[ApprovedEducationalPlan, ...]) -> str:
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
    return (
        f"다음 확정 경로대로 {len(approved)}개 파일을 이동할까요?\n\n"
        + "\n\n".join(displayed_groups)
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
        self.groups = build_preview_groups(outputs)
        self._groups_by_key = {group.key: group for group in self.groups}
        self._approved: tuple[ApprovedEducationalPlan, ...] = ()
        self.setWindowTitle("Sort Pilot - 과목 및 템플릿 검토")
        self.resize(1120, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("정리 결과 미리보기")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        review_count = sum(group.count for group in self.groups if group.needs_review)
        description = (
            f"{len(outputs)}개 파일을 {len(self.groups) - (1 if review_count else 0)}개 경로로 정리합니다. "
            "경로를 선택하면 포함된 파일과 확정 목적지를 확인할 수 있습니다."
        )
        if review_count:
            description += f" 확인이 필요한 파일은 {review_count}개입니다."
        subtitle = QLabel(description)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #475569; font-size: 13px;")
        layout.addWidget(subtitle)

        self.summary = QTreeWidget()
        self.summary.setHeaderLabels(["정리 경로 / 파일 미리보기", "파일 수"])
        self.summary.setRootIsDecorated(False)
        self.summary.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.summary.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.summary.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.summary.setMinimumHeight(min(280, 34 + 58 * max(1, len(self.groups))))
        self.summary.setMaximumHeight(280)
        self.summary.setStyleSheet(
            "QTreeWidget { border: 1px solid #dbe3ec; border-radius: 8px; }"
            "QTreeWidget::item { padding: 6px; }"
            "QTreeWidget::item:selected { background: #e8f0fe; color: #0f172a; }"
        )
        for group in self.groups:
            item = QTreeWidgetItem()
            item.setData(0, Qt.ItemDataRole.UserRole, group.key)
            item.setText(0, f"{group.title}\n{group.file_preview}")
            item.setText(1, f"파일 {group.count}개  ›")
            item.setSizeHint(0, QSize(0, 56))
            if group.needs_review:
                warning_color = QColor("#b45309")
                item.setForeground(0, warning_color)
                item.setForeground(1, warning_color)
                warning_font = QFont(item.font(0))
                warning_font.setBold(True)
                item.setFont(0, warning_font)
            self.summary.addTopLevelItem(item)
        self.summary.itemSelectionChanged.connect(self._summary_selection_changed)
        layout.addWidget(self.summary)

        self.detail_label = QLabel()
        self.detail_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(self.detail_label)

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
        self.organize_button = buttons.addButton(
            "정리 승인",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.table.itemChanged.connect(self._refresh_destinations)
        self._refresh_destinations()
        if self.groups:
            self.summary.setCurrentItem(self.summary.topLevelItem(0))

    def _summary_selection_changed(self) -> None:
        """Filter the detail table to the selected destination summary."""
        selected = self.summary.selectedItems()
        if not selected:
            return
        key = selected[0].data(0, Qt.ItemDataRole.UserRole)
        group = self._groups_by_key.get(key)
        if group is None:
            return
        visible_rows = set(group.row_indexes)
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, row not in visible_rows)
        self.detail_label.setText(f"{group.title} · 파일 {group.count}개")

    def _update_approve_button(self) -> None:
        """Keep the primary action explicit about how many files will move."""
        count = sum(
            self.table.item(row, 6).checkState() == Qt.CheckState.Checked
            for row in range(self.table.rowCount())
        )
        self.organize_button.setText(f"{count}개 파일 정리 승인")

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
        self._update_approve_button()

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
