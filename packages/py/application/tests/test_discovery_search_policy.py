"""V2.37 (incremento 2) — tests de la search policy adaptativa (herméticos).

Certifica la política que convierte el prior de evidencia por familia en cuotas de
emisión deterministas:

* determinismo (misma entrada ⇒ mismo hash y mismas cuotas),
* fail-closed (sin snapshot / sin evidencia / sin cupo ⇒ política vacía),
* exploración garantizada (la explotación nunca absorbe el 100 %),
* la emisión adaptativa del motor no rompe el presupuesto global ni el histórico
  (con política ausente la salida es la de V2.36).
"""

from __future__ import annotations

from typing import Any

from bolsa_application.discovery_catalog import (
    DISCOVERY_FAMILIES,
    DiscoveryBudget,
    DiscoveryBudgetAllocator,
)
from bolsa_application.discovery_evidence import build_discovery_evidence_snapshot
from bolsa_application.discovery_search_policy import (
    MATH_VERSION_SEARCH_POLICY_V0,
    build_search_policy,
)
from bolsa_application.strategy_discovery_engine import (
    ADAPTIVE_FAMILY_PREFIX,
    discover_for_instrument_with_summary,
)


def _snapshot(families: dict[str, int], **kwargs: Any) -> Any:
    aggregates = [
        {
            "presetKey": name,
            "trials": trials,
            "avgScore": 1.0,
            "zeroTrade": 0,
            "failures": 0,
        }
        for name, trials in families.items()
    ]
    return build_discovery_evidence_snapshot(
        snapshot_id="snap-1",
        created_at="2026-09-11T00:00:00+00:00",
        window_from="2026-01-01T00:00:00+00:00",
        window_to="2026-09-11T00:00:00+00:00",
        aggregates=aggregates,
        **kwargs,
    )


# ── Determinismo ────────────────────────────────────────────────────────────────


def test_same_snapshot_yields_same_policy_and_hash() -> None:
    snapshot = _snapshot({"ema_crossover": 20, "rsi_mean_reversion": 10})
    first = build_search_policy(snapshot, adaptive_cap=10)
    second = build_search_policy(snapshot, adaptive_cap=10)
    assert first.policy_hash == second.policy_hash
    assert first.quotas == second.quotas
    assert first.math_version == MATH_VERSION_SEARCH_POLICY_V0


def test_policy_quotas_never_exceed_cap() -> None:
    snapshot = _snapshot({f.name: 10 for f in DISCOVERY_FAMILIES})
    policy = build_search_policy(snapshot, adaptive_cap=7)
    assert policy.total_quota <= 7
    assert sum(q.quota for q in policy.quotas) == policy.total_quota


# ── Fail-closed ─────────────────────────────────────────────────────────────────


def test_no_snapshot_is_empty_policy() -> None:
    policy = build_search_policy(None, adaptive_cap=10)
    assert policy.is_empty()
    assert policy.total_quota == 0


def test_zero_cap_is_empty_policy() -> None:
    snapshot = _snapshot({"ema_crossover": 20})
    assert build_search_policy(snapshot, adaptive_cap=0).is_empty()


def test_no_evidence_is_empty_policy() -> None:
    snapshot = _snapshot({})  # sin familias
    assert build_search_policy(snapshot, adaptive_cap=10).is_empty()


def test_unavailable_families_yield_empty_policy() -> None:
    snapshot = _snapshot({"familia_inexistente": 20})
    policy = build_search_policy(
        snapshot, adaptive_cap=10, available_families=[f.name for f in DISCOVERY_FAMILIES]
    )
    assert policy.is_empty()


# ── Exploración garantizada ─────────────────────────────────────────────────────


def test_exploitation_never_absorbs_all() -> None:
    families = {f.name: 10 for f in DISCOVERY_FAMILIES}
    snapshot = _snapshot(families)
    policy = build_search_policy(
        snapshot,
        adaptive_cap=20,
        available_families=list(families),
        exploitation_top_k=2,
        exploration_ratio=0.25,
    )
    assert policy.exploration_quota > 0
    assert any(q.exploration for q in policy.quotas)


def test_more_evidence_gets_at_least_as_much_quota_top_k() -> None:
    snapshot = _snapshot({"ema_crossover": 100, "rsi_mean_reversion": 3})
    policy = build_search_policy(
        snapshot, adaptive_cap=10, exploitation_top_k=1, exploration_ratio=0.2
    )
    assert policy.quota_for("ema_crossover") >= policy.quota_for("rsi_mean_reversion")


# ── Emisión adaptativa real en el motor ─────────────────────────────────────────


def _budget() -> DiscoveryBudget:
    return DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)


def test_adaptive_emission_without_policy_keeps_history() -> None:
    """Sin política, el carril adaptativo no emite (comportamiento V2.36)."""
    from bolsa_application.discovery_grammar import GrammarBudget

    allocator = DiscoveryBudgetAllocator(adaptive_weight=0.5)
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=_budget(),
        grammar_budget=GrammarBudget(base=_budget()),
        allocator=allocator,
        search_policy=None,
    )
    assert summary.adaptive_candidates == 0
    assert not any(c.strategy_family.startswith(ADAPTIVE_FAMILY_PREFIX) for c in candidates)


def test_adaptive_emission_emits_within_global_budget() -> None:
    from bolsa_application.discovery_grammar import GrammarBudget

    snapshot = _snapshot({f.name: 20 for f in DISCOVERY_FAMILIES})
    allocator = DiscoveryBudgetAllocator(adaptive_weight=0.5, adaptive_min=2)
    budget = _budget()
    allocation = allocator.allocate(budget)
    adaptive_cap = allocation["adaptive"].candidates
    policy = build_search_policy(
        snapshot, adaptive_cap=adaptive_cap, available_families=[f.name for f in DISCOVERY_FAMILIES]
    )
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
        allocator=allocator,
        search_policy=policy,
    )
    assert summary.adaptive_candidates <= adaptive_cap
    assert len(candidates) <= budget.max_candidates
    assert summary.trials_used <= budget.max_trials_total
    assert summary.adaptive_policy_hash == policy.policy_hash


def test_adaptive_emission_is_deterministic() -> None:
    from bolsa_application.discovery_grammar import GrammarBudget

    snapshot = _snapshot({f.name: 20 for f in DISCOVERY_FAMILIES})
    allocator = DiscoveryBudgetAllocator(adaptive_weight=0.5, adaptive_min=2)
    budget = _budget()
    adaptive_cap = allocator.allocate(budget)["adaptive"].candidates
    policy = build_search_policy(snapshot, adaptive_cap=adaptive_cap)

    def run() -> tuple[str, ...]:
        candidates, _ = discover_for_instrument_with_summary(
            instrument_id="AAA",
            budget=budget,
            grammar_budget=GrammarBudget(base=budget),
            allocator=allocator,
            search_policy=policy,
        )
        return tuple(c.id for c in candidates)

    assert run() == run()


# ── V2.38 (incremento 3) — emisión adaptativa por región ────────────────────────


def _snapshot_with_regions() -> Any:
    """Snapshot con una familia partida en dos regiones de parámetros."""
    family = next(f for f in DISCOVERY_FAMILIES if len(f.param_points()) >= 2)
    points = family.param_points()
    from bolsa_application.discovery_param_region import param_region_for_point

    region_a = param_region_for_point(family.param_space, points[0])
    region_b = param_region_for_point(family.param_space, points[1])
    assert region_a and region_b and region_a != region_b
    aggregates = [
        {
            "presetKey": family.name,
            "paramRegion": region_a,
            "trials": 20,
            "avgScore": 1.4,
            "zeroTrade": 0,
            "failures": 0,
        },
        {
            "presetKey": family.name,
            "paramRegion": region_b,
            "trials": 3,
            "avgScore": 0.5,
            "zeroTrade": 0,
            "failures": 0,
        },
    ]
    return build_discovery_evidence_snapshot(
        snapshot_id="snap-region",
        created_at="2026-09-11T00:00:00+00:00",
        window_from="2026-01-01T00:00:00+00:00",
        window_to="2026-09-11T00:00:00+00:00",
        aggregates=aggregates,
    ), family.name, region_a, region_b


def test_region_policy_keys_are_composite_and_hash_versioned() -> None:
    from bolsa_application.discovery_search_policy import GRANULARITY_KEY_VERSION_V0

    snapshot, family, region_a, region_b = _snapshot_with_regions()
    policy = build_search_policy(
        snapshot,
        adaptive_cap=10,
        available_families=[f"{family}|{region_a}", f"{family}|{region_b}"],
    )
    assert policy.metadata["granularityKeyVersion"] == GRANULARITY_KEY_VERSION_V0
    assert any(q.family == f"{family}|{region_a}" for q in policy.quotas)


def test_adaptive_emission_filters_to_requested_region() -> None:
    """Emitir por region NO emite puntos de otra region (fail-closed al grid)."""
    from bolsa_application.discovery_grammar import GrammarBudget

    snapshot, family, region_a, region_b = _snapshot_with_regions()
    allocator = DiscoveryBudgetAllocator(adaptive_weight=0.5, adaptive_min=1)
    budget = _budget()
    adaptive_cap = allocator.allocate(budget)["adaptive"].candidates
    policy = build_search_policy(
        snapshot, adaptive_cap=adaptive_cap, available_families=[family]
    )
    candidates, _ = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
        allocator=allocator,
        search_policy=policy,
    )
    adaptive = [c for c in candidates if c.strategy_family.startswith(ADAPTIVE_FAMILY_PREFIX)]
    # Toda candidata adaptativa de esta familia lleva una región real y nunca la región
    # "explorada" con evidencia escasa no debe colarse en la cuota de la región fuerte.
    regions = {
        c.params.get("discovery_param_region")
        for c in adaptive
        if c.params.get("discovery_family") == family
    }
    assert regions <= {region_a, region_b}


def test_unknown_region_is_fail_closed() -> None:
    """Una región que no existe en el grid no emite nada (no se aproxima)."""
    from bolsa_application.discovery_grammar import GrammarBudget
    from bolsa_application.discovery_search_policy import FamilyQuota, SearchPolicy

    snapshot, family, _, _ = _snapshot_with_regions()
    policy = SearchPolicy(
        quotas=(FamilyQuota(family=f"{family}|r99:inexistente", quota=5, weight=1.0),),
        total_quota=5,
        exploration_quota=0,
        math_version=MATH_VERSION_SEARCH_POLICY_V0,
        policy_hash="test",
    )
    budget = _budget()
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
        allocator=DiscoveryBudgetAllocator(adaptive_weight=0.5, adaptive_min=1),
        search_policy=policy,
    )
    assert summary.adaptive_candidates == 0
    assert not any(c.strategy_family.startswith(ADAPTIVE_FAMILY_PREFIX) for c in candidates)
