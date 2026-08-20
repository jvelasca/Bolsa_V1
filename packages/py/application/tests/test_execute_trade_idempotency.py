"""B-4 (L-M6) — idempotencia del write-path de trade+fee (R-7).

Verifica que el guard de idempotencia de ``ExecuteTrade`` (find_transaction_by_idempotency
+ UNIQUE ``transactions(portfolio_id, idempotency_key)``) rejuega el trade original cuando
se pasa la MISMA ``idempotency_key``, en lugar de escribir trade+fee de nuevo. Sin base de
datos: repos fake en memoria (mismo patrón que test_deposit_withdraw_idempotency).

El cierre de B-4 consiste en que los dos caminos internos de producción (ExecutionRouter
AUTO y ConfirmRecommendationIntent) ahora SI derivan una clave lógica estable como
``idempotency_key``, de modo que este guard se activa en ellos (antes se saltaba porque no
pasaban clave). También se verifica aquí el reenvío de esa clave en ConfirmRecommendationIntent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bolsa_application.accounts import ExecuteTrade
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_domain.entities.portfolio import (
    Portfolio,
    TradeResult,
    Transaction,
)


@dataclass
class _FakeAccount:
    id: str = "acc-1"
    currency: str = "EUR"
    settings: object | None = None


@dataclass
class _FakePortfolio:
    id: str = "pf-1"


@dataclass
class _FakeScope:
    account: _FakeAccount = field(default_factory=_FakeAccount)
    portfolio: _FakePortfolio = field(default_factory=_FakePortfolio)
    legacy_portfolio_id: str = "legacy-1"


class _FakeSummary:
    def __init__(self, cash: float) -> None:
        self.portfolio = Portfolio(id="pf-1", name="p", currency="EUR", cash=cash)
        self.positions: list = []
        self.total_market_value = 0.0
        self.total_cost = 0.0
        self.total_unrealized_pnl = 0.0
        self.total_equity = cash


class _FakeAccountRepo:
    def __init__(self) -> None:
        self.scope = _FakeScope()
        self.touched = 0

    async def resolve_scope(self, account_id: str, portfolio_id: str | None = None) -> _FakeScope:
        return self.scope

    async def touch_activity(self, account_id: str) -> None:
        self.touched += 1


class _FakePortfolioRepo:
    """Emula execute_trade + find_transaction_by_idempotency (guard de B-4)."""

    def __init__(self) -> None:
        self.executions: list[Transaction] = []
        self._seq = 0
        self._by_key: dict[str, Transaction] = {}

    async def find_transaction_by_idempotency(
        self,
        legacy_portfolio_id: str,
        idempotency_key: str,
    ) -> Transaction | None:
        return self._by_key.get(idempotency_key)

    async def get_summary(self, legacy_portfolio_id: str) -> _FakeSummary:
        cash = 0.0
        return _FakeSummary(cash)

    async def execute_trade(
        self,
        *,
        instrument_id: str,
        trade_type: str,
        quantity: float,
        price: float,
        legacy_portfolio_id: str,
        fee_amount: float = 0.0,
        idempotency_key: str | None = None,
    ) -> TradeResult:
        self._seq += 1
        total = quantity * price
        tx = Transaction(
            id=f"tx-{self._seq}",
            type=trade_type,  # type: ignore[arg-type]
            instrument_id=instrument_id,
            symbol="SYM",
            quantity=quantity,
            price=price,
            total=total,
            executed_at="2026-08-20T08:00:00Z",
        )
        self.executions.append(tx)
        if idempotency_key is not None:
            self._by_key[idempotency_key] = tx
        return TradeResult(transaction=tx, summary=_FakeSummary(0.0))


class _FakeLedgerRepo:
    """Emula append_trade + append_fee (ambos escriben en la misma lista)."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str]] = []  # (entry_type, reference_id)

    async def append_trade(
        self,
        *,
        entry_type: str,
        reference_id: str,
        **_: object,
    ) -> None:
        self.rows.append((entry_type, reference_id))

    async def append_fee(
        self,
        *,
        amount: float,
        reference_id: str,
        **_: object,
    ) -> None:
        self.rows.append(("fee", reference_id))


def _build() -> tuple[ExecuteTrade, _FakePortfolioRepo, _FakeLedgerRepo]:
    portfolio = _FakePortfolioRepo()
    ledger = _FakeLedgerRepo()
    use_case = ExecuteTrade(_FakeAccountRepo(), portfolio, ledger)
    return use_case, portfolio, ledger


@pytest.mark.asyncio
async def test_same_idempotency_key_replays_trade_without_duplicating() -> None:
    """Doble envío con la misma clave lógica → trade+fee NO se duplican."""
    use_case, portfolio, ledger = _build()

    first = await use_case.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=10.0,
        price=100.0,
        account_id="acc-1",
        idempotency_key="inst-1|2026-08-20|pol-1|entry_long",
    )
    # 1 ejecución + 1 trade + 1 fee (default ES commission > 0).
    assert len(portfolio.executions) == 1
    assert ledger.rows == [("buy", "tx-1"), ("fee", "tx-1")]

    replay = await use_case.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=10.0,
        price=100.0,
        account_id="acc-1",
        idempotency_key="inst-1|2026-08-20|pol-1|entry_long",
    )
    # Guard: rejuega la transacción original, NO duplica trade ni fee.
    assert len(portfolio.executions) == 1
    assert len(ledger.rows) == 2
    assert replay.transaction.id == first.transaction.id


@pytest.mark.asyncio
async def test_distinct_keys_execute_trade_each_time() -> None:
    """Claves distintas (trades legítimos distintos) → se ejecutan ambos (sin falso positivo)."""
    use_case, portfolio, ledger = _build()

    await use_case.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=10.0,
        price=100.0,
        account_id="acc-1",
        idempotency_key="key-A",
    )
    await use_case.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=5.0,
        price=120.0,
        account_id="acc-1",
        idempotency_key="key-B",
    )
    assert len(portfolio.executions) == 2
    assert len(ledger.rows) == 4  # 2 trades + 2 fees


@pytest.mark.asyncio
async def test_without_key_requires_key() -> None:
    """R-10 F1: la idempotency_key de ExecuteTrade es OBLIGATORIA a nivel de firma.

    La antigua "escotilla residual" (omitir clave → ejecutar cada vez) desaparece:
    omitir la clave lanza TypeError porque es un argumento keyword-only requerido."""
    use_case, portfolio, ledger = _build()

    with pytest.raises(TypeError):
        await use_case.execute(
            instrument_id="inst-1", trade_type="buy", quantity=10.0, price=100.0
        )
    with pytest.raises(TypeError):
        await use_case.execute(
            instrument_id="inst-1", trade_type="buy", quantity=10.0, price=100.0
        )
    assert len(portfolio.executions) == 0
    assert len(ledger.rows) == 0


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs: object) -> TradeResult:
        self.calls.append(kwargs)
        tx = Transaction(
            id="tx-1",
            type="buy",  # type: ignore[arg-type]
            instrument_id="inst-1",
            symbol="SYM",
            quantity=1.0,
            price=10.0,
            total=10.0,
            executed_at="2026-08-20T08:00:00Z",
        )
        return TradeResult(transaction=tx, summary=_FakeSummary(0.0))


@pytest.mark.asyncio
async def test_confirm_recommendation_forwards_decision_id_as_idempotency_key() -> None:
    """ConfirmRecommendationIntent deriva la clave lógica (decision_id) al trade."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)

    await use_case.execute(
        recommendation_raw={
            "decisionId": "DEC-123",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 5.0,
            "suggestedPrice": 12.0,
        },
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["idempotency_key"] == "DEC-123"
