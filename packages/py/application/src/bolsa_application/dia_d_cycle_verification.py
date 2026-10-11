"""P2 — Verificación DÍA-D ENLAZADA a un ciclo AUTO (registro durable).

Caso de uso y helper PURO que convierte el payload de la verificación manual D→hoy en
la fila durable que la enlaza a su ciclo. Doctrina de huecos: un campo ausente se
declara ``None`` (nunca ``""``/``0``); sin ``cycleId``/``instrumentId``/``symbol``/
``diaD``/``endDate``/``mode`` NO se fabrica un enlace (el draft es ``None``).
"""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_dia_d_cycle_verification_draft(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Draft de ``upsert`` desde el payload HTTP; ``None`` si falta lo indispensable.

    NO fabrica identidad: ``strategy_preset_key``/``strategy_version``/
    ``strategy_definition_id`` quedan ``None`` si el ciclo no los declara.
    """
    cycle_id = _clean(payload.get("cycleId") or payload.get("cycle_id"))
    instrument_id = _clean(payload.get("instrumentId") or payload.get("instrument_id"))
    symbol = _clean(payload.get("symbol"))
    dia_d = _clean(payload.get("diaD") or payload.get("dia_d"))
    end_date = _clean(payload.get("endDate") or payload.get("end_date"))
    mode = _clean(payload.get("mode"))
    if not all((cycle_id, instrument_id, symbol, dia_d, end_date, mode)):
        return None
    raw_result = payload.get("result")
    result = raw_result if isinstance(raw_result, dict) else None
    return {
        "cycle_id": cycle_id,
        "instrument_id": instrument_id,
        "symbol": symbol,
        "dia_d": dia_d,
        "end_date": end_date,
        "mode": mode,
        "strategy_preset_key": _clean(
            payload.get("strategyPresetKey") or payload.get("strategy_preset_key")
        ),
        "strategy_version": _clean(
            payload.get("strategyVersion") or payload.get("strategy_version")
        ),
        "strategy_definition_id": _clean(
            payload.get("strategyDefinitionId") or payload.get("strategy_definition_id")
        ),
        "band": _clean(payload.get("band")),
        "result": result,
        "research_evidence_id": _clean(
            payload.get("researchEvidenceId") or payload.get("research_evidence_id")
        ),
    }


class _DiaDCycleVerificationRepo(Protocol):
    async def upsert(
        self,
        *,
        cycle_id: str,
        instrument_id: str,
        symbol: str,
        dia_d: str,
        end_date: str,
        mode: str,
        account_id: str | None = None,
        strategy_preset_key: str | None = None,
        strategy_version: str | None = None,
        strategy_definition_id: str | None = None,
        band: str | None = None,
        result: dict[str, Any] | None = None,
        research_evidence_id: str | None = None,
        verification_id: str | None = None,
    ) -> DiaDCycleVerification: ...

    async def list_verifications(
        self,
        *,
        account_id: str | None = None,
        cycle_id: str | None = None,
        limit: int = 200,
    ) -> list[DiaDCycleVerification]: ...


class PersistDiaDCycleVerification:
    """Registra (idempotente) la verificación DÍA-D enlazada a un ciclo."""

    def __init__(self, repository: _DiaDCycleVerificationRepo) -> None:
        self._repository = repository

    async def execute(
        self, payload: dict[str, Any], *, account_id: str | None
    ) -> DiaDCycleVerification | None:
        draft = build_dia_d_cycle_verification_draft(payload)
        if draft is None:
            return None
        return await self._repository.upsert(**draft, account_id=account_id)


class ListDiaDCycleVerifications:
    """Lista verificaciones del principal; con ``cycle_id`` acota a un ciclo."""

    def __init__(self, repository: _DiaDCycleVerificationRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        account_id: str | None,
        cycle_id: str | None = None,
        limit: int = 200,
    ) -> list[DiaDCycleVerification]:
        return await self._repository.list_verifications(
            account_id=account_id, cycle_id=cycle_id, limit=limit
        )
