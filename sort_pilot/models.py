from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileSuggestion:
    """Normalized classifier recommendation consumed by the desktop UI."""

    file_path: str
    file_name: str
    suggested_name: str
    folder: str
    reason: str

    @property
    def source(self) -> Path:
        """Return the recommendation's source file as a path object."""
        return Path(self.file_path)

    def to_dict(self) -> dict[str, str]:
        """Serialize every stable application-facing recommendation field."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ApprovedFileMove:
    """User-approved destination choice for one classifier suggestion."""

    suggestion: FileSuggestion
    destination_root: str
    folder: str
    move_approved: bool


@dataclass(frozen=True, slots=True)
class FileOperation:
    """Concrete reversible source-to-destination move."""

    source: str
    destination: str

    @property
    def source_path(self) -> Path:
        """Return the operation source as a path object."""
        return Path(self.source)

    @property
    def destination_path(self) -> Path:
        """Return the operation destination as a path object."""
        return Path(self.destination)

