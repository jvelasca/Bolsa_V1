"""SubscribeMarketIndex — hidrata constitutivos y materializa lista catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_application.market_indices import SubscribeMarketIndex
from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta
from bolsa_infrastructure.database.repositories.list_repository import InstrumentListDetail
from bolsa_market.indices.curated_ibex35 import IBEX35_CURATED


@dataclass
class _FakeImportResult:
    instrument: Any
    created: bool = True
    sync: Any = None


@pytest.mark.asyncio
async def test_subscribe_ibex_imports_missing_and_builds_list() -> None:
    # Solo 2 símbolos “ya en BD”; el resto se importan.
    present = {IBEX35_CURATED[0][1], IBEX35_CURATED[1][1]}
    id_by_yahoo = {yahoo: f"id-{sym}" for sym, yahoo, _ in IBEX35_CURATED}

    instrument_repo = MagicMock()
    instrument_repo.get_by_yahoo_symbol = AsyncMock(
        side_effect=lambda y: (
            Instrument(
                id=id_by_yahoo[y],
                symbol=y.split(".")[0],
                yahoo_symbol=y,
                name=y,
                exchange="BME",
                country="ES",
                currency="EUR",
                sector=None,
                isin=None,
                is_active=True,
            )
            if y in present
            else None
        ),
    )
    instrument_repo.get_ids_by_yahoo_symbols = AsyncMock(return_value=id_by_yahoo)

    async def import_exec(**kwargs: Any) -> _FakeImportResult:
        yahoo = kwargs["yahoo_symbol"]
        return _FakeImportResult(
            instrument=InstrumentWithMeta(
                id=id_by_yahoo[yahoo],
                symbol=kwargs["symbol"],
                yahoo_symbol=yahoo,
                name=kwargs["name"],
                exchange="BME",
                country="ES",
                currency="EUR",
                sector=None,
                isin=None,
                is_active=True,
                bar_count=0,
                last_sync=None,
                last_close=None,
                change_pct=None,
            ),
        )

    import_uc = MagicMock()
    import_uc.execute = AsyncMock(side_effect=import_exec)

    created_detail = InstrumentListDetail(
        id="ibex35",
        name="IBEX 35",
        source="catalog",
        instrument_ids=[id_by_yahoo[y] for _, y, _ in IBEX35_CURATED],
        updated_at="2026-07-30T00:00:00+00:00",
    )
    list_repo = MagicMock()
    list_repo.get_by_id = AsyncMock(side_effect=[None, created_detail, created_detail])
    list_repo.list_all = AsyncMock(return_value=[])
    list_repo.create = AsyncMock(return_value=created_detail)
    list_repo.replace_catalog_membership = AsyncMock()
    list_repo.update = AsyncMock()

    result = await SubscribeMarketIndex(list_repo, instrument_repo, import_uc).execute("IBEX35")

    assert result.list_id == "ibex35"
    assert result.progress.total == 35
    assert result.progress.already_present == 2
    assert result.progress.imported == 33
    assert result.status == "ready"
    assert import_uc.execute.await_count == 33
    list_repo.create.assert_awaited_once()
    assert list_repo.create.await_args.kwargs["list_id"] == "ibex35"
    assert len(list_repo.create.await_args.kwargs["instrument_ids"]) == 35


@pytest.mark.asyncio
async def test_subscribe_unknown_pending_index_rejected() -> None:
    use_case = SubscribeMarketIndex(MagicMock(), MagicMock(), MagicMock())
    with pytest.raises(ValueError, match="Constituents no disponibles"):
        await use_case.execute("^UNKNOWNINDEXXYZ")
