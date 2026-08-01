"""Paper D — propose/execute + pipeline semanal FA→D."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_propose_paper_d_use_case,
    get_run_fa_weekly_pipeline_use_case,
)

router = APIRouter(tags=["paper-d"])


class PaperDUniverseBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    list_id: str | None = Field(default=None, alias="listId")
    instrument_ids: list[str] | None = Field(default=None, alias="instrumentIds")


class PaperDProposeBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    universe: PaperDUniverseBody
    horizon: Literal["intraday", "swing", "position", "long_term"] = "swing"
    regime: Literal["risk_on", "neutral", "risk_off", "crisis", "uncertain"] = "neutral"
    min_score_display_100: int = Field(default=55, alias="minScoreDisplay100", ge=0, le=100)
    respect_veto_new_long: bool = Field(default=True, alias="respectVetoNewLong")
    max_candidates: int = Field(default=25, alias="maxCandidates", ge=1, le=100)
    execute: bool = False
    execution_policy_id: str | None = Field(default=None, alias="executionPolicyId")


class FaWeeklyPersistBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    list_id: str | None = Field(default=None, alias="listId")
    name: str | None = None


class FaWeeklyPipelineBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    universe: PaperDUniverseBody
    fundamental_gate: dict[str, Any] = Field(alias="fundamentalGate")
    refresh_stale: bool = Field(default=True, alias="refreshStale")
    max_results: int = Field(default=100, alias="maxResults", ge=1, le=500)
    persist: FaWeeklyPersistBody | None = None
    horizon: Literal["intraday", "swing", "position", "long_term"] = "swing"
    regime: Literal["risk_on", "neutral", "risk_off", "crisis", "uncertain"] = "neutral"
    min_score_display_100: int = Field(default=55, alias="minScoreDisplay100", ge=0, le=100)
    respect_veto_new_long: bool = Field(default=True, alias="respectVetoNewLong")
    max_candidates: int = Field(default=25, alias="maxCandidates", ge=1, le=100)
    execute: bool = False
    execution_policy_id: str | None = Field(default=None, alias="executionPolicyId")


@router.post("/paper-d/propose")
async def propose_paper_d(
    body: PaperDProposeBody,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Paper D — propose (Composite × universo) + execute opcional.
    Execute: PAPER_D_EXECUTE=1 + execute=true + executionPolicyId (paper_auto)
    → ExecutionRouter (Gate cognitivo). ≠ radar (B) ≠ Supervisado (C).
    """
    payload = {
        "universe": {
            "listId": body.universe.list_id,
            "instrumentIds": body.universe.instrument_ids,
        },
        "horizon": body.horizon,
        "regime": body.regime,
        "minScoreDisplay100": body.min_score_display_100,
        "respectVetoNewLong": body.respect_veto_new_long,
        "maxCandidates": body.max_candidates,
        "execute": body.execute,
        "executionPolicyId": body.execution_policy_id,
    }
    try:
        result = await get_propose_paper_d_use_case(session).execute(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": result}


@router.post("/paper-d/weekly-run")
async def run_fa_weekly_pipeline(
    body: FaWeeklyPipelineBody,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Pipeline semanal: Screener FA → whitelist snapshot → Paper D propose/execute.
    Manual (siempre corre). Cron worker: FA_WEEKLY_CRON_ENABLED=1.
    Execute: PAPER_D_EXECUTE=1 + execute=true + policy paper_auto.
    """
    persist: dict[str, Any] | None
    if body.persist is None:
        persist = {}
    else:
        persist = {"listId": body.persist.list_id, "name": body.persist.name}
    payload = {
        "universe": {
            "listId": body.universe.list_id,
            "instrumentIds": body.universe.instrument_ids,
        },
        "fundamentalGate": body.fundamental_gate,
        "refreshStale": body.refresh_stale,
        "maxResults": body.max_results,
        "persist": persist,
        "horizon": body.horizon,
        "regime": body.regime,
        "minScoreDisplay100": body.min_score_display_100,
        "respectVetoNewLong": body.respect_veto_new_long,
        "maxCandidates": body.max_candidates,
        "execute": body.execute,
        "executionPolicyId": body.execution_policy_id,
    }
    try:
        result = await get_run_fa_weekly_pipeline_use_case(session).execute(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": result}
