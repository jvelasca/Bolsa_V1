"""V2.46 / AUTO-6 — Crash/Recovery Day (capa REAL: proceso scheduler + PostgreSQL).

Es la capa del TAG del escenario ``Crash/Recovery`` (la hermética por commit vive en
``apps/api-python/tests/test_auto_v46_crash_recovery.py``). A diferencia de aquélla —que
inyecta reloj/precio/decider y descarta el objeto worker—, aquí el día lo conduce el
**proceso real** ``python -m bolsa_api.workers.scheduler_worker`` sobre PostgreSQL real y
la MUERTE es una **muerte sucia de proceso** (``kill()``/``terminate()``, sin apagado
ordenado): la RAM se pierde de verdad y sólo sobrevive lo DURABLE.

Secuencia certificada:

    BUY PARCIAL (la cola SIM corta la orden: quedan tranchas aplicadas + cola viva)
      → MUERTE SUCIA (se mata el proceso; nada de shutdown)
      → REINICIO (MISMO engine/cuenta sobre la MISMA BD)
      → RECONCILIACIÓN (readopt + reconciliación de arranque: la cola viva se libera)
      → CONTINUAR + CIERRE LIMPIO (``holdingDeadlineAt`` vencido ⇒ ``time_exit``)

Invariantes (medidos sobre lo durable, nunca sobre RAM del test):

* ``fills > orders`` (hubo tranchas reales, no un fill de una pieza);
* al morir el proceso queda una **reserva viva** por la cola NO llenada (el fill parcial
  es un hecho durable, no una impresión del test);
* todo ``ExecutionEvent`` en ``APPLIED`` y **cada** fill con su transacción
  (``transactions.idempotency_key``);
* ``POSITION == Σ APPLIED BUY − Σ APPLIED SELL`` y libro canónico plano al cerrar;
* ni una reserva viva al final (la reconciliación del reinicio liberó la cola);
* cero trazas de venue LIVE.

DESVIACIÓN DECLARADA (§7 del plan). La cola SIM materializa TODAS las tranchas de una
orden dentro del MISMO tick (``_settle`` aplica el schedule completo de una vez), así que
no existe una ventana en la que matar el proceso «en mitad del fill»: el fill parcial
observable es el que el **schedule determinista** deja —una orden cortada con la cola sin
llenar, ``status='partial'``— y que el reinicio debe cerrar contablemente. Se certifica el
estado durable del fill parcial, no la interrupción en vuelo (imposible por construcción
del venue SIM). No se siembra nada: el parcial lo produce el propio proceso.

Mismo límite de MÉTODO que el Golden Day: el barrido de residuos del conftest impide
correr esta suite en paralelo con otra sesión de pytest contra la misma base. El gate del
tag la corre en un paso DEDICADO.
"""

from __future__ import annotations

import asyncio
import os
import subprocess  # noqa: S404 — proceso real del scheduler (objeto del test).
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

# Helpers genéricos (semilla, conteos, spawn/stop, cierre y materialización) del Golden
# Day 2.0: el Crash/Recovery reutiliza la MISMA infraestructura medida en vez de
# reimplementarla. Lo único propio es la identidad del instrumento con fill PARCIAL.
from tests.test_golden_day_v2_process_pg import (  # noqa: E402
    _assert_materialized_and_flat,
    _count_buy_orders,
    _count_distinct_orders,
    _count_fill_contexts,
    _count_positions,
    _count_scoped_ticks,
    _day_progress,
    _env_for,
    _expire_holding_deadlines,
    _proc_failure,
    _seed_account,
    _seed_edge_report,
    _seed_instrument,
    _spawn,
    _stop,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REQUIRED_ENV = "AUTO_CRASH_RECOVERY_PG_REQUIRED"

# Presupuestos de espera (mismos criterios que el Golden Day: fallar informativo, sin
# disparar la duración del job). Se falla al instante si el proceso muere.
_STARTUP_GRACE_S = 150.0
_OPEN_POLLS = 240
_CLOSE_POLLS = 240
_CLOSED_DAY_POLLS = 4

# ── Identidad DETERMINISTA del día (sin sorteo de la cola SIM) ─────────────────────
_SYMBOL = "CRV46"
_SECTOR = "Technology"
_INSTRUMENT_PREFIX = "inst-v46crash-"
#: La entrada real del proceso ocurre en el PRIMER tick (minuto 1); se exige además el
#: minuto 2 para tolerar un arranque que tarde un tick en aprobar (medido: minuto 1).
_BUY_WINDOW = (1, 2)
#: El ``time_exit`` cierra en los primeros ticks del proceso reiniciado.
_SELL_WINDOW = (1, 2, 3)
_FILL_CHUNKS = 4
_MIN_BUY_CHUNKS = 2


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para Crash/Recovery (proceso real) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (Crash/Recovery) no disponible: {exc}")


def _crash_instrument_id(prefix: str) -> str:
    """Id determinista cuyo BUY LLENA PARCIAL (≥2 tranchas) y cuyo SELL llena COMPLETO.

    Barrida pura (sin BD, sin proceso): mismo id en cada ejecución. El reparto de tranchas
    depende SOLO del contexto de mercado (seed/side/instrument), nunca de la cantidad ni
    de la identidad del order (V2.24/A9.1), así que la barrida vale para la cantidad real
    que decida el sizing del pipeline. Si ningún candidato cumpliera, el test falla con
    diagnóstico propio en vez de dejar un rojo espurio al azar.
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    def _probe(side: str, minute: int, candidate: str) -> Any:
        return simulated_fill_schedule(
            instrument_id=candidate,
            side=side,
            quantity=Decimal("100"),
            venue_order_id=f"probe-{side}-{candidate}-{minute}",
            seed=minute * 100_003 + sum(map(ord, candidate)) % 9999,
            fill_chunks=_FILL_CHUNKS,
            base_mid=100.0,
        )

    for n in range(8192):
        candidate = f"{prefix}{n:010d}"
        buy_partial = all(
            _probe("buy", minute, candidate).status == "partial"
            and len(_probe("buy", minute, candidate).fills) >= _MIN_BUY_CHUNKS
            for minute in _BUY_WINDOW
        )
        if not buy_partial:
            continue
        sell_ok = all(
            _probe("sell", minute, candidate).status == "filled" for minute in _SELL_WINDOW
        )
        if sell_ok:
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} tiene BUY PARCIAL (≥{_MIN_BUY_CHUNKS} "
        f"tranchas) en {_BUY_WINDOW} y SELL COMPLETO en {_SELL_WINDOW}; revisar "
        "``draw_queue_noise``"
    )


async def _live_reservations(factory: Any, account_id: str) -> list[Any]:
    """Reservas VIVAS de la cuenta: la cola de capital NO materializada (fill parcial)."""
    from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

    async with factory() as session:
        from sqlalchemy import select

        return list(
            (
                await session.execute(
                    select(PortfolioReservationRow).where(
                        PortfolioReservationRow.account_id == account_id,
                        PortfolioReservationRow.status == "OPEN",
                    )
                )
            )
            .scalars()
            .all()
        )


async def _kill_hard(proc: subprocess.Popen[bytes]) -> None:
    """Muerte SUCIA: nada de ``terminate()`` ordenado mientras haya trabajo en vuelo.

    POSIX: ``kill()`` (SIGKILL, no capturable). Windows: ``kill()`` es ``TerminateProcess``
    —el máximo disponible—; se declara como la muerte sucia del sistema operativo.
    """
    proc.kill()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:  # pragma: no cover — defensivo.
        proc.terminate()
        proc.wait(timeout=10)
    try:
        if proc.stdout is not None:
            proc.stdout.close()
    except OSError:  # pragma: no cover — defensivo.
        pass


@pytest_asyncio.fixture
async def crash_pg_factory() -> Any:
    """Factoría de sesiones PG real (misma configuración que el Golden Day)."""
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


@pytest.mark.asyncio
async def test_crash_recovery_day_real_process_survives_dirty_kill_pg(
    crash_pg_factory: Any,
) -> None:
    """Proceso real: fill parcial durable → muerte sucia → reinicio convergente → plano."""
    golden_pg_factory = crash_pg_factory
    instrument_id = _crash_instrument_id(_INSTRUMENT_PREFIX)
    engine_id = f"auto-cr46-{uuid.uuid4().hex[:8]}"
    log_path = Path(tempfile.gettempdir()) / f"cr46-{engine_id}.log"
    account_id: str | None = None
    edge_report_id: str | None = None
    proc: subprocess.Popen[bytes] | None = None

    try:
        account_id = await _seed_account(golden_pg_factory)
        await _seed_instrument(
            golden_pg_factory,
            instrument_id=instrument_id,
            symbol=_SYMBOL,
            sector=_SECTOR,
        )
        edge_report_id = await _seed_edge_report(
            golden_pg_factory, account_id=account_id, strategy_ref="unversioned"
        )

        env = _env_for(account_id, engine_id, instrument_ids=[instrument_id])
        proc = _spawn(env, log_path)

        # ── FASE 1 · el proceso abre con un fill PARCIAL (cola viva) ──────────────
        position_seen = 0
        live: list[Any] = []
        for _ in range(_OPEN_POLLS):
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                raise AssertionError(
                    _proc_failure(
                        f"el proceso terminó (exit={proc.returncode}) antes de abrir",
                        log_path,
                    )
                )
            position_seen = await _count_positions(golden_pg_factory, account_id)
            live = await _live_reservations(golden_pg_factory, account_id)
            # El fill parcial es un hecho DURABLE: posición materializada + cola viva.
            if position_seen >= 1 and any(float(r.remaining_qty or 0) > 0 for r in live):
                break

        ticks = await _count_scoped_ticks(golden_pg_factory, engine_id)
        buy_orders = await _count_buy_orders(golden_pg_factory, account_id)
        fills = await _count_fill_contexts(golden_pg_factory, account_id)
        orders = await _count_distinct_orders(golden_pg_factory, account_id)

        assert position_seen >= 1, _proc_failure(
            f"el proceso debe abrir una posición V2 (abiertas={position_seen}, "
            f"buy_orders={buy_orders}, ticks={ticks})",
            log_path,
        )
        assert buy_orders >= 1, _proc_failure(
            f"el día debe ver ≥1 señal BUY (órdenes BUY distintas={buy_orders})", log_path
        )
        # ``fills > orders``: la orden se materializó en TRANCHAS, no en una pieza.
        assert fills > orders, _proc_failure(
            f"se esperaban MÁS tranchas que órdenes (fills={fills}, orders={orders})",
            log_path,
        )
        tail = [
            r
            for r in live
            if r.instrument_id == instrument_id and float(r.remaining_qty or 0) > 0
        ]
        assert tail, _proc_failure(
            "la muerte debe ocurrir con el fill PARCIAL durable (cola de reserva viva); "
            f"reservas vivas: {[(r.reservation_id, str(r.remaining_qty)) for r in live]}",
            log_path,
        )
        partial_reservation = tail[0]
        released_before = float(partial_reservation.released_qty or 0)
        remaining_before = float(partial_reservation.remaining_qty or 0)
        assert released_before > 0, "debe haber materializado al menos una trancha"

        # ── MUERTE SUCIA (RAM perdida; sólo sobrevive lo durable) ─────────────────
        await _kill_hard(proc)
        proc = None

        # ── REINICIO · el techo vencido ⇒ reconciliación + ``time_exit`` ──────────
        expired = await _expire_holding_deadlines(golden_pg_factory, account_id)
        assert expired >= 1, "debe vencer el techo durable del plan parcial"

        proc = _spawn(env, log_path)
        sides: set[str] = set()
        pending = 1
        remaining = Decimal("0")
        closed_polls = 0
        for _ in range(_CLOSE_POLLS):
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                raise AssertionError(
                    _proc_failure(
                        f"el proceso terminó (exit={proc.returncode}) durante el cierre",
                        log_path,
                    )
                )
            sides, pending, remaining = await _day_progress(golden_pg_factory, account_id)
            if (
                await _count_positions(golden_pg_factory, account_id) == 0
                and {"buy", "sell"} <= sides
                and pending == 0
                and remaining == 0
            ):
                closed_polls += 1
                if closed_polls >= _CLOSED_DAY_POLLS:
                    break
            else:
                closed_polls = 0

        assert await _count_positions(golden_pg_factory, account_id) == 0, _proc_failure(
            "el día debe cerrar el plan readoptado tras el crash (time_exit)",
            log_path,
        )
        assert {"buy", "sell"} <= sides, _proc_failure(
            f"el día debe cerrar el ciclo BUY→SELL (lados={sorted(sides)})", log_path
        )
        assert pending == 0, _proc_failure(
            f"quedan {pending} ExecutionEvents sin materializar (RETRY/CAPTURED)", log_path
        )
        assert remaining == 0, _proc_failure(
            f"el libro no quedó plano tras el crash: quedan {remaining}", log_path
        )

        # (1) Cada fill con su transacción y ningún fill sin materializar.
        await _assert_materialized_and_flat(golden_pg_factory, account_id=account_id)

        # (2) La cola parcial se liberó al reconciliar: ni una reserva viva al final.
        leftover = await _live_reservations(golden_pg_factory, account_id)
        assert leftover == [], (
            "la reconciliación del reinicio debe liberar la cola del fill parcial; "
            f"quedan vivas: {[(r.reservation_id, str(r.remaining_qty)) for r in leftover]}"
        )
        assert remaining_before > 0, "el escenario exige cola viva ANTES del reinicio"

        # (3) ``fills > orders`` sigue siendo cierto tras el reinicio (sin doble orden).
        fills_after = await _count_fill_contexts(golden_pg_factory, account_id)
        orders_after = await _count_distinct_orders(golden_pg_factory, account_id)
        assert fills_after > orders_after, _proc_failure(
            f"tras el reinicio: fills={fills_after} orders={orders_after}", log_path
        )

        # (4) Zero LIVE: ninguna traza de ESTA cuenta con venue live.
        from sqlalchemy import func, select

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        async with golden_pg_factory() as session:
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
        assert bad == 0, "el Crash/Recovery Day NUNCA debe publicar al bridge LIVE"
    finally:
        if proc is not None:
            await _stop(proc)
        if account_id is not None:
            from sqlalchemy import delete

            from bolsa_infrastructure.database.models.tables import (
                EdgeReportRow,
                ExecutionEventRow,
                SimAutoPositionRow,
                SimConsumedSignalRow,
                SimFillFinanceContextRow,
            )
            from bolsa_infrastructure.database.repositories.account_repository import (
                SqlAlchemyAccountRepository,
            )

            async with golden_pg_factory() as session:
                await session.execute(
                    delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
                )
                await session.execute(
                    delete(SimConsumedSignalRow).where(
                        SimConsumedSignalRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(SimFillFinanceContextRow).where(
                        SimFillFinanceContextRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(ExecutionEventRow).where(ExecutionEventRow.account_id == account_id)
                )
                if edge_report_id is not None:
                    await session.execute(
                        delete(EdgeReportRow).where(EdgeReportRow.id == edge_report_id)
                    )
                try:
                    await SqlAlchemyAccountRepository(session).close_account(account_id)
                except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                    pass
                await session.commit()
