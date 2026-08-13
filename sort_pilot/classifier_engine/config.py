from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Serializable thresholds, paths, exclusions, and engine safety settings."""

    watched_paths: list[str] = field(default_factory=lambda: [str(Path.home() / "Downloads")])
    destination_root: str = str(Path.home() / "Documents" / "Sorted")
    exclusions: list[str] = field(default_factory=list)
    no_ocr_paths: list[str] = field(default_factory=list)
    settle_seconds: float = 5.0
    max_content_mb: int = 200
    extractor_timeout: float = 10.0
    theta_auto: float = 0.55
    theta_suggest: float = 0.15
    min_evidence: float = 3.0
    dry_run: bool = True
    allow_cloud_moves: bool = False
    tier3_enabled: bool = False
    source_weights: dict[str, float] = field(default_factory=lambda: {
        "filename": 3.0, "meta": 2.0, "pair": 1.5,
        "body": 1.0, "obj": 0.8, "ocr": 0.6, "ext": 2.0,
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
