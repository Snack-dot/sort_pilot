from pathlib import Path
from PyQt6.QtWidgets import QMessageBox
from organizer import move_file


class MoveApprovalPopup:
    def show_file_suggestion(self, result: dict) -> None:
        file_path = Path(result["file_path"])
        if not file_path.exists():
            return

        message = QMessageBox()
        message.setWindowTitle("새 파일 발견")
        message.setIcon(QMessageBox.Icon.Question)
        message.setText(f"{result['file_name']} 파일을 발견했습니다.")
        message.setInformativeText(
            f"추천 폴더: {result['folder']}\n\n"
            f"분류 이유: {result['reason']}\n\n"
            "이 폴더로 이동할까요?"
        )

        move_button = message.addButton("이동", QMessageBox.ButtonRole.AcceptRole)
        message.addButton("무시", QMessageBox.ButtonRole.RejectRole)
        message.exec()

        if message.clickedButton() == move_button:
            try:
                target = move_file(file_path, result["folder"])
                QMessageBox.information(None, "이동 완료", str(target))
            except Exception as error:
                QMessageBox.critical(None, "이동 실패", str(error))
