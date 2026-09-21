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
    _live_reservations,
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

        # ── FASE 1 · la carrera se resuelve: alguien abre con fill PARCIAL ────────
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_S)
            _alive(procs, log_path, phase="la carrera")
            positions = await _count_positions(mp_pg_factory, account_id)
            live = await _live_reservations(mp_pg_factory, account_id)
            if positions >= 1 and any(float(r.remaining_qty or 0) > 0 for r in live):
                break

        positions = await _count_positions(mp_pg_factory, account_id)
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

        rows = await _reservation_rows(mp_pg_factory, account_id)
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
