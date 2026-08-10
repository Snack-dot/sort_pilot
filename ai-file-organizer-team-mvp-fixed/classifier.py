from pathlib import Path


def _new_pipeline_result(file_path: Path) -> dict | None:
    """Use the SRS pipeline when the repository root is importable."""
    import sys

    src = Path(__file__).resolve().parent.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from tidy.pipeline import Pipeline

        _, decision, _ = Pipeline().safe_classify(file_path)
    except (ImportError, OSError, ValueError):
        return None
    return {
        "file_path": str(file_path),
        "file_name": file_path.name,
        "folder": decision.category or "기타",
        "reason": f"{decision.tier} 분류 결과 ({decision.action}, margin={decision.margin:.3f})입니다.",
        "confidence": decision.margin,
        "action": decision.action,
        "explanation": decision.explanation,
    }


def classify_file(file_path: Path) -> dict:
    if result := _new_pipeline_result(file_path):
        return result

    name = file_path.stem.lower()
    extension = file_path.suffix.lower()

    rules = [
        (["과제", "assignment", "lecture", "강의", "학교"], "학교"),
        (["회의", "meeting", "기획", "proposal", "업무"], "업무"),
        (["영수증", "receipt", "invoice", "결제", "세금"], "금융"),
        (["이력서", "resume", "자소서", "portfolio", "포트폴리오"], "취업"),
    ]

    for keywords, folder in rules:
        if any(keyword in name for keyword in keywords):
            return {
                "file_path": str(file_path),
                "file_name": file_path.name,
                "folder": folder,
                "reason": "파일명의 의미를 기준으로 분류했습니다.",
            }

    extension_rules = {
        ".pdf": "문서", ".doc": "문서", ".docx": "문서",
        ".txt": "문서", ".ppt": "문서", ".pptx": "문서",
        ".xls": "문서", ".xlsx": "문서", ".csv": "문서",
        ".png": "이미지", ".jpg": "이미지", ".jpeg": "이미지",
        ".gif": "이미지", ".webp": "이미지",
        ".zip": "압축파일", ".rar": "압축파일", ".7z": "압축파일",
        ".mp3": "음악", ".wav": "음악",
        ".mp4": "동영상", ".mov": "동영상",
    }

    return {
        "file_path": str(file_path),
        "file_name": file_path.name,
        "folder": extension_rules.get(extension, "기타"),
        "reason": "파일 확장자를 기준으로 분류했습니다.",
    }
