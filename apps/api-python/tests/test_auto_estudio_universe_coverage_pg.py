"""Verificación EJECUTABLE (PG real) — la lane AUTO recorre TODO el universo ESTUDIO.

CERTIFICA (plan ``verificación AUTO/DÍA-D``, slice ``S1``):

1. El universo canónico del orquestador es la lista ESTUDIO: ``resolve_universe()``
   devuelve ``ok`` con TODOS sus valores, y ``_instruments_for_cycle`` —la MISMA función
   que usa el bucle— devuelve exactamente ese conjunto.
2. El bucle ``auto_orchestrator_loop`` recorre CADA valor y deja EVIDENCIA DURABLE de
   ciclo (candidata + evaluación con ``optimization_run_id``), no solo la mención en el
   informe por valor.
3. La allowlist ``AUTO_ORCHESTRATOR_INSTRUMENTS`` solo **intersecta** el universo (nunca
   lo sustituye); sin ESTUDIO ``ok`` no se opera (fail-closed, mismo contrato que
   ``test_auto_orchestrator_worker.py`` pero sobre el resolver REAL).
4. La cobertura del universo NO depende del reloj de la máquina: la resolución es una
   lectura de **pertenencia** (lista), no una consulta temporal; se demuestra
   booby-trapeando el reloj de barras (``bar_tick``/``last_closed_bar_day``) y
   comprobando que la cobertura no cambia.

HALLAZGO DECLARADO (slice ``S2``, NO cerrado aquí): la lane de OPERACIÓN DIARIA
(``auto_simulation_worker``) NO deriva su watch del universo ESTUDIO — usa el CSV
``AUTO_ENGINE_SIM_WATCH`` (default ``AAA,IBEX``). Este fichero certifica la lane de
**orquestación/estrategia**; el desacoplamiento respecto a la lane diaria se fija y se
declara en ``test_auto_daily_watch_coupling.py`` y en la evidencia del sello.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_ESTUDIO_COVERAGE_PG_REQUIRED=1`` (job ``lifecycle-pg``) un skip silencioso es un
FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import math
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_ESTUDIO_COVERAGE_PG_REQUIRED"

#: Nº de valores sembrados en ESTUDIO. Se recorren TODOS; 3 basta para falsar «solo el
#: primero» y mantiene el coste acotado (un ciclo real ~2 s por valor).
_N_INSTRUMENTS = 3
#: Presupuesto del sondeo de cobertura (0,5 s por vuelta). Un ciclo real por valor tarda
#: ~2 s; 120 vueltas (60 s) da holgura sin disparar la duración del job.
_COVERAGE_POLLS = 120


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la cobertura del universo ESTUDIO pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (cobertura ESTUDIO) no disponible: {exc}")


@pytest_asyncio.fixture
async def estudio_pg_factory() -> async_sessionmaker[AsyncSession]:
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


async def _seed_instrument_with_trend(
    factory: async_sessionmaker[AsyncSession],
    *,
    instrument_id: str,
    symbol: str,
) -> None:
    """Siembra un instrumento con una serie OHLCV con tendencia + oscilación.

    El mismo patrón que ``test_strategy_lifecycle_pg.py`` (drift dominante sobre una
    sinusoide): el campeón del LAB pasa los 4 gates ``lab_validated`` (CPCV/WF) y el
    ciclo deja evaluación persistida. Sin serie, el LAB devuelve «sin evidencia» y el
    valor NO deja el hecho durable que este test exige.
    """
    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow

    async with factory() as session:
        if await session.get(InstrumentRow, instrument_id) is not None:
            return
        now = datetime.now(UTC)
        session.add(
            InstrumentRow(
                id=instrument_id,
                symbol=symbol,
                yahoo_symbol=f"{symbol}.MC",
                name=f"ESTCO Test {symbol}",
                exchange="MCE",
                country="ES",
                currency="EUR",
                type="stock",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        base = Decimal("10.00")
        for day in range(420):
            wave = Decimal(str(round(2.0 * math.sin(2 * math.pi * day / 60.0), 4)))
            drift = Decimal(day) * Decimal("0.08")
            price = base + drift + wave
            session.add(
                OhlcvBarRow(
                    id=uuid.uuid4().hex,
                    instrument_id=instrument_id,
                    timeframe="1d",
                    timestamp=now - timedelta(days=419 - day),
                    open=price,
                    high=price + Decimal("0.10"),
                    low=price - Decimal("0.10"),
                    close=price,
                    volume=1000,
                    adj_close=price,
                    source="yahoo",
                    created_at=now,
                )
            )
        await session.commit()


async def _add_to_estudio(
    factory: async_sessionmaker[AsyncSession], instrument_ids: list[str]
) -> list[str]:
    """AÑADE valores a ESTUDIO preservando los existentes; devuelve los originales.

    No destructivo: el cleanup restaura la lista original (patrón de
    ``test_strategy_lifecycle_pg.py``). Lanza si la lista no admite edición (catálogo),
    que sería un cambio de contrato ajeno a este sello.
    """
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        existing = await repo.ensure_estudio_list()
        originals = list(existing.instrument_ids)
        merged = list(dict.fromkeys([*originals, *instrument_ids]))
        if merged != originals:
            await repo.update(
                SqlAlchemyListRepository.ESTUDIO_LIST_ID,
                instrument_ids=merged,
            )
        await session.commit()
        return originals


async def _restore_estudio(
    factory: async_sessionmaker[AsyncSession], originals: list[str]
) -> None:
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        await repo.ensure_estudio_list()
        await repo.update(
            SqlAlchemyListRepository.ESTUDIO_LIST_ID,
            instrument_ids=originals,
        )
        await session.commit()


async def _cleanup_instrument(
    factory: async_sessionmaker[AsyncSession], instrument_id: str
) -> None:
    from bolsa_infrastructure.database.models.tables import (
        InstrumentRow,
        OhlcvBarRow,
        StrategyCandidateRow,
        StrategyEvaluationRow,
    )

    async with factory() as session:
        await session.execute(
            delete(StrategyEvaluationRow).where(
                StrategyEvaluationRow.instrument_id == instrument_id
            )
        )
        await session.execute(
            delete(StrategyCandidateRow).where(
                StrategyCandidateRow.instrument_id == instrument_id
            )
        )
        await session.execute(
            delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id)
        )
        await session.execute(
            delete(InstrumentRow).where(InstrumentRow.id == instrument_id)
        )
        await session.commit()


async def _covered_instruments(
    factory: async_sessionmaker[AsyncSession], instrument_ids: list[str]
) -> set[str]:
    """Instrumentos del lote con evidencia de ciclo COMPLETA y durable.

    Se exige candidata **y** evaluación con ``optimization_run_id``: la candidata se
    persiste al principio del ciclo, así que esperar solo por ella cancelaría el bucle a
    mitad de la evaluación del último valor (carrera real de esta verificación).
    """
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

    covered: set[str] = set()
    async with factory() as session:
        store = PostgresStrategyLifecycleStore(session)
        for instrument_id in instrument_ids:
            candidates = await store.list_candidates(instrument_id=instrument_id)
            if not candidates:
                continue
            evaluations = await store.list_evaluations(candidates[0].id)
            if any(e.optimization_run_id for e in evaluations):
                covered.add(instrument_id)
    return covered


@pytest.mark.asyncio
async def test_estudio_universe_is_traversed_by_the_loop_pg(
    estudio_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El bucle REAL recorre cada valor de ESTUDIO y deja evidencia durable de ciclo."""
    from bolsa_api.background.auto_orchestrator_worker import (
        _default_orchestrator,
        _instruments_for_cycle,
        auto_orchestrator_loop,
    )
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

    suffix = uuid.uuid4().hex[:8]
    instruments = [f"inst-estco-{suffix}-{index}" for index in range(_N_INSTRUMENTS)]
    # El instrumento debe EXISTIR antes de añadirlo a ESTUDIO: la lista resuelve su
    # detalle uniendo ``instrument_list_items`` con ``instruments``, así que un miembro
    # inexistente no aparecería en el universo.
    originals: list[str] | None = None
    try:
        for index, instrument_id in enumerate(instruments):
            await _seed_instrument_with_trend(
                estudio_pg_factory,
                instrument_id=instrument_id,
                symbol=f"EC{suffix[:3].upper()}{index}",
            )
        originals = await _add_to_estudio(estudio_pg_factory, instruments)

        # Composición REAL: store + ESTUDIO + LAB, sin inyectar nada.
        orchestrator = _default_orchestrator(estudio_pg_factory)

        resolution = await orchestrator.resolve_universe()
        assert resolution is not None, "el orquestador real debe tener resolver de universo"
        assert resolution.status == "ok", f"ESTUDIO debe resolver ok: {resolution}"
        missing = [i for i in instruments if i not in resolution.instrument_ids]
        assert not missing, (
            "resolve_universe debe devolver TODO el universo ESTUDIO sembrado; "
            f"faltan={missing}"
        )

        # La función que usa el bucle ve EXACTAMENTE el mismo universo (sin allowlist).
        watch = await _instruments_for_cycle(orchestrator, allowlist=())
        assert set(watch) >= set(instruments), (
            f"_instruments_for_cycle debe incluir el lote sembrado; watch={watch}"
        )
        # Allowlist INTERSECTA (nunca sustituye): solo el subconjunto pedido…
        subset = await _instruments_for_cycle(orchestrator, allowlist=(instruments[0],))
        assert subset == (instruments[0],), f"la allowlist debe intersectar: {subset}"
        # …y un CSV sin intersección con ESTUDIO ⇒ NO se opera (fail-closed).
        empty = await _instruments_for_cycle(
            orchestrator, allowlist=("nope-not-in-estudio",)
        )
        assert empty == (), f"una allowlist sin intersección no debe operar: {empty}"

        # Se conduce el BUCLE real una iteración (con periodo corto) y se corta en cuanto
        # cada valor ha dejado su candidata durable. No se reimplementa el cuerpo del
        # bucle: es el MISMO ``auto_orchestrator_loop`` que corre en producción.
        task = asyncio.create_task(
            auto_orchestrator_loop(orchestrator, interval_seconds=0.05)
        )
        covered: set[str] = set()
        try:
            for _ in range(_COVERAGE_POLLS):
                await asyncio.sleep(0.5)
                covered = await _covered_instruments(estudio_pg_factory, instruments)
                if covered >= set(instruments):
                    break
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert covered >= set(instruments), (
            "el bucle debe recorrer TODO el universo ESTUDIO (cada valor deja evidencia "
            f"durable de ciclo); sin cubrir={sorted(set(instruments) - covered)}"
        )

        # Evidencia durable COMPLETA por valor: candidata + evaluación con su
        # ``optimization_run_id`` (el ciclo no solo «pasa», persiste su LAB auditable).
        async with estudio_pg_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            for instrument_id in instruments:
                candidates = await store.list_candidates(instrument_id=instrument_id)
                assert candidates, (
                    f"el valor {instrument_id} de ESTUDIO no dejó candidata durable"
                )
                evaluations = await store.list_evaluations(candidates[0].id)
                assert evaluations, (
                    f"el valor {instrument_id} no dejó evaluación de LAB persistida"
                )
                assert any(e.optimization_run_id for e in evaluations), (
                    f"la evaluación de {instrument_id} debe ser auditable "
                    "(_optimization_run_id_ persistido)"
                )
    finally:
        for instrument_id in instruments:
            await _cleanup_instrument(estudio_pg_factory, instrument_id)
        # Solo se restaura si de verdad se modificó ESTUDIO (``originals`` capturado).
        if originals is not None:
            await _restore_estudio(estudio_pg_factory, originals)


@pytest.mark.asyncio
async def test_real_resolver_is_fail_closed_without_ok_estudio() -> None:
    """El resolver REAL (``make_estudio_universe_resolver``) es fail-closed sin ESTUDIO ok.

    Hermético (sin PG): cablea el resolver REAL sobre puertos dobles y comprueba que
    ``_instruments_for_cycle`` NO opera ni cae a la allowlist cuando ESTUDIO está
    ``unavailable``/``empty``/error. Cierra el contrato sobre el MÓDULO de producción.
    """
    from bolsa_api.background.auto_orchestrator_worker import _instruments_for_cycle
    from bolsa_application.orchestrator_universe import make_estudio_universe_resolver

    class _Orch:
        def __init__(self, resolver: Any) -> None:
            self._resolver = resolver

        async def resolve_universe(self) -> Any:
            return await self._resolver()

    class _PortList:
        def __init__(self, instrument_ids: list[str]) -> None:
            self._ids = instrument_ids

        async def execute(self, list_id: str) -> Any:
            return type("_Detail", (), {"instrument_ids": list(self._ids)})()

    class _BoomPort:
        async def execute(self, list_id: str) -> Any:
            raise RuntimeError("estudio down")

    # Sin puerto ⇒ unavailable.
    assert (
        await _instruments_for_cycle(
            _Orch(make_estudio_universe_resolver(None)), allowlist=("AAA",)
        )
        == ()
    )
    # Lista vacía ⇒ empty (no se opera, la allowlist no rescata).
    assert (
        await _instruments_for_cycle(
            _Orch(make_estudio_universe_resolver(_PortList([]))), allowlist=("AAA",)
        )
        == ()
    )
    # Fallo del puerto ⇒ unavailable.
    assert (
        await _instruments_for_cycle(
            _Orch(make_estudio_universe_resolver(_BoomPort())), allowlist=("AAA",)
        )
        == ()
    )
    # Con universo ok, la allowlist solo intersecta.
    watch = await _instruments_for_cycle(
        _Orch(make_estudio_universe_resolver(_PortList(["AAA", "BBB"]))),
        allowlist=("BBB",),
    )
    assert watch == ("BBB",)


def test_universe_coverage_does_not_read_the_bar_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La cobertura del universo es pertenencia de lista, NO una consulta temporal.

    Booby-trap del reloj de barras (``bar_tick``/``last_closed_bar_day``): si la
    cobertura dependiera del reloj de máquina, esta prueba reventaría. Repetir la
    resolución con el reloj «desplazado» (aquí, inutilizado) y comprobar que la
    cobertura no cambia es la verificación falsable de independencia del reloj.
    """
    import bolsa_application.closed_bars as closed_bars
    from bolsa_api.background.auto_orchestrator_worker import _instruments_for_cycle
    from bolsa_application.orchestrator_universe import make_estudio_universe_resolver

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "la cobertura del universo no debe leer el reloj de barras "
            "(el anclaje temporal pertenece a la EJECUCIÓN, no a la cobertura)"
        )

    monkeypatch.setattr(closed_bars, "bar_tick", _boom)
    monkeypatch.setattr(closed_bars, "last_closed_bar_day", _boom)

    class _Orch:
        def __init__(self, resolver: Any) -> None:
            self._resolver = resolver

        async def resolve_universe(self) -> Any:
            return await self._resolver()

    class _PortList:
        async def execute(self, list_id: str) -> Any:
            return type("_Detail", (), {"instrument_ids": ["AAA", "BBB"]})()

    watch = asyncio.run(
        _instruments_for_cycle(
            _Orch(make_estudio_universe_resolver(_PortList())), allowlist=()
        )
    )
    assert watch == ("AAA", "BBB")


def test_closed_bar_anchor_is_stable_within_a_bar() -> None:
    """El anclaje temporal de la EJECUCIÓN es la BARRA CERRADA, no el instante exacto.

    Dentro de la misma barra diaria, ``bar_tick`` y ``last_closed_bar_day`` no cambian:
    es lo que hace que la identidad de una ejecución reintentada intra-barra sea la
    misma (idempotencia) y que la cobertura/entrada no dependan del reloj de la máquina.
    """
    from bolsa_application.closed_bars import bar_tick, last_closed_bar_day

    morning = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    midday = datetime(2026, 10, 13, 14, 30, tzinfo=UTC)
    assert bar_tick(morning, "1d") == bar_tick(midday, "1d")
    assert last_closed_bar_day(morning, "1d") == last_closed_bar_day(midday, "1d")
