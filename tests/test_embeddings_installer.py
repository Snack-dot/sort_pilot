from __future__ import annotations

import gzip
import io
import threading

import numpy as np
import pytest

from sort_pilot.embeddings_installer import (
    SOURCES,
    EmbeddingsInstaller,
    InstallCancelled,
)


def _fake_vec_gzip(word_count: int, dims: int = 4) -> bytes:
    """Build minimal fastText-format gzip content for one fake language source."""
    lines = [f"{word_count} {dims}"]
    for index in range(word_count):
        values = " ".join(f"{0.1 * (index + 1):.4f}" for _ in range(dims))
        lines.append(f"word{index} {values}")
    return gzip.compress("\n".join(lines).encode("utf-8") + b"\n")


class _Response(io.BytesIO):
    """Minimal context-managed urllib response fixture."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_installer_requires_consent_before_building(tmp_path):
    installer = EmbeddingsInstaller(tmp_path, vector_path=tmp_path / "vectors.npz")
    assert not installer.has_consent
    with pytest.raises(PermissionError):
        installer.install()


def test_installer_builds_vocabulary_from_streamed_sources(tmp_path, monkeypatch):
    vector_path = tmp_path / "models" / "vectors.npz"
    installer = EmbeddingsInstaller(tmp_path, vector_path=vector_path)
    installer.record_consent()
    assert installer.has_consent

    monkeypatch.setattr("sort_pilot.embeddings_installer.VOCAB_PER_LANGUAGE", 10)

    responses = {source.url: _fake_vec_gzip(10) for source in SOURCES}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30: _Response(responses[request.full_url]),
    )

    calls: list[tuple[str, int, int]] = []
    installer.install(progress=lambda *args: calls.append(args))

    assert vector_path.is_file()
    data = np.load(vector_path)
    assert len(data["words"]) == 10 * len(SOURCES)
    assert data["vectors"].shape == (10 * len(SOURCES), 4)
    assert installer.ready
    assert calls  # progress callback was invoked at least once per source


def test_installer_cancellation_leaves_no_partial_file(tmp_path, monkeypatch):
    vector_path = tmp_path / "vectors.npz"
    installer = EmbeddingsInstaller(tmp_path, vector_path=vector_path)
    installer.record_consent()

    monkeypatch.setattr("sort_pilot.embeddings_installer.VOCAB_PER_LANGUAGE", 10)
    responses = {source.url: _fake_vec_gzip(10) for source in SOURCES}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30: _Response(responses[request.full_url]),
    )

    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(InstallCancelled):
        installer.install(cancelled=cancelled)
    assert not vector_path.exists()
