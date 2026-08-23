from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .models import ApprovedFileMove, FileSuggestion
from .classifier_engine.hierarchy import TYPE_FAMILIES, UNSORTED_TOPIC, route_type
from .classifier_engine.topics import TopicProfile, validate_topic_name


class PreviewDialog(QDialog):
    """Review and edit classifier destinations before any file is moved."""

    DESTINATION_OPTIONS = (("Sandbox", "sandbox"),)

    def __init__(
        self,
        suggestions: list[FileSuggestion],
        desktop_folder: Path,
        downloads_folder: Path,
        profiles: list[TopicProfile] | None = None,
        parent=None,
    ) -> None:
        """Build an editable move preview for a completed analysis batch."""
        super().__init__(parent)
        self.suggestions = suggestions
        self.profiles = profiles or []
        self.setWindowTitle("Sort Pilot - AI 추천 검토")
        self.resize(900, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("파일별 기준 위치와 정리 폴더를 확인한 뒤 승인하세요."))

        self.table = QTableWidget(len(suggestions), 6)
        self.table.setHorizontalHeaderLabels(
            ["파일명", "현재 위치", "기준 위치", "파일 유형", "주제 / 하위 경로", "이동"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        for row, suggestion in enumerate(suggestions):
            original_name = QTableWidgetItem(suggestion.file_name)
            original_name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, original_name)
            current_location = QTableWidgetItem(str(suggestion.source.parent))
            current_location.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, current_location)
            destination_selector = QComboBox()
            for label, value in self.DESTINATION_OPTIONS:
                destination_selector.addItem(label, value)
            default_destination = "sandbox"
            destination_selector.setCurrentIndex(destination_selector.findData(default_destination))
            self.table.setCellWidget(row, 2, destination_selector)
            parts = Path(suggestion.folder).parts
            family = parts[0] if parts and parts[0] in TYPE_FAMILIES else route_type(suggestion.source)
            topic_path = Path(*parts[1:]).as_posix() if len(parts) > 1 else UNSORTED_TOPIC
            family_item = QTableWidgetItem(family)
            family_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 3, family_item)
            topic_selector = QComboBox()
            topic_selector.setEditable(True)
            topic_selector.addItem(UNSORTED_TOPIC)
            topic_selector.addItems(
                profile.name
                for profile in self.profiles
                if profile.enabled and profile.family == family
            )
            topic_selector.setCurrentText(topic_path)
            self.table.setCellWidget(row, 4, topic_selector)
            self.table.setItem(row, 5, self._checked_item())

        layout.addWidget(self.table)
        buttons = QDialogButtonBox()
        self.organize_button = buttons.addButton("승인하고 적용", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _checked_item() -> QTableWidgetItem:
        """Create a checked, user-toggleable table item."""
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        return item

    def approved_changes(self) -> list[ApprovedFileMove]:
        """Translate checked table rows into validated move requests."""
        approved: list[ApprovedFileMove] = []
        for row, original in enumerate(self.suggestions):
            move_approved = self.table.item(row, 5).checkState() == Qt.CheckState.Checked
            if not move_approved:
                continue
            selector = self.table.cellWidget(row, 2)
            if not isinstance(selector, QComboBox):
                continue
            approved.append(
                ApprovedFileMove(
                    suggestion=original,
                    destination_root=str(selector.currentData()),
                    folder=self._hierarchical_folder(row),
                    move_approved=move_approved,
                )
            )
        return approved

    def _hierarchical_folder(self, row: int) -> str:
        """Reconstruct an approved path while keeping the first-level type immutable."""
        family = self.table.item(row, 3).text()
        selector = self.table.cellWidget(row, 4)
        topic = selector.currentText().strip() if isinstance(selector, QComboBox) else ""
        if not topic or topic == UNSORTED_TOPIC:
            return f"{family}/{UNSORTED_TOPIC}"
        return f"{family}/{validate_topic_name(topic)}"

    def _confirm(self) -> None:
        """Require at least one move and explicit final confirmation."""
        try:
            changes = self.approved_changes()
        except ValueError as exc:
            QMessageBox.warning(self, "잘못된 주제 이름", str(exc))
            return
        count = len(changes)
        if count == 0:
            QMessageBox.information(self, "Sort Pilot", "적용할 파일을 하나 이상 선택하세요.")
            return
        answer = QMessageBox.question(self, "최종 승인", f"선택한 변경 사항을 {count}개 파일에 적용할까요?")
        if answer == QMessageBox.StandardButton.Yes:
            self.accept()
