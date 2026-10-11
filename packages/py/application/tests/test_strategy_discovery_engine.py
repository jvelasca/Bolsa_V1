"""V2.31 / A11 — tests del StrategyDiscoveryEngine (herméticos, sin DB/red).

Certifica que el motor emite candidatas reproducibles desde el catálogo, respeta el
presupuesto global, filtra por rama y aplica fail-closed (sin familias ⇒ sin
candidatas; plantillas incompletas no se inventan).
"""

from __future__ import annotations

from bolsa_application.discovery_catalog import (
    PARENT_MOMENTUM,
    PARENT_TREND,
    DiscoveryBudget,
    DiscoveryFamily,
)
from bolsa_application.strategy_discovery_engine import (
    discover_candidates,
    discover_for_instrument,
    discover_from_universe,
)


def test_discover_emits_candidates_with_definition() -> None:
    candidates = discover_for_instrument(instrument_id="AAA")
    assert candidates
    for candidate in candidates:
        assert candidate.instrument_id == "AAA"
        assert candidate.origin == "discovery"
        assert isinstance(candidate.params.get("definition"), dict)
        assert candidate.params["definition"]["presetKey"]
        assert candidate.params["discovery_family"] == candidate.strategy_family
        assert candidate.params["discovery_parent"] in {
            PARENT_TREND,
            PARENT_MOMENTUM,
            "volatility",
        }


def test_discover_is_deterministic() -> None:
    first = discover_for_instrument(instrument_id="AAA")
    second = discover_for_instrument(instrument_id="AAA")
    assert [c.id for c in first] == [c.id for c in second]
    assert [c.strategy_family for c in first] == [c.strategy_family for c in second]


def test_budget_caps_candidates_and_trials() -> None:
    budget = DiscoveryBudget(max_trials_total=5, max_per_family=2, max_candidates=3)
    candidates = discover_for_instrument(instrument_id="AAA", budget=budget)
    assert len(candidates) == 3

    # max_per_family: ninguna familia puede aportar más de 2 candidatas.
    per_family: dict[str, int] = {}
    for candidate in candidates:
        per_family[candidate.strategy_family] = per_family.get(candidate.strategy_family, 0) + 1
    assert all(count <= 2 for count in per_family.values())


def test_parent_filter_restricts_catalog() -> None:
    candidates = discover_for_instrument(instrument_id="AAA", parent=PARENT_MOMENTUM)
    assert candidates
    assert all(c.params["discovery_parent"] == PARENT_MOMENTUM for c in candidates)


def test_empty_catalog_yields_no_candidates() -> None:
    assert discover_for_instrument(instrument_id="AAA", families=()) == ()


def test_bar_count_filters_families_below_warmup() -> None:
    # Con muy pocas barras, las familias con min_bars_hint alto se descartan.
    candidates = discover_for_instrument(instrument_id="AAA", bar_count=1)
    assert candidates == ()


def test_discover_candidates_alias_matches() -> None:
    assert discover_candidates(instrument_id="AAA") == discover_for_instrument(
        instrument_id="AAA"
    )


def test_custom_id_factory_is_used() -> None:
    candidates = discover_for_instrument(
        instrument_id="AAA",
        candidate_id_factory=lambda instrument, index: f"custom-{instrument}-{index}",
    )
    assert candidates[0].id == "custom-AAA-0"


def test_discover_from_universe_covers_every_instrument() -> None:
    out = discover_from_universe(instrument_ids=["AAA", "BBB"])
    assert set(out) == {"AAA", "BBB"}
    assert out["AAA"]


def test_engine_does_not_emit_unbuildable_points() -> None:
    """Una familia cuya plantilla siempre devuelve None no aporta candidatas."""

    def _never(_point):  # type: ignore[no-untyped-def]
        return None

    dead = DiscoveryFamily(
        name="dead_family",
        parent=PARENT_TREND,
        description="no materializa",
        indicator_ids=("sma",),
        param_space={"period": (10,)},
        template=_never,
    )
    assert discover_for_instrument(instrument_id="AAA", families=(dead,)) == ()


def test_catalog_preset_key_equals_declared_preset_key() -> None:
    """H1: la identidad es EXACTA — nunca se fabrica con el nombre de familia.

    Para el catálogo curado, ``presetKey`` está siempre declarado, así que
    ``candidate.preset_key`` debe ser idéntico al ``presetKey`` de la definición
    materializada (no al ``family.name``).
    """
    candidates = discover_for_instrument(instrument_id="AAA")
    assert candidates
    for candidate in candidates:
        assert candidate.params["discovery_family"] == candidate.strategy_family
        assert candidate.preset_key == candidate.params["definition"]["presetKey"]


def test_template_without_preset_key_declares_gap_not_family_name() -> None:
    """Una definición sin ``presetKey`` ⇒ ``None`` (hueco declarado), no el nombre de familia."""

    def _no_preset(_point):  # type: ignore[no-untyped-def]
        return {"indicatorSpecs": [], "entries": {"operator": "all", "rules": []}}

    family = DiscoveryFamily(
        name="custom_no_preset",
        parent=PARENT_TREND,
        description="definición sin presetKey",
        indicator_ids=("sma",),
        param_space={"period": (10,)},
        template=_no_preset,
    )
    candidates = discover_for_instrument(instrument_id="AAA", families=(family,))
    assert len(candidates) == 1
    assert candidates[0].strategy_family == "custom_no_preset"
    # La etiqueta de familia NO se usa como identidad: el hueco viaja declarado.
    assert candidates[0].preset_key is None


def test_template_with_preset_key_preserves_exact_identity() -> None:
    """Una definición con ``presetKey`` conserva la identidad EXACTA declarada."""

    def _with_preset(_point):  # type: ignore[no-untyped-def]
        return {"presetKey": "custom_preset", "indicatorSpecs": []}

    family = DiscoveryFamily(
        name="custom_with_preset",
        parent=PARENT_TREND,
        description="definición con presetKey",
        indicator_ids=("sma",),
        param_space={"period": (10,)},
        template=_with_preset,
    )
    candidates = discover_for_instrument(instrument_id="AAA", families=(family,))
    assert len(candidates) == 1
    assert candidates[0].preset_key == "custom_preset"
