"""Mundo REAL compartido por los E2E de la cadena AUTO/ESTUDIO (PostgreSQL).

Extraído de ``test_auto_real_route_producer_pg.py`` para que el E2E de la cadena diaria
señal→ciclo→DÍA-D y el seed del navegador usen EL MISMO mundo sembrado. No se duplica el
escenario: barras D1, cuenta PAPER, instrumento con gates reales, edge y estrategia ACTIVE
viven aquí una sola vez.

Contrato:
* Sembrar es determinista (reloj PINNED y serie de cierres fija); el productor lee barras
  reales de ``ohlcv_bars`` y la ACTIVE real de PostgreSQL.
* Limpiar borra TODO el residuo del escenario (``cleanup_world``).
* Un fallo de infraestructura se declara con ``require_or_skip``: con el env de gobierno a
  ``1`` un skip silencioso es FALLO duro.
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

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REPO_ROOT = Path(__file__).resolve().parents[4]
DOTENV_PATH = _REPO_ROOT / ".env"
READINESS_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "paper_material_readiness.py"
)

#: Reloj PINNED del harness: barra D1 ``B`` = día de este instante (UTC).
CLOCK_DAY = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
#: Barras CERRADAS que alimentan la señal/ATR/régimen: terminan en ``B-1``.
CLOSED_BARS = 80
TREND_START = 96.0
TREND_STEP = 0.12
#: Índices ``0..74`` de la tendencia; después un retroceso de 4 barras que deja la SMA(2)
#: POR DEBAJO de la SMA(4) y un salto final en ``B-1`` que produce el cruce ALCISTA.
TREND_BARS = 75
#: Cierre de la ÚLTIMA barra de tendencia (justo por encima del retroceso). Con más
#: contexto (p.ej. 210 barras para que SMA200 sea calculable) el paso se recalcula para
#: terminar SIEMPRE aquí: si no, la serie se convertiría en un desplome del último día y
#: el escenario dejaría de ser «tendencia con retroceso + cruce».
TREND_END = TREND_START + TREND_STEP * (TREND_BARS - 1)
DIP_CLOSES = (104.30, 103.70, 103.10, 102.50)
CROSS_CLOSE = 105.50
#: Barra CORRIENTE ``B`` (ejecución = ``open``) y ``B+1`` (rompe el stop estructural).
DAY_B_OPEN = 105.60
DAY_B_CLOSE = 105.80
DAY_B1_OPEN = 100.00
DAY_B1_CLOSE = 100.00
HALF_RANGE = 0.40
LOT = 100.0
ENTRY_TICKS = 12
EXIT_TICKS = 12
SIDE_BUY = "buy"
SIDE_SELL = "sell"

#: Prefijo de instrumento determinista (el id final lo elige la sonda de fill).
PREFIX = "inst-rroute-"

_BAR = tuple[str, float, float, float, float]


# ── Gobierno honesto del PostgreSQL ─────────────────────────────────────────────────


def require_or_skip(exc: Exception, *, env_name: str) -> None:
    """Skip honesto; con el env de gobierno a ``1`` el skip es un FALLO duro."""
    if os.environ.get(env_name) == "1":
        raise AssertionError(
            f"PostgreSQL requerido ({env_name}) pero no disponible: {exc}"
        ) from exc
    import pytest

    pytest.skip(f"PostgreSQL/Alembic no disponible ({env_name}): {exc}")


async def open_session_factory() -> tuple[Any, Any]:
    """(motor, session_factory) contra la BD real, con migración garantizada."""
    from dotenv import load_dotenv

    load_dotenv(DOTENV_PATH, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    return engine, create_session_factory(engine)


def unreachable_reason(database_url: str, *, timeout: float = 2.0) -> str | None:
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


async def probe_pg() -> None:
    engine, _factory = await open_session_factory()
    await engine.dispose()


def gate_pg(env_name: str) -> None:
    """Gate honesto reutilizable: sin PostgreSQL real se salta (o falla con el env)."""
    from dotenv import load_dotenv

    from bolsa_infrastructure.config import get_settings

    load_dotenv(DOTENV_PATH, override=False)
    get_settings.cache_clear()
    reason = unreachable_reason(get_settings().database_url or "")
    if reason is not None:
        require_or_skip(RuntimeError(reason), env_name=env_name)
    try:
        asyncio.run(probe_pg())
    except Exception as exc:  # noqa: BLE001 — gate honesto por env.
        require_or_skip(exc, env_name=env_name)
        raise


# ── Serie de barras D1 (decisión en B-1, ejecución en B) ────────────────────────────


def closed_closes(closed_bars: int = CLOSED_BARS) -> list[float]:
    """Cierres de las barras CERRADAS (la última es ``B-1``).

    Tendencia alcista (régimen ``trend_up`` medido, no forzado por env) + retroceso de 4
    barras + salto final. El retroceso deja ``SMA(2) <= SMA(4)`` en ``B-2`` y el salto
    produce el cruce alcista EXACTAMENTE en ``B-1``, que es la barra que evalúa la ACTIVE.

    ``closed_bars`` permite escenarios con más contexto (el replay DÍA-D simula 90 días
    previos a ``D``); el patrón final —retroceso + cruce— se conserva, de modo que la
    frontera de decisión sigue siendo la MISMA.
    """
    trend = max(len(DIP_CLOSES) + 2, int(closed_bars) - len(DIP_CLOSES) - 1)
    # Extremo anclado: el paso se recalcula cuando el número de barras cambia, de modo
    # que la frontera (retroceso + cruce en ``B-1``) queda EXACTAMENTE igual y la serie
    # sigue siendo una tendencia alcista con un retroceso corto.
    step = (
        TREND_STEP if trend == TREND_BARS else (TREND_END - TREND_START) / (trend - 1)
    )
    closes = [TREND_START + step * index for index in range(trend)]
    closes.extend(DIP_CLOSES)
    closes.append(CROSS_CLOSE)
    return closes


def closed_bar_rows(
    closed_as_of: str, *, closed_bars: int = CLOSED_BARS
) -> list[_BAR]:
    """(día, open, high, low, close) de las barras cerradas, terminando en ``closed_as_of``."""
    closes = closed_closes(closed_bars)
    end = date.fromisoformat(closed_as_of)
    rows: list[_BAR] = []
    for index, close in enumerate(closes):
        day = (end - timedelta(days=len(closes) - 1 - index)).isoformat()
        open_ = close - TREND_STEP if index == 0 else closes[index - 1]
        rows.append(
            (
                day,
                open_,
                max(open_, close) + HALF_RANGE,
                min(open_, close) - HALF_RANGE,
                close,
            )
        )
    return rows


def current_bar_row(day: str, *, open_: float, close: float) -> _BAR:
    return (
        day,
        open_,
        max(open_, close) + HALF_RANGE,
        min(open_, close) - HALF_RANGE,
        close,
    )


async def seed_bars(
    factory: Any,
    instrument_id: str,
    rows: list[_BAR],
    *,
    timeframe: str = "1d",
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
                    timeframe=timeframe,
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


async def seed_account(session: Any, *, name_prefix: str = "AUTO-RROUTE") -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"{name_prefix}-{uuid.uuid4().hex[:8]}",
        initial_deposit=100_000.0,
    )
    await session.commit()
    return scope.account.id


def strong_fundamentals(fetched_at: str) -> dict[str, Any]:
    """Fundamentales del PERFIL del instrumento (dato, no precio) sanos y medibles.

    No inventan cotización: son los ratios que el catálogo guarda en
    ``profile_snapshot.fundamentals``. ``fetched_at`` debe ser ≤ día del parte para que el
    corte point-in-time los use como *snapshot* (con un ``fetchedAt`` posterior el score
    fundamental queda BLOQUEADO por look-ahead, que es el comportamiento correcto).
    """
    return {
        "marketCap": 8.0e11,
        "advUsd": 2.0e9,
        "fetchedAt": fetched_at,
        "sourceVersion": "e2e-fundamentals-v1",
        "sector": "Technology",
        "trailingPe": 12.0,
        "forwardPe": 10.0,
        "roe": 0.38,
        "roic": 0.30,
        "operatingMargin": 0.35,
        "revenueGrowth": 0.30,
        "earningsGrowth": 0.35,
        "debtToEquity": 0.10,
        "currentRatio": 3.0,
        "freeCashflow": 8.0e10,
        "fcfYield": 0.12,
        "piotroski": 9,
        "altmanZ": 6.0,
    }


async def seed_instrument(
    session: Any,
    instrument_id: str,
    *,
    symbol_prefix: str = "RRT",
    fundamentals: dict[str, Any] | None = None,
) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    if await session.get(InstrumentRow, instrument_id) is not None:
        return

    now = datetime.now(UTC)
    snapshot_fundamentals = (
        dict(fundamentals)
        if fundamentals is not None
        else {"advUsd": 50_000_000.0, "fetchedAt": now.isoformat()}
    )
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"{symbol_prefix}{uuid.uuid4().hex[:6].upper()}",
            yahoo_symbol=f"{symbol_prefix}{uuid.uuid4().hex[:8]}",
            isin=None,
            name="AUTO-real-route-E2E",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            # Gates fail-closed REALES: sector + fundamentales FRESCOS (sin ellos el motor
            # veta por ``sector_unknown``/``liquidity_unknown``).
            sector="Technology",
            profile_snapshot={"fundamentals": snapshot_fundamentals},
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


async def seed_edge_report(
    session: Any,
    *,
    account_id: str,
    strategy_ref: str,
    prefix: str = "edge-rroute",
) -> None:
    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    session.add(
        EdgeReportRow(
            id=f"{prefix}-{uuid.uuid4().hex[:10]}",
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


async def seed_strategy_top(
    factory: Any,
    *,
    instrument_id: str,
    stars: float = 5.0,
    preset_key: str = "sma_crossover",
) -> str:
    """Persiste la foto TOP del instrumento (``instrument_strategy_tops``).

    Sin fila TOP el dictamen diario se queda en ``review_strategy``/``no_valid_top`` y el
    valor nunca llega a proponer: el stance exigiría un TOP vigente. Aquí se siembra el
    TOP REAL (misma tabla y forma que escribe el semifinal del embudo coach), con
    ``updated_at`` fresco para que no cuente como ``stale_top``.
    """
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import (
        InstrumentRow,
        InstrumentStrategyTopRow,
    )
    from bolsa_infrastructure.ids import new_id

    async with factory() as session:
        instrument = await session.get(InstrumentRow, instrument_id)
        assert instrument is not None, "el instrumento debe existir antes de su TOP"
        row = (
            await session.execute(
                select(InstrumentStrategyTopRow).where(
                    InstrumentStrategyTopRow.instrument_id == instrument_id,
                    InstrumentStrategyTopRow.timeframe == "1d",
                )
            )
        ).scalars().first()
        now = datetime.now(UTC)
        slots = [
            {
                "rank": 1,
                "stars": stars,
                "presetKey": preset_key,
                "strategyDefinitionId": preset_key,
                "note": "E2E: TOP vigente sembrado (no es validación estadística)",
            }
        ]
        if row is None:
            row = InstrumentStrategyTopRow(
                id=new_id(),
                instrument_id=instrument_id,
                symbol=instrument.symbol,
                timeframe="1d",
                period_label=None,
                status="semifinal",
                version=1,
                evidence_level="in_sample_only",
                slots=slots,
                coach_headline=None,
                coach_facts=None,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.slots = slots
            row.updated_at = now
        await session.commit()
        return row.id


async def seed_estudio_list(factory: Any, instrument_id: str) -> list[str]:
    """Añade el instrumento a la lista canónica ``estudio`` y devuelve la membresía previa.

    La lista canónica puede existir en la BD de desarrollo: NO se borra. Se guarda la
    membresía anterior para restaurarla EXACTA en la limpieza (el escenario no puede
    dejar residuo en un universo compartido).
    """
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        previous = await repo.ensure_estudio_list()
        before = list(previous.instrument_ids)
        if instrument_id not in before:
            await repo.update("estudio", instrument_ids=[*before, instrument_id])
        await session.commit()
    return before


async def restore_estudio_list(factory: Any, before: list[str]) -> None:
    """Devuelve la lista canónica a su membresía anterior (idempotente)."""
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        await repo.ensure_estudio_list()
        await repo.update("estudio", instrument_ids=list(before))
        await session.commit()


async def seed_active_strategy(
    factory: Any,
    *,
    instrument_id: str,
    lot_qty: float = LOT,
    fast_period: int = 2,
    slow_period: int = 4,
    prefix: str = "rroute",
    suffix: str | None = None,
) -> tuple[str, str]:
    """Persiste la ACTIVE REAL (candidata + versión finalista + promoción) y devuelve ids.

    Es la MISMA fuente que lee ``get_active`` en producción (``strategy_candidates`` +
    ``strategy_versions`` + ``strategy_promotions``) y la misma forma de definición que
    escribe el promotor (``champion_params`` + ``executable`` del preset SMA).

    ``suffix`` permite ids DETERMINISTAS (el seed dev del navegador los necesita para
    limpiar sin adivinar); omitido ⇒ aleatorio, como siempre.
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

    token = suffix or uuid.uuid4().hex[:10]
    candidate_id = f"cand-{prefix}-{token}"
    version_id = f"v-{prefix}-{token}"
    champion_params = {"fastPeriod": fast_period, "slowPeriod": slow_period}
    executable = build_executable_definition("sma_crossover", champion_params)
    assert executable is not None, "el preset SMA debe producir una definición ejecutable"
    definition: dict[str, Any] = {
        "instrument_id": instrument_id,
        "watch": [instrument_id],
        "lot_qty": lot_qty,
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


def bar_tick_for_day(day: str) -> int:
    from bolsa_application.closed_bars import bar_tick

    return bar_tick(datetime.fromisoformat(f"{day}T10:00:00+00:00"), "1d")


def route_clock(clock: datetime = CLOCK_DAY) -> tuple[str, str]:
    """(día de la barra corriente ``B``, ``as_of`` de decisión ``B-1``) según el motor.

    Se usan las MISMAS primitivas que el worker (``bar_window``/``last_closed_bar_day``)
    para no codificar a mano el anclaje del timeframe: el harness siembra exactamente las
    fechas que el motor va a pedir.
    """
    from bolsa_application.closed_bars import bar_window, last_closed_bar_day

    window = bar_window(clock, "1d")
    assert window is not None, "el timeframe D1 debe tener ventana legible"
    return window[0][:10], last_closed_bar_day(clock, "1d")


def filling_instrument_id(
    *,
    buy_tick: int,
    sell_tick: int,
    buy_mid: float,
    sell_mid: float,
    prefix: str = "inst-rroute-",
) -> str:
    """Id determinista que LLENA la compra en ``B`` y la venta en ``B+1``.

    Sin esta sonda el sorteo del venue podría dejar la entrada sin llenar y el rojo sería
    espurio (no un defecto del productor). No altera ningún precio: solo elige un id cuyo
    plan de cola es "ok" en las DOS barras que el run atraviesa.
    """
    from bolsa_application.simulated_broker import fill_seed, simulated_fill_schedule

    for number in range(256):
        candidate = f"{prefix}{number:010d}"
        buy = simulated_fill_schedule(
            instrument_id=candidate,
            side=SIDE_BUY,
            quantity=Decimal("100"),
            venue_order_id=f"probe-buy-{candidate}",
            seed=fill_seed(buy_tick, candidate),
            fill_chunks=4,
            base_mid=buy_mid,
        ).fills
        sell = simulated_fill_schedule(
            instrument_id=candidate,
            side=SIDE_SELL,
            quantity=Decimal("100"),
            venue_order_id=f"probe-sell-{candidate}",
            seed=fill_seed(sell_tick, candidate),
            fill_chunks=4,
            base_mid=sell_mid,
        ).fills
        if buy and sell:
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} llena compra en {buy_tick} y venta en {sell_tick}"
    )


# ── Entorno de la RUTA REAL (sin inyección de fuentes) ──────────────────────────────


def configure_real_route_env(
    monkeypatch: Any,
    instrument_id: str,
    *,
    lot_qty: float = LOT,
) -> None:
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
    monkeypatch.setenv("AUTO_ENGINE_SIM_LOT_QTY", str(int(lot_qty)))
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


def fill_primitives(rows: list[Any]) -> list[dict[str, Any]]:
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


def reservation_primitives(rows: list[Any]) -> list[dict[str, Any]]:
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


def exit_primitives(rows: list[Any]) -> list[dict[str, Any]]:
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


async def read_material(factory: Any, account_id: str) -> dict[str, Any]:
    from sqlalchemy import select

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
        "fills": fill_primitives(list(fills)),
        "reservations": reservation_primitives(list(reservations)),
        "exits": exit_primitives(list(exits)),
        "kill": [
            {
                "engine_id": row.engine_id,
                "engaged": bool(row.engaged),
                "reason": row.reason,
            }
            for row in kill
        ],
    }


def load_readiness_cli() -> Any:
    spec = importlib.util.spec_from_file_location(
        "auto_chain_paper_material_readiness", READINESS_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def readiness(account_id: str, version_id: str) -> Any:
    """Ejecuta el lector REAL del CLI (conexión propia, sin mocks)."""
    module = load_readiness_cli()
    return await module._read(  # noqa: SLF001 — el lector real del CLI es el sujeto.
        account_id,
        [version_id],
        limit=2000,
        min_cycles=32,
    )


# ── Limpieza ───────────────────────────────────────────────────────────────────────


async def cleanup_world(
    *,
    account_id: str | None,
    engine_id: str,
    instrument_id: str | None,
    version_id: str | None,
    candidate_id: str | None,
    estudio_membership: list[str] | None = None,
) -> None:
    """Borra el residuo completo (el barrido autouse de conftest no cubre estas tablas)."""
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import (
        AdaptiveGateStateRow,
        AutoEngineRunRow,
        AutoEngineTickRow,
        AutoExitOrderRow,
        AutoKillStateRow,
        AutoOpsJobRow,
        DecisionJournalEntryRow,
        EstudioDailyProposalRow,
        ExecutionEventRow,
        InstrumentDailyOpinionRow,
        InstrumentRow,
        InstrumentStrategyTopRow,
        OhlcvBarRow,
        PortfolioReservationRow,
        SimAutoPositionRow,
        SimConsumedSignalRow,
        SimFillFinanceContextRow,
        StrategyCandidateRow,
        StrategyPromotionRow,
        StrategyVersionRow,
    )

    engine, factory = await open_session_factory()
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
                    delete(AutoExitOrderRow).where(
                        AutoExitOrderRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(SimAutoPositionRow).where(
                        SimAutoPositionRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(SimConsumedSignalRow).where(
                        SimConsumedSignalRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(ExecutionEventRow).where(
                        ExecutionEventRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(DecisionJournalEntryRow).where(
                        DecisionJournalEntryRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(EstudioDailyProposalRow).where(
                        EstudioDailyProposalRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(AutoOpsJobRow).where(AutoOpsJobRow.account_id == account_id)
                )
                await session.execute(
                    delete(AutoKillStateRow).where(
                        AutoKillStateRow.account_id == account_id
                    )
                )
                await session.execute(
                    delete(AdaptiveGateStateRow).where(
                        AdaptiveGateStateRow.account_id == account_id
                    )
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
                    delete(StrategyCandidateRow).where(
                        StrategyCandidateRow.id == candidate_id
                    )
                )
            if instrument_id:
                await session.execute(
                    delete(InstrumentDailyOpinionRow).where(
                        InstrumentDailyOpinionRow.instrument_id == instrument_id
                    )
                )
                await session.execute(
                    delete(InstrumentStrategyTopRow).where(
                        InstrumentStrategyTopRow.instrument_id == instrument_id
                    )
                )
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
        if estudio_membership is not None:
            await restore_estudio_list(factory, estudio_membership)
    finally:
        await engine.dispose()
