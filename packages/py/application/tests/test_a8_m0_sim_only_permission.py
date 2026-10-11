"""A8 · M0 · §7 — permiso positivo SIM-only en el punto de movimiento de dinero.

La barrera AUTO→REAL no descansa solo en (a) una allowlist de venues y (b) dos env
vars LIVE. El applier que mueve dinero exige una **capacidad afirmativa** del llamante:
``require_sim_only_scope()`` acuña un ``SimOnlyScope`` sellado que
``build_simulated_execute_trade_applier`` NO acepta si falta o si está forjado. Así el
movimiento de dinero declara explícitamente su vía (SIM), en vez de depender de que
alguien recuerde apagar/omitir una capacidad LIVE.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from bolsa_application.simulated_finance import (
    SIM_FINANCE_VENUES,
    SimOnlyScope,
    SimulatedFillFinance,
    build_simulated_execute_trade_applier,
    require_sim_only_scope,
)
from bolsa_application.simulated_settlement import simulated_idempotency_key

_REPO = Path(__file__).resolve().parents[4]
_WORKER = (
    _REPO / "apps" / "api-python" / "src" / "bolsa_api" / "background" / "auto_simulation_worker.py"
)


class _SpyTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        tx = type("Tx", (), {"id": "tx-sim-only"})()
        return type("Result", (), {"transaction": tx})()


def _event(execution_id: str, venue: str) -> SimpleNamespace:
    return SimpleNamespace(execution_id=execution_id, venue=venue, account_id="acc-1")


def _finance(execution_id: str, venue: str) -> SimulatedFillFinance:
    return SimulatedFillFinance(
        instrument_id="AAA",
        side="buy",
        execution_id=execution_id,
        quantity=Decimal("2"),
        price=Decimal("10"),
        account_id="acc-1",
        venue=venue,
    )


# ── La capacidad: sellada, trazable, no forjable ─────────────────────────────────
def test_scope_allows_only_auto_sim_venues() -> None:
    scope = require_sim_only_scope(source="test_sim_only_permission")
    assert scope.source == "test_sim_only_permission"
    for venue in SIM_FINANCE_VENUES:
        assert scope.allows(venue)
        assert scope.allows(venue.upper())
    for venue in ("live", "xtb", "real", "broker_live", ""):
        assert not scope.allows(venue)


def test_scope_requires_a_declared_source() -> None:
    with pytest.raises(ValueError):
        require_sim_only_scope(source="")
    with pytest.raises(ValueError):
        require_sim_only_scope(source="   ")


def test_scope_cannot_be_constructed_directly() -> None:
    """El constructor está sellado: sin la clave privada del módulo, no hay permiso."""
    with pytest.raises(TypeError):
        SimOnlyScope(_key=object(), source="forged")


def test_applier_requires_the_positive_scope() -> None:
    trade = _SpyTrade()
    with pytest.raises(TypeError):
        build_simulated_execute_trade_applier(trade, lambda _e: None)  # type: ignore[call-arg]


def test_applier_rejects_a_forged_scope() -> None:
    class _Forged:
        _key = object()

        def allows(self, venue: str) -> bool:  # noqa: ARG002
            return True

    with pytest.raises(TypeError):
        build_simulated_execute_trade_applier(  # type: ignore[arg-type]
            _SpyTrade(), lambda _e: None, scope=_Forged()
        )


# ── Comportamiento del applier con permiso válido ────────────────────────────────
@pytest.mark.asyncio
async def test_applier_moves_money_only_for_sim_venue() -> None:
    trade = _SpyTrade()
    scope = require_sim_only_scope(source="test_sim_only_permission")
    finances = {"ex-sim": _finance("ex-sim", "simulated"), "ex-live": _finance("ex-live", "live")}
    applier = build_simulated_execute_trade_applier(
        trade, lambda ev: finances.get(ev.execution_id), scope=scope
    )

    assert await applier(_event("ex-sim", "SIMULATED")) is True
    assert await applier(_event("ex-live", "LIVE")) is False
    assert len(trade.calls) == 1
    assert trade.calls[0]["idempotency_key"] == simulated_idempotency_key("ex-sim")
    assert trade.calls[0]["instrument_id"] == "AAA"


# ── El worker AUTO presenta el permiso en su único punto de dinero ────────────────
def test_auto_worker_declares_sim_only_scope_at_money_point() -> None:
    assert _WORKER.exists(), "worker AUTO no presente"
    source = _WORKER.read_text(encoding="utf-8")
    assert "require_sim_only_scope(" in source, (
        "el worker AUTO debe acuñar explícitamente su permiso SIM-only (A8·M0 §7)"
    )
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "build_simulated_execute_trade_applier"
    ]
    assert calls, "el worker AUTO debe construir el applier SIM del punto de dinero"
    for call in calls:
        assert any(kw.arg == "scope" for kw in call.keywords), (
            "todo build_simulated_execute_trade_applier debe pasar scope= (permiso positivo)"
        )
