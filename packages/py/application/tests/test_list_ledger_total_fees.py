"""P1-03 — `ListLedgerEntries.total_trade_fees` agrega todo el histórico.

La página (`execute`) devuelve como mucho `limit` entradas; sumar las filas `fee`
de esa página subestima el coste en cuanto la cuenta supera el límite. El
agregado se delega en el repositorio (`total_fees_for_account`), que excluye la
custodia.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.accounts.ledger import ListLedgerEntries


class _LedgerRepo:
    def __init__(self, *, page: list[Any], total: float) -> None:
        self.page = page
        self.total = total
        self.calls: list[tuple[str, int, int]] = []
        self.total_calls: list[str] = []

    async def list_for_account(
        self,
        account_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        portfolio_id: str | None = None,
    ) -> list[Any]:
        self.calls.append((account_id, limit, offset))
        return self.page[:limit]

    async def total_fees_for_account(self, account_id: str) -> float:
        self.total_calls.append(account_id)
        return self.total


@pytest.mark.anyio
async def test_total_trade_fees_comes_from_repository_not_from_the_page() -> None:
    # 150 comisiones en el histórico; la página solo entrega 100.
    page = [{"type": "fee", "amount": -1.0} for _ in range(100)]
    repo = _LedgerRepo(page=page, total=150.0)
    use_case = ListLedgerEntries(repo)  # type: ignore[arg-type]

    entries = await use_case.execute("acc-1", limit=100)
    total = await use_case.total_trade_fees("acc-1")

    assert len(entries) == 100
    assert total == 150.0
    assert repo.total_calls == ["acc-1"]
    assert repo.calls == [("acc-1", 100, 0)]


@pytest.mark.anyio
async def test_total_trade_fees_is_float_even_when_repository_returns_int() -> None:
    repo = _LedgerRepo(page=[], total=0)
    use_case = ListLedgerEntries(repo)  # type: ignore[arg-type]

    total = await use_case.total_trade_fees("acc-1")

    assert total == 0.0
    assert isinstance(total, float)
