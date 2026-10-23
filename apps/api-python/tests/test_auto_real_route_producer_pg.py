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
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from bolsa_application.paper_material_readiness import (
    BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES,
    READINESS_PRODUCER_READY,
)
from tests.support import auto_chain_e2e as chain

_REQUIRED_ENV = "AUTO_REAL_ROUTE_PRODUCER_PG_REQUIRED"

#: Reloj PINNED del harness: barra D1 ``B`` = día de este instante (UTC).
_CLOCK_DAY = chain.CLOCK_DAY
_DAY_B_OPEN = chain.DAY_B_OPEN
_DAY_B_CLOSE = chain.DAY_B_CLOSE
_DAY_B1_OPEN = chain.DAY_B1_OPEN
_DAY_B1_CLOSE = chain.DAY_B1_CLOSE
_LOT = chain.LOT
_ENTRY_TICKS = chain.ENTRY_TICKS
_EXIT_TICKS = chain.EXIT_TICKS

# El mundo sembrado vive UNA vez en ``tests/support/auto_chain_e2e.py``.
_open_session_factory = chain.open_session_factory
_closed_bar_rows = chain.closed_bar_rows
_current_bar_row = chain.current_bar_row
_seed_bars = chain.seed_bars
_seed_account = chain.seed_account
_seed_instrument = chain.seed_instrument
_seed_edge_report = chain.seed_edge_report
_seed_active_strategy = chain.seed_active_strategy
_bar_tick_for_day = chain.bar_tick_for_day
_route_clock = chain.route_clock
_filling_instrument_id = chain.filling_instrument_id
_configure_real_route_env = chain.configure_real_route_env
_read_material = chain.read_material
_readiness = chain.readiness
_cleanup = chain.cleanup_world


@pytest.fixture
def real_route_pg() -> None:
    """Gate honesto: sin PostgreSQL real se salta (o falla duro con el env de gobierno)."""
    chain.gate_pg(_REQUIRED_ENV)


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
