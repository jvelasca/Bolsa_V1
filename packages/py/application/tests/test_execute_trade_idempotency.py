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

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from bolsa_application.accounts import ExecuteTrade
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord
from bolsa_domain.entities.investor_profile import InvestorProfileRecord
from bolsa_domain.entities.portfolio import (
    Portfolio,
    TradeResult,
    Transaction,
)


def _triggered_trade_plan(
    *,
    decision_id: str,
    instrument_id: str,
    quantity: float,
    entry: float = 100.0,
    stop: float | None = None,
    risk_amount: float = 500.0,
) -> dict[str, Any]:
    """OI-2 — apertura SEMI exige TRIGGERED + quantity para risk_signature."""
    effective_stop = stop if stop is not None else max(0.01, entry * 0.95)
    return {
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "direction": "long",
        "status": "TRIGGERED",
        "quantity": quantity,
        "entry": entry,
        "structuralStop": effective_stop,
        "riskAmount": risk_amount,
    }


def _opening_recommendation(
    *,
    decision_id: str,
    instrument_id: str,
    quantity: float,
    price: float,
    plan_quantity: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    pq = plan_quantity if plan_quantity is not None else max(quantity, 10.0)
    return {
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "action": "recommend_long",
        "suggestedQuantity": quantity,
        "suggestedPrice": price,
        "tradePlan": _triggered_trade_plan(
            decision_id=decision_id,
            instrument_id=instrument_id,
            quantity=pq,
            entry=price,
            stop=max(0.01, price * 0.9),
            risk_amount=max(500.0, pq * max(abs(price - max(0.01, price * 0.9)), 1.0) * 2),
        ),
        **extra,
    }


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
        self.trade_balance: float | None = None
        self.fee_balance: float | None = None
        self.trade_amount: float | None = None
        self.fee_amount: float | None = None

    async def append_trade(
        self,
        *,
        entry_type: str,
        reference_id: str,
        amount: float | None = None,
        balance_after: float | None = None,
        **_: object,
    ) -> None:
        self.rows.append((entry_type, reference_id))
        if amount is not None:
            self.trade_amount = amount
        if balance_after is not None:
            self.trade_balance = balance_after

    async def append_fee(
        self,
        *,
        amount: float,
        reference_id: str,
        balance_after: float | None = None,
        **_: object,
    ) -> None:
        self.rows.append(("fee", reference_id))
        self.fee_amount = amount
        if balance_after is not None:
            self.fee_balance = balance_after


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


class _CashAwarePortfolioRepo:
    """Repo fake con semántica de cash real para verificar la aritmética Decimal.

    ``execute_trade`` aplica notional±fees y el summary POST-lock refleja el cash
    final (EXEC-B-CONC). ``get_summary`` solo se usa en caminos de replay.
    Comprueba que ``ExecuteTrade`` escribe ``balance_after`` secuenciales exactos
    (R-11 C3 / R-10 F3) derivados del summary, no de una lectura pre-lock.
    """

    def __init__(self, cash: float) -> None:
        self._cash = cash
        self._by_key: dict[str, Transaction] = {}
        self.get_summary_calls = 0

    async def find_transaction_by_idempotency(
        self, legacy_portfolio_id: str, idempotency_key: str
    ) -> Transaction | None:
        return self._by_key.get(idempotency_key)

    async def get_summary(self, legacy_portfolio_id: str) -> _FakeSummary:
        self.get_summary_calls += 1
        return _FakeSummary(self._cash)

    async def execute_trade(
        self,
        *,
        instrument_id: str,
        trade_type: str,
        quantity: float,
        price: float,
        legacy_portfolio_id: str,
        fee_amount: float = 0.0,
        idempotency_key: str,
    ) -> TradeResult:
        total = quantity * price
        tx = Transaction(
            id="tx-cash",
            type=trade_type,
            instrument_id=instrument_id,
            symbol="SYM",
            quantity=quantity,
            price=price,
            total=total,
            executed_at="2026-08-20T08:00:00Z",
        )
        # Mirrors producción: buy descuenta notional+fees; sell suma notional − fees.
        if trade_type == "buy":
            self._cash -= total + fee_amount
        else:
            self._cash += total - fee_amount
        self._by_key[idempotency_key] = tx
        return TradeResult(transaction=tx, summary=_FakeSummary(self._cash))


@pytest.mark.asyncio
async def test_execute_trade_with_decimal_sequential_balance_exact() -> None:
    """R-11 C3 / EXEC-B-CONC: buy+fee balance_after desde summary post-lock.

    Compra con fracciones: fee_balance = cash post notional+fee; trade_balance =
    fee_balance + fee. Sin get_summary pre-lock en el camino feliz.
    """
    ledger = _FakeLedgerRepo()
    portfolio = _CashAwarePortfolioRepo(cash=105000.0)
    use_case = ExecuteTrade(_FakeAccountRepo(), portfolio, ledger)  # type: ignore[arg-type]

    await use_case.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=10.0,
        price=100.1234567,
        account_id="acc-1",
        idempotency_key="decimal-key-1-abcdefghij",
    )

    assert portfolio.get_summary_calls == 0
    assert ledger.trade_amount is not None
    assert ledger.fee_amount is not None
    assert ledger.trade_balance is not None
    assert ledger.fee_balance is not None

    # fee_balance == trade_balance + fee (negativo). La resta se reconstruye en
    # float en el fake; usamos approx para tolerar el ULP de representación, pero
    # sigue demostrando que NO hay drift >1 centésima (R-10.8).
    assert ledger.fee_balance == pytest.approx(ledger.trade_balance - ledger.fee_amount), (
        f"secuencia: {ledger.trade_balance} - {ledger.fee_amount} "
        f"debería ser {ledger.fee_balance}"
    )
    # trade_balance == cash_inicial - |amount_trade| (compra: amount negativo).
    assert ledger.trade_balance == pytest.approx(105000.0 - abs(ledger.trade_amount)), (
        f"trade_balance={ledger.trade_balance} != 105000 - {abs(ledger.trade_amount)}"
    )
    # Con el notional fraccionario (>6 decimales), la resta secuencial cierra: la
    # fee_balance queda por debajo de trade_balance en exactamente el fee.
    assert ledger.fee_balance == pytest.approx(105000.0 - abs(ledger.trade_amount) - ledger.fee_amount)
    # EXEC-B-CONC: fee_balance == cash post-lock del summary (último cash del fake).
    assert ledger.fee_balance == pytest.approx(portfolio._cash)


@pytest.mark.asyncio
async def test_execute_trade_sell_sequential_balance_from_post_lock_summary() -> None:
    """EXEC-B-CONC: sell+fee balance_after desde summary post-lock (R-10 F3).

    Venta: amount positivo (notional); fee_balance = prior + notional − fee;
    trade_balance = fee_balance + fee (= prior + notional).
    """
    ledger = _FakeLedgerRepo()
    cash_before = 50_000.0
    portfolio = _CashAwarePortfolioRepo(cash=cash_before)
    use_case = ExecuteTrade(_FakeAccountRepo(), portfolio, ledger)  # type: ignore[arg-type]

    await use_case.execute(
        instrument_id="inst-1",
        trade_type="sell",
        quantity=5.0,
        price=200.0,
        account_id="acc-1",
        idempotency_key="decimal-key-sell-abcdefgh",
    )

    assert portfolio.get_summary_calls == 0
    assert ledger.trade_amount is not None
    assert ledger.fee_amount is not None
    assert ledger.trade_balance is not None
    assert ledger.fee_balance is not None
    assert ledger.trade_amount > 0
    assert ledger.fee_balance == pytest.approx(ledger.trade_balance - ledger.fee_amount)
    assert ledger.trade_balance == pytest.approx(cash_before + ledger.trade_amount)
    assert ledger.fee_balance == pytest.approx(
        cash_before + ledger.trade_amount - ledger.fee_amount
    )
    assert ledger.fee_balance == pytest.approx(portfolio._cash)


@pytest.mark.asyncio
async def test_execute_trade_zero_fee_trade_balance_equals_fee_balance() -> None:
    """EXEC-B-CONC: fees.total==0 → trade_balance == fee_balance; sin append_fee."""
    from bolsa_domain.account_settings import settings_from_dict

    ledger = _FakeLedgerRepo()
    portfolio = _CashAwarePortfolioRepo(cash=10_000.0)
    account_repo = _FakeAccountRepo()
    account_repo.scope.account.settings = settings_from_dict(
        {
            "commission": {"presetId": "none"},
            "tax": {"costBasisMethod": "FIFO", "stampDutyBuyPct": 0.0},
        }
    )
    use_case = ExecuteTrade(account_repo, portfolio, ledger)  # type: ignore[arg-type]

    await use_case.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=50.0,
        account_id="acc-1",
        idempotency_key="decimal-key-zerofee-abcdef",
    )

    assert ledger.rows == [("buy", "tx-cash")]
    assert ledger.fee_amount is None
    assert ledger.trade_balance is not None
    assert ledger.trade_balance == pytest.approx(portfolio._cash)
    assert ledger.trade_balance == pytest.approx(10_000.0 - 100.0)


@pytest.mark.asyncio
async def test_confirm_recommendation_forwards_decision_id_as_idempotency_key() -> None:
    """ConfirmRecommendationIntent: clave lógica = decision|action|side (V1.91 OPEN/T1/EXIT)."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)

    await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-123",
            instrument_id="inst-1",
            quantity=5.0,
            price=12.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["idempotency_key"] == "DEC-123|recommend_long|buy"


class _FakeCognitiveStore:
    """Store en memoria para ConfirmRecommendationIntent (solo get/update)."""

    def __init__(self, session: Any | None = None) -> None:
        self._session = session
        self.updated: list[Any] = []

    async def get_decision_session(self, session_id: str) -> Any | None:
        return self._session

    async def update_decision_session(self, record: Any) -> Any:
        self.updated.append(record)
        return record

    async def append_decision_session(self, record: Any) -> Any:
        return record


def _session_record_with_package(
    *,
    decision_id: str,
    instrument_id: str,
    action: str,
) -> DecisionSessionRecord:
    """Sesión `propose` persistida con runtime.decisionPackage."""
    return DecisionSessionRecord(
        id="DSS-1",
        kind="propose",
        status="open",
        instrument_id=instrument_id,
        created_at="2026-08-24T00:00:00Z",
        decision_id=decision_id,
        payload={
            "decisionId": decision_id,
            "runtime": {
                "decisionPackage": {
                    "decisionId": decision_id,
                    "instrumentId": instrument_id,
                    "action": action,
                }
            },
        },
    )


@pytest.mark.asyncio
async def test_confirm_with_matching_package_executes() -> None:
    """Package de la sesión coherente con el intent → el trade se ejecuta y contrato=present."""
    fake_trade = _FakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-1",
            instrument_id="inst-1",
            action="recommend_long",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-1",
            instrument_id="inst-1",
            quantity=5.0,
            price=12.0,
        ),
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 1
    assert result["intent"]["contract"] == "present_verified"
    assert result["trade"]["status"] == "executed"


@pytest.mark.asyncio
async def test_confirm_with_conflicting_action_rejected() -> None:
    """El package de la sesión abre `sell` pero el intent pide `buy` → fail-closed."""
    fake_trade = _FakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-1",
            instrument_id="inst-1",
            action="recommend_short",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-1",
            instrument_id="inst-1",
            quantity=5.0,
            price=12.0,
        ),
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "decision_package_conflict"
    assert result["intent"]["status"] == "rejected_by_gate"


@pytest.mark.asyncio
async def test_confirm_with_conflicting_instrument_rejected() -> None:
    """El package de la sesión es para otro instrumento → fail-closed."""
    fake_trade = _FakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-1",
            instrument_id="inst-999",
            action="recommend_long",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-1",
            instrument_id="inst-1",
            quantity=5.0,
            price=12.0,
        ),
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "decision_package_conflict"


@pytest.mark.asyncio
async def test_confirm_without_session_orphan_opening_blocked() -> None:
    """H3 / ADR-031 — store cableado sin package → no fill (apertura)."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        cognitive_store=_FakeCognitiveStore(None),  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-123",
            instrument_id="inst-1",
            quantity=5.0,
            price=12.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["intent"]["contract"] == "absent"
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "orphan_opening_blocked"


@pytest.mark.asyncio
async def test_confirm_with_edited_sizing_and_matching_package_executes() -> None:
    """El sizing editado por el humano NO se concilia: trade ejecuta si identidad coincide."""
    fake_trade = _FakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-1",
            instrument_id="inst-1",
            action="recommend_long",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-1",
            instrument_id="inst-1",
            quantity=99.0,
            price=7.5,
            plan_quantity=100.0,
        ),
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["quantity"] == 99.0
    assert result["trade"]["status"] == "executed"


# ── Escalón 3/D1 — re-evaluación VETO de cesta en el confirm SEMI ──────────────
# Replica el Risk de cesta de AUTO en el confirm: solo aperturas; exit_hint/reduce
# quedan fuera; portfolio_summary=None conserva el comportamiento previo.

@dataclass
class _FakePosition:
    """Position mínima para construir la cesta del Risk desde un PortfolioSummary."""

    instrument_id: str
    market_value: float
    sector: str | None = None


class _FakePortfolioSummary:
    """Fake read-only de `GetPortfolioSummary` para el confirm SEMI."""

    def __init__(self, positions: list[_FakePosition], total_equity: float) -> None:
        self.positions = positions
        self.total_equity = total_equity

    async def execute(self, account_id: str | None = None, portfolio_id: str | None = None):
        return self


def _risk_veto_summary() -> _FakePortfolioSummary:
    """Cesta donde la apertura propuesta supera la exposición de sector (>30% moderate)."""
    return _FakePortfolioSummary(
        positions=[
            _FakePosition("t1", 22.0, "tech"),
            _FakePosition("t2", 22.0, "tech"),
            _FakePosition("t3", 22.0, "tech"),
            _FakePosition("t4", 22.0, "tech"),
            _FakePosition("h1", 20.0, "health"),
            _FakePosition("h2", 20.0, "health"),
            _FakePosition("e1", 20.0, "energy"),
            _FakePosition("c1", 10.0, "cons"),
        ],
        total_equity=200.0,
    )


def _risk_allow_summary() -> _FakePortfolioSummary:
    """Cesta diversificada: la apertura propuesta no viola concentración ni sector."""
    return _FakePortfolioSummary(
        positions=[
            _FakePosition("a", 4.0, "tech"),
            _FakePosition("b", 4.0, "health"),
            _FakePosition("c", 4.0, "energy"),
            _FakePosition("d", 4.0, "cons"),
        ],
        total_equity=200.0,
    )


@pytest.mark.asyncio
async def test_confirm_apertura_cesta_veto_bloquea_fill() -> None:
    """Escalón 3/D1 — apertura cuya cesta veta → rejected_by_gate/risk_veto; NO fill."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_veto_summary(),  # type: ignore[arg-type]
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-1",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"
    assert result["intent"]["status"] == "rejected_by_gate"


@pytest.mark.asyncio
async def test_confirm_apertura_cesta_permite_fill() -> None:
    """Escalón 3/D1 — apertura cuya cesta encaja → fill se ejecuta."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-2",
            instrument_id="inst-new",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert result["trade"]["status"] == "executed"


@pytest.mark.asyncio
async def test_confirm_exit_hint_orphan_fail_closed_unknown_side() -> None:
    """Deuda confirm SEMI (Bug 2) — exit_hint sin sesión/package → fail-closed.

    Sin package no se puede saber si el cierre va sell (largo) o buy (corto): se
    rechaza con `unknown_position_side` en vez de ejecutar un sell a ciegas (que hoy
    re-abriría un short). Antes (Escalón 3/D1) un orphan `exit_hint` ejecutaba sell.
    """
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_veto_summary(),  # type: ignore[arg-type]
    )

    result = await use_case.execute(
        recommendation_raw={
            "decisionId": "DEC-3",
            "instrumentId": "inst-1",
            "action": "exit_hint",
            "suggestedQuantity": 2.0,
            "suggestedPrice": 1.0,
        },
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "unknown_position_side"
    assert result["intent"]["status"] == "rejected_by_gate"


@pytest.mark.asyncio
async def test_confirm_wait_no_ejecuta_sell_default() -> None:
    """Deuda confirm SEMI (Bug 1) — una tesis `wait` NO abre/cierra nada.

    Antes, `intent_from_recommendation` mapeaba `wait` → side=`sell`, así que un
    confirm `wait` con `suggestedQuantity>0` ejecutaba una venta default. Ahora
    `wait` no es transaccional: el trade queda vacío y no se llama al ExecuteTrade.
    """
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)

    result = await use_case.execute(
        recommendation_raw={
            "decisionId": "DEC-WAIT",
            "instrumentId": "inst-1",
            "action": "wait",
            "suggestedQuantity": 5.0,
            "suggestedPrice": 10.0,
        },
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"] is None
    assert result["intent"]["status"] == "authorized"


@pytest.mark.asyncio
async def test_confirm_reduce_short_covers_not_reopen() -> None:
    """Bug 2 — `reduce` de un short cubre con **buy** (no reabre con sell).

    Package de sesión = `recommend_short`. `intent_from_recommendation` mapea
    `reduce` → sell por defecto; Confirm corrige el lado desde el package.
    """
    fake_trade = _FakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-RED",
            instrument_id="inst-1",
            action="recommend_short",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw={
            "decisionId": "DEC-RED",
            "instrumentId": "inst-1",
            "action": "reduce",
            "suggestedQuantity": 2.0,
            "suggestedPrice": 1.0,
        },
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["trade_type"] == "buy"
    assert result["trade"]["status"] == "executed"
    assert result["intent"]["side"] == "buy"


@pytest.mark.asyncio
async def test_confirm_exit_hint_short_covers_not_reopen() -> None:
    """Bug 2 — `exit_hint` de un short cubre con **buy**."""
    fake_trade = _FakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-EX",
            instrument_id="inst-1",
            action="recommend_short",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw={
            "decisionId": "DEC-EX",
            "instrumentId": "inst-1",
            "action": "exit_hint",
            "suggestedQuantity": 2.0,
            "suggestedPrice": 1.0,
        },
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["trade_type"] == "buy"
    assert result["trade"]["status"] == "executed"


@pytest.mark.asyncio
async def test_confirm_exit_hint_largo_con_package_ejecuta_sell() -> None:
    """Deuda confirm SEMI (Bug 2) — cerrar un LARGO con package `recommend_long` es legítimo.

    `exit_hint` de un largo requiere `sell`, que coincide con el intent → se ejecuta.
    (Antes D2 rechazaba cualquier exit_hint contra un package `recommend_long`.)
    """
    fake_trade = _FakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-EXL",
            instrument_id="inst-1",
            action="recommend_long",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )

    result = await use_case.execute(
        recommendation_raw={
            "decisionId": "DEC-EXL",
            "instrumentId": "inst-1",
            "action": "exit_hint",
            "suggestedQuantity": 2.0,
            "suggestedPrice": 1.0,
        },
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["trade_type"] == "sell"
    assert result["trade"]["status"] == "executed"


@pytest.mark.asyncio
async def test_confirm_apertura_sin_summary_no_aplica_cesta() -> None:
    """Escalón 3/D1 — portfolio_summary=None conserva el comportamiento previo (sin veto)."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-4",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert result["trade"]["status"] == "executed"


def _sector_gap_summary() -> _FakePortfolioSummary:
    """Cesta tech al 29% (bajo el 30% moderate). El fill nuevo (2%) solo veta
    si entra en tech; si cae a `<unknown>` el sector se queda en 29% y ALLOW.
    """
    return _FakePortfolioSummary(
        positions=[
            _FakePosition("t1", 22.0, "tech"),
            _FakePosition("t2", 22.0, "tech"),
            _FakePosition("t3", 14.0, "tech"),
            _FakePosition("h1", 20.0, "health"),
            _FakePosition("e1", 20.0, "energy"),
            _FakePosition("c1", 10.0, "cons"),
        ],
        total_equity=200.0,
    )


class _FakeInstrument:
    def __init__(self, instrument_id: str, sector: str | None) -> None:
        self.id = instrument_id
        self.sector = sector


class _FakeInstruments:
    """Lookup mínimo `get_by_id` (H1) — mismo contrato que InstrumentSectorLookup."""

    def __init__(self, by_id: dict[str, _FakeInstrument]) -> None:
        self._by_id = by_id

    async def get_by_id(self, instrument_id: str) -> _FakeInstrument | None:
        return self._by_id.get(instrument_id)


class _RaisingPortfolioSummary:
    """H2 — GetPortfolioSummary inyectado que lanza (indisponibilidad)."""

    async def execute(self, account_id: str | None = None, portfolio_id: str | None = None):
        raise RuntimeError("portfolio summary unavailable")


@pytest.mark.asyncio
async def test_confirm_apertura_sector_propuesto_veto_como_auto() -> None:
    """H1 — proposal_sector desde instruments.sector: fill tech sobre cesta 29% → veto.

    Sin este lookup el notional nuevo cae a `<unknown>` y MaxSectorExposure no
    cuenta el overlap (gap vs AUTO `hit.sector`).
    """
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_sector_gap_summary(),  # type: ignore[arg-type]
        instruments=_FakeInstruments({"inst-new": _FakeInstrument("inst-new", "tech")}),
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-H1",
            instrument_id="inst-new",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"
    assert result["intent"]["status"] == "rejected_by_gate"


@pytest.mark.asyncio
async def test_confirm_apertura_summary_falla_fail_closed() -> None:
    """H2 / D1 — summary inyectado que lanza → risk_veto; no hay override por error."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_RaisingPortfolioSummary(),  # type: ignore[arg-type]
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-H2",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"
    assert result["intent"]["status"] == "rejected_by_gate"


# ── H5 — SEMI pasa InvestorProfile a check_opening (mismo SoT que AUTO) ────────


def _profile_boundary_summary() -> _FakePortfolioSummary:
    """Tech al 19% (38/200); fill 4@1 tech → 42/200 = 21%.

    Entre conservative max_sector 20% (VETO) y moderate 30% (ALLOW).
    """
    return _FakePortfolioSummary(
        positions=[
            _FakePosition("t1", 10.0, "tech"),
            _FakePosition("t2", 10.0, "tech"),
            _FakePosition("t3", 10.0, "tech"),
            _FakePosition("t4", 8.0, "tech"),
            _FakePosition("h1", 20.0, "health"),
            _FakePosition("e1", 20.0, "energy"),
            _FakePosition("c1", 10.0, "cons"),
        ],
        total_equity=200.0,
    )


@dataclass
class _FakeAccountWithProfile:
    id: str = "acc-1"
    active_profile_id: str | None = "prof-cons"


@dataclass
class _FakeScopeWithProfile:
    account: _FakeAccountWithProfile = field(default_factory=_FakeAccountWithProfile)


class _FakeAccountsWithProfile:
    """AccountScopeLookup mínimo (H5) — resolve_scope → active_profile_id."""

    def __init__(self, active_profile_id: str | None = "prof-cons") -> None:
        self._scope = _FakeScopeWithProfile(
            account=_FakeAccountWithProfile(active_profile_id=active_profile_id)
        )

    async def resolve_scope(
        self, account_id: str, portfolio_id: str | None = None
    ) -> _FakeScopeWithProfile:
        return self._scope


def _conservative_profile() -> InvestorProfileRecord:
    """Copia mínima de test_trading_policy_guard._profile (template conservative)."""
    return InvestorProfileRecord(
        id="prof-cons",
        name="Test",
        version="1.0.0",
        horizon="swing",
        objectives=("growth",),
        risk_tolerance="low",
        experience="intermediate",
        suggested_policy_template_id="conservative",
        selected_policy_template_id="conservative",
        updated_by="test",
        created_at="2026-07-23T00:00:00Z",
        updated_at="2026-07-23T00:00:00Z",
    )


class _FakeProfileStore:
    """InvestorProfileStore mínimo (H5) — solo get."""

    def __init__(self, profile: InvestorProfileRecord | None) -> None:
        self._profile = profile

    async def get(self, profile_id: str) -> InvestorProfileRecord | None:
        if self._profile is not None and self._profile.id == profile_id:
            return self._profile
        return None


@pytest.mark.asyncio
async def test_confirm_apertura_profile_conservative_veto() -> None:
    """H5 — perfil conservative (max sector 20%) sobre cesta 21% tech → risk_veto."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_profile_boundary_summary(),  # type: ignore[arg-type]
        instruments=_FakeInstruments({"inst-new": _FakeInstrument("inst-new", "tech")}),
        accounts=_FakeAccountsWithProfile(),  # type: ignore[arg-type]
        profile_store=_FakeProfileStore(_conservative_profile()),  # type: ignore[arg-type]
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-H5-VETO",
            instrument_id="inst-new",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"
    assert result["intent"]["status"] == "rejected_by_gate"


@pytest.mark.asyncio
async def test_confirm_apertura_profile_none_allows_same_basket() -> None:
    """H5 — misma cesta 21% tech sin profile_store → defaults moderate (30%) → fill."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_profile_boundary_summary(),  # type: ignore[arg-type]
        instruments=_FakeInstruments({"inst-new": _FakeInstrument("inst-new", "tech")}),
        accounts=_FakeAccountsWithProfile(),  # type: ignore[arg-type]
        profile_store=None,
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-H5-ALLOW",
            instrument_id="inst-new",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert result["trade"]["status"] == "executed"


# ── DS-05 — Data Freshness Gate en confirm SEMI (mismo check_opening que AUTO) ─


class _FakeOhlcv:
    """LatestBarLookup mínimo (DS-05) — get_latest_bar_date."""

    def __init__(self, last_bar: str | None) -> None:
        self._last_bar = last_bar

    async def get_latest_bar_date(
        self, instrument_id: str, *, timeframe: object = None
    ) -> str | None:
        return self._last_bar


class _RaisingOhlcv:
    async def get_latest_bar_date(
        self, instrument_id: str, *, timeframe: object = None
    ) -> str | None:
        raise RuntimeError("ohlcv unavailable")


@pytest.mark.asyncio
async def test_confirm_apertura_stale_bar_risk_veto() -> None:
    """DS-05 — ohlcv inyectado con barra vieja → risk_veto; NO fill."""
    from datetime import UTC, datetime, timedelta

    from bolsa_application.risk_engine import DATA_FRESHNESS_MAX_AGE_SECONDS

    stale = (
        datetime.now(UTC) - timedelta(seconds=DATA_FRESHNESS_MAX_AGE_SECONDS + 3600)
    ).date().isoformat()
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        ohlcv=_FakeOhlcv(stale),
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-DS05-STALE",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"
    assert result["intent"]["status"] == "rejected_by_gate"


@pytest.mark.asyncio
async def test_confirm_apertura_fresh_bar_permite_fill() -> None:
    """DS-05 — ohlcv con barra reciente + cesta OK → fill."""
    from datetime import UTC, datetime

    fresh = datetime.now(UTC).date().isoformat()
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        ohlcv=_FakeOhlcv(fresh),
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-DS05-FRESH",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert result["trade"]["status"] == "executed"


@pytest.mark.asyncio
async def test_confirm_apertura_ohlcv_falla_fail_closed() -> None:
    """DS-05 — lookup OHLCV que lanza → risk_veto (fail-closed, como H2)."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        ohlcv=_RaisingOhlcv(),
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-DS05-OHLCV-FAIL",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"


# ── DS-03 — Account Mandate Gate en confirm SEMI (mismo check_opening que AUTO) ─


class _FakeMandatesNoOpen:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return False, None


class _FakeMandatesOpen:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return True, "st-mandate-1"


class _RaisingMandates:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        raise RuntimeError("mandates unavailable")


@pytest.mark.asyncio
async def test_confirm_apertura_no_open_mandate_risk_veto() -> None:
    """DS-03 — mandates inyectado sin tenure abierto → risk_veto; NO fill."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        mandates=_FakeMandatesNoOpen(),
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-DS03-NO-MANDATE",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"


@pytest.mark.asyncio
async def test_confirm_apertura_open_mandate_permite_fill() -> None:
    """DS-03 — tenure abierto + cesta OK → fill."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        mandates=_FakeMandatesOpen(),
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-DS03-OPEN",
            instrument_id="inst-new",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert result["trade"]["status"] == "executed"


@pytest.mark.asyncio
async def test_confirm_apertura_mandates_falla_fail_closed() -> None:
    """DS-03 — lookup mandates que lanza → risk_veto (fail-closed)."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        mandates=_RaisingMandates(),
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-DS03-MANDATE-FAIL",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"


class _FakePortfolioReconDrift:
    async def portfolio_recon_status(self, account_id: str) -> str:
        return "drift"


class _FakePortfolioReconClean:
    async def portfolio_recon_status(self, account_id: str) -> str:
        return "clean"


@pytest.mark.asyncio
async def test_confirm_apertura_portfolio_drift_risk_veto() -> None:
    """OR-4 — portfolio recon drift → risk_veto; NO fill."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        portfolio_recon=_FakePortfolioReconDrift(),  # type: ignore[arg-type]
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-OR4-DRIFT",
            instrument_id="inst-1",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"


@pytest.mark.asyncio
async def test_confirm_apertura_portfolio_clean_permite_fill() -> None:
    """OR-4 — portfolio recon clean + cesta OK → fill."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_risk_allow_summary(),  # type: ignore[arg-type]
        portfolio_recon=_FakePortfolioReconClean(),  # type: ignore[arg-type]
    )

    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-OR4-CLEAN",
            instrument_id="inst-new",
            quantity=4.0,
            price=1.0,
        ),
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert result["trade"]["status"] == "executed"


@pytest.mark.asyncio
async def test_confirm_expired_recommendation_no_fill() -> None:
    """ADR-031 TTL — expiresAt en el pasado → expired, sin ExecuteTrade."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)
    past = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    raw = _opening_recommendation(
        decision_id="DEC-TTL",
        instrument_id="inst-1",
        quantity=5.0,
        price=12.0,
    )
    raw["expiresAt"] = past

    result = await use_case.execute(
        recommendation_raw=raw,
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "expired"


@pytest.mark.asyncio
async def test_confirm_stale_price_vs_last_close() -> None:
    """ADR-031 — close 100 vs suggested 12 (>2%) → stale_price."""

    class _CloseOhlcv:
        async def get_latest_bar_date(self, instrument_id: str, *, timeframe: object = None) -> str:
            return datetime.now(UTC).date().isoformat()

        async def get_latest_close(self, instrument_id: str, *, timeframe: object = None) -> float:
            return 100.0

    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        ohlcv=_CloseOhlcv(),  # type: ignore[arg-type]
    )
    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(
            decision_id="DEC-PX",
            instrument_id="inst-1",
            quantity=5.0,
            price=12.0,
        ),
        account_id="acc-1",
        execute=True,
    )
    assert len(fake_trade.calls) == 0
    assert result["trade"]["reason"] == "stale_price"


@pytest.mark.asyncio
async def test_confirm_double_execute_concurrent_single_logical_fill() -> None:
    """Dos confirm concurrentes con el mismo decision_id → un fill + un replay."""

    class _IdempotentFakeExecuteTrade:
        def __init__(self) -> None:
            self._lock = asyncio.Lock()
            self._by_key: dict[str, TradeResult] = {}
            self.unique_fills = 0
            self.calls: list[str] = []

        async def execute(self, **kwargs: object) -> TradeResult:
            key = str(kwargs.get("idempotency_key") or "")
            await asyncio.sleep(0.02)
            async with self._lock:
                existing = self._by_key.get(key)
                if existing is not None:
                    self.calls.append("replay")
                    return existing
                self.unique_fills += 1
                tx = Transaction(
                    id=f"tx-{self.unique_fills}",
                    type="buy",  # type: ignore[arg-type]
                    instrument_id="inst-1",
                    symbol="SYM",
                    quantity=1.0,
                    price=10.0,
                    total=10.0,
                    executed_at="2026-08-20T08:00:00Z",
                )
                result = TradeResult(transaction=tx, summary=_FakeSummary(0.0))
                self._by_key[key] = result
                self.calls.append("fill")
                return result

    fake_trade = _IdempotentFakeExecuteTrade()
    store = _FakeCognitiveStore(
        _session_record_with_package(
            decision_id="DEC-RACE",
            instrument_id="inst-1",
            action="recommend_long",
        )
    )
    use_case = ConfirmRecommendationIntent(
        cognitive_store=store,  # type: ignore[arg-type]
        execute_trade=fake_trade,
    )
    raw = _opening_recommendation(
        decision_id="DEC-RACE",
        instrument_id="inst-1",
        quantity=5.0,
        price=12.0,
    )

    async def _once() -> dict[str, Any]:
        return await use_case.execute(
            recommendation_raw=raw,
            account_id="acc-1",
            execute=True,
            session_id="DSS-1",
        )

    r1, r2 = await asyncio.gather(_once(), _once())
    assert fake_trade.unique_fills == 1
    assert {r1["trade"]["status"], r2["trade"]["status"]} == {"executed"}
    assert "fill" in fake_trade.calls
    assert "replay" in fake_trade.calls


class _IdempotentPeekExecuteTrade:
    """OR-1 — fill + peek find_existing_by_idempotency (short-circuit Confirm)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_key: dict[str, TradeResult] = {}
        self.unique_fills = 0
        self.execute_calls = 0
        self.peek_calls = 0

    async def find_existing_by_idempotency(
        self,
        *,
        account_id: str | None = None,
        portfolio_id: str | None = None,
        idempotency_key: str,
    ) -> TradeResult | None:
        _ = account_id, portfolio_id
        self.peek_calls += 1
        return self._by_key.get(idempotency_key)

    async def execute(self, **kwargs: object) -> TradeResult:
        key = str(kwargs.get("idempotency_key") or "")
        async with self._lock:
            self.execute_calls += 1
            existing = self._by_key.get(key)
            if existing is not None:
                return existing
            self.unique_fills += 1
            tx = Transaction(
                id=f"tx-{self.unique_fills}",
                type="buy",  # type: ignore[arg-type]
                instrument_id="inst-1",
                symbol="SYM",
                quantity=1.0,
                price=10.0,
                total=10.0,
                executed_at="2026-08-20T08:00:00Z",
            )
            result = TradeResult(transaction=tx, summary=_FakeSummary(0.0))
            self._by_key[key] = result
            return result


class _CountingJournal:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def append(self, entry: Any) -> Any:
        self.events.append(str(getattr(entry, "event_type", "") or ""))
        return entry


@pytest.mark.asyncio
async def test_or1_confirm_retry_post_fill_short_circuits_without_submit() -> None:
    """OR-1 — retry Confirm paper post-fill → 1 fill, mismos ids, sin segundo submit."""
    from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision
    from bolsa_analytics.cognitive.paper_order import stable_order_id_from_decision

    fake_trade = _IdempotentPeekExecuteTrade()
    journal = _CountingJournal()
    decision_id = "DEC-OR1-RETRY"
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        journal_writer=journal,
    )
    raw = _opening_recommendation(
        decision_id=decision_id,
        instrument_id="inst-1",
        quantity=5.0,
        price=12.0,
    )

    first = await use_case.execute(
        recommendation_raw=raw,
        account_id="acc-1",
        execute=True,
    )
    second = await use_case.execute(
        recommendation_raw=raw,
        account_id="acc-1",
        execute=True,
    )

    assert fake_trade.unique_fills == 1
    assert fake_trade.execute_calls == 1
    assert first["trade"]["status"] == "executed"
    assert second["trade"]["status"] == "executed"
    assert second["trade"].get("idempotentReplay") is True
    assert first["trade"]["transactionId"] == second["trade"]["transactionId"]
    assert first["intent"]["intentId"] == second["intent"]["intentId"]
    assert first["intent"]["intentId"] == stable_intent_id_from_decision(decision_id)
    assert first["paperOrder"]["orderId"] == second["paperOrder"]["orderId"]
    assert first["paperOrder"]["orderId"] == stable_order_id_from_decision(decision_id)
    assert first["paperOrder"]["status"] == "FILLED"
    assert second["paperOrder"]["status"] == "FILLED"
    assert second["executionRecord"]["outcome"] == "executed"
    assert journal.events.count("executed") == 1


@pytest.mark.asyncio
async def test_or1_confirm_missing_decision_id_fail_closed_pre_send() -> None:
    """OR-1 D1 — sin decision_id → error pre-send; no adapter/execute."""
    fake_trade = _IdempotentPeekExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)
    raw = _opening_recommendation(
        decision_id="DEC-TMP",
        instrument_id="inst-1",
        quantity=5.0,
        price=12.0,
    )
    raw["decisionId"] = ""
    raw["tradePlan"]["decisionId"] = ""

    result = await use_case.execute(
        recommendation_raw=raw,
        account_id="acc-1",
        execute=True,
    )

    assert fake_trade.execute_calls == 0
    assert result["trade"]["status"] == "error"
    assert result["trade"]["reason"] == "decision_id_required"
    assert result["intent"]["status"] == "error"


@pytest.mark.asyncio
async def test_or1_stable_intent_and_order_ids_from_decision() -> None:
    """OR-1 D2/D3 — intent_id y order_id estables entre dos confirms."""
    from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision
    from bolsa_analytics.cognitive.paper_order import stable_order_id_from_decision

    decision_id = "DEC-OR1-STABLE"
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)
    raw = _opening_recommendation(
        decision_id=decision_id,
        instrument_id="inst-1",
        quantity=5.0,
        price=12.0,
    )
    r1 = await use_case.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    r2 = await use_case.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    assert r1["intent"]["intentId"] == stable_intent_id_from_decision(decision_id)
    assert r2["intent"]["intentId"] == r1["intent"]["intentId"]
    assert r1["paperOrder"]["orderId"] == stable_order_id_from_decision(decision_id)
    assert r2["paperOrder"]["orderId"] == r1["paperOrder"]["orderId"]


def test_or1_stable_id_helpers_deterministic() -> None:
    from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision
    from bolsa_analytics.cognitive.paper_order import stable_order_id_from_decision

    assert stable_intent_id_from_decision("DEC-1") == "INT-DEC-1"
    assert stable_order_id_from_decision("DEC-1") == "ORD-DEC-1"
    assert stable_intent_id_from_decision("DEC-1") == stable_intent_id_from_decision("DEC-1")

