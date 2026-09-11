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
from typing import Any

from bolsa_application.discovery_catalog import (
    DISCOVERY_FAMILIES,
    CatalogLane,
    DiscoveryBudget,
    DiscoveryBudgetAllocator,
    DiscoveryFamily,
    GrammarLane,
    families_by_parent,
)
from bolsa_application.discovery_grammar import (
    GrammarBudget,
    enumerate_grammar_plans,
    grammar_variants_for_plan,
)
from bolsa_application.discovery_param_region import (
    param_region_for_point,
    split_granularity_key,
)
from bolsa_domain.entities.strategy_lifecycle import StrategyCandidate

__all__ = [
    "ADAPTIVE_FAMILY_PREFIX",
    "GRAMMAR_FAMILY_PREFIX",
    "DiscoveryBudgetAllocator",
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

# V2.37 (incremento 2): prefijo de las candidatas emitidas por el carril adaptativo.
# Distingue la procedencia (catálogo / gramática / adaptive) en la observabilidad y en
# el resumen de emisión, sin colisionar con el prefijo gramatical.
ADAPTIVE_FAMILY_PREFIX = "adaptive:"


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
    # V2.36/A16 (P2-03): cupo explícito por carril del allocator (observabilidad
    # aditiva; nunca reemplaza los campos previos). ``None`` con gramática OFF.
    grammar_simple_cap: int | None = None
    grammar_composite_cap: int | None = None
    adaptive_cap: int | None = None
    # Cupo de trials por carril (mismo reparto explícito, solo lectura).
    catalog_trials_cap: int | None = None
    grammar_trials_cap: int | None = None
    # V2.37 (incremento 2): emisión adaptativa real (observabilidad aditiva).
    # ``adaptive_candidates`` cuenta las emitidas por el carril adaptativo; el resto de
    # campos documentan la política aplicada (0/None si el carril no emitió).
    adaptive_candidates: int = 0
    adaptive_policy_hash: str | None = None
    adaptive_exploration_quota: int | None = None
    adaptive_families: int = 0
    # V2.38 (incremento 3): emisión adaptativa granularizada por region de parametros.
    # ``adaptive_region_emissions`` cuenta las candidatas adaptativas cuya cuota provenía
    # de una clave compuesta ``familia|region``; ``adaptive_region_count`` el nº de
    # regiones distintas cubiertas. Aditivo: con el flag OFF ambos quedan a 0.
    adaptive_region_emissions: int = 0
    adaptive_region_count: int = 0


def _default_candidate_id(instrument_id: str, family_name: str, index: int) -> str:
    return f"disc-{instrument_id}-{family_name}-{index}"


def _points_for_region(family: DiscoveryFamily, param_region: str) -> list[dict[str, Any]]:
    """V2.38 (incremento 3): puntos del grid de ``family`` que caen en ``param_region``.

    Fail-closed: región vacía ⇒ grid completo; región desconocida ⇒ lista vacía (no se
    emite nada, no se aproxima a la familia entera). El orden del grid es el determinista
    de ``param_points()``, así que el filtrado conserva la reproducibilidad.
    """
    region = str(param_region or "").strip()
    if not region:
        return list(family.param_points())
    return [
        point
        for point in family.param_points()
        if param_region_for_point(family.param_space, point) == region
    ]


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
    allocator: DiscoveryBudgetAllocator | None = None,
    search_policy: Any = None,
    emit_param_region: bool = True,
) -> tuple[tuple[StrategyCandidate, ...], DiscoveryEmissionSummary]:
    """V2.35/A15 — como ``discover_for_instrument`` pero devuelve también el resumen.

    El resumen es de **solo lectura**: se calcula sobre las candidatas ya emitidas
    (contando el prefijo ``GRAMMAR_FAMILY_PREFIX``) y sobre el presupuesto efectivo,
    sin alterar el reparto ni la semántica fail-closed. Con ``grammar_budget=None``
    los contadores gramaticales quedan a 0 y la tupla es byte-idéntica a la de A13.

    V2.36/A16 (P2-03): el reparto entre catálogo y gramática ya NO es una reserva
    secuencial dependiente del orden, sino el reparto explícito por carriles del
    ``allocator`` (``DiscoveryBudgetAllocator``). Con ``grammar_budget=None`` el
    allocator no interviene: la salida sigue siendo la histórica (A13).

    V2.37 (incremento 2): ``search_policy`` (``SearchPolicy``) habilita la **emisión
    adaptativa real** en el carril ``adaptive``: reparte su cupo entre familias del
    catálogo según el prior de evidencia. Es una dependencia inyectada (el motor sigue
    puro): sin política o con política vacía el carril no emite nada y la salida es la
    de V2.36. Las candidatas adaptativas reutilizan el catálogo curado y llevan el
    prefijo ``ADAPTIVE_FAMILY_PREFIX`` para no confundirse con catálogo ni gramática.

    V2.38.1/P2-01: ``emit_param_region`` inyecta la decisión de rollout del worker sin
    romper la pureza del motor. Con ``False`` las candidatas **no** llevan
    ``discovery_param_region``; la evidencia persistida queda idéntica a la de V2.37
    (sin región) y el colapso del worker es un no-op, garantizando equivalencia real.
    Con ``True`` (default, comportamiento V2.38) la región se etiqueta siempre.
    """
    effective_budget = (budget or DiscoveryBudget()).normalized()
    catalog = tuple(
        families
        if families is not None
        else (families_by_parent(parent) if parent is not None else DISCOVERY_FAMILIES)
    )

    # V2.36/A16: el cupo del catálogo procede del allocator explícito (no del orden).
    # Con gramática OFF (``grammar_budget is None``) el allocator no se consulta y el
    # catálogo puede consumir todo el presupuesto: comportamiento histórico intacto.
    # Con gramática ON y sin allocator inyectado se usa el reparto por defecto, que
    # garantiza cupo a ambos carriles.
    catalog_cap: int | None = None
    if grammar_budget is not None:
        effective_allocator = (allocator or DiscoveryBudgetAllocator()).normalized()
        allocation = effective_allocator.allocate(effective_budget)
        catalog_cap = allocation[CatalogLane.NAME].candidates
    catalog_candidate_budget = effective_budget
    if catalog_cap is not None:
        catalog_candidate_budget = DiscoveryBudget(
            max_trials_total=effective_budget.max_trials_total,
            max_per_family=effective_budget.max_per_family,
            max_candidates=max(0, min(catalog_cap, effective_budget.max_candidates)),
            min_bars=effective_budget.min_bars,
        )

    candidates: list[StrategyCandidate] = []
    trials_used = 0

    for family in catalog:
        if len(candidates) >= catalog_candidate_budget.max_candidates:
            break
        if trials_used >= catalog_candidate_budget.max_trials_total:
            break
        # Warm-up: si sabemos el nº de barras y no caben los params típicos, se salta.
        if bar_count is not None and bar_count < int(family.min_bars_hint):
            continue
        emitted_for_family = 0
        for point in family.param_points():
            if emitted_for_family >= catalog_candidate_budget.max_per_family:
                break
            if trials_used >= catalog_candidate_budget.max_trials_total:
                break
            if len(candidates) >= catalog_candidate_budget.max_candidates:
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
            # V2.38.1/P2-01: la region solo se etiqueta si el rollout lo pide (inyectado).
            # Con ``emit_param_region=False`` el dict de params es byte-identico al de
            # V2.37 (sin la clave), de modo que la evidencia persistida no lleva region.
            catalog_params: dict[str, Any] = {
                "definition": executable,
                "discovery_family": family.name,
                "discovery_parent": family.parent,
                "discovery_params": dict(point),
            }
            if emit_param_region:
                # V2.38 (incremento 3): region determinista del punto en el grid de la
                # familia; se propaga hasta el trial persistido para agregar por region.
                catalog_params["discovery_param_region"] = param_region_for_point(
                    family.param_space, point
                )
            candidates.append(
                StrategyCandidate(
                    id=str(cid),
                    instrument_id=instrument_id,
                    strategy_family=family.name,
                    params=catalog_params,
                    origin="discovery",
                    data_snapshot_id=data_snapshot_id,
                    preset_key=str(executable.get("presetKey") or family.name),
                )
            )
            emitted_for_family += 1
            trials_used += 1

    # V2.35/A15: cupo reservado al catálogo (observabilidad), solo si hay gramática.
    grammar_cap: int | None = None
    grammar_enabled = grammar_budget is not None
    effective_grammar = grammar_budget.normalized() if grammar_budget is not None else None
    grammar_simple_cap: int | None = None
    grammar_composite_cap: int | None = None
    adaptive_cap: int | None = None
    catalog_trials_cap: int | None = None
    grammar_trials_cap: int | None = None

    # V2.34/A14 / V2.36/A16 — gramática controlada, opt-in, con el MISMO presupuesto
    # global. El reparto catálogo/gramática lo fija el allocator explícito: el catálogo
    # ya se cortó a ``catalog_cap`` (pesos), así que la gramática siempre dispone de su
    # cupo aunque el catálogo tenga familias de sobra (bug A14 arreglado por diseño).
    if effective_grammar is not None:
        grammar_simple_cap = allocation[GrammarLane.SIMPLE].candidates
        grammar_composite_cap = allocation[GrammarLane.COMPOSITE].candidates
        adaptive_cap = allocation["adaptive"].candidates
        catalog_trials_cap = allocation[CatalogLane.NAME].trials
        grammar_trials_cap = (
            allocation[GrammarLane.SIMPLE].trials + allocation[GrammarLane.COMPOSITE].trials
        )
        grammar_cap = grammar_simple_cap + grammar_composite_cap
        candidates, trials_used = _extend_with_grammar(
            candidates=candidates,
            trials_used=trials_used,
            instrument_id=instrument_id,
            effective_budget=effective_budget,
            grammar_budget=effective_grammar,
            grammar_cap=grammar_cap,
            data_snapshot_id=data_snapshot_id,
            candidate_id_factory=candidate_id_factory,
            bar_count=bar_count,
        )
        bar_count_ok = bar_count is None or bar_count >= int(effective_grammar.min_bars)
    else:
        bar_count_ok = True

    # V2.37 (incremento 2) — emisión adaptativa real. El carril ``adaptive`` tenía cupo
    # observable pero no emitía nada (V2.36). Con una ``SearchPolicy`` inyectada, su cupo
    # se reparte entre familias del catálogo ponderadas por el prior de evidencia. Es
    # determinista y fail-closed: sin política o con cupo 0 no se emite nada y la salida
    # es la de V2.36. Las candidatas reutilizan el catálogo curado (no se añade espacio
    # de búsqueda nuevo).
    adaptive_candidates_count = 0
    adaptive_policy_hash: str | None = None
    adaptive_exploration_quota: int | None = None
    adaptive_families_count = 0
    # V2.38 (incremento 3): cobertura de regiones en la emisión adaptativa.
    adaptive_region_emissions_count = 0
    adaptive_regions_seen: set[str] = set()
    if (
        adaptive_cap
        and int(adaptive_cap) > 0
        and search_policy is not None
        and not bool(getattr(search_policy, "is_empty", lambda: True)())
    ):
        adaptive_families_count = len(getattr(search_policy, "quotas", ()) or ())
        adaptive_policy_hash = getattr(search_policy, "policy_hash", None)
        adaptive_exploration_quota = int(getattr(search_policy, "exploration_quota", 0) or 0)
        eligible = tuple(catalog)
        by_name = {family.name: family for family in eligible}
        # V2.38 (incremento 3): la clave de la cuota puede ser la **clave compuesta**
        # (``familia`` o ``familia|region``). Se resuelve a familia + region; la region
        # filtra el grid a ese punto concreto (no se añade espacio de búsqueda).
        regions_by_family: dict[str, dict[str, str]] = {}
        quota_map: dict[str, int] = {}
        for quota in getattr(search_policy, "quotas", ()) or ():
            quota_value = int(getattr(quota, "quota", 0))
            if quota_value <= 0:
                continue
            granularity_key = str(getattr(quota, "family", ""))
            family_name, param_region = split_granularity_key(granularity_key)
            if not family_name:
                continue
            quota_map[granularity_key] = quota_value
            if param_region:
                regions_by_family.setdefault(family_name, {})[granularity_key] = param_region
        # Orden canónico por clave: la política ya viene ordenada, pero se reordena aquí
        # para no depender del orden de su tupla (determinismo explícito).
        for granularity_key in sorted(quota_map):
            budget_left = int(adaptive_cap) - adaptive_candidates_count
            if budget_left <= 0:
                break
            family_name, param_region = split_granularity_key(granularity_key)
            adaptive_family = by_name.get(family_name)
            if adaptive_family is None:
                continue
            if bar_count is not None and bar_count < int(adaptive_family.min_bars_hint):
                continue
            points = adaptive_family.param_points()
            if param_region:
                # Fail-closed: región indicada por la evidencia pero no materializable en
                # el grid actual ⇒ no se emite (no se aproxima a la familia entera).
                points = _points_for_region(adaptive_family, param_region)
                if not points:
                    continue
            family_budget = min(quota_map[granularity_key], budget_left)
            emitted_for_family = 0
            for point in points:
                if emitted_for_family >= family_budget:
                    break
                if adaptive_candidates_count >= int(adaptive_cap):
                    break
                if trials_used >= effective_budget.max_trials_total:
                    break
                executable = adaptive_family.template(point)
                if executable is None:
                    continue
                index = len(candidates)
                cid = (
                    candidate_id_factory(instrument_id, index)
                    if candidate_id_factory is not None
                    else _default_candidate_id(instrument_id, adaptive_family.name, index)
                )
                candidates.append(
                    StrategyCandidate(
                        id=str(cid),
                        instrument_id=instrument_id,
                        strategy_family=f"{ADAPTIVE_FAMILY_PREFIX}{adaptive_family.name}",
                        params={
                            "definition": executable,
                            "discovery_family": adaptive_family.name,
                            "discovery_parent": adaptive_family.parent,
                            "discovery_params": dict(point),
                            # V2.38.1/P2-01: la clave se etiqueta solo si el rollout lo
                            # pide; con OFF el dict es byte-identico al de V2.37.
                            **(
                                {
                                    "discovery_param_region": param_region_for_point(
                                        adaptive_family.param_space, point
                                    )
                                }
                                if emit_param_region
                                else {}
                            ),
                            "discovery_lane": "adaptive",
                            "search_policy_hash": adaptive_policy_hash or "",
                        },
                        origin="discovery",
                        data_snapshot_id=data_snapshot_id,
                        preset_key=str(executable.get("presetKey") or adaptive_family.name),
                    )
                )
                emitted_for_family += 1
                adaptive_candidates_count += 1
                if param_region and emit_param_region:
                    adaptive_region_emissions_count += 1
                    adaptive_regions_seen.add(param_region)
                trials_used += 1

    catalog_candidates = sum(
        1
        for c in candidates
        if not str(c.strategy_family).startswith(GRAMMAR_FAMILY_PREFIX)
        and not str(c.strategy_family).startswith(ADAPTIVE_FAMILY_PREFIX)
    )
    grammar_candidates = sum(
        1 for c in candidates if str(c.strategy_family).startswith(GRAMMAR_FAMILY_PREFIX)
    )
    summary = DiscoveryEmissionSummary(
        catalog_candidates=catalog_candidates,
        grammar_candidates=grammar_candidates,
        total_candidates=len(candidates),
        trials_used=trials_used,
        catalog_cap=catalog_cap,
        grammar_cap=grammar_cap,
        grammar_enabled=grammar_enabled,
        bar_count_ok=bar_count_ok,
        grammar_simple_cap=grammar_simple_cap,
        grammar_composite_cap=grammar_composite_cap,
        adaptive_cap=adaptive_cap,
        catalog_trials_cap=catalog_trials_cap,
        grammar_trials_cap=grammar_trials_cap,
        adaptive_candidates=adaptive_candidates_count,
        adaptive_policy_hash=adaptive_policy_hash,
        adaptive_exploration_quota=adaptive_exploration_quota,
        adaptive_families=adaptive_families_count,
        adaptive_region_emissions=adaptive_region_emissions_count,
        adaptive_region_count=len(adaptive_regions_seen),
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
    allocator: DiscoveryBudgetAllocator | None = None,
    search_policy: Any = None,
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

    V2.36/A16 (P2-03): ``allocator`` permite fijar cuotas explícitas por carril
    (catálogo / gramática simple / gramática compuesta / adaptive). Si es ``None`` se
    usa el reparto por defecto de ``DiscoveryBudgetAllocator``. El allocator solo se
    consulta con gramática habilitada; con ``grammar_budget=None`` no interviene.
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
        allocator=allocator,
        search_policy=search_policy,
    )
    return candidates


def _extend_with_grammar(
    *,
    candidates: list[StrategyCandidate],
    trials_used: int,
    instrument_id: str,
    effective_budget: DiscoveryBudget,
    grammar_budget: GrammarBudget,
    grammar_cap: int,
    data_snapshot_id: str | None,
    candidate_id_factory: CandidateIdFactory | None,
    bar_count: int | None,
) -> tuple[list[StrategyCandidate], int]:
    """Emite candidatas gramaticales consumiendo el cupo que fija el allocator.

    Determinista: ``enumerate_grammar_plans`` ya devuelve un orden total estable; aquí
    solo se corta por el ``grammar_cap`` (del allocator explícito, P2-03), por el
    presupuesto global y por warm-up. Fail-closed: un plan que no materializa no emite
    candidata.
    """
    effective_grammar = grammar_budget.normalized()
    if bar_count is not None and bar_count < int(effective_grammar.min_bars):
        return candidates, trials_used

    # El cupo gramatical viene del allocator (suma de carriles simple+compuesto). Se
    # mantiene además el techo histórico ``max_per_component_variant`` como cota de
    # seguridad: la gramática nunca aporta más planes que variantes declaradas.
    grammar_emission_cap = max(
        0,
        min(
            int(grammar_cap),
            int(effective_grammar.max_per_component_variant),
        ),
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
    allocator: DiscoveryBudgetAllocator | None = None,
    search_policy: Any = None,
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
        allocator=allocator,
        search_policy=search_policy,
    )


def discover_from_universe(
    *,
    instrument_ids: Iterable[str],
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_counts: dict[str, int] | None = None,
    grammar_budget: GrammarBudget | None = None,
    allocator: DiscoveryBudgetAllocator | None = None,
    search_policy: Any = None,
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
            allocator=allocator,
            search_policy=search_policy,
        )
    return out
