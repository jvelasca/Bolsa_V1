"""R-9.2 — reutilización de idempotency_key con payload distinto.

La semántica de idempotencia exige que un retry con la MISMA key rejuegue la
operación original SOLO si el payload coincide. Si el cliente reenvía la misma
key con campos financieros distintos (p. ej. otro ``amount``/``price``), NO se
rejuega en silencio: se lanza ``IdempotencyKeyReused`` (mapeado a HTTP 409). Sin
base de datos: repos fake en memoria (mismo patrón que los tests de idempotencia
existentes de deposit/withdraw y de trade).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bolsa_application.accounts import DepositCashToAccount, ExecuteTrade, WithdrawCashFromAccount
from bolsa_domain.entities.account import LedgerEntry
from bolsa_domain.entities.portfolio import Portfolio, TradeResult, Transaction
from bolsa_domain.errors import IdempotencyKeyReused


@dataclass
class _FakeAccount:
    id: str = "acc-1"
    currency: str = "EUR"
    settings: object | None = None


@dataclass
class _FakePortfolio:
    id: str = "pf-1"
    legacy_portfolio_id: str = "legacy-1"


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


class _FakePortfolioCashRepo:
    def __init__(self) -> None:
        self._cash = 0.0

    async def add_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        self._cash += amount
        return self._cash

    async def deduct_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        self._cash -= amount
        return self._cash

    async def get_summary(self, legacy_portfolio_id: str) -> _FakeSummary:
        return _FakeSummary(self._cash)

    @property
    def cash(self) -> float:
        return self._cash


class _FakeLedgerRepo:
    """Emula find_cash_movement_by_reference + append_cash_movement."""

    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []
        self._seq = 0

    async def find_cash_movement_by_reference(
        self,
        reference_type: str,
        reference_id: str,
        *,
        account_id: str,
        type: str,
    ) -> LedgerEntry | None:
        for entry in self.entries:
            if (
                entry.account_id == account_id
                and entry.reference_type == reference_type
                and entry.reference_id == reference_id
                and entry.type == type
            ):
                return entry
        return None

    async def append_cash_movement(
        self,
        *,
        account_id: str,
        portfolio_id: str,
        entry_type: str,
        amount: float,
        currency: str,
        balance_after: float,
        reference_id: str,
        reference_type: str = "transfer",
        description: str | None = None,
    ) -> LedgerEntry:
        self._seq += 1
        entry = LedgerEntry(
            id=f"entry-{self._seq}",
            account_id=account_id,
            portfolio_id=portfolio_id,
            type=entry_type,
            amount=amount,
            currency=currency,
            balance_after=balance_after,
            instrument_id=None,
            symbol=None,
            quantity=None,
            price=None,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            executed_at="2026-08-20T08:00:00Z",
        )
        self.entries.append(entry)
        return entry


class _FakePortfolioTradeRepo:
    """Emula execute_trade + find_transaction_by_idempotency (guard de trade)."""

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
        return _FakeSummary(0.0)

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


class _FakeLedgerTradeRepo:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str]] = []

    async def append_trade(self, *, entry_type: str, reference_id: str, **_: object) -> None:
        self.rows.append((entry_type, reference_id))

    async def append_fee(self, *, amount: float, reference_id: str, **_: object) -> None:
        self.rows.append(("fee", reference_id))


# --- Deposit ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_deposit_reused_key_with_different_amount_raises_reused() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioCashRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    await use_case.execute("acc-1", amount=1000.0, idempotency_key="dep-key-1")
    assert portfolio.cash == 1000.0
    assert len(ledger.entries) == 1

    # Misma key, amount distinto → conflicto de idempotencia, NO rejuega.
    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute("acc-1", amount=5.0, idempotency_key="dep-key-1")
    # No se ha movido efectivo ni se ha duplicado la entrada.
    assert portfolio.cash == 1000.0
    assert len(ledger.entries) == 1


@pytest.mark.asyncio
async def test_deposit_reused_key_with_same_amount_still_replays() -> None:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioCashRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    first = await use_case.execute("acc-1", amount=1000.0, idempotency_key="dep-key-1")
    replay = await use_case.execute("acc-1", amount=1000.0, idempotency_key="dep-key-1")
    assert replay.id == first.id == "dep-key-1"
    assert portfolio.cash == 1000.0
    assert len(ledger.entries) == 1


@pytest.mark.asyncio
async def test_deposit_reused_key_with_sub_cent_different_amount_raises_reused() -> None:
    """R-10 F2b: comparación por igualdad exacta normalizada a 6 decimales.

    Antes, la tolerancia de 1 céntimo absorbía una diferencia de 4 milésimas
    (100.004 vs 100.000) y rejugaba en silencio. Ahora esa diferencia sub-céntimo
    hace que el payload sea DISTINTO → conflicto (IdempotencyKeyReused), NO rejuega.
    """
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioCashRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    await use_case.execute("acc-1", amount=100.000, idempotency_key="dep-key-1")
    assert portfolio.cash == 100.000
    assert len(ledger.entries) == 1

    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute("acc-1", amount=100.004, idempotency_key="dep-key-1")
    assert portfolio.cash == 100.000
    assert len(ledger.entries) == 1


@pytest.mark.asyncio
async def test_deposit_reused_key_with_exactly_equal_normalized_amount_still_replays() -> None:
    """R-10 F2b: valores exactamente iguales (100 vs 100.000000) sí rejuegan.

    La normalización a 6 decimales hace que distintos rendereados del mismo valor
    colapsen a igualdad exacta y el replay se conserve correctamente.
    """
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioCashRepo()
    use_case = DepositCashToAccount(_FakeAccountRepo(), portfolio, ledger)

    await use_case.execute("acc-1", amount=100.0, idempotency_key="dep-key-1")
    replay = await use_case.execute("acc-1", amount=100.000000, idempotency_key="dep-key-1")
    assert replay.id == "dep-key-1"
    assert portfolio.cash == 100.0
    assert len(ledger.entries) == 1


# --- Withdraw ---------------------------------------------------------------


async def _fund_and_withdraw(amount: float, key: str) -> tuple[WithdrawCashFromAccount, _FakePortfolioCashRepo, _FakeLedgerRepo]:
    ledger = _FakeLedgerRepo()
    portfolio = _FakePortfolioCashRepo()
    account = _FakeAccountRepo()
    deposit = DepositCashToAccount(account, portfolio, ledger)
    await deposit.execute("acc-1", amount=1000.0, idempotency_key="dep-seed")
    withdraw = WithdrawCashFromAccount(account, portfolio, ledger)
    await withdraw.execute("acc-1", amount=amount, idempotency_key=key)
    return withdraw, portfolio, ledger


@pytest.mark.asyncio
async def test_withdraw_reused_key_with_different_amount_raises_reused() -> None:
    withdraw, portfolio, ledger = await _fund_and_withdraw(300.0, "wd-key-1")
    assert portfolio.cash == 700.0

    # Misma key, amount distinto → conflicto (no re-debita, no falla por saldo).
    with pytest.raises(IdempotencyKeyReused):
        await withdraw.execute("acc-1", amount=200.0, idempotency_key="wd-key-1")
    assert portfolio.cash == 700.0
    assert len(ledger.entries) == 2


@pytest.mark.asyncio
async def test_withdraw_reused_key_with_same_amount_still_replays() -> None:
    withdraw, portfolio, ledger = await _fund_and_withdraw(300.0, "wd-key-1")
    replay = await withdraw.execute("acc-1", amount=300.0, idempotency_key="wd-key-1")
    assert replay.id == "wd-key-1"
    assert replay.kind == "external_withdrawal"
    assert portfolio.cash == 700.0
    assert len(ledger.entries) == 2


# --- Trade ------------------------------------------------------------------


def _build_trade() -> tuple[ExecuteTrade, _FakePortfolioTradeRepo, _FakeLedgerTradeRepo]:
    portfolio = _FakePortfolioTradeRepo()
    ledger = _FakeLedgerTradeRepo()
    use_case = ExecuteTrade(_FakeAccountRepo(), portfolio, ledger)
    return use_case, portfolio, ledger


@pytest.mark.asyncio
async def test_trade_reused_key_with_different_price_raises_reused() -> None:
    use_case, portfolio, ledger = _build_trade()
    kwargs = {"instrument_id": "inst-1", "trade_type": "buy", "account_id": "acc-1"}

    await use_case.execute(quantity=10.0, price=100.0, idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1

    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(quantity=10.0, price=200.0, idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1
    assert len(ledger.rows) == 2  # trade + fee originales, sin duplicar


@pytest.mark.asyncio
async def test_trade_reused_key_with_different_quantity_raises_reused() -> None:
    use_case, portfolio, _ = _build_trade()
    kwargs = {"instrument_id": "inst-1", "trade_type": "buy", "account_id": "acc-1"}

    await use_case.execute(quantity=10.0, price=100.0, idempotency_key="tk-1", **kwargs)
    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(quantity=5.0, price=100.0, idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1


@pytest.mark.asyncio
async def test_trade_reused_key_with_different_type_raises_reused() -> None:
    use_case, portfolio, _ = _build_trade()
    kwargs = {"quantity": 10.0, "price": 100.0, "account_id": "acc-1"}

    await use_case.execute(instrument_id="inst-1", trade_type="buy", idempotency_key="tk-1", **kwargs)
    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(instrument_id="inst-1", trade_type="sell", idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1


@pytest.mark.asyncio
async def test_trade_reused_key_with_sub_cent_different_quantity_raises_reused() -> None:
    """R-10 F2b: cantidad con diferencia sub-céntimo (10.004 vs 10.000) → conflicto.

    Antes la tolerancia de 1 céntimo absorbía la diferencia y rejugaba; ahora el
    payload es distinto → IdempotencyKeyReused, NO rejuega ni duplica.
    """
    use_case, portfolio, ledger = _build_trade()
    kwargs = {"instrument_id": "inst-1", "trade_type": "buy", "account_id": "acc-1"}

    await use_case.execute(quantity=10.000, price=100.0, idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1

    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(quantity=10.004, price=100.0, idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1
    assert len(ledger.rows) == 2  # trade + fee originales, sin duplicar


@pytest.mark.asyncio
async def test_trade_reused_key_with_sub_cent_different_price_raises_reused() -> None:
    """R-10 F2b: precio con diferencia sub-céntimo (50.004 vs 50.000) → conflicto."""
    use_case, portfolio, ledger = _build_trade()
    kwargs = {"instrument_id": "inst-1", "trade_type": "buy", "account_id": "acc-1"}

    await use_case.execute(quantity=10.0, price=50.000, idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1

    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(quantity=10.0, price=50.004, idempotency_key="tk-1", **kwargs)
    assert len(portfolio.executions) == 1
    assert len(ledger.rows) == 2


@pytest.mark.asyncio
async def test_trade_reused_key_with_exactly_equal_normalized_payload_still_replays() -> None:
    """R-10 F2b: quantity/price exactamente iguales tras normalizar a 6 decimales
    (10 vs 10.000000, 100 vs 100.000000) siguen rejugando correctamente."""
    use_case, portfolio, ledger = _build_trade()

    first = await use_case.execute(
        instrument_id="inst-1", trade_type="buy", quantity=10.0, price=100.0,
        account_id="acc-1", idempotency_key="tk-1",
    )
    replay = await use_case.execute(
        instrument_id="inst-1", trade_type="buy", quantity=10.000000, price=100.000000,
        account_id="acc-1", idempotency_key="tk-1",
    )
    assert replay.transaction.id == first.transaction.id
    assert len(portfolio.executions) == 1
    assert len(ledger.rows) == 2


@pytest.mark.asyncio
async def test_trade_reused_key_with_same_payload_still_replays() -> None:
    use_case, portfolio, ledger = _build_trade()

    first = await use_case.execute(
        instrument_id="inst-1", trade_type="buy", quantity=10.0, price=100.0,
        account_id="acc-1", idempotency_key="tk-1",
    )
    replay = await use_case.execute(
        instrument_id="inst-1", trade_type="buy", quantity=10.0, price=100.0,
        account_id="acc-1", idempotency_key="tk-1",
    )
    assert replay.transaction.id == first.transaction.id
    assert len(portfolio.executions) == 1
    assert len(ledger.rows) == 2
