"""V2.12 — LiveOrderStore contract (InMemory + PG mapping stub, sin DB).

Verifica el mapeo 1:1 dominio↔fila física de ``PostgresLiveOrderStore``
(account_id incluida tras la faena XL-3 durable) y la semántica fail-closed de
``list_unknown``/integro, con sesión AsyncMock (patrón test_submit_intent_store_pg).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from bolsa_analytics.cognitive.live_order import (
    LiveOrder,
    build_live_order,
    can_transition_live_order,
    transition_live_order,
)
from bolsa_application.live_order_store import (
    InMemoryLiveOrderStore,
    PostgresLiveOrderStore,
)


def _make_order(*, order_id: str = "lo-1", account_id: str = "acc-1") -> LiveOrder:
    order = build_live_order(
        order_id=order_id,
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
        account_id=account_id,
    )
    return transition_live_order(
        transition_live_order(order, "SUBMITTING"),
        "SUBMITTED",
        venue_order_id="xtb-1",
    )


def _row_from(order: LiveOrder) -> MagicMock:
    row = MagicMock()
    row.order_id = order.order_id
    row.account_id = order.account_id
    row.status = order.status
    row.venue = order.venue
    row.instrument_id = order.instrument_id
    row.side = order.side
    row.quantity = order.quantity
    row.filled_quantity = order.filled_quantity
    row.remaining_quantity = order.remaining_quantity
    row.venue_order_id = order.venue_order_id
    row.intent_id = order.intent_id
    row.financial_apply_count = order.financial_apply_count
    return row


@pytest.mark.asyncio
async def test_inmemory_put_get_delete_roundtrip() -> None:
    store = InMemoryLiveOrderStore()
    order = _make_order(order_id="lo-im", account_id="acc-1")
    await store.put(order)
    got = await store.get("lo-im")
    assert got is not None
    assert got.status == "SUBMITTED"
    assert got.venue_order_id == "xtb-1"
    assert got.account_id == "acc-1"
    await store.delete("lo-im")
    assert await store.get("lo-im") is None


@pytest.mark.asyncio
async def test_inmemory_list_unknown_filters_only_unknown() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-sub", account_id="acc-1"))
    unknown = _make_order(order_id="lo-unk", account_id="acc-1")
    await store.put(transition_live_order(unknown, "UNKNOWN"))
    await store.put(_make_order(order_id="lo-other", account_id="acc-2"))

    rows = await store.list_unknown(limit=50)
    assert [r.order_id for r in rows] == ["lo-unk"]


@pytest.mark.asyncio
async def test_inmemory_claim_unknown_mutually_excludes_workers() -> None:
    """Claim garantiza exclusión: un UNKNOWN claim fresco por worker A no lo ve B.

    Reclama exactamente una vez (mismo contrato que el row-lock SKIP LOCKED PG).
    """
    store = InMemoryLiveOrderStore()
    await store.put(_to_unknown(_make_order(order_id="lo-cw", account_id="acc-1")))

    a = await store.claim_unknown_batch(worker_id="worker-a", limit=10)
    assert [o.order_id for o in a] == ["lo-cw"]

    # Segundo worker (mismo store, worker distinto) NO puede reclamar en fresco.
    b = await store.claim_unknown_batch(worker_id="worker-b", limit=10)
    assert b == []

    # Tras liberar el lease, otro worker puede reclamar.
    await store.release_claim("lo-cw")
    c = await store.claim_unknown_batch(worker_id="worker-b", limit=10)
    assert [o.order_id for o in c] == ["lo-cw"]


@pytest.mark.asyncio
async def test_inmemory_claim_stale_allows_reclaim() -> None:
    """Un claim stale (worker colgado/crash) puede ser reapropiado por otro."""
    from datetime import UTC, datetime, timedelta

    store = InMemoryLiveOrderStore()
    await store.put(_to_unknown(_make_order(order_id="lo-st", account_id="acc-1")))

    # Worker A reclama y su lease queda marcado.
    await store.claim_unknown_batch(worker_id="worker-a", limit=10)
    # Simular que pasó más que la ventana stale: mover claimed_at al pasado.
    now = datetime.now(UTC)
    store._claims["lo-st"] = ("worker-a", now - timedelta(seconds=1000))

    # Worker B puede reclamar el lease stale.
    b = await store.claim_unknown_batch(worker_id="worker-b", limit=10)
    assert [o.order_id for o in b] == ["lo-st"]


@pytest.mark.asyncio
async def test_postgres_put_fresh_insert_maps_domain_to_row_and_commits() -> None:
    """put() es un upsert atómico único (sin get→decide→write ni session.add)."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())

    order = _make_order(order_id="lo-pg", account_id="acc-9")
    store = PostgresLiveOrderStore(session)
    await store.put(order)

    session.commit.assert_awaited()
    # Un solo execute para el upsert (no hay get() previo ni add()).
    session.execute.assert_awaited_once()

    stmt = session.execute.await_args.args[0]
    rendered = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    assert "LO-PG" in rendered
    assert "100.0" in rendered  # quantity
    assert "ACCOUNT_ID" in rendered
    assert "STATUS" in rendered
    # Es un ON CONFLICT DO UPDATE sobre el PK, no un plain INSERT/UPDATE aparte.
    assert "ON CONFLICT" in rendered
    assert "DO UPDATE" in rendered


@pytest.mark.asyncio
async def test_postgres_get_maps_row_to_domain_with_account() -> None:
    session = AsyncMock()
    target = _make_order(order_id="lo-get", account_id="acc-3")
    row = _row_from(target)
    found = MagicMock()
    found.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=found)

    store = PostgresLiveOrderStore(session)
    got = await store.get("lo-get")
    assert got is not None
    assert got.order_id == "lo-get"
    assert got.status == "SUBMITTED"
    assert got.account_id == "acc-3"
    assert got.venue_order_id == "xtb-1"


@pytest.mark.asyncio
async def test_postgres_put_conflict_updates_existing_and_commits() -> None:
    """El mismo order_id (fila ya presente) se actualiza atómicamente.

    No requiere pre-read ni add: un único upsert ON CONFLICT DO UPDATE persiste
    la nueva snapshot de la máquina (cambio de estado durable sin carrera).
    """
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())

    store = PostgresLiveOrderStore(session)
    advanced = transition_live_order(_make_order(order_id="lo-up", account_id="acc-4"), "UNKNOWN")
    await store.put(advanced, account_id="acc-4")

    session.commit.assert_awaited()
    session.execute.assert_awaited_once()

    stmt = session.execute.await_args.args[0]
    rendered = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    assert "UNKNOWN" in rendered  # estado avanzado quemado en el upsert
    assert "ACC-4" in rendered
    assert "ON CONFLICT" in rendered


@pytest.mark.asyncio
async def test_postgres_put_integrity_error_rolls_back() -> None:
    """IntegrityError (reserva/otra restricción) → rollback + re-raise."""
    session = AsyncMock()
    session.commit = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("dup")))
    session.rollback = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())

    store = PostgresLiveOrderStore(session)
    with pytest.raises(IntegrityError):
        await store.put(_make_order(order_id="lo-dup", account_id="acc-1"))
    session.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_postgres_put_same_id_is_atomic_upsert_no_toutcou() -> None:
    """Dos put() cross-PID para el mismo order_id nunca chocan en un INSERT.

    Antes, el patrón get()→decide→write permitía que dos procesos vieran "no
    existe" y pelearan por un INSERT del mismo PK (IntegrityError + pérdida de la
    última escritura). El upsert atómico sobre el PK serializa la escritura:
    PUT N+1 = DO UPDATE de la snapshot más nueva, sin excepción.
    """
    session = AsyncMock()
    session.commit = AsyncMock()  # nunca lanza IntegrityError bajo escrituras concurrentes
    session.rollback = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())

    store = PostgresLiveOrderStore(session)
    # writer request A (Confirm) y writer worker B escriben el mismo order_id en
    # rápida sucesión; al ser un único statement upsert, cada uno commit-ea OK.
    await store.put(_make_order(order_id="lo-race", account_id="acc-1"))
    await store.put(
        transition_live_order(_make_order(order_id="lo-race", account_id="acc-1"), "UNKNOWN"),
        account_id="acc-1",
    )

    session.execute.assert_awaited()
    assert session.execute.await_count == 2
    session.commit.assert_awaited()
    session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_postgres_list_unknown_maps_filtered_rows() -> None:
    target = _make_order(order_id="lo-unkq", account_id="acc-1")
    target = transition_live_order(target, "UNKNOWN")
    rows_model = [_row_from(target)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows_model
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    store = PostgresLiveOrderStore(session)
    got = await store.list_unknown(limit=10)
    assert len(got) == 1
    assert got[0].order_id == "lo-unkq"
    assert got[0].status == "UNKNOWN"
    assert got[0].account_id == "acc-1"
    session.execute.assert_awaited()


# ---------------------------------------------------------------------------
# V2.12 — list_open_orders (no-terminal) + cancel_order (persist-only honest).
# ---------------------------------------------------------------------------


def _to_unknown(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "UNKNOWN")
    return transition_live_order(order, "UNKNOWN")


def _to_filled(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "WORKING")
    working = transition_live_order(order, "WORKING", venue_order_id="xtb-1")
    return transition_live_order(working, "FILLED", filled_quantity=100.0)


def _to_rejected(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "REJECTED")
    return transition_live_order(order, "REJECTED")


def _to_cancelled(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "CANCELLED")
    return transition_live_order(order, "CANCELLED")


@pytest.mark.asyncio
async def test_inmemory_list_open_orders_only_non_terminal() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-open-sub", account_id="acc-1"))  # SUBMITTED
    await store.put(_to_unknown(_make_order(order_id="lo-open-unk", account_id="acc-1")))
    await store.put(_to_filled(_make_order(order_id="lo-open-fill", account_id="acc-1")))
    await store.put(_to_rejected(_make_order(order_id="lo-open-rej", account_id="acc-1")))
    await store.put(_to_cancelled(_make_order(order_id="lo-open-cx", account_id="acc-1")))

    rows = await store.list_open_orders(limit=50)
    got = {r.order_id for r in rows}
    # SUBMITTED + UNKNOWN son no-terminales (open); FILLED/REJECTED/CANCELLED no.
    assert got == {"lo-open-sub", "lo-open-unk"}


@pytest.mark.asyncio
async def test_inmemory_list_open_orders_respects_limit_and_counts() -> None:
    store = InMemoryLiveOrderStore()
    for i in range(5):
        await store.put(_make_order(order_id=f"lo-n{i}", account_id="acc-1"))
    limited = await store.list_open_orders(limit=3)
    assert len(limited) == 3


@pytest.mark.asyncio
async def test_postgres_list_open_orders_includes_only_non_terminal() -> None:
    """Barrena la consulta PG (AsyncMock): assert del filtro .in_ y del orden."""
    from bolsa_analytics.cognitive.live_order import NON_TERMINAL_LIVE_STATUSES

    open_row = _row_from(_make_order(order_id="lo-openpg", account_id="acc-1"))
    result = MagicMock()
    result.scalars.return_value.all.return_value = [open_row]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    store = PostgresLiveOrderStore(session)
    got = await store.list_open_orders(limit=10)
    assert [r.order_id for r in got] == ["lo-openpg"]

    stmt = session.execute.await_args.args[0]
    rendered = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    for orphan in NON_TERMINAL_LIVE_STATUSES:
        assert f"'{orphan}'" in rendered
    for terminal in ("FILLED", "REJECTED", "CANCELLED"):
        assert f"'{terminal}'" not in rendered
    assert "UPDATED_AT" in rendered  # orden asc presente (guard de breakage)


@pytest.mark.asyncio
async def test_inmemory_cancel_roundtrip_is_idempotent_single_state() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-cx", account_id="acc-1"))

    cancelled = await store.cancel_order("lo-cx", reason="usuario")
    assert cancelled is not None
    assert cancelled.status == "CANCEL_REQUESTED"  # decisión local, NO CANCELLED

    stored = await store.get("lo-cx")
    assert stored is not None and stored.status == "CANCEL_REQUESTED"
    # CANCEL_REQUESTED NO es terminal: sigue in-flight (pendiente de broker).
    open_orders = await store.list_open_orders(limit=50)
    assert [o.order_id for o in open_orders] == ["lo-cx"]
    assert len(store._by_order) == 1

    # Re-cancel: idempotente → devuelve la orden CANCEL_REQUESTED (no-op).
    again = await store.cancel_order("lo-cx", reason="otra vez")
    assert again is not None and again.status == "CANCEL_REQUESTED"
    assert await store.get("lo-cx") is not None
    assert len(store._by_order) == 1


@pytest.mark.asyncio
async def test_inmemory_cancel_filled_or_rejected_refused() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_to_rejected(_make_order(order_id="lo-rej", account_id="acc-1")))
    await store.put(_to_filled(_make_order(order_id="lo-filled", account_id="acc-1")))

    refused_rej = await store.cancel_order("lo-rej")
    assert refused_rej is not None and refused_rej.status == "REJECTED"

    refused_fill = await store.cancel_order("lo-filled")
    assert refused_fill is not None and refused_fill.status == "FILLED"

    # Siguen terminales en el store: no cancelados, no resucitados.
    rejected_after = await store.get("lo-rej")
    assert rejected_after is not None and rejected_after.status == "REJECTED"
    filled_after = await store.get("lo-filled")
    assert filled_after is not None and filled_after.status == "FILLED"


@pytest.mark.asyncio
async def test_inmemory_cancel_unknown_order_id_returns_none() -> None:
    store = InMemoryLiveOrderStore()
    assert await store.cancel_order("no-such-order") is None
    assert await store.cancel_order("") is None


@pytest.mark.asyncio
async def test_inmemory_cancel_from_unknown_state_is_legal() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_to_unknown(_make_order(order_id="lo-cxu", account_id="acc-1")))
    result = await store.cancel_order("lo-cxu")
    assert result is not None and result.status == "CANCEL_REQUESTED"
    stored = await store.get("lo-cxu")
    assert stored is not None and stored.status == "CANCEL_REQUESTED"


@pytest.mark.asyncio
async def test_inmemory_cancel_tracked_local_not_broker_confirmed() -> None:
    """CANCELLED por decisión local NO es un ack del broker.

    ``get_cancel_meta`` refleja quién/cuándo/por qué y que ``broker_confirmed``
    sigue False hasta que el venue confirme de verdad. Ninguna capa puede leer
    CANCELLED y asumir confirmación broker-side.
    """
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-cc", account_id="acc-1"))

    await store.cancel_order("lo-cc", reason="usuario pide salir", by="pepe")
    meta = await store.get_cancel_meta("lo-cc")
    assert meta is not None
    assert meta.reason == "usuario pide salir"
    assert meta.requested_by == "pepe"
    assert meta.broker_confirmed is False

    # La orden NO se presenta como CANCELLED: sigue CANCEL_REQUESTED (intención
    # registrada, resultado del broker pendiente).
    stored = await store.get("lo-cc")
    assert stored is not None and stored.status == "CANCEL_REQUESTED"
    meta_after = await store.get_cancel_meta("lo-cc")
    assert meta_after is not None and meta_after.broker_confirmed is False


@pytest.mark.asyncio
async def test_inmemory_cancel_broker_confirm_only_via_explicit_set() -> None:
    """Solo una confirmación broker-side explícita marca broker_confirmed."""
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-cbrk", account_id="acc-1"))
    await store.cancel_order("lo-cbrk", reason="mkt", by="sistema")

    meta = await store.get_cancel_meta("lo-cbrk")
    assert meta is not None and meta.broker_confirmed is False

    confirmed = await store.set_broker_cancel_confirmed("lo-cbrk")
    assert confirmed is not None and confirmed.broker_confirmed is True
    assert (await store.get_cancel_meta("lo-cbrk")).broker_confirmed is True
    # Tras el ack del broker la orden SÍ se materializa como CANCELLED (terminal).
    # Antes del ``set_broker_cancel_confirmed`` seguía CANCEL_REQUESTED (decisión
    # local sin ack del venue).
    cancelled = await store.get("lo-cbrk")
    assert cancelled is not None and cancelled.status == "CANCELLED"


@pytest.mark.asyncio
async def test_inmemory_confirm_without_local_cancel_request_is_none() -> None:
    """QA/H5 guard: sin ``cancel_order`` previo, no fabricamos confirmación."""

    async def _never_cancelled(order_id: str) -> None:
        store = InMemoryLiveOrderStore()
        await store.put(_make_order(order_id=order_id, account_id="acc-1"))
        # La maquina está SUBMITTED (no CANCEL_REQUESTED) y nunca se pidió cancel.
        confirmed = await store.set_broker_cancel_confirmed(order_id)
        assert confirmed is None  # no inventa un ack del venue
        meta = await store.get_cancel_meta(order_id)
        assert meta is None  # tampoco crea un doc de cancelación fantasma
        order = await store.get(order_id)
        assert order is not None and order.status == "SUBMITTED"  # sin cambio

    await _never_cancelled("lo-g-nc")


@pytest.mark.asyncio
async def test_postgres_confirm_without_cancel_request_is_none() -> None:
    """QA/H5 guard: PG no estampa broker_cancel_confirmed_at sin decision previa."""
    session = AsyncMock()
    session.commit = AsyncMock()
    existing_row = _row_from(_make_order(order_id="lo-pg-nc", account_id="acc-1"))
    # Fila real sin decisión previa: columnas de cancelación ausentes (None).
    existing_row.cancel_requested_at = None
    existing_row.cancel_reason = None
    existing_row.broker_cancel_confirmed_at = None
    found = MagicMock()
    found.scalar_one_or_none.return_value = existing_row
    session.execute = AsyncMock(return_value=found)

    store = PostgresLiveOrderStore(session)
    confirmed = await store.set_broker_cancel_confirmed("lo-pg-nc")
    assert confirmed is None  # no fabrica confirmación
    # No toca commit de la confirmación (no paso de escritura del ack).
    assert existing_row.broker_cancel_confirmed_at is None
    assert existing_row.status != "CANCELLED"


@pytest.mark.asyncio
async def test_postgres_cancel_tracks_docs_via_upsert() -> None:
    """Cancel PG persiste reason/by en las columnas documentales durables."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    existing_row = _row_from(_make_order(order_id="lo-cdocs", account_id="acc-1"))
    found = MagicMock()
    found.scalar_one_or_none.return_value = existing_row
    session.execute = AsyncMock(return_value=found)

    store = PostgresLiveOrderStore(session)
    await store.cancel_order("lo-cdocs", reason="stop-out", by="risk")

    stmt = session.execute.await_args_list[-1].args[0]
    rendered = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    assert "STOP-OUT" in rendered
    assert "RISK" in rendered
    # El DO UPDATE no reescribe broker_cancel_confirmed_at (no fabrica el ack del
    # broker). El INSERT puede listar la columna con NULL (fila nueva ignora esa
    # columna), pero jamás la asigna a un valor en la cláusula de update.
    do_update_tail = rendered.split("DO UPDATE SET", 1)[1]
    assert "BROKER_CANCEL_CONFIRMED_AT" not in do_update_tail

    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_postgres_cancel_persists_cancelled_and_idempotent() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    existing_row = _row_from(_make_order(order_id="lo-cxpg", account_id="acc-9"))
    found = MagicMock()
    found.scalar_one_or_none.return_value = existing_row
    session.execute = AsyncMock(return_value=found)

    store = PostgresLiveOrderStore(session)
    requested = await store.cancel_order("lo-cxpg")
    assert requested is not None and requested.status == "CANCEL_REQUESTED"
    session.commit.assert_awaited()
    session.rollback.assert_not_called()

    # El estado CANCEL_REQUESTED se persiste mediante el upsert; verifica que el
    # último statement execute (el put) escribe CANCEL_REQUESTED sobre el PK.
    assert session.execute.await_count >= 1
    calls = session.execute.await_args_list
    put_stmt = calls[-1].args[0]
    rendered = str(put_stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    assert "CANCEL_REQUESTED" in rendered
    assert "ON CONFLICT" in rendered

    # Re-cancel (fila ya CANCEL_REQUESTED): get() devuelve no-terminal cancelable,
    # pero no hay auto-bucle → transición CANCEL_REQUESTED→CANCEL_REQUESTED ilegal,
    # se devuelve la orden como no-op idempotente.
    existing_row.status = "CANCEL_REQUESTED"
    again = await store.cancel_order("lo-cxpg")
    assert again is not None and again.status == "CANCEL_REQUESTED"


def test_postgres_cancel_and_list_open_are_exported_on_protocol() -> None:
    """Duck-typing parity: InMemory y Postgres exponen la misma superficie."""
    for store_type in (InMemoryLiveOrderStore, PostgresLiveOrderStore):
        assert hasattr(store_type, "list_open_orders")
        assert hasattr(store_type, "cancel_order")
        assert hasattr(store_type, "get_cancel_meta")
        assert hasattr(store_type, "set_broker_cancel_confirmed")


def test_migration_020_chains_to_live_order_head() -> None:
    """Asegura que la migración 020 cuelga de la cabeza real (019_outbox_position_fifo).

    Si un futuro bump renumera la cadena, este guard falla antes de tocarla.
    """
    from pathlib import Path

    from bolsa_infrastructure.database.models.tables import LiveOrderRow

    migration_path = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "py"
        / "infrastructure"
        / "alembic"
        / "versions"
        / "020_live_orders.py"
    )
    assert migration_path.exists()
    src = migration_path.read_text(encoding="utf-8")
    assert 'down_revision = "019_outbox_position_fifo"' in src
    assert 'revision = "020_live_orders"' in src

    # Paridad de columnas: la fila física del modelo expone las columnas que la
    # migración crea (order_id/account_id/status/venue/instrument_id/side/
    # quantity/filled_quantity/remaining_quantity/venue_order_id/intent_id/
    # financial_apply_count/created_at/updated_at).
    cols = {c.name for c in LiveOrderRow.__table__.columns}
    expecting = {
        "order_id",
        "account_id",
        "status",
        "venue",
        "instrument_id",
        "side",
        "quantity",
        "filled_quantity",
        "remaining_quantity",
        "venue_order_id",
        "intent_id",
        "financial_apply_count",
        "created_at",
        "updated_at",
    }
    assert expecting <= cols


def test_migration_021_extends_live_order_financials() -> None:
    """021 cuelga de 020 (head real) y endurece cantidades + lease recovery.

    Guard offline (sin PG): verifica que el fichero de migración existe, cuelga
    de 020 y que el modelo expone las columnas que la migración añade.
    """
    from pathlib import Path

    from bolsa_infrastructure.database.models.tables import LiveOrderRow

    migration_path = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "py"
        / "infrastructure"
        / "alembic"
        / "versions"
        / "021_live_orders_fin.py"
    )
    assert migration_path.exists()
    src = migration_path.read_text(encoding="utf-8")
    assert 'down_revision = "020_live_orders"' in src
    # Revision id acortado (19 chars) por alembic_version varchar(32).
    assert 'revision = "021_live_orders_fin"' in src
    assert "sa.Numeric(18, 6)" in src  # determinismo numérico (no más Float)
    assert "quantity > 0" in src  # CHECK financiero de invariante en la BD

    cols = {c.name for c in LiveOrderRow.__table__.columns}
    asserting = {
        "recovery_worker_id",
        "recovery_claimed_at",
        "cancel_requested_by",
        "cancel_reason",
        "cancel_requested_at",
        "broker_cancel_confirmed_at",
    }
    assert asserting <= cols
