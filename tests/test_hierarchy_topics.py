from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from sort_pilot.classifier_engine.hierarchy import hierarchical_folder, route_type
from sort_pilot.classifier_engine.topics import (
    AnalysisRecord,
    TopicClassifier,
    TopicProfile,
    TopicProfileStore,
    validate_topic_name,
)
from sort_pilot.migration import collect_migration_candidates


def record(name: str, family: str, terms: dict[str, float]) -> AnalysisRecord:
    return AnalysisRecord(name, Path(name).name, Path(name).name, family, terms)


def test_fixed_type_routing_and_unsorted_hierarchy():
    assert route_type(Path("report.PDF")) == "문서"
    assert route_type(Path("photo.png")) == "이미지"
    assert route_type(Path("backup.zip")) == "압축파일"
    assert route_type(Path("voice.mp3")) == "오디오"
    assert route_type(Path("clip.mp4")) == "동영상"
    assert route_type(Path("unknown.bin")) == "기타"
    assert hierarchical_folder("문서") == "문서/미분류"


def test_profile_store_separates_families_and_validates_names():
    with tempfile.TemporaryDirectory() as directory:
        store = TopicProfileStore(Path(directory) / "profiles.json")
        assert store.load() == []
        store.upsert(store.new_profile("문서", "취미", ["등산", "산행"]))
        store.upsert(store.new_profile("이미지", "취미", ["등산 사진"]))
        with pytest.raises(ValueError):
            store.upsert(store.new_profile("문서", "취미", ["duplicate"]))
        with pytest.raises(ValueError):
            validate_topic_name("bad/name")
        with pytest.raises(ValueError):
            validate_topic_name("미분류")


def test_version_one_builtin_profiles_are_removed_during_load():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "profiles.json"
        builtin = TopicProfile("builtin:old", "문서", "자동주제", origin="builtin")
        user = TopicProfileStore.new_profile("문서", "사용자선택", ["직접"])
        path.write_text(
            json.dumps({"version": 1, "profiles": [asdict(builtin), asdict(user)]}, ensure_ascii=False),
            encoding="utf-8",
        )
        profiles = TopicProfileStore(path).load()
        persisted = json.loads(path.read_text(encoding="utf-8"))
        assert [profile.name for profile in profiles] == ["사용자선택"]
        assert persisted["version"] == 2
        assert all(item["origin"] != "builtin" for item in persisted["profiles"])


def test_only_user_profiles_assign_family_specific_topics():
    classifier = TopicClassifier()
    document_profile = TopicProfileStore.new_profile("문서", "내문서함", ["과제"])
    image_profile = TopicProfileStore.new_profile("이미지", "내사진함", ["과제"])
    records = [
        record("assignment.pdf", "문서", {"과제": 3}),
        record("assignment.png", "이미지", {"과제": 3}),
        record("unmatched.pdf", "문서", {"관계없음": 3}),
    ]
    classifier.assign_existing(records, [document_profile, image_profile])
    assert records[0].topic == "내문서함"
    assert records[1].topic == "내사진함"
    assert records[2].topic is None


def test_builtin_origin_is_never_used_even_if_supplied_programmatically():
    classifier = TopicClassifier()
    legacy = TopicProfile("builtin:legacy", "문서", "자동주제", tags=("과제",), origin="builtin")
    target = record("assignment.pdf", "문서", {"과제": 3})
    classifier.assign_existing([target], [legacy])
    assert target.topic is None


def test_current_batch_discovery_uses_family_minimums():
    classifier = TopicClassifier()
    documents = [
        record(f"doc-{index}.pdf", "문서", {"운영체제": 3, "프로세스": 2, f"term{index}": 0.1})
        for index in range(5)
    ]
    images = [
        record(f"img-{index}.png", "이미지", {"여행": 3, "바다": 2, f"image{index}": 0.1})
        for index in range(9)
    ]
    proposals = classifier.discover(documents + images)
    assert len(proposals) == 1
    assert proposals[0].family == "문서"
    assert len(proposals[0].record_indexes) == 5
    assert "운영체제" in proposals[0].top_terms


def test_migration_preserves_topic_and_deeper_relative_path():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old = root / "직접선택" / "1차" / "과제.pdf"
        old.parent.mkdir(parents=True)
        old.write_text("assignment", encoding="utf-8")
        direct = root / "이미지" / "photo.png"
        direct.parent.mkdir()
        direct.write_bytes(b"not-an-image")
        already = root / "문서" / "직접선택" / "done.pdf"
        already.parent.mkdir(parents=True)
        already.write_text("done", encoding="utf-8")

        candidates = collect_migration_candidates(root)
        targets = {item.source.name: item.folder for item in candidates}
        assert targets["과제.pdf"] == "문서/직접선택/1차"
        assert targets["photo.png"] == "이미지/미분류"
        assert "done.pdf" not in targets
