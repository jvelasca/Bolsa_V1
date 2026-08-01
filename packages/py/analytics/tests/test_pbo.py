"""CSCV PBO lab lite."""

import numpy as np
import pytest

from bolsa_analytics.optimize.pbo import (
    classify_pbo,
    equal_segment_ranges,
    estimate_pbo_cscv,
    pbo_segment_count,
)


def test_pbo_segment_count_even() -> None:
    assert pbo_segment_count(4) == 4
    assert pbo_segment_count(5) == 4
    assert pbo_segment_count(6) == 6
    assert pbo_segment_count(2) == 0


def test_equal_segment_ranges() -> None:
    ranges = equal_segment_ranges(100, 4)
    assert len(ranges) == 4
    assert ranges[0] == (0, 25)
    assert ranges[-1][1] == 100


def test_estimate_pbo_perfect_generalization() -> None:
    # Strategy 0 always best IS and OOS → low PBO
    rng = np.random.default_rng(0)
    matrix = rng.normal(0, 1, size=(6, 8))
    matrix[:, 0] += 5.0
    summary = estimate_pbo_cscv(matrix)
    assert summary["splitCount"] == 20  # C(6,3)
    assert summary["pbo"] < 0.5
    assert classify_pbo(summary["pbo"]) == "low"


def test_estimate_pbo_noise() -> None:
    rng = np.random.default_rng(1)
    matrix = rng.normal(0, 1, size=(6, 12))
    summary = estimate_pbo_cscv(matrix)
    assert 0.0 <= summary["pbo"] <= 1.0
    assert summary["strategyCount"] == 12


def test_estimate_pbo_rejects_odd_s() -> None:
    with pytest.raises(ValueError, match="even"):
        estimate_pbo_cscv(np.zeros((5, 4)))


def test_classify_pbo() -> None:
    assert classify_pbo(0.2) == "low"
    assert classify_pbo(0.55) == "elevated"
    assert classify_pbo(0.8) == "high"
    assert classify_pbo(None) == "n/d"
