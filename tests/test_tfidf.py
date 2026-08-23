from __future__ import annotations

import numpy as np

from sort_pilot.classification.tfidf import (
    CHARACTER_BINS,
    WORD_BINS,
    HashedWordCharacterTfidf,
)


def test_hashed_tfidf_has_separate_word_and_character_channels(tmp_path):
    documents = ("수학 함수 문제지", "수학 함슈 문제지", "영어 독해 교재")
    model = HashedWordCharacterTfidf.fit(documents)
    matrix = model.transform(documents)

    assert matrix.shape == (3, WORD_BINS + CHARACTER_BINS)
    assert np.count_nonzero(matrix[:, :WORD_BINS]) > 0
    assert np.count_nonzero(matrix[:, WORD_BINS:]) > 0
    assert np.linalg.norm(matrix[0, WORD_BINS:] - matrix[1, WORD_BINS:]) < np.linalg.norm(
        matrix[0, WORD_BINS:] - matrix[2, WORD_BINS:]
    )

    model.save(tmp_path / "tfidf.npz", tmp_path)
    loaded = HashedWordCharacterTfidf.load(tmp_path / "tfidf.npz", tmp_path)
    assert np.allclose(loaded.transform(documents), matrix)
    assert "수학" not in (tmp_path / "tfidf.json").read_text(encoding="utf-8")
