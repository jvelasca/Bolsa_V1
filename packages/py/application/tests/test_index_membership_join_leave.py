"""Join/leave de constitutivos: lista exacta; Instrument permanece en BD."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_application.market_indices import SubscribeMarketIndex, SyncSubscribedCatalogIndices
from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta
from bolsa_infrastructure.database.repositories.list_repository import (
    InstrumentListDetail,
    InstrumentListSummary,
)
from bolsa_market.indices.curated_ibex35 import IBEX35_CURATED


def _meta(iid: str, yahoo: str, symbol: str) -> InstrumentWithMeta:
    return InstrumentWithMeta(
        id=iid,
        symbol=symbol,
        yahoo_symbol=yahoo,
        name=symbol,
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
    )


@pytest.mark.asyncio
async def test_subscribe_reports_join_and_leave_without_deleting_instruments() -> None:
    """Simula: lista tenía un extraviado + faltaba el #0; tras sync → join/leave."""
    id_by_yahoo = {yahoo: f"id-{sym}" for sym, yahoo, _ in IBEX35_CURATED}
    orphan_id = "id-ORPHAN-LEFT-INDEX"
    # Estado previo: todos excepto el primero + un huérfano que ya no es constitutivos
    old_ids = [id_by_yahoo[y] for _, y, _ in IBEX35_CURATED[1:]] + [orphan_id]
    first_yahoo = IBEX35_CURATED[0][1]

    present = set(id_by_yahoo.values())  # todos existen en BD tras "import"

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
            if y in id_by_yahoo
            else None
        ),
    )
    instrument_repo.get_ids_by_yahoo_symbols = AsyncMock(return_value=id_by_yahoo)

    import_uc = MagicMock()
    import_uc.execute = AsyncMock(
        side_effect=lambda **kw: MagicMock(
            instrument=_meta(id_by_yahoo[kw["yahoo_symbol"]], kw["yahoo_symbol"], kw["symbol"]),
        ),
    )

    existing = InstrumentListDetail(
        id="ibex35",
        name="IBEX 35",
        source="catalog",
        instrument_ids=old_ids,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    final_ids = [id_by_yahoo[y] for _, y, _ in IBEX35_CURATED]
    updated = InstrumentListDetail(
        id="ibex35",
        name="IBEX 35",
        source="catalog",
        instrument_ids=final_ids,
        updated_at="2026-07-30T00:00:00+00:00",
    )

    list_repo = MagicMock()
    list_repo.get_by_id = AsyncMock(side_effect=[existing, updated])
    list_repo.list_all = AsyncMock(return_value=[])
    list_repo.replace_catalog_membership = AsyncMock(return_value=updated)
    list_repo.update = AsyncMock()
    list_repo.create = AsyncMock()
    list_repo.mark_universe_sync = AsyncMock(return_value=updated)

    # Solo falta el primero → get_by_yahoo still finds all (simula ya en BD)
    # For join/leave we need old vs new; first is join of id, orphan is leave.
    # Make first "missing" from BD so imported=1
    async def get_by_yahoo(y: str) -> Instrument | None:
        if y == first_yahoo:
            return None
        if y in id_by_yahoo:
            return Instrument(
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
        return None

    instrument_repo.get_by_yahoo_symbol = AsyncMock(side_effect=get_by_yahoo)

    result = await SubscribeMarketIndex(list_repo, instrument_repo, import_uc).execute("IBEX35")

    assert orphan_id in result.progress.left
    assert id_by_yahoo[first_yahoo] in result.progress.joined
    assert result.progress.imported == 1
    list_repo.replace_catalog_membership.assert_awaited_once()
    # Nunca se pide borrar el Instrument huérfano — solo sale de la membresía
    assert orphan_id not in result.instrument_ids
    assert len(result.instrument_ids) == 35


@pytest.mark.asyncio
async def test_sync_subscribed_runs_only_ready_catalog_lists() -> None:
    subscribe = MagicMock()
    subscribe.execute = AsyncMock(
        return_value=MagicMock(index_code="IBEX35", list_id="ibex35"),
    )
    list_repo = MagicMock()
    list_repo.list_all = AsyncMock(
        return_value=[
            InstrumentListSummary(
                id="ibex35",
                name="IBEX 35",
                source="catalog",
                item_count=35,
                updated_at="t",
            ),
            InstrumentListSummary(
                id="idx-spx",
                name="S&P 500",
                source="catalog",
                item_count=0,
                updated_at="t",
            ),
            InstrumentListSummary(
                id="custom1",
                name="Favoritos",
                source="custom",
                item_count=3,
                updated_at="t",
            ),
        ],
    )
    await SyncSubscribedCatalogIndices(subscribe, list_repo).execute()
    # IBEX + SPX listos; custom ignorado
    assert subscribe.execute.await_count == 2
    codes = {call.args[0] for call in subscribe.execute.await_args_list}
    assert codes == {"IBEX35", "SPX"}
