from __future__ import annotations

from pathlib import Path, PurePosixPath

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .models import ApprovedFileMove, FileSuggestion
from .classifier_engine.hierarchy import UNSORTED_TOPIC
from .classifier_engine.topics import validate_topic_name


class PreviewDialog(QDialog):
    """Review and edit classifier destinations before any file is moved."""

    USER_TYPES = ("선생님", "학생", "직장인")

    DESTINATION_OPTIONS = (
        ("바탕화면", "desktop"),
        ("다운로드 폴더", "downloads"),
    )

    def __init__(
        self,
        suggestions: list[FileSuggestion],
        desktop_folder: Path,
        downloads_folder: Path,
        user_type: str | None = None,
        parent=None,
    ) -> None:
        """Build an editable move preview for a completed analysis batch."""
        super().__init__(parent)
        self.suggestions = sorted(
            suggestions,
            key=lambda suggestion: (suggestion.folder.casefold(), suggestion.file_name.casefold()),
        )
        self.setWindowTitle("Sort Pilot - AI 추천 검토")
        self.resize(900, 460)

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("사용자 유형:"))
        self.user_type_combo = QComboBox()
        self.user_type_combo.addItem("유형 선택", None)
        for option in self.USER_TYPES:
            self.user_type_combo.addItem(option, option)
        if user_type in self.USER_TYPES:
            self.user_type_combo.setCurrentIndex(self.user_type_combo.findData(user_type))
        self.confirmed_user_type = user_type if user_type in self.USER_TYPES else None
        self.user_type_combo.setEnabled(False)
        controls.addWidget(self.user_type_combo)
        confirm_type = QPushButton("확인")
        confirm_type.setVisible(False)
        controls.addWidget(confirm_type)
        self.user_type_status = QLabel(
            f"{self.confirmed_user_type} 선택됨" if self.confirmed_user_type else ""
        )
        controls.addWidget(self.user_type_status)
        controls.addSpacing(20)
        controls.addWidget(QLabel("폴더 위치:"))
        self.bulk_location_combo = QComboBox()
        self.bulk_location_combo.addItem("일괄 선택", None)
        for label, value in self.DESTINATION_OPTIONS:
            self.bulk_location_combo.addItem(label, value)
        self.bulk_location_combo.currentIndexChanged.connect(self._apply_bulk_location)
        controls.addWidget(self.bulk_location_combo)
        controls.addStretch()
        layout.addLayout(controls)
        layout.addWidget(QLabel("파일별 기준 위치와 정리 폴더를 확인한 뒤 승인하세요."))

        self.table = QTableWidget(len(suggestions), 5)
        self.table.setHorizontalHeaderLabels(
            ["파일명", "현재 위치", "기준 위치", "정리 경로", "이동"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        for row, suggestion in enumerate(self.suggestions):
            original_name = QTableWidgetItem(suggestion.file_name)
            original_name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, original_name)
            current_location = QTableWidgetItem(str(suggestion.source.parent))
            current_location.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, current_location)
            destination_selector = QComboBox()
            for label, value in self.DESTINATION_OPTIONS:
                destination_selector.addItem(label, value)
            default_destination = (
                "desktop"
                if suggestion.source.resolve().is_relative_to(desktop_folder.resolve())
                else "downloads"
            )
            destination_selector.setCurrentIndex(destination_selector.findData(default_destination))
            self.table.setCellWidget(row, 2, destination_selector)
            parts = PurePosixPath(suggestion.folder.replace("\\", "/")).parts
            organization_path = (
                "/".join(parts) if len(parts) >= 2 else f"{parts[0] if parts else '기타'}/{UNSORTED_TOPIC}"
            )
            path_selector = QComboBox()
            path_selector.setEditable(True)
            path_selector.addItem(organization_path)
            path_selector.setCurrentText(organization_path)
            self.table.setCellWidget(row, 3, path_selector)
            self.table.setItem(row, 4, self._checked_item())

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
            move_approved = self.table.item(row, 4).checkState() == Qt.CheckState.Checked
            if not move_approved:
                continue
            selector = self.table.cellWidget(row, 2)
            if not isinstance(selector, QComboBox):
                continue
            approved.append(
                ApprovedFileMove(
                    suggestion=original,
                    destination_root=str(selector.currentData()),
                    folder=self._organization_path(row),
                    move_approved=move_approved,
                )
            )
        return approved

    def _organization_path(self, row: int) -> str:
        """Validate and return one editable full relative organization path."""
        selector = self.table.cellWidget(row, 3)
        value = selector.currentText().strip() if isinstance(selector, QComboBox) else ""
        path = PurePosixPath(value.replace("\\", "/"))
        parts = path.parts
        if path.is_absolute() or Path(value).is_absolute() or not 2 <= len(parts) <= 3:
            raise ValueError("정리 경로는 2~3단계 상대 경로로 입력해 주세요.")
        return "/".join(validate_topic_name(part) for part in parts)

    def selected_user_type(self) -> str | None:
        """Return the user type confirmed before opening this preview."""
        return self.confirmed_user_type

    def _apply_bulk_location(self) -> None:
        """Apply the selected destination root to every preview row."""
        destination = self.bulk_location_combo.currentData()
        if destination is None:
            return
        for row in range(self.table.rowCount()):
            selector = self.table.cellWidget(row, 2)
            if isinstance(selector, QComboBox):
                index = selector.findData(destination)
                if index >= 0:
                    selector.setCurrentIndex(index)

    def _reset_user_type_confirmation(self) -> None:
        """Clear the legacy user-type confirmation state."""
        self.confirmed_user_type = None
        self.user_type_status.clear()

    def _confirm_user_type(self) -> None:
        """Confirm the currently selected legacy user type when enabled."""
        user_type = self.user_type_combo.currentData()
        if user_type is None:
            QMessageBox.information(self, "사용자 유형 선택", "사용자 유형을 선택해 주세요.")
            return
        self.confirmed_user_type = str(user_type)
        self.user_type_status.setText(f"{user_type} 선택됨")

    def _confirm(self) -> None:
        """Require at least one move and explicit final confirmation."""
        try:
            changes = self.approved_changes()
        except ValueError as exc:
            QMessageBox.warning(self, "잘못된 정리 경로", str(exc))
            return
        count = len(changes)
        if count == 0:
            QMessageBox.information(self, "Sort Pilot", "적용할 파일을 하나 이상 선택하세요.")
            return
        answer = QMessageBox.question(self, "최종 승인", f"선택한 변경 사항을 {count}개 파일에 적용할까요?")
        if answer == QMessageBox.StandardButton.Yes:
            self.accept()
