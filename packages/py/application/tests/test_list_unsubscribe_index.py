"""Desuscribir índices catalog + no auto-recrear IBEX en GET /lists."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_application.lists import DeleteInstrumentList, ListInstrumentLists


@pytest.mark.asyncio
async def test_delete_allows_catalog_unsubscribe() -> None:
    repo = MagicMock()
    repo.delete = AsyncMock(return_value=True)
    await DeleteInstrumentList(repo).execute("ibex35")
    repo.delete.assert_awaited_once_with("ibex35")


@pytest.mark.asyncio
async def test_list_lists_syncs_ibex_only_if_present() -> None:
    repo = MagicMock()
    repo.sync_ibex_catalog_list_if_present = AsyncMock(return_value=None)
    repo.list_all = AsyncMock(return_value=[])
    repo.ensure_estudio_list = AsyncMock()
    repo.ensure_ibex_catalog_list = AsyncMock()
    await ListInstrumentLists(repo).execute()
    repo.sync_ibex_catalog_list_if_present.assert_awaited_once()
    repo.ensure_estudio_list.assert_awaited_once()
    repo.ensure_ibex_catalog_list.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_lists_uses_sync_indices_when_provided() -> None:
    repo = MagicMock()
    repo.list_all = AsyncMock(return_value=[])
    repo.sync_ibex_catalog_list_if_present = AsyncMock()
    repo.ensure_estudio_list = AsyncMock()
    sync = MagicMock()
    sync.execute = AsyncMock(return_value=[])
    await ListInstrumentLists(repo, sync_indices=sync).execute()
    sync.execute.assert_awaited_once()
    repo.sync_ibex_catalog_list_if_present.assert_not_awaited()
    repo.ensure_estudio_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_ibex_if_present_skips_when_missing() -> None:
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    session = MagicMock()
    repo = SqlAlchemyListRepository(session)
    repo.get_by_id = AsyncMock(return_value=None)
    # simulate empty name lookup
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=exec_result)

    out = await repo.sync_ibex_catalog_list_if_present()
    assert out is None
