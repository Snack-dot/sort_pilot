from __future__ import annotations

import io
import json
import random
import zipfile
from pathlib import Path

import pytest

from sort_pilot.calibration import (
    CalibrationSampler,
    CalibrationService,
    learn_correction,
)
from sort_pilot.classifier_engine.topics import (
    AnalysisRecord,
    TopicClassifier,
    TopicProfileStore,
    contextual_terms,
)
from sort_pilot.history import HistoryStore
from sort_pilot.local_tagger import DownloadArtifact, LocalModelInstaller, LocalTagger
from sort_pilot.organizer import build_operation, execute_batch


def make_record(name: str, family: str, terms: dict[str, float]) -> AnalysisRecord:
    """Create a compact analysis record for calibration tests."""
    return AnalysisRecord(name, Path(name).name, Path(name).name, family, terms)


def test_sampler_limits_each_family_and_prefers_unseen_files(tmp_path):
    root = tmp_path / "Downloads"
    root.mkdir()
    for index in range(12):
        (root / f"document-{index}.pdf").write_text(f"document {index}", encoding="utf-8")
    for index in range(3):
        (root / f"image-{index}.png").write_bytes(b"image")

    sampler = CalibrationSampler(tmp_path / "state.json", rng=random.Random(7))
    first = sampler.select([root])
    assert sum(path.suffix == ".pdf" for path in first) == 3
    assert sum(path.suffix == ".png" for path in first) == 3
    sampler.remember(first)

    second = sampler.select([root])
    first_documents = {path for path in first if path.suffix == ".pdf"}
    assert not (first_documents & set(second))
    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["version"] == 1


def test_sampler_keeps_small_one_and_two_file_families(tmp_path):
    root = tmp_path / "Downloads"
    root.mkdir()
    (root / "only-document.pdf").write_text("one", encoding="utf-8")
    (root / "first.png").write_bytes(b"one")
    (root / "second.jpg").write_bytes(b"two")

    selected = CalibrationSampler(
        tmp_path / "state.json", rng=random.Random(3)
    ).select([root])
    assert {path.name for path in selected} == {
        "only-document.pdf",
        "first.png",
        "second.jpg",
    }


def test_calibration_draft_persists_only_user_confirmed_topics(tmp_path):
    store = TopicProfileStore(tmp_path / "profiles.json")
    service = CalibrationService(TopicClassifier(), store)
    records = [
        make_record("tax-1.pdf", "문서", {"세금": 3, "영수증": 1}),
        make_record("tax-2.pdf", "문서", {"세금": 2, "영수증": 1}),
    ]
    draft = service.build_draft(records)
    assert len(draft.clusters) == 1
    draft.clusters[0].topic = "세금 자료"
    draft.clusters[0].tags = ["세금", "영수증"]

    profiles = service.save_draft(draft)
    assert [(profile.family, profile.name) for profile in profiles] == [("문서", "세금 자료")]
    assert profiles[0].example_count == 2


def test_calibration_builds_large_vocabulary_and_cooccurrence_context(tmp_path):
    store = TopicProfileStore(tmp_path / "profiles.json")
    service = CalibrationService(TopicClassifier(), store)
    words = {f"word{index}": float(50 - index) for index in range(30)}
    records = [make_record("rich.pdf", "문서", words)]

    draft = service.build_draft(records)
    profiles = service.profiles_from_draft(draft)

    assert len(draft.clusters[0].tags) == 30
    assert len(profiles[0].example_weights) > 100
    assert any(term.startswith("co:") for term in profiles[0].example_weights)
    assert len(contextual_terms(words)) > len(words)


def test_calibration_tags_are_words_extracted_from_seed_files(tmp_path):
    store = TopicProfileStore(tmp_path / "profiles.json")
    service = CalibrationService(TopicClassifier(), store)
    records = [make_record("seed.txt", "문서", {"nebula": 3, "orbit": 2, "telescope": 1})]
    proposal = service.classifier.discover(records)[0]
    suggestions = {
        service.cluster_id(proposal): ("Space", ("nebula", "hallucinated-synonym"))
    }

    draft = service.build_draft(records, suggestions)

    assert "nebula" in draft.clusters[0].tags
    assert "hallucinated-synonym" not in draft.clusters[0].tags
    assert set(draft.clusters[0].tags) == {"nebula", "orbit", "telescope"}


def test_actual_file_body_reaches_the_calibration_profile(tmp_path):
    from sort_pilot.classifier_engine.analyzer import ClassifierEngine
    from sort_pilot.classifier_engine.config import Config
    from sort_pilot.classifier_engine.pipeline import Pipeline

    path = tmp_path / "opaque-name.txt"
    path.write_text("nebula roadmap milestone telescope orbit context", encoding="utf-8")
    store = TopicProfileStore(tmp_path / "profiles.json")
    engine = ClassifierEngine(
        Pipeline(Config(destination_root=str(tmp_path / "sorted")), tmp_path / "engine"),
        store,
    )
    try:
        record = engine.analyze_record(path)
        service = CalibrationService(TopicClassifier(), store)
        draft = service.build_draft([record])
        draft.clusters[0].topic = "Space Project"
        profile = service.profiles_from_draft(draft)[0]
    finally:
        engine.close()

    assert {"nebula", "roadmap", "milestone", "telescope", "orbit", "context"} <= set(profile.tags)
    assert "co:nebula|roadmap" in profile.example_weights or "co:roadmap|nebula" in profile.example_weights


def test_calibration_seed_changes_move_seeds_before_remaining_review(tmp_path):
    desktop = tmp_path / "Desktop"
    downloads = tmp_path / "Downloads"
    desktop.mkdir()
    downloads.mkdir()
    first = downloads / "seed-one.txt"
    second = downloads / "seed-two.txt"
    remaining = downloads / "remaining.txt"
    for path in (first, second, remaining):
        path.write_text("project alpha context", encoding="utf-8")
    records = [
        make_record(str(first), "문서", {"project": 3, "alpha": 2}),
        make_record(str(second), "문서", {"project": 3, "context": 2}),
    ]
    service = CalibrationService(TopicClassifier(), TopicProfileStore(tmp_path / "profiles.json"))
    draft = service.build_draft(records)
    draft.clusters[0].topic = "Alpha Project"
    changes = service.seed_changes(draft, desktop, downloads)

    completed = execute_batch(
        [build_operation(change, downloads) for change in changes],
        HistoryStore(tmp_path / "history.json"),
    )

    assert len(completed) == 2
    assert (downloads / "문서" / "Alpha Project" / first.name).is_file()
    assert (downloads / "문서" / "Alpha Project" / second.name).is_file()
    assert remaining.is_file()
    assert {path.name for path in downloads.iterdir() if path.is_file()} == {remaining.name}


def test_signed_correction_reinforces_choice_and_demotes_prediction(tmp_path):
    store = TopicProfileStore(tmp_path / "profiles.json")
    predicted = store.new_profile("문서", "업무", example_weights={"invoice": 3}, example_count=1)
    chosen = store.new_profile("문서", "세금", example_weights={"tax": 3}, example_count=1)
    record = make_record("tax-invoice.pdf", "문서", {"invoice": 3, "tax": 3})

    profiles = learn_correction([predicted, chosen], record, "업무", "세금")
    by_name = {profile.name: profile for profile in profiles}
    assert by_name["업무"].negative_count == 1
    assert by_name["세금"].example_count == 2

    TopicClassifier().assign_existing([record], profiles)
    assert record.topic == "세금"


def test_version_two_profile_migrates_with_empty_negative_evidence(tmp_path):
    path = tmp_path / "profiles.json"
    profile = TopicProfileStore.new_profile("문서", "개인", ["일기"])
    data = {
        "version": 2,
        "profiles": [
            {
                "id": profile.id,
                "family": profile.family,
                "name": profile.name,
                "tags": list(profile.tags),
                "example_weights": {},
                "example_count": 0,
                "origin": profile.origin,
                "enabled": True,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    loaded = TopicProfileStore(path).load()
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert loaded[0].negative_weights == {}
    assert persisted["version"] == 3
    assert persisted["profiles"][0]["negative_count"] == 0


def test_local_tagger_rejects_incomplete_or_invalid_json():
    from sort_pilot.classifier_engine.topics import TopicProposal

    proposal = TopicProposal("문서", (0,), ("tax",), ("tax.pdf",), {"tax": 1})
    cluster_id = LocalTagger.cluster_id(proposal)
    valid = json.dumps(
        {"results": [{"cluster_id": cluster_id, "topic": "세금", "tags": ["tax", "invoice"]}]}
    )
    assert LocalTagger._validate_response(valid, [proposal])[cluster_id][0] == "세금"
    with pytest.raises(ValueError):
        LocalTagger._validate_response('{"results": []}', [proposal])
    with pytest.raises(json.JSONDecodeError):
        LocalTagger._validate_response("not json", [proposal])


def test_download_verifies_checksum_before_atomic_install(tmp_path, monkeypatch):
    content = b"verified artifact"
    import hashlib

    artifact = DownloadArtifact(
        "artifact.bin",
        "https://example.invalid/artifact.bin",
        len(content),
        hashlib.sha256(content).hexdigest(),
    )

    class Response(io.BytesIO):
        """Minimal context-managed urllib response fixture."""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response(content))
    destination = tmp_path / "artifact.bin"
    LocalModelInstaller._download(artifact, destination, None, None)
    assert destination.read_bytes() == content

    corrupt = DownloadArtifact(artifact.name, artifact.url, len(content), "0" * 64)
    with pytest.raises(RuntimeError):
        LocalModelInstaller._download(corrupt, tmp_path / "bad.bin", None, None)
    assert not (tmp_path / "bad.bin").exists()


def test_runtime_extraction_rejects_path_traversal(tmp_path):
    installer = LocalModelInstaller(tmp_path / "local-ai")
    installer.runtime_dir.parent.mkdir(parents=True)
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.txt", "escape")
    with pytest.raises(RuntimeError, match="Unsafe path"):
        installer._extract_runtime(archive)
    assert not (tmp_path / "escape.txt").exists()


def test_runtime_extraction_installs_server_and_neighbor_dlls(tmp_path):
    installer = LocalModelInstaller(tmp_path / "local-ai")
    installer.runtime_dir.parent.mkdir(parents=True)
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("build/bin/llama-server.exe", "server")
        bundle.writestr("build/bin/ggml.dll", "dll")

    installer._extract_runtime(archive)
    assert installer.server_path.read_text(encoding="utf-8") == "server"
    assert (installer.runtime_dir / "ggml.dll").is_file()
    assert not archive.exists()
