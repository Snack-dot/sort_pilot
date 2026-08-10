from pathlib import Path
from classifier import classify_file
from filters import should_ignore_desktop_item


def scan_desktop() -> list[dict]:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)

    return [
        classify_file(item)
        for item in desktop.iterdir()
        if not should_ignore_desktop_item(item)
    ]
