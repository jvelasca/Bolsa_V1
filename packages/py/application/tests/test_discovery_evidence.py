"""V2.36 (incremento 1) — tests del prior de evidencia adaptativo (herméticos).

Certifica el builder determinista del snapshot que alimenta el carril ``adaptive``:

* determinismo (misma evidencia ⇒ mismo hash y mismos pesos),
* fail-closed (sin muestra/evidencia ⇒ ``adaptive_weight = 0.0``),
* cotas (peso acotado, nunca fuera de ``[0, max]``),
* reproducibilidad por hash,
* reparto de cupos del allocator con el peso adaptativo real (sin romper el global).
"""

from __future__ import annotations

from typing import Any

from bolsa_application.discovery_catalog import (
    DiscoveryBudget,
    DiscoveryBudgetAllocator,
)
from bolsa_application.discovery_evidence import (
    DEFAULT_MAX_ADAPTIVE_WEIGHT,
    build_discovery_evidence_snapshot,
    compute_family_weights,
    compute_lane_weights,
    snapshot_hash,
)
from bolsa_domain.entities.discovery_evidence_snapshot import (
    MATH_VERSION_DISCOVERY_EVIDENCE_V0,
)


def _agg(
    preset: str,
    trials: int,
    *,
    avg_score: float | None = 1.0,
    zero_trade: int = 0,
    failures: int = 0,
) -> dict[str, Any]:
    return {
        "presetKey": preset,
        "trials": trials,
        "avgScore": avg_score,
        "zeroTrade": zero_trade,
        "failures": failures,
    }


def _build(aggregates: list[dict[str, Any]], **kwargs: Any) -> Any:
    return build_discovery_evidence_snapshot(
        snapshot_id="snap-1",
        created_at="2026-09-11T00:00:00+00:00",
        window_from="2026-01-01T00:00:00+00:00",
        window_to="2026-09-11T00:00:00+00:00",
        aggregates=aggregates,
        **kwargs,
    )


# ── Determinismo ────────────────────────────────────────────────────────────────


def test_same_evidence_yields_same_hash_and_weights() -> None:
    aggregates = [_agg("sma", 10), _agg("rsi", 8, avg_score=0.5)]
    first = _build(aggregates)
    second = _build(aggregates)
    assert first.snapshot_hash == second.snapshot_hash
    assert first.family_weights == second.family_weights
    assert first.lane_weights == second.lane_weights


def test_family_order_does_not_change_hash() -> None:
    """El hash es orden-insensible: el builder ordena por familia canónicamente."""
    a = _build([_agg("sma", 10), _agg("rsi", 8)])
    b = _build([_agg("rsi", 8), _agg("sma", 10)])
    assert a.snapshot_hash == b.snapshot_hash


def test_compute_family_weights_orders_canonically() -> None:
    weights, samples = compute_family_weights(
        [_agg("zeta", 5), _agg("alfa", 5), _agg("mid", 5)]
    )
    assert list(weights) == ["alfa", "mid", "zeta"]
    assert list(samples) == ["alfa", "mid", "zeta"]


def test_math_version_is_persisted() -> None:
    snapshot = _build([_agg("sma", 10)])
    assert snapshot.math_version == MATH_VERSION_DISCOVERY_EVIDENCE_V0
    assert snapshot.payload["mathVersion"] == MATH_VERSION_DISCOVERY_EVIDENCE_V0


# ── Fail-closed ─────────────────────────────────────────────────────────────────


def test_no_evidence_yields_zero_adaptive_weight() -> None:
    snapshot = _build([])
    assert snapshot.adaptive_weight() == 0.0
    assert snapshot.has_evidence() is False


def test_families_below_min_samples_do_not_enable_lane() -> None:
    """Con muestra total insuficiente el carril adaptativo queda apagado (0.0)."""
    snapshot = _build([_agg("sma", 1), _agg("rsi", 1)])
    assert snapshot.adaptive_weight() == 0.0


def test_insufficient_samples_produce_no_family_weights() -> None:
    weights, samples = compute_family_weights([_agg("sma", 1)], min_samples=3)
    assert weights == {}
    assert samples == {"sma": 1}


def test_unknown_family_key_is_ignored() -> None:
    weights, samples = compute_family_weights([_agg("", 10), _agg("sma", 10)])
    assert "" not in weights
    assert "" not in samples
    assert weights == {"sma": 1.0}


# ── Cota ────────────────────────────────────────────────────────────────────────


def test_adaptive_weight_is_bounded_by_max() -> None:
    snapshot = _build(
        [_agg("sma", 100, avg_score=1.0)], max_adaptive_weight=0.25
    )
    assert 0.0 < snapshot.adaptive_weight() <= 0.25


def test_adaptive_weight_never_exceeds_one_even_with_high_scores() -> None:
    snapshot = _build([_agg("sma", 100, avg_score=99.0)])
    assert snapshot.adaptive_weight() <= DEFAULT_MAX_ADAPTIVE_WEIGHT


def test_failures_lower_family_strength() -> None:
    healthy = _build([_agg("sma", 100, avg_score=1.0, failures=0)])
    unhealthy = _build([_agg("sma", 100, avg_score=1.0, failures=100)])
    assert healthy.adaptive_weight() > unhealthy.adaptive_weight()


def test_lane_weights_keep_other_lanes_at_defaults() -> None:
    snapshot = _build([_agg("sma", 100, avg_score=1.0)])
    assert snapshot.lane_weights["catalog"] == 2.0
    assert snapshot.lane_weights["grammar_simple"] == 1.0
    assert snapshot.lane_weights["grammar_composite"] == 1.0


# ── Reproducibilidad por hash ───────────────────────────────────────────────────


def test_snapshot_hash_is_stable_across_equivalent_dicts() -> None:
    kwargs = {
        "math_version": MATH_VERSION_DISCOVERY_EVIDENCE_V0,
        "window_from": "a",
        "window_to": "b",
        "family_weights": {"sma": 1.0, "rsi": 0.5},
        "lane_weights": {"adaptive": 0.4, "catalog": 2.0},
        "sample_sizes": {"sma": 10, "rsi": 8},
    }
    other = {
        "math_version": MATH_VERSION_DISCOVERY_EVIDENCE_V0,
        "window_from": "a",
        "window_to": "b",
        "family_weights": {"rsi": 0.5, "sma": 1.0},
        "lane_weights": {"catalog": 2.0, "adaptive": 0.4},
        "sample_sizes": {"rsi": 8, "sma": 10},
    }
    assert snapshot_hash(**kwargs) == snapshot_hash(**other)


def test_different_evidence_changes_hash() -> None:
    a = _build([_agg("sma", 100)])
    b = _build([_agg("sma", 101)])
    assert a.snapshot_hash != b.snapshot_hash


# ── Reparto del allocator con el peso adaptativo real ───────────────────────────


def test_allocator_gives_adaptive_lane_a_real_quota_without_breaking_global() -> None:
    snapshot = _build([_agg("sma", 100, avg_score=1.0)])
    allocator = DiscoveryBudgetAllocator(
        adaptive_weight=snapshot.adaptive_weight()
    )
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    allocation = allocator.allocate(budget)
    assert allocation["adaptive"].candidates >= 1
    assert sum(a.candidates for a in allocation.values()) <= budget.max_candidates
    assert sum(a.trials for a in allocation.values()) <= budget.max_trials_total


def test_zero_weight_adaptive_lane_keeps_history() -> None:
    """Con peso 0 (fail-closed) el reparto es el histórico: adaptive sin cupo."""
    allocator = DiscoveryBudgetAllocator(adaptive_weight=0.0)
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    allocation = allocator.allocate(budget)
    assert allocation["adaptive"].candidates == 0


def test_compute_lane_weights_fail_closed_when_total_below_threshold() -> None:
    lane_weights = compute_lane_weights(
        {"sma": 1.0}, {"sma": 2}, min_total_samples=12
    )
    assert lane_weights["adaptive"] == 0.0
