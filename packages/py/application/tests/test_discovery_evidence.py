"""V2.36 (incremento 1) — tests del prior de evidencia adaptativo (herméticos).

Certifica el builder determinista del snapshot que alimenta el carril ``adaptive``:

* determinismo (misma evidencia ⇒ mismo hash y mismos pesos),
* fail-closed (sin muestra/evidencia ⇒ ``adaptive_weight = 0.0``),
* cotas (peso acotado, nunca fuera de ``[0, max]``),
* reproducibilidad por hash,
* reparto de cupos del allocator con el peso adaptativo real (sin romper el global).
"""

from __future__ import annotations

import math
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
    evidence_fingerprint,
    snapshot_hash,
)
from bolsa_domain.entities.discovery_evidence_snapshot import (
    MATH_VERSION_DISCOVERY_EVIDENCE_V0,
    MATH_VERSION_DISCOVERY_EVIDENCE_V1,
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
    assert snapshot.math_version == MATH_VERSION_DISCOVERY_EVIDENCE_V1
    assert snapshot.payload["mathVersion"] == MATH_VERSION_DISCOVERY_EVIDENCE_V1


def test_v0_math_version_is_still_reproducible() -> None:
    """La fórmula v0 se conserva para reproducir snapshots históricos."""
    snapshot = _build([_agg("sma", 100, avg_score=1.0)], math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V0)
    assert snapshot.math_version == MATH_VERSION_DISCOVERY_EVIDENCE_V0
    # La v0 saturaba el score en 1.0 * success_ratio(1.0) = 1.0.
    assert snapshot.family_weights == {"sma": 1.0}


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
    # v1: sin métricas opcionales, la señal es 1 - exp(-avgScore) * success_ratio.
    assert 0.0 < weights["sma"] < 1.0


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


# ── V2.37/P2-01 — señal v1 (sin saturación, cobertura explícita) ────────────────


def test_v1_does_not_saturate_above_one() -> None:
    """La v1 conserva información por encima de is_score 1.0 (la v0 la perdía)."""
    base = _agg("sma", 100, avg_score=1.0)
    higher = _agg("sma", 100, avg_score=1.5)
    v1_base, _ = compute_family_weights([base], math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V1)
    v1_higher, _ = compute_family_weights([higher], math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V1)
    assert v1_higher["sma"] > v1_base["sma"]

    v0_base, _ = compute_family_weights([base], math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V0)
    v0_higher, _ = compute_family_weights([higher], math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V0)
    assert v0_higher["sma"] == v0_base["sma"]  # v0 saturaba


def test_v1_absent_metric_is_neutral_not_penalized() -> None:
    """Una métrica ausente arrastra al ancla neutral; no puntúa como 0 ni premia."""
    without_sharpe = _agg("sma", 100, avg_score=1.0)
    with_good_sharpe = {**without_sharpe, "presetKey": "good", "avgSharpe": 3.0}
    with_bad_sharpe = {**without_sharpe, "presetKey": "bad", "avgSharpe": -3.0}
    strengths, _ = compute_family_weights(
        [without_sharpe, with_good_sharpe, with_bad_sharpe],
        math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V1,
    )
    # El dato observado manda: bueno > ausente > malo.
    assert strengths["good"] > strengths["sma"] > strengths["bad"]


def test_v1_drawdown_and_profit_factor_move_the_signal() -> None:
    good = _agg("sma", 100, avg_score=1.0)
    good.update({"avgProfitFactor": 2.0, "avgMaxDrawdownPct": 10.0})
    bad = _agg("sma", 100, avg_score=1.0)
    bad.update({"avgProfitFactor": 0.8, "avgMaxDrawdownPct": 80.0})
    weights, _ = compute_family_weights(
        [{**good, "presetKey": "good"}, {**bad, "presetKey": "bad"}],
        math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V1,
    )
    assert weights["good"] > weights["bad"]


def test_v1_posterior_evidence_raises_strength() -> None:
    plain = _agg("sma", 100, avg_score=1.0)
    posterior = {**plain, "presetKey": "with_posterior", "posteriorWeighted": 4.0, "posteriorCount": 4.0}
    weights, _ = compute_family_weights(
        [plain, posterior], math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V1
    )
    assert weights["with_posterior"] > weights["sma"]


def test_v1_strength_is_bounded() -> None:
    extreme = _agg("sma", 100, avg_score=99.0)
    extreme.update({"avgSharpe": 99.0, "avgProfitFactor": 99.0, "avgMaxDrawdownPct": 0.0})
    weights, _ = compute_family_weights([extreme], math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V1)
    assert 0.0 <= weights["sma"] <= 1.0


# ── V2.37/P2-03 — fingerprint del dataset de evidencia ──────────────────────────


def test_evidence_fingerprint_is_deterministic_and_sensitive() -> None:
    a = [_agg("sma", 10)]
    assert evidence_fingerprint(aggregates=a) == evidence_fingerprint(aggregates=list(a))
    assert evidence_fingerprint(aggregates=a) != evidence_fingerprint(aggregates=[_agg("sma", 11)])


def test_snapshot_carries_fingerprint() -> None:
    snapshot = _build([_agg("sma", 10)])
    assert snapshot.evidence_fingerprint.startswith("sha256:")
    assert snapshot.payload["evidenceFingerprint"] == snapshot.evidence_fingerprint


# ── V2.37/P2-02 — política formal exploración/explotación ───────────────────────


def test_exploration_floor_guarantees_exploration_under_extreme_adaptive() -> None:
    """Con el adaptive al máximo, la exploración conserva su suelo reservado."""
    allocator = DiscoveryBudgetAllocator(
        adaptive_weight=100.0, adaptive_min=5, exploration_floor_ratio=0.5
    )
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    allocation = allocator.allocate(budget)
    exploration = (
        allocation["catalog"].candidates
        + allocation["grammar_simple"].candidates
        + allocation["grammar_composite"].candidates
    )
    assert exploration >= allocator.exploration_floor_candidates(budget)
    assert sum(a.candidates for a in allocation.values()) <= budget.max_candidates


def test_exploration_floor_zero_keeps_history() -> None:
    """Con la política desactivada el reparto es el histórico (adaptive sin cota extra)."""
    allocator = DiscoveryBudgetAllocator(adaptive_weight=100.0, exploration_floor_ratio=0.0)
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    raised = allocator.allocate(budget)
    capped = allocator.normalized().allocate(budget)
    assert raised["adaptive"].candidates == capped["adaptive"].candidates


def test_adaptive_never_absorbs_all_exploration() -> None:
    """Invariante 'champion cannot teach itself': el adaptive no toma el 100 %."""
    allocator = DiscoveryBudgetAllocator(adaptive_weight=1000.0, exploration_floor_ratio=0.9)
    budget = DiscoveryBudget(max_trials_total=100, max_per_family=8, max_candidates=50)
    allocation = allocator.allocate(budget)
    assert allocation["adaptive"].candidates <= budget.max_candidates - int(
        math.ceil(budget.max_candidates * 0.9)
    )


# ── V2.38 (incremento 3) — granularidad por región de parámetros ────────────────


def _agg_region(
    preset: str, region: str, trials: int, *, avg_score: float = 1.0
) -> dict[str, Any]:
    return {
        "presetKey": preset,
        "paramRegion": region,
        "trials": trials,
        "avgScore": avg_score,
        "zeroTrade": 0,
        "failures": 0,
    }


def test_without_region_keys_remain_plain_families() -> None:
    """Compatibilidad byte a byte: sin region, la clave es la familia (como V2.37)."""
    snapshot = _build([_agg("sma", 10), _agg("rsi", 8)])
    assert set(snapshot.sample_sizes) == {"sma", "rsi"}
    assert set(snapshot.family_weights) == {"sma", "rsi"}


def test_composite_key_isolates_regions() -> None:
    """Dos regiones de la misma familia se agregan por separado."""
    snapshot = _build(
        [
            _agg_region("sma", "r00:aaa", 6, avg_score=1.4),
            _agg_region("sma", "r01:bbb", 6, avg_score=0.6),
        ]
    )
    keys = set(snapshot.sample_sizes)
    assert keys == {"sma|r00:aaa", "sma|r01:bbb"}
    assert snapshot.family_weights["sma|r00:aaa"] > snapshot.family_weights["sma|r01:bbb"]


def test_composite_key_hash_is_stable_and_sensitive_to_region() -> None:
    first = _build([_agg_region("sma", "r00:aaa", 6)])
    again = _build([_agg_region("sma", "r00:aaa", 6)])
    other = _build([_agg_region("sma", "r01:bbb", 6)])
    assert first.snapshot_hash == again.snapshot_hash
    assert first.snapshot_hash != other.snapshot_hash


def test_family_granularity_payload_is_populated_when_region_present() -> None:
    """``familyGranularity`` deja de estar vacío y documenta la región real."""
    snapshot = _build([_agg_region("sma", "r00:aaa", 6)])
    granularity = snapshot.payload["familyGranularity"]
    assert granularity == {"sma|r00:aaa": {"family": "sma", "paramRegion": "r00:aaa"}}


def test_family_granularity_is_empty_without_region() -> None:
    snapshot = _build([_agg("sma", 10)])
    assert snapshot.payload["familyGranularity"] == {}


def test_granularity_does_not_change_snapshot_hash_vs_plain_family() -> None:
    """``familyGranularity`` es aditivo: NO participa en el ``snapshot_hash``.

    Nota (V2.38.1/P3): comparar evidencia *distinta* (con y sin region) y ver hashes
    distintos es tautologico — ``familyWeights``/``sampleSizes`` ya difieren. Lo que de
    verdad certifica la exclusion de ``familyGranularity`` del hash es que el hash se
    calcula solo sobre ``mathVersion/windowFrom/windowTo/familyWeights/laneWeights/
    sampleSizes`` (ver ``snapshot_hash``): el payload (que incluye granularidad y
    fingerprint) NO entra.
    """
    plain = _build([_agg("sma", 6)])
    granular = _build([_agg_region("sma", "r00:aaa", 6)])
    # Distinta evidencia ⇒ hashes distintos (por los pesos/muestras, no por la granularidad).
    assert plain.snapshot_hash != granular.snapshot_hash
    # El fingerprint sí refleja la region (identidad del dataset).
    assert plain.evidence_fingerprint != granular.evidence_fingerprint
    # La granularidad viaja en el payload, pero fuera de la clave de identidad del snapshot.
    assert "familyGranularity" in granular.payload
    assert snapshot_hash(
        math_version=granular.math_version,
        window_from=granular.window_from,
        window_to=granular.window_to,
        family_weights=granular.family_weights,
        lane_weights=granular.lane_weights,
        sample_sizes=granular.sample_sizes,
    ) == granular.snapshot_hash


def test_fingerprint_is_order_insensitive_across_regions() -> None:
    """V2.38.1/P2-02: el fingerprint es determinista ante orden adverso de regiones.

    Antes solo se ordenaba por ``presetKey``: con dos regiones de la MISMA familia, el
    orden relativo dependia del orden de entrada (``sorted`` es estable), lo que hacia
    fragil un valor que es identidad del dataset. El orden canonico es la clave compuesta.
    """
    from bolsa_application.discovery_evidence import evidence_fingerprint

    rows = [
        _agg_region("sma", "r00:aaa", 6, avg_score=1.4),
        _agg_region("sma", "r01:bbb", 6, avg_score=0.6),
    ]
    reversed_rows = list(reversed(rows))
    assert evidence_fingerprint(aggregates=rows) == evidence_fingerprint(
        aggregates=reversed_rows
    )


def test_fingerprint_is_order_insensitive_across_families_and_regions() -> None:
    """V2.38.1/P2-02: el orden no importa ni entre familias ni entre regiones."""
    from bolsa_application.discovery_evidence import evidence_fingerprint

    rows = [
        _agg("rsi", 8),
        _agg_region("sma", "r01:bbb", 6, avg_score=0.6),
        _agg_region("sma", "r00:aaa", 6, avg_score=1.4),
        _agg("macd", 5),
    ]
    shuffled = [rows[2], rows[0], rows[3], rows[1]]
    assert evidence_fingerprint(aggregates=rows) == evidence_fingerprint(aggregates=shuffled)


def test_mixed_region_and_plain_family_coexist() -> None:
    """Evidencia histórica (sin region) y nueva (con region) pueden coexistir."""
    snapshot = _build(
        [
            _agg("sma", 4),
            _agg_region("sma", "r00:aaa", 6),
        ]
    )
    assert set(snapshot.sample_sizes) == {"sma", "sma|r00:aaa"}


# ── V2.39 (incremento 4) — régimen de mercado como dimensión paralela ───────────


def _agg_regime(
    preset: str,
    regime: str,
    trials: int,
    *,
    region: str = "",
    avg_score: float = 1.0,
) -> dict[str, Any]:
    return {
        "presetKey": preset,
        "paramRegion": region,
        "regime": regime,
        "trials": trials,
        "avgScore": avg_score,
        "zeroTrade": 0,
        "failures": 0,
    }


def test_regime_does_not_enter_the_granularity_key() -> None:
    """V2.39: el régimen es paralelo; la clave sigue siendo `familia|region`."""
    snapshot = _build(
        [
            _agg_regime("sma", "trend_up", 6),
            _agg_regime("sma", "range", 6),
        ]
    )
    # Ambas filas colapsan en la MISMA clave de granularidad (no hay region).
    assert set(snapshot.sample_sizes) == {"sma"}
    assert set(snapshot.family_weights) == {"sma"}


def test_regime_granularity_payload_is_populated_when_regime_present() -> None:
    """``regimeGranularity`` publica el desglose por régimen, aditivo y aparte."""
    snapshot = _build(
        [
            _agg_regime("sma", "trend_up", 6, region="r00:aaa"),
            _agg_regime("sma", "range", 4, region="r00:aaa"),
        ]
    )
    assert snapshot.payload["regimeGranularity"] == {
        "sma|r00:aaa": {"trend_up": 6, "range": 4}
    }


def test_regime_granularity_is_empty_without_regime() -> None:
    snapshot = _build([_agg("sma", 10)])
    assert snapshot.payload["regimeGranularity"] == {}


def test_regime_does_not_change_snapshot_hash_vs_no_regime() -> None:
    """El régimen NO participa en el ``snapshot_hash`` (dimension observable).

    Igual que ``familyGranularity``: el hash se calcula solo sobre
    ``mathVersion/windowFrom/windowTo/familyWeights/laneWeights/sampleSizes``. Se
    certifica reconstruyendo el hash a mano desde esos componentes y comprobando que
    coincide con el del snapshot que sí lleva régimen en el payload.
    """
    with_regime = _build([_agg_regime("sma", "trend_up", 6)])
    assert with_regime.payload["regimeGranularity"] == {"sma": {"trend_up": 6}}
    assert (
        snapshot_hash(
            math_version=with_regime.math_version,
            window_from=with_regime.window_from,
            window_to=with_regime.window_to,
            family_weights=with_regime.family_weights,
            lane_weights=with_regime.lane_weights,
            sample_sizes=with_regime.sample_sizes,
        )
        == with_regime.snapshot_hash
    )


def test_regime_changes_evidence_fingerprint() -> None:
    """El régimen SÍ entra en el fingerprint (identidad del dataset de research)."""
    from bolsa_application.discovery_evidence import evidence_fingerprint

    up = [_agg_regime("sma", "trend_up", 6)]
    down = [_agg_regime("sma", "trend_down", 6)]
    assert evidence_fingerprint(aggregates=up) != evidence_fingerprint(aggregates=down)


def test_fingerprint_is_order_insensitive_across_regimes() -> None:
    """V2.39: el fingerprint no depende del orden de las filas de régimen."""
    from bolsa_application.discovery_evidence import evidence_fingerprint

    rows = [
        _agg_regime("sma", "trend_up", 6),
        _agg_regime("sma", "range", 6),
        _agg_regime("sma", "high_vol", 3),
    ]
    assert evidence_fingerprint(aggregates=rows) == evidence_fingerprint(
        aggregates=list(reversed(rows))
    )


def test_regime_and_region_coexist_without_key_collision() -> None:
    """Región y régimen conviven: la clave compuesta no incorpora el régimen."""
    snapshot = _build(
        [
            _agg_regime("sma", "trend_up", 6, region="r00:aaa"),
            _agg_regime("sma", "range", 4, region="r01:bbb"),
        ]
    )
    assert set(snapshot.sample_sizes) == {"sma|r00:aaa", "sma|r01:bbb"}
    assert snapshot.payload["regimeGranularity"] == {
        "sma|r00:aaa": {"trend_up": 6},
        "sma|r01:bbb": {"range": 4},
    }
