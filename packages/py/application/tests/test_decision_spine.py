"""Decision Spine — índice de unicidad SEMI=AUTO (mismo risk, distinta autorización).

DS-01/02/06/09/11 viven en ``test_execute_trade_idempotency.py``.
DS-04 vive en ``test_risk_engine_portfolio_fit.py`` (+ H1 SEMI sector).
DS-05 vive aquí (AUTO stale) + ``test_risk_engine.py`` (unit) + SEMI en
``test_execute_trade_idempotency.py``.
DS-03 vive aquí (AUTO no mandate) + unit + SEMI en idempotency.
DS-08 (este fichero): AUTO + ``check_opening`` DENY → el router **no** llama a ``ExecuteTrade``.

No cubiertos aquí: DS-12..15 broker.
Suite: ``pnpm test:decision-spine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from bolsa_analytics.signals.strategy import SignalEventV1
from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.risk_engine import DATA_FRESHNESS_MAX_AGE_SECONDS
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord


@dataclass
class _FakePosition:
    instrument_id: str
    market_value: float
    sector: str | None = None
    quantity: float = 1.0


class _FakePortfolioSummary:
    def __init__(self, positions: list[_FakePosition], total_equity: float) -> None:
        self.positions = positions
        self.total_equity = total_equity

    async def execute(
        self, account_id: str | None = None, portfolio_id: str | None = None
    ) -> _FakePortfolioSummary:
        return self


class _FakeAccount:
    id = "acc-ds08"
    type = "simulated"
    initial_deposit = 200.0
    active_profile_id = None


class _FakeScope:
    account = _FakeAccount()


class _FakeAccountRepo:
    async def resolve_scope(
        self, account_id: str, portfolio_id: str | None = None
    ) -> _FakeScope:
        return _FakeScope()

    async def get_settings_json(self, account_id: str) -> dict[str, Any]:
        return {}

    async def merge_settings_json(self, account_id: str, fragment: dict[str, Any]) -> None:
        return None


class _FakeExecuteTrade:
    def __init__(self, *, return_result: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self._return_result = return_result

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self._return_result:
            return None
        tx = type("Tx", (), {"id": "tx-ds03"})()
        return type("TradeResult", (), {"transaction": tx})()


def _sector_gap_summary() -> _FakePortfolioSummary:
    """Misma cesta H1: tech 29%. Fill 2% tech solo veta si ``proposal_sector`` entra."""
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


def _empty_summary() -> _FakePortfolioSummary:
    return _FakePortfolioSummary(positions=[], total_equity=200.0)


def _a_beta_opening_hit(
    *,
    instrument_id: str = "inst-new",
    sector: str = "tech",
    quantity: float = 4.0,
    price: float = 1.0,
    stop: float = 0.95,
    auto_source: str = "estudio_dictamen",
    trade_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """V1.33 — hit Estudio + TradePlan TRIGGERED (paridad SEMI)."""
    plan = trade_plan
    if plan is None:
        risk = quantity * abs(price - stop)
        plan = {
            "decisionId": "dec-auto-test",
            "instrumentId": instrument_id,
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": quantity,
            "entry": price,
            "structuralStop": stop,
            "riskAmount": risk,
            "initialRiskR": 1,
            "whyNot": [],
            "executionAllowed": True,
        }
    return {
        "sector": sector,
        "instrumentId": instrument_id,
        "autoSource": auto_source,
        "tradePlan": plan,
    }


def _paper_policy() -> ExecutionPolicyRecord:
    return ExecutionPolicyRecord(
        id="pol-ds08",
        name="paper-ds08",
        definition={},
        mode="paper_auto",
        account_id="acc-ds08",
        strategy_definition_id="st-1",
        origin="test",
        enabled=True,
        user_id=None,
        created_at="2026-08-24T00:00:00Z",
        updated_at="2026-08-24T00:00:00Z",
    )


def _entry_long_signal(
    *,
    timestamp: str | None = None,
    instrument_id: str = "inst-new",
    signal_id: str = "sig-ds08",
) -> SignalEventV1:
    ts = timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return SignalEventV1(
        id=signal_id,
        instrument_id=instrument_id,
        timestamp=ts,
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=1.0,
    )


def _router(summary: _FakePortfolioSummary, trade: _FakeExecuteTrade) -> ExecutionRouter:
    return ExecutionRouter(
        policy_repo=object(),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=trade,  # type: ignore[arg-type]
        portfolio_summary=summary,  # type: ignore[arg-type]
        profile_store=None,
    )


@pytest.mark.asyncio
async def test_ds08_auto_risk_block_does_not_execute_trade() -> None:
    """DS-08 — AUTO: ``check_opening`` DENY (sector) → skipped; cero ``ExecuteTrade``."""
    fake_trade = _FakeExecuteTrade()
    result = await _router(_sector_gap_summary(), fake_trade)._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(),
        hit=_a_beta_opening_hit(),
        sizing_value=4.0,
    )

    assert result.status == "skipped"
    assert result.reason is not None
    assert result.reason.startswith("Risk Engine:")
    assert "Exposición sector superada" in result.reason
    assert fake_trade.calls == []


@pytest.mark.asyncio
async def test_ds05_auto_stale_data_does_not_execute_trade() -> None:
    """DS-05 — AUTO: barra/señal más vieja que el umbral → skipped; cero ``ExecuteTrade``."""
    stale_ts = (
        datetime.now(UTC) - timedelta(seconds=DATA_FRESHNESS_MAX_AGE_SECONDS + 3600)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    fake_trade = _FakeExecuteTrade()
    result = await _router(_empty_summary(), fake_trade)._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(timestamp=stale_ts),
        hit=_a_beta_opening_hit(),
        sizing_value=4.0,
    )

    assert result.status == "skipped"
    assert result.reason is not None
    assert result.reason.startswith("Risk Engine:")
    assert "data_freshness:stale:" in result.reason
    assert fake_trade.calls == []


class _FakeMandatesNoOpen:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return False, None


class _FakeMandatesOpen:
    def __init__(self, strategy_id: str = "st-1") -> None:
        self._strategy_id = strategy_id

    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return True, self._strategy_id


def _router_with_mandates(
    summary: _FakePortfolioSummary,
    trade: _FakeExecuteTrade,
    mandates: object,
) -> ExecutionRouter:
    return ExecutionRouter(
        policy_repo=object(),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=trade,  # type: ignore[arg-type]
        portfolio_summary=summary,  # type: ignore[arg-type]
        profile_store=None,
        mandates=mandates,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_ds03_auto_no_open_mandate_does_not_execute_trade() -> None:
    """DS-03 — AUTO: sin tenure abierto → skipped; cero ``ExecuteTrade``."""
    fake_trade = _FakeExecuteTrade()
    result = await _router_with_mandates(
        _empty_summary(), fake_trade, _FakeMandatesNoOpen()
    )._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(),
        hit=_a_beta_opening_hit(),
        sizing_value=4.0,
    )

    assert result.status == "skipped"
    assert result.reason is not None
    assert result.reason.startswith("Risk Engine:")
    assert "account_mandate:no_open_tenure" in result.reason
    assert fake_trade.calls == []


class _FakeInstrumentDataStatus:
    def __init__(self, warnings: tuple[str, ...]) -> None:
        self._warnings = warnings

    async def execute(self, instrument_id: str) -> Any:
        return type("Status", (), {"sanity_warnings": self._warnings})()


def _passing_edge_report():
    from bolsa_analytics.cognitive.edge_report import (
        StatisticalSuiteResult,
        build_edge_report,
    )

    suite = StatisticalSuiteResult(
        trials_n=120,
        walk_forward_efficiency=0.92,
        monte_carlo_p_value=0.01,
        dsr=0.87,
        psr=0.91,
        bootstrap_alpha_ci_lower=0.01,
        bootstrap_alpha_ci_upper=0.05,
        stress_survival_rate=0.9,
    )
    return build_edge_report("st-1", suite)


async def _attach_passing_edge(router: ExecutionRouter) -> None:
    async def _ok(_policy: ExecutionPolicyRecord):
        return _passing_edge_report()

    router._resolve_edge_report = _ok  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_ds03_auto_open_mandate_matching_strategy_executes() -> None:
    """DS-03 — AUTO: tenure abierto + estrategia alineada + edge OK → fill."""
    fake_trade = _FakeExecuteTrade(return_result=True)
    router = _router_with_mandates(
        _empty_summary(), fake_trade, _FakeMandatesOpen("st-1")
    )
    await _attach_passing_edge(router)
    result = await router._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(),
        hit=_a_beta_opening_hit(),
        sizing_value=4.0,
    )

    assert result.status == "trade_executed"
    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["quantity"] == 4.0


@pytest.mark.asyncio
async def test_paper_auto_missing_edge_does_not_execute_trade() -> None:
    """V1.17.1 — paper_auto sin EdgeReport no rellena (umbrales, auto_live=False)."""
    fake_trade = _FakeExecuteTrade(return_result=True)
    result = await _router_with_mandates(
        _empty_summary(), fake_trade, _FakeMandatesOpen("st-1")
    )._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(instrument_id="inst-no-edge", signal_id="sig-no-edge"),
        hit=_a_beta_opening_hit(instrument_id="inst-no-edge"),
        sizing_value=4.0,
    )
    assert result.status == "skipped"
    assert result.reason is not None
    assert result.reason.startswith("Risk Engine:")
    assert fake_trade.calls == []


def _luck_edge_report():
    from bolsa_analytics.cognitive.edge_report import EdgeReport, StatisticalSuiteResult

    return EdgeReport(
        edge_report_id="EDGE-luck-test",
        version="1.0.0",
        strategy_or_signal_ref="st-1",
        created_at="2026-08-27T00:00:00Z",
        suite=StatisticalSuiteResult(trials_n=5, dsr=0.1),
        credibility=40.0,
        edge_score=40.0,
        band="luck",
    )


async def _attach_luck_edge(router: ExecutionRouter) -> None:
    async def _luck(_policy: ExecutionPolicyRecord):
        return _luck_edge_report()

    router._resolve_edge_report = _luck  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_paper_auto_luck_edge_does_not_execute_trade() -> None:
    """V1.17.1 — EdgeReport band=luck veta paper_auto (enforce_edge_thresholds, auto_live=False)."""
    fake_trade = _FakeExecuteTrade(return_result=True)
    router = _router_with_mandates(
        _empty_summary(), fake_trade, _FakeMandatesOpen("st-1")
    )
    await _attach_luck_edge(router)
    result = await router._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(instrument_id="inst-luck", signal_id="sig-luck"),
        hit=_a_beta_opening_hit(instrument_id="inst-luck"),
        sizing_value=4.0,
    )
    assert result.status == "skipped"
    assert result.reason is not None
    assert "edge_band_luck" in result.reason
    assert fake_trade.calls == []


class _FakeInstrumentDataStatusBoom:
    async def execute(self, instrument_id: str) -> Any:
        raise RuntimeError("status unavailable")


@pytest.mark.asyncio
async def test_paper_auto_sanity_lookup_failed_vetoes() -> None:
    """V1.17.1 — fallo de GetInstrumentDataStatus → DENY fail-closed."""
    fake_trade = _FakeExecuteTrade(return_result=True)
    router = ExecutionRouter(
        policy_repo=object(),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=fake_trade,  # type: ignore[arg-type]
        portfolio_summary=_empty_summary(),  # type: ignore[arg-type]
        profile_store=None,
        mandates=_FakeMandatesOpen("st-1"),  # type: ignore[arg-type]
        instrument_data_status=_FakeInstrumentDataStatusBoom(),
    )
    await _attach_passing_edge(router)
    result = await router._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(instrument_id="inst-status-boom", signal_id="sig-status-boom"),
        hit=_a_beta_opening_hit(instrument_id="inst-status-boom"),
        sizing_value=4.0,
    )
    assert result.status == "skipped"
    assert result.reason is not None
    assert "instrument_data_status:lookup_failed" in result.reason
    assert fake_trade.calls == []


def _router_with_sanity(
    warnings: tuple[str, ...],
    trade: _FakeExecuteTrade,
) -> ExecutionRouter:
    return ExecutionRouter(
        policy_repo=object(),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=trade,  # type: ignore[arg-type]
        portfolio_summary=_empty_summary(),  # type: ignore[arg-type]
        profile_store=None,
        mandates=_FakeMandatesOpen("st-1"),  # type: ignore[arg-type]
        instrument_data_status=_FakeInstrumentDataStatus(warnings),
    )


@pytest.mark.asyncio
async def test_paper_auto_sanity_split_vetoes() -> None:
    fake_trade = _FakeExecuteTrade(return_result=True)
    router = _router_with_sanity(
        ("movimiento 55.00% en 2024-01-01 — revisar split/dividendo",),
        fake_trade,
    )
    await _attach_passing_edge(router)
    result = await router._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(instrument_id="inst-split", signal_id="sig-split"),
        hit=_a_beta_opening_hit(instrument_id="inst-split"),
        sizing_value=4.0,
    )
    assert result.status == "skipped"
    assert result.reason is not None
    assert "split" in result.reason.lower() or "sanity" in result.reason.lower() or "risk_veto" in result.reason.lower() or "dividendo" in result.reason.lower()
    assert fake_trade.calls == []


@pytest.mark.asyncio
async def test_paper_auto_sanity_gap_only_allows() -> None:
    fake_trade = _FakeExecuteTrade(return_result=True)
    router = _router_with_sanity(("gap de 2 días",), fake_trade)
    await _attach_passing_edge(router)
    result = await router._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(instrument_id="inst-gap-ok", signal_id="sig-gap"),
        hit=_a_beta_opening_hit(instrument_id="inst-gap-ok"),
        sizing_value=4.0,
    )
    assert result.status == "trade_executed", result.reason
    assert len(fake_trade.calls) == 1
    assert fake_trade.calls[0]["quantity"] == 4.0

