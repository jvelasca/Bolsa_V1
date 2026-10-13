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

ESTE FICHERO CERTIFICA LA LANE DE **ORQUESTACIÓN/ESTRATEGIA**. El desacoplamiento de la
lane de **operación diaria** respecto a ESTUDIO (hallazgo ``S2`` declarado en ``v2.88.122``)
se **cierra** en ``v2.88.123`` de forma **env-gated**: el watch diario deriva del universo
canónico con ``AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO`` (ver
``test_auto_daily_watch_coupling.py`` y ``test_auto_daily_watch_from_estudio_pg.py``).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_ESTUDIO_COVERAGE_PG_REQUIRED=1`` (job ``lifecycle-pg``) un skip silencioso es un
FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests._estudio_pg_helpers import (
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
_REQUIRED_ENV = "AUTO_ESTUDIO_COVERAGE_PG_REQUIRED"

#: Nº de valores sembrados en ESTUDIO. Se recorren TODOS; 3 basta para falsar «solo el
#: primero» y mantiene el coste acotado (un ciclo real ~2 s por valor).
_N_INSTRUMENTS = 3
#: Presupuesto del sondeo de cobertura (0,5 s por vuelta). Un ciclo real por valor tarda
#: ~2 s; 120 vueltas (60 s) da holgura sin disparar la duración del job.
_COVERAGE_POLLS = 120


@pytest_asyncio.fixture
async def estudio_pg_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="cobertura ESTUDIO")
        raise
    try:
        yield factory
    finally:
        await engine.dispose()


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
    # El instrumento debe EXISTIR antes de fijarlo en ESTUDIO: la lista resuelve su
    # detalle uniendo ``instrument_list_items`` con ``instruments``, así que un miembro
    # inexistente no aparecería en el universo.
    # Se FIJA ESTUDIO al lote sembrado (``set_estudio``, no ``add_to_estudio``): el universo
    # certificado es EXACTAMENTE estos valores. Anclar el alcance hace la verificación
    # determinista (no depende de cuántos miembros arrastre ESTUDIO de otras pruebas ni del
    # tamaño del catálogo) y acota el coste del bucle a los valores sembrados. El lote se
    # restaura en el ``finally`` con ``restore_estudio`` (no destructivo).
    originals: list[str] | None = None
    try:
        for index, instrument_id in enumerate(instruments):
            await seed_instrument_with_trend(
                estudio_pg_factory,
                instrument_id=instrument_id,
                symbol=f"EC{suffix[:3].upper()}{index}",
            )
        originals = await set_estudio(estudio_pg_factory, instruments)

        # Composición REAL: store + ESTUDIO + LAB, sin inyectar nada.
        orchestrator = _default_orchestrator(estudio_pg_factory)

        resolution = await orchestrator.resolve_universe()
        assert resolution is not None, "el orquestador real debe tener resolver de universo"
        assert resolution.status == "ok", f"ESTUDIO debe resolver ok: {resolution}"
        missing = [i for i in instruments if i not in resolution.instrument_ids]
        assert not missing, (
            f"resolve_universe debe devolver TODO el universo ESTUDIO sembrado; faltan={missing}"
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
        empty = await _instruments_for_cycle(orchestrator, allowlist=("nope-not-in-estudio",))
        assert empty == (), f"una allowlist sin intersección no debe operar: {empty}"

        # Se conduce el BUCLE real una iteración (con periodo corto) y se corta en cuanto
        # cada valor ha dejado su candidata durable. No se reimplementa el cuerpo del
        # bucle: es el MISMO ``auto_orchestrator_loop`` que corre en producción.
        task = asyncio.create_task(auto_orchestrator_loop(orchestrator, interval_seconds=0.05))
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
                assert candidates, f"el valor {instrument_id} de ESTUDIO no dejó candidata durable"
                evaluations = await store.list_evaluations(candidates[0].id)
                assert evaluations, f"el valor {instrument_id} no dejó evaluación de LAB persistida"
                assert any(e.optimization_run_id for e in evaluations), (
                    f"la evaluación de {instrument_id} debe ser auditable "
                    "(_optimization_run_id_ persistido)"
                )
    finally:
        for instrument_id in instruments:
            await cleanup_instrument(estudio_pg_factory, instrument_id)
        # Solo se restaura si de verdad se modificó ESTUDIO (``originals`` capturado).
        if originals is not None:
            await restore_estudio(estudio_pg_factory, originals)


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
        _instruments_for_cycle(_Orch(make_estudio_universe_resolver(_PortList())), allowlist=())
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
