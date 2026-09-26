"""V2.74 (AUTO-MATERIAL-2) — E2E PostgreSQL del PRODUCTOR V2 y del gate de dos niveles.

Certifica sobre PostgreSQL REAL lo que la costura hermética
(``test_auto_v74_producer_seam.py``) NO puede cerrar: que la estructura que el productor
AUTO 2.0 acuña —``cycle_id`` en los fills, reserva de entrada con denominador positivo,
intent de salida con ``cycle_id``, ciclo cerrado y R medible— **sobrevive al COMMIT** y es
**reconstruida por ``paper_material_readiness_v2`` desde una conexión nueva**, sin la
memoria del proceso que produjo el material.

Diferencia con la costura hermética: allí los stores son in-memory y el material nunca
cruza una transacción. Aquí el material cruza la frontera real:

    worker (AutoSimRuntime, camino real)
        → commit (PostgreSQL)
        → engine.dispose()  ("fin del proceso")
        → conexión NUEVA
        → paper_material_readiness_v2 (el MISMO lector del CLI, sin mocks)
        → PRODUCER_READY

Lo que se demuestra, punto por punto del protocolo: ``cycle_id != NULL`` en los fills,
``reservations > 0`` con ``reserved_risk > 0`` preservado pese al cierre,
``exit.cycle_id != NULL``, ``closed_cycles = true`` y ``R != NULL``. Todo ello leído por
el gate REAL (no por un helper del test) sobre una conexión que el productor nunca tocó.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_V74_PRODUCER_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. La venue es PAPER
virtual; NUNCA se abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import socket
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.paper_material_readiness import (
    BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES,
    READINESS_PRODUCER_READY,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_V74_PRODUCER_PG_REQUIRED"
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper_material_readiness.py"

#: Versión de estrategia con la que el decider determinista ATRIBUYE sus propuestas. Es la
#: MISMA vía que un decider de producción (``DecisionPackage.source = "active-strategy:<v>"``);
#: sin atribución el fill nace con ``strategy_version_id`` NULL y el gate —que lee por versión
#: pedida— no podría MEDIRLO.
_STRATEGY_VERSION = "v74-producer-orb-v1"
_STRATEGY_SOURCE = f"active-strategy:{_STRATEGY_VERSION}"
_ATR = 2.0  # 2 % de 100 ⇒ stop estructural en 100 − 1.5×2 = 97.
_ENTRY = 100.0
_BREAK = 96.0  # rompe el stop (97): dispara la salida estructural del arm V2.
_LOT = 100.0
_MINUTE_STEP = timedelta(minutes=1)
_TICKS = 12


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el E2E del productor V2 pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (E2E productor V2) no disponible: {exc}")


# ── Acceso a PostgreSQL ─────────────────────────────────────────────────────────────


async def _open_session_factory() -> tuple[Any, Any]:
    """(motor, session_factory) contra la BD real, con migración garantizada."""
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    return engine, create_session_factory(engine)


def _unreachable_reason(database_url: str, *, timeout: float = 2.0) -> str | None:
    """TCP preflight rápido: ``None`` si el puerto responde, si no el motivo.

    ``ensure_migrated`` normaliza la URL con ``url.split("?", 1)[0]`` (descarta el query),
    así que un ``connect_timeout`` en la URL no llega al driver y un host caído puede dejar
    el skip colgado decenas de segundos. La sonda TCP lo convierte en un skip inmediato.
    """
    from sqlalchemy.engine import make_url

    if not database_url:
        return "DATABASE_URL sin configurar"
    url = make_url(database_url)
    host = url.host or "localhost"
    port = url.port or 5432
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return None
    except OSError as exc:
        return f"{host}:{port} inalcanzable ({exc})"


async def _probe() -> None:
    engine, _factory = await _open_session_factory()
    await engine.dispose()


@pytest.fixture
def v74_pg() -> None:
    """Gate honesto: sin PostgreSQL real se salta (o falla duro con el env de gobierno)."""
    from dotenv import load_dotenv

    from bolsa_infrastructure.config import get_settings

    load_dotenv(_DOTENV, override=False)
    get_settings.cache_clear()
    reason = _unreachable_reason(get_settings().database_url or "")
    if reason is not None:
        _require_or_skip(RuntimeError(reason))
    try:
        asyncio.run(_probe())
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise


# ── Fixture determinista del productor ──────────────────────────────────────────────


def _filling_instrument_id(prefix: str, *, side: str = "buy") -> str:
    """Id determinista cuya orden ``side`` LLENA en toda la ventana de ticks (cola SIM).

    Misma barrida que ``test_auto_v2_durable_pg``: con un id aleatorio el sorteo del venue
    puede dejar la entrada sin llenar y el rojo sería espurio (no un defecto del productor).
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    for n in range(64):
        candidate = f"{prefix}{n:010d}"
        fills = [
            simulated_fill_schedule(
                instrument_id=candidate,
                side=side,
                quantity=Decimal("100"),
                venue_order_id=f"probe-{candidate}-{minute}",
                seed=minute * 100_003 + sum(map(ord, candidate)) % 9999,
                fill_chunks=4,
                base_mid=_ENTRY,
            ).fills
            for minute in range(0, 9)
        ]
        if all(fills):
            return candidate
    raise AssertionError(f"ningún id determinista de {prefix} llena en la ventana de minutos")


class _RoundTrip:
    """Decider determinista del arm V2: BUY sin posición; HOLD con posición.

    La salida NO la pide el decider: la dispara el ``ExitPlan`` (parada estructural) al
    romper el precio —el MISMO camino que un stop real— para que el ciclo cierre con la
    identidad y la reserva de salida del productor, no por una venta arbitraria.
    """

    def __init__(self, worker: Any, instrument_id: str) -> None:
        self._worker = worker
        self._symbol = instrument_id
        self._entered = False

    def __call__(self, symbol: str) -> Any:
        from bolsa_application.decision_contract import DecisionPackage

        if symbol != self._symbol:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        held = self._worker._open.get(self._symbol, Decimal("0"))
        if held <= 0 and not self._entered:
            self._entered = True
            return DecisionPackage(
                action="BUY",
                instrument_id=self._symbol,
                quantity=_LOT,
                source=_STRATEGY_SOURCE,
            )
        return DecisionPackage(action="HOLD", instrument_id=self._symbol, quantity=0)


async def _seed_account(session: AsyncSession) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"AUTO-V74E-{uuid.uuid4().hex[:8]}",
        initial_deposit=100_000.0,
    )
    await session.commit()
    return scope.account.id


async def _seed_instrument(session: AsyncSession, instrument_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    if await session.get(InstrumentRow, instrument_id) is not None:
        return

    now = datetime.now(UTC)
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"V74{uuid.uuid4().hex[:6].upper()}",
            yahoo_symbol=f"V74{uuid.uuid4().hex[:8]}",
            isin=None,
            name="AUTO-V74-Producer-E2E",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            # Gates fail-closed REALES: sector + fundamentals FRESCOS (sin ellos el motor
            # veta por ``sector_unknown``/``liquidity_unknown`` y no se ejercita el productor).
            sector="Technology",
            profile_snapshot={
                "fundamentals": {"advUsd": 50_000_000.0, "fetchedAt": now.isoformat()}
            },
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


async def _seed_edge_report(session: AsyncSession, *, account_id: str, strategy_ref: str) -> None:
    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    session.add(
        EdgeReportRow(
            id=f"edge-v74e-{uuid.uuid4().hex[:10]}",
            version="v2.74-producer-e2e",
            strategy_or_signal_ref=strategy_ref,
            instrument_universe_ref=None,
            account_id=account_id,
            credibility=Decimal("0.80"),
            edge_score=Decimal("0.90"),
            band="positive",
            suite={},
            notes=[],
            payload=None,
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _run_arm(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    instrument_id: str,
    engine_id: str,
) -> None:
    """Conduce el camino REAL (runtime → worker → stores PG) y abre+cierra un ciclo V2."""
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
    )

    prices = {instrument_id: _ENTRY}
    holder = {"now": datetime(2026, 9, 15, 9, 0, tzinfo=UTC)}

    worker = AutoSimulationWorker(
        engine_id=engine_id,
        account_id=account_id,
        clock=lambda: holder["now"],
        price_script=lambda symbol, _minute: prices.get(symbol, _ENTRY),
        atr_source=lambda _symbol: _ATR,
        sector_source=lambda _symbol: "Technology",
        liquidity_source=lambda _symbol: 50_000_000.0,
    )
    worker._decider = _RoundTrip(worker, instrument_id)  # noqa: SLF001 — seam interno de test.
    runtime = AutoSimRuntime(
        factory,
        worker=worker,
        engine_id=engine_id,
        account_id=account_id,
        atr_source=lambda _symbol: _ATR,
        liquidity_source=lambda _symbol: 50_000_000.0,
    )

    opened = False
    for _ in range(_TICKS):
        await runtime.run_tick()
        holder["now"] = holder["now"] + _MINUTE_STEP
        if worker._open.get(instrument_id, Decimal("0")) > 0:
            opened = True
            break
    assert opened, "el productor V2 abre por el camino real"

    # Parada estructural: el precio rompe el stop del ExitPlan la barra siguiente.
    prices[instrument_id] = _BREAK
    closed = False
    for _ in range(_TICKS):
        await runtime.run_tick()
        holder["now"] = holder["now"] + _MINUTE_STEP
        if worker._open.get(instrument_id, Decimal("0")) <= 0:
            closed = True
            break
    assert closed, "la parada estructural cierra el ciclo (round-trip V2)"

    # Asentamiento: con el libro plano y sin re-entrada (``_entered``), unos ticks más dejan
    # que las salidas en vuelo se reconcilien antes de medir.
    for _ in range(_TICKS):
        await runtime.run_tick()
        holder["now"] = holder["now"] + _MINUTE_STEP


async def _entry_reservation_primitives(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> dict[str, Any] | None:
    """La reserva de ENTRADA durable del ciclo, como primitivas (fuera de la sesión)."""
    from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

    async with factory() as session:
        row = (
            await session.execute(
                select(PortfolioReservationRow)
                .where(
                    PortfolioReservationRow.account_id == account_id,
                    PortfolioReservationRow.side == "buy",
                    PortfolioReservationRow.cycle_id.is_not(None),
                )
                .order_by(PortfolioReservationRow.created_at.asc())
            )
        ).scalars().first()
    if row is None:
        return None
    return {
        "reservation_id": row.reservation_id,
        "cycle_id": row.cycle_id,
        "side": row.side,
        "status": row.status,
        "reserved_risk": None if row.reserved_risk is None else Decimal(row.reserved_risk),
        "quantity": None if row.quantity is None else Decimal(row.quantity),
        "remaining_qty": None if row.remaining_qty is None else Decimal(row.remaining_qty),
    }


def _configure_producer_env(monkeypatch: pytest.MonkeyPatch, instrument_id: str) -> None:
    """Fija las env del productor (las MISMAS que el harness de evidencia v2.74).

    Sin ``AUTO_ENGINE_SIMULATED_WATCH`` el runtime no vigila nada y el worker nunca propone;
    sin ``V2_ENGINE_ENV`` el camino es legacy (fills sin ``cycle_id`` y sin reservas). Se fijan
    con ``monkeypatch`` para que revienten al terminar el test y no contaminen la sesión.
    """
    from bolsa_application.auto_v2_entry import V2_ENGINE_ENV

    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_SPINE_AUTO", "1")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_TOP_N", "5")
    monkeypatch.setenv("AUTO_ENGINE_SIM_LOT_QTY", str(int(_LOT)))
    monkeypatch.setenv("AUTO_ENGINE_SIM_INTERVAL_SECONDS", "1.0")
    # El gate PAPER se corre con esta venue: su guarda exige ``paper``.
    monkeypatch.setenv("BROKER_VENUE", "paper")


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("v74_paper_material_readiness_e2e", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _all_reservations_primitives(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> list[dict[str, Any]]:
    from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

    async with factory() as session:
        rows = (
            await session.execute(
                select(PortfolioReservationRow)
                .where(PortfolioReservationRow.account_id == account_id)
                .order_by(PortfolioReservationRow.created_at.asc())
            )
        ).scalars().all()
    return [
        {
            "id": row.reservation_id,
            "side": row.side,
            "status": row.status,
            "cycle_id": row.cycle_id,
            "reserved_risk": None if row.reserved_risk is None else str(row.reserved_risk),
            "remaining_qty": None if row.remaining_qty is None else str(row.remaining_qty),
            "exit_order_id": row.exit_order_id,
        }
        for row in rows
    ]


async def _fetch_entry_reservation(
    account_id: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Lee las reservas con una conexión NUEVA (tras el dispose del productor)."""
    engine, factory = await _open_session_factory()
    try:
        entry = await _entry_reservation_primitives(factory, account_id)
        all_rows = await _all_reservations_primitives(factory, account_id)
        return entry, all_rows
    finally:
        await engine.dispose()


async def _cleanup(account_id: str, engine_id: str, instrument_id: str) -> None:
    """Borra el residuo del test (el barrido autouse de conftest no cubre estas tablas)."""
    from bolsa_infrastructure.database.models.tables import (
        AdaptiveGateStateRow,
        AutoEngineRunRow,
        AutoEngineTickRow,
        AutoExitOrderRow,
        AutoKillStateRow,
        DecisionJournalEntryRow,
        EdgeReportRow,
        ExecutionEventRow,
        PortfolioReservationRow,
        SimAutoPositionRow,
        SimConsumedSignalRow,
        SimFillFinanceContextRow,
    )

    engine, factory = await _open_session_factory()
    try:
        async with factory() as session:
            await session.execute(
                delete(SimFillFinanceContextRow).where(
                    SimFillFinanceContextRow.account_id == account_id
                )
            )
            await session.execute(
                delete(PortfolioReservationRow).where(
                    PortfolioReservationRow.account_id == account_id
                )
            )
            await session.execute(
                delete(AutoExitOrderRow).where(AutoExitOrderRow.account_id == account_id)
            )
            await session.execute(
                delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
            )
            await session.execute(
                delete(SimConsumedSignalRow).where(SimConsumedSignalRow.account_id == account_id)
            )
            await session.execute(
                delete(ExecutionEventRow).where(ExecutionEventRow.account_id == account_id)
            )
            await session.execute(
                delete(DecisionJournalEntryRow).where(
                    DecisionJournalEntryRow.account_id == account_id
                )
            )
            await session.execute(
                delete(AutoKillStateRow).where(AutoKillStateRow.account_id == account_id)
            )
            await session.execute(
                delete(AdaptiveGateStateRow).where(AdaptiveGateStateRow.account_id == account_id)
            )
            await session.execute(
                delete(EdgeReportRow).where(EdgeReportRow.account_id == account_id)
            )
            await session.execute(
                delete(AutoEngineTickRow).where(AutoEngineTickRow.engine_id == engine_id)
            )
            await session.execute(
                delete(AutoEngineRunRow).where(AutoEngineRunRow.engine_id == engine_id)
            )
            await session.commit()

        # Grafo de la cuenta (portfolio, ledger... + la cuenta). El barrido global de
        # conftest es la red de seguridad; borrarlo aquí evita residuo entre tests.
        from tests.conftest import purge_accounts

        await purge_accounts(factory, [account_id])
    finally:
        await engine.dispose()


# ── El E2E ──────────────────────────────────────────────────────────────────────────


def test_v2_producer_structure_survives_commit_and_the_gate_rebuilds_it(
    v74_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El material V2 sobrevive al commit y el gate lo declara PRODUCER_READY DESDE PG.

    Protocolo: AUTO V2 ON → worker real → entrada + reserva + salida → cierre → COMMIT →
    ``engine.dispose()`` → conexión NUEVA → ``paper_material_readiness_v2`` (lector REAL del
    CLI) → ``PRODUCER_READY`` con los cinco invariantes de estructura reconstruidos.
    """
    instrument_id = _filling_instrument_id("inst-v74e-", side="buy")
    _configure_producer_env(monkeypatch, instrument_id)
    engine_id = f"auto-v74e-{uuid.uuid4().hex[:10]}"

    async def _scenario() -> dict[str, Any]:
        engine, factory = await _open_session_factory()
        seeded_account: str | None = None
        try:
            async with factory() as session:
                seeded_account = await _seed_account(session)
                await _seed_instrument(session, instrument_id)
                await _seed_edge_report(
                    session, account_id=seeded_account, strategy_ref=_STRATEGY_VERSION
                )
            await _run_arm(
                factory,
                account_id=seeded_account,
                instrument_id=instrument_id,
                engine_id=engine_id,
            )
            # Frontera de durabilidad: se cortan TODAS las conexiones del productor. Lo que
            # se lea después proviene del COMMIT, no de la memoria ni del pool del worker.
            await engine.dispose()

            # Proceso nuevo: el gate REAL abre su propia conexión (sin mocks, lector del CLI).
            module = _load_cli()
            readiness = await module._read(  # noqa: SLF001 — el lector real del CLI es el sujeto.
                seeded_account,
                [_STRATEGY_VERSION],
                limit=2000,
                min_cycles=32,
            )
            entry, all_reservations = await _fetch_entry_reservation(seeded_account)
            return {"readiness": readiness, "entry": entry, "reservations": all_reservations}
        finally:
            await engine.dispose()
            if seeded_account is not None:
                await _cleanup(seeded_account, engine_id, instrument_id)

    result = asyncio.run(_scenario())
    readiness = result["readiness"]
    entry = result["entry"]
    reservations = result["reservations"]

    # (1) El gate declara ESTRUCTURA sobre material reconstruido desde PostgreSQL.
    assert readiness.producer_ready is True
    assert readiness.verdict == READINESS_PRODUCER_READY
    assert readiness.producer_blockers == ()
    assert readiness.evidence_ready is False
    assert BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES in readiness.blockers

    facts = readiness.facts
    lineage = readiness.lineage

    # (2) cycle_id != NULL en TODO el material del universo pedido.
    assert facts["durableFills"] > 0
    assert facts["fillsWithCycle"] == facts["durableFills"]
    assert facts["fillsWithoutCycle"] == 0

    # (3) closed_cycles = true y R != NULL (denominador reconstruido tras el cierre).
    assert facts["closedCycles"] >= 1
    assert facts["measurableCycles"] >= 1
    assert lineage["closure"]["closedCyclesWithRisk"] >= 1

    # (4) Reservas con denominador positivo. El productor puede dejar VIVA una reserva de
    # SALIDA (intento de salida superado por otro: ``reserved_risk = 0``); lo que NO puede
    # quedar es una reserva VIVA de COMPRA, porque sería un denominador mutable tras cerrar.
    assert facts["reservations"] > 0
    assert facts["reservationsWithCycle"] > 0
    live = [
        row
        for row in reservations
        if str(row["status"]).upper() == "OPEN"
        and row["remaining_qty"] is not None
        and Decimal(row["remaining_qty"]) > 0
    ]
    assert all(str(row["side"]).lower() != "buy" for row in live), (
        "una reserva VIVA de compra sería un denominador de R vivo tras el cierre"
    )

    # (5) exit.cycle_id != NULL (linaje de salida medido, no inventado).
    assert lineage["cycle"]["exitOrders"] is not None
    assert lineage["cycle"]["exitOrdersWithCycle"] >= 1

    # (6) La fila durable de la reserva de ENTRADA conserva el denominador histórico
    # pese a estar liberada: ``reserved_risk > 0`` con ``remaining_qty = 0``.
    assert entry is not None, "la reserva de entrada del ciclo quedó persistida"
    assert entry["cycle_id"] and entry["side"] == "buy"
    assert entry["reserved_risk"] is not None and entry["reserved_risk"] > 0
    assert entry["remaining_qty"] is not None and entry["remaining_qty"] <= 0
    assert entry["status"] != "OPEN"
