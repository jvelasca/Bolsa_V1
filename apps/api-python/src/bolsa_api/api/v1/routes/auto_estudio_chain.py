"""API: AUTO · ESTUDIO — evidencia de la CADENA por valor (read-only).

Expone el artefacto ``auto-estudio-chain-v1`` que compone
:func:`bolsa_application.auto_chain_durable_reader.build_chain_evidence_artifact`: por cada
valor del universo ESTUDIO y por ciclo, las **nueve** etapas durables
(``SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL → PROTECTION → SETTLEMENT →
CYCLE_CLOSED``), la identidad de estrategia **EJECUTADA** que sella el ciclo, el contraste con
la **mejor puntuada** del selector cross-asset, el P&L conciliado y la verificación DÍA-D.

Reglas duras (las mismas que el lector):

* **Read-only.** Solo ``SELECT``; no abre el motor, no escribe en la BD ni cambia umbrales.
* **No fabrica.** Una etapa sin traza durable viaja ``None`` (hueco declarado), **nunca** ``0``.
  Un valor sin ciclos declara ``cycles = []`` y ``measured = false``.
* **Fail-closed por cuenta.** Sin cuenta visible del principal no se lee nada
  (``available = false`` con ``no_account_scope``). Un fallo de lectura es un **error
  declarado** (``error`` + nota), nunca una lista vacía disfrazada de medición.

No se promociona ``CONFIRMED`` ni se declara rentabilidad: la ventana PAPER real es OPERACIÓN.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    get_list_repository,
    resolve_account_scope_or_default,
)
from bolsa_application.auto_chain_durable_reader import (
    build_chain_evidence_artifact,
    read_estudio_chain_evidence,
)
from bolsa_application.paper_desk_entry import resolve_estudio_universe

__all__ = ["EstudioChainResponseDto", "router"]

router = APIRouter()
logger = logging.getLogger(__name__)

#: Sufijo por defecto del motor AUTO (mismo que el CLI ``v2_99``).
_DEFAULT_ENGINE_ID = "auto-sim"

#: Tope de ciclos leídos por petición (la ruta es interactiva, no un export masivo).
_MAX_LIMIT = 200


class EstudioChainResponseDto(BaseModel):
    """Evidencia de la cadena por valor. ``available = false`` declara el hueco o el error."""

    model_config = ConfigDict(populate_by_name=True)

    available: bool
    readOnly: bool = True
    account_id: str | None = Field(default=None, alias="accountId")
    as_of: str | None = Field(default=None, alias="asOf")
    engine_id: str | None = Field(default=None, alias="engineId")
    estudio: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    best_scored: dict[str, Any] | None = Field(default=None, alias="bestScored")
    values: list[dict[str, Any]] = Field(default_factory=list)
    cycles_outside_estudio: list[dict[str, Any]] = Field(
        default_factory=list, alias="cyclesOutsideEstudio"
    )
    meta: dict[str, Any] = Field(default_factory=dict)
    limits: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    #: Motivo legible cuando la lectura falla. Un hueco **medido** no lo rellena.
    error: str | None = None


class _SessionEstudioList:
    """``EstudioListPort`` sobre la sesión de la petición (sin abrir sesiones nuevas).

    ``resolve_estudio_universe`` solo necesita ``execute(list_id)``; se reutiliza el resolver
    canónico de ESTUDIO en vez de reimplementar el universo.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, list_id: str) -> Any:
        from bolsa_application.lists import GetInstrumentList

        return await GetInstrumentList(
            get_list_repository(self._session)
        ).execute(list_id)


async def _resolve_estudio(session: AsyncSession) -> dict[str, Any]:
    """Universo ESTUDIO por el camino canónico (fail-closed si no se puede resolver)."""
    resolution = await resolve_estudio_universe(_SessionEstudioList(session))
    return {
        "status": getattr(resolution, "status", None),
        "instrumentIds": [
            str(i) for i in (getattr(resolution, "instrument_ids", None) or []) if i
        ],
    }


@router.get("/auto/estudio-chain", response_model=EstudioChainResponseDto)
async def get_auto_estudio_chain(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cycle_id: Annotated[str | None, Query(alias="cycleId")] = None,
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    engine_id: Annotated[str | None, Query(alias="engineId")] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 100,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> EstudioChainResponseDto:
    """Cadena durable por valor de ESTUDIO para la cuenta activa (read-only, fail-closed)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return EstudioChainResponseDto(available=False, notes=["no_account_scope"])

    resolved_engine = (engine_id or _DEFAULT_ENGINE_ID).strip() or _DEFAULT_ENGINE_ID
    try:
        estudio = await _resolve_estudio(session)
        read = await read_estudio_chain_evidence(
            session,
            str(scope),
            engine_id=resolved_engine,
            limit=int(limit),
            cycle_id=str(cycle_id) if cycle_id else None,
            instrument_id=str(instrument_id) if instrument_id else None,
        )
        artifact = build_chain_evidence_artifact(
            account_id=str(scope),
            estudio=estudio,
            cycles=read["cycles"],
            best_scored=read["bestScored"],
            meta={
                "engineId": resolved_engine,
                "limit": int(limit),
                "cycleId": str(cycle_id) if cycle_id else None,
                "instrumentId": str(instrument_id) if instrument_id else None,
                "source": "auto_chain_durable_reader",
            },
            limits=[
                "Read-only: solo SELECT; no escribe en la BD durable ni cambia el motor.",
                "La cadena se LEE de hechos durables; una etapa sin traza declara None, nunca 0.",
                "La foto TOP3 sella la identidad (preset + versión) del candidato ganador desde "
                "la migración 057; las fotos anteriores viajan sin identidad (hueco declarado) "
                "y el emparejamiento por preset es entonces None, nunca una inferencia.",
                "NO certifica la ventana PAPER real ni la rentabilidad: eso es OPERACIÓN.",
            ],
        )
    except Exception as exc:  # noqa: BLE001 — un fallo se DECLARA, no se convierte en lista vacía.
        logger.exception("estudio-chain: lectura fallida para la cuenta %s", scope)
        return EstudioChainResponseDto(
            available=False,
            account_id=str(scope),
            engine_id=resolved_engine,
            notes=["read_failed"],
            error=f"{type(exc).__name__}: {exc}",
        )

    if estudio.get("status") != "ok":
        # Universo no disponible/vacío: se expone la evidencia leída con el hueco declarado.
        artifact.setdefault("notes", []).append(f"estudio_{estudio.get('status') or 'unknown'}")

    return EstudioChainResponseDto(
        available=True,
        account_id=str(scope),
        as_of=artifact.get("asOf"),
        engine_id=resolved_engine,
        estudio=dict(artifact.get("estudio") or {}),
        summary=dict(artifact.get("summary") or {}),
        best_scored=artifact.get("bestScored"),
        values=list(artifact.get("values") or []),
        cycles_outside_estudio=list(artifact.get("cyclesOutsideEstudio") or []),
        meta=dict(artifact.get("meta") or {}),
        limits=list(artifact.get("limits") or []),
        notes=list(artifact.get("notes") or []),
    )
