from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .models import ApprovedFileMove, FileSuggestion


class PreviewDialog(QDialog):
    def __init__(self, suggestions: list[FileSuggestion], parent=None) -> None:
        super().__init__(parent)
        self.suggestions = suggestions
        self.setWindowTitle("Sort Pilot - AI 추천 검토")
        self.resize(900, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("파일 분석 결과입니다. 저장 위치와 새 이름을 확인한 뒤 승인하세요."))

        self.table = QTableWidget(len(suggestions), 3)
        self.table.setHorizontalHeaderLabels(["파일명", "추천 정리 위치", "위치 변경"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        for row, suggestion in enumerate(suggestions):
            original_name = QTableWidgetItem(suggestion.file_name)
            original_name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, original_name)
            suggested_location = suggestion.source.parent / suggestion.folder
            self.table.setItem(row, 1, QTableWidgetItem(str(suggested_location)))
            self.table.setItem(row, 2, self._checked_item())

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
            move_approved = self.table.item(row, 2).checkState() == Qt.CheckState.Checked
            if not move_approved:
                continue
            approved.append(
                ApprovedFileMove(
                    suggestion=original,
                    folder=self._relative_folder(
                        self.table.item(row, 1).text().strip(),
                        original,
                    ),
                    move_approved=move_approved,
                )
            )
        return approved

    @staticmethod
    def _relative_folder(value: str, original: FileSuggestion) -> str:
        if not value:
            return original.folder
        path = Path(value)
        try:
            return str(path.relative_to(original.source.parent))
        except ValueError:
            return value

    def _confirm(self) -> None:
        count = len(self.approved_changes())
        if count == 0:
            QMessageBox.information(self, "Sort Pilot", "적용할 파일을 하나 이상 선택하세요.")
            return
        answer = QMessageBox.question(self, "최종 승인", f"선택한 변경 사항을 {count}개 파일에 적용할까요?")
        if answer == QMessageBox.StandardButton.Yes:
            self.accept()
