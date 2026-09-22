"""Phase 4: cosine similarity, ranking and threshold. Pure numpy: no database, no Ollama."""
import math

import numpy as np
import pytest

from app.services.vector_math import cosine_similarities, rank, valid_rows


def cos(a, b) -> float:
    return float(cosine_similarities(np.array(a, dtype=float), np.array([b], dtype=float))[0])


# ---------------------------------------------------------- cosine similarity

def test_known_value():
    assert cos([1, 0], [1, 1]) == pytest.approx(1 / math.sqrt(2))  # 45 degrees apart


def test_identical_vectors_score_one():
    assert cos([0.2, -0.5, 0.9], [0.2, -0.5, 0.9]) == pytest.approx(1.0)


def test_length_does_not_matter_only_direction():
    assert cos([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)


def test_orthogonal_vectors_score_zero():
    assert cos([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)


def test_opposite_vectors_score_minus_one():
    assert cos([1, 2], [-1, -2]) == pytest.approx(-1.0)


def test_matrix_version_matches_the_formula_row_by_row():
    rng = np.random.default_rng(7)
    query, matrix = rng.normal(size=768), rng.normal(size=(5, 768))
    expected = [np.dot(query, row) / (np.linalg.norm(query) * np.linalg.norm(row)) for row in matrix]
    assert cosine_similarities(query, matrix) == pytest.approx(expected)


def test_mismatched_dimensions_are_refused():
    with pytest.raises(ValueError, match="cannot compare"):
        cosine_similarities(np.ones(768), np.ones((2, 384)))


@pytest.mark.parametrize("query, matrix", [
    (np.zeros(3), np.ones((2, 3))),                  # zero question vector
    (np.ones(3), np.array([[1.0, 1, 1], [0, 0, 0]])),  # a zero stored vector
], ids=["zero-query", "zero-row"])
def test_zero_vectors_are_refused(query, matrix):
    with pytest.raises(ValueError, match="zero vector"):
        cosine_similarities(query, matrix)


# ---------------------------------------------------------- ranking, threshold, top_k

def test_rank_highest_first():
    assert rank(np.array([0.2, 0.9, 0.5]), top_k=10, threshold=0.0) == [1, 2, 0]


def test_threshold_filters_and_is_inclusive():
    scores = np.array([0.2, 0.9, 0.5, 0.55])
    assert rank(scores, top_k=10, threshold=0.55) == [1, 3]  # 0.55 itself is accepted
    assert rank(scores, top_k=10, threshold=0.3) == [1, 3, 2]


def test_top_k_limits_the_number_of_results():
    scores = np.array([0.6, 0.9, 0.7, 0.8])
    assert rank(scores, top_k=2, threshold=0.0) == [1, 3]
    assert rank(scores, top_k=1, threshold=0.0) == [1]


def test_nothing_above_threshold_gives_nothing():
    assert rank(np.array([0.1, 0.3, 0.2]), top_k=3, threshold=0.55) == []  # no low-score fallback


def test_no_scores_gives_nothing():
    assert rank(np.array([]), top_k=3, threshold=0.0) == []


def test_equal_scores_keep_their_order():
    assert rank(np.array([0.7, 0.7, 0.7]), top_k=3, threshold=0.0) == [0, 1, 2]


# ---------------------------------------------------------- stored vectors

def test_valid_rows_builds_a_matrix():
    matrix, kept = valid_rows([[1, 0, 0], [0, 1, 0]], dimension=3)
    assert matrix.shape == (2, 3) and kept == [0, 1]


def test_malformed_vectors_are_left_out():
    vectors = [
        None,               # missing
        "not a vector",
        {"a": 1},
        [1, 2],             # wrong dimension
        [1, "x", 2],        # not numbers
        [1, float("nan"), 2],
        [0, 0, 0],          # zero vector: no direction
        [0.1, 0.2, 0.3],    # the only good one
    ]
    matrix, kept = valid_rows(vectors, dimension=3)
    assert kept == [7]
    assert matrix.tolist() == [[0.1, 0.2, 0.3]]


def test_no_vectors_gives_an_empty_matrix():
    matrix, kept = valid_rows([], dimension=768)
    assert matrix.shape == (0, 768) and kept == []
