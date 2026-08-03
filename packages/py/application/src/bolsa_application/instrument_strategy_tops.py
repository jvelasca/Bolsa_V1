"""Use cases: TOP-3 estrategias AT por instrumento."""

from __future__ import annotations

from typing import Any

from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    InstrumentStrategyTopRecord,
    SqlAlchemyInstrumentStrategyTopRepository,
)


def assert_lab_validated_slots_have_run_id(
    *,
    evidence_level: str,
    status: str,
    slots: list[dict[str, Any]],
) -> None:
    """Reject lab_validated / active TOP without runId (Camino A Checklist)."""
    if evidence_level != "lab_validated" and status != "active":
        return
    missing: list[Any] = []
    for slot in slots:
        run_id = slot.get("runId") or slot.get("run_id")
        if not (isinstance(run_id, str) and run_id.strip()):
            missing.append(slot.get("rank", slot.get("label", "?")))
    if missing:
        raise ValueError(
            "lab_validated/active TOP requires runId on every slot; "
            f"missing {missing}"
        )


class GetInstrumentStrategyTop:
    """Obtiene Instrument Strategy Top."""
    def __init__(self, repo: SqlAlchemyInstrumentStrategyTopRepository) -> None:
        self._repo = repo

    async def execute(
        self, instrument_id: str, timeframe: str = "1d"
    ) -> InstrumentStrategyTopRecord | None:
        return await self._repo.get(instrument_id, timeframe)


class UpsertInstrumentStrategyTop:
    """Crea o actualiza Instrument Strategy Top."""
    def __init__(self, repo: SqlAlchemyInstrumentStrategyTopRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        slots: list[dict[str, Any]],
        symbol: str | None = None,
        period_label: str | None = None,
        status: str = "semifinal",
        evidence_level: str = "in_sample_only",
        coach_headline: str | None = None,
        coach_facts: dict[str, Any] | None = None,
    ) -> InstrumentStrategyTopRecord:
        assert_lab_validated_slots_have_run_id(
            evidence_level=evidence_level,
            status=status,
            slots=slots,
        )
        return await self._repo.upsert(
            instrument_id=instrument_id,
            timeframe=timeframe,
            slots=slots,
            symbol=symbol,
            period_label=period_label,
            status=status,
            evidence_level=evidence_level,
            coach_headline=coach_headline,
            coach_facts=coach_facts,
        )


class DeleteInstrumentStrategyTop:
    """Elimina Instrument Strategy Top."""
    def __init__(self, repo: SqlAlchemyInstrumentStrategyTopRepository) -> None:
        self._repo = repo

    async def execute(self, instrument_id: str, timeframe: str = "1d") -> bool:
        return await self._repo.delete(instrument_id, timeframe)
