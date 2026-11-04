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


async def _refresh(accounts, key):
    stub = SimpleNamespace(_accounts=accounts)
    return await ExecutionRouter._refresh_equity_marks(stub, key, 100_000.0, 100_000.0)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _clean_book():
    GLOBAL_EQUITY_MARK_BOOK.reset()
    yield
    GLOBAL_EQUITY_MARK_BOOK.reset()


@pytest.mark.asyncio
async def test_hydrate_failure_without_marks_requests_veto() -> None:
    _dds, unavailable = await _refresh(_Accounts(fail_get=True), "acc-p3-a")
    assert unavailable is True


@pytest.mark.asyncio
async def test_hydrate_failure_with_marks_in_memory_keeps_going() -> None:
    await _refresh(_Accounts(), "acc-p3-b")
    _dds, unavailable = await _refresh(_Accounts(fail_get=True), "acc-p3-b")
    assert unavailable is False


@pytest.mark.asyncio
async def test_healthy_path_persists_and_is_available() -> None:
    accounts = _Accounts()
    _dds, unavailable = await _refresh(accounts, "acc-p3-c")
    assert unavailable is False
    assert accounts.merged and "equityMarks" in accounts.merged[0]


@pytest.mark.asyncio
async def test_persist_failure_does_not_raise_nor_veto() -> None:
    _dds, unavailable = await _refresh(_Accounts(fail_merge=True), "acc-p3-d")
    assert unavailable is False
