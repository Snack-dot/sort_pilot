from pathlib import Path
import shutil

INVALID_FOLDER_CHARS = '<>:"/\\|?*'


def move_file(
    file_path: Path,
    folder_name: str,
    base_folder: Path | None = None,
) -> Path:
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError("이동할 파일이 존재하지 않습니다.")

    if base_folder is None:
        base_folder = file_path.parent

    safe_name = folder_name.strip()
    for char in INVALID_FOLDER_CHARS:
        safe_name = safe_name.replace(char, "")
    safe_name = safe_name or "기타"

    target_folder = base_folder / safe_name
    target_folder.mkdir(parents=True, exist_ok=True)

    target_path = target_folder / file_path.name
    counter = 1
    while target_path.exists():
        target_path = target_folder / f"{file_path.stem}_{counter}{file_path.suffix}"
        counter += 1

    shutil.move(str(file_path), str(target_path))
    return target_path
