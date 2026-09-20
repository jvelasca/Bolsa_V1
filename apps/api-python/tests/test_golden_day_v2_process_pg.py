"""AUTO-5 / V2.45 — Golden Day 2.0: el DÍA REAL en el PROCESO scheduler + PostgreSQL real.

Es la capa del TAG del gate de dos capas (la capa hermética por commit vive en
``apps/api-python/tests/test_auto_v2_golden_day_evidence.py``). A diferencia de aquélla
—que inyecta reloj, precio y decider—, aquí NO hay ``run_tick()`` manual ni decider
scripteado: el día lo conduce el **proceso real**
``python -m bolsa_api.workers.scheduler_worker`` con el Decision Spine determinista,
sobre PostgreSQL real, y lo que se certifica es lo que el proceso dejó DURABLE.

FASE 1 — apertura real (≥3 señales, `fills > orders`):

* El proceso abre una posición V2 por cada instrumento del watch (3 instrumentos, 3
  sectores distintos), con el camino REAL de fuentes: sector + ADV/fundamentos del
  catálogo y ``EdgeReport`` persistido (sin dato el motor veta; aquí hay dato).
* ``fills > orders``: la cola SIM parte la orden en tranchas (``fill_chunks``), así que
  el espejo durable ``sim_fill_finance_context`` tiene MÁS filas que ``venue_order_id``
  distintos — la prueba de que el día no finge un fill de una sola pieza.
* Todos los ``execution_events`` en ``APPLIED`` y cada fill con su transacción.

FASE 2 — cierre real (libro plano) por ``time_exit`` + rehidratación durable:

* El precio del camino SIM real es PLANO (``flat_price_script``) y el horizonte de la
  plantilla de política es de 21–90 días, así que un día V2 NO cierra por T1/trailing
  dentro del presupuesto de un test de certificación. El cierre por GEOMETRÍA
  (T1/trailing/régimen) se certifica en la capa hermética, donde el precio y el reloj
  se inyectan (``test_auto_v2_golden_day_evidence.py``).
* Aquí se dispara el cierre por la vía que SÍ es durable y real: se detiene el proceso,
  se lleva el **techo de mantenimiento** (``holdingDeadlineAt`` del JSONB de
  ``sim_auto_positions``) al pasado —el techo se congela al nacer y sobrevive al
  reinicio, E1— y se reinicia el MISMO engine. El worker nuevo REHIDRATA el plan y
  vende por ``time_exit``; el libro canónico queda plano, todo ``APPLIED`` y cada fill
  con su transacción.

Gobierno de honestidad (patrón del repo): sin PostgreSQL real/credenciales hace
``pytest.skip``; con ``AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`` un skip silencioso es un
FALLO duro. NUNCA abre el bridge LIVE.

Límite declarado de MÉTODO: el barrido de residuos del conftest
(``purge_all_residuals``; borra toda cuenta ajena y todo instrumento ``inst-%`` al
terminar la SESIÓN de pytest) impide correr esta suite en PARALELO con otra sesión
de pytest contra la misma base: dos sesiones vivas a la vez se borran los datos
entre sí y el motor queda reintentando liquidaciones contra filas que ya no están.
El gate del tag corre el fichero en un paso DEDICADO, que es la forma soportada.
"""

from __future__ import annotations

import asyncio
import os
import subprocess  # noqa: S404 — proceso real del scheduler (objeto del test).
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"
_REQUIRED_ENV = "AUTO_GOLDEN_DAY_V2_PG_REQUIRED"

# Presupuesto de espera para que el subproceso produzca sus ticks. El arranque paga el
# import de la app + bootstrap de BD antes del primer tick, así que se da holgura — pero
# SIN disparar la duración del job: un test de certificación debe fallar de forma
# informativa, no quedarse minutos esperando. Complementariamente se falla al instante
# si el proceso muere (``proc.poll()`` en los bucles).
_STARTUP_GRACE_S = 150.0
# Sondeos consecutivos (0,5 s cada uno) con el día cerrado Y plano antes de certificar.
# Evita certificar una pausa entre tranchas de la misma orden (ver el bucle del día).
_CLOSED_DAY_POLLS = 4
# Presupuesto para el sondeo de progreso de la fase de apertura.
_OPEN_POLLS = 240
# Presupuesto para el cierre tras el reinicio (rehidratación + venta por ``time_exit``).
_CLOSE_POLLS = 240

# ── V2.45/AUTO-5 — identidad DETERMINISTA del día (sin sorteo de la cola SIM) ──────
#
# El venue SIM deriva TODO su ruido de ``sha256(seed, instrument_id, side, ...)`` con
# ``seed = self._minute * 100_003 + sum(ord(symbol)) % 9999``. Con un id ALEATORIO un
# porcentaje de ejecuciones se queda sin entrada (orden rechazada por la cola noisy o
# parcial que no consume la cantidad) ⇒ rojo espurio, sin defecto de producto. Los ids
# se eligen con una barrida pura y determinista que exige, en TODA la ventana de ticks
# del test: (a) que la orden BUY llene en ≥2 tranchas (para poder afirmar ``fills >
# orders``) y (b) que la orden SELL llene en los primeros minutos (el cierre por
# ``time_exit`` ocurre en el 2º proceso recién arrancado).
_SYMBOLS = ("GDPA", "GDPB", "GDPC")
_SECTORS = ("Technology", "Healthcare", "Energy")
_INSTRUMENT_PREFIXES = ("inst-gd2-0-", "inst-gd2-1-", "inst-gd2-2-")
_FILL_WINDOW = range(0, 9)
_SELL_WINDOW = (1, 2, 3)
_FILL_CHUNKS = 4
_MIN_BUY_CHUNKS = 2


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el Golden Day 2.0 (proceso real) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (Golden Day 2.0) no disponible: {exc}")


def _proc_failure(msg: str, log_path: Path) -> str:
    """Mensaje de fallo con la cola del log del proceso scheduler (diagnóstico)."""
    tail = ""
    try:
        if log_path.exists():
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    except OSError:
        pass
    return f"{msg}\n--- scheduler log tail ---\n{tail}"


def _filling_instrument_id(prefix: str) -> str:
    """Id determinista que llena en BUY (≥2 tranchas) y en SELL COMPLETO en la ventana.

    Barrida pura (sin BD, sin proceso): mismo id en cada ejecución. Si ningún candidato
    cumpliera, el test falla con diagnóstico propio en vez de dejar el rojo espurio al
    azar (mismo patrón que ``test_a9_scheduler_process_pg_zero_human``).

    El llenado COMPLETO de la SELL es una propiedad del sorteo (``sim_rand(seed, side,
    instrument_id, "partialcut", i)``) y NO de la cantidad: por eso garantizarlo aquí
    asegura que el ``time_exit`` del día cierra la posición entera (libro plano) sea
    cual sea la cantidad viva.
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

    for n in range(512):
        candidate = f"{prefix}{n:010d}"
        buy_ok = all(
            len(_probe("buy", minute, candidate).fills) >= _MIN_BUY_CHUNKS
            for minute in _FILL_WINDOW
        )
        sell_ok = all(
            _probe("sell", minute, candidate).status == "filled" for minute in _SELL_WINDOW
        )
        if buy_ok and sell_ok:
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} llena en BUY (≥{_MIN_BUY_CHUNKS} tranchas) y "
        f"en SELL COMPLETO en la ventana del Golden Day; revisar ``draw_queue_noise``"
    )


@pytest_asyncio.fixture
async def golden_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
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


async def _seed_account(factory: async_sessionmaker[AsyncSession]) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    async with factory() as session:
        account_id = (
            await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"AUTO-GD2-{uuid.uuid4().hex[:8]}",
                initial_deposit=100_000.0,
            )
        ).account.id
        await session.commit()
    return account_id


async def _seed_instrument(
    factory: async_sessionmaker[AsyncSession],
    *,
    instrument_id: str,
    symbol: str,
    sector: str,
) -> None:
    """Siembra el instrumento (idempotente) con sector y fundamentales FRESCOS.

    V2.40.1 — gates fail-closed REALES: sin sector el motor veta por ``sector_unknown``
    y sin ADV/frescura por ``liquidity_unknown``. Sembrarlos es lo que certifica el
    camino real de producción.

    El id es DETERMINISTA (día reproducible) y la barrida que lo elige es PURA (sin BD):
    no depende de que el instrumento exista. El barrido de residuos del conftest
    (``purge_all_residuals``, ``inst-%``) lo borra al terminar la sesión de pytest —
    también a las cuentas—, así que cada corrida vuelve a sembrarlo; por eso la
    idempotencia aquí es un no-op en la práctica y no un contrato de persistencia.
    """
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    async with factory() as session:
        if await session.get(InstrumentRow, instrument_id) is not None:
            return
        now = datetime.now(UTC)
        session.add(
            InstrumentRow(
                id=instrument_id,
                symbol=symbol,
                yahoo_symbol=symbol,
                isin=None,
                name="AUTO-GD2",
                exchange="BMAD",
                country="ES",
                currency="EUR",
                type="stock",
                is_active=True,
                sector=sector,
                profile_snapshot={
                    "fundamentals": {"advUsd": 50_000_000.0, "fetchedAt": now.isoformat()}
                },
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def _seed_edge_report(
    factory: async_sessionmaker[AsyncSession], *, account_id: str, strategy_ref: str
) -> str:
    """``EdgeReport`` vigente de la versión: la fuente REAL de ``edge`` del tick.

    V2.40.1 eliminó el ``default_edge``; sin este informe persistido el componente de
    edge vale 0 y el motor veta por ``edge_below_threshold`` (el spine no declara
    versión ⇒ el ref es ``unversioned``).
    """
    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    report_id = f"edge-gd2-{uuid.uuid4().hex[:10]}"
    async with factory() as session:
        session.add(
            EdgeReportRow(
                id=report_id,
                version="v2.45-test",
                strategy_or_signal_ref=strategy_ref,
                instrument_universe_ref=None,
                account_id=account_id,
                credibility=Decimal("0.80"),
                edge_score=Decimal("0.9"),
                band="positive",
                suite={},
                notes=[],
                payload=None,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    return report_id


# ── Lecturas SCOPED al día (nunca globales: un día solo es válido si ESTE proceso lo
#    produjo). ─────────────────────────────────────────────────────────────────────
async def _count_scoped_ticks(factory: async_sessionmaker[AsyncSession], engine_id: str) -> int:
    from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AutoEngineTickRow)
                    .where(AutoEngineTickRow.engine_id == engine_id)
                )
            ).scalar()
            or 0
        )


async def _count_buy_orders(factory: async_sessionmaker[AsyncSession], account_id: str) -> int:
    """ÓRDENES BUY distintas (``count(distinct venue_order_id)``).

    ``execution_events`` no tiene columna ``side``: el lado va embebido en
    ``venue_order_id`` (``sim-{engine}-{acct}-{side}-...``), así que se filtra por ese
    patrón. Se cuentan ÓRDENES, no tranchas: varias filas de la MISMA orden son las
    tranchas de su fill (V2.40.3).
    """
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count(func.distinct(ExecutionEventRow.venue_order_id))).where(
                        ExecutionEventRow.account_id == account_id,
                        ExecutionEventRow.venue_order_id.like("%-buy-%"),
                    )
                )
            ).scalar()
            or 0
        )


async def _count_distinct_orders(factory: async_sessionmaker[AsyncSession], account_id: str) -> int:
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count(func.distinct(ExecutionEventRow.venue_order_id))).where(
                        ExecutionEventRow.account_id == account_id
                    )
                )
            ).scalar()
            or 0
        )


async def _count_fill_contexts(factory: async_sessionmaker[AsyncSession], account_id: str) -> int:
    from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(SimFillFinanceContextRow)
                    .where(SimFillFinanceContextRow.account_id == account_id)
                )
            ).scalar()
            or 0
        )


async def _count_positions(factory: async_sessionmaker[AsyncSession], account_id: str) -> int:
    from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(SimAutoPositionRow)
                    .where(SimAutoPositionRow.account_id == account_id)
                )
            ).scalar()
            or 0
        )


async def _day_progress(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> tuple[set[str], int, Decimal]:
    """(lados ya liquidados, trazas que NO están ``APPLIED``, posición canónica viva).

    La posición se lee de la tabla canónica ``positions`` (la que escribe
    ``ExecuteTrade``), no de ``position_states``, que el AUTO SIM nunca escribe.
    """
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        InvestmentPortfolioRow,
        PositionRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        sides = {
            str(s or "").strip().lower()
            for s in (
                await session.execute(
                    select(SimFillFinanceContextRow.side).where(
                        SimFillFinanceContextRow.account_id == account_id
                    )
                )
            ).scalars()
        }
        pending = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(ExecutionEventRow)
                    .where(
                        ExecutionEventRow.account_id == account_id,
                        ExecutionEventRow.status != "APPLIED",
                    )
                )
            ).scalar()
            or 0
        )
        legacy_ids = [
            legacy
            for legacy in (
                await session.execute(
                    select(InvestmentPortfolioRow.legacy_portfolio_id).where(
                        InvestmentPortfolioRow.account_id == account_id
                    )
                )
            ).scalars()
            if legacy
        ]
        remaining = sum(
            (
                Decimal(str(quantity))
                for quantity in (
                    await session.execute(
                        select(PositionRow.quantity).where(PositionRow.portfolio_id.in_(legacy_ids))
                    )
                ).scalars()
            ),
            Decimal("0"),
        )
    return sides, pending, remaining


async def _expire_holding_deadlines(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> int:
    """Lleva el techo de mantenimiento de CADA plan durable al PASADO (seam E1).

    El techo se congela al nacer y sobrevive al reinicio (``holdingDeadlineAt`` en el
    JSONB ``position_state``): llevarlo al pasado y reiniciar el MISMO engine es la
    forma REAL —sin tocar producción— de disparar el ``TIME_STOP``/``time_exit`` que en
    un día natural ocurriría al vencer el horizonte (21–90 días).
    """
    from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    updated = 0
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            state = dict(row.position_state or {})
            if not state:
                continue
            state["holdingDeadlineAt"] = past
            row.position_state = state  # reasignación: el ORM detecta el cambio en JSON.
            updated += 1
        await session.commit()
    return updated


async def _assert_materialized_and_flat(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
) -> None:
    """Cierre REAL del día: ningún fill sin materializar y libro canónico plano.

    Cada fila del espejo durable ``sim_fill_finance_context`` tiene su transacción en el
    ledger (``transactions.idempotency_key``). Un fill que el motor dio por bueno sin
    mover dinero rompe aquí.
    """
    from bolsa_application.auto_daily_journal import (
        LedgerCashMovement,
        reconstruct_accounting_from_state,
    )
    from bolsa_application.simulated_settlement import simulated_idempotency_key
    from bolsa_domain.lifecycle import assert_equity_invariant
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        InvestmentPortfolioRow,
        PositionRow,
        SimFillFinanceContextRow,
        TransactionRow,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    async with factory() as session:
        entries = await SqlAlchemyLedgerRepository(session).list_for_account(account_id, limit=None)
        legacy_ids = [
            legacy
            for legacy in (
                await session.execute(
                    select(InvestmentPortfolioRow.legacy_portfolio_id).where(
                        InvestmentPortfolioRow.account_id == account_id
                    )
                )
            ).scalars()
            if legacy
        ]
        contexts = (
            (
                await session.execute(
                    select(SimFillFinanceContextRow)
                    .where(SimFillFinanceContextRow.account_id == account_id)
                    .order_by(
                        SimFillFinanceContextRow.created_at,
                        SimFillFinanceContextRow.execution_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        events = (
            (
                await session.execute(
                    select(ExecutionEventRow).where(ExecutionEventRow.account_id == account_id)
                )
            )
            .scalars()
            .all()
        )
        transactions = (
            (
                await session.execute(
                    select(TransactionRow).where(TransactionRow.portfolio_id.in_(legacy_ids))
                )
            )
            .scalars()
            .all()
        )
        position_rows = (
            (
                await session.execute(
                    select(PositionRow).where(PositionRow.portfolio_id.in_(legacy_ids))
                )
            )
            .scalars()
            .all()
        )

        # (1) Ningún fill sin materializar.
        stuck = sorted({str(e.status) for e in events} - {"APPLIED"})
        assert not stuck, (
            f"día Golden con ExecutionEvents fuera de APPLIED: {stuck} "
            "(fills dados por buenos por el motor sin materializar dinero)"
        )
        materialized = {t.idempotency_key for t in transactions if t.idempotency_key}
        unmaterialized = sorted(
            c.execution_id
            for c in contexts
            if (c.idempotency_key or simulated_idempotency_key(c.execution_id)) not in materialized
        )
        assert not unmaterialized, (
            f"fills con contexto durable pero SIN transacción en el ledger: {unmaterialized}"
        )

        # (2) Libro plano: la posición canónica REAL (``positions``) vuelve a cero.
        remaining = sum((Decimal(str(p.quantity)) for p in position_rows), Decimal("0"))
        assert remaining == 0, (
            f"el día Golden debe dejar el libro plano: quedan {remaining} "
            f"({len(position_rows)} filas en positions)"
        )

        # (3) Invariante de equity (dominio) sobre el ledger real.
        movements = [
            LedgerCashMovement(
                category=(entry.type or "").strip().lower(),
                amount=Decimal(str(entry.amount)),
            )
            for entry in entries
        ]
        from tests.applied_fill_equity import realized_notional_from_applied_fills

        closed_pnl = await realized_notional_from_applied_fills(session, account_id)
        accounting = reconstruct_accounting_from_state(
            movements=movements,
            remaining=remaining,
            avg_cost=Decimal("0"),
            last_price=Decimal("0"),
            closed_pnl=closed_pnl,
        )
        assert_equity_invariant(accounting)


def _env_for(account_id: str, engine_id: str, *, instrument_ids: list[str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "1",
            # V2 (AUTO 2.0) ON: el día lo conduce el pipeline V2, no el camino legacy.
            "AUTO_ENGINE_SIM_V2": "1",
            "AUTO_ENGINE_SIM_V2_REGIME": "BULL_TREND",
            "AUTO_ENGINE_SIM_V2_EQUITY": "100000",
            "AUTO_ENGINE_SIM_V2_TOP_N": "3",
            "AUTO_ENGINE_SIM_ACCOUNT_ID": account_id,
            "AUTO_ENGINE_SIM_ENGINE_ID": engine_id,
            "AUTO_ENGINE_SIMULATED_VENUE": "simulated",
            "AUTO_ENGINE_SIMULATED_WATCH": ",".join(instrument_ids),
            "AUTO_ENGINE_SIM_INTERVAL_SECONDS": "1.0",
            "AUTO_ENGINE_SIM_LOT_QTY": "100",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def _spawn(env: dict[str, str], log_path: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(  # noqa: S603 — comando fijo del repo.
        [sys.executable, "-m", "bolsa_api.workers.scheduler_worker"],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=open(log_path, "a", encoding="utf-8"),  # noqa: SIM115 — cerrado abajo.
        stderr=subprocess.STDOUT,
    )


async def _stop(proc: subprocess.Popen[bytes]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    try:
        if proc.stdout is not None:
            proc.stdout.close()
    except OSError:
        pass


@pytest.mark.asyncio
async def test_golden_day_v2_real_process_opens_and_closes_the_book_pg(
    golden_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El proceso scheduler real conduce el Golden Day 2.0 (V2) sobre PostgreSQL real.

    FASE 1: abre ≥3 posiciones con fill materializado, planes durables y ``fills >
    orders``. FASE 2: reinicio con el techo de mantenimiento vencido ⇒ cierre por
    ``time_exit``, libro plano y cada fill con su transacción.
    """
    instrument_ids = [_filling_instrument_id(prefix) for prefix in _INSTRUMENT_PREFIXES]
    engine_id = f"auto-gd2-{uuid.uuid4().hex[:8]}"
    log_path = Path(tempfile.gettempdir()) / f"gd2-{engine_id}.log"
    account_id: str | None = None
    edge_report_id: str | None = None
    proc: subprocess.Popen[bytes] | None = None

    try:
        account_id = await _seed_account(golden_pg_factory)
        for instrument_id, symbol, sector in zip(instrument_ids, _SYMBOLS, _SECTORS, strict=True):
            await _seed_instrument(
                golden_pg_factory,
                instrument_id=instrument_id,
                symbol=symbol,
                sector=sector,
            )
        edge_report_id = await _seed_edge_report(
            golden_pg_factory, account_id=account_id, strategy_ref="unversioned"
        )

        env = _env_for(account_id, engine_id, instrument_ids=instrument_ids)
        proc = _spawn(env, log_path)

        # ── FASE 1: apertura real (`≥3` señales, libro con fill materializado) ────
        opened = 0
        for _ in range(_OPEN_POLLS):
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                raise AssertionError(
                    _proc_failure(
                        f"el proceso scheduler terminó (exit={proc.returncode}) antes de abrir",
                        log_path,
                    )
                )
            opened = await _count_positions(golden_pg_factory, account_id)
            if opened >= len(instrument_ids):
                break

        ticks = await _count_scoped_ticks(golden_pg_factory, engine_id)
        buy_orders = await _count_buy_orders(golden_pg_factory, account_id)
        assert opened >= len(instrument_ids), _proc_failure(
            f"el proceso debe abrir una posición V2 por instrumento del watch "
            f"(abiertas={opened} de {len(instrument_ids)}, buy_orders={buy_orders}, "
            f"ticks={ticks})",
            log_path,
        )
        assert buy_orders >= len(instrument_ids), _proc_failure(
            f"el día Golden debe ver ≥{len(instrument_ids)} señales (órdenes BUY distintas: "
            f"{buy_orders})",
            log_path,
        )

        # ``fills > orders``: la cola SIM parte la orden en tranchas ⇒ el espejo durable
        # tiene más filas que órdenes distintas. Es la prueba de que el día no finge un
        # fill de una sola pieza (requisito explícito del plan AUTO-5).
        fills = await _count_fill_contexts(golden_pg_factory, account_id)
        orders = await _count_distinct_orders(golden_pg_factory, account_id)
        assert fills > orders, _proc_failure(
            f"el día Golden debe materializar MÁS tranchas que órdenes (fills={fills}, "
            f"orders={orders}); con ids deterministas de ≥{_MIN_BUY_CHUNKS} tranchas por BUY "
            "esto es estructural, no un valor afortunado",
            log_path,
        )

        # ── FASE 2: reinicio con el techo VENCIDO ⇒ cierre por ``time_exit`` ─────
        await _stop(proc)
        proc = None
        expired = await _expire_holding_deadlines(golden_pg_factory, account_id)
        assert expired >= len(instrument_ids), (
            f"deben vencer los {len(instrument_ids)} techos durables, no {expired}"
        )

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
            "el día Golden debe cerrar los planes durables (time_exit + rehidratación)",
            log_path,
        )
        assert {"buy", "sell"} <= sides, _proc_failure(
            f"el día Golden debe cerrar el ciclo BUY→SELL (lados={sorted(sides)})",
            log_path,
        )
        assert pending == 0, _proc_failure(
            f"el día Golden deja {pending} ExecutionEvents sin materializar (RETRY/CAPTURED)",
            log_path,
        )
        assert remaining == 0, _proc_failure(
            f"el día Golden no deja el libro plano: quedan {remaining}", log_path
        )
        await _assert_materialized_and_flat(golden_pg_factory, account_id=account_id)

        # Zero human / zero LIVE: ninguna traza de ESTA cuenta con venue live.
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
        assert bad == 0, "el proceso Golden Day NUNCA debe publicar al bridge LIVE"
    finally:
        if proc is not None:
            await _stop(proc)
        if account_id is not None:
            from bolsa_infrastructure.database.models.tables import (
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
                    from bolsa_infrastructure.database.models.tables import EdgeReportRow

                    await session.execute(
                        delete(EdgeReportRow).where(EdgeReportRow.id == edge_report_id)
                    )
                try:
                    await SqlAlchemyAccountRepository(session).close_account(account_id)
                except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                    pass
                await session.commit()
