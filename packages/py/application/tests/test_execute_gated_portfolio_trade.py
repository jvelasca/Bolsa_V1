"""ExecuteGatedPortfolioTrade — HTTP paper trade con check_opening (I1)."""

from __future__ import annotations

from typing import Any, Literal

import pytest

from bolsa_application.execute_gated_portfolio_trade import (
    ExecuteGatedPortfolioTrade,
    OpeningVetoedError,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, TradeResult, Transaction


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.existing: TradeResult | None = None

    async def find_existing_by_idempotency(self, **kwargs: Any) -> TradeResult | None:
        """Peek de replay: por defecto no hay trade previo con esa key."""
        return self.existing

    async def execute(self, **kwargs: Any) -> TradeResult:
        self.calls.append(kwargs)
        side = str(kwargs.get("trade_type", "buy")).lower()
        tx_type: Literal["buy", "sell"] = "sell" if side == "sell" else "buy"
        tx = Transaction(
            id="tx-http",
            type=tx_type,
            instrument_id=kwargs["instrument_id"],
            symbol="SYM",
            quantity=float(kwargs["quantity"]),
            price=float(kwargs["price"]),
            total=float(kwargs["quantity"]) * float(kwargs["price"]),
            executed_at="2026-08-25T00:00:00Z",
        )
        return TradeResult(
            transaction=tx,
            summary=PortfolioSummary(
                portfolio=Portfolio(id="pf", name="p", currency="EUR", cash=0.0),
                positions=[],
                total_market_value=0.0,
                total_cost=0.0,
                total_unrealized_pnl=0.0,
                total_equity=0.0,
            ),
        )


class _AllowSummary:
    async def execute(self, *, account_id: str) -> Any:
        return type("Sum", (), {"total_equity": 10_000.0, "positions": []})()


class _VetoSummary:
    async def execute(self, *, account_id: str) -> Any:
        raise RuntimeError("summary down")


def _uc(*, summary: Any, trade: _FakeExecuteTrade) -> ExecuteGatedPortfolioTrade:
    return ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=summary,
    )


@pytest.mark.asyncio
async def test_gated_http_buy_allows_when_gate_ok() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc(summary=_AllowSummary(), trade=trade)
    result = await uc.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert result.transaction.id == "tx-http"
    assert len(trade.calls) == 1


@pytest.mark.asyncio
async def test_gated_http_buy_risk_veto_no_trade() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc(summary=_VetoSummary(), trade=trade)
    with pytest.raises(OpeningVetoedError, match="risk_veto"):
        await uc.execute(
            instrument_id="inst-1",
            trade_type="buy",
            quantity=2.0,
            price=10.0,
            account_id="acc-1",
            idempotency_key="k" * 16,
        )
    assert trade.calls == []


@pytest.mark.asyncio
async def test_gated_http_sell_skips_opening_gate() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc(summary=_VetoSummary(), trade=trade)
    result = await uc.execute(
        instrument_id="inst-1",
        trade_type="sell",
        quantity=1.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert result.transaction.id == "tx-http"
    assert len(trade.calls) == 1
    assert trade.calls[0]["trade_type"] == "sell"


@pytest.mark.asyncio
async def test_replay_idempotente_no_reevalua_el_gate_de_apertura() -> None:
    """Regresión P2: un replay (misma key + mismo payload) NO debe pasar por el gate.

    Antes, el gate se evaluaba antes de la idempotencia: en un reintento legítimo (mismo
    payload tras un timeout) la posición ya estaba abierta por el primer intento, el gate
    la vetaba y devolvía 403 en lugar de rejugar el resultado (200).
    """
    trade = _FakeExecuteTrade()
    # El trade ya existe (replay) y coincide exactamente con el payload entrante.
    trade.existing = TradeResult(
        transaction=Transaction(
            id="tx-original",
            type="buy",
            instrument_id="inst-1",
            symbol="SYM",
            quantity=2.0,
            price=10.0,
            total=20.0,
            executed_at="2026-08-25T00:00:00Z",
        ),
        summary=PortfolioSummary(
            portfolio=Portfolio(id="pf", name="p", currency="EUR", cash=0.0),
            positions=[],
            total_market_value=0.0,
            total_cost=0.0,
            total_unrealized_pnl=0.0,
            total_equity=0.0,
        ),
    )
    # Un summary que VETA: si el gate se evaluara, esto lanzaría OpeningVetoedError.
    uc = _uc(summary=_VetoSummary(), trade=trade)

    result = await uc.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )

    assert result.transaction.id == "tx-original"
    # No se ejecutó un trade nuevo: es un replay, no una nueva apertura.
    assert trade.calls == []


@pytest.mark.asyncio
async def test_key_reutilizada_con_payload_distinto_da_409_antes_del_gate() -> None:
    """El 409 por key reutilizada tiene prioridad sobre el 403 del gate.

    Si la key existe pero el payload cambió, es un error determinista del cliente: debe
    reportarse como ``IdempotencyKeyReused`` (409), no enmascararse como veto de apertura.
    """
    from bolsa_domain.errors import IdempotencyKeyReused

    trade = _FakeExecuteTrade()
    trade.existing = TradeResult(
        transaction=Transaction(
            id="tx-original",
            type="buy",
            instrument_id="inst-1",
            symbol="SYM",
            quantity=2.0,
            price=10.0,
            total=20.0,
            executed_at="2026-08-25T00:00:00Z",
        ),
        summary=PortfolioSummary(
            portfolio=Portfolio(id="pf", name="p", currency="EUR", cash=0.0),
            positions=[],
            total_market_value=0.0,
            total_cost=0.0,
            total_unrealized_pnl=0.0,
            total_equity=0.0,
        ),
    )
    uc = _uc(summary=_VetoSummary(), trade=trade)

    with pytest.raises(IdempotencyKeyReused):
        await uc.execute(
            instrument_id="inst-1",
            trade_type="buy",
            quantity=2.0,
            price=999.0,  # payload divergente
            account_id="acc-1",
            idempotency_key="k" * 16,
        )
    assert trade.calls == []


@pytest.mark.asyncio
async def test_gated_http_sell_fenced_when_position_open() -> None:
    from bolsa_application.execute_gated_portfolio_trade import ExitVetoedError

    trade = _FakeExecuteTrade()
    # Fila NO manual (SEMI/AUTO): el fence se mantiene.
    exit_store = _ExitStore(
        row={
            "id": "pos-1",
            "status": "OPEN",
            "birth_override_reason": None,
            "trade_plan_id": "tp-1",
            "trade_plan_snapshot": {},
        }
    )

    class _ExitUc:
        def __init__(self):
            self._store = exit_store

        async def get_open(self, account_id: str, instrument_id: str):
            return await exit_store.get_open_for_instrument(account_id, instrument_id)

    uc = ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=_VetoSummary(),
        position_from_exit=_ExitUc(),  # type: ignore[arg-type]
    )
    with pytest.raises(ExitVetoedError, match="position_exit_requires_confirm"):
        await uc.execute(
            instrument_id="inst-1",
            trade_type="sell",
            quantity=1.0,
            price=10.0,
            account_id="acc-1",
            idempotency_key="k" * 16,
        )
    assert trade.calls == []
    assert exit_store.updates == []


def _human_manual_open_row() -> dict[str, Any]:
    """Fila abierta nacida por el canal HTTP manual (H1)."""
    from bolsa_analytics.cognitive.position_state import build_position_state_from_fill

    plan: dict[str, Any] = {
        "decisionId": "manual-tx-open",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "HUMAN_MANUAL",
        "origin": "HUMAN_MANUAL",
        "entry": 10.0,
    }
    pos = build_position_state_from_fill(
        plan,
        fill_price=10.0,
        fill_quantity=2.0,
        filled_at="2026-10-07T15:00:00Z",
        position_id="pos-manual-1",
        override={"reason": "human_manual"},
    )
    assert pos is not None
    return {
        "id": "pos-manual-1",
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "status": "OPEN",
        "trade_plan_id": "manual-tx-open",
        "trade_plan_snapshot": plan,
        "birth_override_reason": "human_manual",
        "position_state": pos.to_dict(),
    }


@pytest.mark.asyncio
async def test_gated_http_sell_allows_when_position_origin_human_manual() -> None:
    """H1 (V2.88.85) — una posición HUMAN_MANUAL sí cierra por HTTP."""
    trade = _FakeExecuteTrade()
    exit_store = _ExitStore(row=_human_manual_open_row())
    uc = ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=_VetoSummary(),
        position_from_exit=PersistPositionFromExit(exit_store),
    )
    result = await uc.execute(
        instrument_id="inst-1",
        trade_type="sell",
        quantity=1.0,
        price=11.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert result.transaction.id == "tx-http"
    assert len(trade.calls) == 1
    assert trade.calls[0]["trade_type"] == "sell"
    # El sync cierra/reduce la PositionState (no se queda abierta sin salida).
    assert len(exit_store.updates) == 1
    assert exit_store.updates[0]["status"] == "PARTIAL"


def test_row_is_human_manual_signals() -> None:
    """H1 (V2.88.85) — las tres señales de origen manual (y el rechazo del resto)."""
    from bolsa_application.execute_gated_portfolio_trade import row_is_human_manual

    assert row_is_human_manual(None) is False
    assert row_is_human_manual({"birth_override_reason": "human_manual"}) is True
    assert row_is_human_manual({"trade_plan_id": "manual-tx-9"}) is True
    assert row_is_human_manual({"trade_plan_snapshot": {"origin": "HUMAN_MANUAL"}}) is True
    # Una posición SEMI/AUTO no se autoriza por accidente.
    assert (
        row_is_human_manual(
            {
                "birth_override_reason": None,
                "trade_plan_id": "tp-1",
                "trade_plan_snapshot": {"origin": "HUMAN_CONFIRM"},
            }
        )
        is False
    )


class _FillStore:
    def __init__(self) -> None:
        self.inserts: list[dict] = []
        self.open_by_instrument: dict[tuple[str, str], dict] = {}

    async def get_by_open_transaction_id(self, open_transaction_id: str):
        return None

    async def get_open_for_instrument(self, account_id: str, instrument_id: str):
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs):
        row = {"id": kwargs.get("position_id") or "pos-new", **kwargs}
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        self.inserts.append(kwargs)
        return row


class _ExitStore:
    def __init__(self, row=None):
        self.row = row
        self.updates = []

    async def get_open_for_instrument(self, account_id: str, instrument_id: str):
        return self.row

    async def update_state(self, *, position_id: str, status: str, position_state: dict):
        self.updates.append({"status": status})
        return self.row


@pytest.mark.asyncio
async def test_gated_http_buy_persists_manual_position() -> None:
    trade = _FakeExecuteTrade()
    fill_store = _FillStore()
    uc = ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=_AllowSummary(),
        position_from_fill=PersistPositionFromFill(fill_store),
        position_from_exit=PersistPositionFromExit(_ExitStore()),
    )
    await uc.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert len(fill_store.inserts) == 1
    assert fill_store.inserts[0]["birth_override_reason"] == "human_manual"
    snap = fill_store.inserts[0]["trade_plan_snapshot"]
    assert snap["status"] == "HUMAN_MANUAL"
    assert snap["origin"] == "HUMAN_MANUAL"
    assert str(snap["decisionId"]).startswith("manual-")


class _FakeOhlcv:
    def __init__(self, last_bar: str) -> None:
        self._last_bar = last_bar

    async def get_latest_bar_date(
        self, instrument_id: str, *, timeframe: object = None
    ) -> str | None:
        return self._last_bar


class _FakeMandatesOpen:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return True, "st-mandate-1"


class _FakeInstrumentDataStatus:
    def __init__(self, warnings: tuple[str, ...]) -> None:
        self._warnings = warnings

    async def execute(self, instrument_id: str, *, timeframe: object = None) -> Any:
        return type("Status", (), {"sanity_warnings": self._warnings})()


def _uc_with_sanity(*, warnings: tuple[str, ...], trade: _FakeExecuteTrade) -> ExecuteGatedPortfolioTrade:
    from datetime import UTC, datetime

    return ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=_AllowSummary(),
        ohlcv=_FakeOhlcv(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        mandates=_FakeMandatesOpen(),  # type: ignore[arg-type]
        instrument_data_status=_FakeInstrumentDataStatus(warnings),
    )


@pytest.mark.asyncio
async def test_gated_http_buy_sanity_split_vetoes() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc_with_sanity(
        warnings=("movimiento 55.00% en 2024-01-01 — revisar split/dividendo",),
        trade=trade,
    )
    with pytest.raises(OpeningVetoedError, match="risk_veto"):
        await uc.execute(
            instrument_id="inst-1",
            trade_type="buy",
            quantity=2.0,
            price=10.0,
            account_id="acc-1",
            idempotency_key="k" * 16,
        )
    assert trade.calls == []


@pytest.mark.asyncio
async def test_gated_http_buy_sanity_gap_only_allows() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc_with_sanity(warnings=("gap de 2 días",), trade=trade)
    result = await uc.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert result.transaction.id == "tx-http"
    assert len(trade.calls) == 1
