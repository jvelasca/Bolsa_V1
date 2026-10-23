"""AUTO-MATERIAL-3 — E2E PostgreSQL de la RUTA REAL del productor (cierre de ``815ed4d0``).

Qué cierra este fichero (y qué NO cierra ``test_auto_v74_producer_pg_e2e.py``)
----------------------------------------------------------------------------
El E2E de V2.74 abre y cierra un ciclo sobre PostgreSQL REAL, pero lo hace con precio
**sintético inyectado** (``price_script``) y con un decider de prueba (``_RoundTrip``).
Eso certifica la ESTRUCTURA durable, no que el motor pueda producirla con el dato REAL.
La diferencia importa: la ventana PAPER del 2026-10-23 midió 80/80 precios y **0 ciclos**,
y al correr el worker con el interruptor de la ventana encendido pero sin barras el turno
cae en ``precio AUSENTE`` ⇒ HOLD. Por tanto la certificación funcional exige demostrar la
ruta completa con:

* **barras D1 reales** en ``ohlcv_bars`` (decisión ``close(B-1)`` / ejecución ``open(B)``),
* **estrategia ACTIVE real** leída de PostgreSQL (``load_active_strategy_decider``), que
  evalúa su PROPIA definición ejecutable (cruce SMA) y atribuye ``strategy_version_id``,
* **sin inyección de fuentes**: no hay ``price_script``, ni ``price_source``, ni
  ``atr_source``, ni ``sector_source``, ni ``liquidity_source``, ni ``edge_source``.

Protocolo del positivo
----------------------
    barras D1 (B-79 … B-1, B, B+1)
      → OhlcvPriceSource (close(B-1) / open(B), fuente "MARKET_CLOSE")
      → ACTIVE desde PG (cruce SMA alcista en B-1)
      → plan_v2_tick → reserva durable (save_claim) → fill con cycle_id
      → stop estructural en B+1 → SELL con el MISMO cycle_id
      → COMMIT → engine.dispose() → conexión NUEVA
      → paper_material_readiness_v3 (lector REAL del CLI) → PRODUCER_READY

Controles negativos (mismo fichero, stores PostgreSQL reales)
-------------------------------------------------------------
* Sin espejo de reservas ⇒ veto ``RESERVATION_UNMEASURABLE`` y 0 fills.
* ``save_claim`` devuelve ``False`` ⇒ veto ``RESERVATION_ALREADY_LIVE`` y 0 fills.
* ``save_claim`` lanza ⇒ 0 fills y ninguna fila huérfana en ``sim_fill_finance_context``.
* Sin barra ``B`` ⇒ ``precio AUSENTE`` contado, HOLD y 0 fills (no se fabrica precio).
* El primer ``save`` del INTENT de salida falla y el de emergencia funciona ⇒ fila
  ``EMERGENCY`` con el MISMO ``cycle_id`` y venta emitida, legible desde otra conexión.
* Fallan INTENT y emergencia ⇒ NO se emite la venta y ``auto_kill_state`` queda en
  ``SYSTEM_ERROR`` de forma DURABLE.

Gobierno de honestidad (patrón del repo): sin PostgreSQL real se hace ``pytest.skip``;
con ``AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. La
venue es PAPER virtual: NUNCA se abre el bridge LIVE y no se mueve el sello ``.160``.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import socket
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
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
_REQUIRED_ENV = "AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED"
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper_material_readiness.py"

#: Prefijo de instrumento determinista (el id final lo elige la sonda de fill).
_PREFIX = "inst-rroute-"
#: Reloj PINNED del harness: barra D1 ``B`` = día de este instante (UTC).
_CLOCK_DAY = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
#: Barras CERRADAS que alimentan la señal/ATR/régimen: terminan en ``B-1``.
_CLOSED_BARS = 80
_TREND_START = 96.0
_TREND_STEP = 0.12
#: Índices ``0..74`` de la tendencia; después un retroceso de 4 barras que deja la SMA(2)
#: POR DEBAJO de la SMA(4) y un salto final en ``B-1`` que produce el cruce ALCISTA.
_TREND_BARS = 75
_DIP_CLOSES = (104.30, 103.70, 103.10, 102.50)
_CROSS_CLOSE = 105.50
#: Barra CORRIENTE ``B`` (ejecución = ``open``) y ``B+1`` (rompe el stop estructural).
_DAY_B_OPEN = 105.60
_DAY_B_CLOSE = 105.80
_DAY_B1_OPEN = 100.00
_DAY_B1_CLOSE = 100.00
_HALF_RANGE = 0.40
_LOT = 100.0
_ENTRY_TICKS = 12
_EXIT_TICKS = 12
_SIDE_BUY = "buy"
_SIDE_SELL = "sell"


# ── Gobierno honesto del PostgreSQL ─────────────────────────────────────────────────


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            "PostgreSQL requerido para el E2E de la RUTA REAL del productor pero no "
            f"disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (E2E ruta real del productor) no disponible: {exc}")


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
    """TCP preflight rápido para que un host caído sea skip inmediato, no un cuelgue."""
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
def real_route_pg() -> None:
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


# ── Serie de barras D1 (decisión en B-1, ejecución en B) ────────────────────────────


def _closed_closes() -> list[float]:
    """Cierres de las barras CERRADAS (la última es ``B-1``).

    Tendencia alcista (régimen ``trend_up`` medido, no forzado por env) + retroceso de 4
    barras + salto final. El retroceso deja ``SMA(2) <= SMA(4)`` en ``B-2`` y el salto
    produce el cruce alcista EXACTAMENTE en ``B-1``, que es la barra que evalúa la ACTIVE.
    """
    closes = [_TREND_START + _TREND_STEP * index for index in range(_TREND_BARS)]
    closes.extend(_DIP_CLOSES)
    closes.append(_CROSS_CLOSE)
    return closes


def _closed_bar_rows(closed_as_of: str) -> list[tuple[str, float, float, float, float]]:
    """(día, open, high, low, close) de las barras cerradas, terminando en ``closed_as_of``."""
    closes = _closed_closes()
    end = date.fromisoformat(closed_as_of)
    rows: list[tuple[str, float, float, float, float]] = []
    for index, close in enumerate(closes):
        day = (end - timedelta(days=len(closes) - 1 - index)).isoformat()
        open_ = close - _TREND_STEP if index == 0 else closes[index - 1]
        rows.append(
            (
                day,
                open_,
                max(open_, close) + _HALF_RANGE,
                min(open_, close) - _HALF_RANGE,
                close,
            )
        )
    return rows


def _current_bar_row(day: str, *, open_: float, close: float) -> tuple[str, float, float, float, float]:
    return (
        day,
        open_,
        max(open_, close) + _HALF_RANGE,
        min(open_, close) - _HALF_RANGE,
        close,
    )


async def _seed_bars(
    factory: async_sessionmaker[AsyncSession],
    instrument_id: str,
    rows: list[tuple[str, float, float, float, float]],
) -> None:
    from bolsa_infrastructure.database.models.tables import OhlcvBarRow
    from bolsa_infrastructure.ids import new_id

    async with factory() as session:
        for day, open_, high, low, close in rows:
            open_d = Decimal(str(open_))
            close_d = Decimal(str(close))
            session.add(
                OhlcvBarRow(
                    id=new_id(),
                    instrument_id=instrument_id,
                    timeframe="1d",
                    timestamp=datetime.fromisoformat(f"{day}T00:00:00+00:00"),
                    open=open_d,
                    high=Decimal(str(high)),
                    low=Decimal(str(low)),
                    close=close_d,
                    volume=1000,
                    adj_close=close_d,
                    source="yahoo",
                    created_at=datetime.now(UTC),
                )
            )
        await session.commit()


# ── Semillas: cuenta, instrumento, edge y estrategia ACTIVE ─────────────────────────


async def _seed_account(session: AsyncSession) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"AUTO-RROUTE-{uuid.uuid4().hex[:8]}",
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
            symbol=f"RRT{uuid.uuid4().hex[:6].upper()}",
            yahoo_symbol=f"RRT{uuid.uuid4().hex[:8]}",
            isin=None,
            name="AUTO-real-route-E2E",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            # Gates fail-closed REALES: sector + fundamentales FRESCOS (sin ellos el motor
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


async def _seed_edge_report(
    session: AsyncSession, *, account_id: str, strategy_ref: str
) -> None:
    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    session.add(
        EdgeReportRow(
            id=f"edge-rroute-{uuid.uuid4().hex[:10]}",
            version="v2.88-real-route-e2e",
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


async def _seed_active_strategy(
    factory: async_sessionmaker[AsyncSession],
    *,
    instrument_id: str,
) -> tuple[str, str]:
    """Persiste la ACTIVE REAL (candidata + versión finalista + promoción) y devuelve ids.

    Es la MISMA fuente que lee ``get_active`` en producción (``strategy_candidates`` +
    ``strategy_versions`` + ``strategy_promotions``) y la misma forma de definición que
    escribe el promotor (``champion_params`` + ``executable`` del preset SMA).
    """
    from bolsa_application.strategy_executable_definition import build_executable_definition
    from bolsa_application.strategy_lifecycle_store import (
        PostgresStrategyLifecycleStore,
        StrategyPromotionRecord,
    )
    from bolsa_domain.entities.strategy_lifecycle import (
        StrategyFinalist,
        StrategyPromotion,
    )
    from bolsa_infrastructure.database.models.tables import StrategyCandidateRow

    suffix = uuid.uuid4().hex[:10]
    candidate_id = f"cand-rroute-{suffix}"
    version_id = f"v-route-{suffix}"
    champion_params = {"fastPeriod": 2, "slowPeriod": 4}
    executable = build_executable_definition("sma_crossover", champion_params)
    assert executable is not None, "el preset SMA debe producir una definición ejecutable"
    definition: dict[str, Any] = {
        "instrument_id": instrument_id,
        "watch": [instrument_id],
        "lot_qty": _LOT,
        "champion_params": champion_params,
        "executable": executable,
    }
    definition_hash = hashlib.sha256(
        json.dumps(definition, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    created_at = datetime.now(UTC).isoformat()

    async with factory() as session:
        now = datetime.now(UTC)
        session.add(
            StrategyCandidateRow(
                id=candidate_id,
                instrument_id=instrument_id,
                strategy_family="sma_crossover",
                params=dict(champion_params),
                origin="estudio",
                data_snapshot_id=None,
                preset_key="sma_crossover",
                strategy_definition_id="sma_crossover",
                state="estudio",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

        store = PostgresStrategyLifecycleStore(session)
        await store.save_finalist(
            StrategyFinalist(
                candidate_id=candidate_id,
                version_id=version_id,
                name="SMA 2/4 (ruta real)",
                definition_hash=definition_hash,
                definition=definition,
                created_at=created_at,
                preset_key="sma_crossover",
            )
        )
        await store.save_promotion(
            StrategyPromotionRecord(
                promotion=StrategyPromotion(
                    finalist_id=version_id,
                    promoted=True,
                    reasons=(),
                    shadow_validated=True,
                ),
                candidate_id=candidate_id,
                instrument_id=instrument_id,
                version_id=version_id,
                created_at=created_at,
            )
        )
    return version_id, candidate_id


# ── Sonda determinista de fill (el book SIM llena o no según seed/símbolo) ──────────


def _bar_tick_for_day(day: str) -> int:
    from bolsa_application.closed_bars import bar_tick

    return bar_tick(datetime.fromisoformat(f"{day}T10:00:00+00:00"), "1d")


def _route_clock() -> tuple[str, str]:
    """(día de la barra corriente ``B``, ``as_of`` de decisión ``B-1``) según el motor.

    Se usan las MISMAS primitivas que el worker (``bar_window``/``last_closed_bar_day``)
    para no codificar a mano el anclaje del timeframe: el harness siembra exactamente las
    fechas que el motor va a pedir.
    """
    from bolsa_application.closed_bars import bar_window, last_closed_bar_day

    window = bar_window(_CLOCK_DAY, "1d")
    assert window is not None, "el timeframe D1 debe tener ventana legible"
    return window[0][:10], last_closed_bar_day(_CLOCK_DAY, "1d")


def _filling_instrument_id(*, buy_tick: int, sell_tick: int, buy_mid: float, sell_mid: float) -> str:
    """Id determinista que LLENA la compra en ``B`` y la venta en ``B+1``.

    Sin esta sonda el sorteo del venue podría dejar la entrada sin llenar y el rojo sería
    espurio (no un defecto del productor). No altera ningún precio: solo elige un id cuyo
    plan de cola es "ok" en las DOS barras que el run atraviesa.
    """
    from bolsa_application.simulated_broker import fill_seed, simulated_fill_schedule

    for number in range(256):
        candidate = f"{_PREFIX}{number:010d}"
        buy = simulated_fill_schedule(
            instrument_id=candidate,
            side=_SIDE_BUY,
            quantity=Decimal("100"),
            venue_order_id=f"probe-buy-{candidate}",
            seed=fill_seed(buy_tick, candidate),
            fill_chunks=4,
            base_mid=buy_mid,
        ).fills
        sell = simulated_fill_schedule(
            instrument_id=candidate,
            side=_SIDE_SELL,
            quantity=Decimal("100"),
            venue_order_id=f"probe-sell-{candidate}",
            seed=fill_seed(sell_tick, candidate),
            fill_chunks=4,
            base_mid=sell_mid,
        ).fills
        if buy and sell:
            return candidate
    raise AssertionError(
        f"ningún id determinista de {_PREFIX} llena compra en {buy_tick} y venta en {sell_tick}"
    )


# ── Entorno de la RUTA REAL (sin inyección de fuentes) ──────────────────────────────


def _configure_real_route_env(monkeypatch: pytest.MonkeyPatch, instrument_id: str) -> None:
    """Fija SOLO configuración declarada: ni precios ni fuentes inyectadas.

    Enciende el precio REAL (``AUTO_ENGINE_SIM_REAL_PRICE=1``), la estrategia ACTIVE con su
    SignalEvaluator y el pipeline V2. NO se fija ``AUTO_ENGINE_SIM_V2_REGIME``: el régimen
    se MIDE de las barras sembradas. NO se inyecta ``price_script``/``price_source``/
    ``atr_source``/``sector_source``/``liquidity_source``/``edge_source``.
    """
    from bolsa_application.auto_v2_entry import V2_ENGINE_ENV

    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_ENGINE_SIM_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_TOP_N", "5")
    monkeypatch.setenv("AUTO_ENGINE_SIM_LOT_QTY", str(int(_LOT)))
    monkeypatch.setenv("AUTO_ENGINE_SIM_INTERVAL_SECONDS", "1.0")
    # El interruptor que la ventana PAPER exporta: aquí SÍ es la ruta real.
    monkeypatch.setenv("AUTO_ENGINE_SIM_REAL_PRICE", "1")
    # Estrategia ACTIVE real desde PostgreSQL, evaluando su PROPIA definición ejecutable.
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", "1")
    monkeypatch.setenv("AUTO_OPERATIONAL_AUDIT", "1")
    # El gate PAPER se corre con esta venue: su guarda exige ``paper``.
    monkeypatch.setenv("BROKER_VENUE", "paper")


# ── Lectura del material durable (conexión NUEVA) ──────────────────────────────────


def _fill_primitives(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "execution_id": row.execution_id,
            "side": row.side,
            "quantity": Decimal(row.quantity),
            "price": Decimal(row.price),
            "reference_mid": None if row.reference_mid is None else Decimal(row.reference_mid),
            "price_source": row.price_source,
            "cycle_id": row.cycle_id,
            "strategy_version_id": row.strategy_version_id,
        }
        for row in rows
    ]


def _reservation_primitives(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "reservation_id": row.reservation_id,
            "side": row.side,
            "status": row.status,
            "cycle_id": row.cycle_id,
            "reserved_risk": None if row.reserved_risk is None else Decimal(row.reserved_risk),
            "quantity": None if row.quantity is None else Decimal(row.quantity),
            "remaining_qty": None if row.remaining_qty is None else Decimal(row.remaining_qty),
            "exit_order_id": row.exit_order_id,
        }
        for row in rows
    ]


def _exit_primitives(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "exit_order_id": row.exit_order_id,
            "side": row.side,
            "state": row.state,
            "emergency": bool(row.emergency),
            "cycle_id": row.cycle_id,
            "requested_qty": None if row.requested_qty is None else Decimal(row.requested_qty),
            "filled_qty": None if row.filled_qty is None else Decimal(row.filled_qty),
            "reservation_id": row.reservation_id,
        }
        for row in rows
    ]


async def _read_material(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> dict[str, Any]:
    from bolsa_infrastructure.database.models.tables import (
        AutoExitOrderRow,
        AutoKillStateRow,
        PortfolioReservationRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        fills = (
            await session.execute(
                select(SimFillFinanceContextRow)
                .where(SimFillFinanceContextRow.account_id == account_id)
                .order_by(SimFillFinanceContextRow.created_at.asc())
            )
        ).scalars().all()
        reservations = (
            await session.execute(
                select(PortfolioReservationRow)
                .where(PortfolioReservationRow.account_id == account_id)
                .order_by(PortfolioReservationRow.created_at.asc())
            )
        ).scalars().all()
        exits = (
            await session.execute(
                select(AutoExitOrderRow)
                .where(AutoExitOrderRow.account_id == account_id)
                .order_by(AutoExitOrderRow.created_at.asc())
            )
        ).scalars().all()
        kill = (
            await session.execute(
                select(AutoKillStateRow).where(AutoKillStateRow.account_id == account_id)
            )
        ).scalars().all()
    return {
        "fills": _fill_primitives(list(fills)),
        "reservations": _reservation_primitives(list(reservations)),
        "exits": _exit_primitives(list(exits)),
        "kill": [
            {
                "engine_id": row.engine_id,
                "engaged": bool(row.engaged),
                "reason": row.reason,
            }
            for row in kill
        ],
    }


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("real_route_paper_material_readiness", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _readiness(account_id: str, version_id: str) -> Any:
    """Ejecuta el lector REAL del CLI (conexión propia, sin mocks)."""
    module = _load_cli()
    return await module._read(  # noqa: SLF001 — el lector real del CLI es el sujeto.
        account_id,
        [version_id],
        limit=2000,
        min_cycles=32,
    )


# ── Limpieza ───────────────────────────────────────────────────────────────────────


async def _cleanup(
    *,
    account_id: str | None,
    engine_id: str,
    instrument_id: str | None,
    version_id: str | None,
    candidate_id: str | None,
) -> None:
    """Borra el residuo completo (el barrido autouse de conftest no cubre estas tablas)."""
    from bolsa_infrastructure.database.models.tables import (
        AdaptiveGateStateRow,
        AutoEngineRunRow,
        AutoEngineTickRow,
        AutoExitOrderRow,
        AutoKillStateRow,
        DecisionJournalEntryRow,
        EdgeReportRow,
        ExecutionEventRow,
        InstrumentRow,
        OhlcvBarRow,
        PortfolioReservationRow,
        SimAutoPositionRow,
        SimConsumedSignalRow,
        SimFillFinanceContextRow,
        StrategyCandidateRow,
        StrategyPromotionRow,
        StrategyVersionRow,
    )

    engine, factory = await _open_session_factory()
    try:
        async with factory() as session:
            if account_id:
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
                    delete(SimConsumedSignalRow).where(
                        SimConsumedSignalRow.account_id == account_id
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
                await session.execute(
                    delete(AutoKillStateRow).where(AutoKillStateRow.account_id == account_id)
                )
                await session.execute(
                    delete(AdaptiveGateStateRow).where(
                        AdaptiveGateStateRow.account_id == account_id
                    )
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
            if version_id:
                await session.execute(
                    delete(StrategyPromotionRow).where(
                        StrategyPromotionRow.finalist_id == version_id
                    )
                )
                await session.execute(
                    delete(StrategyVersionRow).where(StrategyVersionRow.id == version_id)
                )
            if candidate_id:
                await session.execute(
                    delete(StrategyCandidateRow).where(StrategyCandidateRow.id == candidate_id)
                )
            if instrument_id:
                await session.execute(
                    delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id)
                )
                await session.execute(
                    delete(InstrumentRow).where(InstrumentRow.id == instrument_id)
                )
            await session.commit()

        if account_id:
            from tests.conftest import purge_accounts

            await purge_accounts(factory, [account_id])
    finally:
        await engine.dispose()


# ── El escenario (una corrida completa de la ruta real) ────────────────────────────


def _force_exit_persist_failure(worker: Any, *, mode: str) -> None:
    """Envuelve SOLO el guardado del INTENT de salida (no el motor ni el store)."""
    real_save = worker._v2_save_exit_order  # noqa: SLF001 — seam del test, no del motor.
    calls = {"failed": 0}

    async def _fail_first(order: Any) -> bool:
        if mode == "emergency" and calls["failed"] == 0:
            calls["failed"] += 1
            return False
        if mode == "halt":
            calls["failed"] += 1
            return False
        return bool(await real_save(order))

    worker._v2_save_exit_order = _fail_first  # noqa: SLF001 — instancia del test.


def _prepare(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, str]:
    """Resuelve el reloj PINNED y deja el entorno con el watch REAL ya fijado.

    El id del instrumento es determinista a partir del tick de compra/venta, pero el
    worker lo necesita en ``AUTO_ENGINE_SIM_WATCH`` ANTES de construirse. Por eso el
    llamante lo resuelve aquí, con las mismas primitivas de barras del motor, y lo
    devuelve para sembrar el escenario. Devuelve ``(instrument_id, day_b, closed_as_of)``.
    """
    day_b, closed_as_of = _route_clock()
    day_b1 = (date.fromisoformat(day_b) + timedelta(days=1)).isoformat()
    instrument_id = _filling_instrument_id(
        buy_tick=_bar_tick_for_day(day_b),
        sell_tick=_bar_tick_for_day(day_b1),
        buy_mid=_DAY_B_OPEN,
        sell_mid=_DAY_B1_OPEN,
    )
    _configure_real_route_env(monkeypatch, instrument_id)
    return instrument_id, day_b, closed_as_of


async def _run_route(
    *,
    scenario: str,
    with_current_bar: bool,
    instrument_id: str,
    day_b: str,
    closed_as_of: str,
) -> dict[str, Any]:
    """Conduce la ruta real (o su control negativo) y devuelve los hechos medidos.

    ``scenario``: ``"positive"`` | ``"exit_emergency"`` | ``"exit_halt"``.
    ``with_current_bar``: ``False`` omite la barra ``B`` (control de ``precio AUSENTE``).
    ``instrument_id``/``day_b``/``closed_as_of`` los resuelve el llamante con el MISMO
    reloj PINNED, para poder fijar el watch del entorno antes de construir el worker.

    Los controles de ENTRADA (sin store / claim rechazado / claim con excepción) se
    instalan por ``monkeypatch`` ANTES de llamar aquí (parchean el seam de composición).
    """
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
        load_active_strategy_decider,
    )

    engine, factory = await _open_session_factory()
    account_id: str | None = None
    version_id: str | None = None
    candidate_id: str | None = None
    engine_id = f"auto-rroute-{uuid.uuid4().hex[:10]}"
    try:
        holder = {"now": _CLOCK_DAY}
        day_b1 = (date.fromisoformat(day_b) + timedelta(days=1)).isoformat()

        async with factory() as session:
            account_id = await _seed_account(session)
            await _seed_instrument(session, instrument_id)
        version_id, candidate_id = await _seed_active_strategy(
            factory, instrument_id=instrument_id
        )
        async with factory() as session:
            await _seed_edge_report(session, account_id=account_id, strategy_ref=version_id)

        bars = _closed_bar_rows(closed_as_of)
        if with_current_bar:
            bars.append(_current_bar_row(day_b, open_=_DAY_B_OPEN, close=_DAY_B_CLOSE))
        bars.append(_current_bar_row(day_b1, open_=_DAY_B1_OPEN, close=_DAY_B1_CLOSE))
        await _seed_bars(factory, instrument_id, bars)

        worker = AutoSimulationWorker(
            engine_id=engine_id,
            account_id=account_id,
            clock=lambda: holder["now"],
        )
        # El reloj PINNED debe resolver EXACTAMENTE las fronteras que el harness sembró.
        assert worker._v2_current_bar_day() == day_b  # noqa: SLF001 — coherencia del harness.
        assert worker._v2_closed_bar_as_of() == closed_as_of  # noqa: SLF001
        runtime = AutoSimRuntime(factory, worker=worker, engine_id=engine_id, account_id=account_id)

        async def _install_decider() -> Any:
            """Decider de PRODUCCIÓN (no un fake), refrescado por tick como el loop."""
            decider = await load_active_strategy_decider(
                factory,
                instrument_id=instrument_id,
                watch=(instrument_id,),
                lot_qty=_LOT,
                signal_enabled=True,
                as_of=worker._v2_closed_bar_as_of(),  # noqa: SLF001 — frontera B-1.
            )
            assert decider is not None, "la ruta real exige la ACTIVE de PostgreSQL"
            runtime.set_decider(decider)
            return decider

        decider = await _install_decider()
        entry_package = decider(instrument_id)
        assert entry_package.action == "BUY", (
            "la ACTIVE debe producir el cruce alcista en B-1 (no HOLD): "
            f"action={entry_package.action} source={entry_package.source}"
        )
        assert entry_package.source.startswith(f"active-strategy:{version_id}"), (
            "la propuesta debe atribuir la versión ACTIVE exacta: " f"{entry_package.source}"
        )

        opened = False
        for _ in range(_ENTRY_TICKS):
            holder["now"] = _CLOCK_DAY
            await _install_decider()
            await runtime.run_tick()
            if worker._open.get(instrument_id, Decimal("0")) > 0:  # noqa: SLF001
                opened = True
                break

        closed = False
        if opened:
            if scenario in {"exit_emergency", "exit_halt"}:
                _force_exit_persist_failure(worker, mode=scenario.removeprefix("exit_"))
            for _ in range(_EXIT_TICKS):
                holder["now"] = datetime.fromisoformat(f"{day_b1}T10:00:00+00:00")
                await _install_decider()
                await runtime.run_tick()
                if worker._open.get(instrument_id, Decimal("0")) <= 0:  # noqa: SLF001
                    closed = True
                    break

        missing = dict(worker.price_missing_counts)
        open_qty = Decimal(worker._open.get(instrument_id, Decimal("0")))  # noqa: SLF001

        # Frontera de durabilidad: se cortan TODAS las conexiones del productor.
        await engine.dispose()
        new_engine, new_factory = await _open_session_factory()
        try:
            material = await _read_material(new_factory, account_id)
            readiness = await _readiness(account_id, version_id)
        finally:
            await new_engine.dispose()

        return {
            "account_id": account_id,
            "instrument_id": instrument_id,
            "version_id": version_id,
            "candidate_id": candidate_id,
            "engine_id": engine_id,
            "day_b": day_b,
            "closed_as_of": closed_as_of,
            "opened": opened,
            "closed": closed,
            "open_qty": open_qty,
            "missing": missing,
            "entry_action": entry_package.action,
            "entry_source": entry_package.source,
            **material,
            "readiness": readiness,
        }
    finally:
        await engine.dispose()
        if account_id is not None:
            await _cleanup(
                account_id=account_id,
                engine_id=engine_id,
                instrument_id=instrument_id,
                version_id=version_id,
                candidate_id=candidate_id,
            )


# ── Positivo: la ruta real abre, reserva, cierra y el gate lo reconstruye ──────────


def test_real_route_opens_reserves_closes_and_gate_rebuilds_producer_ready(
    real_route_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E POSITIVO: barra D1 real + ACTIVE real ⇒ ciclo durable y ``PRODUCER_READY``."""
    # Entorno con el watch REAL ya fijado: no se inyecta ninguna fuente de precio.
    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)

    result = asyncio.run(
        _run_route(
            scenario="positive",
            with_current_bar=True,
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
        )
    )
    version_id = result["version_id"]

    assert result["opened"] is True, "la ruta real abre con precio de barra (sin price_script)"
    assert result["closed"] is True, "el stop estructural cierra el ciclo por el camino real"
    assert result["open_qty"] == 0, "el libro queda plano tras el cierre"
    assert not result["missing"], "la ruta real no debe declarar precio AUSENTE"

    fills = result["fills"]
    assert fills, "hay fills durables"
    buys = [fill for fill in fills if fill["side"] == "buy"]
    sells = [fill for fill in fills if fill["side"] == "sell"]
    assert buys and sells, f"round-trip completo: buys={len(buys)} sells={len(sells)}"

    entry = buys[0]
    # (1) La fuente del precio es la REAL de barras (nunca el 100.0 sintético).
    assert entry["price_source"] == "MARKET_CLOSE"
    assert entry["reference_mid"] == Decimal(str(_DAY_B_OPEN)), (
        "el mid de referencia del fill DEBE ser open(B) de la barra sembrada: "
        f"{entry['reference_mid']}"
    )
    # El precio materializado es el mid de la barra ± fricción del venue SIM (bps).
    slippage_bps = abs(entry["price"] - entry["reference_mid"]) / entry["reference_mid"] * 10_000
    assert slippage_bps <= 50, f"fricción SIM fuera de rango: {slippage_bps} bps"
    # (2) Atribución: la versión ACTIVE real, sin el sufijo de preset en la identidad.
    assert entry["strategy_version_id"] == version_id
    assert entry["cycle_id"], "el fill nace con ciclo financiero (V2.47)"
    assert entry["cycle_id"] != "", "un fill sin cycle_id no certifica el productor"

    cycle_id = entry["cycle_id"]
    assert all(fill["cycle_id"] == cycle_id for fill in fills), (
        "todos los fills del round-trip comparten el MISMO cycle_id"
    )

    # (3) La reserva de ENTRADA es durable, con denominador positivo y el MISMO ciclo.
    entry_reservations = [
        row
        for row in result["reservations"]
        if row["side"] == "buy" and row["cycle_id"] == cycle_id
    ]
    assert entry_reservations, "no hay aprobación sin reserva: falta la fila de entrada"
    reservation = entry_reservations[0]
    assert reservation["reserved_risk"] is not None and reservation["reserved_risk"] > 0

    # (4) La salida tiene identidad durable y hereda el ciclo de la posición.
    exit_orders = [row for row in result["exits"] if row["cycle_id"] == cycle_id]
    assert exit_orders, "la salida debe dejar un INTENT durable con el mismo cycle_id"
    assert any(row["side"] == "sell" for row in result["exits"])

    # (5) El gate REAL reconstruye la ESTRUCTURA desde una conexión nueva.
    readiness = result["readiness"]
    facts = readiness.facts
    lineage = readiness.lineage
    assert readiness.producer_ready is True, (
        f"el productor debe quedar PRODUCER_READY: {readiness.verdict} {readiness.producer_blockers}"
    )
    assert readiness.verdict == READINESS_PRODUCER_READY
    assert readiness.producer_blockers == ()
    assert readiness.evidence_ready is False
    assert BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES in readiness.blockers

    assert facts["durableFills"] > 0
    assert facts["fillsWithCycle"] == facts["durableFills"]
    assert facts["fillsWithoutCycle"] == 0
    assert facts["reservations"] > 0
    assert facts["reservationsWithCycle"] > 0
    assert facts["closedCycles"] >= 1
    assert facts["measurableCycles"] >= 1
    assert facts["perVersion"][version_id]["measurableCycles"] >= 1
    assert lineage["cycle"]["exitOrdersWithCycle"] >= 1
    assert lineage["closure"]["closedCyclesWithRisk"] >= 1


# ── Negativos de ENTRADA ───────────────────────────────────────────────────────────


def test_real_route_without_reservation_store_vetoes_the_entry(
    real_route_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin espejo de reservas la aprobación NO se emite (``RESERVATION_UNMEASURABLE``)."""
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker

    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)
    original_real_turn = AutoSimulationWorker.real_turn

    async def _real_turn_without_reservations(self: Any, **kwargs: Any) -> Any:
        kwargs["reservation_store"] = None
        return await original_real_turn(self, **kwargs)

    monkeypatch.setattr(AutoSimulationWorker, "real_turn", _real_turn_without_reservations)

    result = asyncio.run(
        _run_route(
            scenario="positive",
            with_current_bar=True,
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
        )
    )

    assert result["opened"] is False, "sin reserva durable no hay apertura (fail-closed)"
    assert result["fills"] == [], "no puede haber NINGÚN fill sin compromiso durable"
    assert result["reservations"] == [], "no debe existir fila de reserva"
    assert result["readiness"].producer_ready is False


def test_real_route_rejected_claim_vetoes_the_entry_and_does_not_duplicate(
    real_route_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``save_claim`` perdido (carrera) ⇒ veto y ni un fill ni una reserva duplicada."""
    import bolsa_application.reservation_store as reservation_store_module

    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)
    real_store_cls = reservation_store_module.PostgresReservationStore

    class _RejectingClaimStore:
        def __init__(self, session: Any) -> None:
            self._inner = real_store_cls(session)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        async def save_claim(self, reservation: Any) -> bool:
            return False

    monkeypatch.setattr(
        reservation_store_module, "PostgresReservationStore", _RejectingClaimStore
    )

    result = asyncio.run(
        _run_route(
            scenario="positive",
            with_current_bar=True,
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
        )
    )

    assert result["opened"] is False, "una carrera perdida no se convierte en apertura"
    assert result["fills"] == [], "un claim perdido no puede producir un fill huérfano"
    assert result["reservations"] == [], "el claim nunca llegó a persistir la fila"


def test_real_route_claim_exception_leaves_no_orphan_fill(
    real_route_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``save_claim`` que lanza ⇒ 0 fills y ninguna fila huérfana de contexto financiero."""
    import bolsa_application.reservation_store as reservation_store_module

    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)
    real_store_cls = reservation_store_module.PostgresReservationStore

    class _ExplodingClaimStore:
        def __init__(self, session: Any) -> None:
            self._inner = real_store_cls(session)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        async def save_claim(self, reservation: Any) -> bool:
            raise RuntimeError("claim_store_unavailable")

    monkeypatch.setattr(
        reservation_store_module, "PostgresReservationStore", _ExplodingClaimStore
    )

    result = asyncio.run(
        _run_route(
            scenario="positive",
            with_current_bar=True,
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
        )
    )

    assert result["opened"] is False, "una excepción en el claim no autoriza a emitir"
    assert result["fills"] == [], "sin reserva durable no puede quedar contexto de fill"
    assert result["reservations"] == [], "el alta fallida no deja fila de reserva"


def test_real_route_missing_current_bar_fails_closed_to_hold(
    real_route_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin barra ``B`` no hay precio de ejecución: HOLD declarado y 0 fills.

    Es el control que impide "arreglar" el E2E fabricando precio: el proveedor REAL dice
    ``no hay precio`` y el motor NO cae a ``close(B-1)`` ni a ``100.0``.
    """
    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)

    result = asyncio.run(
        _run_route(
            scenario="positive",
            with_current_bar=False,
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
        )
    )

    assert result["opened"] is False
    assert result["missing"].get(result["instrument_id"], 0) > 0, (
        "la ausencia de precio debe contar y declararse (no fallar en silencio): "
        f"{result['missing']}"
    )
    assert result["fills"] == [], "precio AUSENTE ⇒ ni un fill"
    assert result["readiness"].producer_ready is False


# ── Negativos de SALIDA ────────────────────────────────────────────────────────────


def test_real_route_exit_intent_falls_back_to_emergency_and_still_sells(
    real_route_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si el INTENT de salida no es durable, se persiste ``EMERGENCY`` y SÍ se vende."""
    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)

    result = asyncio.run(
        _run_route(
            scenario="exit_emergency",
            with_current_bar=True,
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
        )
    )

    assert result["opened"] is True, "la entrada sigue siendo real (precio de barra)"
    assert result["closed"] is True, "reducir riesgo nunca se bloquea por un fallo de reserva"

    sells = [fill for fill in result["fills"] if fill["side"] == "sell"]
    assert sells, "la venta de emergencia se emite"
    cycle_id = sells[0]["cycle_id"]
    assert cycle_id, "la venta hereda el ciclo de la posición"

    emergency = [row for row in result["exits"] if row["cycle_id"] == cycle_id]
    assert emergency, "la fila de emergencia hereda el MISMO cycle_id"
    assert any(row["emergency"] for row in emergency), (
        f"debe quedar constancia EMERGENCY: {[row['state'] for row in emergency]}"
    )
    assert result["kill"] == [] or all(not row["engaged"] for row in result["kill"]), (
        "una salida de emergencia NO debe dejar el sistema parado"
    )


def test_real_route_exit_intent_and_emergency_failure_halts_durably(
    real_route_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si INTENT y emergencia fallan: NO se emite la venta y el HALT es durable."""
    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)

    result = asyncio.run(
        _run_route(
            scenario="exit_halt",
            with_current_bar=True,
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
        )
    )

    assert result["opened"] is True
    assert result["closed"] is False, "no se vende sin identidad durable de la salida"
    assert [fill for fill in result["fills"] if fill["side"] == "sell"] == [], (
        "una salida sin rastro durable JAMÁS se emite"
    )
    assert result["open_qty"] > 0, "la posición sigue abierta (no se fabricó un cierre)"

    # El HALT se lee desde una CONEXIÓN NUEVA: es estado del SISTEMA, no del proceso.
    assert result["kill"], "la parada dura debe quedar persistida"
    system_error = [row for row in result["kill"] if row["reason"] == "SYSTEM_ERROR"]
    assert system_error, f"motivo esperado SYSTEM_ERROR: {result['kill']}"
    assert all(row["engaged"] for row in system_error)
