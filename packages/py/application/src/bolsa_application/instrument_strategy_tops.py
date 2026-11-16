"""Use cases: TOP-3 estrategias AT por instrumento."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bolsa_application.strategy_lab_phase import LabThresholds, p1_gate_from_metrics
from bolsa_domain.entities.strategy_lifecycle import GateStatus
from bolsa_domain.repositories.backtest_repository import BacktestRepository
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    InstrumentStrategyTopRecord,
    SqlAlchemyInstrumentStrategyTopRepository,
)


def assert_lab_validated_slots_have_run_id(
    *,
    evidence_level: str,
    status: str,
    slots: list[dict[str, Any]],
) -> None:
    """Reject lab_validated / active TOP without runId (Camino A Checklist)."""
    if evidence_level != "lab_validated" and status != "active":
        return
    missing: list[Any] = []
    for slot in slots:
        run_id = slot.get("runId") or slot.get("run_id")
        if not (isinstance(run_id, str) and run_id.strip()):
            missing.append(slot.get("rank", slot.get("label", "?")))
    if missing:
        raise ValueError(
            "lab_validated/active TOP requires runId on every slot; "
            f"missing {missing}"
        )


class TopProvenanceError(ValueError):
    """El TOP cita evidencia que el servidor no puede verificar (R3)."""


@dataclass(frozen=True, slots=True)
class SlotProvenance:
    rank: int
    run_id: str | None
    p1_status: str
    reason: str | None
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.p1_status == GateStatus.PASS.value


@dataclass(frozen=True, slots=True)
class TopProvenance:
    """Procedencia DERIVADA de los runs citados (nunca la declara el cliente)."""

    evidence_level: str
    slots: tuple[SlotProvenance, ...]

    @property
    def verified(self) -> bool:
        return bool(self.slots) and all(slot.verified for slot in self.slots)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(
            f"slot {slot.rank}: {slot.reason}" for slot in self.slots if slot.reason
        )


def _run_net_metrics(run: Any) -> dict[str, Any] | None:
    """``manifest.outputs.isMetrics`` del run — el payload que midió P1."""
    manifest = getattr(run, "manifest", None)
    if not isinstance(manifest, dict):
        return None
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        return None
    metrics = outputs.get("isMetrics")
    return metrics if isinstance(metrics, dict) else None


async def verify_top_provenance(
    *,
    instrument_id: str,
    slots: list[dict[str, Any]],
    backtests: BacktestRepository | None,
    thresholds: LabThresholds | None = None,
) -> TopProvenance:
    """Verifica en SERVIDOR que cada slot cita un run real del instrumento con P1 medido.

    Fail-closed: sin repositorio de runs no se puede verificar nada, así que ninguna
    afirmación ``lab_validated`` sobrevive. Un slot sin ``runId`` no es un error (es un
    candidato in-sample), pero tampoco es evidencia.
    """
    th = thresholds or LabThresholds()
    resolved: list[SlotProvenance] = []

    for raw in slots:
        rank = int(raw.get("rank") or len(resolved) + 1)
        run_id_raw = raw.get("runId") or raw.get("run_id")
        run_id = run_id_raw.strip() if isinstance(run_id_raw, str) else ""
        if not run_id:
            resolved.append(
                SlotProvenance(
                    rank=rank,
                    run_id=None,
                    p1_status=GateStatus.NOT_EVALUATED.value,
                    reason="sin_run_id",
                )
            )
            continue

        if backtests is None:
            resolved.append(
                SlotProvenance(
                    rank=rank,
                    run_id=run_id,
                    p1_status=GateStatus.NOT_EVALUATED.value,
                    reason="procedencia_no_verificable",
                )
            )
            continue

        run = await backtests.get_run(run_id)
        if run is None:
            raise TopProvenanceError(
                f"slot {rank}: el run {run_id} no existe en backtest_runs"
            )
        if str(getattr(run, "instrument_id", "") or "") != instrument_id:
            raise TopProvenanceError(
                f"slot {rank}: el run {run_id} no pertenece al instrumento {instrument_id}"
            )

        metrics = _run_net_metrics(run)
        gate = p1_gate_from_metrics(metrics, thresholds=th)
        resolved.append(
            SlotProvenance(
                rank=rank,
                run_id=run_id,
                p1_status=gate.status.value,
                reason=None if gate.status is GateStatus.PASS else gate.detail,
                metrics=dict(gate.metrics or {}),
            )
        )

    provenance = TopProvenance(
        evidence_level="lab_validated",
        slots=tuple(resolved),
    )
    # ``lab_validated`` solo si TODOS los slots demuestran P1; si no, es in-sample.
    level = "lab_validated" if provenance.verified else "in_sample_only"
    return TopProvenance(evidence_level=level, slots=provenance.slots)



class GetInstrumentStrategyTop:
    """Obtiene Instrument Strategy Top."""
    def __init__(self, repo: SqlAlchemyInstrumentStrategyTopRepository) -> None:
        self._repo = repo

    async def execute(
        self, instrument_id: str, timeframe: str = "1d"
    ) -> InstrumentStrategyTopRecord | None:
        return await self._repo.get(instrument_id, timeframe)


class UpsertInstrumentStrategyTop:
    """Crea o actualiza Instrument Strategy Top.

    R3 (auditoría LAB 2026-11-16): la procedencia **se deriva en servidor** de los runs
    citados. El cliente ya no decide ``evidenceLevel``: si afirma ``lab_validated`` sin que
    P1 esté en PASS en todos los slots, el upsert falla con ``TopProvenanceError`` (422 en
    la ruta) en vez de guardar un 200 con evidencia inventada.
    """

    def __init__(
        self,
        repo: SqlAlchemyInstrumentStrategyTopRepository,
        *,
        backtests: BacktestRepository | None = None,
        thresholds: LabThresholds | None = None,
    ) -> None:
        self._repo = repo
        self._backtests = backtests
        self._thresholds = thresholds

    async def execute(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        slots: list[dict[str, Any]],
        symbol: str | None = None,
        period_label: str | None = None,
        status: str = "semifinal",
        evidence_level: str = "in_sample_only",
        coach_headline: str | None = None,
        coach_facts: dict[str, Any] | None = None,
    ) -> InstrumentStrategyTopRecord:
        assert_lab_validated_slots_have_run_id(
            evidence_level=evidence_level,
            status=status,
            slots=slots,
        )
        provenance = await verify_top_provenance(
            instrument_id=instrument_id,
            slots=slots,
            backtests=self._backtests,
            thresholds=self._thresholds,
        )
        derived_level = provenance.evidence_level

        if status == "active" and derived_level != "lab_validated":
            detail = "; ".join(provenance.reasons) or "procedencia insuficiente"
            raise TopProvenanceError(
                f"un TOP active exige beneficio neto medido (P1) en los tres slots: {detail}"
            )
        if evidence_level == "lab_validated" and derived_level != "lab_validated":
            detail = "; ".join(provenance.reasons) or "procedencia insuficiente"
            raise TopProvenanceError(
                "lab_validated exige P1 en PASS en todos los slots con run verificado: "
                f"{detail}"
            )

        return await self._repo.upsert(
            instrument_id=instrument_id,
            timeframe=timeframe,
            slots=slots,
            symbol=symbol,
            period_label=period_label,
            status=status,
            evidence_level=derived_level,
            coach_headline=coach_headline,
            coach_facts=coach_facts,
        )


class DeleteInstrumentStrategyTop:
    """Elimina Instrument Strategy Top."""
    def __init__(self, repo: SqlAlchemyInstrumentStrategyTopRepository) -> None:
        self._repo = repo

    async def execute(self, instrument_id: str, timeframe: str = "1d") -> bool:
        return await self._repo.delete(instrument_id, timeframe)
