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

from bolsa_application.discovery_catalog import (
    DISCOVERY_FAMILIES,
    DiscoveryBudget,
    DiscoveryFamily,
    families_by_parent,
)
from bolsa_domain.entities.strategy_lifecycle import StrategyCandidate

__all__ = [
    "discover_candidates",
    "discover_for_instrument",
    "discover_from_universe",
]

# Firma del generador de ids: ``(instrument_id, index) -> str`` (reproducible).
CandidateIdFactory = Callable[[str, int], str]


def _default_candidate_id(instrument_id: str, family_name: str, index: int) -> str:
    return f"disc-{instrument_id}-{family_name}-{index}"


def discover_for_instrument(
    *,
    instrument_id: str,
    families: Sequence[DiscoveryFamily] | None = None,
    parent: str | None = None,
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_count: int | None = None,
) -> tuple[StrategyCandidate, ...]:
    """Genera las candidatas de descubrimiento para un instrumento.

    ``families`` permite inyectar un catálogo alternativo (tests); por defecto usa
    ``DISCOVERY_FAMILIES``. ``parent`` filtra por rama (trend/momentum/volatility).
    ``bar_count`` (opcional) descarta familias cuyo ``min_bars_hint`` no quepa en la
    ventana disponible — evita candidatas condenadas a "sin trials" por warm-up.

    El reparto del presupuesto es determinista: se recorre el catálogo en orden y
    cada familia aporta como máximo ``max_per_family`` puntos hasta agotar
    ``max_trials_total`` y ``max_candidates``.
    """
    effective_budget = (budget or DiscoveryBudget()).normalized()
    catalog = tuple(
        families
        if families is not None
        else (families_by_parent(parent) if parent is not None else DISCOVERY_FAMILIES)
    )
    if not catalog:
        return ()

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

    return tuple(candidates)


def discover_candidates(
    *,
    instrument_id: str,
    families: Sequence[DiscoveryFamily] | None = None,
    parent: str | None = None,
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_count: int | None = None,
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
    )


def discover_from_universe(
    *,
    instrument_ids: Iterable[str],
    budget: DiscoveryBudget | None = None,
    data_snapshot_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    bar_counts: dict[str, int] | None = None,
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
        )
    return out
