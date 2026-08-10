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

from .models import FileSuggestion


class PreviewDialog(QDialog):
    def __init__(self, suggestions: list[FileSuggestion], destination_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.suggestions = suggestions
        self.destination_root = destination_root
        self.setWindowTitle("Sort Pilot - AI 추천 검토")
        self.resize(900, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("파일 분석 결과입니다. 저장 위치와 새 이름을 확인한 뒤 승인하세요."))

        self.table = QTableWidget(len(suggestions), 4)
        self.table.setHorizontalHeaderLabels(["승인", "현재 파일명", "AI 추천 파일명", "AI 추천 저장 위치"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        for row, suggestion in enumerate(suggestions):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            checkbox.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, checkbox)
            self.table.setItem(row, 1, QTableWidgetItem(suggestion.file_name))
            self.table.setItem(row, 2, QTableWidgetItem(suggestion.suggested_name))
            self.table.setItem(row, 3, QTableWidgetItem(str(destination_root / suggestion.folder)))

        layout.addWidget(self.table)
        buttons = QDialogButtonBox()
        self.organize_button = buttons.addButton("승인하고 적용", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_suggestions(self) -> list[FileSuggestion]:
        selected: list[FileSuggestion] = []
        for row, original in enumerate(self.suggestions):
            if self.table.item(row, 0).checkState() != Qt.CheckState.Checked:
                continue
            selected.append(
                FileSuggestion(
                    file_path=original.file_path,
                    file_name=original.file_name,
                    suggested_name=self.table.item(row, 2).text().strip() or original.file_name,
                    folder=original.folder,
                    reason=original.reason,
                )
            )
        return selected

    def _confirm(self) -> None:
        count = len(self.selected_suggestions())
        if count == 0:
            QMessageBox.information(self, "Sort Pilot", "적용할 파일을 하나 이상 선택하세요.")
            return
        answer = QMessageBox.question(self, "최종 승인", f"추천 내용대로 {count}개 파일을 이동하고 이름을 바꿀까요?")
        if answer == QMessageBox.StandardButton.Yes:
            self.accept()
