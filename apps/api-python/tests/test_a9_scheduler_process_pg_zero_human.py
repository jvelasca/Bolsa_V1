"""V2.24 / A9.1 (P2-04) — Reina REAL: proceso scheduler + spine determinista real.

A diferencia de ``test_auto_scheduler_real_pg_zero_human_intervention`` (que llama
``runtime.run_tick()`` directamente y usa un decider scripteado), este test arranca
el **proceso real** ``python -m bolsa_api.workers.scheduler_worker`` —con su gate de
env y su ``auto_sim_loop`` periódico— sobre PostgreSQL real, y deja que el propio
scheduler conduzca el día AUTO con el **Decision Spine determinista** (sin humano,
sin ``run_tick`` manual, sin ``_ScriptDecider``).

Gobierno de honestidad (patrón del repo): sin PostgreSQL real/credenciales hace
``pytest.skip``; con ``AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1`` un skip silencioso es
un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import subprocess  # noqa: S404 — proceso real del scheduler (objeto del test).
import sys
import tempfile
import time
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"
_REQUIRED_ENV = "AUTO_SCHEDULER_PROCESS_PG_REQUIRED"
_TIMEOUT_S = 90.0
# Presupuesto de espera para que el subproceso produzca sus ticks. El arranque paga
# import de la app + bootstrap de BD antes del primer tick, así que se da holgura sobre
# ``_TIMEOUT_S`` — pero SIN disparar la duración del job: un test de certificación debe
# fallar de forma informativa, no quedarse 8 minutos esperando. Complementariamente se
# falla al instante si el proceso muere (ver ``proc.poll()`` en los bucles).
_STARTUP_GRACE_S = 120.0
# Vigilancia acotada tras un restart: el caso CORRECTO es que NO ocurra nada (no se
# re-compra), así que este sondeo es corto a propósito — no debe agotar el presupuesto
# de arranque en el camino feliz.
_RESTART_WATCH_S = 20.0
# Sondeos consecutivos (0,5 s cada uno) con el día cerrado Y plano antes de certificar.
# Evita certificar una pausa entre tranchas de la misma orden (ver el bucle del día).
_CLOSED_DAY_POLLS = 4


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"AUTO scheduler process PG requerido pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (proceso scheduler AUTO) no disponible: {exc}")


def _proc_failure(msg: str, log_path: Path) -> str:
    """Mensaje de fallo con la cola del log del proceso scheduler (diagnóstico)."""
    tail = ""
    try:
        if log_path.exists():
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    except OSError:
        pass
    return f"{msg}\n--- scheduler log tail ---\n{tail}"


@pytest_asyncio.fixture
async def sched_process_factory() -> async_sessionmaker[AsyncSession]:
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


async def _count(factory: async_sessionmaker[AsyncSession], model: object) -> int:
    async with factory() as session:
        return int((await session.execute(select(func.count()).select_from(model))).scalar() or 0)


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


async def _count_scoped_events(factory: async_sessionmaker[AsyncSession], account_id: str) -> int:
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(ExecutionEventRow)
                    .where(ExecutionEventRow.account_id == account_id)
                )
            ).scalar()
            or 0
        )


async def _count_scoped_ledger(factory: async_sessionmaker[AsyncSession], account_id: str) -> int:
    from bolsa_infrastructure.database.models.tables import LedgerEntryRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(LedgerEntryRow)
                    .where(LedgerEntryRow.account_id == account_id)
                )
            ).scalar()
            or 0
        )


# ── V2.40.3 — certificación del día AUTO: libro plano + dinero materializado ──────
#
# Identidad DETERMINISTA de certificación. El broker simulado deriva TODO su ruido
# (cola noisy, parcial a mitad de camino, slippage) de ``sha256(seed, instrument,
# side, ...)``, y en el primer tick de un proceso recién arrancado ``seed`` depende solo
# del id del instrumento. Con un instrumento ALEATORIO, medido sobre 5 000 ids de esta
# familia, el **12,4 %** de las ejecuciones se quedaba sin entrada (orden rechazada por la
# cola noisy o parcial que no consume la cantidad): el gate «libro plano» habría sido una
# moneda al aire en vez de una certificación. El instrumento se elige con una barrida
# determinista (``_filling_instrument_id``) ⇒ mismo id y mismo día en cada ejecución. El
# aislamiento entre runs lo siguen dando la cuenta SIM (id aleatorio) y el ``engine_id``;
# el instrumento se siembra solo si no existe.
_CERT_INSTRUMENT_PREFIX = "inst-a9proc-"
_CERT_SYMBOL = "A9CERT"
_RESTART_INSTRUMENT_PREFIX = "inst-a9restart-"
# = ``_FILL_CHUNKS`` del worker: solo importa para elegir un instrumento cuya orden llene.
_CERT_FILL_CHUNKS = 4


def _filling_instrument_id(prefix: str, *, side: str) -> str:
    """Instrumento determinista cuya orden ``side`` NO topa con una costa terminal.

    El venue SIM decide si una orden llena a partir de ``draw_queue_noise(seed, instrument,
    side)`` con ``seed = sum(ord(symbol)) % 9999`` en el primer tick de un proceso recién
    arrancado (``_minute = 0``). Es decir: **el resultado depende del id del instrumento**, y
    con un id aleatorio la orden puede caer en ``noise_reject``/``noise_timeout``/
    ``noise_market_closed``/``noise_unavailable``/``noise_unknown`` (o en el residual que no
    llena) ⇒ ``fills=()`` ⇒ el spine determinista ya no vuelve a proponer entrada en ese
    proceso y el día AUTO nunca ocurre. Medido sobre 5 000 ids aleatorios de esta familia:
    **12,4 %** de las ejecuciones se quedaban sin entrada — rojo espurio, sin defecto.

    La barrida es pura (sin BD, sin proceso) y determinista: mismo id en cada ejecución,
    mismo día simulado. Si ningún candidato llenara, el test falla con diagnóstico propio en
    vez de quedarse esperando 120 s.
    """
    from decimal import Decimal

    from bolsa_application.simulated_broker import simulated_fill_schedule

    for n in range(64):
        candidate = f"{prefix}{n:010d}"
        seed = sum(map(ord, candidate)) % 9999
        schedule = simulated_fill_schedule(
            instrument_id=candidate,
            side=side,
            quantity=Decimal("100"),
            venue_order_id=f"probe-{candidate}",
            seed=seed,
            fill_chunks=_CERT_FILL_CHUNKS,
            base_mid=100.0,
        )
        if schedule.fills:
            return candidate
    raise AssertionError(
        f"ningún instrumento determinista de {prefix} llena en la cola SIM ({side}); "
        "revisar los umbrales de draw_queue_noise o la familia de ids"
    )


async def _seed_instrument(
    factory: async_sessionmaker[AsyncSession], *, instrument_id: str, symbol: str
) -> None:
    """Siembra el instrumento del test, idempotente (solo si NO existe).

    Con identidad fijada (día determinista) el segundo run no puede re-insertar la
    misma PK, y borrarla no es opción: el ledger de runs anteriores la referencia
    (``ON DELETE SET NULL`` contaminaría asientos ya escritos).
    """
    from datetime import UTC, datetime

    from bolsa_infrastructure.database.models.tables import InstrumentRow

    async with factory() as session:
        if await session.get(InstrumentRow, instrument_id) is not None:
            return
        session.add(
            InstrumentRow(
                id=instrument_id,
                symbol=symbol,
                yahoo_symbol=symbol,
                isin=None,
                name="A9-Proc",
                exchange="BMAD",
                country="ES",
                currency="EUR",
                type="stock",
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def _day_progress(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> tuple[set[str], int, Decimal]:
    """(lados ya liquidados, trazas que NO están ``APPLIED``, posición canónica viva).

    El día AUTO es un ciclo BUY→SELL de UNA sola pasada (el spine queda en COOLDOWN
    tras el cierre), así que «el SELL está liquidado» es una condición de progreso
    estable: una vez alcanzada, el proceso ya no abre nada más. La posición se lee de la
    tabla canónica ``positions`` (la que escribe ``ExecuteTrade``), no de
    ``position_states``, que el AUTO SIM nunca escribe.
    """
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        InvestmentPortfolioRow,
        PositionRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        sides = {
            str(s).strip().lower()
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


async def _assert_full_day_closed(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    instrument_id: str,
) -> None:
    """V2.40.3 (P2-A/P2-B): el día AUTO cierra el libro y NO deja dinero sin cuadrar.

    Tres afirmaciones, cada una con su diagnóstico propio:

    1. **Ningún fill sin materializar.** Todo ``ExecutionEvent`` de la cuenta está
       ``APPLIED`` (ni ``CAPTURED``/``APPLYING``/``RETRY``/``FAILED``) y cada fila del
       espejo durable ``sim_fill_finance_context`` tiene su transacción en el ledger
       (``transactions.idempotency_key``). Un fill que el motor dio por bueno sin
       mover dinero rompe aquí — es el fallo que destapó la clave de idempotencia
       truncada (los 4 fills de una orden colapsaban en una clave, la 2ª..Nª quedaban
       en RETRY y la posición se quedaba a medias).
    2. **Libro plano.** La posición canónica REAL de la cuenta (``positions``, la que
       escribe ``ExecuteTrade``) vuelve a cero. Ojo: ``position_states`` NO sirve como
       canónico aquí — esa tabla es del camino lifecycle/paper y el AUTO SIM nunca la
       escribe; leerla daba ``remaining=0`` siempre y hacía que la invariante de
       equity midiera otra cosa (el desajuste que se vio en CI).
    3. **Invariante de equity del dominio** sobre el ledger real, con el P&L cerrado
       reconstruido desde una fuente INDEPENDIENTE del cash (el espejo de fills), para
       que ``cash == initial + realized − fees`` sea una afirmación financiera y no una
       tautología. Con el libro plano, esa identidad solo se cumple si cada fill del
       espejo tiene su notional exacto en el ledger.
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
        # ``positions``/``transactions`` cuelgan del portfolio LEGACY
        # (``portfolios.id``) y ``ledger_entries`` del nuevo
        # (``investment_portfolios.id``): el puente es ``legacy_portfolio_id``.
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
                    select(PositionRow).where(
                        PositionRow.portfolio_id.in_(legacy_ids),
                        PositionRow.instrument_id == instrument_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        sides = {(c.side or "").strip().lower() for c in contexts}

        # (1) Ningún fill sin materializar.
        assert {"buy", "sell"} <= sides, (
            f"el día AUTO no completó el ciclo BUY→SELL: lados con contexto = {sorted(sides)}"
        )
        stuck = sorted({str(e.status) for e in events} - {"APPLIED"})
        assert not stuck, (
            f"día AUTO con ExecutionEvents fuera de APPLIED: {stuck} "
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
            f"el día AUTO debe dejar el libro plano: quedan {remaining} de {instrument_id} "
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
        # P&L cerrado desde el espejo de fills (fuente independiente del ``cash``):
        # el neto de notionales del día es, en un libro plano, el resultado realizado.
        # AUTO-1A (P0.6): solo fills ``APPLIED`` (el contexto se persiste antes de mover
        # dinero ⇒ sumarlo entero contabilizaba chunks en ``RETRY``).
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


@pytest.mark.asyncio
async def test_a9_scheduler_process_full_day_pg_zero_human(
    sched_process_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El proceso scheduler real conduce BUY→HOLD→SELL de un día AUTO (P2-04).

    Config: ``AUTO_SIMULATION_WORKER_ENABLED=1`` + ``AUTO_ENGINE_SIM_SPINE_AUTO=1`` +
    cuenta SIM inequívoca + venue ``simulated`` + intervalo corto. Sin HTTP, sin UI,
    sin ``run_tick()`` manual, sin decider scripteado. Se comprueba que el scheduler,
    por sí solo, produce ticks/fills/ledger y deja el libro plano.

    V2.40.3: el test espera al CIERRE del día (SELL liquidado y ninguna traza sin
    materializar) en vez de cortar al 3er tick, y certifica (a) que ningún fill quedó
    sin mover dinero, (b) que la posición canónica vuelve a cero y (c) el invariante de
    equity del dominio sobre el ledger real. La identidad del instrumento se elige de
    forma determinista para que el día simulado sea reproducible
    (``_filling_instrument_id``).
    """

    instrument_id = _filling_instrument_id(_CERT_INSTRUMENT_PREFIX, side="buy")
    engine_id = f"auto-a9proc-{uuid.uuid4().hex[:8]}"
    account_id: str | None = None
    log_path = Path(tempfile.gettempdir()) / f"a9proc-{engine_id}.log"

    # Semilla: cuenta SIM (aislada por id) + instrumento fijo + watch en el env.
    await _seed_instrument(sched_process_factory, instrument_id=instrument_id, symbol=_CERT_SYMBOL)
    async with sched_process_factory() as session:
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        account_id = (
            await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"AUTO-A9PROC-{uuid.uuid4().hex[:8]}",
                initial_deposit=100_000.0,
            )
        ).account.id
        await session.commit()

    env = os.environ.copy()
    env.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "1",
            "AUTO_ENGINE_SIM_ACCOUNT_ID": account_id,
            "AUTO_ENGINE_SIM_ENGINE_ID": engine_id,
            "AUTO_ENGINE_SIMULATED_VENUE": "simulated",
            "AUTO_ENGINE_SIMULATED_WATCH": instrument_id,
            "AUTO_ENGINE_SIM_INTERVAL_SECONDS": "1.0",
            "AUTO_ENGINE_SIM_LOT_QTY": "100",
            "PYTHONUNBUFFERED": "1",
        }
    )

    proc = subprocess.Popen(  # noqa: S603 — comando fijo del repo.
        [sys.executable, "-m", "bolsa_api.workers.scheduler_worker"],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=open(log_path, "w", encoding="utf-8"),  # noqa: SIM115 — cerrado abajo.
        stderr=subprocess.STDOUT,
    )
    try:
        # Deja correr el proceso el tiempo suficiente para varios ticks (BUY→…→SELL).
        # Todo se cuenta SCOPED a este engine_id/cuenta (nunca global): un día AUTO
        # solo es válido si ESTE proceso produjo SUS ticks/fills/ledger.
        #
        # Robustez ante carga: el subproceso paga import de la app + bootstrap de BD
        # antes de emitir su primer tick, y bajo un job completo (miles de tests) ese
        # arranque puede alargarse. Se espera por PROGRESO real con holgura de arranque
        # (``_STARTUP_GRACE_S``) y se falla AL INSTANTE con el log del subproceso si el
        # proceso muere, en vez de agotar el plazo a ciegas y reportar «0 eventos».
        #
        # V2.40.3: el progreso que se espera es el DÍA COMPLETO (SELL liquidado), sin
        # ninguna traza sin materializar y con el libro plano — y ese estado tiene que
        # MANTENERSE durante varios sondeos. No basta «un instante favorable»: el ciclo
        # BUY→SELL se materializa en tranchas a lo largo de varios ticks, así que un
        # ``pending == 0`` puntual puede ser una pausa entre dos tranchas de la misma
        # orden y la comprobación siguiente vería un ``APPLYING`` en vuelo (falso rojo
        # del gate «ningún fill sin materializar»). Antes se cortaba al 3er tick —media
        # jornada, posición abierta— y el gate de «libro plano» fallaba por construcción.
        ticks = events = ledger = 0
        sides: set[str] = set()
        pending = 1
        remaining = Decimal("0")
        closed_polls = 0
        deadline = time.monotonic() + _STARTUP_GRACE_S
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                # Murió (crash o kill externo): no tiene sentido seguir esperando.
                raise AssertionError(
                    _proc_failure(
                        f"el proceso scheduler terminó (exit={proc.returncode}) sin producir ticks",
                        log_path,
                    )
                )
            ticks = await _count_scoped_ticks(sched_process_factory, engine_id)
            events = await _count_scoped_events(sched_process_factory, account_id)
            ledger = await _count_scoped_ledger(sched_process_factory, account_id)
            if ticks >= 3 and events >= 2 and ledger >= 2:
                sides, pending, remaining = await _day_progress(sched_process_factory, account_id)
                if {"buy", "sell"} <= sides and pending == 0 and remaining == 0:
                    closed_polls += 1
                    if closed_polls >= _CLOSED_DAY_POLLS:
                        break
                else:
                    closed_polls = 0  # el día sigue vivo: reinicia la cuenta de calma
        assert ticks > 0, _proc_failure("el proceso scheduler debe persistir SUS ticks", log_path)
        assert events > 0, _proc_failure(
            "el día AUTO del proceso debe tener ExecutionEvents", log_path
        )
        assert ledger > 0, _proc_failure(
            "el día AUTO del proceso debe mover el ledger real", log_path
        )
        assert {"buy", "sell"} <= sides, _proc_failure(
            f"el día AUTO del proceso debe cerrar el ciclo BUY→SELL (lados={sorted(sides)}, "
            f"ticks={ticks}, events={events}, ledger={ledger})",
            log_path,
        )
        assert pending == 0, _proc_failure(
            f"el día AUTO deja {pending} ExecutionEvents sin materializar (RETRY/CAPTURED)",
            log_path,
        )
        assert remaining == 0, _proc_failure(
            f"el día AUTO no deja el libro plano: quedan {remaining} ({instrument_id})",
            log_path,
        )

        # Zero human / zero LIVE: ninguna traza de ESTA cuenta con venue live.
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow as EvRow

        async with sched_process_factory() as session:
            bad = (
                await session.execute(
                    select(func.count())
                    .select_from(EvRow)
                    .where(
                        EvRow.account_id == account_id,
                        func.lower(EvRow.venue).in_(
                            ("live", "broker_live", "xtb", "real", "live_bridge")
                        ),
                    )
                )
            ).scalar()
        assert int(bad or 0) == 0, "el proceso AUTO no debe publicar al bridge LIVE"

        # V2.40.3 (P2-A/P2-B): cierre REAL del día AUTO — ningún fill sin materializar,
        # libro plano e invariante de equity del dominio sobre el ledger real.
        if os.environ.get("AUTO_EQUITY_INVARIANT_PG_REQUIRED") == "1":
            await _assert_full_day_closed(
                sched_process_factory,
                account_id=account_id,
                instrument_id=instrument_id,
            )
    finally:
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

    # Cleanup. El instrumento de certificación NO se borra: es una identidad fija
    # (día determinista) y el ledger de runs anteriores la referencia
    # (``ON DELETE SET NULL`` contaminaría asientos ya escritos).
    if account_id:
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import (
            SimAutoPositionRow as PosRow,
        )
        from bolsa_infrastructure.database.models.tables import (
            SimFillFinanceContextRow as CtxRow,
        )
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        async with sched_process_factory() as session:
            await session.execute(delete(PosRow).where(PosRow.account_id == account_id))
            await session.execute(delete(CtxRow).where(CtxRow.account_id == account_id))
            try:
                await SqlAlchemyAccountRepository(session).close_account(account_id)
            except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                pass
            await session.commit()


# ── V2.24.2 (P2-D): restart REAL del proceso con posición + protección abierta ────


async def _scoped_buy_orders(factory: async_sessionmaker[AsyncSession], account_id: str) -> int:
    """ÓRDENES BUY distintas de la cuenta (para probar que el restart no re-compró).

    ``execution_events`` no tiene columna ``side``; el lado va embebido en
    ``venue_order_id`` (``sim-{engine}-{acct}-{side}-...``, P1-03), así que se filtra
    por ese patrón, scoped a la cuenta.

    V2.40.3 — se cuentan **órdenes** (``count(distinct venue_order_id)``) y **no filas**:
    un evento es una *trancha* de fill, y las tranchas de la MISMA orden se materializan
    a lo largo de varios ticks (una quedó ``APPLYING`` en vuelo al matar el proceso y su
    hermana se aplicó tras el restart). Contar filas convertía el invariante "no re-comprar"
    en "no seguir liquidando la orden ya abierta", que no es lo que se certifica: en CI este
    test solo pasaba porque el bug de colisión de claves (V2.40.3/F1) congelaba el contador
    en 1 — verde falso. Una re-compra real es una ``venue_order_id`` NUEVA.
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


@pytest.mark.asyncio
async def test_a9_scheduler_process_restart_with_open_protected_position_pg(
    sched_process_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V2.24.2 (P2-D): el proceso scheduler se reinicia con posición ABIERTA.

    A diferencia del restart de A9.1 (a mitad de jornada, sin garantizar protección
    activa), aquí la posición queda abierta al matar el proceso con su estado de
    protección ya persistido. Tras el reinicio del MISMO engine el proceso debe
    readoptar la posición durable: NO vuelve a comprar (no se emite una ``venue_order_id``
    BUY nueva; las tranchas de la orden ya abierta sí pueden terminar de materializarse) y la
    fila de proyección sigue presente. Sin PostgreSQL real/credenciales hace skip;
    con ``AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1`` un skip es FALLO duro. NUNCA LIVE.
    """
    from bolsa_infrastructure.database.models.tables import SimAutoPositionRow as PosRow

    # V2.40.3: instrumento DETERMINISTA de la familia ``inst-a9restart-`` elegido por
    # ``_filling_instrument_id`` (mismo motivo que el día completo: el id decide el ruido
    # de cola del venue y con un id aleatorio ~12 % de las ejecuciones se quedaban sin
    # entrada ⇒ rojo espurio del test, no defecto del motor).
    instrument_id = _filling_instrument_id(_RESTART_INSTRUMENT_PREFIX, side="buy")
    engine_id = f"auto-a9restart-{uuid.uuid4().hex[:8]}"
    account_id: str | None = None
    log_path = Path(tempfile.gettempdir()) / f"a9restart-{engine_id}.log"

    async with sched_process_factory() as session:
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        account_id = (
            await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"AUTO-A9RESTART-{uuid.uuid4().hex[:8]}",
                initial_deposit=100_000.0,
            )
        ).account.id
        await session.commit()

    # Instrumento determinista: se siembra solo si NO existe (mismo criterio que el día
    # completo: borrarlo rompería las referencias de runs anteriores y el id fijo es lo
    # que hace reproducible el ruido de cola del venue).
    await _seed_instrument(
        sched_process_factory,
        instrument_id=instrument_id,
        symbol=f"R9{uuid.uuid4().hex[:6].upper()}",
    )

    env = os.environ.copy()
    env.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "1",
            "AUTO_ENGINE_SIM_ACCOUNT_ID": account_id,
            "AUTO_ENGINE_SIM_ENGINE_ID": engine_id,
            "AUTO_ENGINE_SIMULATED_VENUE": "simulated",
            "AUTO_ENGINE_SIMULATED_WATCH": instrument_id,
            "AUTO_ENGINE_SIM_INTERVAL_SECONDS": "1.0",
            "AUTO_ENGINE_SIM_LOT_QTY": "100",
            # Retén largo: la posición debe seguir ABIERTA cuando matemos el proceso.
            "AUTO_ENGINE_SIM_EXIT_AFTER_TICKS": "1000",
            "PYTHONUNBUFFERED": "1",
        }
    )

    def _spawn() -> subprocess.Popen[bytes]:
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

    proc = _spawn()
    try:
        # Espera a que el proceso EMITA una orden BUY durable antes de matarlo.
        # Igual que en el escenario de día completo: se espera por progreso real con
        # holgura de arranque y se falla al instante si el subproceso muere.
        buys_before = 0
        deadline = time.monotonic() + _STARTUP_GRACE_S
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                raise AssertionError(
                    _proc_failure(
                        f"el proceso scheduler terminó (exit={proc.returncode}) antes de "
                        "abrir posición",
                        log_path,
                    )
                )
            buys_before = await _scoped_buy_orders(sched_process_factory, account_id)
            if buys_before > 0:
                break
        assert buys_before > 0, _proc_failure(
            "el proceso debe abrir (BUY durable) antes del restart", log_path
        )

        # Crash + restart del MISMO engine sobre la MISMA BD.
        await _stop(proc)
        proc = _spawn()

        # El restart debe readoptar (NO re-comprar): las órdenes BUY no se doblan.
        #
        # OJO: aquí NO se espera «a que pase algo». El camino CORRECTO es que nunca
        # ocurra una segunda orden, así que un bucle «hasta que buys_after crezca o
        # venza el plazo» agotaría SIEMPRE el presupuesto entero de arranque (el bug
        # de los 180s×2). Se sondea un plazo corto y acotado: si el restart fuese a
        # re-comprar lo haría en sus primeros ticks, no al final. Un margen corto
        # detecta igual la re-compra y no convierte el caso feliz en una espera larga.
        #
        # V2.40.3: el invariante es sobre ÓRDENES, no sobre tranchas de fill (ver
        # ``_scoped_buy_orders``): el restart puede legítimamente materializar la
        # trancha que quedó en vuelo al matar el proceso, y eso no es una re-compra.
        buys_after = buys_before
        deadline = time.monotonic() + _RESTART_WATCH_S
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                raise AssertionError(
                    _proc_failure(
                        f"el proceso scheduler terminó (exit={proc.returncode}) tras el restart",
                        log_path,
                    )
                )
            buys_after = await _scoped_buy_orders(sched_process_factory, account_id)
            if buys_after > buys_before:
                break  # re-compra detectada: falla abajo con diagnóstico.
        assert buys_after == buys_before, _proc_failure(
            "el restart con posición abierta NO debe re-comprar (readopción durable)",
            log_path,
        )
    finally:
        await _stop(proc)

    # Cleanup (el instrumento se deja: identidad determinista compartida entre runs).
    if account_id:
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import (
            SimFillFinanceContextRow as CtxRow,
        )
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        async with sched_process_factory() as session:
            await session.execute(delete(PosRow).where(PosRow.account_id == account_id))
            await session.execute(delete(CtxRow).where(CtxRow.account_id == account_id))
            try:
                await SqlAlchemyAccountRepository(session).close_account(account_id)
            except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                pass
            await session.commit()
