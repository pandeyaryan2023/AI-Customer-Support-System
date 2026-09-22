"""Comparing embedding vectors. Pure numpy: no database, no Ollama.

    cosine similarity(A, B) = (A · B) / (|A| × |B|)

1.0 means the two vectors point the same way (same meaning), 0 means unrelated, and
-1 means opposite. Only direction counts, not length.
"""
import numpy as np


def cosine_similarities(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """The cosine similarity between `query` and every row of `matrix`, in one step.

    `matrix @ query` computes all the dot products A · B at once; dividing by the
    lengths turns each one into a cosine.
    """
    if query.ndim != 1 or matrix.ndim != 2 or matrix.shape[1] != query.shape[0]:
        raise ValueError(f"cannot compare a {query.shape} vector with a {matrix.shape} matrix")
    query_length = np.linalg.norm(query)
    row_lengths = np.linalg.norm(matrix, axis=1)
    # A zero vector has no direction, so its angle to anything is undefined.
    if query_length == 0 or np.any(row_lengths == 0):
        raise ValueError("cosine similarity is undefined for a zero vector")
    scores = (matrix @ query) / (row_lengths * query_length)
    return np.clip(scores, -1.0, 1.0)  # rounding can land a hair outside [-1, 1]


def valid_rows(vectors: list, dimension: int) -> tuple[np.ndarray, list[int]]:
    """Stack the usable vectors into a matrix, one row each.

    Returns the matrix and the positions (in `vectors`) of the rows kept. A vector is
    left out if it is not a list of `dimension` finite numbers, or is all zeros.
    """
    rows, kept = [], []
    for position, vector in enumerate(vectors):
        try:
            row = np.asarray(vector, dtype=np.float64)
        except (TypeError, ValueError):
            continue
        if row.shape != (dimension,) or not np.all(np.isfinite(row)) or not np.any(row):
            continue
        rows.append(row)
        kept.append(position)
    matrix = np.vstack(rows) if rows else np.empty((0, dimension))
    return matrix, kept


def rank(scores: np.ndarray, top_k: int, threshold: float) -> list[int]:
    """Positions of the best scores: at or above `threshold`, highest first, at most `top_k`.

    The sort is stable, so equal scores keep their original order and the result is
    always the same for the same input.
    """
    order = np.argsort(-scores, kind="stable")
    return [int(i) for i in order if scores[i] >= threshold][:top_k]
