"""P2/v111 — Verificación DÍA-D ENLAZADA a un ciclo AUTO (registro durable).

Caso de uso y helpers PUROS que convierten la verificación manual D→hoy en la fila durable
que la enlaza a su ciclo. Doctrina de huecos: un campo ausente se declara ``None`` (nunca
``""``/``0``); sin ``cycleId``/``diaD``/``endDate``/``mode`` NO se fabrica un enlace.

**Resolución por servidor (v111).** La identidad del ciclo (instrumento, símbolo y estrategia
EJECUTADA) NO se acepta del navegador: se DERIVA de los hechos durables AUTO con un
``DiaDCycleFactsResolver``. Si el ciclo no existe en el estado durable ⇒ ``404``
(``DiaDCycleNotFoundError``); si un campo declarado por el cliente contradice el hecho durable
⇒ ``409`` (``DiaDCycleIdentityConflictError``). Un ``facts_hash`` determinista sella qué
snapshot de hechos respaldó la verificación.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification

#: Versión del esquema del hash de hechos (audita la fórmula). No cambia sin bump.
DIA_D_FACTS_SCHEMA_VERSION = "dia_d_cycle_verification_facts_v1"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_dia_d_cycle_verification_draft(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Draft de ``upsert`` desde el payload HTTP; ``None`` si falta lo indispensable.

    Helper PURO histórico: se conserva para la proyección read-only de ``dia_d_link``
    (declara si un ciclo PUEDE enlazar una verificación). La ESCRITURA en producción usa
    :class:`ResolveDiaDCycleVerification`, que deriva la identidad del ciclo en el servidor.

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
        "facts_hash": None,
        "verified_by": _clean(payload.get("verifiedBy") or payload.get("verified_by")),
    }


@dataclass(frozen=True, slots=True)
class DiaDCycleFacts:
    """Identidad durable del ciclo AUTO (derivada de los hechos, NUNCA del navegador).

    Un campo ``None`` es un hueco DECLARADO (el ciclo no sella esa identidad); jamás se
    rellena con ``""``/``0``.
    """

    cycle_id: str
    instrument_id: str | None
    symbol: str | None
    strategy_preset_key: str | None
    strategy_version: str | None


class DiaDCycleFactsResolver(Protocol):
    """Resuelve la identidad durable del ciclo para una cuenta (``None`` si no existe)."""

    async def resolve(
        self, *, account_id: str, cycle_id: str
    ) -> DiaDCycleFacts | None: ...


class DiaDCycleNotFoundError(Exception):
    """El ``cycleId`` no corresponde a ningún ciclo AUTO durable de la cuenta."""

    def __init__(self, cycle_id: str) -> None:
        super().__init__(f"cycle_not_found: {cycle_id}")
        self.cycle_id = cycle_id


class DiaDCycleIdentityConflictError(Exception):
    """Un campo declarado por el cliente contradice el hecho durable del ciclo."""

    def __init__(self, conflicts: Mapping[str, tuple[Any, Any]]) -> None:
        super().__init__("cycle_identity_conflict")
        self.conflicts: dict[str, tuple[Any, Any]] = dict(conflicts)


def compute_dia_d_facts_hash(
    *,
    cycle_id: str,
    instrument_id: str | None,
    strategy_preset_key: str | None,
    strategy_version: str | None,
    dia_d: str,
    end_date: str,
    mode: str,
) -> str:
    """Hash determinista del snapshot de hechos que respalda la verificación.

    Orden canónico + separadores compactos (patrón ``definition_hash``): dos verificaciones
    sobre los MISMOS hechos producen el mismo hash; cambiar cualquiera lo cambia.
    """
    payload = {
        "schemaVersion": DIA_D_FACTS_SCHEMA_VERSION,
        "cycleId": cycle_id,
        "instrumentId": instrument_id,
        "strategyPresetKey": strategy_preset_key,
        "strategyVersion": strategy_version,
        "diaD": dia_d,
        "endDate": end_date,
        "mode": mode,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


#: Campos que un cliente PUEDE declarar y que se contrastan contra el hecho durable. Si el
#: cliente no los declara, no hay contraste; si el hecho durable no existe (hueco), el
#: declarado no puede contradecir un hueco (no se fabrica un conflicto).
_CONTRAST_FIELDS: tuple[tuple[str, str], ...] = (
    ("instrumentId", "instrument_id"),
    ("symbol", "symbol"),
    ("strategyPresetKey", "strategy_preset_key"),
    ("strategyVersion", "strategy_version"),
)


def _declared_conflicts(
    payload: Mapping[str, Any], facts: DiaDCycleFacts
) -> dict[str, tuple[str, str]]:
    durable: dict[str, str | None] = {
        "instrumentId": facts.instrument_id,
        "symbol": facts.symbol,
        "strategyPresetKey": facts.strategy_preset_key,
        "strategyVersion": facts.strategy_version,
    }
    conflicts: dict[str, tuple[str, str]] = {}
    for alias, snake in _CONTRAST_FIELDS:
        declared = _clean(payload.get(alias) or payload.get(snake))
        if declared is None:
            continue
        durable_value = _clean(durable[alias])
        if durable_value is None:
            continue
        if declared != durable_value:
            conflicts[alias] = (declared, durable_value)
    return conflicts


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
        facts_hash: str | None = None,
        verified_by: str | None = None,
        verification_id: str | None = None,
    ) -> DiaDCycleVerification: ...

    async def list_verifications(
        self,
        *,
        account_id: str | None = None,
        cycle_id: str | None = None,
        limit: int = 200,
    ) -> list[DiaDCycleVerification]: ...


class ResolveDiaDCycleVerification:
    """Registra (idempotente) la verificación DÍA-D resolviendo el ciclo en el servidor.

    Deriva la identidad del ciclo desde los hechos durables AUTO; el navegador NO declara qué
    ocurrió en el ciclo. ``cycleId`` inexistente ⇒ :class:`DiaDCycleNotFoundError`; identidad
    declarada que contradice el hecho durable ⇒ :class:`DiaDCycleIdentityConflictError`.
    """

    def __init__(
        self,
        repository: _DiaDCycleVerificationRepo,
        facts_resolver: DiaDCycleFactsResolver,
    ) -> None:
        self._repository = repository
        self._facts = facts_resolver

    async def execute(
        self, payload: dict[str, Any], *, account_id: str
    ) -> DiaDCycleVerification:
        cycle_id = _clean(payload.get("cycleId") or payload.get("cycle_id"))
        mode = _clean(payload.get("mode"))
        dia_d = _clean(payload.get("diaD") or payload.get("dia_d"))
        end_date = _clean(payload.get("endDate") or payload.get("end_date"))
        if not all((cycle_id, mode, dia_d, end_date)):
            raise ValueError("incomplete_dia_d_verification_payload")
        assert cycle_id is not None and mode is not None
        assert dia_d is not None and end_date is not None

        facts = await self._facts.resolve(account_id=account_id, cycle_id=cycle_id)
        if facts is None:
            raise DiaDCycleNotFoundError(cycle_id)

        conflicts = _declared_conflicts(payload, facts)
        if conflicts:
            raise DiaDCycleIdentityConflictError(conflicts)

        raw_result = payload.get("result")
        result = raw_result if isinstance(raw_result, dict) else None
        facts_hash = compute_dia_d_facts_hash(
            cycle_id=cycle_id,
            instrument_id=facts.instrument_id,
            strategy_preset_key=facts.strategy_preset_key,
            strategy_version=facts.strategy_version,
            dia_d=dia_d,
            end_date=end_date,
            mode=mode,
        )
        return await self._repository.upsert(
            cycle_id=cycle_id,
            account_id=account_id,
            # Identidad del ciclo: DERIVADA del hecho durable (hueco declarado si falta).
            instrument_id=facts.instrument_id or "",
            symbol=facts.symbol or "",
            dia_d=dia_d,
            end_date=end_date,
            mode=mode,
            strategy_preset_key=facts.strategy_preset_key,
            strategy_version=facts.strategy_version,
            # ``strategy_definition_id`` NO es un hecho durable del ciclo: se declara el hueco.
            strategy_definition_id=None,
            # Banda/resultado: observación humana de la verificación, ligada al ``facts_hash``.
            band=_clean(payload.get("band")),
            result=result,
            research_evidence_id=_clean(
                payload.get("researchEvidenceId") or payload.get("research_evidence_id")
            ),
            facts_hash=facts_hash,
            verified_by=_clean(payload.get("verifiedBy") or payload.get("verified_by")),
        )


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
