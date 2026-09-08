"""P2-01 (E2 full V2.14) — drift durable ``live_orders`` → incidente ``live_drift``.

Cubre el writer ``order_live_drift_incident``:

* gate env ``bajo go`` fail-closed (default OFF);
* strict kinds — solo cancel_broker_side / fill_unseen / state_mismatch abren
  incidente; ``query_unavailable`` (bridge que no contestó) NO abre (evita vetos
  falsos de apertura por timeouts);
* un OPEN por cuenta y kind — replay no-op, no duplica ni sobrescribe snapshot;
* dedup OPEN multi-worker en ``PostgresOperationalIncidentStore.put`` (stub de
  sesión, patrón test_dex3): dos workers que ven ``get_active=None`` y putean a la
  vez → el commit del 2º choca (IntegrityError por el partial-unique), tras
  rollback re-consulta y halla el OPEN vencedor → se reconcilia hacia él (sin
  crear un 2º OPEN ni auto-heal).
"""

from __future__ import annotations

from collections import Counter
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from bolsa_analytics.cognitive.operational_incident import open_incident
from bolsa_application.live_order_machine_reconcile import LiveOrderDrift
from bolsa_application.operational_incident_store import (
    InMemoryOperationalIncidentStore,
    PostgresOperationalIncidentStore,
)
from bolsa_application.order_live_drift_incident import (
    LIVE_DRIFT_DURABLE_WRITER_ENV,
    actionable_accounts,
    drift_is_actionable,
    live_drift_durable_writer_enabled,
    publish_order_live_drifts,
)


def _drift(
    *,
    kind: str,
    account_id: str = "acc-1",
    order_id: str = "lo-1",
    venue_order_id: str = "xtb-1",
    machine_state: str = "WORKING",
    broker_state: str | None = "cancelled",
    suggested: str | None = None,
) -> LiveOrderDrift:
    return LiveOrderDrift(
        order_id=order_id,
        account_id=account_id,
        venue_order_id=venue_order_id,
        machine_state=machine_state,
        broker_state=broker_state,
        kind=kind,
        suggested=suggested,
    )


class _Report:
    def __init__(self, *drifts: LiveOrderDrift) -> None:
        self.drifts = list(drifts)

    def summary(self) -> dict[str, object]:
        kinds: Counter[str] = Counter(d.kind for d in self.drifts)
        return {"drifts": len(self.drifts), "kinds": dict(kinds)}


def test_gate_default_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_DRIFT_DURABLE_WRITER_ENV, raising=False)
    assert live_drift_durable_writer_enabled() is False
    for on in ("1", "true", "yes", "on", "ON"):
        monkeypatch.setenv(LIVE_DRIFT_DURABLE_WRITER_ENV, on)
        assert live_drift_durable_writer_enabled() is True


def test_strict_kinds_only_broker_confirmed() -> None:
    for kind in ("cancel_broker_side", "fill_unseen", "state_mismatch"):
        assert drift_is_actionable(_drift(kind=kind)) is True
    # query_unavailable NO es accionable (timeout transitorio del bridge).
    assert drift_is_actionable(_drift(kind="query_unavailable")) is False


def test_actionable_accounts_ignores_unavailable_and_blank_account() -> None:
    report = _Report(
        _drift(kind="query_unavailable", account_id="acc-x"),
        _drift(kind="fill_unseen", account_id="  acc-1  ", order_id="o1"),
    )
    accounts = actionable_accounts(report)
    assert [a.account_id for a in accounts] == ["acc-1"]


@pytest.mark.asyncio
async def test_publish_opens_one_live_drift_per_account() -> None:
    """Drifts accionables → un incidente live_drift por cuenta; unavailable se omite."""
    store = InMemoryOperationalIncidentStore()
    report = _Report(
        _drift(kind="fill_unseen", account_id="acc-1", order_id="o1"),
        _drift(kind="cancel_broker_side", account_id="acc-1", order_id="o2"),
        _drift(kind="state_mismatch", account_id="acc-2", order_id="o3"),
        _drift(kind="query_unavailable", account_id="acc-3", order_id="o4"),
    )
    result = await publish_order_live_drifts(report, holder=store)
    assert result.opened == 2  # acc-1 (o1+o2) + acc-2 (o3)
    assert result.accounts_with_actionable == 2
    assert result.skipped_unavailable == 1

    active_1 = await store.list_active("acc-1")
    assert len(active_1) == 1
    assert active_1[0].kind == "live_drift"
    assert "fill_unseen" in (active_1[0].snapshot or "")
    assert "cancel_broker_side" in (active_1[0].snapshot or "")
    assert await store.list_active("acc-3") == []  # unavailable → sin incidente


@pytest.mark.asyncio
async def test_replay_no_op_when_active_already_open() -> None:
    """Un OPEN por (account, live_drift): el 2º publish no duplica ni reescribe."""
    store = InMemoryOperationalIncidentStore()
    report = _Report(_drift(kind="cancel_broker_side", account_id="acc-1"))
    first = await publish_order_live_drifts(report, holder=store)
    assert first.opened == 1

    opened = await store.list_active("acc-1")
    assert len(opened) == 1
    first_snapshot = opened[0].snapshot

    second = await publish_order_live_drifts(report, holder=store)
    assert second.opened == 0
    assert second.already_active == 1

    after = await store.list_active("acc-1")
    assert len(after) == 1
    assert after[0].snapshot == first_snapshot  # el OPEN no se sobrescribe


def _incident_row_mock(*, incident_id: str, account_id: str, snapshot: str) -> MagicMock:
    row = MagicMock()
    row.id = incident_id
    row.account_id = account_id
    row.kind = "live_drift"
    row.status = "open"
    row.snapshot = snapshot
    row.opened_at = MagicMock()
    row.reviewed_at = None
    row.reviewed_by = None
    row.resolved_at = None
    row.resolved_by = None
    row.resolution_note = None
    row.cleared_at = None
    return row


@pytest.mark.asyncio
async def test_put_dedup_open_two_session_race_keeps_winner() -> None:
    """P2-2 determinista (stub PG): dos writers → el perdedor NO crea un 2º OPEN.

    Worker A commitea el OPEN; worker B (que también vio get_active=None) hace su
    put y choca en commit con IntegrityError por el partial-unique (account,kind)
    activo. Tras rollback, put re-consulta get_active y halla el OPEN vencedor de
    A → se reconcilia devolviendo sin crear fila ni auto-heal.
    """
    session = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    # Orden de execute en el put de B:
    #   1) select por id del incident de B   → sin fila (None) → add + commit
    #   2) commit lanza IntegrityError  → rollback → get_active
    #   3) select get_active(account,kind)   → devuelve el OPEN vencedor de A
    first_lookup = MagicMock()
    first_lookup.scalar_one_or_none.return_value = None  # no existe por id aún
    winner_lookup = MagicMock()
    winner_lookup.scalar_one_or_none.return_value = _incident_row_mock(
        incident_id="inc-race-winner",
        account_id="acc-race",
        snapshot="opened by worker A",
    )
    session.execute = AsyncMock(side_effect=[first_lookup, winner_lookup])
    session.commit = AsyncMock(
        side_effect=IntegrityError("stmt", {}, Exception("partial_unique_open"))
    )

    store = PostgresOperationalIncidentStore(session)  # type: ignore[arg-type]
    loser = open_incident(
        incident_id="inc-race-loser",
        account_id="acc-race",
        kind="live_drift",
        snapshot="opened by worker B",
    )

    # put de B no re-lanza (hay OPEN competidor) → OPEN deduplicado.
    await store.put(loser)

    session.rollback.assert_awaited_once()
    # tras el conflicto se re-consultó get_active (re-consulta del vencedor).
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_put_integrity_error_no_winner_reraises() -> None:
    """IntegrityError real (sin OPEN competidor) → rollback + re-raise (no silencia)."""
    session = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    first_lookup = MagicMock()
    first_lookup.scalar_one_or_none.return_value = None
    no_winner = MagicMock()
    no_winner.scalar_one_or_none.return_value = None  # tras rollback: sin activo
    session.execute = AsyncMock(side_effect=[first_lookup, no_winner])
    session.commit = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("dup_pk")))

    store = PostgresOperationalIncidentStore(session)  # type: ignore[arg-type]
    inc = open_incident(
        incident_id="inc-pk-collision",
        account_id="acc-1",
        kind="live_drift",
        snapshot="x",
    )
    with pytest.raises(IntegrityError):
        await store.put(inc)
    session.rollback.assert_awaited()
