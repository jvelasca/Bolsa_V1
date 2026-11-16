"""R3 — la procedencia del TOP-3 se verifica en servidor (auditoría LAB 2026-11-16).

Un TOP que el cliente puede inventar hace irrelevante cualquier gate posterior: si el
slot cita un run que no existe, de otro instrumento o sin P1 medido, el servidor no
guarda un 200 optimista. El nivel de evidencia se DERIVA de los runs, nunca del body.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from bolsa_application.instrument_strategy_tops import (
    TopProvenanceError,
    UpsertInstrumentStrategyTop,
    verify_top_provenance,
)
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    InstrumentStrategyTopRecord,
)


@dataclass
class _Run:
    instrument_id: str
    manifest: dict[str, Any] | None


NET_PASSING = {
    "returnBasis": "net",
    "netReturnPct": 6.0,
    "roundTripCostBps": 32.0,
    "expectancyCurrency": 11.0,
    "excessReturnPct": 2.0,
    "netTradeCount": 45,
}


def _run(metrics: dict[str, Any] | None, instrument_id: str = "AAA") -> _Run:
    outputs: dict[str, Any] = {}
    if metrics is not None:
        outputs["isMetrics"] = metrics
    return _Run(
        instrument_id=instrument_id,
        manifest={"outputs": outputs} if metrics is not None else None,
    )


class _FakeBacktests:
    def __init__(self, runs: dict[str, _Run]) -> None:
        self._runs = runs

    async def get_run(self, run_id: str) -> _Run | None:
        return self._runs.get(run_id)


class _FakeTopRepo:
    def __init__(self) -> None:
        self.saved: dict[str, Any] | None = None

    async def upsert(self, **kwargs: Any) -> InstrumentStrategyTopRecord:
        self.saved = kwargs
        now = datetime.now(UTC)
        return InstrumentStrategyTopRecord(
            id="ist_test",
            instrument_id=kwargs["instrument_id"],
            symbol=kwargs.get("symbol"),
            timeframe=kwargs["timeframe"],
            period_label=kwargs.get("period_label"),
            status=kwargs["status"],
            version=1,
            evidence_level=kwargs["evidence_level"],
            slots=kwargs["slots"],
            coach_headline=kwargs.get("coach_headline"),
            coach_facts=kwargs.get("coach_facts"),
            created_at=now,
            updated_at=now,
        )


def _slot(rank: int, run_id: str | None) -> dict[str, Any]:
    return {"rank": rank, "label": f"E{rank}", "runId": run_id}


@pytest.mark.asyncio
async def test_slot_citing_a_real_run_with_p1_derives_lab_validated() -> None:
    backtests = _FakeBacktests({"run-1": _run(NET_PASSING)})
    provenance = await verify_top_provenance(
        instrument_id="AAA",
        slots=[_slot(1, "run-1")],
        backtests=backtests,
    )
    assert provenance.evidence_level == "lab_validated"
    assert provenance.verified is True


@pytest.mark.asyncio
async def test_client_cannot_declare_lab_validated_without_p1() -> None:
    gross = {"returnBasis": "gross", "netReturnPct": None}
    backtests = _FakeBacktests({"run-gross": _run(gross)})
    repo = _FakeTopRepo()
    with pytest.raises(TopProvenanceError, match="lab_validated"):
        await UpsertInstrumentStrategyTop(repo, backtests=backtests).execute(
            instrument_id="AAA",
            timeframe="1d",
            slots=[_slot(1, "run-gross")],
            evidence_level="lab_validated",
        )
    assert repo.saved is None  # no se guardó un 200 con evidencia inventada


@pytest.mark.asyncio
async def test_client_cannot_upgrade_the_derived_level() -> None:
    """Aunque el cliente diga in_sample_only, el servidor guarda lo que midió."""
    backtests = _FakeBacktests({"run-1": _run(NET_PASSING)})
    repo = _FakeTopRepo()
    row = await UpsertInstrumentStrategyTop(repo, backtests=backtests).execute(
        instrument_id="AAA",
        timeframe="1d",
        slots=[_slot(1, "run-1")],
        evidence_level="in_sample_only",
    )
    assert row.evidence_level == "lab_validated"


@pytest.mark.asyncio
async def test_unknown_run_id_is_rejected() -> None:
    with pytest.raises(TopProvenanceError, match="no existe"):
        await verify_top_provenance(
            instrument_id="AAA",
            slots=[_slot(1, "run-fantasma")],
            backtests=_FakeBacktests({}),
        )


@pytest.mark.asyncio
async def test_run_of_another_instrument_is_rejected() -> None:
    backtests = _FakeBacktests({"run-1": _run(NET_PASSING, instrument_id="BBB")})
    with pytest.raises(TopProvenanceError, match="no pertenece"):
        await verify_top_provenance(
            instrument_id="AAA",
            slots=[_slot(1, "run-1")],
            backtests=backtests,
        )


@pytest.mark.asyncio
async def test_active_requires_net_profit_in_every_slot() -> None:
    backtests = _FakeBacktests(
        {
            "run-1": _run(NET_PASSING),
            "run-2": _run({**NET_PASSING, "netReturnPct": -1.0}),
        }
    )
    repo = _FakeTopRepo()
    with pytest.raises(TopProvenanceError, match="active"):
        await UpsertInstrumentStrategyTop(repo, backtests=backtests).execute(
            instrument_id="AAA",
            timeframe="1d",
            slots=[_slot(1, "run-1"), _slot(2, "run-2")],
            status="active",
            evidence_level="lab_validated",
        )
    assert repo.saved is None


@pytest.mark.asyncio
async def test_semifinal_without_run_ids_stays_in_sample() -> None:
    repo = _FakeTopRepo()
    row = await UpsertInstrumentStrategyTop(repo).execute(
        instrument_id="AAA",
        timeframe="1d",
        slots=[_slot(1, None)],
    )
    assert row.evidence_level == "in_sample_only"
    assert repo.saved is not None


@pytest.mark.asyncio
async def test_without_run_repository_nothing_can_be_lab_validated() -> None:
    """Fail-closed: sin forma de verificar, la afirmación lab no sobrevive."""
    provenance = await verify_top_provenance(
        instrument_id="AAA",
        slots=[_slot(1, "run-1")],
        backtests=None,
    )
    assert provenance.evidence_level == "in_sample_only"
    assert "procedencia_no_verificable" in " ".join(provenance.reasons)
