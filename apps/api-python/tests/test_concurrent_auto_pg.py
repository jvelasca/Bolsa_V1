"""V2.46 / AUTO-6 — Concurrent AUTO (capa REAL: PostgreSQL, sesiones concurrentes).

Es la capa del TAG del escenario ``Concurrent AUTO`` (el núcleo hermético por commit vive
en ``apps/api-python/tests/test_auto_v46_concurrent.py``). El gemelo real es ESTRECHO a
propósito: no inventa un segundo producto, ejercita la MISMA costura de producción
—``AutoSimRuntime.run_tick`` con los stores ``Postgres*``— desde **tres sesiones
concurrentes** sobre la MISMA cuenta/engine/instrumento/barra/señales.

Qué se conduce igual que el proceso real: el tick va por ``real_turn`` (composición real
de stores/fuentes por sesión, ingestión de la señal del spine, RiskGate, reserva durable,
emisión, settlement). Qué NO se replica: no se arrancan tres procesos ``scheduler_worker``
(eso es el crash test); aquí se usan tres sesiones ``AsyncSession`` concurrentes, que es
donde vive la carrera: cada ``await`` de ida y vuelta a PostgreSQL es un punto de
interleaving real.

Invariante que se certifica (1 señal ⇒ 1 decisión ⇒ 1 orden):

* **un solo INTENT de orden** entre las tres instancias (``Σ _order_seq == 1``); medir el
  intent, y no ``count(distinct venue_order_id)``, es deliberado: la identidad de orden del
  venue es determinista por ``(engine, minuto, lado, símbolo, seq)``, así que una emisión
  duplicada tendría el MISMO ``venue_order_id``/``execution_id`` y sería financieramente
  idempotente — invisible a un ``count``. El intent sí lo ve;
* **una sola fila** de reserva durable por ``(cuenta, instrumento)`` (claim atómico por
  ``reservation_id`` determinista ``RES-dec-<hash>`` derivado de ``(cuenta, señal)``);
* ``Σ reserved_cash`` viva == la cola NO llenada (jamás × nº de workers);
* contabilidad cerrada: ``released_qty == Σ APPLIED`` y ``remaining_qty == pedido − Σ``;
* toda instancia que NO abrió declara POR QUÉ (ni un veto silencioso).

Gate: ``AUTO_CONCURRENT_PG_REQUIRED=1`` ⇒ un skip mudo es FALLO duro.

Mismo límite de MÉTODO que el resto de suites PG: no correr en paralelo con otra sesión de
pytest contra la misma base (el barrido de residuos del conftest es de sesión).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from tests.test_golden_day_v2_process_pg import (  # noqa: E402
    _env_for,
    _seed_account,
    _seed_edge_report,
    _seed_instrument,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REQUIRED_ENV = "AUTO_CONCURRENT_PG_REQUIRED"

_SYMBOL = "CNC46"
_SECTOR = "Technology"
_INSTRUMENT_PREFIX = "inst-v46conc-"
_SESSIONS = 3
_FILL_CHUNKS = 4
_MIN_BUY_CHUNKS = 2
#: La entrada real del proceso ocurre en el primer tick (minuto 1); se exige además el
#: minuto 2 para tolerar un arranque que tarde un tick en aprobar.
_ENTRY_WINDOW = (1, 2)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para Concurrent AUTO pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (Concurrent AUTO) no disponible: {exc}")


@pytest_asyncio.fixture
async def concurrent_pg_factory() -> Any:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env", override=False)
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


def _partial_buy_instrument_id(prefix: str) -> str:
    """Id determinista cuyo BUY LLENA PARCIAL (≥2 tranchas) en la ventana de entrada.

    Barrida pura (sin BD, sin proceso): mismo id en cada ejecución. El reparto de tranchas
    depende SOLO del contexto de mercado (seed/side/instrument), nunca de la cantidad ni de
    la identidad del order (V2.24/A9.1), así que la barrida vale para la cantidad real que
    decida el sizing del pipeline. El fill PARCIAL es lo que deja la reserva VIVA: sin cola
    viva no habría compromiso que medir y el test pasaría por vacío.
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    for n in range(8192):
        candidate = f"{prefix}{n:010d}"
        results = [
            simulated_fill_schedule(
                instrument_id=candidate,
                side="buy",
                quantity=Decimal("100"),
                venue_order_id=f"probe-{candidate}-{minute}",
                seed=minute * 100_003 + sum(map(ord, candidate)) % 9999,
                fill_chunks=_FILL_CHUNKS,
                base_mid=100.0,
            )
            for minute in _ENTRY_WINDOW
        ]
        if all(
            r.status == "partial" and len(r.fills) >= _MIN_BUY_CHUNKS for r in results
        ):
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} tiene BUY PARCIAL (≥{_MIN_BUY_CHUNKS} "
        f"tranchas) en {_ENTRY_WINDOW}; revisar ``draw_queue_noise``"
    )


class _BuyOnce:
    """Spine determinista: BUY para el instrumento vigilado, HOLD para lo demás."""

    def __init__(self, symbol: str, lot: float = 100.0) -> None:
        self._symbol = symbol
        self._lot = lot

    def __call__(self, symbol: str) -> Any:
        from bolsa_application.decision_contract import DecisionPackage

        if symbol != self._symbol:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        return DecisionPackage(action="BUY", instrument_id=self._symbol, quantity=self._lot)


def _apply_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)


async def _make_runtime(factory: Any, *, engine_id: str, account_id: str, symbol: str) -> Any:
    """Una instancia MÁS del motor: worker propio + runtime real sobre la MISMA base."""
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
    )

    worker = AutoSimulationWorker(
        decider=_BuyOnce(symbol),
        engine_id=engine_id,
        account_id=account_id,
    )
    return AutoSimRuntime(factory, worker=worker, engine_id=engine_id, account_id=account_id)


async def _reservations(factory: Any, account_id: str) -> list[Any]:
    from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

    async with factory() as session:
        return list(
            (
                await session.execute(
                    select(PortfolioReservationRow).where(
                        PortfolioReservationRow.account_id == account_id
                    )
                )
            )
            .scalars()
            .all()
        )


async def _execution_rows(factory: Any, account_id: str) -> list[Any]:
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    async with factory() as session:
        return list(
            (
                await session.execute(
                    select(ExecutionEventRow).where(ExecutionEventRow.account_id == account_id)
                )
            )
            .scalars()
            .all()
        )


async def _applied_buy_qty(factory: Any, account_id: str) -> Decimal:
    """``Σ`` cantidades BUY en ``APPLIED`` (la autoridad financiera de lo materializado)."""
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        rows = (
            await session.execute(
                select(SimFillFinanceContextRow.instrument_id, SimFillFinanceContextRow.quantity)
                .join(
                    ExecutionEventRow,
                    ExecutionEventRow.execution_id == SimFillFinanceContextRow.execution_id,
                )
                .where(
                    ExecutionEventRow.account_id == account_id,
                    ExecutionEventRow.status == "APPLIED",
                    func.lower(SimFillFinanceContextRow.side) == "buy",
                )
            )
        ).all()
    total = Decimal("0")
    for _instrument_id, quantity in rows:
        total += Decimal(str(quantity))
    return total


@pytest.mark.asyncio
async def test_concurrent_auto_three_sessions_claim_one_signal_pg(
    concurrent_pg_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tres sesiones concurrentes sobre la misma cuenta: 1 señal ⇒ 1 intent ⇒ 1 reserva."""
    instrument_id = _partial_buy_instrument_id(_INSTRUMENT_PREFIX)
    engine_id = f"auto-cn46-{uuid.uuid4().hex[:8]}"
    account_id: str | None = None
    edge_report_id: str | None = None

    try:
        account_id = await _seed_account(concurrent_pg_factory)
        await _seed_instrument(
            concurrent_pg_factory,
            instrument_id=instrument_id,
            symbol=_SYMBOL,
            sector=_SECTOR,
        )
        edge_report_id = await _seed_edge_report(
            concurrent_pg_factory, account_id=account_id, strategy_ref="unversioned"
        )
        _apply_env(
            monkeypatch,
            _env_for(account_id, engine_id, instrument_ids=[instrument_id]),
        )

        # ── OLEADA 1 · tres sesiones concurrentes sobre la MISMA señal ─────────────
        wave = [
            await _make_runtime(
                concurrent_pg_factory,
                engine_id=engine_id,
                account_id=account_id,
                symbol=instrument_id,
            )
            for _ in range(_SESSIONS)
        ]
        await asyncio.gather(*(runtime.run_tick() for runtime in wave))

        workers = [runtime.worker for runtime in wave]

        # (1) 1 señal ⇒ 1 INTENT de orden entre las tres instancias.
        intents = sum(int(worker._order_seq) for worker in workers)  # noqa: SLF001
        assert intents == 1, (
            f"la misma señal produjo {intents} intents de orden entre {_SESSIONS} "
            "instancias concurrentes (debe ser exactamente 1)"
        )

        # (2) Exactamente UNA instancia abre la posición; el resto no.
        opened = [
            worker for worker in workers if worker._open.get(instrument_id, Decimal("0")) > 0
        ]
        assert len(opened) == 1, (
            "exactamente una instancia debe abrir; abrieron "
            f"{len(opened)}: {[str(w._open.get(instrument_id)) for w in workers]}"
        )
        held = opened[0]._open[instrument_id]
        assert held > 0

        # (3) Los perdedores declaran POR QUÉ (claim perdido o señal ya consumida),
        #     nunca un veto silencioso.
        from bolsa_application.auto_reason_codes import RESERVATION_ALREADY_LIVE

        losers = [worker for worker in workers if worker is not opened[0]]
        allowed = {RESERVATION_ALREADY_LIVE, "hold_no_op", "signal_already_consumed"}
        for loser in losers:
            raw = loser._last_gate_reason  # noqa: SLF001
            codes = {str(code) for code in raw} if isinstance(raw, (tuple, list, set)) else {
                str(raw or "")
            }
            codes.discard("")
            assert codes, "una instancia perdedora no puede vetar sin declarar el motivo"
            assert codes <= allowed, (
                f"motivo de veto inesperado en una carrera perdida: {sorted(codes)}"
            )

        # (4) Una SOLA fila de reserva durable por (cuenta, instrumento): claim atómico.
        rows = await _reservations(concurrent_pg_factory, account_id)
        assert len(rows) == 1, (
            "la reserva durable debe ser única por (cuenta, instrumento); hay "
            f"{len(rows)} filas: {[r.reservation_id for r in rows]}"
        )
        reservation = rows[0]
        requested = Decimal(str(reservation.quantity))
        released = Decimal(str(reservation.released_qty or 0))
        remaining = Decimal(str(reservation.remaining_qty or 0))

        # (5) Contabilidad cerrada: pedido = liberado por fill + cola viva.
        assert released == held, (
            "lo liberado por fill debe ser exactamente lo materializado: "
            f"released={released} materializado={held}"
        )
        assert remaining == requested - held, (
            f"cola viva {remaining} != pedido {requested} − materializado {held}"
        )
        assert remaining > 0, (
            "el escenario exige fill PARCIAL (cola viva); el id debe producir un parcial"
        )
        applied = await _applied_buy_qty(concurrent_pg_factory, account_id)
        assert applied == released, (
            f"Σ APPLIED BUY ({applied}) != reserva liberada ({released})"
        )

        # (6) Sin sobre-riesgo: lo comprometido vivo es la cola de UNA reserva, no ×3.
        live = [
            row
            for row in rows
            if str(row.status).upper() == "OPEN" and float(row.remaining_qty or 0) > 0
        ]
        assert len(live) <= 1, f"doble compromiso vivo: {[r.reservation_id for r in live]}"
        committed = sum(float(row.reserved_cash or 0) for row in live)
        ceiling = float(reservation.reserved_cash or 0)
        assert committed <= ceiling + 1e-6, (
            f"sobre-riesgo: comprometido {committed} > tope de una reserva {ceiling}"
        )

        # ── OLEADA 2 · tres instancias NUEVAS (RAM vacía) sobre la MISMA base ──────
        events_before = len(await _execution_rows(concurrent_pg_factory, account_id))
        second = [
            await _make_runtime(
                concurrent_pg_factory,
                engine_id=engine_id,
                account_id=account_id,
                symbol=instrument_id,
            )
            for _ in range(_SESSIONS)
        ]
        await asyncio.gather(*(runtime.run_tick() for runtime in second))

        assert sum(int(rt.worker._order_seq) for rt in second) == 0, (  # noqa: SLF001
            "la segunda oleada no puede emitir ni una orden (señal consumida + claim vivo)"
        )
        # La instancia nueva RE-ADOPTA la posición durable (misma cantidad); no la re-abre.
        for rt in second:
            readopted = rt.worker._open.get(instrument_id, Decimal("0"))  # noqa: SLF001
            assert readopted in (Decimal("0"), held), (
                "una instancia nueva no puede abrir una posición distinta: "
                f"{readopted} (materializado {held})"
            )
        assert len(await _reservations(concurrent_pg_factory, account_id)) == 1, (
            "la segunda oleada no puede añadir filas de reserva"
        )
        assert len(await _execution_rows(concurrent_pg_factory, account_id)) == events_before, (
            "la segunda oleada no puede añadir ni una traza de ejecución"
        )
    finally:
        if account_id is not None:
            from sqlalchemy import delete

            from bolsa_infrastructure.database.models.tables import (
                EdgeReportRow,
                ExecutionEventRow,
                PortfolioReservationRow,
                SimAutoPositionRow,
                SimConsumedSignalRow,
                SimFillFinanceContextRow,
            )

            async with concurrent_pg_factory() as session:
                for model in (
                    SimAutoPositionRow,
                    SimConsumedSignalRow,
                    SimFillFinanceContextRow,
                    ExecutionEventRow,
                    PortfolioReservationRow,
                ):
                    await session.execute(
                        delete(model).where(model.account_id == account_id)  # type: ignore[attr-defined]
                    )
                if edge_report_id is not None:
                    await session.execute(
                        delete(EdgeReportRow).where(EdgeReportRow.id == edge_report_id)
                    )
                await session.commit()
