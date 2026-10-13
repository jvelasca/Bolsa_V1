"""Verificación EJECUTABLE (PG real) — la lane diaria AUTO EVALÚA todo el universo ESTUDIO.

CERTIFICA (paso 2 del veredicto de auditoría; sello ``v2.88.124``) que, con el gate
``AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO`` ON y la lane diaria **REAL** (``AutoSimRuntime``
→ ``auto_turn``, no un stub) sobre PostgreSQL real:

(a) **COBERTURA POR VALOR.** Cada valor elegible de ESTUDIO **entra en el watch** y es
    **evaluado** por el turno (``report.decided`` los cuenta). Además, todo valor que
    **produce candidata BUY** deja **evidencia durable por símbolo** (hecho M2
    ``auto_entry_decision`` en ``decision_journal_entries`` con el ``AUTO_OPERATIONAL_AUDIT``
    ON, y/u otra fila ligada al símbolo en reservas/posición/TOP3).
(b) **AÑADIDO entra:** un valor añadido a ESTUDIO aparece en ``_watch_symbols()`` tras el
    refresco y deja hecho durable.
(c) **RETIRADO sale:** un valor retirado de ESTUDIO desaparece del watch y **no** emite
    hechos nuevos.
(d) **UNIVERSO VACÍO:** ``set_estudio([])`` + refresco ⇒ ``_watch_symbols() == []`` y el
    turno **no decide** (fail-closed).
(e) **ERROR de ESTUDIO:** un puerto/resolver que **lanza** ⇒ watch vacío y sin hechos
    nuevos (fail-closed; nunca cae al CSV).
(f) **EXCLUSIONES explícitas:** el CSV ``AUTO_ENGINE_SIMULATED_WATCH`` pasa a **allowlist
    que intersecta** (intersección ⇒ subconjunto; sin intersección ⇒ ``[]``).

HUECO DECLARADO (honestidad, no se maquilla): un valor **evaluado que NO opera**
(``HOLD`` o precio ausente) **NO** deja hoy **ningún hecho durable por símbolo** — solo el
contador **agregado** por tick (``auto_engine_ticks.decided``). El caso (a) lo hace
**falsable**: exige evidencia durable para los valores que producen candidata BUY, y para
el valor HOLD exige únicamente que **fue evaluado** (estuvo en el watch) y **no** exige (de
hecho declara la AUSENCIA de) fila ``auto_entry_decision`` por símbolo. NO se inventa un
hecho durable nuevo ni se cambia el motor.

RÉGIMEN y ENVS usadas (todas por ``monkeypatch``, reversibles): ``AUTO_ENGINE_SIMULATED_
WATCH_FROM_ESTUDIO=1`` (acopla el watch a ESTUDIO), ``AUTO_OPERATIONAL_AUDIT=1`` (sella los
hechos durables), ``AUTO_ENGINE_SIM_V2=1`` + ``AUTO_ENGINE_SIM_V2_REGIME=BULL_TREND`` +
``AUTO_ENGINE_SIM_V2_EQUITY=100000`` (pipeline AUTO 2.0), ``AUTO_ENGINE_SIMULATED_VENUE=
simulated`` y ``AUTO_SIMULATION_WORKER_ENABLED=1``. NUNCA abre el bridge LIVE.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_DAILY_COVERAGE_PG_REQUIRED=1`` (job ``lifecycle-pg``) un skip silencioso es un
FALLO duro. La siembra es **NO destructiva**: restaura la lista ESTUDIO previa y limpia los
instrumentos/hechos del lote.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.background import paper_auto_engine_worker as worker_mod
from bolsa_api.background.estudio_watch import SessionScopedEstudioList
from tests._estudio_pg_helpers import (
    add_to_estudio,
    cleanup_instrument,
    make_pg_session_factory,
    require_or_skip,
    restore_estudio,
    seed_instrument_with_trend,
    set_estudio,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_DAILY_COVERAGE_PG_REQUIRED"

#: Envs de la lane diaria (canónicas). El CSV pasa a allowlist solo con el flag ON.
_ENV_FROM_ESTUDIO = worker_mod._ENV_SIM_WATCH_FROM_ESTUDIO
_ENV_AUDIT = "AUTO_OPERATIONAL_AUDIT"
_ENV_V2 = "AUTO_ENGINE_SIM_V2"
_ENV_REGIME = "AUTO_ENGINE_SIM_V2_REGIME"
_ENV_EQUITY = "AUTO_ENGINE_SIM_V2_EQUITY"
_ENV_VENUE = "AUTO_ENGINE_SIMULATED_VENUE"
_ENV_WORKER = "AUTO_SIMULATION_WORKER_ENABLED"
_ENV_SIM_WATCH = worker_mod._ENV_SIM_WATCH
_ENV_DRY_WATCH = worker_mod._ENV_WATCH
_ENV_DRY_FROM_ESTUDIO = worker_mod._ENV_WATCH_FROM_ESTUDIO

#: Hecho M2 del journal durable por candidata (una fila por valor que compite con BUY).
_EVENT_ENTRY_DECISION = "auto_entry_decision"

#: Turnos reales por caso (un turno basta para cubrir el universo; 3 robustece el aserto
#: "tras N turnos" y cubre el caso de señal consumida en la MISMA barra).
_TICKS = 3


@pytest_asyncio.fixture
async def estudio_pg_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="cobertura diaria ESTUDIO")
        raise
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla el estado de módulo y limpia las envs de la lane entre casos."""
    for name in (
        _ENV_FROM_ESTUDIO,
        _ENV_DRY_FROM_ESTUDIO,
        _ENV_SIM_WATCH,
        _ENV_DRY_WATCH,
        _ENV_AUDIT,
        _ENV_V2,
        _ENV_REGIME,
        _ENV_EQUITY,
        _ENV_VENUE,
        _ENV_WORKER,
    ):
        monkeypatch.delenv(name, raising=False)
    worker_mod.reset_watch_memory_for_tests()
    yield
    worker_mod.reset_watch_memory_for_tests()


def _enable_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enciende la lane diaria REAL acoplada a ESTUDIO, con la auditoría M2 ON."""
    monkeypatch.setenv(_ENV_FROM_ESTUDIO, "1")
    monkeypatch.setenv(_ENV_AUDIT, "1")
    monkeypatch.setenv(_ENV_V2, "1")
    monkeypatch.setenv(_ENV_REGIME, "BULL_TREND")
    monkeypatch.setenv(_ENV_EQUITY, "100000")
    monkeypatch.setenv(_ENV_VENUE, "simulated")
    monkeypatch.setenv(_ENV_WORKER, "1")


@contextlib.asynccontextmanager
async def _seeded_lane(
    factory: async_sessionmaker[AsyncSession],
    count: int,
    *,
    add_all: bool = True,
) -> AsyncIterator[tuple[list[str], list[str]]]:
    """Siembra ``count`` instrumentos con tendencia; opcionalmente los AÑADE a ESTUDIO.

    NO destructivo: captura los originales de ESTUDIO (vía ``add_to_estudio``) y, al
    salir, limpia instrumentos y restaura la lista previa.
    """
    suffix = uuid.uuid4().hex[:8]
    instruments = [f"inst-acov-{suffix}-{index}" for index in range(count)]
    for index, instrument_id in enumerate(instruments):
        await seed_instrument_with_trend(
            factory,
            instrument_id=instrument_id,
            symbol=f"AC{suffix[:3].upper()}{index}",
        )
    originals = await add_to_estudio(factory, instruments if add_all else [])
    try:
        yield instruments, originals
    finally:
        for instrument_id in instruments:
            await cleanup_instrument(factory, instrument_id)
        await restore_estudio(factory, originals)


async def _seed_account(factory: async_sessionmaker[AsyncSession]) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    async with factory() as session:
        scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
            name=f"ACOV-{uuid.uuid4().hex[:8]}", initial_deposit=100_000.0
        )
        await session.commit()
        return str(scope.account.id)


def _make_lane(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    engine_id: str,
    buy_symbols: set[str],
) -> tuple[Any, Any]:
    """Compone el ``AutoSimRuntime`` REAL con un spine determinista BUY/HOLD por símbolo.

    El decider es el único seam inyectado (igual que ``test_auto_v2_durable_pg.py``): el
    runtime, los stores, el RiskGate y el sumidero M2 son los de producción. ``buy_symbols``
    es un ``set`` **mutable**: un caso puede añadir un valor y el spine lo ve al vuelo.
    """
    from bolsa_api.background import auto_simulation_worker as sim
    from bolsa_application.decision_contract import DecisionPackage

    def _decider(symbol: str) -> Any:
        is_buy = symbol in buy_symbols
        return DecisionPackage(
            action="BUY" if is_buy else "HOLD",
            instrument_id=symbol,
            quantity=100.0 if is_buy else 0.0,
        )

    engine = sim.AutoSimulationWorker(engine_id=engine_id, account_id=account_id, decider=_decider)
    runtime = sim.AutoSimRuntime(factory, worker=engine, engine_id=engine_id, account_id=account_id)
    return engine, runtime


async def _refresh(factory: async_sessionmaker[AsyncSession]) -> None:
    """Refresca el watch desde ESTUDIO con el resolver REAL (una vez por turno)."""
    await worker_mod.refresh_watch_from_estudio(SessionScopedEstudioList(factory))


async def _durable_symbols(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    symbols: list[str],
) -> set[str]:
    """Valores del lote con >=1 fila durable ligada a ese símbolo (journal/reserva/posición/TOP3).

    La evidencia se exige para valores que **operan** o **producen candidata BUY**; un
    valor que NO opera (HOLD) no aparece aquí (hueco declarado, ver docstring de cabecera).
    """
    from bolsa_infrastructure.database.models.tables import (
        DecisionJournalEntryRow,
        PortfolioReservationRow,
        SimAutoPositionRow,
        Top3OpportunityRow,
    )

    wanted = list(symbols)
    found: set[str] = set()
    async with factory() as session:
        found |= set(
            (
                await session.execute(
                    select(DecisionJournalEntryRow.instrument_id)
                    .where(DecisionJournalEntryRow.account_id == account_id)
                    .where(DecisionJournalEntryRow.instrument_id.in_(wanted))
                )
            )
            .scalars()
            .all()
        )
        found |= set(
            (
                await session.execute(
                    select(SimAutoPositionRow.symbol)
                    .where(SimAutoPositionRow.account_id == account_id)
                    .where(SimAutoPositionRow.symbol.in_(wanted))
                )
            )
            .scalars()
            .all()
        )
        found |= set(
            (
                await session.execute(
                    select(PortfolioReservationRow.instrument_id)
                    .where(PortfolioReservationRow.account_id == account_id)
                    .where(PortfolioReservationRow.instrument_id.in_(wanted))
                )
            )
            .scalars()
            .all()
        )
        found |= set(
            (
                await session.execute(
                    select(Top3OpportunityRow.asset_id)
                    .where(Top3OpportunityRow.asset_id.in_(wanted))
                    .where(Top3OpportunityRow.run_id.like(f"top3-{account_id}-%"))
                )
            )
            .scalars()
            .all()
        )
    return {s for s in found if s}


async def _entry_decision_count(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    symbols: list[str],
) -> int:
    """Nº de hechos M2 ``auto_entry_decision`` durables por símbolo (la huella del BUY)."""
    from bolsa_infrastructure.database.models.tables import DecisionJournalEntryRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(DecisionJournalEntryRow)
                    .where(DecisionJournalEntryRow.account_id == account_id)
                    .where(DecisionJournalEntryRow.event_type == _EVENT_ENTRY_DECISION)
                    .where(DecisionJournalEntryRow.instrument_id.in_(symbols))
                )
            ).scalar()
            or 0
        )


async def _cleanup_account(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    engine_id: str,
) -> None:
    """Limpia los hechos durables del lote (cuenta/engine propios del caso)."""
    from bolsa_infrastructure.database.models.tables import (
        DecisionJournalEntryRow,
        PortfolioReservationRow,
        SimAutoPositionRow,
        SimConsumedSignalRow,
        Top3OpportunityRow,
    )

    async with factory() as session:
        await session.execute(
            delete(DecisionJournalEntryRow).where(
                DecisionJournalEntryRow.account_id == account_id
            )
        )
        await session.execute(
            delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
        )
        await session.execute(
            delete(SimConsumedSignalRow).where(SimConsumedSignalRow.account_id == account_id)
        )
        await session.execute(
            delete(PortfolioReservationRow).where(
                PortfolioReservationRow.account_id == account_id
            )
        )
        await session.execute(
            delete(Top3OpportunityRow).where(
                Top3OpportunityRow.run_id.like(f"top3-{account_id}-%")
            )
        )
        await session.commit()


class _BoomPort:
    """Puerto ESTUDIO que SIEMPRE lanza: el resolver debe degradar a fail-closed."""

    async def execute(self, list_id: str) -> Any:
        raise RuntimeError("estudio down")


# ── (a) COBERTURA POR VALOR ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_each_estudio_value_is_evaluated_and_buy_leaves_durable_fact_pg(
    estudio_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Todo valor de ESTUDIO se evalúa; los que producen BUY dejan hecho durable.

    HUECO DECLARADO: el valor HOLD **no** deja hecho durable por símbolo; solo se certifica
    que fue **evaluado** (estuvo en el watch) — se declara su ausencia en el journal M2.
    """
    _enable_lane(monkeypatch)
    async with _seeded_lane(estudio_pg_factory, 3) as (instruments, _originals):
        buy_ids = instruments[:2]
        hold_id = instruments[2]
        account_id = await _seed_account(estudio_pg_factory)
        engine_id = f"auto-acov-{uuid.uuid4().hex[:10]}"
        _engine, runtime = _make_lane(
            estudio_pg_factory, account_id=account_id, engine_id=engine_id, buy_symbols=set(buy_ids)
        )
        try:
            reports = []
            for _ in range(_TICKS):
                await _refresh(estudio_pg_factory)
                reports.append(await runtime.run_tick())

            watch = worker_mod._watch_symbols()
            assert set(instruments) <= set(watch), (
                f"todo valor elegible de ESTUDIO debe estar en el watch; watch={watch}"
            )
            assert all(report is not None and report.decided >= len(instruments) for report in reports), (
                "el turno REAL debe EVALUAR cada valor del watch (report.decided los cuenta)"
            )

            durable = await _durable_symbols(
                estudio_pg_factory, account_id=account_id, symbols=instruments
            )
            # Los valores que PRODUCEN candidata BUY exigen evidencia durable por símbolo.
            for instrument_id in buy_ids:
                assert instrument_id in durable, (
                    f"el valor {instrument_id} produjo candidata BUY y debe dejar >=1 fila "
                    "durable ligada a su símbolo (journal M2/reserva/posición/TOP3)"
                )

            # HUECO DECLARADO (falsable): el valor HOLD fue evaluado (watch) y NO deja
            # hecho durable por símbolo. No se exige fila; se declara su ausencia.
            assert hold_id in watch, (
                f"el valor HOLD {hold_id} DEBE haber sido EVALUADO (estuvo en el watch)"
            )
            hold_rows = await _entry_decision_count(
                estudio_pg_factory, account_id=account_id, symbols=[hold_id]
            )
            assert hold_rows == 0, (
                "HUECO DECLARADO: hoy un valor evaluado que NO opera (HOLD / precio ausente) "
                "no deja ningún hecho durable POR SÍMBOLO (solo el contador agregado del tick); "
                f"el aserto falla si aparecen filas M2 para {hold_id}"
            )
        finally:
            await _cleanup_account(estudio_pg_factory, account_id=account_id, engine_id=engine_id)


# ── (b) AÑADIDO entra ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_added_value_enters_watch_and_leaves_durable_fact_pg(
    estudio_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un valor AÑADIDO a ESTUDIO entra en el watch tras el refresco y deja hecho durable."""
    _enable_lane(monkeypatch)
    async with _seeded_lane(estudio_pg_factory, 2, add_all=False) as (instruments, _originals):
        first, added = instruments
        account_id = await _seed_account(estudio_pg_factory)
        engine_id = f"auto-acov-{uuid.uuid4().hex[:10]}"
        buy_symbols = {first}
        _engine, runtime = _make_lane(
            estudio_pg_factory, account_id=account_id, engine_id=engine_id, buy_symbols=buy_symbols
        )
        try:
            await add_to_estudio(estudio_pg_factory, [first])
            await _refresh(estudio_pg_factory)
            await runtime.run_tick()
            assert first in worker_mod._watch_symbols()

            # AÑADIR (a ESTUDIO y al spine) ⇒ entra tras el refresco.
            await add_to_estudio(estudio_pg_factory, [added])
            buy_symbols.add(added)
            await _refresh(estudio_pg_factory)
            assert added in worker_mod._watch_symbols(), (
                f"un valor añadido a ESTUDIO debe entrar en el watch; watch={worker_mod._watch_symbols()}"
            )
            await runtime.run_tick()

            durable = await _durable_symbols(
                estudio_pg_factory, account_id=account_id, symbols=[first, added]
            )
            assert added in durable, (
                f"el valor añadido {added} debe dejar hecho durable (journal M2/reserva/posición/TOP3)"
            )
        finally:
            await _cleanup_account(estudio_pg_factory, account_id=account_id, engine_id=engine_id)


# ── (c) RETIRADO sale ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_removed_value_leaves_watch_and_emits_no_new_fact_pg(
    estudio_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un valor RETIRADO de ESTUDIO sale del watch y no emite hechos nuevos suyos."""
    _enable_lane(monkeypatch)
    async with _seeded_lane(estudio_pg_factory, 2) as (instruments, _originals):
        keep_id, removed_id = instruments
        account_id = await _seed_account(estudio_pg_factory)
        engine_id = f"auto-acov-{uuid.uuid4().hex[:10]}"
        _engine, runtime = _make_lane(
            estudio_pg_factory, account_id=account_id, engine_id=engine_id, buy_symbols=set(instruments)
        )
        try:
            await _refresh(estudio_pg_factory)
            await runtime.run_tick()

            # RETIRAR el segundo valor de ESTUDIO ⇒ sale del watch.
            await set_estudio(estudio_pg_factory, [keep_id])
            await _refresh(estudio_pg_factory)
            assert removed_id not in worker_mod._watch_symbols(), (
                "un valor retirado de ESTUDIO debe salir del watch"
            )

            before = await _entry_decision_count(
                estudio_pg_factory, account_id=account_id, symbols=[removed_id]
            )
            await runtime.run_tick()
            after = await _entry_decision_count(
                estudio_pg_factory, account_id=account_id, symbols=[removed_id]
            )
            assert after == before, (
                "un valor retirado de ESTUDIO no debe emitir hechos durables nuevos"
            )
        finally:
            await _cleanup_account(estudio_pg_factory, account_id=account_id, engine_id=engine_id)


# ── (d) UNIVERSO VACÍO ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_estudio_watch_is_empty_and_turn_decides_nothing_pg(
    estudio_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ESTUDIO vacío ⇒ watch vacío y el turno NO decide (fail-closed)."""
    _enable_lane(monkeypatch)
    async with _seeded_lane(estudio_pg_factory, 1) as (instruments, _originals):
        account_id = await _seed_account(estudio_pg_factory)
        engine_id = f"auto-acov-{uuid.uuid4().hex[:10]}"
        _engine, runtime = _make_lane(
            estudio_pg_factory, account_id=account_id, engine_id=engine_id, buy_symbols=set(instruments)
        )
        try:
            originals = await set_estudio(estudio_pg_factory, [])
            try:
                await _refresh(estudio_pg_factory)
                assert worker_mod._watch_symbols() == [], (
                    "ESTUDIO vacío ⇒ watch vacío (la allowlist CSV nunca lo sustituye)"
                )
                report = await runtime.run_tick()
                assert report is not None and report.decided == 0, (
                    "sin universo no se decide ningún símbolo (fail-closed)"
                )
            finally:
                await restore_estudio(estudio_pg_factory, originals)
        finally:
            await _cleanup_account(estudio_pg_factory, account_id=account_id, engine_id=engine_id)


# ── (e) ERROR de ESTUDIO ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_estudio_error_watch_is_empty_and_emits_no_new_fact_pg(
    estudio_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un puerto ESTUDIO que LANZA ⇒ watch vacío y sin hechos nuevos (fail-closed)."""
    _enable_lane(monkeypatch)
    async with _seeded_lane(estudio_pg_factory, 2) as (instruments, _originals):
        account_id = await _seed_account(estudio_pg_factory)
        engine_id = f"auto-acov-{uuid.uuid4().hex[:10]}"
        _engine, runtime = _make_lane(
            estudio_pg_factory, account_id=account_id, engine_id=engine_id, buy_symbols=set(instruments)
        )
        try:
            await _refresh(estudio_pg_factory)
            await runtime.run_tick()
            before = await _entry_decision_count(
                estudio_pg_factory, account_id=account_id, symbols=instruments
            )

            await worker_mod.refresh_watch_from_estudio(_BoomPort())
            assert worker_mod._watch_symbols() == [], (
                "un error de ESTUDIO ⇒ watch vacío (nunca cae a la allowlist)"
            )
            report = await runtime.run_tick()
            assert report is not None and report.decided == 0, (
                "con ESTUDIO en error el turno no decide (fail-closed)"
            )
            after = await _entry_decision_count(
                estudio_pg_factory, account_id=account_id, symbols=instruments
            )
            assert after == before, "un ESTUDIO en error no debe emitir hechos nuevos"
        finally:
            await _cleanup_account(estudio_pg_factory, account_id=account_id, engine_id=engine_id)


# ── (f) EXCLUSIONES explícitas (allowlist CSV que intersecta) ────────────────────────


@pytest.mark.asyncio
async def test_csv_allowlist_intersects_estudio_pg(
    estudio_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El CSV pasa a allowlist que INTERSECTA; sin intersección ⇒ watch vacío."""
    _enable_lane(monkeypatch)
    async with _seeded_lane(estudio_pg_factory, 3, add_all=False) as (instruments, _originals):
        await add_to_estudio(estudio_pg_factory, instruments)

        monkeypatch.setenv(_ENV_SIM_WATCH, f"{instruments[1]},ZZZ-NOT-IN-ESTUDIO")
        await _refresh(estudio_pg_factory)
        assert worker_mod._watch_symbols() == [instruments[1]], (
            "el CSV debe INTERSECTAR ESTUDIO (nunca sustituirlo)"
        )

        monkeypatch.setenv(_ENV_SIM_WATCH, "ZZZ-NOT-IN-ESTUDIO")
        await _refresh(estudio_pg_factory)
        assert worker_mod._watch_symbols() == [], (
            "una allowlist sin intersección con ESTUDIO ⇒ watch vacío"
        )
