"""``RunEstudioDailyOps`` — universo, hints server-side, opiniones y propuestas dry-run.

Cubre los criterios falsables del plan:

* ``N`` valores ESTUDIO ⇒ ``N`` partes y los contadores suman ``N``;
* universo ``empty``/``unavailable`` ⇒ cero opiniones y estado declarado;
* un fallo de UN valor no aborta el batch (``error`` por valor, con motivo);
* los hints salen de servidor (chips + posiciones) y ``has_eod_bar`` NO se hardcodea;
* ``propose`` reutiliza las opiniones ``eod_batch`` (``opinionSource``), en dry-run;
* solo se publican niveles del ``TradePlan``; un hueco viaja ``None``, nunca ``0``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pytest

from bolsa_application.estudio_daily_ops import (
    STATUS_ERROR,
    STATUS_NO_PLAN,
    STATUS_NO_SIGNAL,
    STATUS_OK,
    RunEstudioDailyOps,
)

_DAY = "2026-10-18"


@dataclass(frozen=True)
class _Universe:
    instrument_ids: list[str]


@dataclass(frozen=True)
class _Opinion:
    instrument_id: str
    stance: str
    dictamen_stars: int
    as_of_bar_date: date = date(2026, 10, 18)
    reasons: tuple[str, ...] = ()
    gate_status: str | None = "PASS"
    top_id: str | None = "top-1"
    top_version: int | None = 3
    engine_version: str = "opinion_v1"
    computed_at: datetime = datetime(2026, 10, 18, 20, 0)

    @property
    def reasons_list(self) -> list[str]:
        return list(self.reasons)


class _FakeEstudioList:
    def __init__(self, ids: list[str] | None) -> None:
        self._ids = ids

    async def execute(self, list_id: str) -> Any:
        if self._ids is None:
            raise RuntimeError("lista ilegible")
        return _Universe(instrument_ids=list(self._ids))


class _FakeOpinions:
    def __init__(self, rows: dict[str, _Opinion], broken: set[str] | None = None) -> None:
        self._rows = rows
        self._broken = broken or set()
        self.calls: list[list[str]] = []
        self.hints_seen: list[Any] = []

    async def run_eod_batch(
        self,
        *,
        instrument_ids: list[str],
        as_of_bar_date: date | None = None,
        account_id: str | None = None,
        force: bool = True,
        hints: list[Any] | None = None,
    ) -> list[Any]:
        if any(iid in self._broken for iid in instrument_ids):
            raise RuntimeError("fallo del batch")
        self.calls.append(list(instrument_ids))
        self.hints_seen.extend(hints or [])
        return [self._rows[iid] for iid in instrument_ids if iid in self._rows]


class _FakePropose:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self._result = result or {"hits": [], "skipped": []}
        self.payloads: list[dict[str, Any]] = []

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        return self._result


class _FakeComposite:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 40,
        horizon: str = "swing",
        regime: str = "neutral",
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(list(instrument_ids))
        return [
            {
                "instrumentId": iid,
                "ticker": f"T{iid.upper()}",
                "indiceOperativo": 72.0,
                "technicalDisplay100": 61.0,
                "confidence": "HIGH",
                "regime": "neutral",
            }
            for iid in instrument_ids
        ]


class _FakeFundamentals:
    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 80,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {"instrumentId": iid, "scoreDisplay100": 55.0, "distress": False}
            for iid in instrument_ids
        ]


class _FakePositions:
    def __init__(self, open_ids: list[str]) -> None:
        self._open = open_ids

    async def list_open_for_account(self, account_id: str) -> list[Any]:
        return [_Position(iid) for iid in self._open]


@dataclass(frozen=True)
class _Position:
    instrument_id: str


def _hit(iid: str) -> dict[str, Any]:
    return {
        "instrumentId": iid,
        "symbol": f"T{iid.upper()}",
        "planId": "plan-1",
        "tradePlan": {
            "status": "TRIGGERED",
            "direction": "long",
            # ``target2`` no existe: debe viajar None, jamás 0.
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 110.0,
            "target2": None,
            "riskAmount": 250.0,
            "expectedRR": 2.0,
            "whyNot": [],
        },
        "signal": {
            "presetKey": "estudio_auto",
            "strategyDefinitionId": None,
            "strategyVersion": 1,
        },
    }


def _skipped(iid: str) -> dict[str, Any]:
    return {
        "instrumentId": iid,
        "reason": "no_tradeplan",
        "tradePlanStatus": "NO_TRADE",
        "whyNot": ["gap_risk"],
        "tradePlan": {
            "status": "NO_TRADE",
            "entry": None,
            "structuralStop": None,
            "whyNot": ["gap_risk"],
        },
    }


def _service(
    *,
    ids: list[str] | None,
    rows: dict[str, _Opinion],
    propose: _FakePropose,
    broken: set[str] | None = None,
) -> tuple[RunEstudioDailyOps, _FakeOpinions]:
    opinions = _FakeOpinions(rows, broken)
    service = RunEstudioDailyOps(
        _FakeEstudioList(ids),
        opinions,
        propose,
        composite=_FakeComposite(),
        fundamentals=_FakeFundamentals(),
        positions=_FakePositions(["inst-noplan"]),
    )
    return service, opinions


@pytest.mark.asyncio
async def test_every_estudio_value_gets_a_part_and_counts_sum_to_the_universe() -> None:
    rows = {
        "inst-ok": _Opinion("inst-ok", "buy", 4),
        "inst-noplan": _Opinion("inst-noplan", "buy", 3),
        "inst-hold": _Opinion("inst-hold", "hold_watch", 2),
    }
    propose = _FakePropose(
        {"hits": [_hit("inst-ok")], "skipped": [_skipped("inst-noplan")]}
    )
    service, opinions = _service(ids=list(rows), rows=rows, propose=propose)

    report = await service.execute(account_id="acc-1", as_of=_DAY)
    payload = report.to_dict()

    assert payload["status"] == "ok"
    assert payload["scannedCount"] == 3
    assert payload["counts"] == {"ok": 1, "no_signal": 1, "no_plan": 1, "error": 0}
    assert payload["countsConsistent"] is True
    by_id = {value["instrumentId"]: value for value in payload["values"]}

    assert by_id["inst-ok"]["status"] == STATUS_OK
    assert by_id["inst-ok"]["plan"]["entry"] == 100.0
    assert by_id["inst-ok"]["plan"]["structuralStop"] == 95.0
    assert by_id["inst-ok"]["plan"]["target2"] is None
    assert by_id["inst-ok"]["strategy"]["presetKey"] == "estudio_auto"

    assert by_id["inst-noplan"]["status"] == STATUS_NO_PLAN
    assert by_id["inst-noplan"]["reason"] == "no_tradeplan"
    assert by_id["inst-noplan"]["whyNot"] == ["gap_risk"]

    assert by_id["inst-hold"]["status"] == STATUS_NO_SIGNAL
    assert by_id["inst-hold"]["reason"].startswith("stance:")

    # ``propose`` corre en dry-run y reutiliza las opiniones ``eod_batch``.
    assert propose.payloads and propose.payloads[0]["execute"] is False
    assert propose.payloads[0]["opinionSource"] == "eod_batch"
    assert propose.payloads[0]["hints"]
    # El batch de opiniones recibió hints de servidor con ``has_eod_bar`` declarado None.
    assert opinions.hints_seen
    assert {hint.has_eod_bar for hint in opinions.hints_seen} == {None}
    assert any(hint.position_open for hint in opinions.hints_seen)


@pytest.mark.asyncio
async def test_empty_and_unavailable_universe_write_no_opinions() -> None:
    for ids, expected in (([], "empty"), (None, "unavailable")):
        propose = _FakePropose()
        service, opinions = _service(ids=ids, rows={}, propose=propose)

        report = await service.execute(account_id="acc-1", as_of=_DAY)

        assert report.status == expected
        assert report.values == []
        assert opinions.calls == []
        assert propose.payloads == []
        assert report.notes


@pytest.mark.asyncio
async def test_a_broken_value_is_isolated_and_the_batch_continues() -> None:
    ids = [f"inst-{index}" for index in range(12)]
    rows = {iid: _Opinion(iid, "hold_watch", 1) for iid in ids}
    propose = _FakePropose()
    service, _ = _service(ids=ids, rows=rows, propose=propose, broken={"inst-3"})

    report = await service.execute(account_id="acc-1", as_of=_DAY)

    payload = report.to_dict()
    by_id = {value["instrumentId"]: value for value in payload["values"]}
    assert by_id["inst-3"]["status"] == STATUS_ERROR
    assert by_id["inst-3"]["reason"].startswith("opinion_error:")
    assert by_id["inst-4"]["status"] == STATUS_NO_SIGNAL
    assert payload["counts"]["error"] == 1
    assert sum(payload["counts"].values()) == payload["scannedCount"] == 12


@pytest.mark.asyncio
async def test_propose_failure_marks_only_buy_values_as_error_and_never_as_ok() -> None:
    rows = {
        "inst-buy": _Opinion("inst-buy", "buy", 4),
        "inst-hold": _Opinion("inst-hold", "hold_watch", 1),
    }

    class _ExplodingPropose:
        async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("propose caído")

    service = RunEstudioDailyOps(
        _FakeEstudioList(list(rows)),
        _FakeOpinions(rows),
        _ExplodingPropose(),
        composite=_FakeComposite(),
        fundamentals=_FakeFundamentals(),
    )
    report = await service.execute(account_id="acc-1", as_of=_DAY)
    by_id = {value.instrument_id: value for value in report.values}

    assert by_id["inst-buy"].status == STATUS_ERROR
    assert by_id["inst-buy"].reason.startswith("propose_error:")
    assert by_id["inst-hold"].status == STATUS_NO_SIGNAL
    assert any("propose no disponible" in note for note in report.notes)
