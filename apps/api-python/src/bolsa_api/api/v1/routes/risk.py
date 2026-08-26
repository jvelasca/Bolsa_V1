"""A3 — API kill switch runtime (OR-P7) + VS-1/RV-1 broker venue Paper|Live.

Endpoints bajo ``/api/risk`` para activar/consultar el veto de aperturas
automáticas sin reiniciar el proceso. Combina env ``RISK_KILL_SWITCH`` con
memoria de proceso y Redis (best-effort).

RV-1: ``/broker-venue`` con override memoria + Redis (coalesce; default paper).
PA-1: preferencia por cuenta vive en ``/accounts/{id}/broker-venue`` (≠ este router).
OE-1: ``GET /ops-self-eval`` scorecard SEMI+AUTO read-only (measure ≠ Accept).

@see docs/engineering/camino-d-a2-a5-prep-2026-08-04.md
@see docs/engineering/risk-engine-or-re-2026-08-04.md
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_repository,
    get_daily_opinion_telemetry_service,
    get_db_session,
)
from bolsa_application.broker_venue_runtime import (
    account_broker_venue_from_settings,
    broker_venue_status,
    effective_broker_venue_async,
    normalize_broker_venue,
    set_broker_venue,
)
from bolsa_application.ops_self_eval import build_ops_self_eval_report
from bolsa_application.ops_self_eval_counts import load_semi_account_counts
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
    brokerVenue: Literal["paper", "live"] = "paper"
    updated: dict[str, Any] | None = None


class BrokerVenueBody(BaseModel):
    venue: Literal["paper", "live"]


class BrokerVenueResponse(BaseModel):
    brokerVenue: Literal["paper", "live"]
    env: Literal["paper", "live"]
    runtimeMemory: Literal["paper", "live"] | None = None
    redis: Literal["paper", "live"] | None = None
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
        brokerVenue=await effective_broker_venue_async(),
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
        brokerVenue=await effective_broker_venue_async(),
        updated=updated,
    )


@router.get("/broker-venue", response_model=BrokerVenueResponse)
async def get_broker_venue() -> BrokerVenueResponse:
    """Lee venue efectivo (memory ?? redis ?? env ``BROKER_VENUE``; default paper)."""
    st = await broker_venue_status()
    return BrokerVenueResponse(
        brokerVenue=st["brokerVenue"],
        env=st["env"],
        runtimeMemory=st["runtimeMemory"],
        redis=st["redis"],
    )


@router.post("/broker-venue", response_model=BrokerVenueResponse)
async def post_broker_venue(body: BrokerVenueBody) -> BrokerVenueResponse:
    """Fija override Paper|Live (memoria + Redis best-effort)."""
    updated = await set_broker_venue(body.venue)
    st = await broker_venue_status()
    return BrokerVenueResponse(
        brokerVenue=st["brokerVenue"],
        env=st["env"],
        runtimeMemory=st["runtimeMemory"],
        redis=st["redis"],
        updated=updated,
    )


@router.get("/ops-self-eval")
async def get_ops_self_eval(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: str = Query(
        "default-account-seed",
        alias="accountId",
        min_length=1,
        max_length=128,
    ),
    lookback_days: int = Query(120, alias="lookbackDays", ge=7, le=366),
) -> dict[str, Any]:
    """OE-1 — scorecard SEMI + AUTO (read-only). measure ≠ Accept · ≠ flip env."""
    st = await kill_switch_status()
    venue = await effective_broker_venue_async()

    pref: Literal["paper", "live"] | None = None
    try:
        settings = await get_account_repository(session).get_settings_json(account_id)
        pref_raw = account_broker_venue_from_settings(settings)
        if pref_raw is not None:
            pref = normalize_broker_venue(pref_raw)
    except ValueError:
        pref = None

    days: int | None = None
    prec: float | None = None
    recall: float | None = None
    alarma_buy: int | None = None
    mature: int | None = None
    try:
        tel = await get_daily_opinion_telemetry_service(session).compute(
            lookback_days=lookback_days
        )
        days = int(tel.days_with_opinions)
        prec = tel.buy_precision_5d
        recall = tel.buy_recall_5d
        alarma_buy = int(tel.alarma_buy_count)
        mature = int(tel.mature_buy_sample)
    except Exception:  # noqa: BLE001 — telemetry gap → UNAVAILABLE marks
        days = None

    confirm_seed: int | None = None
    journal_seed: int | None = None
    buys_seed: int | None = None
    trade_like: int | None = None
    cash_dd: float | None = None
    try:
        counts = await load_semi_account_counts(session, account_id=account_id)
        confirm_seed = int(counts["confirmSeed"])
        journal_seed = int(counts["journalSeed"])
        buys_seed = int(counts["buysSeed"])
        trade_like = int(counts["tradeLike"])
        cash_dd = float(counts["cashMaxDdFrac"])
    except Exception:  # noqa: BLE001 — DB gap
        confirm_seed = None

    return build_ops_self_eval_report(
        account_id=account_id,
        lookback_days=lookback_days,
        paper_d_execute_env=paper_d_execute_allowed(),
        kill_switch_effective=bool(st["effective"]),
        broker_venue=venue,
        account_venue_preference=pref,
        days_with_opinions=days,
        buy_precision_5d=prec,
        buy_recall_5d=recall,
        alarma_buy_count=alarma_buy,
        mature_buy_sample=mature,
        confirm_seed=confirm_seed,
        journal_seed=journal_seed,
        buys_seed=buys_seed,
        trade_like=trade_like,
        cash_max_dd_frac=cash_dd,
        portfolio_reconciliation_status="not_wired",
    )
