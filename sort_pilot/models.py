from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileSuggestion:
    file_path: str
    file_name: str
    suggested_name: str
    folder: str
    reason: str

    @property
    def source(self) -> Path:
        return Path(self.file_path)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ApprovedFileMove:
    """User-approved folder move based on an analyzer suggestion."""

    suggestion: FileSuggestion
    destination_root: str
    folder: str
    move_approved: bool


@dataclass(frozen=True, slots=True)
class FileOperation:
    source: str
    destination: str

    @property
    def source_path(self) -> Path:
        return Path(self.source)

    @property
    def destination_path(self) -> Path:
        return Path(self.destination)
