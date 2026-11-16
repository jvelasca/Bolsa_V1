"""Gates y veredicto **advisory** de la verificación periódica de estrategia (ADR-050).

Qué decide
----------
Con N épocas no solapadas ya medidas, este módulo responde una sola pregunta:

    ¿La estrategia activa sigue siendo defendible frente a sus alternativas y frente a la
    candidata vigente, con evidencia independiente y fresca?

Y responde con un veredicto **descriptivo**, nunca con una orden:

* ``continue`` — todo pasa y la operativa no queda peor que el mejor brazo.
* ``watch`` — la muestra es válida pero hay señales mixtas (peor que un brazo, salud en
  vigilancia o candidata mejor sin ventaja concluyente).
* ``relab`` — la operativa real pierde de forma sostenida contra un brazo contrafactual:
  procede re-ejecutar el laboratorio de selección.
* ``promote_requires_human`` — la candidata point-in-time supera a la operativa en todas las
  épocas: se propone, no se activa.
* ``insufficient_sample`` — falta muestra independiente (incluye ventanas solapadas).
* ``inconclusive_version_change`` — la ventana cruza un cambio de estrategia/mandato.

Invariantes
-----------
* ``NOT_EVALUATED`` **nunca** cuenta como PASS.
* ``activationAllowed`` es siempre ``False``: puede pedir re-LAB o proponer una mutación,
  nunca escribir la estrategia activa.
* El bootstrap es determinista (semilla fija): dos ejecuciones dan el mismo intervalo.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from bolsa_application.dia_d_as_run import (
    ARM_AS_RUN,
    ARM_CASH,
    ARM_MARKET_BH,
    QUALITY_CONSISTENT,
    QUALITY_INCONSISTENT,
)
from bolsa_application.dia_d_certification import certify_artifact
from bolsa_application.strategy_verification_cadence import (
    VerificationEpoch,
    independent_sample_gate,
)
from bolsa_application.strategy_verification_profile import (
    StrategyVerificationProfileV1,
)

__all__ = [
    "GATE_FAIL",
    "GATE_NOT_EVALUATED",
    "GATE_PASS",
    "VERDICT_CONTINUE",
    "VERDICT_INCONCLUSIVE_VERSION",
    "VERDICT_INSUFFICIENT_SAMPLE",
    "VERDICT_PROMOTE_REQUIRES_HUMAN",
    "VERDICT_RELAB",
    "VERDICT_WATCH",
    "EpochMeasurement",
    "VerificationVerdict",
    "artifact_measurement_hash",
    "epoch_measurement_from_artifact",
    "evaluate_verification",
    "measurement_hash",
]

GATE_PASS = "pass"
GATE_FAIL = "fail"
GATE_NOT_EVALUATED = "not_evaluated"

VERDICT_CONTINUE = "continue"
VERDICT_WATCH = "watch"
VERDICT_RELAB = "relab"
VERDICT_PROMOTE_REQUIRES_HUMAN = "promote_requires_human"
VERDICT_INSUFFICIENT_SAMPLE = "insufficient_sample"
VERDICT_INCONCLUSIVE_VERSION = "inconclusive_version_change"

#: Brazos que NO compiten como "mejor estrategia": ``cash`` es el control sin exposición y
#: ``market_bh`` no tiene R (benchmark de retorno). Compararse contra ellos sería tramposo en
#: ambas direcciones.
_NON_COMPETING_ARMS = frozenset({ARM_AS_RUN, ARM_CASH, ARM_MARKET_BH})

#: Semilla y remuestreos del bootstrap: determinismo antes que potencia.
_BOOTSTRAP_SEED = 20260101
_BOOTSTRAP_RESAMPLES = 2000

#: Claves volátiles que NO forman parte de la identidad de una medición.
_VOLATILE_KEYS = frozenset({"hash", "meta", "generatedAt", "generated_at", "createdAt"})


def measurement_hash(payload: Mapping[str, Any]) -> str:
    """Hash estable de una MEDICIÓN (sin timestamps ni metadatos de ejecución).

    El ``hash`` del artefacto incluye ``meta.generatedAt``, así que dos rejuegos idénticos
    producen hashes distintos. Esta huella se calcula sobre el contenido medido y sirve para
    demostrar que dos runs son la misma medición.
    """
    body = {key: value for key, value in payload.items() if key not in _VOLATILE_KEYS}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def artifact_measurement_hash(artifact: Mapping[str, Any]) -> str:
    """``measurement_hash`` de un artefacto as-run ya sellado."""
    return measurement_hash(artifact)


@dataclass(frozen=True, slots=True)
class EpochMeasurement:
    """Lo que una época aporta al veredicto (extraído de su artefacto as-run)."""

    epoch_id: str
    day: str
    to_day: str
    artifact_hash: str
    measured: bool
    certified: bool
    arms_r: Mapping[str, float | None]
    arms_return_pct: Mapping[str, float | None] = field(default_factory=dict)
    closed_cycles: int = 0
    operations: int = 0
    consistent_decisions: int = 0
    inconsistent_decisions: int = 0
    unrealized_r: float | None = None
    strategy_version: str | None = None
    mandate_version: str | None = None
    candidate_measured: bool = False
    candidate_return_pct: float | None = None
    candidate_gap: str | None = None
    certification_checks: Mapping[str, str] = field(default_factory=dict)

    @property
    def as_run_r(self) -> float | None:
        return self.arms_r.get(ARM_AS_RUN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "epochId": self.epoch_id,
            "day": self.day,
            "toDay": self.to_day,
            "artifactHash": self.artifact_hash,
            "measured": self.measured,
            "certified": self.certified,
            "armsR": {arm: value for arm, value in sorted(self.arms_r.items())},
            "armsReturnPct": {
                arm: value for arm, value in sorted(self.arms_return_pct.items())
            },
            "closedCycles": self.closed_cycles,
            "operations": self.operations,
            "consistentDecisions": self.consistent_decisions,
            "inconsistentDecisions": self.inconsistent_decisions,
            "unrealizedR": self.unrealized_r,
            "strategyVersion": self.strategy_version,
            "mandateVersion": self.mandate_version,
            "candidateMeasured": self.candidate_measured,
            "candidateReturnPct": self.candidate_return_pct,
            "candidateGap": self.candidate_gap,
            "certificationChecks": dict(self.certification_checks),
        }


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def epoch_measurement_from_artifact(
    artifact: Mapping[str, Any],
    *,
    epoch: VerificationEpoch,
) -> EpochMeasurement:
    """Extrae la medición de una época desde el artefacto as-run ya sellado.

    No re-mide: lee los agregados que el artefacto publica y el bloque de candidata. La
    certificación se recalcula con ``certify_artifact`` (es una función pura del sobre).
    """
    arms = artifact.get("arms") or ()
    arms_r: dict[str, float | None] = {}
    arms_return: dict[str, float | None] = {}
    ledger_rows: list[Mapping[str, Any]] = []
    closed = 0
    unrealized: float | None = None
    for arm in arms if isinstance(arms, (list, tuple)) else ():
        if not isinstance(arm, Mapping):
            continue
        name = str(arm.get("arm") or "")
        if not name:
            continue
        arms_r[name] = _as_float(arm.get("realizedR"))
        arms_return[name] = _as_float(arm.get("returnPct"))
        closed += int(arm.get("cycles") or 0)
        if name == ARM_AS_RUN:
            unrealized = _as_float(arm.get("unrealizedR"))
            for row in arm.get("ledger") or ():
                if isinstance(row, Mapping):
                    ledger_rows.append(row)

    audit = artifact.get("audit") if isinstance(artifact.get("audit"), Mapping) else {}
    versions = audit.get("versions") if isinstance(audit.get("versions"), Mapping) else {}
    candidate = (
        artifact.get("candidateForward")
        if isinstance(artifact.get("candidateForward"), Mapping)
        else None
    )
    certification = certify_artifact(artifact)
    checks = {
        str(check.name): str(check.status) for check in certification.checks
    }
    candidate_measured = bool(candidate and candidate.get("measured"))
    candidate_gap: str | None = None
    if candidate is not None and not candidate_measured:
        candidate_gap = str(candidate.get("reason") or "candidate_not_measured")
    return EpochMeasurement(
        epoch_id=epoch.epoch_id,
        day=epoch.day,
        to_day=epoch.to_day,
        artifact_hash=str(artifact.get("hash") or ""),
        measured=bool(artifact.get("measured")),
        certified=bool(certification.certified),
        arms_r=arms_r,
        arms_return_pct=arms_return,
        closed_cycles=closed,
        operations=len(ledger_rows),
        consistent_decisions=sum(
            1 for row in ledger_rows if row.get("decisionQuality") == QUALITY_CONSISTENT
        ),
        inconsistent_decisions=sum(
            1 for row in ledger_rows if row.get("decisionQuality") == QUALITY_INCONSISTENT
        ),
        unrealized_r=unrealized,
        strategy_version=(
            None if versions.get("strategy") is None else str(versions["strategy"])
        ),
        mandate_version=(
            None if versions.get("mandate") is None else str(versions["mandate"])
        ),
        candidate_measured=candidate_measured,
        candidate_return_pct=_as_float((candidate or {}).get("returnPct")),
        candidate_gap=candidate_gap,
        certification_checks=checks,
    )


def _mean(values: Iterable[float | None]) -> float | None:
    rows = [value for value in values if value is not None]
    if not rows:
        return None
    return sum(rows) / len(rows)


def _gate(name: str, status: str, reason: str | None = None, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"gate": name, "status": status, "reason": reason}
    payload.update(details)
    return payload


def _best_arm_by_epoch(
    epochs: Sequence[EpochMeasurement],
) -> tuple[str | None, list[float | None]]:
    """Mejor brazo por época (excluyendo as_run, cash y market_bh) y su R por época."""
    totals: dict[str, list[float]] = {}
    for epoch in epochs:
        for arm, value in epoch.arms_r.items():
            if arm in _NON_COMPETING_ARMS or value is None:
                continue
            totals.setdefault(arm, []).append(value)
    if not totals:
        return None, [None for _ in epochs]
    best_arm = max(sorted(totals), key=lambda arm: sum(totals[arm]) / len(totals[arm]))
    return best_arm, [epoch.arms_r.get(best_arm) for epoch in epochs]


def _bootstrap_low(differences: Sequence[float]) -> float | None:
    """Percentil 5 % de la media de las diferencias (bootstrap determinista)."""
    if len(differences) < 2:
        return None
    rng = random.Random(_BOOTSTRAP_SEED)
    size = len(differences)
    means: list[float] = []
    for _ in range(_BOOTSTRAP_RESAMPLES):
        sample = [differences[rng.randrange(size)] for _ in range(size)]
        means.append(sum(sample) / size)
    means.sort()
    return means[int(0.05 * (len(means) - 1))]


def _freshness_gate(
    epochs: Sequence[EpochMeasurement],
    *,
    today: str,
    max_age_days: float | None,
) -> dict[str, Any]:
    if not epochs:
        return _gate("freshness", GATE_NOT_EVALUATED, "no_epochs")
    try:
        last = date.fromisoformat(epochs[-1].to_day)
        reference = date.fromisoformat(str(today)[:10])
    except ValueError:
        return _gate("freshness", GATE_NOT_EVALUATED, "unreadable_dates")
    age = (reference - last).days
    if max_age_days is None:
        return _gate("freshness", GATE_PASS, None, ageDays=age, ttlDays=None)
    if age > float(max_age_days):
        return _gate("freshness", GATE_FAIL, f"stale_evidence:{age}>{max_age_days}", ageDays=age)
    return _gate("freshness", GATE_PASS, None, ageDays=age, ttlDays=float(max_age_days))


def _version_gate(epochs: Sequence[EpochMeasurement]) -> dict[str, Any]:
    strategies = sorted({str(epoch.strategy_version or "") for epoch in epochs})
    mandates = sorted({str(epoch.mandate_version or "") for epoch in epochs})
    if len(strategies) > 1 or len(mandates) > 1:
        return _gate(
            "version_integrity",
            GATE_FAIL,
            "version_change_in_window",
            strategyVersions=strategies,
            mandateVersions=mandates,
        )
    return _gate(
        "version_integrity",
        GATE_PASS,
        None,
        strategyVersions=strategies,
        mandateVersions=mandates,
    )


@dataclass(frozen=True, slots=True)
class VerificationVerdict:
    """Veredicto advisory completo, con sus gates y sus números."""

    verdict: str
    activation_allowed: bool
    profile_id: str
    profile_hash: str
    gates: tuple[Mapping[str, Any], ...]
    samples: int
    required_samples: int
    as_run_mean_r: float | None = None
    best_arm: str | None = None
    best_arm_mean_r: float | None = None
    mean_excess_r: float | None = None
    share_epochs_not_worse: float | None = None
    bootstrap_low: float | None = None
    candidate_mean_return_pct: float | None = None
    as_run_mean_return_pct: float | None = None
    epochs: tuple[Mapping[str, Any], ...] = ()
    reasons: tuple[str, ...] = ()
    limits: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "activationAllowed": False,
            "profileId": self.profile_id,
            "profileHash": self.profile_hash,
            "gates": [dict(gate) for gate in self.gates],
            "samples": self.samples,
            "requiredSamples": self.required_samples,
            "asRunMeanR": self.as_run_mean_r,
            "bestArm": self.best_arm,
            "bestArmMeanR": self.best_arm_mean_r,
            "meanExcessR": self.mean_excess_r,
            "shareEpochsNotWorse": self.share_epochs_not_worse,
            "bootstrapLow": self.bootstrap_low,
            "candidateMeanReturnPct": self.candidate_mean_return_pct,
            "asRunMeanReturnPct": self.as_run_mean_return_pct,
            "epochs": [dict(epoch) for epoch in self.epochs],
            "reasons": list(self.reasons),
            "limits": list(self.limits),
        }


def evaluate_verification(
    epochs: Sequence[EpochMeasurement],
    *,
    profile: StrategyVerificationProfileV1,
    today: str,
    health: Mapping[str, Any] | None = None,
) -> VerificationVerdict:
    """Compone los gates y emite el veredicto. ``NOT_EVALUATED`` nunca es PASS.

    ``health`` es el resultado ya calculado de ``evaluate_active_health`` (o su equivalente);
    si no se aporta, el gate de salud observada queda ``not_evaluated`` y el veredicto no
    puede pasar de ``watch``. La verificación no recalcula la salud del sistema operativo.
    """
    samples = [epoch for epoch in epochs if epoch.measured]
    sample_gate = independent_sample_gate(
        [
            VerificationEpoch(
                epoch_id=epoch.epoch_id,
                index=index,
                day=epoch.day,
                to_day=epoch.to_day,
                # Una época medida se comporta como cerrada: la apertura la declara el
                # planificador, no la lectura del artefacto.
                status="closed",
            )
            for index, epoch in enumerate(samples)
        ],
        required=profile.samples.min_cohort_samples,
    )
    gates: list[dict[str, Any]] = [
        _gate(
            "independent_sample",
            GATE_PASS if sample_gate["passed"] else GATE_FAIL,
            None if sample_gate["passed"] else str(sample_gate["reason"]),
            samples=sample_gate["samples"],
            required=sample_gate["required"],
        )
    ]

    method_bad = [epoch.epoch_id for epoch in samples if not epoch.certified]
    gates.append(
        _gate(
            "method_certified",
            GATE_FAIL if method_bad else GATE_PASS,
            None if not method_bad else "artifacts_not_certified",
            failures=method_bad,
        )
    )

    gates.append(_version_gate(samples))
    gates.append(
        _freshness_gate(
            samples,
            today=today,
            max_age_days=profile.thresholds.max_evidence_age_days,
        )
    )

    as_run_mean = _mean(epoch.as_run_r for epoch in samples)
    best_arm, best_values = _best_arm_by_epoch(samples)
    best_mean = _mean(best_values)
    differences = [
        epoch.as_run_r - best
        for epoch, best in zip(samples, best_values, strict=False)
        if epoch.as_run_r is not None and best is not None
    ]
    mean_excess = _mean(differences)
    share_not_worse = (
        sum(1 for value in differences if value >= 0.0) / len(differences)
        if differences
        else None
    )
    bootstrap_low = _bootstrap_low(differences)

    if best_arm is None:
        gates.append(_gate("as_run_vs_best_arm", GATE_NOT_EVALUATED, "no_comparison_arm"))
    else:
        thresholds = profile.thresholds
        passed = (
            mean_excess is not None
            and mean_excess >= float(thresholds.min_excess_mean_r)
            and share_not_worse is not None
            and share_not_worse >= float(thresholds.min_share_epochs_not_worse)
            and bootstrap_low is not None
            and bootstrap_low >= 0.0
        )
        gates.append(
            _gate(
                "as_run_vs_best_arm",
                GATE_PASS if passed else GATE_FAIL,
                None if passed else "as_run_not_better_than_best_arm",
                bestArm=best_arm,
                meanExcessR=mean_excess,
                shareEpochsNotWorse=share_not_worse,
                bootstrapLow=bootstrap_low,
            )
        )

    as_run_return = _mean(epoch.arms_return_pct.get(ARM_AS_RUN) for epoch in samples)
    candidate_values = [epoch.candidate_return_pct for epoch in samples]
    candidate_all_measured = bool(samples) and all(
        epoch.candidate_measured and value is not None
        for epoch, value in zip(samples, candidate_values, strict=False)
    )
    candidate_mean = _mean(candidate_values) if candidate_all_measured else None
    if not samples:
        gates.append(_gate("candidate_vs_as_run", GATE_NOT_EVALUATED, "no_samples"))
    elif not candidate_all_measured:
        gates.append(
            _gate(
                "candidate_vs_as_run",
                GATE_NOT_EVALUATED,
                "candidate_not_measured_in_all_epochs",
            )
        )
    elif candidate_mean is None or as_run_return is None:
        gates.append(_gate("candidate_vs_as_run", GATE_NOT_EVALUATED, "returns_unavailable"))
    else:
        candidate_wins = candidate_mean > as_run_return
        gates.append(
            _gate(
                "candidate_vs_as_run",
                GATE_PASS if candidate_wins else GATE_FAIL,
                None if candidate_wins else "candidate_not_better",
                candidateMeanReturnPct=candidate_mean,
                asRunMeanReturnPct=as_run_return,
            )
        )

    health_state = str((health or {}).get("state") or (health or {}).get("status") or "")
    if not health_state:
        gates.append(_gate("observed_health", GATE_NOT_EVALUATED, "health_not_provided"))
    elif health_state == "continue":
        gates.append(_gate("observed_health", GATE_PASS, None))
    else:
        gates.append(
            _gate("observed_health", GATE_FAIL, f"health_{health_state}")
        )

    verdict = _decide(
        gates=gates,
        sample_passed=bool(sample_gate["passed"]),
        mean_excess=mean_excess,
        share_not_worse=share_not_worse,
        profile=profile,
        candidate_wins=(
            candidate_mean is not None
            and as_run_return is not None
            and candidate_mean > as_run_return
        ),
    )

    reasons = [str(gate["reason"]) for gate in gates if gate["reason"]]
    limits = [
        "Veredicto DESCRIPTIVO y advisory: no autoriza operar ni sustituye la estrategia activa.",
        "El bootstrap es determinista y con muestra pequeña solo descarta diferencias gruesas.",
        "``cash`` y ``market_bh`` no compiten como 'mejor estrategia': control y benchmark.",
        "Una candidata solo se compara si está medida en TODAS las épocas de la ventana.",
    ]
    if any(gate["status"] == GATE_NOT_EVALUATED for gate in gates):
        limits.append(
            "Hay gates NOT_EVALUATED: se publican como huecos y el veredicto no los cuenta "
            "como aprobados."
        )

    return VerificationVerdict(
        verdict=verdict,
        activation_allowed=False,
        profile_id=profile.profile_id,
        profile_hash=profile.hash(),
        gates=tuple(gates),
        samples=sample_gate["samples"],
        required_samples=sample_gate["required"],
        as_run_mean_r=as_run_mean,
        best_arm=best_arm,
        best_arm_mean_r=best_mean,
        mean_excess_r=mean_excess,
        share_epochs_not_worse=share_not_worse,
        bootstrap_low=bootstrap_low,
        candidate_mean_return_pct=candidate_mean,
        as_run_mean_return_pct=as_run_return,
        epochs=tuple(epoch.to_dict() for epoch in samples),
        reasons=tuple(reasons),
        limits=tuple(limits),
    )


def _decide(
    *,
    gates: Sequence[Mapping[str, Any]],
    sample_passed: bool,
    mean_excess: float | None,
    share_not_worse: float | None,
    profile: StrategyVerificationProfileV1,
    candidate_wins: bool,
) -> str:
    """Traduce gates a veredicto, del más informativo al más conservador."""
    by_name = {str(gate["gate"]): str(gate["status"]) for gate in gates}
    if by_name.get("independent_sample") != GATE_PASS:
        return VERDICT_INSUFFICIENT_SAMPLE
    if by_name.get("version_integrity") == GATE_FAIL:
        return VERDICT_INCONCLUSIVE_VERSION
    if by_name.get("method_certified") == GATE_FAIL:
        return VERDICT_INSUFFICIENT_SAMPLE
    if by_name.get("freshness") == GATE_FAIL:
        return VERDICT_INSUFFICIENT_SAMPLE

    thresholds = profile.thresholds
    dominated = (
        mean_excess is not None
        and share_not_worse is not None
        and mean_excess < 0.0
        and share_not_worse < float(thresholds.min_share_epochs_not_worse)
    )
    if dominated and profile.decision.relab_on_arm_dominance:
        return VERDICT_RELAB
    if candidate_wins:
        return VERDICT_PROMOTE_REQUIRES_HUMAN
    if by_name.get("as_run_vs_best_arm") != GATE_PASS:
        return VERDICT_WATCH
    if by_name.get("observed_health") != GATE_PASS:
        return (
            VERDICT_WATCH
            if profile.decision.watch_on_inconclusive
            else VERDICT_INSUFFICIENT_SAMPLE
        )
    if by_name.get("candidate_vs_as_run") == GATE_FAIL:
        # La candidata no mejora: es una buena noticia para la estrategia activa, no un fallo
        # del método. No rebaja el veredicto.
        return VERDICT_CONTINUE
    return VERDICT_CONTINUE
