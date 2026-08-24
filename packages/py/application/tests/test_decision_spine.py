"""Decision Spine — índice de unicidad SEMI=AUTO (mismo risk, distinta autorización).

DS-01/02/06/09/11 viven en ``test_execute_trade_idempotency.py``.
DS-04 vive en ``test_risk_engine_portfolio_fit.py`` (+ H1 SEMI sector).
DS-08 (este fichero): AUTO + ``check_opening`` DENY → el router **no** llama a ``ExecuteTrade``.

No cubiertos aquí: DS-03 Mandate de cuenta · DS-05 stale · DS-12..15 broker.
Suite: ``pnpm test:decision-spine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from bolsa_analytics.signals.strategy import SignalEventV1
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord

from bolsa_application.execution_router import ExecutionRouter


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

    async def execute(self, account_id: str | None = None, portfolio_id: str | None = None) -> _FakePortfolioSummary:
        return self


class _FakeAccount:
    id = "acc-ds08"
    type = "simulated"
    initial_deposit = 200.0
    active_profile_id = None


class _FakeScope:
    account = _FakeAccount()


class _FakeAccountRepo:
    async def resolve_scope(self, account_id: str, portfolio_id: str | None = None) -> _FakeScope:
        return _FakeScope()

    async def get_settings_json(self, account_id: str) -> dict[str, Any]:
        return {}

    async def merge_settings_json(self, account_id: str, fragment: dict[str, Any]) -> None:
        return None


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


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


def _entry_long_signal() -> SignalEventV1:
    return SignalEventV1(
        id="sig-ds08",
        instrument_id="inst-new",
        timestamp="2026-08-24T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=1.0,
    )


@pytest.mark.asyncio
async def test_ds08_auto_risk_block_does_not_execute_trade() -> None:
    """DS-08 — AUTO: ``check_opening`` DENY (sector) → skipped; cero ``ExecuteTrade``."""
    fake_trade = _FakeExecuteTrade()
    router = ExecutionRouter(
        policy_repo=object(),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=fake_trade,  # type: ignore[arg-type]
        portfolio_summary=_sector_gap_summary(),  # type: ignore[arg-type]
        profile_store=None,
    )

    result = await router._execute_paper_trade(
        _paper_policy(),
        _entry_long_signal(),
        hit={"sector": "tech", "instrumentId": "inst-new"},
        sizing_value=4.0,
    )

    assert result.status == "skipped"
    assert result.reason is not None
    assert result.reason.startswith("Risk Engine:")
    assert "Exposición sector superada" in result.reason
    assert fake_trade.calls == []
