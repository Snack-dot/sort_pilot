from __future__ import annotations

from pathlib import Path

import numpy as np

TOP_N_TERMS = 5
SEMANTIC_MATCH_THRESHOLD = 0.30
VECTOR_PATH = Path(__file__).parents[2] / "data" / "models" / "word_vectors.npz"

_VOCAB: dict[str, np.ndarray] | None = None


def load_vocab() -> dict[str, np.ndarray] | None:
    """Lazily load the bundled pretrained word-vector vocabulary, caching only a successful load.

    Deliberately re-checks ``VECTOR_PATH.exists()`` (one cheap stat call) every
    time the vocabulary hasn't loaded yet, rather than caching the absence
    permanently, so a vocabulary installed mid-session (via the consent flow
    in ``embeddings_installer.py``) is picked up without an app restart.
    """
    global _VOCAB
    if _VOCAB is None and VECTOR_PATH.exists():
        data = np.load(VECTOR_PATH)
        _VOCAB = dict(zip(data["words"].tolist(), data["vectors"].astype(np.float32)))
    return _VOCAB


def _resolve(term: str, vocab: dict[str, np.ndarray]) -> np.ndarray | None:
    """Resolve one feature term to a vector, expanding YOLO object labels and collocations into plain words."""
    if term.startswith("obj:"):
        words = term[len("obj:"):].replace("_", " ").split()
    elif term.startswith(("bi:", "tri:")):
        words = term.split(":", 1)[1].split()
    elif term.startswith("pair:"):
        return None
    else:
        words = [term]
    found = [vocab[word] for word in words if word in vocab]
    return np.mean(found, axis=0) if found else None


def doc_vectors(
    terms: dict[str, float],
    vocab: dict[str, np.ndarray],
    idf: dict[str, float],
    top_n: int = TOP_N_TERMS,
) -> list[np.ndarray]:
    """Return unit vectors for a document's most distinctive words, kept separate (not averaged)."""
    ranked = sorted(terms.items(), key=lambda item: -item[1] * idf.get(item[0], 1.0))[:top_n]
    resolved = (_resolve(term, vocab) for term, _ in ranked)
    return [vector / norm for vector in resolved if vector is not None and (norm := float(np.linalg.norm(vector)))]


def semantic_similarity(vectors_a: list[np.ndarray], vectors_b: list[np.ndarray]) -> float:
    """Return greedy best-match word-vector similarity between two documents (relaxed word-mover style).

    Each side's words are matched to their closest counterpart on the other side rather
    than averaged into one blurred vector, so a document keeps credit for genuinely
    matching specific words instead of drifting toward a generic shared domain.
    """
    if not vectors_a or not vectors_b:
        return 0.0
    a_to_b = [max(float(np.dot(a, b)) for b in vectors_b) for a in vectors_a]
    b_to_a = [max(float(np.dot(a, b)) for a in vectors_a) for b in vectors_b]
    return (sum(a_to_b) / len(a_to_b) + sum(b_to_a) / len(b_to_a)) / 2
