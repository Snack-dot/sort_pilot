from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Serializable settings used by local content extraction."""

    exclusions: list[str] = field(default_factory=list)
    max_content_mb: int = 200
    source_weights: dict[str, float] = field(default_factory=lambda: {
        "body": 1.0,
        "pair": 1.5,
        "obj": 0.8,
        "ocr": 0.6,
    })

    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load known settings or create a default configuration file."""
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        values = json.loads(path.read_text(encoding="utf-8"))
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in values.items() if k in known})

    def save(self, path: Path) -> None:
        """Persist the current configuration as atomically replaced UTF-8 JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent, prefix="classifier-config-", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(asdict(self), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)


def data_dir() -> Path:
    """Return the legacy-compatible private classifier data directory."""
    root = Path(os.getenv("APPDATA", Path.home() / ".local" / "share")) / "tidy"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root
