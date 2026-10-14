"""Verificación EJECUTABLE (PG real) — evidencia de la cadena AUTO POR VALOR de ESTUDIO.

CERTIFICA (plan ``evidencia funcional AUTO por valor ESTUDIO``, fase 3):

1. El **PROCESO real** (``python -m bolsa_api.workers.scheduler_worker``) conduce el pipeline
   AUTO 2.0 sobre el universo **ESTUDIO** sembrado (``AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO=1``
   y ``AUTO_OPERATIONAL_AUDIT=1``) y produce, por cada valor, un ciclo **CERRADO**.
2. La evidencia por valor (``read_estudio_chain_evidence`` + ``build_chain_evidence_artifact``)
   enciende las **NUEVE etapas** de cada ciclo desde HECHOS DURABLES: la proyección del lado
   ejecutado vale ``1`` en TODAS; un ``None`` es un hueco real (no se admite).
3. La identidad de la estrategia **EJECUTADA** (``strategyPresetKey``/``strategyVersion``) viaja
   sellada por el ciclo, y el contraste con la **mejor puntuada** nunca fabrica un ``False`` sin
   término de comparación (``executedVsBest`` es ``True``/``False``/``None``); además, el preset de
   la mejor puntuada es un hueco DECLARADO (la foto cross-asset no sella identidad) y el resolutor
   canónico del valor declara la identidad única o **AMBIGUA** (nunca elige «ganadora»).
4. El último eslabón se contrasta con fuente INDEPENDIENTE: la verificación DÍA-D del ciclo
   (``executedVsDiaD``) y su ``linkable``/borrador (``diaDLink``, helper canónico reutilizado);
   sin verificación durable no se fabrica coincidencia ni divergencia.
5. La conciliación de P&L cuadra: ``CYCLE_CLOSED.pnl == SETTLEMENT.pnl`` por ciclo y la suma
   cuadra EXACTA al libro aplicado (fuente INDEPENDIENTE) al quantum del dinero.
6. **Control negativo**: un ``cycleId`` ajeno NO hereda hechos ni completa su cadena.

GOBIERNO DE HONESTIDAD: sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_ESTUDIO_CHAIN_PG_REQUIRED=1`` (job ``lifecycle-pg``) un skip silencioso es FALLO.
NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
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
from tests._estudio_pg_helpers import restore_estudio, set_estudio
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
    _env_for,
    _expire_holding_deadlines,
    _filling_instrument_id,
    _proc_failure,
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
_REQUIRED_ENV = "AUTO_ESTUDIO_CHAIN_PG_REQUIRED"
#: Flag que acopla el watch diario al universo canónico ESTUDIO.
_ENV_WATCH_FROM_ESTUDIO = "AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO"

#: Quantum del DINERO (``NUMERIC(18, 6)`` en el ledger).
_MONEY = Decimal("0.000001")


def _require_or_skip(exc: Exception) -> None:
    import os

    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la evidencia de cadena ESTUDIO pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (evidencia de cadena ESTUDIO) no disponible: {exc}")


@pytest_asyncio.fixture
async def chain_pg_factory() -> async_sessionmaker[AsyncSession]:
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


def _to_money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)


async def _read_evidence(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    engine_id: str,
    study_instruments: list[str],
    cycle_id: str | None = None,
) -> dict[str, Any]:
    """Lee la evidencia de cadena por valor con el lector NUEVO (read-only)."""
    from bolsa_application.auto_chain_durable_reader import (
        build_chain_evidence_artifact,
        read_estudio_chain_evidence,
    )

    async with factory() as session:
        if cycle_id is not None:
            read = await read_estudio_chain_evidence(
                session, account_id, engine_id=engine_id, cycle_id=cycle_id
            )
        else:
            read = await read_estudio_chain_evidence(session, account_id, engine_id=engine_id)
    return build_chain_evidence_artifact(
        account_id=account_id,
        estudio={"status": "ok", "instrumentIds": list(study_instruments)},
        cycles=read["cycles"],
        best_scored=read["bestScored"],
    )


async def _gross_notional(factory: async_sessionmaker[AsyncSession], account_id: str) -> Decimal:
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
async def test_estudio_chain_evidence_covers_nine_steps_per_value_pg(
    chain_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Cada valor de ESTUDIO enciende las 9 etapas desde durable y su P&L concilia."""
    from tests.applied_fill_equity import realized_notional_from_applied_fills

    instrument_ids = [_filling_instrument_id(prefix) for prefix in _INSTRUMENT_PREFIXES[:2]]
    symbols = _SYMBOLS[:2]
    sectors = _SECTORS[:2]
    engine_id = f"auto-estchain-{uuid.uuid4().hex[:8]}"
    log_path = Path(tempfile.gettempdir()) / f"estchain-{engine_id}.log"
    account_id: str | None = None
    edge_report_id: str | None = None
    originals: list[str] | None = None
    proc: Any = None

    try:
        account_id = await _seed_account(chain_pg_factory)
        for instrument_id, symbol, sector in zip(instrument_ids, symbols, sectors, strict=True):
            await _seed_instrument(
                chain_pg_factory, instrument_id=instrument_id, symbol=symbol, sector=sector
            )
        edge_report_id = await _seed_edge_report(
            chain_pg_factory, account_id=account_id, strategy_ref="unversioned"
        )
        # ESTUDIO es el universo CANÓNICO: se ancla al lote sembrado (no destructivo).
        originals = await set_estudio(chain_pg_factory, instrument_ids)
        env = _env_for(
            account_id,
            engine_id,
            instrument_ids=instrument_ids,
            extra={_ENV_WATCH_FROM_ESTUDIO: "1"},
        )

        # ── FASE 1: apertura (una posición por valor) ─────────────────────────────
        proc = _spawn(env, log_path)
        opened = 0
        for _ in range(_OPEN_POLLS):
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                raise AssertionError(
                    _proc_failure(
                        f"el proceso terminó (exit={proc.returncode}) antes de abrir", log_path
                    )
                )
            opened = await _count_positions(chain_pg_factory, account_id)
            if opened >= len(instrument_ids):
                break
        assert opened >= len(instrument_ids), _proc_failure(
            f"el proceso debe abrir una posición por valor de ESTUDIO (abiertas={opened} de "
            f"{len(instrument_ids)})",
            log_path,
        )

        # ── FASE 2: reinicio con el techo vencido ⇒ cierre por ``time_exit`` ───────
        await _stop(proc)
        proc = None
        expired = await _expire_holding_deadlines(chain_pg_factory, account_id)
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
                        f"el proceso terminó (exit={proc.returncode}) durante el cierre", log_path
                    )
                )
            sides, pending, remaining = await _day_progress(chain_pg_factory, account_id)
            if (
                await _count_positions(chain_pg_factory, account_id) == 0
                and {"buy", "sell"} <= sides
                and pending == 0
                and remaining == 0
            ):
                closed_polls += 1
                if closed_polls >= _CLOSED_DAY_POLLS:
                    break
            else:
                closed_polls = 0
        assert await _count_positions(chain_pg_factory, account_id) == 0, _proc_failure(
            "el día debe cerrar TODOS los planes durables (time_exit + rehidratación)", log_path
        )
        assert {"buy", "sell"} <= sides, _proc_failure(
            f"cada ciclo debe ser BUY→SELL (lados={sorted(sides)})", log_path
        )
        assert pending == 0, _proc_failure(
            f"quedan {pending} ExecutionEvents sin materializar", log_path
        )
        assert remaining == 0, _proc_failure("el libro no queda plano", log_path)
        await _assert_materialized_and_flat(chain_pg_factory, account_id=account_id)

        # ── Evidencia POR VALOR de ESTUDIO (lector nuevo) ─────────────────────────
        artifact = await _read_evidence(
            chain_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            study_instruments=instrument_ids,
        )
        assert artifact["readOnly"] is True
        # La foto del selector no sella identidad: si viaja, el preset de la mejor puntuada es un
        # hueco DECLARADO (``UNKNOWN ≠ 0``), nunca el de la estrategia ejecutada.
        if artifact["bestScored"] is not None:
            assert artifact["bestScored"]["bestScoredPresetKey"] is None
            assert artifact["bestScored"]["strategyMeasurement"] == "UNKNOWN"
        by_id = {value["instrumentId"]: value for value in artifact["values"]}
        assert set(by_id) == set(instrument_ids), (
            f"la evidencia debe cubrir CADA valor de ESTUDIO; valores={sorted(by_id)}"
        )

        async with chain_pg_factory() as session:
            ledger_realized = await realized_notional_from_applied_fills(session, account_id)

        monitor_total = Decimal("0")
        seen_instruments: set[str] = set()
        for instrument_id in instrument_ids:
            value = by_id[instrument_id]
            assert value["measured"] is True, (
                f"el valor {instrument_id} de ESTUDIO no tiene ningún ciclo; ciclos={value['cycles']}"
            )
            assert value["cycles"], f"{instrument_id} debe declarar al menos un ciclo"
            # 0) El resolutor CANÓNICO del valor (reutilizado del informe por valor) declara la
            #    identidad ejecutada sin inventar una «ganadora»: única, o AMBIGUA declarada.
            strategy = value["strategy"]
            declared_presets = {
                cycle["executed"]["strategyPresetKey"]
                for cycle in value["cycles"]
                if cycle["executed"]["strategyPresetKey"]
            }
            if len(declared_presets) == 1:
                assert strategy["presetKey"] == next(iter(declared_presets))
                assert strategy["presetKeyAmbiguous"] is False
            elif not declared_presets:
                assert strategy["presetKey"] is None
                assert strategy["presetKeyAmbiguous"] is False
            else:
                assert strategy["presetKey"] is None, (
                    "identidades distintas en el valor NO eligen una «ganadora»: "
                    f"{sorted(declared_presets)}"
                )
                assert strategy["presetKeyAmbiguous"] is True
            # Todo ciclo del valor queda clasificado (enlazable / sin ``cycleId`` / repetido).
            assert len(strategy["cycles"]) + strategy["unlinkedCycles"] + strategy[
                "duplicateCycles"
            ] == len(value["cycles"])
            assert value["strategyDiaD"]["verifications"] == sum(
                1 for cycle in value["cycles"] if cycle["diaD"] is not None
            )
            for cycle in value["cycles"]:
                cycle_id = str(cycle["cycleId"])
                # 1) Las NUEVE etapas encendidas desde durable: ningún ``None``.
                not_reached = {
                    step: cycle["steps"].get(step)
                    for step in _CANONICAL_STEPS
                    if cycle["steps"].get(step) != 1
                }
                assert not not_reached, (
                    f"el ciclo {cycle_id} de {instrument_id} debe encender las NUEVE etapas "
                    f"desde hechos durables; sin encender={not_reached} "
                    f"(states={cycle['chain']['notReached']})"
                )
                assert cycle["chain"]["complete"] is True
                # 2) Identidad EJECUTADA sellada por el ciclo (no inferida del ranking). El
                #    sandbox corre una estrategia SIN versión: el preset/la versión viajan
                #    ``None`` (hueco DECLARADO, jamás un preset inventado), y el ``rank``
                #    durable del hecho de decisión sí viaja. Se exige que la identidad aporte
                #    AL MENOS el ``rank`` —la prueba de que NO se cae al #1 cuando no resuelve.
                executed = cycle["executed"]
                assert executed["measurement"] == "COMPLETE", (
                    f"el ciclo {cycle_id} debe declarar su identidad ejecutada como medida; "
                    f"executed={executed}"
                )
                assert isinstance(executed["rank"], int) and executed["rank"] > 0, (
                    f"el ciclo {cycle_id} debe sellar el ``rank`` durable de su estrategia "
                    f"ejecutada; executed={executed}"
                )
                # Como el sandbox no versiona la estrategia, el preset/versión son huecos
                # explícitos (None), nunca un relleno: es exactamente la doctrina ``UNKNOWN != 0``.
                preset = executed["strategyPresetKey"]
                assert preset is None or (
                    isinstance(preset, str) and preset.strip() == preset != ""
                ), f"un preset declarado no puede ser vacío ni con espacios: {preset!r}"
                assert cycle["executedVsBest"]["executedRank"] == executed["rank"]
                # 3) Contraste con la mejor puntuada: True/False/None (nunca fabricado).
                assert "executedIsTopRanked" in cycle["executedVsBest"]
                assert cycle["executedVsBest"]["executedIsTopRanked"] in (True, False, None)
                # 3b) La foto cross-asset NO sella identidad de estrategia: el preset de la
                #     MEJOR PUNTUADA es un hueco DECLARADO. Jamás se rellena con el de la
                #     ejecutada para fingir una coincidencia que la fuente no puede afirmar.
                assert cycle["executedVsBest"]["bestScoredPresetKey"] is None
                assert cycle["executedVsBest"]["presetMatch"] is None
                # 3c) El eslabón DÍA-D y su contraste INDEPENDIENTE con la identidad del ciclo:
                #     sin verificación durable NO se fabrica un ``False`` con una sola parte.
                assert isinstance(cycle["diaDLink"]["linkable"], bool)
                assert cycle["diaDLink"]["linkable"] is (cycle["diaD"] is not None)
                cross = cycle["executedVsDiaD"]
                assert cross["matches"] in (True, False, None)
                if cycle["diaD"] is None:
                    assert cross["matches"] is None, (
                        f"sin verificación DÍA-D no se puede afirmar coincidencia: {cross}"
                    )
                    assert cross["measurement"] == "UNKNOWN"
                else:
                    assert cross["measurement"] in ("COMPLETE", "UNKNOWN")
                # 4) Conciliación de P&L ciclo a ciclo (cierre vs liquidación durable).
                pnl = cycle["pnl"]
                assert pnl["reconciled"] is True, (
                    f"el P&L del ciclo {cycle_id} de {instrument_id} debe cuadrar (cierre vs "
                    f"liquidación): {pnl}"
                )
                monitor_total += _to_money(pnl["cycleClosedPnl"])
                seen_instruments.add(instrument_id)

        assert seen_instruments == set(instrument_ids), (
            f"debe haber evidencia por CADA valor de ESTUDIO; vistos={sorted(seen_instruments)}"
        )
        assert monitor_total == _to_money(ledger_realized), (
            "la suma de los ciclos debe cuadrar EXACTO con el libro aplicado: "
            f"ciclos={monitor_total} libro={ledger_realized}"
        )
        gross = await _gross_notional(chain_pg_factory, account_id)
        assert gross > 0, (
            "el día debe mover notional bruto > 0 (si no, la conciliación no dice nada)"
        )

        # ── Control NEGATIVO: un ``cycleId`` ajeno NO hereda hechos ────────────────
        foreign_id = "cyc-estchain-foreign-000000"
        foreign = await _read_evidence(
            chain_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            study_instruments=instrument_ids,
            cycle_id=foreign_id,
        )
        foreign_cycles = [
            cycle
            for value in foreign["values"]
            for cycle in value["cycles"]
            if cycle["cycleId"] == foreign_id
        ] + [cycle for cycle in foreign["cyclesOutsideEstudio"] if cycle["cycleId"] == foreign_id]
        assert foreign_cycles, "el drill-down por ciclo ajeno debe devolver el ciclo pedido"
        foreign_cycle = foreign_cycles[0]
        assert foreign_cycle["chain"]["complete"] is False, (
            "un ``cycleId`` ajeno NO puede encender la cadena"
        )
        assert foreign_cycle["steps"]["SIGNAL"] is None
        # Ni el eslabón DÍA-D ni su contraste se fabrican para un ciclo ajeno.
        assert foreign_cycle["diaDLink"]["linkable"] is False
        assert foreign_cycle["executedVsDiaD"]["matches"] is None

        # ── NUNCA bridge LIVE (régimen SIM declarado) ─────────────────────────────
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        async with chain_pg_factory() as session:
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
        assert bad == 0, "la evidencia de cadena NUNCA debe publicar al bridge LIVE"
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

            async with chain_pg_factory() as session:
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
        if originals is not None:
            await restore_estudio(chain_pg_factory, originals)
