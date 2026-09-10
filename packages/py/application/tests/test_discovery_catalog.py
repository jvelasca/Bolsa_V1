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
    DiscoveryBudget,
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
