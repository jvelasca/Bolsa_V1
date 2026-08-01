"""Pipeline semanal FA → whitelist → Paper D (propose/execute opcional).

Orquesta ``RunFundamentalScreener`` + ``ProposePaperDPlan``.
Execute sigue gated por ``PAPER_D_EXECUTE`` (no lo activa este módulo).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from bolsa_analytics.signals.fundamental_gate import build_fundamental_gate
from bolsa_analytics.signals.fundamental_screener import week_key_utc

FA_WEEKLY_PIPELINE_VERSION = "fa_weekly_pipeline_v1"
MADRID = ZoneInfo("Europe/Madrid")


class _Screener(Protocol):
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class _Propose(Protocol):
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...


def is_fa_weekly_window(
    now: datetime | None = None,
    *,
    weekday: int = 4,
    hour: int = 18,
) -> bool:
    """True en/después de la hora local Madrid del weekday (0=lun … 4=vie)."""
    dt = now or datetime.now(MADRID)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MADRID)
    local = dt.astimezone(MADRID)
    if local.weekday() != int(weekday):
        return False
    return local.hour >= int(hour)


def default_fa_weekly_gate(
    *,
    max_trailing_pe: float = 25.0,
    min_roe: float = 0.10,
    min_piotroski: float = 6.0,
    use_sector_bands: bool = True,
) -> dict[str, Any]:
    gate = build_fundamental_gate(
        max_trailing_pe=max_trailing_pe,
        min_roe=min_roe,
        min_piotroski=min_piotroski,
        use_sector_bands=use_sector_bands,
    )
    if gate is None:
        raise ValueError("Gate FA semanal vacío")
    return gate


def gate_from_json_or_defaults(raw: str | None, **defaults: Any) -> dict[str, Any]:
    text = (raw or "").strip()
    if text:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("FA_WEEKLY_GATE_JSON debe ser un objeto")
        return parsed
    return default_fa_weekly_gate(
        max_trailing_pe=float(defaults.get("max_trailing_pe") or 25.0),
        min_roe=float(defaults.get("min_roe") or 0.10),
        min_piotroski=float(defaults.get("min_piotroski") or 6.0),
        use_sector_bands=defaults.get("use_sector_bands", True) is not False,
    )


def build_cron_payload_from_settings(settings: Any) -> dict[str, Any] | None:
    """Payload para el worker; None si falta universo."""
    list_id = (getattr(settings, "fa_weekly_universe_list_id", None) or "").strip()
    if not list_id:
        return None
    gate = gate_from_json_or_defaults(
        getattr(settings, "fa_weekly_gate_json", None),
        max_trailing_pe=getattr(settings, "fa_weekly_max_trailing_pe", 25.0),
        min_roe=getattr(settings, "fa_weekly_min_roe", 0.10),
        min_piotroski=getattr(settings, "fa_weekly_min_piotroski", 6.0),
        use_sector_bands=getattr(settings, "fa_weekly_use_sector_bands", True),
    )
    whitelist = (getattr(settings, "fa_weekly_whitelist_list_id", None) or "").strip() or None
    policy = (getattr(settings, "fa_weekly_execution_policy_id", None) or "").strip() or None
    execute = bool(getattr(settings, "fa_weekly_execute", False))
    return {
        "universe": {"listId": list_id},
        "fundamentalGate": gate,
        "refreshStale": True,
        "maxResults": int(getattr(settings, "fa_weekly_max_results", 100) or 100),
        "persist": {"listId": whitelist} if whitelist else {},
        "horizon": "swing",
        "regime": "neutral",
        "minScoreDisplay100": int(
            getattr(settings, "fa_weekly_min_score_display_100", 55) or 55
        ),
        "respectVetoNewLong": True,
        "maxCandidates": int(getattr(settings, "fa_weekly_max_candidates", 25) or 25),
        "execute": execute,
        "executionPolicyId": policy,
    }


class RunFaWeeklyPipeline:
    """Screener FA (persist) → Paper D sobre la whitelist materializada."""

    def __init__(self, screener: _Screener, propose: _Propose) -> None:
        self._screener = screener
        self._propose = propose

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        universe = payload.get("universe") or {}
        gate = payload.get("fundamentalGate")
        if not isinstance(gate, dict):
            raise ValueError("fundamentalGate requerido")

        persist = payload.get("persist")
        if persist is None:
            persist = {}
        if not isinstance(persist, dict):
            raise ValueError("persist inválido")

        screener_result = await self._screener.execute(
            {
                "universe": universe,
                "fundamentalGate": gate,
                "refreshStale": payload.get("refreshStale", True) is not False,
                "maxResults": payload.get("maxResults") or 100,
                "persist": persist,
            }
        )

        week = str(screener_result.get("weekKey") or week_key_utc())
        whitelist_id = screener_result.get("persistedListId")
        hit_count = int(screener_result.get("hitCount") or 0)
        notes: list[str] = [
            f"{FA_WEEKLY_PIPELINE_VERSION}: Screener FA → whitelist → Paper D",
            "Execute gated por PAPER_D_EXECUTE (independiente del cron).",
        ]

        propose_result: dict[str, Any] | None = None
        if hit_count <= 0 or not whitelist_id:
            status = "completed_no_hits" if hit_count <= 0 else "propose_skipped_no_whitelist"
            if hit_count <= 0:
                notes.append("Sin hits FA; no se propone Paper D.")
            else:
                notes.append("Hits sin whitelist persistida; propose omitido.")
            return {
                "pipelineVersion": FA_WEEKLY_PIPELINE_VERSION,
                "weekKey": week,
                "status": status,
                "whitelistListId": whitelist_id,
                "screener": screener_result,
                "propose": None,
                "notes": notes,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
            }

        propose_result = await self._propose.execute(
            {
                "universe": {"listId": whitelist_id},
                "horizon": payload.get("horizon") or "swing",
                "regime": payload.get("regime") or "neutral",
                "minScoreDisplay100": payload.get("minScoreDisplay100") or 55,
                "respectVetoNewLong": payload.get("respectVetoNewLong", True) is not False,
                "maxCandidates": payload.get("maxCandidates") or 25,
                "execute": payload.get("execute") is True,
                "executionPolicyId": payload.get("executionPolicyId"),
            }
        )
        notes.append(
            f"Paper D sobre whitelist {whitelist_id}: "
            f"elegibles={propose_result.get('eligibleCount')} "
            f"status={propose_result.get('executeStatus')}"
        )
        return {
            "pipelineVersion": FA_WEEKLY_PIPELINE_VERSION,
            "weekKey": week,
            "status": "completed",
            "whitelistListId": whitelist_id,
            "screener": screener_result,
            "propose": propose_result,
            "notes": notes,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
