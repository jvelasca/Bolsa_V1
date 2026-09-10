"""V2.24 / A9.1 — durabilidad e integridad del AUTO SIM (hermético, sin PG).

Cubre los P1 del audit V2.23 y los P2 de endurecimiento:

* P1-02 — ``sim_auto_positions`` aislada por CUENTA (dos cuentas, mismo engine/
  símbolo ⇒ cada una lee la suya).
* P1-03 — ``execution_id`` con namespace único (dos cuentas ⇒ identidades distintas).
* P1-04 — ``account_id=None`` ⇒ AUTO BLOQUEADO (0 órdenes, veto observable).
* P2-01 — estado de protección durable (entry/high) sobrevive crash/restart.
* P2-02 — reconciliación ``ExecutionEvents`` ↔ canónico ↔ proyección.
* P2-06 — trailing etiquetado antes que T1; T1 parcial; edad por símbolo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    ProtectionConfig,
    step_minute_clock,
)
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    POSITION_PROJECTION_OK,
    POSITION_PROJECTION_REBUILT,
    POSITION_PROJECTION_UNKNOWN,
    reconcile_sim_account,
    reconcile_sim_position,
)
from bolsa_application.simulated_settlement import auto_venue_order_id


@pytest.fixture
def auto_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")


def _buy(symbol: str, qty: float = 100.0) -> DecisionPackage:
    return DecisionPackage(action="BUY", instrument_id=symbol, quantity=qty)


def _hold(symbol: str) -> DecisionPackage:
    return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)


# ── P1-03: identidad de execution_id namespaceada ───────────────────────────────


def test_execution_identity_namespaced_by_account() -> None:
    """Dos cuentas, mismo engine/símbolo/minuto ⇒ venue_order_id DISTINTOS."""
    a = auto_venue_order_id(
        engine_id="auto-sim",
        account_id="acc-A",
        instrument_id="AAA",
        side="buy",
        logical_order_id="m1-buy-AAA-1",
    )
    b = auto_venue_order_id(
        engine_id="auto-sim",
        account_id="acc-B",
        instrument_id="AAA",
        side="buy",
        logical_order_id="m1-buy-AAA-1",
    )
    assert a != b, "la identidad debe namespacear la cuenta (P1-03)"
    assert "accA" in a and "accB" in b


@pytest.mark.asyncio
async def test_two_accounts_same_symbol_distinct_execution_ids(
    auto_env: None,
) -> None:
    """Dos workers/cuentas sobre el mismo símbolo NO comparten execution_id."""
    store = InMemoryExecutionEventStore()
    seen: dict[str, set[str]] = {"A": set(), "B": set()}
    for account in ("A", "B"):
        _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
        w = AutoSimulationWorker(
            clock=clock, exec_store=store, account_id=f"acc-{account}"
        )
        w._decider = _buy
        await w.auto_turn()
        for row in w.journal_pairs():
            if row.kind == "fill":
                seen[account].add(row.execution_id)
    assert seen["A"] and seen["B"]
    assert not (seen["A"] & seen["B"]), "cuentas distintas ⇒ sin colisión de identidad"


# ── P1-02: aislamiento de la proyección por cuenta ──────────────────────────────


@pytest.mark.asyncio
async def test_position_store_isolated_by_account() -> None:
    """Mismo engine/símbolo en dos cuentas ⇒ cada una lee solo la suya (P1-02)."""
    store = InMemorySimAutoPositionStore()
    await store.upsert("acc-A", "auto-sim", "AAA", Decimal("100"))
    await store.upsert("acc-B", "auto-sim", "AAA", Decimal("200"))
    assert dict(await store.read_open("acc-A", "auto-sim")) == {"AAA": Decimal("100")}
    assert dict(await store.read_open("acc-B", "auto-sim")) == {"AAA": Decimal("200")}


# ── P1-04: account_id None ⇒ AUTO bloqueado ─────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_blocked_without_account_id(auto_env: None) -> None:
    """AUTO durable sin cuenta inequívoca NO opera (P1-04, fail-closed)."""
    store = InMemoryExecutionEventStore()
    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
        account_id=None,
        require_account_id=True,
    )
    worker._decider = _buy
    report = await worker.auto_turn()
    assert report.orders == 0 and report.fills == 0
    assert not worker.open_symbols
    assert "account_id_required" in worker._last_gate_reason


# ── P2-01: estado de protección durable tras crash ──────────────────────────────


@pytest.mark.asyncio
async def test_protection_state_survives_restart(auto_env: None) -> None:
    """entry/high durables: un worker readoptado conserva el máximo (P2-01)."""
    store = InMemoryExecutionEventStore()
    pos_store = InMemorySimAutoPositionStore()
    account = "acc-prot"

    _s1, clock1 = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1, exec_store=store, position_store=pos_store, account_id=account
    )
    w1._decider = _buy
    await w1.auto_turn()
    await w1._persist_position("AAA", w1._open["AAA"])
    # Simula un máximo alcanzado (high = 110) persistido en la proyección.
    await pos_store.upsert(
        account,
        "auto-sim",
        "AAA",
        w1._open["AAA"],
        entry_price=Decimal("100"),
        high_watermark=Decimal("110"),
    )

    _s2, clock2 = step_minute_clock(datetime(2026, 9, 9, 9, 5, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2, exec_store=store, position_store=pos_store, account_id=account
    )
    await w2.readopt_positions()
    assert w2._open.get("AAA", Decimal("0")) > 0
    assert w2._entry_price.get("AAA") == Decimal("100")
    assert w2._high_price.get("AAA") == Decimal("110")


# ── V2.24.2 (P2-D): restart con posición y PROTECCIÓN abierta ────────────────────


@pytest.mark.asyncio
async def test_restart_with_open_position_trailing_uses_persisted_watermark(
    auto_env: None,
) -> None:
    """Tras reiniciar con posición abierta, el trailing usa el máximo PERSISTIDO.

    No basta con que el lifecycle de ejecución se readopte (A9.1): aquí la posición
    queda abierta y con protección activa, se reinicia el worker, y el nuevo worker
    debe (1) NO re-comprar y (2) forzar un ``trailing_stop`` —no un falso ``t1_exit``—
    con el ``high_watermark`` restaurado. Sin la protección durable el worker olvidaría
    el máximo y el retroceso se etiquetaría mal.
    """
    store = InMemoryExecutionEventStore()
    pos_store = InMemorySimAutoPositionStore()
    account = "acc-restart-prot"
    protection = ProtectionConfig(
        stop_pct=0.05, t1_pct=0.02, trailing_pct=0.015, enabled=True, t1_fraction=1.0
    )

    # Worker 1: abre posición @100 y persiste el estado de protección (max 110).
    _s1, clock1 = step_minute_clock(datetime(2026, 9, 10, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1,
        exec_store=store,
        position_store=pos_store,
        account_id=account,
    )
    w1._decider = _buy
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) > 0
    await pos_store.upsert(
        account,
        "auto-sim",
        "AAA",
        w1._open["AAA"],
        entry_price=Decimal("100"),
        high_watermark=Decimal("110"),  # el máximo ya superó T1 (102)
        stop_price=Decimal("95"),
    )

    # Worker 2 (reinicio): readopta posición Y protección desde el espejo durable.
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 10, 9, 30, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2,
        exec_store=store,
        position_store=pos_store,
        account_id=account,
    )
    w2._decider = _buy  # sigue proponiendo BUY: NO debe apilar
    await w2.readopt_positions()
    assert w2._open.get("AAA", Decimal("0")) > 0, "readopta posición"
    assert w2._high_price.get("AAA") == Decimal("110"), "readopta el máximo (P2-01)"

    # No doble BUY: un turno con el decider proponiendo BUY sobre posición readoptada
    # no abre una segunda vez (G7) y NO duplica efecto financiero.
    turn = await w2.auto_turn()
    assert turn.opened == 0, "NO segundo BUY tras readopción con posición abierta"
    assert w2._open.get("AAA", Decimal("0")) > 0

    # Precio 108: retrocede desde 110 (trailing 1.5% ⇒ umbral 108.35) pero sigue
    # por encima de T1 (102); el motivo correcto es trailing, no t1_exit.
    reason = protection.exit_reason(
        held=True,
        entry=Decimal("100"),
        high=w2._high_price["AAA"],
        price=Decimal("108.2"),
        minute=w2.minute,
    )
    assert reason == "trailing_stop", reason
    # El umbral de trailing depende del high_watermark PERSISTIDO (110×0.985=108.35):
    # un precio por encima de ese umbral (108.6) NO es trailing, aunque esté por
    # debajo del máximo. Sin el máximo durable, este límite no existiría.
    assert (
        protection.exit_reason(
            held=True,
            entry=Decimal("100"),
            high=w2._high_price["AAA"],
            price=Decimal("108.6"),
            minute=w2.minute,
        )
        in {None, "t1_exit"}  # 108.6 > 108.35 ⇒ no es trailing
    )


# ── P2-02: reconciliación ───────────────────────────────────────────────────────


class _Ev:
    def __init__(self, symbol: str, side: str, qty: str, venue: str = "SIMULATED") -> None:
        self.instrument_id = symbol
        self.side = side
        self.qty = Decimal(qty)
        self.venue = venue


def test_reconcile_ok() -> None:
    verdict = reconcile_sim_position(
        symbol="AAA",
        execution_events=[_Ev("AAA", "buy", "100")],
        financial_positions={"AAA": Decimal("100")},
        sim_auto_positions={"AAA": Decimal("100")},
    )
    assert verdict.status == POSITION_PROJECTION_OK
    assert verdict.allows_new_openings


def test_reconcile_divergent_blocks_openings() -> None:
    verdict = reconcile_sim_position(
        symbol="AAA",
        execution_events=[_Ev("AAA", "buy", "100")],
        financial_positions={"AAA": Decimal("200")},
        sim_auto_positions={"AAA": Decimal("100")},
    )
    assert verdict.status == POSITION_PROJECTION_DIVERGENT
    assert not verdict.allows_new_openings


def test_reconcile_rebuilds_stale_projection() -> None:
    verdict = reconcile_sim_position(
        symbol="AAA",
        execution_events=[_Ev("AAA", "buy", "100")],
        financial_positions={"AAA": Decimal("100")},
        sim_auto_positions={"AAA": Decimal("40")},
    )
    assert verdict.status == POSITION_PROJECTION_REBUILT
    assert verdict.rebuilt and verdict.allows_new_openings


def test_reconcile_unknown_without_canonical() -> None:
    verdict = reconcile_sim_position(
        symbol="AAA",
        execution_events=[_Ev("AAA", "buy", "100")],
        financial_positions=None,
        sim_auto_positions={"AAA": Decimal("100")},
    )
    assert verdict.status == POSITION_PROJECTION_UNKNOWN
    assert not verdict.allows_new_openings


# ── V2.24.2 (P2-C): reconciliación GLOBAL de la cuenta ──────────────────────────


def test_account_reconciliation_ok_when_all_symbols_match() -> None:
    report = reconcile_sim_account(
        account_id="acc-1",
        engine_id="eng-1",
        symbols=("AAA", "BBB"),
        execution_events=[_Ev("AAA", "buy", "100"), _Ev("BBB", "buy", "50")],
        financial_positions={"AAA": Decimal("100"), "BBB": Decimal("50")},
        sim_auto_positions={"AAA": Decimal("100"), "BBB": Decimal("50")},
    )
    assert report.status == POSITION_PROJECTION_OK
    assert report.ok and not report.blocks_openings
    assert set(report.symbols) == {"AAA", "BBB"}


def test_account_reconciliation_blocks_on_any_divergent() -> None:
    """Un solo símbolo divergente bloquea aperturas en TODA la cuenta (fail-closed)."""
    report = reconcile_sim_account(
        account_id="acc-1",
        engine_id="eng-1",
        symbols=("AAA", "BBB"),
        execution_events=[_Ev("AAA", "buy", "100"), _Ev("BBB", "buy", "50")],
        financial_positions={"AAA": Decimal("100"), "BBB": Decimal("999")},
        sim_auto_positions={"AAA": Decimal("100"), "BBB": Decimal("50")},
    )
    assert report.status == POSITION_PROJECTION_DIVERGENT
    assert report.blocks_openings
    assert [v.symbol for v in report.divergent] == ["BBB"]


def test_account_reconciliation_detects_phantom_projection() -> None:
    """Una posición SOLO en la proyección (fantasma) no queda invisible."""
    report = reconcile_sim_account(
        account_id="acc-1",
        engine_id="eng-1",
        symbols=("AAA",),
        execution_events=[_Ev("AAA", "buy", "100")],
        financial_positions={"AAA": Decimal("100")},
        sim_auto_positions={"AAA": Decimal("100"), "GHOST": Decimal("7")},
    )
    assert "GHOST" in report.symbols
    # GHOST no está en el canónico ⇒ su veredicto es UNKNOWN (fail-closed).
    ghost = next(v for v in report.verdicts if v.symbol == "GHOST")
    assert ghost.status == POSITION_PROJECTION_UNKNOWN
    assert report.blocks_openings


def test_account_reconciliation_blocks_on_unknown_canonical() -> None:
    """Sin canónico (None), ningún símbolo es OK: la cuenta queda bloqueada."""
    report = reconcile_sim_account(
        account_id="acc-1",
        engine_id="eng-1",
        symbols=("AAA",),
        execution_events=[_Ev("AAA", "buy", "100")],
        financial_positions=None,
        sim_auto_positions={"AAA": Decimal("100")},
    )
    assert report.status == POSITION_PROJECTION_UNKNOWN
    assert report.blocks_openings


# ── P2-06: trailing vs T1, edad por símbolo, T1 parcial ─────────────────────────


def test_exit_reason_trailing_wins_over_t1() -> None:
    """Un retroceso desde un máximo > T1 se etiqueta ``trailing_stop``, no ``t1_exit``."""
    cfg = ProtectionConfig(
        stop_pct=0.02, t1_pct=0.02, trailing_pct=0.015, enabled=True
    )
    # Entrada 100, máximo 110 (+10%), precio actual 105 (+5%: por encima de T1).
    reason = cfg.exit_reason(
        held=True,
        entry=Decimal("100"),
        high=Decimal("110"),
        price=Decimal("105"),
        minute=1,
    )
    assert reason == "trailing_stop"


def test_exit_reason_t1_when_no_retracement() -> None:
    cfg = ProtectionConfig(stop_pct=0.0, t1_pct=0.02, trailing_pct=0.015, enabled=True)
    reason = cfg.exit_reason(
        held=True,
        entry=Decimal("100"),
        high=Decimal("103"),
        price=Decimal("102.5"),
        minute=1,
    )
    assert reason == "t1_exit"


def test_t1_partial_fraction() -> None:
    cfg = ProtectionConfig(t1_pct=0.02, t1_fraction=0.3, enabled=True)
    assert cfg.exit_fraction("t1_exit") == 0.3
    assert cfg.exit_fraction("protective_stop") == 1.0


def test_auto_decision_engine_age_is_per_symbol() -> None:
    """``exit_after_ticks`` no debe depender del número de símbolos del watch (P2-06)."""
    from bolsa_application.auto_decision_engine import AutoDecisionEngine

    engine = AutoDecisionEngine(
        watch=("AAA", "BBB"), exit_after_ticks=3, lot_qty=10, enabled=True
    )
    # Tick real 1: ambos símbolos BUY.
    assert engine("AAA").action == "BUY"
    assert engine("BBB").action == "BUY"
    # Ticks reales 2 y 3: HOLD para ambos (retención completa, no cerrada antes).
    assert engine("AAA").action == "HOLD"
    assert engine("BBB").action == "HOLD"
    assert engine("AAA").action == "HOLD"
    assert engine("BBB").action == "HOLD"
    # Tick real 4: cierre de AMBOS (sin que un símbolo acelere al otro).
    assert engine("AAA").action == "SELL"
    assert engine("BBB").action == "SELL"


@pytest.mark.asyncio
async def test_t1_partial_leaves_residual_position(auto_env: None, monkeypatch) -> None:
    """T1 parcial vende la fracción y mantiene el resto (P2-06)."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_PROTECTION", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_STOP_PCT", "0.0")
    monkeypatch.setenv("AUTO_ENGINE_SIM_T1_PCT", "0.02")
    monkeypatch.setenv("AUTO_ENGINE_SIM_TRAILING_PCT", "0.0")
    monkeypatch.setenv("AUTO_ENGINE_SIM_T1_FRACTION", "0.3")

    store = InMemoryExecutionEventStore()
    prices = {"v": 100.0}

    def script(symbol: str, _minute: int) -> float:
        return prices["v"]

    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
        price_script=script,
    )
    worker._decider = _buy
    await worker.auto_turn()
    assert worker._open["AAA"] == Decimal("100.000000")

    # Sube a 110 (+10% ⇒ T1): vende 30% y deja 70.
    prices["v"] = 110.0
    worker._decider = _hold
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == Decimal("70.000000")
