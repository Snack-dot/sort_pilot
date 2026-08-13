from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .classifier_engine.hierarchy import TYPE_FAMILIES, UNSORTED_TOPIC, route_type
from .filters import is_safe_candidate


@dataclass(frozen=True, slots=True)
class MigrationCandidate:
    """One existing nested file and its proposed hierarchical relative folder."""

    source: Path
    root: Path
    folder: str
    family: str
    topic: str


def collect_migration_candidates(root: Path) -> list[MigrationCandidate]:
    """Collect safe files needing previewed conversion from flat to typed topics."""
    if not root.is_dir():
        raise NotADirectoryError(root)
    candidates: list[MigrationCandidate] = []
    for top_folder in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name.casefold()):
        if top_folder.name.startswith("."):
            continue
        for source in sorted(top_folder.rglob("*")):
            if not is_safe_candidate(source):
                continue
            relative = source.relative_to(root)
            parts = relative.parts
            if len(parts) < 2:
                continue
            family = route_type(source)
            top_name = parts[0]
            inner_parents = parts[1:-1]
            if top_name == family:
                if inner_parents:
                    continue  # Already under <type>/<topic>/...
                topic = UNSORTED_TOPIC
                preserved: tuple[str, ...] = ()
            else:
                topic = top_name
                preserved = tuple(inner_parents)
            if top_name in TYPE_FAMILIES and top_name != family:
                preserved = tuple(inner_parents)
            folder = Path(family, topic, *preserved).as_posix()
            candidates.append(MigrationCandidate(source.resolve(), root.resolve(), folder, family, topic))
    return candidates
