"""V2.34 / A14 — tests herméticos de la gramática controlada de Discovery.

Certifica las propiedades duras de la gramática:

* **Vocabulario y materialización**: cada plan produce una ``StrategyDefinitionV1`` que
  el motor declarativo puede ejecutar (specs, entries/exits, signalKind válido).
* **Techo combinatorio**: el número de planes está acotado por ``GrammarBudget`` y un
  test fija el conteo exacto con el presupuesto por defecto (blindaje anti-explosión).
* **Determinismo**: mismas entradas ⇒ mismos planes, mismo orden, mismos nombres.
* **Vetos**: no se repite el mismo indicador con los mismos parámetros en dos bloques.
* **Integración**: con ``grammar_budget=None`` la salida del engine es idéntica a la del
  catálogo; con gramática las candidatas respetan el contrato del Discovery.
"""

from __future__ import annotations

from bolsa_application.discovery_catalog import (
    CatalogLane,
    DiscoveryBudget,
    DiscoveryBudgetAllocator,
    GrammarLane,
)
from bolsa_application.discovery_grammar import (
    COMPONENT_EXIT,
    COMPONENT_MOMENTUM,
    COMPONENT_REGIME,
    COMPONENT_TREND_FILTER,
    COMPONENT_TRIGGER,
    GRAMMAR_COMPONENT_ORDER,
    GRAMMAR_VARIANTS,
    MAX_OPTIONAL_COMPONENTS,
    GrammarBudget,
    GrammarComponent,
    GrammarPlan,
    enumerate_grammar_plans,
)
from bolsa_application.strategy_discovery_engine import (
    GRAMMAR_FAMILY_PREFIX,
    DiscoveryEmissionSummary,
    discover_for_instrument,
    discover_for_instrument_with_summary,
)

_VALID_SIGNAL_KINDS = {"entry_long", "entry_short", "exit"}


# ── Vocabulario ───────────────────────────────────────────────────────────────


def test_grammar_has_the_five_functional_blocks() -> None:
    """El vocabulario cubre REGIME/TREND/MOMENTUM/TRIGGER/EXIT, sin bloques extra."""
    assert set(GRAMMAR_VARIANTS) == {
        COMPONENT_REGIME,
        COMPONENT_TREND_FILTER,
        COMPONENT_MOMENTUM,
        COMPONENT_TRIGGER,
        COMPONENT_EXIT,
    }
    assert GRAMMAR_COMPONENT_ORDER == (
        COMPONENT_REGIME,
        COMPONENT_TREND_FILTER,
        COMPONENT_MOMENTUM,
    )


def test_every_variant_is_well_formed() -> None:
    """Cada variante declara specs y reglas con el signalKind de su bloque."""
    for kind, variants in GRAMMAR_VARIANTS.items():
        assert variants, f"el bloque {kind} no tiene variantes"
        for variant in variants:
            assert isinstance(variant, GrammarComponent)
            assert variant.kind == kind
            assert variant.name
            specs = variant.build_specs()
            rules = variant.build_rules()
            assert specs, f"{variant.name} no declara specs"
            assert rules, f"{variant.name} no declara reglas"
            expected_kind = "exit" if kind == COMPONENT_EXIT else "entry_long"
            for rule in rules:
                assert rule["signalKind"] in _VALID_SIGNAL_KINDS
                assert rule["signalKind"] == expected_kind
                assert rule["type"] in {
                    "indicator_cross",
                    "indicator_compare",
                    "price_vs_indicator",
                    "indicator_vs_indicator",
                }


def _spec_ref(spec: dict) -> tuple[str, tuple[tuple[str, object], ...]]:
    return (
        spec["definitionId"],
        tuple(sorted((spec.get("parameters") or {}).items())),
    )


def test_materialized_plans_are_executable_definitions() -> None:
    """Cada plan materializa una StrategyDefinitionV1 completa y coherente."""
    plans = enumerate_grammar_plans(GrammarBudget(max_per_component_variant=2))
    assert plans
    for plan in plans:
        definition = plan.materialize()
        assert definition is not None, f"{plan.name} no materializa"
        assert definition["presetKey"] == plan.preset_key
        assert definition["indicatorSpecs"]
        assert definition["entries"]["rules"]
        assert definition["exits"]["rules"]
        assert definition["entries"]["operator"] == "all"
        assert definition["exits"]["operator"] == "all"
        for rule in definition["entries"]["rules"]:
            assert rule["signalKind"] == "entry_long"
        for rule in definition["exits"]["rules"]:
            assert rule["signalKind"] == "exit"
        declared = {_spec_ref(spec) for spec in definition["indicatorSpecs"]}
        for rule in definition["entries"]["rules"] + definition["exits"]["rules"]:
            for key in ("leftSpec", "rightSpec", "indicatorSpec"):
                spec = rule.get(key)
                if isinstance(spec, dict):
                    assert _spec_ref(spec) in declared, f"{plan.name} referencia spec ausente"


def test_materialize_deduplicates_indicator_specs() -> None:
    """Un spec compartido por dos bloques aparece una sola vez en ``indicatorSpecs``."""
    trigger = next(
        v for v in GRAMMAR_VARIANTS[COMPONENT_TRIGGER] if v.name == "trigger_ema10_cross_ema50"
    )
    trend = next(
        v for v in GRAMMAR_VARIANTS[COMPONENT_TREND_FILTER] if v.name == "trend_ema10_gt_ema50"
    )
    exit_component = GRAMMAR_VARIANTS[COMPONENT_EXIT][0]
    plan = GrammarPlan(name="dedup_probe", components=(trend, trigger, exit_component))
    definition = plan.materialize()
    assert definition is not None
    keys = [_spec_ref(spec) for spec in definition["indicatorSpecs"]]
    assert len(keys) == len(set(keys)), "indicatorSpecs tiene duplicados"


# ── Techo combinatorio y determinismo ─────────────────────────────────────────


def test_default_budget_yields_a_bounded_exact_plan_count() -> None:
    """Fija el conteo exacto con el presupuesto por defecto (blindaje anti-explosión).

    Si se añade una variante o cambia el techo, este test obliga a revisar el coste de
    multiple testing de forma consciente.
    """
    plans = enumerate_grammar_plans()
    assert len(plans) == 1784
    # Muy por debajo de la explosión del producto completo con los 5 bloques a la vez.
    full_product = 4 * 4 * 4 * 5 * 4
    assert len(plans) < full_product * 100


def test_budget_ceiling_is_enforced() -> None:
    """Menos variantes por bloque ⇒ menos planes; el techo acota por arriba."""
    one_variant = enumerate_grammar_plans(GrammarBudget(max_per_component_variant=1))
    two_variants = enumerate_grammar_plans(GrammarBudget(max_per_component_variant=2))
    assert len(one_variant) <= len(two_variants)
    # 1 variante por bloque × 3 combinaciones de bloques opcionales (1, 2 y 3 bloques),
    # más las variantes de exit extra que no colisionan con el trigger por defecto.
    assert len(one_variant) == 7


def test_max_components_is_capped_at_three() -> None:
    """``normalized`` nunca permite más de 3 componentes opcionales."""
    budget = GrammarBudget(max_components=99).normalized()
    assert budget.max_components == MAX_OPTIONAL_COMPONENTS == 3
    budget0 = GrammarBudget(max_components=0).normalized()
    assert budget0.max_components == 1


def test_multiple_components_never_exceed_optional_ceiling() -> None:
    """Ningún plan arma más de 3 bloques opcionales."""
    for plan in enumerate_grammar_plans(GrammarBudget(max_per_component_variant=1)):
        optional = [c for c in plan.components if c.kind in GRAMMAR_COMPONENT_ORDER]
        assert len(optional) <= MAX_OPTIONAL_COMPONENTS


def test_enumeration_is_deterministic() -> None:
    """Dos enumeraciones idénticas producen el mismo orden y los mismos nombres."""
    first = enumerate_grammar_plans()
    second = enumerate_grammar_plans()
    assert [p.name for p in first] == [p.name for p in second]


def test_plans_are_unique() -> None:
    """No hay dos planes con el mismo nombre (ids de candidata reproducibles)."""
    names = [
        p.name for p in enumerate_grammar_plans(GrammarBudget(max_per_component_variant=2))
    ]
    assert len(names) == len(set(names))


# ── Vetos ─────────────────────────────────────────────────────────────────────


def test_no_plan_repeats_identical_rules_across_blocks() -> None:
    """El veto de redundancia evita reglas idénticas repetidas en dos bloques.

    Compartir specs es legítimo (se deduplican al materializar); repetir la MISMA regla
    no aporta información y se veta.
    """
    for plan in enumerate_grammar_plans(GrammarBudget(max_per_component_variant=2)):
        seen: set[tuple[object, ...]] = set()
        for component in plan.components:
            for rule in component.build_rules():
                key = (
                    rule.get("type"),
                    rule.get("signalKind"),
                    rule.get("direction"),
                    rule.get("operator"),
                    str(rule.get("leftSpec")),
                    str(rule.get("rightSpec")),
                    str(rule.get("indicatorSpec")),
                )
                assert key not in seen, f"{plan.name} repite una regla"
                seen.add(key)


def test_plan_without_required_blocks_does_not_materialize() -> None:
    """Sin EXIT (o sin TRIGGER) el plan no materializa: fail-closed."""
    trigger = GRAMMAR_VARIANTS[COMPONENT_TRIGGER][0]
    only_trigger = GrammarPlan(name="no_exit", components=(trigger,))
    assert only_trigger.materialize() is None

    exit_component = GRAMMAR_VARIANTS[COMPONENT_EXIT][0]
    only_exit = GrammarPlan(name="no_trigger", components=(exit_component,))
    assert only_exit.materialize() is None


# ── Integración con el engine ─────────────────────────────────────────────────


def test_engine_output_is_unchanged_when_grammar_is_disabled() -> None:
    """Con ``grammar_budget=None`` la salida es idéntica al catálogo (cero regresión)."""
    baseline = discover_for_instrument(instrument_id="AAA")
    explicit_none = discover_for_instrument(instrument_id="AAA", grammar_budget=None)
    assert [c.id for c in baseline] == [c.id for c in explicit_none]
    assert [c.strategy_family for c in baseline] == [c.strategy_family for c in explicit_none]


def test_engine_appends_grammar_candidates_after_catalog() -> None:
    """Con gramática ON, el catálogo va primero y la gramática ocupa su cupo explícito.

    V2.36/A16 (P2-03): el reparto ya NO es el remanente del catálogo, sino cuotas
    explícitas del ``DiscoveryBudgetAllocator``. El catálogo conserva su prefijo (se
    corta a su cupo) y la gramática se añade después con el suyo.
    """
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    baseline = discover_for_instrument(instrument_id="AAA", budget=budget)
    with_grammar = discover_for_instrument(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
    )
    # El catálogo conserva el prefijo de su salida, recortado a su cupo por el allocator.
    catalog_part = [
        c for c in with_grammar if not c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX)
    ]
    assert [c.strategy_family for c in catalog_part] == [
        c.strategy_family for c in baseline[: len(catalog_part)]
    ]
    # Catálogo primero, gramática después.
    first_grammar = next(
        i
        for i, c in enumerate(with_grammar)
        if c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX)
    )
    assert all(
        c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX) for c in with_grammar[first_grammar:]
    )
    grammar_candidates = [
        c for c in with_grammar if c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX)
    ]
    assert grammar_candidates, "no se emitieron candidatas gramaticales"
    for candidate in grammar_candidates:
        assert candidate.origin == "discovery"
        assert candidate.preset_key
        definition = candidate.params["definition"]
        assert definition["entries"]["rules"]
        assert definition["exits"]["rules"]
        assert candidate.params["discovery_parent"] == "grammar"


def test_engine_reserves_budget_for_grammar_so_it_is_not_starved() -> None:
    """Un catálogo que agota ``max_candidates`` no puede dejar a la gramática sin sitio."""
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    candidates = discover_for_instrument(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
    )
    grammar_candidates = [
        c for c in candidates if c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX)
    ]
    assert grammar_candidates, "la gramática quedó sin presupuesto"


def test_engine_grammar_reserve_never_consumes_the_whole_budget() -> None:
    """Con un presupuesto mínimo, la reserva deja al menos una candidata al catálogo."""
    budget = DiscoveryBudget(max_trials_total=10, max_per_family=10, max_candidates=2)
    candidates = discover_for_instrument(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
    )
    assert len(candidates) <= budget.max_candidates
    assert any(not c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX) for c in candidates)


def test_engine_grammar_respects_global_candidate_budget() -> None:
    """La gramática nunca excede ``max_candidates``/``max_trials_total`` globales."""
    budget = DiscoveryBudget(max_trials_total=10, max_per_family=10, max_candidates=12)
    candidates = discover_for_instrument(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
    )
    assert len(candidates) <= budget.max_candidates


def test_engine_grammar_is_deterministic() -> None:
    """Dos llamadas con gramática producen los mismos ids, en el mismo orden."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    grammar_budget = GrammarBudget(base=budget)
    first = discover_for_instrument(
        instrument_id="AAA", budget=budget, grammar_budget=grammar_budget
    )
    second = discover_for_instrument(
        instrument_id="AAA", budget=budget, grammar_budget=grammar_budget
    )
    assert [c.id for c in first] == [c.id for c in second]
    assert [c.strategy_family for c in first] == [c.strategy_family for c in second]


def test_engine_grammar_respects_warmup_filter() -> None:
    """Con ``bar_count`` insuficiente, la gramática no emite (fail-closed por warm-up)."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    candidates = discover_for_instrument(
        instrument_id="AAA",
        budget=budget,
        bar_count=10,
        grammar_budget=GrammarBudget(base=budget, min_bars=120),
    )
    assert not [
        c for c in candidates if c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX)
    ]


# ── V2.35/A15: observabilidad (resumen de emisión) ──────────────────────────────


def test_summary_grammar_disabled_reports_zero_grammar_candidates() -> None:
    """Con gramática OFF: contadores gramaticales a 0 y total == catálogo (sin cambio)."""
    candidates, summary = discover_for_instrument_with_summary(instrument_id="AAA")
    assert isinstance(summary, DiscoveryEmissionSummary)
    assert summary.grammar_enabled is False
    assert summary.grammar_candidates == 0
    assert summary.catalog_cap is None
    assert summary.grammar_cap is None
    assert summary.catalog_candidates == summary.total_candidates == len(candidates)


def test_summary_grammar_disabled_is_byte_identical_to_wrapper() -> None:
    """Regresión A13: ``discover_for_instrument`` == el resumen con gramática OFF."""
    candidates, _ = discover_for_instrument_with_summary(instrument_id="AAA")
    assert candidates == discover_for_instrument(instrument_id="AAA")


def test_summary_counts_catalog_and_grammar_and_sums_to_total() -> None:
    """Con gramática ON: la procedencia se cuenta y cuadra con el total emitido."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
    )
    grammar = [
        c for c in candidates if c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX)
    ]
    assert summary.grammar_enabled is True
    assert summary.grammar_candidates == len(grammar) > 0
    assert summary.total_candidates == len(candidates)
    assert summary.catalog_candidates + summary.grammar_candidates == len(candidates)
    assert summary.catalog_cap is not None
    assert summary.grammar_cap is not None


def test_summary_grammar_warmup_flag_is_false_when_bar_count_is_low() -> None:
    """El resumen refleja el warm-up sin inventar candidatas gramaticales."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    _, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        bar_count=10,
        grammar_budget=GrammarBudget(base=budget, min_bars=120),
    )
    assert summary.bar_count_ok is False
    assert summary.grammar_candidates == 0


def test_summary_is_deterministic() -> None:
    """Mismo presupuesto ⇒ mismo resumen (observabilidad reproducible)."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    grammar_budget = GrammarBudget(base=budget)
    _, first = discover_for_instrument_with_summary(
        instrument_id="AAA", budget=budget, grammar_budget=grammar_budget
    )
    _, second = discover_for_instrument_with_summary(
        instrument_id="AAA", budget=budget, grammar_budget=grammar_budget
    )
    assert first == second


# ── V2.36/A16 (P2-03): allocator explícito (cuotas por carril) ──────────────────


def test_allocator_lane_caps_come_from_weights_not_consumption_order() -> None:
    """El cupo del catálogo procede del allocator (pesos), no del orden de consumo."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    allocator = DiscoveryBudgetAllocator(
        catalog_weight=1.0, grammar_simple_weight=1.0, grammar_composite_weight=0.0
    )
    _, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
        allocator=allocator,
    )
    allocation = allocator.allocate(budget)
    assert summary.catalog_cap == allocation[CatalogLane.NAME].candidates
    assert summary.grammar_simple_cap == allocation[GrammarLane.SIMPLE].candidates
    assert summary.grammar_composite_cap == allocation[GrammarLane.COMPOSITE].candidates
    assert summary.adaptive_cap == allocation["adaptive"].candidates


def test_allocator_catalog_never_exceeds_its_cap() -> None:
    """El catálogo no puede emitir más candidatas que su cupo del allocator."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    allocator = DiscoveryBudgetAllocator(
        catalog_weight=1.0, grammar_simple_weight=1.0, grammar_composite_weight=0.0
    )
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
        allocator=allocator,
    )
    assert summary.catalog_cap is not None
    assert summary.catalog_candidates <= summary.catalog_cap
    assert summary.total_candidates <= budget.max_candidates


def test_allocator_grammar_lane_is_guaranteed_a_share() -> None:
    """El cupo de la gramática es > 0 aunque el catálogo tenga familias de sobra (A14)."""
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
    )
    assert summary.grammar_cap is not None and summary.grammar_cap > 0
    assert summary.grammar_candidates > 0
    assert any(c.strategy_family.startswith(GRAMMAR_FAMILY_PREFIX) for c in candidates)


def test_allocator_total_stays_within_global_budget() -> None:
    """Suma de carriles ≤ presupuesto global y total emitido dentro del presupuesto."""
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    allocator = DiscoveryBudgetAllocator()
    allocation = allocator.allocate(budget)
    assert sum(a.candidates for a in allocation.values()) <= budget.max_candidates
    assert sum(a.trials for a in allocation.values()) <= budget.max_trials_total
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
        allocator=allocator,
    )
    assert summary.total_candidates <= budget.max_candidates
    assert summary.trials_used <= budget.max_trials_total


def test_allocator_is_order_independent_no_lane_starves() -> None:
    """Permutar los pesos intercambia cupos sin dejar ningún carril a 0."""
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    base = DiscoveryBudgetAllocator(
        catalog_weight=2.0, grammar_simple_weight=1.0, grammar_composite_weight=1.0
    )
    swapped = DiscoveryBudgetAllocator(
        catalog_weight=1.0, grammar_simple_weight=2.0, grammar_composite_weight=1.0
    )
    base_alloc = base.allocate(budget)
    swapped_alloc = swapped.allocate(budget)
    assert swapped_alloc[CatalogLane.NAME].candidates > 0
    assert swapped_alloc[GrammarLane.SIMPLE].candidates > 0
    assert (
        swapped_alloc[GrammarLane.SIMPLE].candidates
        > base_alloc[GrammarLane.SIMPLE].candidates
    )
    # Y el engine refleja el cupo del catálogo del allocator inyectado, no del orden.
    _, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
        allocator=swapped,
    )
    assert summary.catalog_cap == swapped_alloc[CatalogLane.NAME].candidates


def test_allocator_engine_is_deterministic_across_repeated_runs() -> None:
    """Mismo allocator + presupuesto ⇒ mismas candidatas y mismo resumen, repetible."""
    budget = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    allocator = DiscoveryBudgetAllocator()
    grammar_budget = GrammarBudget(base=budget)
    results = [
        discover_for_instrument_with_summary(
            instrument_id="AAA",
            budget=budget,
            grammar_budget=grammar_budget,
            allocator=allocator,
        )
        for _ in range(3)
    ]
    first_candidates, first_summary = results[0]
    for candidates, summary in results[1:]:
        assert [c.id for c in candidates] == [c.id for c in first_candidates]
        assert summary == first_summary


def test_allocator_grammar_disabled_output_is_unchanged() -> None:
    """Regresión A13: con gramática OFF el allocator no interviene (salida idéntica)."""
    budget = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    baseline = discover_for_instrument(instrument_id="AAA", budget=budget)
    # Un allocator que daría TODO el cupo a la gramática no debe alterar nada con OFF.
    hostile = DiscoveryBudgetAllocator(
        catalog_weight=0.0,
        grammar_simple_weight=100.0,
        grammar_composite_weight=100.0,
    )
    off_with_allocator, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=None,
        allocator=hostile,
    )
    assert [c.id for c in off_with_allocator] == [c.id for c in baseline]
    assert [c.strategy_family for c in off_with_allocator] == [
        c.strategy_family for c in baseline
    ]
    assert summary.grammar_enabled is False
    assert summary.catalog_cap is None
    assert summary.grammar_cap is None
    assert summary.adaptive_cap is None


def test_allocator_small_budget_keeps_catalog_alive() -> None:
    """Con presupuesto mínimo, el catálogo conserva al menos una candidata."""
    budget = DiscoveryBudget(max_trials_total=10, max_per_family=10, max_candidates=2)
    candidates, summary = discover_for_instrument_with_summary(
        instrument_id="AAA",
        budget=budget,
        grammar_budget=GrammarBudget(base=budget),
    )
    assert len(candidates) <= budget.max_candidates
    assert summary.catalog_candidates >= 1

