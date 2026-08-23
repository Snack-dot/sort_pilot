from __future__ import annotations

from pathlib import Path

import pytest

from sort_pilot.classifier_engine.actions import Executor
from sort_pilot.classifier_engine.analyzer import ClassifierEngine
from sort_pilot.classifier_engine.config import Config
from sort_pilot.classifier_engine.pipeline import Pipeline
from sort_pilot.classifier_engine.store import Store
from sort_pilot.classifier_engine.topics import TopicProfileStore
from sort_pilot.history import HistoryStore
from sort_pilot.models import FileOperation
from sort_pilot.organizer import execute_batch, undo_latest
from sort_pilot.sandbox import SandboxViolationError, require_in_sandbox


def test_sandbox_accepts_root_and_descendants(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    document = sandbox / "document.pdf"
    document.write_bytes(b"pdf")

    assert require_in_sandbox(sandbox, sandbox) == sandbox.resolve()
    assert require_in_sandbox(document, sandbox) == document.resolve()


def test_sandbox_rejects_sibling_and_prefix_paths(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    with pytest.raises(SandboxViolationError, match="outside the sandbox"):
        require_in_sandbox(tmp_path / "outside.pdf", sandbox)
    with pytest.raises(SandboxViolationError, match="outside the sandbox"):
        require_in_sandbox(tmp_path / "sandbox-copy" / "outside.pdf", sandbox)


@pytest.mark.parametrize("outside_side", ["source", "destination"])
def test_batch_rejects_any_path_outside_before_moving(
    tmp_path: Path,
    outside_side: str,
) -> None:
    sandbox = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    sandbox.mkdir()
    outside.mkdir()
    inside_source = sandbox / "inside.txt"
    outside_source = outside / "outside.txt"
    inside_source.write_text("inside", encoding="utf-8")
    outside_source.write_text("outside", encoding="utf-8")
    source = outside_source if outside_side == "source" else inside_source
    destination = (
        outside / "moved.txt" if outside_side == "destination" else sandbox / "moved.txt"
    )
    history = HistoryStore(tmp_path / "history.json")

    with pytest.raises(SandboxViolationError, match="outside the sandbox"):
        execute_batch(
            [FileOperation(str(source), str(destination))],
            history,
            sandbox,
        )

    assert inside_source.is_file()
    assert outside_source.is_file()
    assert not destination.exists()
    assert history.latest_batch() is None


def test_undo_rejects_legacy_history_outside_sandbox(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    sandbox.mkdir()
    outside.mkdir()
    source = outside / "original.txt"
    destination = outside / "moved.txt"
    destination.write_text("outside", encoding="utf-8")
    history = HistoryStore(tmp_path / "history.json")
    history.record("legacy", FileOperation(str(source), str(destination)))

    with pytest.raises(SandboxViolationError, match="outside the sandbox"):
        undo_latest(history, sandbox)

    assert destination.is_file()
    assert not source.exists()


def test_legacy_executor_rejects_non_sandbox_source_even_in_dry_run(
    tmp_path: Path,
) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"pdf")
    store = Store(tmp_path / "state.db")
    executor = Executor(store, dry_run=True, sandbox_root=sandbox)
    try:
        with pytest.raises(SandboxViolationError, match="outside the sandbox"):
            executor.execute(outside, sandbox, "category")
    finally:
        store.close()


def test_classifier_rejects_reading_outside_sandbox(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    analyzer = ClassifierEngine(
        Pipeline(Config(destination_root=str(sandbox)), tmp_path / "engine"),
        TopicProfileStore(tmp_path / "profiles.json"),
        sandbox_root=sandbox,
    )
    try:
        with pytest.raises(SandboxViolationError, match="outside the sandbox"):
            analyzer.analyze_record(outside)
    finally:
        analyzer.close()
