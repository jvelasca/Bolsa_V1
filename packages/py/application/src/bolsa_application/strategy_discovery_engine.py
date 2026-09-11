"""V2.31 / A11 — StrategyDiscoveryEngine (P1-01 de la auditoría V2.30).

Convierte el **catálogo curado** de familias (``discovery_catalog``) en
``StrategyCandidate`` reproducibles para el LABORATORIO. Es el eslabón que faltaba:

    ESTUDIO → [DISCOVERY ENGINE] → LAB → TOP3 → COACH → FINALISTA → ACTIVE

Antes de V2.31 el orquestador generaba **una** candidata por instrumento con una
familia fija (``OrchestratorDeps.strategy_family``), así que el AUTO nunca podía
descubrir entre los indicadores disponibles. Este motor emite N candidatas por
instrumento a partir del search space declarado, respetando un **presupuesto global**
(anti-explosión combinatoria: multiple testing / PBO / coste — auditoría §19/P2-03).

Propiedades duras:

* **Determinista**: mismo catálogo + mismo presupuesto ⇒ mismas candidatas, en el
  mismo orden e ids reproducibles.
* **Fail-closed**: una plantilla que no materializa (parámetros incompletos) no
  produce candidata; presupuesto agotado ⇒ se corta; sin familias ⇒ tupla vacía.
* **Sin red / IA / DB**: función pura. El LAB decide después con datos reales.

La candidata lleva en ``params`` dos claves que consume el runner genérico del LAB:

* ``definition``: la ``StrategyDefinitionV1`` ejecutable materializada por la
  plantilla (la que evaluará el motor de reglas declarativo).
* ``discovery_family`` / ``discovery_parent``: trazabilidad (auditoría).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from bolsa_application.discovery_catalog import (
    DISCOVERY_FAMILIES,
    DiscoveryBudget,
    DiscoveryFamily,
    families_by_parent,
)
from bolsa_application.discovery_grammar import (
    GrammarBudget,
    enumerate_grammar_plans,
    grammar_variants_for_plan,
)
from bolsa_domain.entities.strategy_lifecycle import StrategyCandidate

__all__ = [
    "GRAMMAR_FAMILY_PREFIX",
    "DiscoveryEmissionSummary",
    "discover_candidates",
    "discover_for_instrument",
    "discover_for_instrument_with_summary",
    "discover_from_universe",
]

# Firma del generador de ids: ``(instrument_id, index) -> str`` (reproducible).
CandidateIdFactory = Callable[[str, int], str]

# Prefijo de familia de las candidatas gramaticales (A14). El ``presetKey`` del plan
# viaja como ``strategy_family`` para que ``_rules_grid_for`` pueda localizarlo.
GRAMMAR_FAMILY_PREFIX = "grammar:"


@dataclass(frozen=True, slots=True)
class DiscoveryEmissionSummary:
    """V2.35/A15 — resumen determinista de lo EMITIDO por el discovery (solo lectura).

    Observabilidad para gobernar el rollout de la gramática: cuántas candidatas
    aporta el catálogo curado, cuántas la gramática controlada, qué presupuesto se
    consumió y qué cupo se reservó a cada vía. **No** altera ninguna decisión ni
    presupuesto: se calcula a partir de lo ya emitido (el prefijo
    ``GRAMMAR_FAMILY_PREFIX`` distingue la procedencia). Sin IA, sin red, sin DB.
    """

    catalog_candidates: int = 0
    grammar_candidates: int = 0
    total_candidates: int = 0
    trials_used: int = 0
    # Cupo máximo de candidatas del catálogo cuando la gramática está habilitada.
    catalog_cap: int | None = None
    # Techo de emisión de planes gramaticales en este ciclo (sino None).
    grammar_cap: int | None = None
    grammar_enabled: bool = False
    # Warm-up: False si ``bar_count`` no alcanzó ``GrammarBudget.min_bars``.
    bar_count_ok: bool = True


def _default_candidate_id(instrument_id: str, family_name: str, index: int) -> str:
    return f"disc-{instrument_id}-{family_name}-{index}"


def discover_for_instrument_with_summary(
    *,
    instrument_id: str,
    families: Sequence[DiscoveryFamily] | None = None,
    parent: str | None = None,
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_count: int | None = None,
    grammar_budget: GrammarBudget | None = None,
) -> tuple[tuple[StrategyCandidate, ...], DiscoveryEmissionSummary]:
    """V2.35/A15 — como ``discover_for_instrument`` pero devuelve también el resumen.

    El resumen es de **solo lectura**: se calcula sobre las candidatas ya emitidas
    (contando el prefijo ``GRAMMAR_FAMILY_PREFIX``) y sobre el presupuesto efectivo,
    sin alterar el reparto ni la semántica fail-closed. Con ``grammar_budget=None``
    los contadores gramaticales quedan a 0 y la tupla es byte-idéntica a la de A13.
    """
    effective_budget = (budget or DiscoveryBudget()).normalized()
    catalog = tuple(
        families
        if families is not None
        else (families_by_parent(parent) if parent is not None else DISCOVERY_FAMILIES)
    )

    candidates: list[StrategyCandidate] = []
    trials_used = 0

    for family in catalog:
        if len(candidates) >= effective_budget.max_candidates:
            break
        if trials_used >= effective_budget.max_trials_total:
            break
        # Warm-up: si sabemos el nº de barras y no caben los params típicos, se salta.
        if bar_count is not None and bar_count < int(family.min_bars_hint):
            continue
        emitted_for_family = 0
        for point in family.param_points():
            if emitted_for_family >= effective_budget.max_per_family:
                break
            if trials_used >= effective_budget.max_trials_total:
                break
            if len(candidates) >= effective_budget.max_candidates:
                break
            executable = family.template(point)
            if executable is None:
                # Punto no construible (fail-closed): no se inventa una candidata.
                continue
            index = len(candidates)
            cid = (
                candidate_id_factory(instrument_id, index)
                if candidate_id_factory is not None
                else _default_candidate_id(instrument_id, family.name, index)
            )
            candidates.append(
                StrategyCandidate(
                    id=str(cid),
                    instrument_id=instrument_id,
                    strategy_family=family.name,
                    params={
                        "definition": executable,
                        "discovery_family": family.name,
                        "discovery_parent": family.parent,
                        "discovery_params": dict(point),
                    },
                    origin="discovery",
                    data_snapshot_id=data_snapshot_id,
                    preset_key=str(executable.get("presetKey") or family.name),
                )
            )
            emitted_for_family += 1
            trials_used += 1

    # V2.35/A15: cupo reservado al catálogo (observabilidad), solo si hay gramática.
    catalog_cap: int | None = None
    grammar_cap: int | None = None
    grammar_enabled = grammar_budget is not None
    effective_grammar = grammar_budget.normalized() if grammar_budget is not None else None

    # V2.34/A14 — gramática controlada, opt-in, con el MISMO presupuesto global.
    # Se reserva una porción del presupuesto para la gramática (si está habilitada), de
    # modo que el catálogo no la deje sin espacio: sin esta reserva, un catálogo grande
    # (24 candidatas) agotaría ``max_candidates`` y la gramática jamás emitiría.
    if effective_grammar is not None:
        catalog_cap = effective_budget.max_candidates
        reserve = _grammar_reserve(effective_budget, effective_grammar)
        if reserve > 0:
            catalog_cap = max(0, effective_budget.max_candidates - reserve)
        # Recorta las candidatas del catálogo ya emitidas si excedieran el cupo reservado.
        if len(candidates) > catalog_cap:
            overflow = len(candidates) - catalog_cap
            candidates = candidates[:catalog_cap]
            trials_used = max(0, trials_used - overflow)
        candidates, trials_used = _extend_with_grammar(
            candidates=candidates,
            trials_used=trials_used,
            instrument_id=instrument_id,
            effective_budget=effective_budget,
            grammar_budget=effective_grammar,
            data_snapshot_id=data_snapshot_id,
            candidate_id_factory=candidate_id_factory,
            bar_count=bar_count,
        )
        # Techo real de emisión gramatical: mismo cálculo que ``_extend_with_grammar``.
        grammar_cap = min(
            int(effective_grammar.max_per_component_variant),
            int(effective_budget.max_per_family),
        )
        bar_count_ok = bar_count is None or bar_count >= int(effective_grammar.min_bars)
    else:
        bar_count_ok = True

    catalog_candidates = sum(
        1 for c in candidates if not str(c.strategy_family).startswith(GRAMMAR_FAMILY_PREFIX)
    )
    grammar_candidates = len(candidates) - catalog_candidates
    summary = DiscoveryEmissionSummary(
        catalog_candidates=catalog_candidates,
        grammar_candidates=grammar_candidates,
        total_candidates=len(candidates),
        trials_used=trials_used,
        catalog_cap=catalog_cap,
        grammar_cap=grammar_cap,
        grammar_enabled=grammar_enabled,
        bar_count_ok=bar_count_ok,
    )
    return tuple(candidates), summary


def discover_for_instrument(
    *,
    instrument_id: str,
    families: Sequence[DiscoveryFamily] | None = None,
    parent: str | None = None,
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_count: int | None = None,
    grammar_budget: GrammarBudget | None = None,
) -> tuple[StrategyCandidate, ...]:
    """Genera las candidatas de descubrimiento para un instrumento.

    ``families`` permite inyectar un catálogo alternativo (tests); por defecto usa
    ``DISCOVERY_FAMILIES``. ``parent`` filtra por rama (trend/momentum/volatility).
    ``bar_count`` (opcional) descarta familias cuyo ``min_bars_hint`` no quepa en la
    ventana disponible — evita candidatas condenadas a "sin trials" por warm-up.

    El reparto del presupuesto es determinista: se recorre el catálogo en orden y
    cada familia aporta como máximo ``max_per_family`` puntos hasta agotar
    ``max_trials_total`` y ``max_candidates``.

    V2.34/A14: si se pasa ``grammar_budget``, tras las familias del catálogo se
    emiten candidatas de la **gramática controlada** (REGIME + TREND + MOMENTUM +
    TRIGGER + EXIT) consumiendo el MISMO presupuesto global (``budget``). Con
    ``grammar_budget=None`` (default) el comportamiento es byte-idéntico al previo a
    A14 — la gramática es opt-in, nunca rompe el catálogo existente.

    V2.35/A15: delega en ``discover_for_instrument_with_summary`` y descarta el
    resumen de observabilidad (API estable previa, sin cambios de firma).
    """
    candidates, _ = discover_for_instrument_with_summary(
        instrument_id=instrument_id,
        families=families,
        parent=parent,
        budget=budget,
        data_snapshot_id=data_snapshot_id,
        candidate_id_factory=candidate_id_factory,
        bar_count=bar_count,
        grammar_budget=grammar_budget,
    )
    return candidates


def _grammar_reserve(
    effective_budget: DiscoveryBudget, grammar_budget: GrammarBudget
) -> int:
    """Nº de candidatas reservadas a la gramática dentro de ``max_candidates``.

    La reserva es acotada: nunca más de la mitad del presupuesto de candidatas ni más
    que las variantes por bloque permitidas, y siempre deja al menos una candidata al
    catálogo (si el presupuesto lo permite).
    """
    effective_grammar = grammar_budget.normalized()
    half = effective_budget.max_candidates // 2
    reserve = min(effective_grammar.max_per_component_variant, half)
    if reserve < 1:
        reserve = 1
    # Deja sitio al catálogo: si el presupuesto es 1, la reserva no puede comérselo todo.
    return max(0, min(reserve, effective_budget.max_candidates - 1))


def _extend_with_grammar(
    *,
    candidates: list[StrategyCandidate],
    trials_used: int,
    instrument_id: str,
    effective_budget: DiscoveryBudget,
    grammar_budget: GrammarBudget,
    data_snapshot_id: str | None,
    candidate_id_factory: CandidateIdFactory | None,
    bar_count: int | None,
) -> tuple[list[StrategyCandidate], int]:
    """Emite candidatas gramaticales consumiendo el remanente del presupuesto global.

    Determinista: ``enumerate_grammar_plans`` ya devuelve un orden total estable; aquí
    solo se corta por presupuesto y warm-up. Fail-closed: un plan que no materializa
    no emite candidata.
    """
    effective_grammar = grammar_budget.normalized()
    if bar_count is not None and bar_count < int(effective_grammar.min_bars):
        return candidates, trials_used

    # El tope de emisión de la gramática es su propio ``max_per_component_variant``
    # (acota cuántos planes aporta, no cuántos puntos por familia del catálogo), pero
    # nunca puede exceder ``max_per_family`` del presupuesto global: el presupuesto
    # sigue siendo único y compartido.
    grammar_emission_cap = min(
        int(effective_grammar.max_per_component_variant),
        int(effective_budget.max_per_family),
    )

    emitted_for_grammar = 0
    for plan in enumerate_grammar_plans(effective_grammar):
        if len(candidates) >= effective_budget.max_candidates:
            break
        if trials_used >= effective_budget.max_trials_total:
            break
        if emitted_for_grammar >= grammar_emission_cap:
            break
        executable = plan.materialize()
        if executable is None:
            continue
        index = len(candidates)
        cid = (
            candidate_id_factory(instrument_id, index)
            if candidate_id_factory is not None
            else _default_candidate_id(instrument_id, plan.preset_key, index)
        )
        # Grid de variantes hermanas: permite que el LAB re-optimice el plan y que el
        # PBO CSCV tenga columnas que rankear (un plan suelto no produce PBO).
        grammar_variants = grammar_variants_for_plan(
            plan, max_variants=max(2, int(effective_grammar.max_per_component_variant))
        )
        candidates.append(
            StrategyCandidate(
                id=str(cid),
                instrument_id=instrument_id,
                strategy_family=f"{GRAMMAR_FAMILY_PREFIX}{plan.preset_key}",
                params={
                    "definition": executable,
                    "discovery_family": plan.preset_key,
                    "discovery_parent": "grammar",
                    "discovery_params": {"grammar_plan": plan.name},
                    "grammar_variants": grammar_variants,
                },
                origin="discovery",
                data_snapshot_id=data_snapshot_id,
                preset_key=plan.preset_key,
            )
        )
        emitted_for_grammar += 1
        trials_used += 1

    return candidates, trials_used


def discover_candidates(
    *,
    instrument_id: str,
    families: Sequence[DiscoveryFamily] | None = None,
    parent: str | None = None,
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_count: int | None = None,
    grammar_budget: GrammarBudget | None = None,
) -> tuple[StrategyCandidate, ...]:
    """Alias público estable de ``discover_for_instrument`` (nombre del motor)."""
    return discover_for_instrument(
        instrument_id=instrument_id,
        families=families,
        parent=parent,
        budget=budget,
        data_snapshot_id=data_snapshot_id,
        candidate_id_factory=candidate_id_factory,
        bar_count=bar_count,
        grammar_budget=grammar_budget,
    )


def discover_from_universe(
    *,
    instrument_ids: Iterable[str],
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_counts: dict[str, int] | None = None,
    grammar_budget: GrammarBudget | None = None,
) -> dict[str, tuple[StrategyCandidate, ...]]:
    """Descubre candidatas para todo un universo (útil fuera del orquestador).

    El presupuesto se aplica **por instrumento** (el orquestador procesa un
    instrumento por ciclo); ``bar_counts`` permite el filtro de warm-up por símbolo.
    """
    counts = dict(bar_counts or {})
    out: dict[str, tuple[StrategyCandidate, ...]] = {}
    for instrument_id in instrument_ids:
        symbol = str(instrument_id)
        if not symbol:
            continue
        out[symbol] = discover_for_instrument(
            instrument_id=symbol,
            budget=budget,
            data_snapshot_id=data_snapshot_id,
            candidate_id_factory=candidate_id_factory,
            bar_count=counts.get(symbol),
            grammar_budget=grammar_budget,
        )
    return out
