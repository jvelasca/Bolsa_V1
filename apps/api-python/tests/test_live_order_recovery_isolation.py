"""Fija por contrato el aislamiento del LiveOrderRecoveryWorker (auditoría `G4`, P3).

Hermético a propósito: **sin PostgreSQL, sin red y sin `get_settings` real**. Ejercita
las FUNCIONES REALES del worker con `monkeypatch` de entorno (no copia la lógica) y fija
la propiedad read-only «nunca re-POSTea; UNKNOWN solo sale por `query_broker`» con un
análisis AST del propio módulo + el camino real de `resolve_one_unknown` sobre dobles en
memoria.

Ancla en el código real ([`live_order_recovery_worker.py`]):
* `LIVE_RECOVERY_WORKER_ENABLED` nace **ON** (`_worker_enabled`, default `"1"`).
* `financial_apply_enabled()` (`LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED`) es
  **fail-closed OFF** por defecto y SOLO `1|true|yes|on` lo enciende.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bolsa_analytics.cognitive.live_order import LiveOrder
from bolsa_api.background import live_order_recovery_worker as recovery
from bolsa_application.live_order_query import (
    BrokerOrderQueryResult,
    MockLiveOrderQuery,
)

_WORKER_PATH = Path(recovery.__file__).resolve()
_ENV_ENABLED = recovery._ENV_ENABLED
_GO_ENV = recovery._GO_ENV


def _unknown_order(
    *, order_id: str = "ord-1", venue_order_id: str | None = "venue-1"
) -> LiveOrder:
    return LiveOrder(
        order_id=order_id,
        status="UNKNOWN",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=Decimal("10"),
        filled_quantity=Decimal("0"),
        remaining_quantity=Decimal("10"),
        venue_order_id=venue_order_id,
        intent_id=None,
        financial_apply_count=0,
        account_id="acc-1",
    )


class _RecordingStore:
    """Doble mínimo del store: registra los `put` en memoria (sin PG)."""

    def __init__(self) -> None:
        self.puts: list[tuple[Any, str]] = []

    async def put(self, order: Any, *, account_id: str) -> None:
        self.puts.append((order, account_id))


# ── LIVE_RECOVERY_WORKER_ENABLED: nace ON (default "1") ───────────────────────────
def test_worker_enabled_defaults_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_ENV_ENABLED, raising=False)
    assert recovery._worker_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "OFF", " False "])
def test_worker_enabled_explicit_off(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(_ENV_ENABLED, value)
    assert recovery._worker_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "cualquier-cosa"])
def test_worker_enabled_any_other_value_on(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(_ENV_ENABLED, value)
    assert recovery._worker_enabled() is True


# ── LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED: fail-closed OFF por defecto ──────
def test_financial_apply_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_GO_ENV, raising=False)
    assert recovery.financial_apply_enabled() is False


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "2", "enabled", "sí"])
def test_financial_apply_fail_closed(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(_GO_ENV, value)
    assert recovery.financial_apply_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "Yes", " on "])
def test_financial_apply_go_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(_GO_ENV, value)
    assert recovery.financial_apply_enabled() is True


# ── Read-only: el módulo del worker NUNCA re-POSTea (no hay vía `.submit`) ────────
def _readonly_source() -> str:
    return _WORKER_PATH.read_text(encoding="utf-8")


def test_worker_module_anchor_exists() -> None:
    """El fichero y los dos helpers reales existen (ancla de contrato, no de humo)."""
    assert _WORKER_PATH.is_file(), _WORKER_PATH
    tree = ast.parse(_readonly_source())
    defs = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {"_worker_enabled", "financial_apply_enabled", "resolve_one_unknown"} <= defs


def test_worker_module_never_submits_or_reposts() -> None:
    """El worker es read-only: ni `resolve_broker_adapter` ni un `X.submit(...)`."""
    source = _readonly_source()
    tree = ast.parse(source)
    submit_calls = sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "submit"
    )
    assert submit_calls == [], f"el recovery worker NO debe hacer POST (submit) L{submit_calls}"
    assert "resolve_broker_adapter" not in source, "el worker no debe resolver el adapter POST"
    # La única vía al broker es la query (`XtbLiveOrderQueryAdapter`); NO el adapter de POST.
    assert "XtbBrokerAdapter" not in source, "el worker no debe referenciar el adapter de POST"
    assert "query_broker_order" in source, "la única salida de UNKNOWN es la query al broker"


# ── Read-only funcional: UNKNOWN solo sale por `query_broker` ─────────────────────
@pytest.mark.asyncio
async def test_resolve_without_query_stays_unknown() -> None:
    """Sin cliente de query → fila sigue UNKNOWN (fail-closed, sin re-POST)."""
    order = _unknown_order()
    store = _RecordingStore()
    status = await recovery.resolve_one_unknown(order, None, store=store, account_id="acc-1")
    assert status == "unavailable"
    assert len(store.puts) == 1
    assert store.puts[0][0].status == "UNKNOWN"
    assert store.puts[0][1] == "acc-1"


@pytest.mark.asyncio
async def test_resolve_without_venue_order_id_does_not_query() -> None:
    """Sin `venue_order_id` ni siquiera se consulta al broker: sigue UNKNOWN."""
    order = _unknown_order(order_id="ord-2", venue_order_id=None)
    query = MockLiveOrderQuery(
        BrokerOrderQueryResult(
            outcome="filled",
            venue_order_id=None,
            filled_quantity=None,
            remaining_quantity=None,
        )
    )
    store = _RecordingStore()
    status = await recovery.resolve_one_unknown(order, query, store=store, account_id="acc-1")
    assert status == "unavailable"
    assert query.calls == 0
    assert store.puts[0][0].status == "UNKNOWN"


@pytest.mark.asyncio
async def test_unknown_exits_only_via_broker_query() -> None:
    """UNKNOWN→WORKING se persiste SOLO tras consultar `query_broker_order`."""
    order = _unknown_order(order_id="ord-3")
    query = MockLiveOrderQuery(
        BrokerOrderQueryResult(
            outcome="working",
            venue_order_id="venue-1",
            filled_quantity=None,
            remaining_quantity=None,
        )
    )
    store = _RecordingStore()
    status = await recovery.resolve_one_unknown(order, query, store=store, account_id="acc-1")
    assert status == "resolved"
    assert query.calls == 1
    assert len(store.puts) == 1
    assert store.puts[0][0].status == "WORKING"
