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


class PreviewDialog(QDialog):
    DESTINATION_OPTIONS = (
        ("바탕화면", "desktop"),
        ("다운로드 폴더", "downloads"),
    )

    def __init__(
        self,
        suggestions: list[FileSuggestion],
        desktop_folder: Path,
        downloads_folder: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.suggestions = suggestions
        self.setWindowTitle("Sort Pilot - AI 추천 검토")
        self.resize(900, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("파일별 기준 위치와 정리 폴더를 확인한 뒤 승인하세요."))

        self.table = QTableWidget(len(suggestions), 5)
        self.table.setHorizontalHeaderLabels(
            ["파일명", "현재 위치", "기준 위치", "옮길 위치", "이동"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

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
            default_destination = (
                "desktop"
                if suggestion.source.parent.resolve() == desktop_folder.resolve()
                else "downloads"
            )
            destination_selector.setCurrentIndex(
                destination_selector.findData(default_destination)
            )
            self.table.setCellWidget(row, 2, destination_selector)
            self.table.setItem(row, 3, QTableWidgetItem(suggestion.folder))
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
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        return item

    def approved_changes(self) -> list[ApprovedFileMove]:
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
                    folder=self.table.item(row, 3).text().strip() or original.folder,
                    move_approved=move_approved,
                )
            )
        return approved

    def _confirm(self) -> None:
        count = len(self.approved_changes())
        if count == 0:
            QMessageBox.information(self, "Sort Pilot", "적용할 파일을 하나 이상 선택하세요.")
            return
        answer = QMessageBox.question(self, "최종 승인", f"선택한 변경 사항을 {count}개 파일에 적용할까요?")
        if answer == QMessageBox.StandardButton.Yes:
            self.accept()
