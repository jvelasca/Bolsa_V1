"""A3 — API kill switch runtime (OR-P7).

Endpoints bajo ``/api/risk`` para activar/consultar el veto de aperturas
automáticas sin reiniciar el proceso. Combina env ``RISK_KILL_SWITCH`` con
memoria de proceso y Redis (best-effort).

@see docs/engineering/camino-d-a2-a5-prep-2026-08-04.md
@see docs/engineering/risk-engine-or-re-2026-08-04.md
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.risk_runtime import kill_switch_status, set_kill_switch

router = APIRouter(prefix="/risk", tags=["risk"])


class KillSwitchBody(BaseModel):
    """Body POST kill switch: ``enabled=true`` bloquea aperturas automáticas."""

    enabled: bool = Field(..., description="true = bloquear aperturas automáticas")


class KillSwitchResponse(BaseModel):
    """Estado efectivo del kill switch + lectura de ``PAPER_D_EXECUTE`` (solo info)."""

    effective: bool
    env: bool
    runtimeMemory: bool
    redis: bool | None = None
    paperDExecuteEnv: bool = False
    updated: dict[str, Any] | None = None


@router.get("/kill-switch", response_model=KillSwitchResponse)
async def get_kill_switch() -> KillSwitchResponse:
    """Lee kill switch efectivo (env ∨ memoria ∨ Redis) y si Paper D execute está on."""
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
    """Activa o desactiva el kill switch runtime (memoria + Redis si hay)."""
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
