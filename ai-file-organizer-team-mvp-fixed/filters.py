from pathlib import Path

IGNORED_EXTENSIONS = {
    ".lnk", ".url", ".exe", ".msi", ".bat",
    ".cmd", ".com", ".scr", ".ps1",
}
TEMP_EXTENSIONS = {
    ".tmp", ".part", ".crdownload", ".download",
}


def is_temporary_file(path: Path) -> bool:
    return path.suffix.lower() in TEMP_EXTENSIONS


def should_ignore_desktop_item(path: Path) -> bool:
    if path.is_dir() or not path.is_file():
        return True
    if path.name.startswith("."):
        return True

    extension = path.suffix.lower()
    return extension in IGNORED_EXTENSIONS or extension in TEMP_EXTENSIONS
