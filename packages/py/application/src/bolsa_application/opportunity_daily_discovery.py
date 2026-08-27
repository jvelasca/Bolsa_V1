"""Opportunity Daily Discovery — scan opt-in + propose acotado (V1.19).

No convierte Decision Board en screener. No ejecuta órdenes.
Ranking de Mesa NO depende del propose (hits del scan bastan para funnel).

Freeze: Ranking≠BUY · Confirm=firma · Opportunity≠Permission · AUTO off ·
PAPER_D_EXECUTE off.
"""

from __future__ import annotations

from typing import Any, Protocol

OPPORTUNITY_DISCOVERY_PAYLOAD_KEY = "opportunityDiscovery"
DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID = "ibex35"
DEFAULT_OPPORTUNITY_PROPOSE_CAP = 15
DEFAULT_OPPORTUNITY_PRESET_KEY = "sma_crossover"

# settings_json keys (cuenta)
SETTINGS_DAILY_SCAN_ENABLED = "opportunityDailyScanEnabled"
SETTINGS_UNIVERSE_LIST_ID = "opportunityUniverseListId"


def is_opportunity_discovery_payload(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(payload.get(OPPORTUNITY_DISCOVERY_PAYLOAD_KEY))


def build_opportunity_scan_payload(
    *,
    list_id: str = DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
    account_id: str | None = None,
    propose_cap: int = DEFAULT_OPPORTUNITY_PROPOSE_CAP,
    preset_key: str = DEFAULT_OPPORTUNITY_PRESET_KEY,
    timeframe: str = "1d",
    max_results: int = 100,
) -> dict[str, Any]:
    """Payload para EnqueueScanJob / ProcessScanJob (solo lectura + propose)."""
    cap = max(0, min(int(propose_cap), DEFAULT_OPPORTUNITY_PROPOSE_CAP))
    payload: dict[str, Any] = {
        "universe": {"listId": list_id},
        "timeframe": timeframe,
        "presetKey": preset_key,
        "maxResults": max_results,
        "barLimit": 500,
        OPPORTUNITY_DISCOVERY_PAYLOAD_KEY: True,
        "opportunityProposeCap": cap,
    }
    if account_id:
        payload["opportunityAccountId"] = account_id
    return payload


def _hit_score(hit: Any) -> float:
    if isinstance(hit, dict):
        for key in ("globalScore", "global_score", "aiScore", "ai_score"):
            raw = hit.get(key)
            if isinstance(raw, (int, float)):
                return float(raw)
        return 0.0
    for attr in ("global_score", "ai_score"):
        raw = getattr(hit, attr, None)
        if isinstance(raw, (int, float)):
            return float(raw)
    return 0.0


def _hit_instrument_id(hit: Any) -> str | None:
    if isinstance(hit, dict):
        raw = hit.get("instrumentId") or hit.get("instrument_id")
        return str(raw) if raw else None
    raw = getattr(hit, "instrument_id", None)
    return str(raw) if raw else None


def _hit_symbol(hit: Any) -> str | None:
    if isinstance(hit, dict):
        raw = hit.get("symbol")
        return str(raw) if raw else None
    raw = getattr(hit, "symbol", None)
    return str(raw) if raw else None


def select_hits_for_propose(
    hits: list[Any],
    *,
    cap: int = DEFAULT_OPPORTUNITY_PROPOSE_CAP,
) -> list[Any]:
    """Top-N hits por score — tope duro; nunca execute."""
    limit = max(0, min(int(cap), DEFAULT_OPPORTUNITY_PROPOSE_CAP))
    if limit <= 0 or not hits:
        return []
    ordered = sorted(hits, key=_hit_score, reverse=True)
    return ordered[:limit]


def account_wants_daily_scan(settings_json: dict[str, Any] | None) -> bool:
    """Preferencia de cuenta; ausente = no (opt-in)."""
    if not isinstance(settings_json, dict):
        return False
    raw = settings_json.get(SETTINGS_DAILY_SCAN_ENABLED)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def resolve_universe_list_id(
    settings_json: dict[str, Any] | None,
    *,
    default: str = DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
) -> str:
    if isinstance(settings_json, dict):
        raw = settings_json.get(SETTINGS_UNIVERSE_LIST_ID)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return default


class _EnqueuePort(Protocol):
    async def execute(
        self,
        payload: dict[str, Any],
        *,
        tracker_definition_id: str | None = None,
    ) -> Any: ...


class _ProposePort(Protocol):
    async def execute(self, **kwargs: Any) -> Any: ...


class EnqueueOpportunityDailyScan:
    """Encola scan de discovery (sin execute). Default list = ibex35."""

    def __init__(self, enqueue: _EnqueuePort) -> None:
        self._enqueue = enqueue

    async def execute(
        self,
        *,
        list_id: str = DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
        account_id: str | None = None,
        propose_cap: int = DEFAULT_OPPORTUNITY_PROPOSE_CAP,
    ) -> Any:
        payload = build_opportunity_scan_payload(
            list_id=list_id,
            account_id=account_id,
            propose_cap=propose_cap,
        )
        return await self._enqueue.execute(payload)


class ProposeOpportunityHits:
    """Propose acotado post-scan — DecisionSession de lectura; cero Router/execute."""

    def __init__(self, propose: _ProposePort) -> None:
        self._propose = propose

    async def execute(
        self,
        hits: list[Any],
        *,
        account_id: str,
        cap: int = DEFAULT_OPPORTUNITY_PROPOSE_CAP,
        suggested_quantity: float = 1.0,
    ) -> dict[str, Any]:
        selected = select_hits_for_propose(hits, cap=cap)
        proposed = 0
        errors: list[dict[str, str]] = []
        for hit in selected:
            iid = _hit_instrument_id(hit)
            if not iid:
                continue
            symbol = _hit_symbol(hit)
            try:
                await self._propose.execute(
                    instrument_id=iid,
                    suggested_quantity=suggested_quantity,
                    account_id=account_id,
                    symbol=symbol,
                )
                proposed += 1
            except Exception as exc:  # noqa: BLE001 — isolation per hit
                errors.append({"instrumentId": iid, "error": str(exc)})
        return {
            "selected": len(selected),
            "proposed": proposed,
            "errors": errors,
            "executed": False,
            "auto": False,
        }
