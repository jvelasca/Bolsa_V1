"""Validación gobernada ``AdaptationVerdictV1`` — LAB y as-run **independientes** (ADR-049).

Dos métodos, dos veredictos:

* **LAB** mide el experimento (retorno neto, drawdown, ventanas positivas, exceso vs compra,
  coste, muestra y corrección por pruebas múltiples).
* **DÍA-D as-run** mide la reproducción histórica de la operativa real y exige que el
  **método** esté certificado (``dia_d_certification``).

No se mezclan: un LAB favorable no mejora el veredicto as-run ni al revés. La activación
exige **los dos** en verde y, aun así, solo habilita *pedir* aprobación humana. Ningún PASE es
automático: ``NOT_EVALUATED`` nunca cuenta como ``PASS``; sin coste declarado no hay veredicto;
y si la huella de los umbrales pre-registrados no coincide con la declarada, se rechaza.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_application.baseline_arms import BASELINE_THRESHOLDS
from bolsa_application.dia_d_as_run import (
    ARM_AS_RUN,
    ARM_CANDIDATE,
    DEFAULT_MIN_COHORT_SAMPLES,
)
from bolsa_application.dia_d_certification import (
    VERDICT_CERTIFIED,
    VERDICT_INSUFFICIENT,
    DiaDCohortCertificationV1,
    certify_cohort,
)

__all__ = [
    "GATE_FAIL",
    "GATE_NOT_EVALUATED",
    "GATE_PASS",
    "SIDE_LAB",
    "SIDE_AS_RUN",
    "VERDICT_REJECTED",
    "VERDICT_REQUIRES_HUMAN",
    "AdaptationVerdictV1",
    "GateResult",
    "GateSideVerdict",
    "preregistration_hash",
    "validate_adaptation_proposal",
    "validate_as_run_gates",
    "validate_lab_gates",
]

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_NOT_EVALUATED = "NOT_EVALUATED"

SIDE_LAB = "lab"
SIDE_AS_RUN = "as_run"

VERDICT_REQUIRES_HUMAN = "requires_human_approval"
VERDICT_REJECTED = "rejected"

_METRIC_GATES: tuple[tuple[str, str, str], ...] = (
    ("minNetReturnPct", "netReturnPct", "min"),
    ("maxDrawdownPct", "maxDrawdownPct", "max"),
    ("minPositiveWindowPct", "positiveWindowPct", "min"),
    ("minExcessVsBuyHoldPct", "excessVsBuyHoldPct", "min"),
    ("minRoundTripCostBps", "roundTripCostBps", "min"),
)


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def preregistration_hash(thresholds: Mapping[str, Any] | None = None) -> str:
    """Huella de los umbrales efectivos: los parciales se completan con la línea base."""
    limits = {**BASELINE_THRESHOLDS, **dict(thresholds or {})}
    return _short_hash(limits)


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    status: str
    value: float | None = None
    threshold: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class GateSideVerdict:
    """Veredicto de UN método. Tiene su propio hash: no se puede confundir con el otro."""

    side: str
    status: str
    gates: tuple[GateResult, ...]
    hash: str
    reasons: tuple[str, ...]

    @property
    def measured(self) -> bool:
        return all(gate.status != GATE_NOT_EVALUATED for gate in self.gates)

    @property
    def passed(self) -> bool:
        return self.status == GATE_PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "status": self.status,
            "gates": [gate.to_dict() for gate in self.gates],
            "hash": self.hash,
            "measured": self.measured,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class AdaptationVerdictV1:
    proposal_id: str
    candidate_id: str | None
    preregistration_hash: str
    lab: GateSideVerdict
    as_run: GateSideVerdict
    gates: tuple[GateResult, ...]
    arms: tuple[dict[str, Any], ...]
    verdict: str
    reasons: tuple[str, ...]
    certification: DiaDCohortCertificationV1 | None = None

    @property
    def measured(self) -> bool:
        return all(gate.status != GATE_NOT_EVALUATED for gate in self.gates)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "version": "AdaptationVerdictV1",
            "proposalId": self.proposal_id,
            "candidateId": self.candidate_id,
            "preregistrationHash": self.preregistration_hash,
            "lab": self.lab.to_dict(),
            "asRun": self.as_run.to_dict(),
            "gates": [gate.to_dict() for gate in self.gates],
            "arms": [dict(arm) for arm in self.arms],
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "measured": self.measured,
            "certification": None if self.certification is None else self.certification.to_dict(),
        }
        payload["hash"] = _short_hash(payload)
        return payload


def _side_status(gates: Sequence[GateResult]) -> str:
    if any(gate.status == GATE_FAIL for gate in gates):
        return GATE_FAIL
    if any(gate.status == GATE_NOT_EVALUATED for gate in gates):
        return GATE_NOT_EVALUATED
    return GATE_PASS


def _side_reasons(gates: Sequence[GateResult]) -> tuple[str, ...]:
    reasons: list[str] = []
    for gate in gates:
        if gate.status == GATE_FAIL:
            reasons.append(f"gate_fail:{gate.name}")
        elif gate.status == GATE_NOT_EVALUATED:
            reasons.append(f"gate_not_evaluated:{gate.name}")
    return tuple(dict.fromkeys(reasons))


def _metric_gate(
    name: str, field_name: str, direction: str, lab: Mapping[str, Any], threshold: float
) -> GateResult:
    if lab.get("measured") is not True:
        return GateResult(
            name=name,
            status=GATE_NOT_EVALUATED,
            threshold=threshold,
            reason="lab_not_measured",
        )
    value = _finite(lab.get(field_name))
    if value is None:
        return GateResult(
            name=name,
            status=GATE_NOT_EVALUATED,
            threshold=threshold,
            reason=f"{field_name}_not_measured",
        )
    passed = value >= threshold if direction == "min" else value <= threshold
    return GateResult(
        name=name,
        status=GATE_PASS if passed else GATE_FAIL,
        value=value,
        threshold=threshold,
        reason=None if passed else f"{field_name}_{'below' if direction == 'min' else 'above'}_threshold",
    )


def _as_run_summary(artifacts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Medias de los brazos medidos; los no medidos se declaran, no se rellenan con 0."""
    totals: dict[str, list[float]] = {}
    gaps: list[str] = []
    for artifact in artifacts or ():
        arms = artifact.get("arms")
        if not isinstance(arms, list):
            gaps.append("artifact_without_arms")
            continue
        for arm in arms:
            if not isinstance(arm, Mapping) or arm.get("measured") is not True:
                continue
            value = _finite(arm.get("realizedR"))
            if value is None:
                continue
            totals.setdefault(str(arm.get("arm") or ""), []).append(value)
    means = {name: sum(values) / len(values) for name, values in totals.items()}
    return {"means": means, "samples": len(artifacts or ()), "gaps": gaps}


def _artifacts_hash(
    artifacts: Sequence[Mapping[str, Any]], *, min_samples: int
) -> str:
    fingerprints = [
        str(artifact.get("hash") or _short_hash(artifact))
        for artifact in artifacts or ()
        if isinstance(artifact, Mapping)
    ]
    return _short_hash({"artifacts": fingerprints, "minSamples": int(min_samples)})


def validate_lab_gates(
    *,
    lab: Mapping[str, Any],
    thresholds: Mapping[str, float] | None = None,
    declared_preregistration_hash: str | None = None,
    min_samples: int = DEFAULT_MIN_COHORT_SAMPLES,
) -> GateSideVerdict:
    """Veredicto del método LAB, sin mirar el as-run."""
    limits = {**BASELINE_THRESHOLDS, **dict(thresholds or {})}
    prereg = preregistration_hash(limits)

    if declared_preregistration_hash and declared_preregistration_hash != prereg:
        gates: tuple[GateResult, ...] = (
            GateResult(
                name="preregistration",
                status=GATE_FAIL,
                reason="preregistration_mismatch",
            ),
        )
        return GateSideVerdict(
            side=SIDE_LAB,
            status=GATE_FAIL,
            gates=gates,
            hash=_short_hash({"side": SIDE_LAB, "preregistration": prereg, "gates": [g.to_dict() for g in gates]}),
            reasons=("preregistration_mismatch",),
        )

    gates_list: list[GateResult] = [
        GateResult(name="preregistration", status=GATE_PASS)
    ]
    for name, field_name, direction in _METRIC_GATES:
        gates_list.append(_metric_gate(name, field_name, direction, lab, float(limits[name])))

    samples = _finite(lab.get("samples"))
    required = max(1, int(min_samples))
    if samples is None:
        gates_list.append(
            GateResult(
                name="min_samples",
                status=GATE_NOT_EVALUATED,
                threshold=float(required),
                reason="samples_not_measured",
            )
        )
    else:
        gates_list.append(
            GateResult(
                name="min_samples",
                status=GATE_PASS if samples >= required else GATE_FAIL,
                value=samples,
                threshold=float(required),
                reason=None if samples >= required else "insufficient_sample",
            )
        )

    corrected = lab.get("multipleTestingCorrected")
    if corrected is None:
        gates_list.append(
            GateResult(
                name="multiple_testing",
                status=GATE_NOT_EVALUATED,
                reason="correction_not_declared",
            )
        )
    else:
        gates_list.append(
            GateResult(
                name="multiple_testing",
                status=GATE_PASS if corrected is True else GATE_FAIL,
                reason=None if corrected is True else "correction_missing",
            )
        )

    gates = tuple(gates_list)
    return GateSideVerdict(
        side=SIDE_LAB,
        status=_side_status(gates),
        gates=gates,
        hash=_short_hash(
            {
                "side": SIDE_LAB,
                "preregistration": prereg,
                "gates": [gate.to_dict() for gate in gates],
            }
        ),
        reasons=_side_reasons(gates),
    )


def validate_as_run_gates(
    *,
    as_run_artifacts: Sequence[Mapping[str, Any]] = (),
    min_samples: int = DEFAULT_MIN_COHORT_SAMPLES,
) -> tuple[GateSideVerdict, DiaDCohortCertificationV1]:
    """Veredicto del método DÍA-D as-run, con certificación del método como primer gate.

    El LAB no entra aquí: la certificación y la comparación candidata-vs-as-run se calculan
    solo con los artefactos as-run.
    """
    required = max(1, int(min_samples))
    artifacts = [artifact for artifact in as_run_artifacts or () if isinstance(artifact, Mapping)]
    certification = certify_cohort(artifacts, min_samples=required)
    gates: list[GateResult] = []

    if certification.verdict == VERDICT_INSUFFICIENT:
        gates.append(
            GateResult(
                name="as_run_certification",
                status=GATE_NOT_EVALUATED,
                threshold=float(required),
                value=float(certification.samples),
                reason="insufficient_as_run_sample",
            )
        )
    elif certification.verdict != VERDICT_CERTIFIED:
        gates.append(
            GateResult(
                name="as_run_certification",
                status=GATE_FAIL,
                value=float(certification.samples),
                threshold=float(required),
                reason="as_run_not_certified",
            )
        )
    else:
        gates.append(
            GateResult(
                name="as_run_certification",
                status=GATE_PASS,
                value=float(certification.samples),
                threshold=float(required),
            )
        )

    summary = _as_run_summary(artifacts)
    candidate_mean = summary["means"].get(ARM_CANDIDATE)
    as_run_mean = summary["means"].get(ARM_AS_RUN)

    if summary["samples"] < required:
        gates.append(
            GateResult(
                name="as_run_cohort",
                status=GATE_NOT_EVALUATED,
                value=float(summary["samples"]),
                threshold=float(required),
                reason="insufficient_as_run_sample",
            )
        )
    elif candidate_mean is None:
        gates.append(
            GateResult(
                name="as_run_cohort",
                status=GATE_NOT_EVALUATED,
                reason="candidate_arm_not_measured",
            )
        )
    elif as_run_mean is None:
        gates.append(
            GateResult(
                name="as_run_cohort",
                status=GATE_NOT_EVALUATED,
                reason="as_run_arm_not_measured",
            )
        )
    else:
        improvement = candidate_mean - as_run_mean
        passed = improvement > 0
        gates.append(
            GateResult(
                name="as_run_cohort",
                status=GATE_PASS if passed else GATE_FAIL,
                value=round(improvement, 6),
                threshold=0.0,
                reason=None if passed else "candidate_does_not_beat_as_run",
            )
        )

    return (
        GateSideVerdict(
            side=SIDE_AS_RUN,
            status=_side_status(gates),
            gates=tuple(gates),
            hash=_short_hash(
                {
                    "side": SIDE_AS_RUN,
                    "artifacts": _artifacts_hash(artifacts, min_samples=required),
                    "certification": certification.to_dict()["hash"],
                    "gates": [gate.to_dict() for gate in gates],
                }
            ),
            reasons=_side_reasons(gates),
        ),
        certification,
    )


def _arm_rows(summary: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    means = summary.get("means") or {}
    return tuple(
        {"arm": name, "meanR": round(value, 6), "measured": True}
        for name, value in sorted(means.items())
    )


def validate_adaptation_proposal(
    *,
    proposal_id: str,
    candidate_id: str | None,
    lab: Mapping[str, Any],
    as_run_artifacts: Sequence[Mapping[str, Any]] = (),
    thresholds: Mapping[str, float] | None = None,
    declared_preregistration_hash: str | None = None,
    min_samples: int = DEFAULT_MIN_COHORT_SAMPLES,
) -> AdaptationVerdictV1:
    """Compone dos veredictos independientes; ninguno sustituye al otro."""
    limits = {**BASELINE_THRESHOLDS, **dict(thresholds or {})}
    prereg = preregistration_hash(limits)
    artifacts = [artifact for artifact in as_run_artifacts or () if isinstance(artifact, Mapping)]

    lab_side = validate_lab_gates(
        lab=lab,
        thresholds=limits,
        declared_preregistration_hash=declared_preregistration_hash,
        min_samples=min_samples,
    )

    # Umbrales pre-registrados que no coinciden: se rechaza sin medir nada más.
    if lab_side.gates and lab_side.gates[0].reason == "preregistration_mismatch":
        as_run_side = GateSideVerdict(
            side=SIDE_AS_RUN,
            status=GATE_NOT_EVALUATED,
            gates=(),
            hash=_short_hash(
                {
                    "side": SIDE_AS_RUN,
                    "artifacts": _artifacts_hash(artifacts, min_samples=int(min_samples)),
                }
            ),
            reasons=(),
        )
        return AdaptationVerdictV1(
            proposal_id=proposal_id,
            candidate_id=candidate_id,
            preregistration_hash=prereg,
            lab=lab_side,
            as_run=as_run_side,
            gates=lab_side.gates,
            arms=(),
            verdict=VERDICT_REJECTED,
            reasons=lab_side.reasons,
            certification=None,
        )

    as_run_side, certification = validate_as_run_gates(
        as_run_artifacts=artifacts,
        min_samples=min_samples,
    )

    gates = lab_side.gates + as_run_side.gates
    summary = _as_run_summary(artifacts)
    reasons: list[str] = []
    reasons.extend(f"lab:{reason}" for reason in lab_side.reasons)
    reasons.extend(f"as_run:{reason}" for reason in as_run_side.reasons)
    reasons.extend(str(gap) for gap in summary["gaps"])

    if lab_side.status == GATE_PASS and as_run_side.status == GATE_PASS:
        # Todo medido y en verde todavía NO autoriza nada: solo habilita la decisión humana.
        verdict = VERDICT_REQUIRES_HUMAN
        reasons.extend(("human_approval_required", "activation_forbidden"))
    else:
        verdict = VERDICT_REJECTED

    return AdaptationVerdictV1(
        proposal_id=proposal_id,
        candidate_id=candidate_id,
        preregistration_hash=prereg,
        lab=lab_side,
        as_run=as_run_side,
        gates=gates,
        arms=_arm_rows(summary),
        verdict=verdict,
        reasons=tuple(dict.fromkeys(reasons)),
        certification=certification,
    )
