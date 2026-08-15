from __future__ import annotations

import threading

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from .local_tagger import (
    MODEL,
    MODEL_DISPLAY_NAME,
    MODEL_TERMS_URL,
    InstallCancelled,
    LocalModelInstaller,
)


def ensure_local_model(parent, installer: LocalModelInstaller) -> bool:
    """Ask for model-license consent and install with cancellable progress."""
    if installer.ready:
        return True
    message = QMessageBox(parent)
    message.setWindowTitle("로컬 AI 모델 설치")
    message.setTextFormat(Qt.TextFormat.RichText)
    message.setText(
        f"파일 분류를 위해 {MODEL_DISPLAY_NAME} 모델({MODEL.size / 1_000_000:.0f}MB)을 "
        f"이 PC에만 설치합니다.<br><a href='{MODEL_TERMS_URL}'>모델 사용 조건</a>에 동의하시겠습니까?"
    )
    message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if message.exec() != QMessageBox.StandardButton.Yes:
        return False
    installer.record_consent()
    cancelled = threading.Event()
    progress = QProgressDialog("로컬 AI 모델 준비 중", "취소", 0, MODEL.size + 20_000_000, parent)
    progress.setWindowTitle("Sort Pilot")
    progress.setMinimumDuration(0)

    def update(name: str, current: int, total: int) -> None:
        """Reflect installer progress and propagate UI cancellation."""
        offset = 0 if name == MODEL.name else MODEL.size
        progress.setMaximum(MODEL.size + 20_000_000)
        progress.setValue(offset + min(current, total))
        progress.setLabelText(f"{name}: {current / 1_000_000:.0f}/{total / 1_000_000:.0f}MB")
        QApplication.processEvents()
        if progress.wasCanceled():
            cancelled.set()

    try:
        installer.install(update, cancelled)
        progress.close()
        return True
    except InstallCancelled:
        progress.close()
        return False
    except Exception as exc:
        progress.close()
        QMessageBox.warning(parent, "로컬 AI 모델", f"모델 설치에 실패했습니다.\n{exc}")
        return False
