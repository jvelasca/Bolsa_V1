"""FIE F4 — Screener FA puro (universo × gate; sin TA/OHLCV)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bolsa_analytics.knowledge.fundamental_card import build_fundamental_card
from bolsa_analytics.signals.fundamental_gate import passes_fundamental_gate

FUNDAMENTAL_SCREENER_VERSION = "fund_screener_v1"


def week_key_utc(now: datetime | None = None) -> str:
    """Clave ISO semana (YYYY-Www) en UTC — lista blanca semanal."""
    dt = now or datetime.now(UTC)
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _definition_with_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {"hybrid": {"fundamentalGate": gate}, "kind": "fundamental_screener"}


def evaluate_fundamental_candidate(
    *,
    instrument_id: str,
    symbol: str,
    name: str | None,
    fundamentals: dict[str, Any] | None,
    gate: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Returns ``(hit, skip)`` — exactamente uno no-None.
    """
    ok, reason = passes_fundamental_gate(_definition_with_gate(gate), fundamentals)
    if not ok:
        return None, {
            "instrumentId": instrument_id,
            "symbol": symbol,
            "reason": reason or "No cumple filtro fundamental",
        }

    score100: int | None = None
    confidence: str | None = None
    if isinstance(fundamentals, dict):
        card = build_fundamental_card(
            instrument_id=instrument_id,
            ticker=symbol,
            fundamentals=fundamentals,
        )
        score100 = card.get("scoreDisplay100")
        meta = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
        confidence = meta.get("confidence")

    hit = {
        "instrumentId": instrument_id,
        "symbol": symbol,
        "name": name,
        "sector": fundamentals.get("sector") if isinstance(fundamentals, dict) else None,
        "scoreDisplay100": score100,
        "trailingPe": fundamentals.get("trailingPe") if isinstance(fundamentals, dict) else None,
        "roe": fundamentals.get("roe") if isinstance(fundamentals, dict) else None,
        "piotroski": fundamentals.get("piotroski") if isinstance(fundamentals, dict) else None,
        "fcfYield": fundamentals.get("fcfYield") if isinstance(fundamentals, dict) else None,
        "dcfUpside": fundamentals.get("dcfUpside") if isinstance(fundamentals, dict) else None,
        "grahamUpside": fundamentals.get("grahamUpside") if isinstance(fundamentals, dict) else None,
        "confidence": confidence,
    }
    return hit, None


def assemble_screener_result(
    *,
    hits: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    scanned_count: int,
    refreshed_count: int,
    list_id: str | None,
    persisted_list_id: str | None,
    max_results: int,
) -> dict[str, Any]:
    capped = hits[: max(1, min(max_results, 500))]
    return {
        "screenerVersion": FUNDAMENTAL_SCREENER_VERSION,
        "screenerId": f"fas_{uuid4().hex[:12]}",
        "scannedCount": scanned_count,
        "hitCount": len(capped),
        "skippedCount": len(skipped),
        "fundamentalsRefreshedCount": refreshed_count,
        "listId": list_id,
        "persistedListId": persisted_list_id,
        "weekKey": week_key_utc(),
        "hits": capped,
        "skipped": skipped,
    }
