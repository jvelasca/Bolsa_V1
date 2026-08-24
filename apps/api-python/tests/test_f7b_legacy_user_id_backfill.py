"""R12-AUTH F7b: backfill one-shot de ``investment_accounts.user_id`` legacy NULL."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.main import create_app, lifespan
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import InvestmentAccountRow

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKFILL_SCRIPT = _REPO_ROOT / "scripts" / "verify" / "backfill_legacy_account_user_id.py"
_OWNED_USER_ID = "f7b-already-owned"


def _now() -> datetime:
    return datetime.now(UTC)


def _load_backfill_module() -> ModuleType:
    name = "backfill_legacy_account_user_id"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, _BACKFILL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def _insert_raw_account(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str | None,
    name: str,
) -> str:
    account_id = f"f7b-{uuid4().hex[:16]}"
    async with factory() as session:
        session.add(
            InvestmentAccountRow(
                id=account_id,
                user_id=user_id,
                name=name,
                type="simulated",
                status="active",
                currency="EUR",
                base_currency="EUR",
                initial_deposit=Decimal("1000"),
                leverage=Decimal("1"),
                is_default=False,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.commit()
    return account_id


async def _delete_raw_account(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(InvestmentAccountRow, account_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


async def _read_user_id(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
) -> str | None:
    async with factory() as session:
        row = await session.get(InvestmentAccountRow, account_id)
        assert row is not None
        return row.user_id


@pytest.mark.asyncio
async def test_f7b_dry_run_does_not_mutate_null_or_owned_rows() -> None:
    """(a) dry-run cuenta/lista y no muta 2 filas NULL + 1 ya owned."""
    backfill = _load_backfill_module()
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        null_a = await _insert_raw_account(
            factory, user_id=None, name="F7b dry-run null A"
        )
        null_b = await _insert_raw_account(
            factory, user_id=None, name="F7b dry-run null B"
        )
        owned = await _insert_raw_account(
            factory, user_id=_OWNED_USER_ID, name="F7b dry-run owned"
        )
        try:
            async with factory() as session:
                listed = await backfill.list_legacy_null_account_ids(session)
            assert null_a in listed
            assert null_b in listed
            assert owned not in listed

            assert await _read_user_id(factory, null_a) is None
            assert await _read_user_id(factory, null_b) is None
            assert await _read_user_id(factory, owned) == _OWNED_USER_ID
        finally:
            await _delete_raw_account(factory, null_a)
            await _delete_raw_account(factory, null_b)
            await _delete_raw_account(factory, owned)


@pytest.mark.asyncio
async def test_f7b_apply_stamps_bootstrap_only_on_null_rows() -> None:
    """(b) --apply asigna bootstrap SOLO a NULL y deja owned intacto."""
    backfill = _load_backfill_module()
    bootstrap = get_settings().owner_principal()
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        null_a = await _insert_raw_account(
            factory, user_id=None, name="F7b apply null A"
        )
        null_b = await _insert_raw_account(
            factory, user_id=None, name="F7b apply null B"
        )
        owned = await _insert_raw_account(
            factory, user_id=_OWNED_USER_ID, name="F7b apply owned"
        )
        scoped = (null_a, null_b, owned)
        try:
            async with factory() as session:
                updated = await backfill.apply_legacy_account_user_id_backfill(
                    session,
                    bootstrap=bootstrap,
                    restrict_to_ids=scoped,
                )
                await session.commit()
            assert updated == 2
            assert await _read_user_id(factory, null_a) == bootstrap
            assert await _read_user_id(factory, null_b) == bootstrap
            assert await _read_user_id(factory, owned) == _OWNED_USER_ID
        finally:
            await _delete_raw_account(factory, null_a)
            await _delete_raw_account(factory, null_b)
            await _delete_raw_account(factory, owned)


@pytest.mark.asyncio
async def test_f7b_apply_second_pass_is_noop() -> None:
    """(c) apply 2ª vez es no-op (0 filas)."""
    backfill = _load_backfill_module()
    bootstrap = get_settings().owner_principal()
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        null_a = await _insert_raw_account(
            factory, user_id=None, name="F7b noop null A"
        )
        null_b = await _insert_raw_account(
            factory, user_id=None, name="F7b noop null B"
        )
        owned = await _insert_raw_account(
            factory, user_id=_OWNED_USER_ID, name="F7b noop owned"
        )
        scoped = (null_a, null_b, owned)
        try:
            async with factory() as session:
                first = await backfill.apply_legacy_account_user_id_backfill(
                    session,
                    bootstrap=bootstrap,
                    restrict_to_ids=scoped,
                )
                await session.commit()
            assert first == 2

            async with factory() as session:
                second = await backfill.apply_legacy_account_user_id_backfill(
                    session,
                    bootstrap=bootstrap,
                    restrict_to_ids=scoped,
                )
                await session.commit()
            assert second == 0
            assert await _read_user_id(factory, null_a) == bootstrap
            assert await _read_user_id(factory, null_b) == bootstrap
            assert await _read_user_id(factory, owned) == _OWNED_USER_ID
        finally:
            await _delete_raw_account(factory, null_a)
            await _delete_raw_account(factory, null_b)
            await _delete_raw_account(factory, owned)
