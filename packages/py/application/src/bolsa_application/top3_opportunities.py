"""V2.88 — selector TOP3 de oportunidades (activos) + persistencia auditable.

Recibe los ``OpportunityScore`` rankeados del ``OpportunityBoard`` y selecciona los 3
mejores ACTIVOS a evaluar (``select_top_opportunities``), anotando rank, componentes y
motivos. Las que quedan fuera del TOP se registran con ``TOP_N_EXCLUDED`` (motivo
honesto del no-trade, nunca un ``edge_below_threshold`` falso).

La persistencia se expone como ``Top3OpportunityRecord`` serializable y un ``Protocol``
``Top3OpportunitySink``: el glue de base de datos (tabla nueva o ``scope="asset"`` en
``instrument_strategy_tops``) requiere migración y queda fuera de este módulo (puro).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from bolsa_analytics.cognitive.opportunity_ranker import (
    TOP_N_EXCLUDED,
    OpportunityScore,
    select_top_opportunities,
)
from bolsa_application.opportunity_board import AssetExclusion

__all__ = [
    "HISTORICAL_SCORING_NO_CHAMPION",
    "Top3Opportunity",
    "Top3OpportunityRecord",
    "Top3OpportunitySink",
    "Top3OpportunitySelection",
    "select_top3_assets",
    "select_top3_records",
]

#: V2.88.84 — motivo DECLARADO de un slot del TOP3 cuyo score se calculó SIN evidencia LAB
#: del campeón ACTIVE: el motor cayó al scoring histórico (solo ``edge``+``liquidity``). El
#: activo sigue siendo operable, pero la degradación deja de ser silenciosa: la foto durable
#: lo dice. Sin esta marca, un slot puntuado a ciegas se leería igual que uno con evidencia.
HISTORICAL_SCORING_NO_CHAMPION = "scoring_historico_sin_campeon"


@dataclass(frozen=True, slots=True)
class Top3Opportunity:
    """Un activo del TOP3 con su score y componentes explicables."""

    rank: int
    instrument_id: str
    combined: float
    components: dict[str, float] = field(default_factory=dict)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Top3OpportunityRecord:
    """Registro persistible/auditable de un slot del TOP3 (scope activo)."""

    run_id: str
    rank: int
    instrument_id: str
    combined: float
    components: dict[str, float]
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "rank": self.rank,
            "assetId": self.instrument_id,
            "score": self.combined,
            "components": dict(self.components),
            "reason": self.reason,
        }


class Top3OpportunitySink(Protocol):
    """Sink de persistencia del TOP3 (implementación DB fuera de este módulo)."""

    async def save(self, records: list[Top3OpportunityRecord]) -> None: ...


@dataclass(frozen=True, slots=True)
class Top3OpportunitySelection:
    """Resultado del selector: TOP3 seleccionado + excluidos con motivo real."""

    run_id: str
    selected: tuple[Top3Opportunity, ...] = ()
    top_n_excluded: tuple[Top3Opportunity, ...] = ()
    excluded: tuple[AssetExclusion, ...] = ()

    def to_records(self) -> list[Top3OpportunityRecord]:
        """Serializa el TOP3 a registros auditables (selected + top_n_excluded)."""
        records: list[Top3OpportunityRecord] = []
        for opportunity in self.selected:
            records.append(
                Top3OpportunityRecord(
                    run_id=self.run_id,
                    rank=opportunity.rank,
                    instrument_id=opportunity.instrument_id,
                    combined=opportunity.combined,
                    components=opportunity.components,
                    reason=opportunity.reason,
                )
            )
        return records


def select_top3_assets(
    scores: list[OpportunityScore] | tuple[OpportunityScore, ...],
    *,
    top_n: int = 3,
    run_id: str = "",
    excluded: tuple[AssetExclusion, ...] = (),
) -> Top3OpportunitySelection:
    """Selecciona el TOP N de oportunidades (activos) ya rankeados.

    ``top_n <= 0`` ⇒ vacío (fail-closed, idéntico al contrato del ranker). Los activos
    fuera del TOP se anotan con ``TOP_N_EXCLUDED`` (motivo honesto); los veteados por el
    board (sin evidencia o veto operativo) llegan en ``excluded``.
    """
    if top_n <= 0:
        return Top3OpportunitySelection(run_id=run_id, excluded=excluded)
    top = select_top_opportunities(scores, top_n=top_n)
    selected = tuple(
        Top3Opportunity(
            rank=opportunity.rank or (index + 1),
            instrument_id=opportunity.instrument_id,
            combined=opportunity.combined,
            components=dict(opportunity.components),
        )
        for index, opportunity in enumerate(top)
    )
    selected_ids = {o.instrument_id for o in selected}
    top_n_excluded = tuple(
        Top3Opportunity(
            rank=opportunity.rank or 0,
            instrument_id=opportunity.instrument_id,
            combined=opportunity.combined,
            components=dict(opportunity.components),
            reason=TOP_N_EXCLUDED,
        )
        for opportunity in scores
        if opportunity.instrument_id not in selected_ids
    )
    return Top3OpportunitySelection(
        run_id=run_id,
        selected=selected,
        top_n_excluded=top_n_excluded,
        excluded=excluded,
    )


def _base_symbol(instrument_id: str) -> str:
    """Activo base de una clave de candidata (``SÍMBOLO#versión`` ⇒ ``SÍMBOLO``).

    ``plan_v2_tick`` puede rankear por ``candidate_key`` (con ``allow_distinct_strategies``);
    el TOP3 es de ACTIVOS, así que colapsa a la parte del símbolo.
    """
    return str(instrument_id).split("#", 1)[0]


def select_top3_records(
    scores: Sequence[OpportunityScore],
    *,
    top_n: int = 3,
    run_id: str = "",
    evidenced_symbols: frozenset[str] = frozenset(),
) -> list[Top3OpportunityRecord]:
    """TOP3 serializable que DECLARA, por slot, si el score usó evidencia LAB o histórico.

    Reutiliza :func:`select_top3_assets` (mismo top N, misma semántica de ``TOP_N_EXCLUDED``)
    y añade la procedencia del score: un activo cuyo símbolo base NO figura en
    ``evidenced_symbols`` se puntuó con scoring histórico (no había campeón ACTIVE) y su slot
    lo declara con :data:`HISTORICAL_SCORING_NO_CHAMPION`. Un activo con evidencia lleva
    ``reason=None`` (no se inventa un motivo para lo que sí se midió). La ausencia de
    evidencia, aquí, es un HECHO declarado, no un silencio.
    """
    selection = select_top3_assets(list(scores), top_n=top_n, run_id=run_id)
    records: list[Top3OpportunityRecord] = []
    for opportunity in selection.selected:
        symbol = _base_symbol(opportunity.instrument_id)
        evidenced = symbol in evidenced_symbols
        records.append(
            Top3OpportunityRecord(
                run_id=run_id,
                rank=opportunity.rank,
                instrument_id=symbol,
                combined=opportunity.combined,
                components=dict(opportunity.components),
                reason=None if evidenced else HISTORICAL_SCORING_NO_CHAMPION,
            )
        )
    return records
