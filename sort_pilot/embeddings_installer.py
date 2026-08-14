from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .classifier_engine.embeddings import VECTOR_PATH

VOCAB_PER_LANGUAGE = 100_000
REFERENCE_SHA256 = "aee86795e9892825da0a7d02c67d5ac7f66c4ea16360d642c9ddf1f58828b972"


@dataclass(frozen=True, slots=True)
class FastTextSource:
    """One official pretrained fastText vector release to stream from."""

    language: str
    url: str


SOURCES = (
    FastTextSource("ko", "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.ko.300.vec.gz"),
    FastTextSource("en", "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.vec.gz"),
)


class InstallCancelled(RuntimeError):
    """Raised when the user cancels the semantic-vocabulary installation."""


class EmbeddingsInstaller:
    """Consent-gated local build of the bundled semantic-matching word vectors.

    Unlike the Gemma/llama.cpp installer, this does not download one pinned
    artifact and verify it byte-for-byte: fastText's official releases are
    multi-gigabyte, and only the most frequent ``VOCAB_PER_LANGUAGE`` words per
    language are needed, so each source is streamed and decompressed on the
    fly, stopping (and closing the connection) once enough words are read.
    That makes the exact resulting bytes environment-dependent (numpy/zlib
    version, platform), so the result is checked structurally rather than
    against a fixed hash — REFERENCE_SHA256 documents the maintainer's own
    build for THIRD_PARTY.md, the same way the locally-exported YOLO ONNX
    model's pinned hash is informational rather than runtime-enforced.
    """

    def __init__(self, root: Path, vector_path: Path = VECTOR_PATH) -> None:
        """Resolve the consent-record location and target vector-file path."""
        self.root = root
        self.vector_path = vector_path
        self.consent_path = root / "embeddings_consent.json"

    @property
    def ready(self) -> bool:
        """Return whether the vector file already exists."""
        return self.vector_path.is_file()

    @property
    def has_consent(self) -> bool:
        """Return whether the user has explicitly agreed to this download."""
        try:
            data = json.loads(self.consent_path.read_text(encoding="utf-8"))
            return bool(data.get("accepted"))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return False

    def record_consent(self) -> None:
        """Persist explicit acceptance separately from the built artifact."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.consent_path.write_text(
            json.dumps({"accepted": True, "accepted_at": time.time()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def install(
        self,
        progress: Callable[[str, int, int], None] | None = None,
        cancelled: threading.Event | None = None,
    ) -> None:
        """Stream the top-frequency words from each official source and build the local vector bundle."""
        if not self.has_consent:
            raise PermissionError("Semantic-vocabulary download must be accepted before installation")
        words: list[str] = []
        vectors: list[np.ndarray] = []
        for source in SOURCES:
            source_words, source_vectors = self._stream_top_words(source, progress, cancelled)
            if not source_words:
                raise RuntimeError(f"No vectors were read from {source.language} source")
            words.extend(source_words)
            vectors.extend(source_vectors)
        self._build(words, vectors)

    def _stream_top_words(
        self,
        source: FastTextSource,
        progress: Callable[[str, int, int], None] | None,
        cancelled: threading.Event | None,
    ) -> tuple[list[str], list[np.ndarray]]:
        """Read only the top VOCAB_PER_LANGUAGE most frequent lines without downloading the full file."""
        words: list[str] = []
        vectors: list[np.ndarray] = []
        request = urllib.request.Request(source.url, headers={"User-Agent": "SortPilot/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            with gzip.GzipFile(fileobj=response) as stream:
                stream.readline()  # header: "<vocab_size> <dims>"
                for count, line in enumerate(stream):
                    if count >= VOCAB_PER_LANGUAGE:
                        break
                    if cancelled is not None and cancelled.is_set():
                        raise InstallCancelled("Semantic-vocabulary installation cancelled")
                    parts = line.decode("utf-8").rstrip().split(" ")
                    words.append(parts[0])
                    vectors.append(np.array(parts[1:], dtype=np.float32))
                    if progress and count % 5000 == 0:
                        progress(source.language, count, VOCAB_PER_LANGUAGE)
        return words, vectors

    def _build(self, words: list[str], vectors: list[np.ndarray]) -> None:
        """Quantize and atomically install the combined vocabulary, verifying its structure."""
        array = np.stack(vectors).astype(np.float16)
        if array.ndim != 2 or array.shape[0] != len(words):
            raise RuntimeError("Built semantic vocabulary shape does not match its word list")
        self.vector_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.vector_path.with_suffix(self.vector_path.suffix + ".part")
        try:
            with temporary.open("wb") as stream:
                np.savez_compressed(stream, words=np.array(words), vectors=array)
            os.replace(temporary, self.vector_path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def reference_digest() -> str:
        """Return the maintainer's own reference build hash, for documentation only."""
        return REFERENCE_SHA256
