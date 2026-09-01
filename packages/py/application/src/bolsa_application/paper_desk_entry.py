"""V1.50 — EntryTick real: Estudio → Ranking → TradePlan → OpeningGate.

Adapta ``ProposeEstudioAutoOpenings`` al puerto ``PaperDeskEntryPort``.
Transporta ``CandidateSnapshot`` (no tira ``hits[]``). Paper-D Composite fuera.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from bolsa_analytics.cognitive.operating_policy import resolve_operating_policy
from bolsa_application.daily_ops_report import (
    ESTUDIO_LIST_ID,
    ESTUDIO_STATUS_EMPTY,
    ESTUDIO_STATUS_OK,
    ESTUDIO_STATUS_UNAVAILABLE,
    EstudioUniverseResolution,
)
from bolsa_application.paper_desk_cycle import (
    CandidateSnapshot,
    EntryReasonCode,
    PaperDeskEntryTickResult,
)

_EXECUTED_ACTION_STATUSES = frozenset({"trade_executed", "executed"})
_GATE_EVAL = "not_evaluated"


class EstudioListPort(Protocol):
    async def execute(self, list_id: str) -> Any: ...


class EstudioAutoProposePort(Protocol):
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...


async def resolve_estudio_universe(
    estudio_list: EstudioListPort | None,
) -> EstudioUniverseResolution:
    """Resuelve universo Estudio (≠ confundir empty con unavailable)."""
    if estudio_list is None:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    try:
        detail = await estudio_list.execute(ESTUDIO_LIST_ID)
    except Exception:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    if detail is None:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    raw = getattr(detail, "instrument_ids", None)
    if not isinstance(raw, list):
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_UNAVAILABLE)
    ids = [str(i) for i in raw if i]
    if not ids:
        return EstudioUniverseResolution(status=ESTUDIO_STATUS_EMPTY)
    return EstudioUniverseResolution(status=ESTUDIO_STATUS_OK, instrument_ids=ids)


def _count_executed_actions(execution: dict[str, Any] | None) -> int:
    if not execution:
        return 0
    actions = execution.get("actions") or []
    return sum(
        1
        for action in actions
        if str(action.get("status") or "") in _EXECUTED_ACTION_STATUSES
    )


def _float_field(plan: dict[str, Any] | None, *keys: str) -> float | None:
    if not isinstance(plan, dict):
        return None
    for key in keys:
        raw = plan.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
    return None


def _score_from_stars(stars: Any) -> float:
    try:
        return float(stars)
    except (TypeError, ValueError):
        return 0.0


def _rank_for(
    iid: str,
    ranked_ids: list[str],
    fallback_index: int,
) -> int:
    if iid in ranked_ids:
        return ranked_ids.index(iid) + 1
    return fallback_index


def _skip_reason_code(row: dict[str, Any]) -> EntryReasonCode:
    raw = str(row.get("reason") or "")
    if raw.startswith("propose_error"):
        return "ENTRY_INFRA_UNAVAILABLE"
    why = row.get("whyNot")
    if not isinstance(why, list):
        plan = row.get("tradePlan")
        why = plan.get("whyNot") if isinstance(plan, dict) else []
    if isinstance(why, list) and "no_stop" in why:
        return "ENTRY_INVALID_STOP"
    if raw == "sin_precio":
        return "ENTRY_NO_TRIGGER"
    return "ENTRY_NO_TRIGGER"


def _human_for_code(code: EntryReasonCode, raw: str | None = None) -> str:
    labels: dict[EntryReasonCode, str] = {
        "ENTRY_NO_TRIGGER": "TradePlan no TRIGGERED — ranking ≠ autorización.",
        "ENTRY_INVALID_STOP": "Stop inválido — no BUY.",
        "ENTRY_RISK_LIMIT": "OpeningGate DENY (riesgo / concentración).",
        "ENTRY_STALE_DATA": "Datos stale — no evaluar como 0 oportunidades.",
        "ENTRY_MANDATE_BLOCK": "Mandato de cuenta veta la apertura.",
        "ENTRY_POLICY_MISSING": "executionPolicyId / política requerida.",
        "ENTRY_MARKET_CLOSED": "Mercado cerrado.",
        "ENTRY_DUPLICATE": "Propuesta duplicada.",
        "ENTRY_ENV_BLOCKED": "PAPER_D_EXECUTE off.",
        "ENTRY_UNIVERSE_EMPTY": "Estudio list empty — 0 candidatos.",
        "ENTRY_UNIVERSE_UNAVAILABLE": "Estudio list unavailable — no sabemos.",
        "ENTRY_INFRA_UNAVAILABLE": "Fallo de infraestructura al proponer.",
    }
    base = labels[code]
    if raw:
        return f"{base} ({raw})"
    return base


def _gate_reason_code(action_reason: str | None) -> EntryReasonCode:
    text = (action_reason or "").lower()
    if "fresh" in text or "stale" in text:
        return "ENTRY_STALE_DATA"
    if "mandate" in text:
        return "ENTRY_MANDATE_BLOCK"
    if "closed" in text or "market" in text:
        return "ENTRY_MARKET_CLOSED"
    return "ENTRY_RISK_LIMIT"


def _snapshot_from_hit(
    hit: dict[str, Any],
    *,
    rank: int,
    score: float,
    template_id: str | None,
    analysis_as_of: str | None,
    market_as_of: str | None,
    execution_as_of: str | None,
    dry_run: bool,
    action: dict[str, Any] | None,
) -> CandidateSnapshot:
    signal = hit.get("signal") if isinstance(hit.get("signal"), dict) else {}
    plan = hit.get("tradePlan") if isinstance(hit.get("tradePlan"), dict) else None
    iid = str(hit.get("instrumentId") or signal.get("instrumentId") or "")
    decision_id = str(signal.get("id") or f"edo-{iid}")
    as_of = analysis_as_of or str(hit.get("asOfBarDate") or "")[:10] or None
    mandate = _GATE_EVAL
    freshness = _GATE_EVAL
    vetoes: tuple[str, ...] = ()
    reason_code: EntryReasonCode | None = None
    human: str | None = None
    if not dry_run and isinstance(action, dict):
        status = str(action.get("status") or "")
        action_reason = str(action.get("reason") or "") or None
        if status not in _EXECUTED_ACTION_STATUSES:
            reason_code = _gate_reason_code(action_reason)
            human = _human_for_code(reason_code, action_reason)
            vetoes = (action_reason or reason_code,)
            mandate = "ok" if reason_code != "ENTRY_MANDATE_BLOCK" else "veto"
            freshness = "ok" if reason_code != "ENTRY_STALE_DATA" else "stale"
        else:
            mandate = "ok"
            freshness = "ok"
    return CandidateSnapshot(
        decision_id=decision_id,
        instrument_id=iid,
        symbol=(str(hit["symbol"]) if hit.get("symbol") else None),
        rank=rank,
        score=score,
        auto_source=str(hit.get("autoSource") or "") or None,
        template_id=template_id,
        analysis_as_of=as_of,
        market_as_of=market_as_of,
        execution_as_of=execution_as_of,
        trade_plan=plan,
        entry=_float_field(plan, "entry"),
        structural_stop=_float_field(plan, "structuralStop", "stop"),
        target1=_float_field(plan, "target1"),
        target2=_float_field(plan, "target2"),
        risk_amount=_float_field(plan, "riskAmount"),
        expected_rr=_float_field(plan, "expectedRR"),
        mandate=mandate,
        freshness=freshness,
        vetoes=vetoes,
        reason_code=reason_code,
        human_message=human,
    )


def _snapshot_from_skipped(
    row: dict[str, Any],
    *,
    rank: int,
    score: float,
    template_id: str | None,
    analysis_as_of: str | None,
    market_as_of: str | None,
) -> CandidateSnapshot:
    iid = str(row.get("instrumentId") or "")
    code = _skip_reason_code(row)
    raw = str(row.get("reason") or "") or None
    plan = row.get("tradePlan") if isinstance(row.get("tradePlan"), dict) else None
    return CandidateSnapshot(
        decision_id=str(row.get("decisionId") or f"skip-{iid}"),
        instrument_id=iid,
        symbol=(str(row["symbol"]) if row.get("symbol") else None),
        rank=rank,
        score=score,
        auto_source=str(row.get("autoSource") or "") or None,
        template_id=template_id,
        analysis_as_of=analysis_as_of or str(row.get("asOfBarDate") or "")[:10] or None,
        market_as_of=market_as_of,
        execution_as_of=None,
        trade_plan=plan,
        entry=_float_field(plan, "entry"),
        structural_stop=_float_field(plan, "structuralStop", "stop"),
        target1=_float_field(plan, "target1"),
        target2=_float_field(plan, "target2"),
        risk_amount=_float_field(plan, "riskAmount"),
        expected_rr=_float_field(plan, "expectedRR"),
        mandate=_GATE_EVAL,
        freshness=_GATE_EVAL,
        vetoes=(),
        reason_code=code,
        human_message=_human_for_code(code, raw),
    )


def map_estudio_propose_to_entry_tick(
    out: dict[str, Any],
    *,
    dry_run: bool,
    template_id: str | None = None,
    operating_policy: dict[str, Any] | None = None,
    analysis_as_of: str | None = None,
    market_as_of: str | None = None,
) -> PaperDeskEntryTickResult:
    """Mapea salida ``ProposeEstudioAutoOpenings`` → ``PaperDeskEntryTickResult``."""
    hits_raw = out.get("hits") or []
    hits = [h for h in hits_raw if isinstance(h, dict)]
    skipped_raw = out.get("skipped") or []
    skipped_rows = [s for s in skipped_raw if isinstance(s, dict)]
    ranked = out.get("candidates") or []
    ranked_ids = [
        str(c.get("instrumentId"))
        for c in ranked
        if isinstance(c, dict) and c.get("instrumentId")
    ]
    cand_stars = {
        str(c.get("instrumentId")): c.get("dictamenStars")
        for c in ranked
        if isinstance(c, dict) and c.get("instrumentId")
    }
    hit_count = int(out.get("hitCount") or len(hits) or 0)
    skipped_count = len(skipped_rows)
    execute_status = str(out.get("executeStatus") or "dry_run")
    notes = tuple(str(n) for n in (out.get("notes") or []))
    generated = str(out.get("generatedAt") or "") or None
    execution_as_of = None if dry_run or execute_status == "dry_run" else generated
    execution = out.get("execution") if isinstance(out.get("execution"), dict) else None
    actions_by_iid: dict[str, dict[str, Any]] = {}
    if isinstance(execution, dict):
        for action in execution.get("actions") or []:
            if isinstance(action, dict) and action.get("instrumentId"):
                actions_by_iid[str(action["instrumentId"])] = action

    candidates = tuple(
        _snapshot_from_hit(
            hit,
            rank=_rank_for(str(hit.get("instrumentId") or ""), ranked_ids, i + 1),
            score=_score_from_stars(
                cand_stars.get(str(hit.get("instrumentId") or ""))
                or hit.get("dictamenStars")
            ),
            template_id=template_id,
            analysis_as_of=analysis_as_of,
            market_as_of=market_as_of,
            execution_as_of=execution_as_of,
            dry_run=dry_run or execute_status == "dry_run",
            action=actions_by_iid.get(str(hit.get("instrumentId") or "")),
        )
        for i, hit in enumerate(hits)
    )
    skipped = tuple(
        _snapshot_from_skipped(
            row,
            rank=_rank_for(str(row.get("instrumentId") or ""), ranked_ids, i + 1),
            score=_score_from_stars(
                cand_stars.get(str(row.get("instrumentId") or ""))
                or row.get("dictamenStars")
            ),
            template_id=template_id,
            analysis_as_of=analysis_as_of,
            market_as_of=market_as_of,
        )
        for i, row in enumerate(skipped_rows)
    )

    common = {
        "proposed_count": hit_count,
        "skipped_count": skipped_count,
        "notes": notes,
        "candidates": candidates,
        "skipped": skipped,
        "template_id": template_id,
        "operating_policy": operating_policy,
    }

    if execute_status == "blocked_env":
        return PaperDeskEntryTickResult(
            status="blocked",
            reason="paper_auto_env_blocked",
            reason_code="ENTRY_ENV_BLOCKED",
            **common,
        )

    if dry_run or execute_status == "dry_run":
        return PaperDeskEntryTickResult(
            status="dry_run",
            **common,
        )

    executed_count = _count_executed_actions(execution)
    gate_blocked = hit_count > 0 and executed_count == 0
    return PaperDeskEntryTickResult(
        status="blocked" if gate_blocked else "executed",
        executed_count=executed_count,
        reason="opening_gate_denied" if gate_blocked else None,
        reason_code="ENTRY_RISK_LIMIT" if gate_blocked else None,
        **common,
    )


def _policy_dict(template_id: str | None) -> dict[str, Any]:
    return resolve_operating_policy(template_id).to_dict()


def _value_error_code(message: str) -> EntryReasonCode:
    low = message.lower()
    if "policy" in low or "política" in low or "politica" in low:
        return "ENTRY_POLICY_MISSING"
    return "ENTRY_NO_TRIGGER"


class EstudioPaperDeskEntry:
    """EntryTick PAPER: lista Estudio → rank → TradePlan TRIGGERED → Router/check_opening."""

    def __init__(
        self,
        *,
        propose: EstudioAutoProposePort,
        estudio_list: EstudioListPort | None = None,
        max_candidates: int = 25,
    ) -> None:
        self._propose = propose
        self._estudio_list = estudio_list
        self._max_candidates = max_candidates

    async def run_entry_tick(
        self,
        *,
        account_id: str,
        as_of: str | None,
        dry_run: bool,
        paper_d_execute: bool,
        execution_policy_id: str | None,
        template_id: str | None,
    ) -> PaperDeskEntryTickResult:
        policy = _policy_dict(template_id)
        analysis_as_of = as_of.strip()[:10] if as_of and as_of.strip() else None
        if not dry_run and not paper_d_execute:
            return PaperDeskEntryTickResult(
                status="blocked",
                reason="paper_auto_env_blocked",
                reason_code="ENTRY_ENV_BLOCKED",
                notes=("EntryTick blocked: PAPER_D_EXECUTE off.",),
                template_id=template_id,
                operating_policy=policy,
            )

        universe = await resolve_estudio_universe(self._estudio_list)
        if universe.status == ESTUDIO_STATUS_UNAVAILABLE:
            return PaperDeskEntryTickResult(
                status="unavailable",
                reason="estudio_universe_unavailable",
                reason_code="ENTRY_UNIVERSE_UNAVAILABLE",
                notes=("Estudio list unavailable — 0 propuestas.",),
                template_id=template_id,
                operating_policy=policy,
            )
        if universe.status == ESTUDIO_STATUS_EMPTY:
            return PaperDeskEntryTickResult(
                status="dry_run" if dry_run else "proposed",
                proposed_count=0,
                reason_code="ENTRY_UNIVERSE_EMPTY",
                notes=("Estudio list empty — 0 candidatos.",),
                template_id=template_id,
                operating_policy=policy,
            )

        as_of_bar: date | str | None = None
        if as_of:
            try:
                as_of_bar = date.fromisoformat(as_of.strip()[:10])
            except ValueError:
                as_of_bar = as_of.strip()[:10]

        payload: dict[str, Any] = {
            "instrumentIds": universe.instrument_ids,
            "accountId": account_id,
            "maxCandidates": self._max_candidates,
            "execute": (not dry_run) and paper_d_execute,
        }
        if template_id:
            payload["templateId"] = template_id
        if as_of_bar is not None:
            payload["asOfBarDate"] = as_of_bar
        if execution_policy_id:
            payload["executionPolicyId"] = execution_policy_id

        if payload["execute"] and not execution_policy_id:
            return PaperDeskEntryTickResult(
                status="blocked",
                reason="execution_policy_required",
                reason_code="ENTRY_POLICY_MISSING",
                notes=("executionPolicyId requerido cuando dryRun=false.",),
                template_id=template_id,
                operating_policy=policy,
            )

        try:
            out = await self._propose.execute(payload)
        except ValueError as exc:
            code = _value_error_code(str(exc))
            return PaperDeskEntryTickResult(
                status="blocked",
                reason="entry_propose_failed",
                reason_code=code,
                notes=(str(exc),),
                template_id=template_id,
                operating_policy=policy,
            )
        except Exception as exc:
            return PaperDeskEntryTickResult(
                status="unavailable",
                reason="entry_propose_unavailable",
                reason_code="ENTRY_INFRA_UNAVAILABLE",
                notes=(str(exc),),
                template_id=template_id,
                operating_policy=policy,
            )

        return map_estudio_propose_to_entry_tick(
            out,
            dry_run=dry_run,
            template_id=template_id,
            operating_policy=policy,
            analysis_as_of=analysis_as_of,
            market_as_of=None,
        )
