"""HTTP V1.47 — Paper Desk cycle + daily report (PAPER_D gate).

POST /cycle = único mutador. GET /daily-report = consulta (dry-run evaluate).
Hechos de mercado: OperationalContext (no body flags).
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_daily_ops_report_use_case,
    get_db_session,
    get_paper_desk_cycle_use_case,
)
from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.paper_daily_report import build_paper_daily_report
from bolsa_application.paper_desk_cycle import PaperDeskCycleInput

router = APIRouter()


class PaperDeskCycleRequestDto(BaseModel):
    dry_run: bool = Field(default=True, alias="dryRun")
    template_id: str | None = Field(default="moderate", alias="templateId")
    as_of: str | None = Field(default=None, alias="asOf")

    model_config = {"populate_by_name": True}


def _parse_as_of(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return date_cls.fromisoformat(raw.strip()[:10]).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="asOf inválido (YYYY-MM-DD)") from exc


@router.post("/paper-desk/cycle")
async def paper_desk_cycle(
    body: PaperDeskCycleRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str = Query(alias="accountId"),
    execution_policy_id: str | None = Query(default=None, alias="executionPolicyId"),
) -> dict[str, Any]:
    """V1.47 — un ciclo EntryTick + PositionTick. dryRun default true."""
    if not paper_d_execute_allowed() and not body.dry_run:
        raise HTTPException(
            status_code=403,
            detail={"code": "paper_auto_env_blocked", "message": "PAPER_D_EXECUTE off"},
        )

    uc = get_paper_desk_cycle_use_case(
        session, execution_policy_id=execution_policy_id, dry_run=body.dry_run
    )
    result = await uc.execute(
        PaperDeskCycleInput(
            account_id=account_id,
            as_of=_parse_as_of(body.as_of),
            dry_run=body.dry_run,
            execution_policy_id=execution_policy_id,
            template_id=body.template_id,
        )
    )
    report = build_paper_daily_report(result)
    return {
        "data": {
            "cycle": result.to_dict(),
            "autoDesk": report.to_dict(),
        }
    }


@router.get("/paper-desk/daily-report")
async def paper_desk_daily_report(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str = Query(alias="accountId"),
    as_of: str | None = Query(default=None, alias="asOf"),
    execution_policy_id: str | None = Query(default=None, alias="executionPolicyId"),
    template_id: str | None = Query(default="moderate", alias="templateId"),
) -> dict[str, Any]:
    """V1.47 — DailyOpsReport de consulta. autoDesk vía dry-run evaluate. Nunca muta."""
    as_of_s = _parse_as_of(as_of)
    day: date_cls | None = None
    if as_of_s:
        day = date_cls.fromisoformat(as_of_s)

    uc = get_paper_desk_cycle_use_case(
        session, execution_policy_id=execution_policy_id, dry_run=True
    )
    cycle = await uc.execute(
        PaperDeskCycleInput(
            account_id=account_id,
            as_of=as_of_s,
            dry_run=True,
            execution_policy_id=execution_policy_id,
            template_id=template_id,
        )
    )
    auto_desk = build_paper_daily_report(cycle).to_dict()

    from bolsa_api.schemas.account_mappers import to_account_summary_dto, to_ledger_entry_dto
    from bolsa_application.daily_ops_report import DAILY_OPS_REPORT_SCHEMA

    try:
        bundle = await get_daily_ops_report_use_case(session).execute(
            account_id,
            as_of=day,
            auto_desk=auto_desk,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "data": {
            "schemaVersion": DAILY_OPS_REPORT_SCHEMA,
            "asOf": bundle.as_of.isoformat(),
            "generatedAt": bundle.generated_at,
            "accountId": bundle.account_id,
            "summary": to_account_summary_dto(bundle.summary).model_dump(by_alias=True),
            "ledgerToday": [
                to_ledger_entry_dto(e).model_dump(by_alias=True) for e in bundle.ledger_today
            ],
            "tradesToday": [
                to_ledger_entry_dto(e).model_dump(by_alias=True) for e in bundle.trades_today
            ],
            "week": bundle.week,
            "f3PendingCount": bundle.f3_pending_count,
            "channels": bundle.channels,
            "opinions": bundle.opinions,
            "notes": bundle.notes,
            "estudioStatus": bundle.estudio_status,
            "estudioCount": bundle.estudio_count,
            "autoDesk": auto_desk,
            "cycle": cycle.to_dict(),
        }
    }
