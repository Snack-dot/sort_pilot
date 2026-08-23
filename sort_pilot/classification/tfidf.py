from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from sort_pilot.sandbox import require_in_sandbox


HASHED_TFIDF_VERSION = "hashed-word-char-tfidf-v1"
WORD_BINS = 128
CHARACTER_BINS = 256


@dataclass(frozen=True, slots=True)
class HashedWordCharacterTfidf:
    """Privacy-preserving word and OCR-robust character TF-IDF transformer."""

    word_idf: np.ndarray
    character_idf: np.ndarray
    version: str = HASHED_TFIDF_VERSION

    def __post_init__(self) -> None:
        if self.version != HASHED_TFIDF_VERSION:
            raise ValueError("Unsupported TF-IDF model version.")
        for name, value, size in (
            ("word_idf", self.word_idf, WORD_BINS),
            ("character_idf", self.character_idf, CHARACTER_BINS),
        ):
            array = np.asarray(value, dtype=np.float64)
            if array.shape != (size,) or not np.isfinite(array).all() or np.any(array < 1.0):
                raise ValueError(f"Invalid {name} array.")
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self.schema_feature_names()

    @staticmethod
    def schema_feature_names() -> tuple[str, ...]:
        """Return the fixed hashed feature schema without fitting on any text."""
        return tuple(f"word_tfidf:{index:03d}" for index in range(WORD_BINS)) + tuple(
            f"char_tfidf:{index:03d}" for index in range(CHARACTER_BINS)
        )

    @classmethod
    def fit(cls, documents: Sequence[str]) -> "HashedWordCharacterTfidf":
        """Fit smoothed IDF arrays without retaining any source word or OCR n-gram."""
        values = tuple(documents)
        if not values or not all(isinstance(value, str) for value in values):
            raise ValueError("TF-IDF fitting needs a non-empty text sequence.")
        word_df = np.zeros(WORD_BINS, dtype=np.float64)
        character_df = np.zeros(CHARACTER_BINS, dtype=np.float64)
        for value in values:
            for index in set(_word_bins(value)):
                word_df[index] += 1.0
            for index in set(_character_bins(value)):
                character_df[index] += 1.0
        count = float(len(values))
        return cls(
            word_idf=np.log((1.0 + count) / (1.0 + word_df)) + 1.0,
            character_idf=np.log((1.0 + count) / (1.0 + character_df)) + 1.0,
        )

    def transform(self, documents: Sequence[str]) -> np.ndarray:
        """Return independently normalized word and character TF-IDF channels."""
        values = tuple(documents)
        if not values or not all(isinstance(value, str) for value in values):
            raise ValueError("TF-IDF transform needs a non-empty text sequence.")
        matrix = np.zeros((len(values), WORD_BINS + CHARACTER_BINS), dtype=np.float64)
        for row, value in enumerate(values):
            word = _tfidf_row(_word_bins(value), self.word_idf)
            character = _tfidf_row(_character_bins(value), self.character_idf)
            matrix[row] = np.concatenate((word, character))
        return matrix

    def save(self, path: Path, sandbox_root: Path) -> None:
        """Save only hashed-bin IDFs and schema metadata inside the sandbox."""
        target = require_in_sandbox(path, sandbox_root, label="TF-IDF model")
        if target.suffix.casefold() != ".npz":
            raise ValueError("TF-IDF model path must end in .npz.")
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = target.with_suffix(".json")
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f"{target.stem}-",
            suffix=".npz",
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        metadata_temporary = temporary.with_suffix(".json")
        try:
            with temporary.open("wb") as stream:
                np.savez_compressed(
                    stream,
                    word_idf=self.word_idf,
                    character_idf=self.character_idf,
                )
                stream.flush()
                os.fsync(stream.fileno())
            metadata_temporary.write_text(
                json.dumps(
                    {
                        "version": self.version,
                        "word_bins": WORD_BINS,
                        "character_bins": CHARACTER_BINS,
                        "raw_vocabulary_persisted": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(temporary, target)
            os.replace(metadata_temporary, metadata_path)
        finally:
            temporary.unlink(missing_ok=True)
            metadata_temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: Path, sandbox_root: Path) -> "HashedWordCharacterTfidf":
        target = require_in_sandbox(path, sandbox_root, label="TF-IDF model")
        metadata = json.loads(target.with_suffix(".json").read_text(encoding="utf-8"))
        if metadata != {
            "version": HASHED_TFIDF_VERSION,
            "word_bins": WORD_BINS,
            "character_bins": CHARACTER_BINS,
            "raw_vocabulary_persisted": False,
        }:
            raise ValueError("Invalid TF-IDF metadata.")
        with np.load(target, allow_pickle=False) as values:
            if set(values.files) != {"word_idf", "character_idf"}:
                raise ValueError("Invalid TF-IDF arrays.")
            return cls(values["word_idf"], values["character_idf"])


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _word_bins(value: str) -> tuple[int, ...]:
    words = re.findall(r"[가-힣]+|[a-z][a-z0-9]*|\d+", _normalized(value))
    terms = [*words, *(f"{left}\u241f{right}" for left, right in zip(words, words[1:]))]
    return tuple(_hash_bin(term, WORD_BINS, b"word") for term in terms)


def _character_bins(value: str) -> tuple[int, ...]:
    normalized = _normalized(value)
    return tuple(
        _hash_bin(normalized[offset : offset + size], CHARACTER_BINS, b"char")
        for size in (3, 4, 5)
        for offset in range(max(0, len(normalized) - size + 1))
        if normalized[offset : offset + size].strip()
    )


def _hash_bin(value: str, bins: int, person: bytes) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8, person=person).digest()
    return int.from_bytes(digest, "big") % bins


def _tfidf_row(indices: Sequence[int], idf: np.ndarray) -> np.ndarray:
    result = np.zeros(len(idf), dtype=np.float64)
    for index, count in Counter(indices).items():
        result[index] = (1.0 + math.log(count)) * idf[index]
    norm = float(np.linalg.norm(result))
    return result if norm == 0.0 else result / norm
