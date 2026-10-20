"""Contrato del DTO ``GET /top3-opportunities`` (V2.88.153 — identidad aditiva).

La foto cross-asset sella desde la migración 057 el preset/versión del candidato ganador.
El DTO los publica TAL CUAL: una fila histórica sin identidad viaja ``null`` (hueco
declarado) y **nunca** se rellena con el activo, el rank ni la estrategia ejecutada.
"""

from __future__ import annotations

from datetime import UTC, datetime

from bolsa_api.api.v1.routes.top3_opportunities import _to_dto
from bolsa_infrastructure.database.repositories.top3_opportunity_repository import (
    Top3OpportunityRowRecord,
)


def _row(**overrides: object) -> Top3OpportunityRowRecord:
    base: dict[str, object] = {
        "id": "top3_x",
        "run_id": "top3-acc-bar",
        "rank": 1,
        "asset_id": "AAA",
        "combined": 0.87,
        "components": {"edge": 0.9},
        "regime": "trend_up",
        "reasons": ["scoring_historico_sin_campeon"],
        "created_at": datetime(2026, 10, 7, tzinfo=UTC),
        "strategy_preset_key": "momentum_breakout",
        "strategy_version": "2026.10.1",
    }
    base.update(overrides)
    return Top3OpportunityRowRecord(**base)  # type: ignore[arg-type]


def test_dto_publishes_declared_identity() -> None:
    dto = _to_dto(_row())
    assert dto.strategyPresetKey == "momentum_breakout"
    assert dto.strategyVersion == "2026.10.1"
    # El resto del contrato permanece intacto (cambio ADITIVO).
    assert dto.assetId == "AAA"
    assert dto.score == 0.87
    assert dto.reasons == ["scoring_historico_sin_campeon"]


def test_dto_declares_the_gap_as_null_and_never_infers() -> None:
    dto = _to_dto(_row(strategy_preset_key=None, strategy_version=None))
    assert dto.strategyPresetKey is None
    assert dto.strategyVersion is None
    # La ausencia no contamina el resto del slot: el activo y el score siguen publicados.
    assert dto.assetId == "AAA"
    assert dto.score == 0.87


def test_dto_keeps_a_partial_identity_as_declared() -> None:
    dto = _to_dto(_row(strategy_preset_key="trend_follow", strategy_version=None))
    assert dto.strategyPresetKey == "trend_follow"
    assert dto.strategyVersion is None
