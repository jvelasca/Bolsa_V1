"""V1.25 / V1.33 — sizing único en openings supervisados (SEMI Confirm + AUTO A-β).

TradePlan TRIGGERED = única autoridad; % caja / libro no es mandato.
Paridad TS: ``resolveSupervisedOpeningQuantity`` (@bolsa/shared).
"""

from __future__ import annotations

from typing import Any


def _finite_positive(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    n = float(value)
    if n != n or abs(n) == float("inf") or n <= 0:
        return None
    return n


def resolve_supervised_opening_quantity(
    trade_plan: object | None,
    *,
    server_suggested_quantity: float | None = None,
) -> float | None:
    """Cantidad canónica para apertura supervisada (None = sin mandato).

    ``server_suggested_quantity`` se ignora: solo documenta paridad con el
    contrato TS (el plan TRIGGERED manda).
    """
    _ = server_suggested_quantity
    plan = trade_plan if isinstance(trade_plan, dict) else None
    if plan is None:
        return None
    if plan.get("status") != "TRIGGERED":
        return None
    return _finite_positive(plan.get("quantity"))


def extract_hit_trade_plan(hit: dict[str, Any] | None) -> dict[str, Any] | None:
    """TradePlan en hit AUTO (camelCase o snake)."""
    if not isinstance(hit, dict):
        return None
    plan = hit.get("tradePlan")
    if plan is None:
        plan = hit.get("trade_plan")
    return plan if isinstance(plan, dict) else None


# V1.33 A-δ — aperturas AUTO solo desde Estudio (dictamen / alarma).
AUTO_OPENING_SOURCES = frozenset({"estudio_dictamen", "estudio_alarma"})


def extract_hit_auto_source(hit: dict[str, Any] | None) -> str | None:
    if not isinstance(hit, dict):
        return None
    raw = hit.get("autoSource")
    if raw is None:
        raw = hit.get("auto_source")
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    return cleaned or None


def is_allowed_auto_opening_source(source: str | None) -> bool:
    return source in AUTO_OPENING_SOURCES
