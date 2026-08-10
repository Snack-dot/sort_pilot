from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from .models import FileSuggestion


class FileAnalyzer(Protocol):
    def analyze(self, file_path: Path) -> FileSuggestion: ...


class RuleBasedAnalyzer:
    """Temporary lightweight analyzer; replaceable by a local-AI implementation."""

    CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("학교", ("과제", "강의", "수업", "학교", "시험", "운영체제")),
        ("금융", ("영수증", "세금", "invoice", "receipt", "결제", "쿠팡")),
        ("업무", ("회의", "보고서", "업무", "회사", "계약")),
        ("이미지", ("스크린샷", "사진", "image", "img", "screenshot")),
    )

    EXTENSION_FOLDERS = {
        ".jpg": "이미지",
        ".jpeg": "이미지",
        ".png": "이미지",
        ".gif": "이미지",
        ".webp": "이미지",
        ".pdf": "문서",
        ".txt": "문서",
        ".docx": "문서",
    }

    def analyze(self, file_path: Path) -> FileSuggestion:
        normalized = file_path.stem.casefold()
        folder = next(
            (category for category, words in self.CATEGORIES if any(word in normalized for word in words)),
            self.EXTENSION_FOLDERS.get(file_path.suffix.casefold(), "기타"),
        )
        suggested_name = self._clean_name(file_path)
        return FileSuggestion(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            suggested_name=suggested_name,
            folder=folder,
            reason=f"파일명과 확장자를 기준으로 '{folder}' 유형으로 분류했습니다.",
        )

    @staticmethod
    def _clean_name(file_path: Path) -> str:
        stem = re.sub(r"\s+", "_", file_path.stem.strip())
        stem = re.sub(r"(?i)\b(final[_ -]*){2,}", "final_", stem)
        return f"{stem}{file_path.suffix.casefold()}"

