from __future__ import annotations

import mimetypes
from pathlib import Path


TYPE_FAMILIES = ("문서", "이미지", "압축파일", "오디오", "동영상", "기타")
UNSORTED_TOPIC = "미분류"

EXTENSION_FAMILIES: dict[str, str] = {
    **{ext: "문서" for ext in (".pdf", ".txt", ".md", ".csv", ".rtf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt")},
    **{ext: "이미지" for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic")},
    **{ext: "압축파일" for ext in (".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz")},
    **{ext: "오디오" for ext in (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma")},
    **{ext: "동영상" for ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv")},
}

MIME_FAMILIES = {
    "text": "문서",
    "image": "이미지",
    "audio": "오디오",
    "video": "동영상",
}


def route_type(path: Path) -> str:
    """Route a file into one fixed Korean type family using extension then MIME."""
    suffix = path.suffix.casefold()
    if suffix in EXTENSION_FAMILIES:
        return EXTENSION_FAMILIES[suffix]
    mime = mimetypes.guess_type(path.name)[0]
    major = mime.split("/", 1)[0] if mime else ""
    return MIME_FAMILIES.get(major, "기타")


def hierarchical_folder(family: str, topic: str | None = None) -> str:
    """Return a safe two-level relative folder using the reserved fallback topic."""
    safe_family = family if family in TYPE_FAMILIES else "기타"
    safe_topic = (topic or UNSORTED_TOPIC).strip() or UNSORTED_TOPIC
    return f"{safe_family}/{safe_topic}"
