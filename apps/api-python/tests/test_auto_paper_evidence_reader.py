"""PAPER-2.1 — lector de evidencia durable PAPER, hermético (sin PostgreSQL).

Certifica las reglas de AISLAMIENTO y HONESTIDAD del lector ``read_paper_evidence`` con dobles
de las fuentes durables (store de fills + repositorio del journal), sin tocar base de datos:

1. Un cierre durable SIN cuenta atribuible (``account_id`` nulo/vacío) NO se incorpora al ámbito
   consultado: se declara (``unattributed_settlements_excluded``) y cuenta como contradicción.
2. Un cierre durable de OTRA cuenta tampoco entra (y no se confunde con el anterior).
3. Un fallo de lectura de fills se DECLARA (``fills_not_loaded``); jamás se lee como material
    10|   limpio ni como evidencia favorable.
4. Una ventana truncada por el ``limit`` se declara (``fills_window_truncated``).
5. Un fill sin ``cycle_id`` se cuenta como huérfano; no se atribuye a ninguna operación.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from bolsa_application.auto_operational_monitor import AUTO_CYCLE_SETTLEMENT_EVENT
from bolsa_application.paper_evidence_reader import read_paper_evidence

_ACCOUNT = "acc-paper-1"
_OTHER_ACCOUNT = "acc-paper-2"
_VERSION = "orb-1"


@dataclass(frozen=True, slots=True)
class _Fill:
    execution_id: str
    side: str
    price: Decimal
    quantity: Decimal
    cycle_id: str | None
    reference_mid: Decimal | None = Decimal("100")
    direction: object = None
    strategy_version_id: str | None = _VERSION
    created_at: datetime | None = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
    account_id: str = _ACCOUNT


@dataclass(frozen=True, slots=True)
class _Entry:
    account_id: str | None
    event_type: str
    payload: dict[str, Any]
    decision_id: str = "JNL-x"
    created_at: datetime = field(default_factory=lambda: datetime(2026, 10, 1, tzinfo=UTC))


def _round_trip(cycle: str) -> list[_Fill]:
    return [
        _Fill(f"{cycle}#buy", "buy", Decimal("100"), Decimal("10"), cycle),
        _Fill(f"{cycle}#sell", "sell", Decimal("110"), Decimal("10"), cycle),
    ]


def _settlement(cycle: str, account_id: str | None = _ACCOUNT) -> _Entry:
    return _Entry(
        account_id=account_id,
        event_type=AUTO_CYCLE_SETTLEMENT_EVENT,
        payload={
            "event": AUTO_CYCLE_SETTLEMENT_EVENT,
            "cycleId": cycle,
            "pnl": "100",
            "pnlMeasurement": "COMPLETE",
            "closedQty": "10",
        },
    )


class _FakeStore:
    def __init__(
        self,
        *,
        fills: list[_Fill],
        cycle_ids: list[str],
        counts: dict[str | None, int] | None = None,
        fail: bool = False,
    ) -> None:
        self._fills = fills
        self._cycle_ids = cycle_ids
        self._counts = counts if counts is not None else {_VERSION: len(fills)}
        self._fail = fail

    async def list_recent_cycle_ids(self, account_id: str | None, *, limit: int = 500) -> list[str]:
        if self._fail:
            raise RuntimeError("durable fills unavailable")
        return list(self._cycle_ids[:limit])

    async def list_by_cycle_ids(
        self, account_id: str | None, cycle_ids: list[str], limit: int = 5000
    ) -> list[_Fill]:
        if self._fail:
            raise RuntimeError("durable fills unavailable")
        return list(self._fills[:limit])

    async def count_by_strategy_version(self, *, account_id: str | None = None) -> dict[str | None, int]:
        if self._fail:
            raise RuntimeError("durable fills unavailable")
        return dict(self._counts)


class _FakeRepository:
    def __init__(self, entries: list[_Entry], *, fail: bool = False) -> None:
        self._entries = entries
        self._fail = fail

    async def list_by_decision_ids(self, decision_ids: list[str]) -> list[_Entry]:
        if self._fail:
            raise RuntimeError("durable settlements unavailable")
        return list(self._entries)


def _patch(monkeypatch: pytest.MonkeyPatch, store: _FakeStore, repo: _FakeRepository) -> None:
    monkeypatch.setattr(
        "bolsa_application.sim_durable_store.PostgresSimFillFinanceContextStore",
        lambda session, autocommit=False: store,
    )
    monkeypatch.setattr(
        "bolsa_infrastructure.database.repositories.journal_repository.SqlAlchemyJournalRepository",
        lambda session: repo,
    )


@pytest.mark.asyncio
async def test_a_settlement_without_account_is_excluded_and_declared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle = "cyc-1"
    fills = _round_trip(cycle)
    store = _FakeStore(fills=fills, cycle_ids=[cycle])
    repo = _FakeRepository(
        [_settlement(cycle, account_id=None), _settlement(cycle, account_id=_ACCOUNT)]
    )
    _patch(monkeypatch, store, repo)

    dto = await read_paper_evidence(object(), _ACCOUNT)

    rec = dto["reconciliation"]
    # Solo el cierre CON cuenta entra en el ámbito: el anónimo se declara, no se incorpora.
    assert rec["settlementsTotal"] == 1
    assert "unattributed_settlements_excluded" in dto["notes"]
    assert any(c.startswith("settlement_without_account") for c in dto["contradictions"])
    assert dto["verdict"] == "NO_CONFIRMED"


@pytest.mark.asyncio
async def test_a_settlement_of_another_account_is_not_admitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle = "cyc-2"
    store = _FakeStore(fills=_round_trip(cycle), cycle_ids=[cycle])
    repo = _FakeRepository([_settlement(cycle, account_id=_OTHER_ACCOUNT)])
    _patch(monkeypatch, store, repo)

    dto = await read_paper_evidence(object(), _ACCOUNT)

    rec = dto["reconciliation"]
    assert rec["settlementsTotal"] == 0
    # Un cierre de otra cuenta no es "sin cuenta": no se declara como no atribuido.
    assert "unattributed_settlements_excluded" not in dto["notes"]


@pytest.mark.asyncio
async def test_an_unreadable_fills_source_is_declared_never_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeStore(fills=[], cycle_ids=[], fail=True)
    _patch(monkeypatch, store, _FakeRepository([]))

    dto = await read_paper_evidence(object(), _ACCOUNT)

    rec = dto["reconciliation"]
    assert rec["fillsLoaded"] is False
    assert "fills_not_loaded" in dto["notes"]
    # Sin lectura no hay material limpio: la no-contradicción queda SIN DATO.
    assert "non_contradiction" in dto["unknownCriterionIds"]
    assert dto["fillsTotalForAccount"] is None


@pytest.mark.asyncio
async def test_a_truncated_window_is_declared(monkeypatch: pytest.MonkeyPatch) -> None:
    cycle = "cyc-3"
    store = _FakeStore(fills=_round_trip(cycle), cycle_ids=[cycle])
    _patch(monkeypatch, store, _FakeRepository([]))

    dto = await read_paper_evidence(object(), _ACCOUNT, fill_limit=1)

    assert dto["fillsWindowFull"] is False
    assert "fills_window_truncated" in dto["notes"]


@pytest.mark.asyncio
async def test_a_fill_without_a_cycle_is_counted_as_orphan(monkeypatch: pytest.MonkeyPatch) -> None:
    orphan = _Fill("EX-legacy", "buy", Decimal("100"), Decimal("10"), None)
    store = _FakeStore(fills=[orphan], cycle_ids=[])
    _patch(monkeypatch, store, _FakeRepository([]))

    dto = await read_paper_evidence(object(), _ACCOUNT)

    rec = dto["reconciliation"]
    assert rec["orphanExecutions"] == 1
    assert rec["fillsWithCycle"] == 0
    assert any(c.startswith("fill_without_cycle") for c in dto["contradictions"])


@pytest.mark.asyncio
async def test_an_unreadable_settlements_source_is_declared_never_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo de LECTURA de los cierres se declara; jamás se degrada a evidencia limpia.

    El hueco simétrico del fallo de fills: sin la fuente de cierres, ``closure_reconciliation``,
    ``durable_results`` y ``non_contradiction`` quedan SIN DATO (``UNKNOWN ≠ 0``).
    """
    cycle = "cyc-settlements-fail"
    store = _FakeStore(fills=_round_trip(cycle), cycle_ids=[cycle])
    _patch(monkeypatch, store, _FakeRepository([], fail=True))

    dto = await read_paper_evidence(object(), _ACCOUNT)

    rec = dto["reconciliation"]
    assert rec["fillsLoaded"] is True
    assert rec["settlementsLoaded"] is False
    assert "settlements_not_loaded" in dto["notes"]
    for criterion_id in ("closure_reconciliation", "durable_results", "non_contradiction"):
        assert criterion_id in dto["unknownCriterionIds"]
    assert dto["verdict"] == "NO_CONFIRMED"
