"""P3 — el circuit breaker de drawdown no traga fallos de hidratación/persistencia de marcas."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bolsa_application.account_drawdown import GLOBAL_EQUITY_MARK_BOOK
from bolsa_application.execution_router import ExecutionRouter


class _Accounts:
    def __init__(self, *, fail_get=False, fail_merge=False, settings=None) -> None:
        self.fail_get = fail_get
        self.fail_merge = fail_merge
        self.settings = settings
        self.merged: list[dict] = []

    async def get_settings_json(self, _key):
        if self.fail_get:
            raise RuntimeError("db down")
        return self.settings

    async def merge_settings_json(self, _key, fragment):
        if self.fail_merge:
            raise RuntimeError("db down")
        self.merged.append(fragment)


async def _refresh(accounts, key, equity: float = 100_000.0):
    stub = SimpleNamespace(_accounts=accounts)
    return await ExecutionRouter._refresh_equity_marks(
        stub,  # type: ignore[arg-type]
        key,
        equity,
        100_000.0,
    )


@pytest.fixture(autouse=True)
def _clean_book():
    GLOBAL_EQUITY_MARK_BOOK.reset()
    yield
    GLOBAL_EQUITY_MARK_BOOK.reset()


@pytest.mark.asyncio
async def test_hydrate_failure_without_marks_requests_veto() -> None:
    _dds, denial = await _refresh(_Accounts(fail_get=True), "acc-p3-a")
    assert denial == "drawdown_marks:unavailable"


@pytest.mark.asyncio
async def test_hydrate_failure_with_marks_in_memory_keeps_going() -> None:
    await _refresh(_Accounts(), "acc-p3-b")
    _dds, denial = await _refresh(_Accounts(fail_get=True), "acc-p3-b")
    assert denial is None


@pytest.mark.asyncio
async def test_healthy_path_persists_and_is_available() -> None:
    accounts = _Accounts()
    _dds, denial = await _refresh(accounts, "acc-p3-c")
    assert denial is None
    assert accounts.merged and "equityMarks" in accounts.merged[0]


@pytest.mark.asyncio
async def test_persist_failure_requests_veto() -> None:
    """Una marca no durable no autoriza aperturas: un crash la convertiría en 0 %."""
    _dds, denial = await _refresh(_Accounts(fail_merge=True), "acc-p3-d")
    assert denial == "drawdown_marks:not_persisted"


@pytest.mark.asyncio
async def test_persist_failure_keeps_marks_in_memory_and_recovers() -> None:
    """El fallo no revierte el libro: la siguiente evaluación persiste y deja de vetar."""
    key = "acc-p3-e"
    _dds, denial = await _refresh(_Accounts(fail_merge=True), key)
    assert denial == "drawdown_marks:not_persisted"
    assert GLOBAL_EQUITY_MARK_BOOK.has_marks(key)

    accounts = _Accounts()
    dds, denial = await _refresh(accounts, key)
    assert denial is None
    assert accounts.merged and dds.daily_pct == 0.0


@pytest.mark.asyncio
async def test_unavailable_takes_precedence_over_not_persisted() -> None:
    _dds, denial = await _refresh(
        _Accounts(fail_get=True, fail_merge=True), "acc-p3-f"
    )
    assert denial == "drawdown_marks:unavailable"


@pytest.mark.asyncio
async def test_non_finite_equity_is_unmeasured_not_zero() -> None:
    _dds, denial = await _refresh(_Accounts(), "acc-p3-g", equity=float("nan"))
    assert denial is None
    assert _dds.daily_pct is None
    assert _dds.weekly_pct is None
    assert _dds.max_pct is None
