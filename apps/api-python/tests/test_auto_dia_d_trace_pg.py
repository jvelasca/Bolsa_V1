"""Verificación EJECUTABLE (PG real) — traza DÍA-D extremo a extremo + P&L conciliado.

CERTIFICA (plan ``verificación AUTO/DÍA-D``, slice ``S3``):

1. El ciclo **CERRADO producido por el PROCESO** scheduler real (no sembrado) enciende
   las NUEVE etapas canónicas —``SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL →
   PROTECTION → SETTLEMENT → CYCLE_CLOSED``— leyendo HECHOS DURABLES. Se **enumeran**
   los ``unknown``/``absent``; no se admite ninguno silencioso.
2. **Conciliación de P&L**: el realizado del cierre reconstruido por el monitor
   (``CYCLE_CLOSED.pnl``) y el realizado declarado por la **liquidación durable**
   (``SETTLEMENT.pnl``) coinciden con la reconstrucción INDEPENDIENTE desde el libro
   aplicado (``realized_notional_from_applied_fills``, la MISMA fuente del invariante de
   equity del Golden Day). Igualdad decimal exacta **al quantum del dinero**
   (``NUMERIC(18, 6)``): el monitor reconstruye en 12 decimales y el libro cuantiza cada
   fill a 6, así que la identidad se exige en el quantum representable del ledger.
3. **Controles negativos**: un ``cycleId`` ajeno NO hereda el ``SIGNAL``; el drill-down
   devuelve el ciclo pedido con las etapas SIN encender (nunca finge un hecho).

MÉTODO: reutiliza el arnés de PROCESO REAL de ``test_golden_day_v2_process_pg.py``
(``python -m bolsa_api.workers.scheduler_worker``, ``AUTO_OPERATIONAL_AUDIT=1``,
``read_operational_monitor``), con UN instrumento (el mínimo para producir un ciclo
cerrado) para acotar el coste. El sandbox corre con el precio PLANO inyectado
(``flat_price_script``) y cierre por ``time_exit``: la conciliación certifica la
IDENTIDAD de fuentes (monitor ↔ libro aplicado), no la magnitud del resultado.

RÉGIMEN DECLARADO: camino SIM (``AUTO_ENGINE_SIM_V2``), NUNCA bridge LIVE.

GOBIERNO DE HONESTIDAD: sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_DIA_D_TRACE_PG_REQUIRED=1`` (job ``lifecycle-pg``) un skip silencioso es FALLO.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Arnés de proceso real reutilizado (mismo día, mismos helpers: NO se duplica el motor).
from tests.test_golden_day_v2_process_pg import (
    _CANONICAL_STEPS,
    _CLOSE_POLLS,
    _CLOSED_DAY_POLLS,
    _INSTRUMENT_PREFIXES,
    _OPEN_POLLS,
    _SECTORS,
    _SYMBOLS,
    _assert_materialized_and_flat,
    _count_positions,
    _day_progress,
    _durable_fact_health,
    _env_for,
    _expire_holding_deadlines,
    _filling_instrument_id,
    _monitor_steps,
    _proc_failure,
    _read_monitor_cycles,
    _seed_account,
    _seed_edge_report,
    _seed_instrument,
    _spawn,
    _stop,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_DIA_D_TRACE_PG_REQUIRED"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la traza DÍA-D pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (traza DÍA-D) no disponible: {exc}")


@pytest_asyncio.fixture
async def trace_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    if _DOTENV.exists():
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


def _facts(step: dict[str, Any]) -> dict[str, Any]:
    return {str(fact.get("key")): fact.get("value") for fact in (step.get("facts") or [])}


#: Quantum del DINERO (``NUMERIC(18, 6)`` en el ledger). El monitor reconstruye el
#: realizado con aritmética FIFO de 12 decimales (sin cuantizar por fill), mientras el
#: libro aplicado cuantiza cada fill a 6 (ver ``applied_fill_equity``). La conciliación
#: se exige EXACTA al quantum representable del dinero, que es el contrato real.
_MONEY = Decimal("0.000001")


def _to_money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)


async def _gross_notional(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> Decimal:
    """Notional BRUTO (suma de |qty·price|) de los fills de la cuenta.

    Hace la conciliación NO vacua: un realizado 0 solo es informativo si el día movió
    dinero de verdad (bruto > 0), no si no hubo fills.
    """
    from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

    async with factory() as session:
        rows = (
            await session.execute(
                select(
                    SimFillFinanceContextRow.quantity,
                    SimFillFinanceContextRow.price,
                ).where(SimFillFinanceContextRow.account_id == account_id)
            )
        ).all()
    gross = Decimal("0")
    for quantity, price in rows:
        if quantity is None or price is None:
            continue
        gross += abs(Decimal(str(quantity)) * Decimal(str(price)))
    return gross


@pytest.mark.asyncio
async def test_dia_d_chain_is_fully_traced_and_pnl_reconciled_pg(
    trace_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El ciclo cerrado del PROCESO enciende las 9 etapas y su P&L cuadra con el libro."""
    from tests.applied_fill_equity import realized_notional_from_applied_fills

    instrument_id = _filling_instrument_id(_INSTRUMENT_PREFIXES[0])
    engine_id = f"auto-diad-{uuid.uuid4().hex[:8]}"
    log_path = Path(tempfile.gettempdir()) / f"diad-{engine_id}.log"
    account_id: str | None = None
    edge_report_id: str | None = None
    proc: Any = None

    try:
        account_id = await _seed_account(trace_pg_factory)
        await _seed_instrument(
            trace_pg_factory,
            instrument_id=instrument_id,
            symbol=_SYMBOLS[0],
            sector=_SECTORS[0],
        )
        edge_report_id = await _seed_edge_report(
            trace_pg_factory, account_id=account_id, strategy_ref="unversioned"
        )

        env = _env_for(account_id, engine_id, instrument_ids=[instrument_id])

        # ── FASE 1: apertura (una posición con fill materializado) ────────────────
        proc = _spawn(env, log_path)
        opened = 0
        for _ in range(_OPEN_POLLS):
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                raise AssertionError(
                    _proc_failure(
                        f"el proceso terminó (exit={proc.returncode}) antes de abrir",
                        log_path,
                    )
                )
            opened = await _count_positions(trace_pg_factory, account_id)
            if opened >= 1:
                break
        assert opened >= 1, _proc_failure("el proceso debe abrir la posición V2", log_path)

        # ── FASE 2: reinicio con el techo vencido ⇒ cierre por ``time_exit`` ──────
        await _stop(proc)
        proc = None
        expired = await _expire_holding_deadlines(trace_pg_factory, account_id)
        assert expired >= 1, f"debe vencer el techo durable (vencidos={expired})"

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
            sides, pending, remaining = await _day_progress(trace_pg_factory, account_id)
            if (
                await _count_positions(trace_pg_factory, account_id) == 0
                and {"buy", "sell"} <= sides
                and pending == 0
                and remaining == 0
            ):
                closed_polls += 1
                if closed_polls >= _CLOSED_DAY_POLLS:
                    break
            else:
                closed_polls = 0
        assert await _count_positions(trace_pg_factory, account_id) == 0, _proc_failure(
            "el día debe cerrar el plan durable (time_exit + rehidratación)", log_path
        )
        assert {"buy", "sell"} <= sides, _proc_failure(
            f"el ciclo debe ser BUY→SELL (lados={sorted(sides)})", log_path
        )
        assert pending == 0, _proc_failure(
            f"quedan {pending} ExecutionEvents sin materializar", log_path
        )
        assert remaining == 0, _proc_failure("el libro no queda plano", log_path)
        await _assert_materialized_and_flat(trace_pg_factory, account_id=account_id)

        # ── Traza: 9 etapas canónicas desde HECHOS DURABLES (sin ``unknown`` silencioso) ──
        cycles = await _read_monitor_cycles(
            trace_pg_factory, account_id=account_id, engine_id=engine_id
        )
        assert cycles, "el monitor debe reconstruir al menos un ciclo del material durable"
        closed_cycle = next((c for c in cycles if c.get("closed") is True), None)
        assert closed_cycle is not None, (
            "debe existir un ciclo CERRADO reconstruido del día del worker; "
            f"ciclos={[c.get('cycleId') for c in cycles]}"
        )
        cycle_steps = _monitor_steps(closed_cycle)
        not_reached = {
            step_id: (cycle_steps.get(step_id) or {}).get("state")
            for step_id in _CANONICAL_STEPS
            if (cycle_steps.get(step_id) or {}).get("state") != "reached"
        }
        assert not not_reached, (
            "el ciclo del WORKER debe encender las NUEVE etapas canónicas desde hechos "
            f"durables; sin encender={not_reached} (cycleId={closed_cycle.get('cycleId')!r})"
        )

        # ── Conciliación de P&L: monitor ↔ liquidación durable ↔ libro aplicado ───
        async with trace_pg_factory() as session:
            ledger_realized = await realized_notional_from_applied_fills(session, account_id)
        closed_facts = _facts(cycle_steps["CYCLE_CLOSED"])
        assert "pnl" in closed_facts, (
            f"CYCLE_CLOSED debe declarar su ``pnl`` reconstruido; facts={closed_facts}"
        )
        monitor_pnl = _to_money(closed_facts["pnl"])
        assert monitor_pnl == _to_money(ledger_realized), (
            "el realizado de CYCLE_CLOSED debe cuadrar EXACTO al quantum del dinero con "
            f"el libro aplicado: monitor={monitor_pnl} libro={ledger_realized}"
        )
        settlement_facts = _facts(cycle_steps["SETTLEMENT"])
        if settlement_facts.get("pnl") is not None:
            assert _to_money(settlement_facts["pnl"]) == _to_money(ledger_realized), (
                "la liquidación durable debe declarar el MISMO realizado que el libro: "
                f"settlement={settlement_facts['pnl']} libro={ledger_realized}"
            )
        # La igualdad no es vacua: el día movió dinero (bruto > 0) con AMBOS lados.
        gross = await _gross_notional(trace_pg_factory, account_id)
        assert gross > 0, "el día debe mover notional bruto > 0 (si no, la conciliación no dice nada)"

        # Los hechos durables (orden/settlement/protección) llevan identidad determinista.
        health = await _durable_fact_health(trace_pg_factory, account_id)
        assert health["nullKey"] == 0, (
            f"ningún hecho durable puede quedar sin ``dedupe_key``; salud={health}"
        )
        assert not health["duplicates"], (
            f"bajo exactly-once no puede haber ``dedupe_key`` repetida; salud={health}"
        )

        # ── Control NEGATIVO: un ``cycle_id`` ajeno NO hereda hechos ──────────────
        foreign_id = "cyc-foreign-does-not-exist-000000"
        foreign = await _read_monitor_cycles(
            trace_pg_factory, account_id=account_id, engine_id=engine_id, cycle_id=foreign_id
        )
        assert [c.get("cycleId") for c in foreign] == [foreign_id], (
            "el drill-down por ciclo debe devolver EL ciclo pedido, no otro"
        )
        foreign_steps = _monitor_steps(foreign[0])
        assert (foreign_steps.get("SIGNAL") or {}).get("state") != "reached", (
            "un ``cycle_id`` ajeno NO puede heredar el SIGNAL de otro ciclo"
        )
        assert (foreign_steps.get("SETTLEMENT") or {}).get("state") != "reached", (
            "un ``cycle_id`` ajeno NO puede heredar la liquidación de otro ciclo"
        )

        # ── Reloj: la traza se ancla en HECHOS (fechas durables), no en el reloj de máquina ──
        # El cierre declarado por el monitor viene del hecho durable (``closedAt``) y es
        # determinista entre lecturas: repetir la consulta no cambia la traza.
        again = await _read_monitor_cycles(
            trace_pg_factory, account_id=account_id, engine_id=engine_id
        )
        again_closed = next((c for c in again if c.get("closed") is True), None)
        assert again_closed is not None
        assert again_closed.get("cycleId") == closed_cycle.get("cycleId")
        assert _facts(_monitor_steps(again_closed)["CYCLE_CLOSED"])["pnl"] == closed_facts["pnl"]

        # NUNCA bridge LIVE (régimen SIM declarado).
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        async with trace_pg_factory() as session:
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
        assert bad == 0, "la traza DÍA-D NUNCA debe publicar al bridge LIVE"
    finally:
        if proc is not None:
            await _stop(proc)
        if account_id is not None:
            from bolsa_infrastructure.database.models.tables import (
                DecisionJournalEntryRow,
                ExecutionEventRow,
                SimAutoPositionRow,
                SimConsumedSignalRow,
                SimFillFinanceContextRow,
            )
            from bolsa_infrastructure.database.repositories.account_repository import (
                SqlAlchemyAccountRepository,
            )

            async with trace_pg_factory() as session:
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
                await session.execute(
                    delete(DecisionJournalEntryRow).where(
                        DecisionJournalEntryRow.account_id == account_id
                    )
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
