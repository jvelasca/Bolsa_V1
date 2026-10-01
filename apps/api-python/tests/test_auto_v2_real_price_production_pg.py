"""W4 (``v2.88.17-beta``) — el camino de PRODUCCIÓN/PAPER deja de fabricar un precio (PG real).

Criterio de éxito **re-declarado** de ``W4`` (plan ``docs/engineering/plan-w4-precio-real-2026-10-01.md``
§7): el runtime real (``AutoSimRuntime``) sirve el precio del motor desde el REPOSITORIO de
barras (precio **real**) y **no** desde el ``100.0`` plano de ``flat_price_script``. El OOS
(``v2_86``/``v2_87``) ya usaba precio real; el ``100.0`` sólo corría aquí (§7.bis). Tres
afirmaciones:

1. El proveedor real, **sobre PostgreSQL**, parte la ventana ``<= B`` en las DOS fronteras
   (§3.1): ``mid`` = ``close`` de la última barra CERRADA (día ``< B``); ``execution`` =
   ``open`` de la barra CORRIENTE (día ``== B``). Ninguna vale ``100.0`` y ``close(B)``
   **nunca** se usa para decidir (no-lookahead).
2. **Fail-closed**: sin barra ``B`` no hay ``execution`` ⇒ el símbolo queda sin precio
   (``missing``) y **jamás** se cae al ``close(B-1)`` rancio (caza ``M287``).
3. El interruptor ``AUTO_ENGINE_SIM_REAL_PRICE`` **GOVIERNA** la composición del runtime:
   ON la compone; OFF deja el ``price_script`` hermético (``Δ = 0``, costura inerte).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real/credenciales hace
``pytest.skip``; con ``AUTO_V2_REAL_PRICE_PG_REQUIRED=1`` un skip es FALLO DURO. NUNCA abre
el bridge LIVE (venue simulated/paper).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
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
_REQUIRED_ENV = "AUTO_V2_REAL_PRICE_PG_REQUIRED"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para W4 (precio real) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (W4 precio real) no disponible: {exc}")


@pytest_asyncio.fixture
async def real_price_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head.
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_instrument(session: AsyncSession, instrument_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    if await session.get(InstrumentRow, instrument_id) is not None:
        return
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"W4{suffix.upper()}",
            yahoo_symbol=f"W4{suffix}",
            name="W4 precio real",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


async def _seed_bar(
    session: AsyncSession, instrument_id: str, *, day: str, open_: float, close: float
) -> None:
    """Siembra UNA barra D1 con ``open``/``close`` conocidos (día ISO ``YYYY-MM-DD``)."""
    from bolsa_infrastructure.database.models.tables import OhlcvBarRow
    from bolsa_infrastructure.ids import new_id

    ts = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    open_d = Decimal(str(open_))
    close_d = Decimal(str(close))
    session.add(
        OhlcvBarRow(
            id=new_id(),
            instrument_id=instrument_id,
            timeframe="1d",
            timestamp=ts,
            open=open_d,
            high=max(open_d, close_d) + Decimal("1"),
            low=min(open_d, close_d) - Decimal("1"),
            close=close_d,
            volume=1000,
            adj_close=close_d,
            source="yahoo",
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _cleanup_instrument(factory: async_sessionmaker[AsyncSession], instrument_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow

    async with factory() as session:
        await session.execute(
            delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id)
        )
        await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
        await session.commit()


# ── 1. Las DOS fronteras, sobre PostgreSQL real ────────────────────────────────


@pytest.mark.asyncio
async def test_real_source_splits_decision_and_execution_on_pg(
    real_price_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``mid`` = ``close(B-1)`` (decisión); ``execution`` = ``open(B)`` (ejecución). Ni 100.0.

    Con ``close(B-1) = 20`` y ``close(B) = 40`` y ``open(B) = 30``: la decisión DEBE anclar en
    ``20`` (nunca ``40``: sería lookahead) y la ejecución en ``30`` (nunca ``20``: precio
    rancio). El ``100.0`` del ``flat_price_script`` no aparece por ningún lado.
    """
    from bolsa_api.background.auto_simulation_worker import _compose_price_source

    symbol = f"w4rp-{uuid.uuid4().hex[:10]}"
    b_prev2, b_prev, b = "2026-06-10", "2026-06-11", "2026-06-12"
    try:
        async with real_price_pg_factory() as session:
            await _seed_instrument(session, symbol)
            await _seed_bar(session, symbol, day=b_prev2, open_=10.0, close=11.0)
            await _seed_bar(session, symbol, day=b_prev, open_=11.0, close=20.0)
            await _seed_bar(session, symbol, day=b, open_=30.0, close=40.0)

            source = _compose_price_source(session, watch=[symbol], as_of=lambda: b)
            await source.refresh()

            assert source.execution(symbol) == pytest.approx(30.0), "ejecución = open(B)"
            assert source.mid(symbol) == pytest.approx(20.0), "decisión = close(B-1), no close(B)"
            assert source.mid(symbol) != pytest.approx(40.0), "close(B) sería LOOKAHEAD"
            assert source.missing([symbol]) == (), "con barra B el símbolo SÍ es ejecutable"
            assert source.execution(symbol) != pytest.approx(100.0)
            assert source.mid(symbol) != pytest.approx(100.0)
    finally:
        await _cleanup_instrument(real_price_pg_factory, symbol)


# ── 2. Fail-closed: sin barra B no hay precio de ejecución (nunca B-1) ─────────


@pytest.mark.asyncio
async def test_real_source_fails_closed_without_current_bar_on_pg(
    real_price_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sin barra ``B``: ``execution`` es ``None`` (HOLD) y NO cae al ``close(B-1)`` rancio.

    Es la mutación ``M287`` cazada en vivo: el símbolo queda declarado en ``missing`` y la
    decisión (que sí tiene ``close(B-1)``) no se usa como precio de ejecución.
    """
    from bolsa_api.background.auto_simulation_worker import _compose_price_source

    symbol = f"w4rp-{uuid.uuid4().hex[:10]}"
    b_prev2, b_prev, b = "2026-06-10", "2026-06-11", "2026-06-12"
    try:
        async with real_price_pg_factory() as session:
            await _seed_instrument(session, symbol)
            await _seed_bar(session, symbol, day=b_prev2, open_=10.0, close=11.0)
            await _seed_bar(session, symbol, day=b_prev, open_=11.0, close=20.0)
            # NO se siembra la barra del día B.

            source = _compose_price_source(session, watch=[symbol], as_of=lambda: b)
            await source.refresh()

            assert source.execution(symbol) is None, "sin open(B) no hay precio de ejecución"
            assert source.missing([symbol]) == (symbol,), "la ausencia se DECLARA"
            assert source.mid(symbol) == pytest.approx(20.0), "la decisión sí ve close(B-1)"
            assert source.execution(symbol) != pytest.approx(20.0), "M287: nunca el precio rancio"
    finally:
        await _cleanup_instrument(real_price_pg_factory, symbol)


# ── 3. El interruptor GOVIERNA la composición del runtime ──────────────────────


@pytest.mark.asyncio
async def test_flag_governs_runtime_price_composition_on_pg(
    real_price_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OFF ⇒ el runtime NO compone precio real (``Δ = 0``); ON ⇒ lo compone.

    Prueba la costura de producción: el ``100.0`` sólo se retira cuando el operador lo pide
    explícitamente. Se observa con un espía sobre ``_compose_price_source`` (no depende del
    llenado del venue ni de que haya ATR).
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    from bolsa_api.background import auto_simulation_worker as w

    symbol = f"w4rp-{uuid.uuid4().hex[:10]}"
    engine_id = f"w4rp-{uuid.uuid4().hex[:10]}"
    calls = {"n": 0}
    real = w._compose_price_source

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(w, "_compose_price_source", _spy)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")

    account_id: str | None = None
    try:
        async with real_price_pg_factory() as session:
            await _seed_instrument(session, symbol)
            scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"W4-RP-{uuid.uuid4().hex[:8]}", initial_deposit=100_000.0
            )
            await session.commit()
            account_id = scope.account.id

        worker = w.AutoSimulationWorker(engine_id=engine_id, account_id=account_id)
        runtime = w.AutoSimRuntime(
            real_price_pg_factory, worker=worker, engine_id=engine_id, account_id=account_id
        )

        monkeypatch.delenv(w.AUTO_REAL_PRICE_ENV, raising=False)
        await runtime.run_tick()
        assert calls["n"] == 0, "con el flag OFF el runtime NO compone precio real (Δ = 0)"

        monkeypatch.setenv(w.AUTO_REAL_PRICE_ENV, "1")
        await runtime.run_tick()
        assert calls["n"] >= 1, "con el flag ON el runtime SÍ compone el precio real"
    finally:
        from bolsa_infrastructure.database.models.tables import (
            SimAutoPositionRow,
            SimConsumedSignalRow,
        )

        async with real_price_pg_factory() as session:
            if account_id is not None:
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
                await session.commit()
        await _cleanup_instrument(real_price_pg_factory, symbol)
