from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from organizer import move_file


class BatchPreviewDialog(QDialog):
    def __init__(self, results: list[dict]) -> None:
        super().__init__()
        self.results = results
        self.setWindowTitle("바탕화면 정리 미리보기")
        self.resize(820, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "폴더, 바로가기, 실행파일은 제외했습니다. "
            "정리할 일반 파일을 확인하세요."
        ))

        self.table = QTableWidget(len(results), 4)
        self.table.setHorizontalHeaderLabels(
            ["정리", "파일", "추천 폴더", "분류 이유"]
        )
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        for row, result in enumerate(results):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(checkbox)

            self.table.setCellWidget(row, 0, holder)
            self.table.setItem(row, 1, QTableWidgetItem(result["file_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(result["folder"]))
            self.table.setItem(row, 3, QTableWidgetItem(result["reason"]))
            result["_checkbox"] = checkbox

        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)

        organize = QPushButton("선택한 파일 정리")
        organize.clicked.connect(self.organize_selected)

        buttons.addWidget(cancel)
        buttons.addWidget(organize)
        layout.addLayout(buttons)

    def organize_selected(self) -> None:
        selected = [r for r in self.results if r["_checkbox"].isChecked()]

        if not selected:
            QMessageBox.information(self, "바탕화면 정리", "선택된 파일이 없습니다.")
            return

        answer = QMessageBox.question(
            self,
            "최종 확인",
            f"{len(selected)}개 파일을 정리할까요?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        success = 0
        for result in selected:
            try:
                path = Path(result["file_path"])
                move_file(path, result["folder"], path.parent)
                success += 1
            except Exception:
                pass

        QMessageBox.information(
            self,
            "정리 완료",
            f"{success}개 파일을 정리했습니다.",
        )
        self.accept()
