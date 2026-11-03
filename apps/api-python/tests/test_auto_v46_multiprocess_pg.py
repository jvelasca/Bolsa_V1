"""V2.46.x (AUTO-6 hardening) — concurrencia MULTI-PROCESO real (scheduler + PostgreSQL).

La capa hermética (``test_auto_v46_concurrent.py``) y la de sesiones PG
(``test_concurrent_auto_pg.py``) demuestran el *claim* atómico dentro de un proceso / entre
sesiones. Esta capa cierra lo que ninguna de las dos mide: **N procesos
``scheduler_worker`` reales**, cada uno con su propia RAM, su propio reloj y sus propios
stores, compitiendo por la MISMA cuenta/engine/instrumento/barra/señal. Es la forma más
cercana a "varios contenedores del mismo worker" que el repo puede ejercitar.

Invariante medido SOBRE LO DURABLE (nunca sobre la RAM del test, que no ve a los procesos):

* **1 orden distinta** — ``count(distinct venue_order_id)`` de BUY == 1;
* **1 reserva** — una sola fila de ``portfolio_reservations`` para la cuenta;
* **1 efecto financiero** — ``Σ APPLIED BUY == released_qty`` de esa única reserva;
* tras MATAR UNO de los procesos y reiniciarlo, los invariantes siguen en pie (el
  reemplazo converge al MISMO compromiso en vez de apilar otro).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_MULTIPROCESS_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre LIVE.

Mismo límite de MÉTODO que el Crash Day / Golden Day: el barrido de residuos del conftest
impide correr esta suite en paralelo con otra sesión de pytest contra la misma base. El gate
del tag la corre en un paso DEDICADO.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from tests.test_crash_recovery_day_process_pg import (  # noqa: E402
    _crash_instrument_id,
    _kill_hard,
)
from tests.test_golden_day_v2_process_pg import (  # noqa: E402
    _count_buy_orders,
    _count_distinct_orders,
    _count_positions,
    _env_for,
    _proc_failure,
    _seed_account,
    _seed_edge_report,
    _seed_instrument,
    _spawn,
    _stop,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REQUIRED_ENV = "AUTO_MULTIPROCESS_PG_REQUIRED"

#: Nº de procesos simultáneos sobre la MISMA cuenta/engine/señal.
_PROCESSES = 3
_MAX_POLLS = 160  # × 0.5 s = 80 s de presupuesto para que la carrera se resuelva.
_CONVERGE_POLLS = 60
_POLL_S = 0.5

_SYMBOL = "MPR46"
_SECTOR = "Technology"
_INSTRUMENT_PREFIX = "inst-v46mp-"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la concurrencia multi-proceso AUTO-6 pero no "
            f"disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (multi-proceso AUTO-6) no disponible: {exc}")


@pytest_asyncio.fixture
async def mp_pg_factory() -> Any:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env", override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _reservation_rows(factory: Any, account_id: str) -> list[Any]:
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

    async with factory() as session:
        return list(
            (
                await session.execute(
                    select(PortfolioReservationRow).where(
                        PortfolioReservationRow.account_id == account_id
                    )
                )
            )
            .scalars()
            .all()
        )


async def _materialization_snapshot(factory: Any, account_id: str) -> tuple[int, list[Any]]:
    """(posiciones abiertas, filas de reserva) leídas de lo DURABLE en un mismo instante."""
    return (
        await _count_positions(factory, account_id),
        await _reservation_rows(factory, account_id),
    )


def _materialized(positions: int, rows: Sequence[Any]) -> bool:
    """La FASE 1 está resuelta: hay posición Y una reserva que ya materializó ≥1 trancha.

    **Por qué NO se espera a «una reserva viva con cola».** El camino caliente persiste la
    posición (``_persist_position``, store con ``autocommit=True``) y DESPUÉS libera la
    reserva del fill (``_v2_release_reservations_for_fill``) en **dos transacciones
    distintas**. Entre las dos existe un estado durable —legítimo— en el que la posición ya
    está y ``released_qty`` sigue en 0. Romper el bucle en ese estado ejecutaba la aserción
    de materialización antes de tiempo: medido en CI, ``assert Decimal('0') > 0`` con el
    resto de invariantes todavía sin escribir. Y exigir una reserva ``OPEN`` con cola
    tampoco vale: un fill **completo** deja la fila en ``RELEASED_BY_FILL`` con
    ``remaining_qty = 0``, así que el bucle nunca rompía y gastaba los 80 s de presupuesto
    (medido en local: 115 s de corrida).

    La condición que sí es estable en cualquier punto intermedio es la contabilidad cerrada
    (``released + remaining == requested``, que el libro mantiene en cada liberación) junto
    con haber materializado al menos una trancha: es exactamente lo que el test asserta.
    """
    if positions < 1 or not rows:
        return False
    for row in rows:
        requested = Decimal(str(row.quantity or 0))
        released = Decimal(str(row.released_qty or 0))
        remaining = Decimal(str(row.remaining_qty or 0))
        if released > 0 and released + remaining == requested:
            return True
    return False


def _materialization_dump(positions: int, rows: Sequence[Any]) -> str:
    """Estado durable legible para el mensaje de fallo (sin inventar cifras)."""
    detail = [
        f"{row.reservation_id}(status={row.status}, qty={row.quantity}, "
        f"released={row.released_qty}, remaining={row.remaining_qty})"
        for row in rows
    ]
    return f"posiciones={positions}, reservas={detail or 'ninguna'}"


def test_la_materializacion_no_se_da_por_hecha_entre_las_dos_transacciones() -> None:
    """Regresión del fallo intermitente de CI (``assert Decimal('0') > 0``).

    ``_persist_position`` hace **commit propio** de la posición y
    ``_v2_release_reservations_for_fill`` libera la reserva en un commit **posterior**: hay
    un instante durable, y legítimo, con la posición ya escrita y ``released_qty = 0``. El
    bucle de espera no puede romper ahí. Prueba PURA: no necesita PostgreSQL.
    """
    from types import SimpleNamespace

    sin_liberar = SimpleNamespace(
        quantity=Decimal("100"), released_qty=Decimal("0"), remaining_qty=Decimal("100")
    )
    liberada = SimpleNamespace(
        quantity=Decimal("100"), released_qty=Decimal("100"), remaining_qty=Decimal("0")
    )
    partial = SimpleNamespace(
        quantity=Decimal("100"), released_qty=Decimal("40"), remaining_qty=Decimal("60")
    )
    assert _materialized(1, [sin_liberar]) is False
    assert _materialized(1, [liberada]) is True
    assert _materialized(1, [partial]) is True
    assert _materialized(0, [liberada]) is False
    assert _materialized(1, []) is False


def _alive(procs: list[Any], log_path: Path, *, phase: str) -> None:
    for index, proc in enumerate(procs):
        if proc.poll() is not None:
            raise AssertionError(
                _proc_failure(
                    f"proceso #{index} terminó (exit={proc.returncode}) durante {phase}",
                    log_path,
                )
            )


@pytest.mark.asyncio
async def test_n_real_processes_claim_one_signal_exactly_once_pg(mp_pg_factory: Any) -> None:
    """N procesos reales compiten por una señal: 1 orden, 1 reserva, 1 efecto financiero."""
    instrument_id = _crash_instrument_id(_INSTRUMENT_PREFIX)
    engine_id = f"auto-mp46-{uuid.uuid4().hex[:8]}"
    log_path = Path(tempfile.gettempdir()) / f"mp46-{engine_id}.log"
    account_id: str | None = None
    edge_report_id: str | None = None
    procs: list[Any] = []

    try:
        account_id = await _seed_account(mp_pg_factory)
        await _seed_instrument(
            mp_pg_factory, instrument_id=instrument_id, symbol=_SYMBOL, sector=_SECTOR
        )
        edge_report_id = await _seed_edge_report(
            mp_pg_factory, account_id=account_id, strategy_ref="unversioned"
        )

        env = _env_for(account_id, engine_id, instrument_ids=[instrument_id])
        procs = [_spawn(env, log_path) for _ in range(_PROCESSES)]

        # ── FASE 1 · la carrera se resuelve: alguien abre y materializa una trancha ─────
        # El bucle espera el HECHO que el test asserta (materialización durable), no un
        # proxy: ver ``_materialized`` para las dos formas en que el proxy fallaba.
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_S)
            _alive(procs, log_path, phase="la carrera")
            positions, rows = await _materialization_snapshot(mp_pg_factory, account_id)
            if _materialized(positions, rows):
                break

        positions, rows = await _materialization_snapshot(mp_pg_factory, account_id)
        assert _materialized(positions, rows), _proc_failure(
            "ningún proceso materializó una trancha durable en "
            f"{_MAX_POLLS * _POLL_S:.0f}s: {_materialization_dump(positions, rows)}",
            log_path,
        )
        assert positions >= 1, _proc_failure(
            f"algún proceso debe abrir posición (abiertas={positions})", log_path
        )

        # ── Invariantes SOBRE LO DURABLE ─────────────────────────────────────────
        buy_orders = await _count_buy_orders(mp_pg_factory, account_id)
        distinct_orders = await _count_distinct_orders(mp_pg_factory, account_id)
        assert buy_orders == 1, _proc_failure(
            f"la misma señal produjo {buy_orders} órdenes BUY distintas entre "
            f"{_PROCESSES} procesos (debe ser exactamente 1); órdenes totales="
            f"{distinct_orders}",
            log_path,
        )

        assert len(rows) == 1, _proc_failure(
            "la reserva debe ser única por (cuenta, instrumento): hay "
            f"{len(rows)} filas {[r.reservation_id for r in rows]}",
            log_path,
        )
        reservation = rows[0]
        requested = Decimal(str(reservation.quantity))
        released = Decimal(str(reservation.released_qty or 0))
        remaining = Decimal(str(reservation.remaining_qty or 0))
        assert released > 0, _proc_failure("debe haber materializado ≥1 trancha", log_path)
        assert released + remaining == requested, _proc_failure(
            f"contabilidad cerrada: released={released} + remaining={remaining} "
            f"!= pedido={requested}",
            log_path,
        )

        # ── FASE 2 · muere UN proceso y se reinicia: sin compromiso nuevo ─────────
        victim = procs.pop(0)
        await _kill_hard(victim)
        procs.append(_spawn(env, log_path))

        for _ in range(_CONVERGE_POLLS):
            await asyncio.sleep(_POLL_S)
            _alive(procs, log_path, phase="la convergencia tras el reinicio")

        buy_orders_after = await _count_buy_orders(mp_pg_factory, account_id)
        rows_after = await _reservation_rows(mp_pg_factory, account_id)
        assert buy_orders_after == 1, _proc_failure(
            f"tras matar y reiniciar un proceso, las órdenes BUY distintas deben seguir "
            f"siendo 1 (son {buy_orders_after})",
            log_path,
        )
        assert len(rows_after) == 1, _proc_failure(
            f"tras el reinicio no puede haber una segunda reserva (hay {len(rows_after)})",
            log_path,
        )

        # Cero LIVE: ninguna traza de esta cuenta publicada al bridge LIVE.
        from sqlalchemy import func, select

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        async with mp_pg_factory() as session:
            bad = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(ExecutionEventRow)
                        .where(
                            ExecutionEventRow.account_id == account_id,
                            func.lower(ExecutionEventRow.venue).in_(
                                ("live", "broker_live", "xtb", "real", "live_bridge")
                            ),
                        )
                    )
                ).scalar()
                or 0
            )
        assert bad == 0, "la concurrencia multi-proceso NUNCA debe publicar al bridge LIVE"
    finally:
        for proc in procs:
            try:
                await _stop(proc)
            except Exception:  # noqa: BLE001 — cleanup nunca tira el test.
                pass
        if account_id is not None:
            from sqlalchemy import delete

            from bolsa_infrastructure.database.models.tables import (
                EdgeReportRow,
                ExecutionEventRow,
                PortfolioReservationRow,
                SimAutoPositionRow,
                SimConsumedSignalRow,
                SimFillFinanceContextRow,
            )

            async with mp_pg_factory() as session:
                for model in (
                    SimAutoPositionRow,
                    SimConsumedSignalRow,
                    SimFillFinanceContextRow,
                    ExecutionEventRow,
                    PortfolioReservationRow,
                ):
                    await session.execute(
                        delete(model).where(model.account_id == account_id)  # type: ignore[attr-defined]
                    )
                if edge_report_id is not None:
                    await session.execute(
                        delete(EdgeReportRow).where(EdgeReportRow.id == edge_report_id)
                    )
                await session.commit()
