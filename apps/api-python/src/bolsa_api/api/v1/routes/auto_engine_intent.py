"""API: INTENCIÓN durable del operador sobre AUTO (M10).

Expone ``GET``/``POST /api/auto/engine-intent``.

Por qué existe: AUTO se habilitaba **sólo** por ``AUTO_SIMULATION_WORKER_ENABLED``. Tras un
reinicio con la variable puesta, el worker arrancaba aunque el operador lo hubiera apagado.
Un ``POST`` con ``enabled=false`` deja el apagado en ``auto_engine_intent`` y **gana al env**
en cada tick; un ``enabled=true`` vuelve a autorizar el arranque (siempre que el env siga ON).

La respuesta declara los tres hechos por separado —``envEnabled`` (variable), ``operatorState``
(fila durable; ``null`` = el operador no declaró nada) y ``effectiveEnabled`` (lo que el motor
hará)— en vez de un booleano que oculte cuál de los dos decidió.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)
from bolsa_api.background.auto_simulation_worker import sim_worker_enabled
from bolsa_application.auto_engine_intent_store import (
    INTENT_OFF,
    INTENT_ON,
    AutoEngineIntent,
    PostgresAutoEngineIntentStore,
)

router = APIRouter()

_ENGINE_ENV = "AUTO_ENGINE_SIM_ENGINE_ID"


def _engine_id() -> str:
    """La identidad del motor que conduce AUTO (misma resolución que el worker)."""
    import os

    return (os.getenv(_ENGINE_ENV) or "").strip() or "auto-sim"


class AutoEngineIntentDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accountId: str | None = None
    engineId: str
    envEnabled: bool
    operatorState: str | None = None
    effectiveEnabled: bool
    reason: str | None = None
    actor: str | None = None
    updatedAt: str | None = None
    version: int | None = None
    notes: list[str] = Field(default_factory=list)


class AutoEngineIntentBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool
    reason: str | None = Field(default=None, max_length=500)
    actor: str | None = Field(default=None, max_length=200)


def _dto(
    *,
    account_id: str | None,
    engine_id: str,
    intent: AutoEngineIntent | None,
    env_enabled: bool,
    notes: list[str] | None = None,
) -> AutoEngineIntentDto:
    operator_state = intent.desired_state if intent is not None else None
    # Sólo un OFF canónico apaga; un estado ausente o ilegible deja decidir al env.
    effective = env_enabled and operator_state != INTENT_OFF
    return AutoEngineIntentDto(
        accountId=account_id,
        engineId=engine_id,
        envEnabled=env_enabled,
        operatorState=operator_state or None,
        effectiveEnabled=effective,
        reason=intent.reason if intent is not None else None,
        actor=intent.actor if intent is not None else None,
        updatedAt=intent.updated_at if intent is not None else None,
        version=intent.version if intent is not None else None,
        notes=list(notes or []),
    )


@router.get("/auto/engine-intent", response_model=AutoEngineIntentDto)
async def get_auto_engine_intent(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoEngineIntentDto:
    """Intención durable + lo que el motor haría ahora mismo (read-only)."""
    engine_id = _engine_id()
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return _dto(
            account_id=None,
            engine_id=engine_id,
            intent=None,
            env_enabled=sim_worker_enabled(),
            notes=["no_account_scope"],
        )
    intent = await PostgresAutoEngineIntentStore(session).load(str(scope), engine_id)
    return _dto(
        account_id=str(scope),
        engine_id=engine_id,
        intent=intent,
        env_enabled=sim_worker_enabled(),
    )


@router.post("/auto/engine-intent", response_model=AutoEngineIntentDto)
async def post_auto_engine_intent(
    body: AutoEngineIntentBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoEngineIntentDto:
    """Declara la intención del operador; un ``OFF`` gana al env en todos los ticks."""
    engine_id = _engine_id()
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        notes = ["no_account_scope", "intent_not_recorded"]
        return _dto(
            account_id=None,
            engine_id=engine_id,
            intent=None,
            env_enabled=sim_worker_enabled(),
            notes=notes,
        )
    desired = INTENT_ON if body.enabled else INTENT_OFF
    from datetime import UTC, datetime

    intent = AutoEngineIntent(
        account_id=str(scope),
        engine_id=engine_id,
        desired_state=desired,
        reason=body.reason,
        actor=body.actor,
        updated_at=datetime.now(UTC).isoformat(),
    )
    store = PostgresAutoEngineIntentStore(session)
    await store.save(intent)
    saved = await store.load(str(scope), engine_id)
    return _dto(
        account_id=str(scope),
        engine_id=engine_id,
        intent=saved,
        env_enabled=sim_worker_enabled(),
    )


__all__ = ["router"]
