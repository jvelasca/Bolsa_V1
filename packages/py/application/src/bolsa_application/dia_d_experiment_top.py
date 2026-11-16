"""F-D server-side — el experimento TOP DÍA D deja de vivir solo en el navegador.

Contexto (R6 de la auditoría LAB, 2026-11-16). Cuando el LAB verifica una fecha
pasada ``D`` produce un TOP que **no** es el operativo (F-hoy): es un experimento
as-of D. Hasta ahora ese experimento se guardaba en ``localStorage``, así que
cerrar el navegador lo borraba y ninguna auditoría podía verlo.

Este módulo lo persiste con la infraestructura que ya existe y que es
intrínsecamente auditable: ``research_evidence`` (append-only, ADR-018). Cada
guardado es una fila nueva con ``source='dia_d_experiment_top'``; el experimento
vigente es la fila **más reciente** para ``(instrumento, timeframe, D)``.

Reglas duras:

* **Procedencia verificada en servidor.** Un slot que cita un ``runId``
  inexistente o de otro instrumento se rechaza (``TopProvenanceError`` ⇒ 422);
  nunca se guarda una cita que el servidor no puede ver.
* **No se inventa P1.** Un experimento no exige beneficio neto medido para
  guardarse —es un sandbox—, pero tampoco lo afirma: el nivel se **deriva** de
  los runs citados y se publica con el experimento.
* **Sin backdating.** El sello temporal lo pone el servidor al insertar; el
  cliente no aporta ``savedAt``.
* **Sin Belief, sin Finalistas, sin ledger.** Guardar un experimento no mueve
  nada del universo TRADING.

@see docs/adr/019-dual-universes-lab-vs-trading.md
@see docs/adr/052-p1-gate-beneficio-neto.md
@see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §9 (R6)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from bolsa_application.instrument_strategy_tops import (
    TopProvenanceError,
    verify_top_provenance,
)
from bolsa_application.research_evidence import evidence_weight_for_level
from bolsa_domain.entities.research_evidence import EvidenceLevel, ResearchEvidence
from bolsa_domain.repositories.backtest_repository import BacktestRepository

DIA_D_EXPERIMENT_TOP_ENGINE = "dia-d-experiment-top-v1"
DIA_D_EXPERIMENT_TOP_SOURCE = "dia_d_experiment_top"
MATH_VERSION_DIA_D_EXPERIMENT_TOP_V0 = "dia_d_experiment_top_v0"
DIA_D_EXPERIMENT_TOP_SCHEMA_VERSION = "dia_d_experiment_top_v1"

_MAX_SLOTS = 3

_EXPERIMENT_NOTE = (
    "Experimento DÍA D as-of: sandbox del LAB. No es el TOP operativo (F-hoy), "
    "no escribe Finalistas ni el ledger DEMO."
)


class DiaDExperimentTopRejected(ValueError):
    """El experimento no puede guardarse tal y como llegó (400/422 en la ruta)."""


class _EvidenceRepo(Protocol):
    async def insert_evidence(
        self,
        *,
        instrument_id: str,
        level: str,
        source: str,
        evidence_weight: float,
        summary: dict[str, Any],
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        edge_report_id: str | None = None,
        math_version: str | None = None,
        evidence_id: str | None = None,
    ) -> ResearchEvidence: ...

    async def list_evidence(
        self,
        *,
        instrument_id: str | None = None,
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        level: str | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchEvidence], int]: ...


@dataclass(frozen=True, slots=True)
class DiaDExperimentTopRecord:
    """Experimento vigente tal y como lo publica la API (nunca inferido)."""

    id: str
    instrument_id: str
    timeframe: str
    as_of_dia_d: str
    saved_at: str
    level: str
    slots: tuple[dict[str, Any], ...]
    symbol: str | None = None
    coach_headline: str | None = None
    production_top1_at_save: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None

    @property
    def top1(self) -> dict[str, Any] | None:
        ranked = sorted(self.slots, key=lambda slot: int(slot.get("rank") or 0))
        return ranked[0] if ranked else None


def _parse_as_of(raw: str) -> date:
    try:
        return date.fromisoformat(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise DiaDExperimentTopRejected("asOfDiaD debe ser una fecha ISO (YYYY-MM-DD)") from exc


def validate_as_of_dia_d(raw: str, *, today: date | None = None) -> str:
    """D es una fecha **pasada**: un experimento no puede mirar al futuro."""
    parsed = _parse_as_of(raw)
    reference = today or datetime.now(UTC).date()
    if parsed > reference:
        raise DiaDExperimentTopRejected(
            "asOfDiaD no puede ser futura: el experimento es as-of de un día ya cerrado"
        )
    return parsed.isoformat()


def _normalise_slots(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 1 <= len(slots) <= _MAX_SLOTS:
        raise DiaDExperimentTopRejected(f"slots debe tener entre 1 y {_MAX_SLOTS} entradas")
    ranked = sorted(slots, key=lambda slot: int(slot.get("rank") or 0))
    ranks = [int(slot.get("rank") or 0) for slot in ranked]
    if ranks != list(range(1, len(ranked) + 1)):
        raise DiaDExperimentTopRejected("ranks deben ser 1..N consecutivos")
    for slot in ranked:
        label = slot.get("label")
        if not (isinstance(label, str) and label.strip()):
            raise DiaDExperimentTopRejected("cada slot declara label")
    return ranked


def _experiment_level(provenance_slots: list[dict[str, Any]]) -> EvidenceLevel:
    """C si TODOS los slots citan un run verificado; D si alguno es narrativa."""
    if provenance_slots and all(slot.get("runId") for slot in provenance_slots):
        return "C"
    return "D"


def build_dia_d_experiment_summary(
    *,
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Cuerpo durable del experimento (lo que se puede auditar después)."""
    summary: dict[str, Any] = {
        "kind": "dia_d_experiment_top",
        "schemaVersion": DIA_D_EXPERIMENT_TOP_SCHEMA_VERSION,
        "engine": DIA_D_EXPERIMENT_TOP_ENGINE,
        "sandbox": True,
        "timeframe": payload["timeframe"],
        "asOfDiaD": payload["asOfDiaD"],
        "slots": payload["slots"],
        "provenance": provenance,
        "note": _EXPERIMENT_NOTE,
    }
    symbol = payload.get("symbol")
    if isinstance(symbol, str) and symbol.strip():
        summary["symbol"] = symbol.strip()
    headline = payload.get("coachHeadline")
    if isinstance(headline, str) and headline.strip():
        summary["coachHeadline"] = headline.strip()
    production = payload.get("productionTop1AtSave")
    if isinstance(production, dict):
        summary["productionTop1AtSave"] = production
    return summary


class SaveDiaDExperimentTop:
    """Guarda (append-only) el TOP experimento as-of D y devuelve el vigente."""

    def __init__(
        self,
        evidence: _EvidenceRepo | None,
        *,
        backtests: BacktestRepository | None = None,
    ) -> None:
        self._evidence = evidence
        self._backtests = backtests

    async def execute(
        self,
        payload: dict[str, Any],
        *,
        today: date | None = None,
    ) -> DiaDExperimentTopRecord:
        if self._evidence is None:
            raise DiaDExperimentTopRejected(
                "sin almacén de evidencia no se puede guardar el experimento"
            )
        instrument_id = str(payload.get("instrumentId") or "").strip()
        if not instrument_id:
            raise DiaDExperimentTopRejected("instrumentId es obligatorio")
        timeframe = str(payload.get("timeframe") or "").strip()
        if not timeframe:
            raise DiaDExperimentTopRejected("timeframe es obligatorio")
        as_of = validate_as_of_dia_d(str(payload.get("asOfDiaD") or ""), today=today)
        slots = _normalise_slots(list(payload.get("slots") or []))

        # La procedencia la deriva el servidor; el cliente no la declara.
        provenance = await verify_top_provenance(
            instrument_id=instrument_id,
            slots=slots,
            backtests=self._backtests,
        )
        provenance_payload = {
            "evidenceLevel": provenance.evidence_level,
            "slots": [
                {
                    "rank": slot.rank,
                    "runId": slot.run_id,
                    "p1Status": slot.p1_status,
                    "reason": slot.reason,
                }
                for slot in provenance.slots
            ],
        }
        level = _experiment_level(provenance_payload["slots"])
        summary = build_dia_d_experiment_summary(
            payload={**payload, "timeframe": timeframe, "asOfDiaD": as_of, "slots": slots},
            provenance=provenance_payload,
        )
        evidence = await self._evidence.insert_evidence(
            instrument_id=instrument_id,
            level=level,
            source=DIA_D_EXPERIMENT_TOP_SOURCE,
            evidence_weight=evidence_weight_for_level(level),
            summary=summary,
            math_version=MATH_VERSION_DIA_D_EXPERIMENT_TOP_V0,
        )
        return _record_from_evidence(evidence)


class GetDiaDExperimentTop:
    """Experimento vigente para ``(instrumento, timeframe, D)`` o ``None``.

    El hueco se declara: ``None`` significa «no hay experimento guardado», nunca
    un objeto vacío ni un cero inventado.
    """

    def __init__(self, evidence: _EvidenceRepo | None) -> None:
        self._evidence = evidence

    async def execute(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        as_of_dia_d: str,
    ) -> DiaDExperimentTopRecord | None:
        if self._evidence is None:
            return None
        iid = str(instrument_id or "").strip()
        tf = str(timeframe or "").strip() or "1d"
        if not iid:
            return None
        try:
            wanted_day = _parse_as_of(as_of_dia_d).isoformat()
        except DiaDExperimentTopRejected:
            return None

        rows, _ = await self._evidence.list_evidence(
            instrument_id=iid,
            source=DIA_D_EXPERIMENT_TOP_SOURCE,
            limit=200,
            offset=0,
        )
        for row in rows:  # ya viene ordenado por created_at desc
            summary = row.summary if isinstance(row.summary, dict) else {}
            if summary.get("kind") != "dia_d_experiment_top":
                continue
            if str(summary.get("timeframe") or "") != tf:
                continue
            if str(summary.get("asOfDiaD") or "") != wanted_day:
                continue
            return _record_from_evidence(row)
        return None


def _record_from_evidence(evidence: ResearchEvidence) -> DiaDExperimentTopRecord:
    summary = evidence.summary if isinstance(evidence.summary, dict) else {}
    raw_slots = summary.get("slots")
    slots: list[dict[str, Any]] = []
    if isinstance(raw_slots, list):
        slots = [slot for slot in raw_slots if isinstance(slot, dict)]
    provenance = summary.get("provenance")
    production = summary.get("productionTop1AtSave")
    symbol = summary.get("symbol")
    headline = summary.get("coachHeadline")
    return DiaDExperimentTopRecord(
        id=evidence.id,
        instrument_id=evidence.instrument_id,
        timeframe=str(summary.get("timeframe") or ""),
        as_of_dia_d=str(summary.get("asOfDiaD") or ""),
        saved_at=evidence.created_at,
        level=evidence.level,
        slots=tuple(sorted(slots, key=lambda slot: int(slot.get("rank") or 0))),
        symbol=symbol if isinstance(symbol, str) else None,
        coach_headline=headline if isinstance(headline, str) else None,
        production_top1_at_save=production if isinstance(production, dict) else None,
        provenance=provenance if isinstance(provenance, dict) else None,
    )


__all__ = [
    "DIA_D_EXPERIMENT_TOP_ENGINE",
    "DIA_D_EXPERIMENT_TOP_SCHEMA_VERSION",
    "DIA_D_EXPERIMENT_TOP_SOURCE",
    "MATH_VERSION_DIA_D_EXPERIMENT_TOP_V0",
    "DiaDExperimentTopRecord",
    "DiaDExperimentTopRejected",
    "GetDiaDExperimentTop",
    "SaveDiaDExperimentTop",
    "TopProvenanceError",
    "build_dia_d_experiment_summary",
    "validate_as_of_dia_d",
]
