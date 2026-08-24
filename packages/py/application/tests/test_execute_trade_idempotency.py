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
from typing import Any

import pytest

from bolsa_application.accounts import ExecuteTrade
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord
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
        recommendation_raw={
            "decisionId": "DEC-1",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 5.0,
            "suggestedPrice": 12.0,
        },
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
        recommendation_raw={
            "decisionId": "DEC-1",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 5.0,
            "suggestedPrice": 12.0,
        },
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
        recommendation_raw={
            "decisionId": "DEC-1",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 5.0,
            "suggestedPrice": 12.0,
        },
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "decision_package_conflict"


@pytest.mark.asyncio
async def test_confirm_without_session_executes_with_contract_absent() -> None:
    """Sin sesión/package (orphan) → el trade NO se bloquea; contrato=absent (visibilidad)."""
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(execute_trade=fake_trade)

    result = await use_case.execute(
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
    assert result["intent"]["contract"] == "absent"
    assert result["trade"]["status"] == "executed"


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
        recommendation_raw={
            "decisionId": "DEC-1",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 99.0,  # tamaño editado, ajeno al paquete
            "suggestedPrice": 7.5,
        },
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
        recommendation_raw={
            "decisionId": "DEC-1",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 4.0,
            "suggestedPrice": 1.0,
        },
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
        recommendation_raw={
            "decisionId": "DEC-2",
            "instrumentId": "inst-new",
            "action": "recommend_long",
            "suggestedQuantity": 4.0,
            "suggestedPrice": 1.0,
        },
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
async def test_confirm_reduce_short_conflict_no_reapertura() -> None:
    """Deuda confirm SEMI (Bug 2) — `reduce` de un short NO ejecuta un sell de apertura.

    Package de sesión = `recommend_short` (posición corta). `intent_from_recommendation`
    mapea `reduce` → sell, pero cerrar/reducir un corto debe ser **buy** (cover). El
    side `sell` diverge del requerido `buy` → `decision_package_conflict` fail-closed.
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

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "decision_package_conflict"
    assert result["intent"]["status"] == "rejected_by_gate"


@pytest.mark.asyncio
async def test_confirm_exit_hint_short_conflict_no_reapertura() -> None:
    """Deuda confirm SEMI (Bug 2) — `exit_hint` de un short NO ejecuta un sell de apertura."""
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

    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "decision_package_conflict"


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
        recommendation_raw={
            "decisionId": "DEC-4",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 4.0,
            "suggestedPrice": 1.0,
        },
        account_id="acc-1",
        execute=True,
    )

    assert len(fake_trade.calls) == 1
    assert result["trade"]["status"] == "executed"
