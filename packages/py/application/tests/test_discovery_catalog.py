"""V2.31 / A11 — tests del catálogo de descubrimiento (herméticos, sin DB/red).

Certifica el search space curado: familias por rama, espacios de parámetros pequeños,
plantillas que materializan definiciones evaluables por el motor de reglas, y
fail-closed cuando faltan parámetros.
"""

from __future__ import annotations

from bolsa_application.discovery_catalog import (
    DISCOVERY_FAMILIES,
    PARENT_MOMENTUM,
    PARENT_TREND,
    PARENT_VOLATILITY,
    CatalogLane,
    DiscoveryBudget,
    DiscoveryBudgetAllocator,
    GrammarLane,
    families_by_parent,
    family_by_name,
    iter_param_points,
)


def test_catalog_has_three_parent_branches() -> None:
    parents = {family.parent for family in DISCOVERY_FAMILIES}
    assert parents == {PARENT_TREND, PARENT_MOMENTUM, PARENT_VOLATILITY}


def test_catalog_covers_more_than_the_three_h0_families() -> None:
    # Antes de V2.31 solo existían SMA/RSI/MACD: el catálogo debe superarlas claramente.
    assert len(DISCOVERY_FAMILIES) >= 10
    names = {family.name for family in DISCOVERY_FAMILIES}
    assert {"ema_crossover", "donchian_breakout", "bb_reversion"} <= names


def test_every_family_declares_indicators_and_small_param_space() -> None:
    for family in DISCOVERY_FAMILIES:
        assert family.indicator_ids, family.name
        assert family.param_space, family.name
        # Anti-explosión: cada lista del grid es pequeña (<= 4 valores).
        for key, values in family.param_space.items():
            assert 0 < len(values) <= 4, f"{family.name}.{key}={values}"
        # El producto cartesiano total debe ser pequeño (<= 8 puntos por familia).
        assert len(family.param_points()) <= 8, family.name


def test_param_points_are_deterministic_cartesian() -> None:
    space = {"a": (1, 2), "b": ("x", "y")}
    points = iter_param_points(space)
    assert points == [
        {"a": 1, "b": "x"},
        {"a": 1, "b": "y"},
        {"a": 2, "b": "x"},
        {"a": 2, "b": "y"},
    ]
    assert iter_param_points(space) == points  # reproducible


def test_templates_materialize_evaluable_definitions() -> None:
    for family in DISCOVERY_FAMILIES:
        produced = 0
        for point in family.param_points():
            definition = family.template(point)
            if definition is None:
                continue
            produced += 1
            assert definition["presetKey"]
            assert definition["indicatorSpecs"]
            entries = definition["entries"]["rules"]
            exits = definition["exits"]["rules"]
            assert entries and exits
            assert all(rule["signalKind"] in {"entry_long", "exit"} for rule in entries + exits)
        # Cada familia del catálogo debe poder materializar al menos un punto.
        assert produced >= 1, family.name


def test_templates_fail_closed_on_incomplete_params() -> None:
    # Un punto vacío no debe producir una definición a medias.
    assert family_by_name("ema_crossover").template({}) is None  # type: ignore[union-attr]
    assert family_by_name("rsi_mean_reversion").template({}) is None  # type: ignore[union-attr]


def test_family_lookup_and_parent_filter() -> None:
    assert family_by_name("ema_crossover") is not None
    assert family_by_name("nope") is None
    assert families_by_parent(PARENT_TREND)
    assert all(f.parent == PARENT_TREND for f in families_by_parent(PARENT_TREND))
    assert families_by_parent() == DISCOVERY_FAMILIES


def test_budget_normalizes_to_positive() -> None:
    budget = DiscoveryBudget(max_trials_total=0, max_per_family=-1, max_candidates=0, min_bars=0)
    normalized = budget.normalized()
    assert normalized.max_trials_total >= 1
    assert normalized.max_per_family >= 1
    assert normalized.max_candidates >= 1
    assert normalized.min_bars >= 1


# ── V2.36/A16 (P2-03): allocator explícito de presupuesto por carril ────────────


def test_allocator_declares_the_four_lanes() -> None:
    """El allocator reparte entre catálogo, gramática simple/compuesta y adaptive."""
    allocation = DiscoveryBudgetAllocator().allocate(DiscoveryBudget())
    assert set(allocation) == {
        CatalogLane.NAME,
        GrammarLane.SIMPLE,
        GrammarLane.COMPOSITE,
        "adaptive",
    }


def test_allocator_is_deterministic_and_idempotent() -> None:
    """Mismo allocator + mismo presupuesto ⇒ mismo reparto, repetible."""
    allocator = DiscoveryBudgetAllocator()
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    first = allocator.allocate(budget)
    second = allocator.allocate(budget)
    assert first == second
    assert allocator.allocate(budget) == first


def test_allocator_never_exceeds_global_budget() -> None:
    """La suma de cupos por carril nunca supera ``max_candidates``/``max_trials_total``."""
    allocator = DiscoveryBudgetAllocator()
    for budget in (
        DiscoveryBudget(),
        DiscoveryBudget(max_trials_total=3, max_per_family=1, max_candidates=1),
        DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24),
        DiscoveryBudget(max_trials_total=100, max_per_family=4, max_candidates=7),
    ):
        allocation = allocator.allocate(budget)
        assert sum(a.candidates for a in allocation.values()) <= budget.max_candidates
        assert sum(a.trials for a in allocation.values()) <= budget.max_trials_total


def test_allocator_guarantees_non_zero_share_to_grammar() -> None:
    """La gramática recibe cupo > 0 con los pesos por defecto (bug A14 no reaparece)."""
    allocation = DiscoveryBudgetAllocator().allocate(DiscoveryBudget())
    assert allocation[GrammarLane.SIMPLE].candidates > 0
    assert allocation[CatalogLane.NAME].candidates > 0


def test_allocator_guarantees_catalog_share_so_grammar_cannot_starve_it() -> None:
    """Aunque la gramática tenga mucho peso, el catálogo conserva su cupo."""
    allocator = DiscoveryBudgetAllocator(
        catalog_weight=0.1,
        grammar_simple_weight=10.0,
        grammar_composite_weight=10.0,
    )
    allocation = allocator.allocate(DiscoveryBudget())
    assert allocation[CatalogLane.NAME].candidates > 0


def test_allocator_order_independence_of_lane_weights() -> None:
    """Intercambiar el peso de dos carriles intercambia sus cupos (no los anula).

    La asignación depende SOLO de los pesos, no de quién consome primero: permutar
    dos pesos simétricos produce la permutación simétrica de los cupos.
    """
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    base = DiscoveryBudgetAllocator(
        catalog_weight=2.0, grammar_simple_weight=1.0, grammar_composite_weight=1.0
    ).allocate(budget)
    swapped = DiscoveryBudgetAllocator(
        catalog_weight=1.0, grammar_simple_weight=2.0, grammar_composite_weight=1.0
    ).allocate(budget)
    assert swapped[GrammarLane.SIMPLE].candidates > base[GrammarLane.SIMPLE].candidates
    assert swapped[CatalogLane.NAME].candidates < base[CatalogLane.NAME].candidates
    # Ambos carriles conservan cupo (nadie queda a 0 por el orden).
    assert swapped[CatalogLane.NAME].candidates > 0
    assert swapped[GrammarLane.SIMPLE].candidates > 0


def test_allocator_adaptive_lane_is_a_zero_placeholder() -> None:
    """``adaptive`` no aprende ni emite: peso 0 ⇒ cupo 0 con los defaults."""
    allocation = DiscoveryBudgetAllocator().allocate(DiscoveryBudget())
    assert allocation["adaptive"].candidates == 0
    assert allocation["adaptive"].trials == 0


def test_allocator_all_zero_weights_falls_back_to_catalog() -> None:
    """Sin pesos ni pisos el reparto degenerado da todo al catálogo (compatibilidad)."""
    allocator = DiscoveryBudgetAllocator(
        catalog_weight=0.0,
        grammar_simple_weight=0.0,
        grammar_composite_weight=0.0,
        adaptive_weight=0.0,
        catalog_min=0,
        grammar_simple_min=0,
        grammar_composite_min=0,
        adaptive_min=0,
    )
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    allocation = allocator.allocate(budget)
    assert allocation[CatalogLane.NAME].candidates == 24
    assert sum(a.candidates for a in allocation.values()) == 24


def test_allocator_normalizes_negative_and_nan_weights() -> None:
    """Pesos negativos/NaN se sanean a 0 (fail-safe, sin reparto negativo)."""
    allocator = DiscoveryBudgetAllocator(
        catalog_weight=-5.0, grammar_simple_weight=float("nan")
    ).normalized()
    assert allocator.catalog_weight == 0.0
    assert allocator.grammar_simple_weight == 0.0


def test_allocator_normalized_weights_sum_to_one() -> None:
    """Los pesos normalizados son una distribución (suman 1.0) y son deterministas."""
    weights = DiscoveryBudgetAllocator().normalized_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights[CatalogLane.NAME] == 0.5
    assert weights[GrammarLane.SIMPLE] == 0.25
    assert weights["adaptive"] == 0.0


def test_allocator_lane_for_grammar_maps_simple_and_composite() -> None:
    """El carril de gramática distingue plan simple (1 bloque opcional) de compuesto."""
    allocator = DiscoveryBudgetAllocator()
    assert allocator.lane_for_grammar(composite=False) == GrammarLane.SIMPLE
    assert allocator.lane_for_grammar(composite=True) == GrammarLane.COMPOSITE
