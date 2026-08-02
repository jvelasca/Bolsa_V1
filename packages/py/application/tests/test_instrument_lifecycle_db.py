"""Tests del ciclo de vida listas ↔ BD (purge seguro)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from bolsa_application.instrument_lifecycle import GetInstrumentRemovalPreview
from bolsa_application.remove_list_instrument import (
    DeleteInstrument,
    ListOrphanInstruments,
    RemoveInstrumentFromList,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_env() -> None:
    env_path = _repo_root() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


@pytest_asyncio.fixture
async def db_session():
    """Sesión real PostgreSQL; se omite si no hay BD."""
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"PostgreSQL no disponible: {exc}")

    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


@pytest.mark.asyncio
async def test_purge_with_sync_logs_does_not_nullify(db_session) -> None:
    """Regresión META: borrar instrumento con data_sync_log no debe UPDATE null."""
    from bolsa_infrastructure.database.models import (
        DataSyncLogRow,
        InstrumentListItemRow,
        InstrumentListRow,
        InstrumentRow,
        OhlcvBarRow,
        PriceAlertRow,
    )

    now = datetime.now(UTC)
    instrument_id = _new_id("inst")
    list_id = _new_id("list")
    yahoo = f"TESTPURGE.{uuid.uuid4().hex[:8]}"

    db_session.add(
        InstrumentRow(
            id=instrument_id,
            symbol="TPURGE",
            yahoo_symbol=yahoo,
            name="Purge Test Co",
            exchange="NASDAQ",
            country="US",
            currency="USD",
            sector=None,
            type="stock",
            is_active=True,
            profile_snapshot=None,
            last_xtb_validation=None,
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        DataSyncLogRow(
            id=_new_id("slog"),
            instrument_id=instrument_id,
            provider="yahoo",
            status="success",
            bars_added=10,
            error=None,
            synced_at=now,
        ),
    )
    db_session.add(
        OhlcvBarRow(
            id=_new_id("bar"),
            instrument_id=instrument_id,
            timeframe="1d",
            timestamp=now,
            open=Decimal(1),
            high=Decimal(2),
            low=Decimal("0.5"),
            close=Decimal("1.5"),
            volume=1000,
            adj_close=None,
            source="yahoo",
            created_at=now,
        ),
    )
    db_session.add(
        PriceAlertRow(
            id=_new_id("alert"),
            instrument_id=instrument_id,
            symbol="TPURGE",
            condition="above",
            price_source="daily_close",
            target_price=Decimal(10),
            is_active=True,
            triggered_at=None,
            triggered_price=None,
            note="test",
            created_at=now,
        ),
    )
    db_session.add(
        InstrumentListRow(
            id=list_id,
            name=f"purge-test-{uuid.uuid4().hex[:6]}",
            source="custom",
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        InstrumentListItemRow(
            id=_new_id("item"),
            list_id=list_id,
            instrument_id=instrument_id,
            sort_order=0,
        ),
    )
    await db_session.flush()

    preview = await GetInstrumentRemovalPreview(db_session).execute(
        instrument_id,
        excluding_list_id=list_id,
    )
    assert preview is not None
    assert preview.would_be_orphan
    assert preview.can_purge
    assert preview.ohlcv_bar_count >= 1
    assert preview.price_alerts_total >= 1

    result = await RemoveInstrumentFromList(db_session).execute(
        list_id,
        instrument_id,
        purge_if_orphan=True,
    )
    assert result.removed_from_list
    assert result.purged
    assert result.became_orphan is False

    inst = await db_session.get(InstrumentRow, instrument_id)
    assert inst is None

    logs = await db_session.execute(
        select(func.count()).select_from(DataSyncLogRow).where(
            DataSyncLogRow.instrument_id == instrument_id,
        ),
    )
    assert int(logs.scalar_one()) == 0

    bars = await db_session.execute(
        select(func.count()).select_from(OhlcvBarRow).where(
            OhlcvBarRow.instrument_id == instrument_id,
        ),
    )
    assert int(bars.scalar_one()) == 0

    alerts = await db_session.execute(
        select(func.count()).select_from(PriceAlertRow).where(
            PriceAlertRow.instrument_id == instrument_id,
        ),
    )
    assert int(alerts.scalar_one()) == 0

    # limpiar lista vacía de prueba
    lst = await db_session.get(InstrumentListRow, list_id)
    if lst is not None:
        await db_session.delete(lst)
        await db_session.flush()


@pytest.mark.asyncio
async def test_remove_without_purge_keeps_instrument(db_session) -> None:
    from bolsa_infrastructure.database.models import (
        InstrumentListItemRow,
        InstrumentListRow,
        InstrumentRow,
    )

    now = datetime.now(UTC)
    instrument_id = _new_id("inst")
    list_id = _new_id("list")
    yahoo = f"TESTKEEP.{uuid.uuid4().hex[:8]}"

    db_session.add(
        InstrumentRow(
            id=instrument_id,
            symbol="TKEEP",
            yahoo_symbol=yahoo,
            name="Keep Test Co",
            exchange="NASDAQ",
            country="US",
            currency="USD",
            sector=None,
            type="stock",
            is_active=True,
            profile_snapshot=None,
            last_xtb_validation=None,
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        InstrumentListRow(
            id=list_id,
            name=f"keep-test-{uuid.uuid4().hex[:6]}",
            source="custom",
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        InstrumentListItemRow(
            id=_new_id("item"),
            list_id=list_id,
            instrument_id=instrument_id,
            sort_order=0,
        ),
    )
    await db_session.flush()

    result = await RemoveInstrumentFromList(db_session).execute(
        list_id,
        instrument_id,
        purge_if_orphan=False,
    )
    assert result.removed_from_list
    assert not result.purged
    assert result.became_orphan

    inst = await db_session.get(InstrumentRow, instrument_id)
    assert inst is not None

    orphans = await ListOrphanInstruments(db_session).execute(limit=500)
    assert any(o.id == instrument_id for o in orphans.orphans)

    await DeleteInstrument(db_session).execute(instrument_id)
    assert await db_session.get(InstrumentRow, instrument_id) is None

    lst = await db_session.get(InstrumentListRow, list_id)
    if lst is not None:
        await db_session.delete(lst)
        await db_session.flush()


@pytest.mark.asyncio
async def test_delete_blocked_while_still_in_list(db_session) -> None:
    from bolsa_infrastructure.database.models import (
        InstrumentListItemRow,
        InstrumentListRow,
        InstrumentRow,
    )

    now = datetime.now(UTC)
    instrument_id = _new_id("inst")
    list_id = _new_id("list")
    yahoo = f"TESTBLOCK.{uuid.uuid4().hex[:8]}"

    db_session.add(
        InstrumentRow(
            id=instrument_id,
            symbol="TBLOCK",
            yahoo_symbol=yahoo,
            name="Block Test",
            exchange="NASDAQ",
            country="US",
            currency="USD",
            sector=None,
            type="stock",
            is_active=True,
            profile_snapshot=None,
            last_xtb_validation=None,
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        InstrumentListRow(
            id=list_id,
            name=f"block-test-{uuid.uuid4().hex[:6]}",
            source="custom",
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        InstrumentListItemRow(
            id=_new_id("item"),
            list_id=list_id,
            instrument_id=instrument_id,
            sort_order=0,
        ),
    )
    await db_session.flush()

    with pytest.raises(ValueError, match="listas"):
        await DeleteInstrument(db_session).execute(instrument_id)

    # cleanup
    await RemoveInstrumentFromList(db_session).execute(
        list_id,
        instrument_id,
        purge_if_orphan=True,
    )
    lst = await db_session.get(InstrumentListRow, list_id)
    if lst is not None:
        await db_session.delete(lst)
        await db_session.flush()


def test_delete_instrument_uses_sql_delete_not_orm_delete() -> None:
    """Guardrail estático: el purge no debe usar session.delete(row)."""
    import inspect

    import bolsa_application.remove_list_instrument as mod

    src = inspect.getsource(mod.DeleteInstrument.execute)
    assert "session.delete" not in src
    assert "delete(InstrumentRow)" in src or "delete(InstrumentRow)" in inspect.getsource(mod)
