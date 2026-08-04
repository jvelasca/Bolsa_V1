"""A3 — API kill switch runtime (OR-P7)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.risk_runtime import kill_switch_status, set_kill_switch

router = APIRouter(prefix="/risk", tags=["risk"])


class KillSwitchBody(BaseModel):
    enabled: bool = Field(..., description="true = bloquear aperturas automáticas")


class KillSwitchResponse(BaseModel):
    effective: bool
    env: bool
    runtimeMemory: bool
    redis: bool | None = None
    paperDExecuteEnv: bool = False
    updated: dict | None = None


@router.get("/kill-switch", response_model=KillSwitchResponse)
async def get_kill_switch() -> KillSwitchResponse:
    st = await kill_switch_status()
    return KillSwitchResponse(
        effective=bool(st["effective"]),
        env=bool(st["env"]),
        runtimeMemory=bool(st["runtimeMemory"]),
        redis=st.get("redis"),
        paperDExecuteEnv=paper_d_execute_allowed(),
    )


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def post_kill_switch(body: KillSwitchBody) -> KillSwitchResponse:
    updated = await set_kill_switch(body.enabled)
    st = await kill_switch_status()
    return KillSwitchResponse(
        effective=bool(st["effective"]),
        env=bool(st["env"]),
        runtimeMemory=bool(st["runtimeMemory"]),
        redis=st.get("redis"),
        paperDExecuteEnv=paper_d_execute_allowed(),
        updated=updated,
    )
