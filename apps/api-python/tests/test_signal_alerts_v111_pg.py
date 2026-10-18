"""v111 — alertas de señal: ownership por cuenta, claim atómico y OUTBOX de entregas (PG, gated).

Cubre los hallazgos 3, 4 y 6 del lote v111 sobre ``signal_alert_subscriptions`` y la tabla
nueva ``alert_deliveries`` (migración 054):

* la tabla ``alert_deliveries`` y las columnas de *claim*/*ownership* están en head;
* ``claim_bar`` es un claim ATÓMICO: una sola barra ⇒ un solo ganador (worker vs. evaluación);
* el lease del claim se cierra con ``finish_bar_claim`` y expira solo (trabajo reclamable);
* ``list``/``get``/``delete``/``reset`` acotan por ``account_id``;
* el OUTBOX transiciona PENDING → DELIVERED | RETRYABLE_FAILED → DEAD_LETTER con reintentos
  diferidos y ``last_bar_timestamp`` deja de ser prueba de «entregado»;
* la unicidad ``(suscripción, barra, canal)`` impide duplicar una entrega.

Requiere PostgreSQL. Es GATE cuando ``SIGNAL_ALERTS_PG_REQUIRED=1``; si no, ``pytest.skip``.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    InstrumentRow,
    SignalAlertSubscriptionRow,
)
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    DELIVERY_DEAD_LETTER,
    DELIVERY_DELIVERED,
    DELIVERY_PENDING,
    DELIVERY_RETRYABLE_FAILED,
    AlertDeliveryRecord,
    SqlAlchemySignalAlertRepository,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED = "SIGNAL_ALERTS_PG_REQUIRED"
_ALEMBIC_HEAD = "056_auto_ops_jobs"
_SUBSCRIPTIONS = "signal_alert_subscriptions"
_DELIVERIES = "alert_deliveries"


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def pg_session() -> AsyncIterator[AsyncSession]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        if os.environ.get(_REQUIRED) == "1":
            raise AssertionError(f"PG required but unavailable: {exc}") from exc
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


async def _seed_subscription(
    session: AsyncSession,
    *,
    account_id: str | None,
    is_active: bool = True,
) -> str:
    """Siembra instrumento + suscripción y devuelve el ``id`` de la suscripción.

    Todo vive en la transacción del test (la fixture hace ``rollback``), así que no deja rastro.
    """
    suffix = uuid.uuid4().hex[:8]
    instrument_id = f"inst-v111-{suffix}"
    now = datetime.now(UTC)
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"V{suffix.upper()}",
            yahoo_symbol=f"V{suffix}.MC",
            name=f"v111 alerts {suffix}",
            exchange="MCE",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    repo = SqlAlchemySignalAlertRepository(session)
    record = await repo.create(
        instrument_id=instrument_id,
        strategy_definition_id=None,
        preset_key=None,
        timeframe="1d",
        channels=["toast", "webhook"],
        account_id=account_id,
    )
    if not is_active:
        await session.execute(
            update(SignalAlertSubscriptionRow)
            .where(SignalAlertSubscriptionRow.id == record.id)
            .values(is_active=False)
        )
        await session.flush()
    return record.id


def _claimed_ids(deliveries: list[AlertDeliveryRecord]) -> set[str]:
    return {delivery.id for delivery in deliveries}


# ── Estructura (migración 054) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_migration_054_is_at_head_and_creates_the_outbox(pg_session: AsyncSession) -> None:
    from bolsa_infrastructure.database.migrations import alembic_head

    assert alembic_head() == _ALEMBIC_HEAD

    columns = {
        row[0]
        for row in (
            await pg_session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=:t"
                ),
                {"t": _SUBSCRIPTIONS},
            )
        ).fetchall()
    }
    assert {
        "account_id",
        "processing_bar_timestamp",
        "processing_token",
        "processing_started_at",
    } <= columns

    delivery_columns = {
        row[0]
        for row in (
            await pg_session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=:t"
                ),
                {"t": _DELIVERIES},
            )
        ).fetchall()
    }
    assert {
        "id",
        "subscription_id",
        "account_id",
        "bar_timestamp",
        "signal_kind",
        "channel",
        "status",
        "attempt",
        "payload",
        "last_error",
        "next_retry_at",
        "claimed_at",
        "delivered_at",
    } <= delivery_columns

    constraints = {
        row[0]
        for row in (
            await pg_session.execute(
                text(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_schema='public' AND table_name=:t AND constraint_type='UNIQUE'"
                ),
                {"t": _DELIVERIES},
            )
        ).fetchall()
    }
    assert "alert_deliveries_subscription_bar_channel_key" in constraints

    indexes = {
        row[0]
        for row in (
            await pg_session.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
            )
        ).fetchall()
    }
    assert {
        "alert_deliveries_account_id_idx",
        "alert_deliveries_status_retry_idx",
        "signal_alert_subscriptions_account_id_idx",
    } <= indexes


# ── Claim atómico de barra ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_bar_has_one_winner_per_bar_and_dedupes(pg_session: AsyncSession) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-claim")

    winner = await repo.claim_bar(
        sub_id,
        account_id="acc-claim",
        bar_timestamp="2026-09-01",
        signal_kind="entry_long",
        signal_price=10.5,
    )
    assert winner is not None and winner.token

    # El perdedor (worker vs. evaluación manual) no recibe fila: misma barra y lease vivo.
    loser = await repo.claim_bar(
        sub_id,
        account_id="acc-claim",
        bar_timestamp="2026-09-01",
        signal_kind="entry_long",
        signal_price=10.5,
    )
    assert loser is None

    # Con el lease VIVO tampoco puede saltar a otra barra (evita doble despacho concurrente).
    assert (
        await repo.claim_bar(
            sub_id,
            account_id="acc-claim",
            bar_timestamp="2026-09-02",
            signal_kind="entry_long",
            signal_price=11.0,
        )
        is None
    )

    await repo.finish_bar_claim(sub_id, winner.token)
    next_bar = await repo.claim_bar(
        sub_id,
        account_id="acc-claim",
        bar_timestamp="2026-09-02",
        signal_kind="entry_long",
        signal_price=11.0,
    )
    assert next_bar is not None
    assert next_bar.subscription.last_bar_timestamp == "2026-09-02"

    # Repetir la barra ya procesada sigue siendo no-op (dedupe por ``IS DISTINCT FROM``).
    await repo.finish_bar_claim(sub_id, next_bar.token)
    assert (
        await repo.claim_bar(
            sub_id,
            account_id="acc-claim",
            bar_timestamp="2026-09-02",
            signal_kind="entry_long",
            signal_price=11.0,
        )
        is None
    )


@pytest.mark.asyncio
async def test_claim_bar_honours_account_scope_and_inactive_flag(pg_session: AsyncSession) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-owner")

    # Otra cuenta no puede reclamar la suscripción ajena.
    assert (
        await repo.claim_bar(
            sub_id,
            account_id="acc-intruso",
            bar_timestamp="2026-09-03",
            signal_kind="exit",
            signal_price=9.0,
        )
        is None
    )

    inactive = await _seed_subscription(pg_session, account_id="acc-owner", is_active=False)
    assert (
        await repo.claim_bar(
            inactive,
            account_id="acc-owner",
            bar_timestamp="2026-09-03",
            signal_kind="exit",
            signal_price=9.0,
        )
        is None
    )


@pytest.mark.asyncio
async def test_expired_lease_is_reclaimable(pg_session: AsyncSession) -> None:
    """Un worker caído a mitad de claim no bloquea la barra para siempre."""
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-lease")

    first = await repo.claim_bar(
        sub_id,
        account_id="acc-lease",
        bar_timestamp="2026-09-04",
        signal_kind="entry_long",
        signal_price=12.0,
        lease_seconds=3600.0,
    )
    assert first is not None
    # El lease se VENCE: se envejece el sello del claim de forma explícita (determinista; no
    # depende de la granularidad del reloj de Windows, que puede repetir el mismo instante).
    await pg_session.execute(
        update(SignalAlertSubscriptionRow)
        .where(SignalAlertSubscriptionRow.id == sub_id)
        .values(processing_started_at=datetime.now(UTC) - timedelta(hours=2))
    )
    await pg_session.flush()
    reclaimed = await repo.claim_bar(
        sub_id,
        account_id="acc-lease",
        bar_timestamp="2026-09-05",
        signal_kind="entry_long",
        signal_price=12.5,
        lease_seconds=3600.0,
    )
    assert reclaimed is not None
    assert reclaimed.token != first.token


@pytest.mark.asyncio
async def test_finish_bar_claim_requires_the_matching_token(pg_session: AsyncSession) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-token")

    claim = await repo.claim_bar(
        sub_id,
        account_id="acc-token",
        bar_timestamp="2026-09-06",
        signal_kind="exit",
        signal_price=8.0,
    )
    assert claim is not None
    # Un token ajeno NO libera el lease del ganador.
    await repo.finish_bar_claim(sub_id, "token-ajeno")
    assert (
        await repo.claim_bar(
            sub_id,
            account_id="acc-token",
            bar_timestamp="2026-09-07",
            signal_kind="exit",
            signal_price=8.5,
        )
        is None
    )
    await repo.finish_bar_claim(sub_id, claim.token)
    assert (
        await repo.claim_bar(
            sub_id,
            account_id="acc-token",
            bar_timestamp="2026-09-07",
            signal_kind="exit",
            signal_price=8.5,
        )
        is not None
    )


# ── Ownership en el CRUD ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_crud_scopes_every_operation_by_account(pg_session: AsyncSession) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    mine = await _seed_subscription(pg_session, account_id="acc-mia")
    other = await _seed_subscription(pg_session, account_id="acc-otra")

    assert await repo.get_by_id(mine, account_id="acc-otra") is None
    assert await repo.get_by_id(mine, account_id="acc-mia") is not None

    visible = {record.id for record in await repo.list_all(account_id="acc-mia")}
    assert mine in visible and other not in visible

    assert await repo.reset_bar_dedupe(other, account_id="acc-mia") is None
    assert await repo.delete(other, account_id="acc-mia") is False
    assert await repo.delete(other, account_id="acc-otra") is True


@pytest.mark.asyncio
async def test_reset_bar_dedupe_clears_the_dedupe_and_the_lease(pg_session: AsyncSession) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-reset")
    assert (
        await repo.claim_bar(
            sub_id,
            account_id="acc-reset",
            bar_timestamp="2026-09-08",
            signal_kind="entry_long",
            signal_price=13.0,
        )
        is not None
    )

    reset = await repo.reset_bar_dedupe(sub_id, account_id="acc-reset")
    assert reset is not None
    assert reset.last_bar_timestamp is None
    # La MISMA barra vuelve a ser reclamable (era el objetivo del reset manual).
    assert (
        await repo.claim_bar(
            sub_id,
            account_id="acc-reset",
            bar_timestamp="2026-09-08",
            signal_kind="entry_long",
            signal_price=13.0,
        )
        is not None
    )


# ── OUTBOX de entregas ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outbox_pending_is_claimed_once_and_then_delivered(
    pg_session: AsyncSession,
) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-outbox")

    pending = await repo.enqueue_delivery(
        subscription_id=sub_id,
        account_id="acc-outbox",
        bar_timestamp="2026-09-09",
        signal_kind="entry_long",
        channel="webhook",
        payload={"url": "https://hooks.example.com/x"},
    )
    assert pending.status == DELIVERY_PENDING and pending.attempt == 0

    claimed = await repo.claim_due_deliveries(limit=500, lease_seconds=60.0, max_attempts=3)
    assert pending.id in _claimed_ids(claimed)

    # Reclamar de nuevo en el acto: sigue el lease ⇒ no vuelve a salir (no hay doble envío).
    again = await repo.claim_due_deliveries(limit=500, lease_seconds=60.0, max_attempts=3)
    assert pending.id not in _claimed_ids(again)

    delivered = await repo.mark_delivery_delivered(pending.id)
    assert delivered is not None
    assert delivered.status == DELIVERY_DELIVERED and delivered.attempt == 1
    assert delivered.next_retry_at is None

    terminal = await repo.claim_due_deliveries(limit=500, lease_seconds=60.0, max_attempts=3)
    assert pending.id not in _claimed_ids(terminal)


@pytest.mark.asyncio
async def test_outbox_retry_backoff_defers_and_then_releases(pg_session: AsyncSession) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-retry")

    delivery = await repo.enqueue_delivery(
        subscription_id=sub_id,
        account_id="acc-retry",
        bar_timestamp="2026-09-10",
        signal_kind="exit",
        channel="email",
        payload=None,
    )

    deferred = await repo.mark_delivery_failed(
        delivery.id,
        error="boom smtp",
        next_retry_at=datetime.now(UTC) + timedelta(hours=1),
        dead_letter=False,
    )
    assert deferred is not None
    assert deferred.status == DELIVERY_RETRYABLE_FAILED
    assert deferred.attempt == 1 and deferred.last_error == "boom smtp"
    now_claimed = await repo.claim_due_deliveries(limit=500, lease_seconds=60.0, max_attempts=3)
    assert delivery.id not in _claimed_ids(now_claimed)

    # Vencido el backoff, la entrega vuelve a ser reclamable (reintento REAL, no silencioso).
    ready = await repo.mark_delivery_failed(
        delivery.id,
        error="boom smtp",
        next_retry_at=datetime.now(UTC) - timedelta(seconds=1),
        dead_letter=False,
    )
    assert ready is not None and ready.attempt == 2
    released = await repo.claim_due_deliveries(limit=500, lease_seconds=60.0, max_attempts=5)
    assert delivery.id in _claimed_ids(released)


@pytest.mark.asyncio
async def test_outbox_dead_letter_is_terminal_and_truncates_the_error(
    pg_session: AsyncSession,
) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-dlq")

    delivery = await repo.enqueue_delivery(
        subscription_id=sub_id,
        account_id="acc-dlq",
        bar_timestamp="2026-09-11",
        signal_kind="entry_long",
        channel="webhook",
        payload=None,
    )
    dead = await repo.mark_delivery_failed(
        delivery.id,
        error="x" * 900,
        next_retry_at=None,
        dead_letter=True,
    )
    assert dead is not None
    assert dead.status == DELIVERY_DEAD_LETTER
    assert dead.next_retry_at is None
    assert dead.last_error is not None and len(dead.last_error) == 500

    assert delivery.id not in _claimed_ids(
        await repo.claim_due_deliveries(limit=500, lease_seconds=60.0, max_attempts=9)
    )


@pytest.mark.asyncio
async def test_expire_exhausted_deliveries_moves_them_to_dead_letter(
    pg_session: AsyncSession,
) -> None:
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-expire")

    delivery = await repo.enqueue_delivery(
        subscription_id=sub_id,
        account_id="acc-expire",
        bar_timestamp="2026-09-12",
        signal_kind="exit",
        channel="toast",
        payload=None,
    )
    for _ in range(3):
        await repo.mark_delivery_failed(
            delivery.id,
            error="sigue fallando",
            next_retry_at=datetime.now(UTC) - timedelta(seconds=1),
            dead_letter=False,
        )

    moved = await repo.expire_exhausted_deliveries(max_attempts=3)
    assert moved >= 1
    rows = await repo.list_deliveries(subscription_id=sub_id)
    assert [row.status for row in rows] == [DELIVERY_DEAD_LETTER]
    assert delivery.id not in _claimed_ids(
        await repo.claim_due_deliveries(limit=500, lease_seconds=60.0, max_attempts=3)
    )


@pytest.mark.asyncio
async def test_enqueue_delivery_rejects_a_duplicate_bar_and_channel(
    pg_session: AsyncSession,
) -> None:
    """La unicidad ``(suscripción, barra, canal)`` impide DUPLICAR la entrega de una barra."""
    repo = SqlAlchemySignalAlertRepository(pg_session)
    sub_id = await _seed_subscription(pg_session, account_id="acc-unique")

    kwargs = {
        "subscription_id": sub_id,
        "account_id": "acc-unique",
        "bar_timestamp": "2026-09-13",
        "signal_kind": "entry_long",
        "channel": "webhook",
        "payload": None,
    }
    await repo.enqueue_delivery(**kwargs)
    # El mismo ``(barra)`` por OTRO canal SÍ es una entrega distinta.
    other_channel = await repo.enqueue_delivery(**dict(kwargs, channel="email"))
    assert other_channel.channel == "email"

    # Duplicar el mismo ``(suscripción, barra, canal)`` NO se absorbe: falla (última aserción,
    # porque el ``IntegrityError`` aborta la transacción del test).
    with pytest.raises(IntegrityError):
        await repo.enqueue_delivery(**kwargs)
