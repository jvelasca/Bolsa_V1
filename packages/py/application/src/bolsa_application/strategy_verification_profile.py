"""Perfil de verificación periódica de estrategia — configuración **pre-registrada**.

Qué resuelve
------------
El DÍA-D as-run mide bien, pero cada corrida era una combinación ad-hoc de banderas: sin un
perfil declarado y hasheado ANTES de medir, dos corridas con umbrales distintos podían
compararse como si fueran la misma prueba. Este módulo fija ese contrato.

Reglas duras (fail-closed, coherentes con ADR-049):

* **La muestra mínima no se baja.** ``minCohortSamples >= 12``; un perfil con menos es
  inválido, no una variante.
* **La activación automática está prohibida.** ``allowAutoActivation`` debe ser ``False``: el
  perfil configura CÓMO se verifica, nunca autoriza operar.
* **El universo de D se declara.** Sin instrumentos declarados no se puede certificar el
  estado inicial y el perfil es inválido.
* **Sin coste no hay veredicto.** El modelo de ejecución debe declarar un round-trip > 0.
* **Hash determinista.** Mismo perfil ⇒ mismo ``profileHash``; cambiar un umbral lo cambia.

Este módulo es puro: no lee configuración, no escribe nada y no ejecuta mediciones.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from bolsa_application.dia_d_as_run import (
    ARM_AS_RUN,
    ARM_CANDIDATE,
    ARM_CASH,
    ARM_MARKET_BH,
    AS_RUN_ARMS,
    DEFAULT_COST_BPS,
    DEFAULT_MAX_PARTICIPATION_PCT,
    DEFAULT_MIN_COHORT_SAMPLES,
    AsRunExecutionModel,
)

__all__ = [
    "CADENCE_MODE_EPOCHS",
    "DECISION_POLICY_VERSION",
    "PROFILE_SCHEMA_VERSION",
    "StrategyVerificationProfileV1",
    "VerificationCadence",
    "VerificationCandidatePolicy",
    "VerificationDecisionPolicy",
    "VerificationProfileError",
    "VerificationSamples",
    "VerificationThresholds",
    "default_profile",
    "is_iso_day",
    "profile_hash",
]

PROFILE_SCHEMA_VERSION = "StrategyVerificationProfileV1"
DECISION_POLICY_VERSION = "strategy-verification-decision-v1"

#: Única cadencia soportada: épocas no solapadas (la ventana móvil es un complemento).
CADENCE_MODE_EPOCHS = "epochs"

#: Épocas que entran al veredicto por defecto. Se declara para que la muestra acumulada y la
#: muestra que pesa en la decisión no se confundan.
DEFAULT_EPOCHS_IN_VERDICT = DEFAULT_MIN_COHORT_SAMPLES


class VerificationProfileError(ValueError):
    """El perfil no satisface el contrato: se rechaza, no se corrige en silencio."""


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def profile_hash(payload: Mapping[str, Any]) -> str:
    """Hash determinista de un perfil."""
    return hashlib.sha256(_canonical(dict(payload)).encode("utf-8")).hexdigest()


def is_iso_day(value: Any) -> bool:
    """``YYYY-MM-DD`` válido de calendario (no basta con la forma)."""
    text = str(value or "").strip()
    if len(text) < 10:
        return False
    try:
        date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class VerificationCadence:
    """Cada cuántos días se abre una época y cómo se complementa con la ventana móvil.

    ``everyDays`` es el paso entre anclas: la época ``k`` cubre ``(D_k, D_{k+1}]``. Con
    ``everyDays=30`` la primera cohorte de 12 muestras tarda ~12 meses: es el precio de la
    independencia. Con ``everyDays`` pequeño las muestras llegan antes, pero comparten
    posiciones abiertas y la cohorte lo declara.
    """

    every_days: int = 30
    anchor_day: str | None = None
    rolling_enabled: bool = True
    rolling_lookback_days: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.every_days, bool) or int(self.every_days) < 1:
            raise VerificationProfileError("everyDays debe ser un entero >= 1")
        if self.anchor_day is not None and not is_iso_day(self.anchor_day):
            raise VerificationProfileError("anchorDay debe ser una fecha YYYY-MM-DD")
        if isinstance(self.rolling_lookback_days, bool) or int(self.rolling_lookback_days) < 1:
            raise VerificationProfileError("rollingLookbackDays debe ser un entero >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": CADENCE_MODE_EPOCHS,
            "everyDays": int(self.every_days),
            "anchorDay": self.anchor_day,
            "rollingEnabled": bool(self.rolling_enabled),
            "rollingLookbackDays": int(self.rolling_lookback_days),
        }


@dataclass(frozen=True, slots=True)
class VerificationSamples:
    """Mínimos de muestra. ``minCohortSamples`` nunca baja de 12."""

    min_cohort_samples: int = DEFAULT_MIN_COHORT_SAMPLES
    min_closed_cycles: int = 1
    min_per_instrument_cycles: int = 0
    epochs_in_verdict: int = DEFAULT_EPOCHS_IN_VERDICT

    def __post_init__(self) -> None:
        if int(self.min_cohort_samples) < DEFAULT_MIN_COHORT_SAMPLES:
            raise VerificationProfileError(
                f"minCohortSamples no puede bajar de {DEFAULT_MIN_COHORT_SAMPLES}"
            )
        if int(self.min_closed_cycles) < 0:
            raise VerificationProfileError("minClosedCycles debe ser >= 0")
        if int(self.min_per_instrument_cycles) < 0:
            raise VerificationProfileError("minPerInstrumentCycles debe ser >= 0")
        if int(self.epochs_in_verdict) < 1:
            raise VerificationProfileError("epochsInVerdict debe ser >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "minCohortSamples": int(self.min_cohort_samples),
            "minClosedCycles": int(self.min_closed_cycles),
            "minPerInstrumentCycles": int(self.min_per_instrument_cycles),
            "epochsInVerdict": int(self.epochs_in_verdict),
        }


@dataclass(frozen=True, slots=True)
class VerificationCandidatePolicy:
    """Cómo se mide la candidata.

    ``requirePointInTime`` es innegociable: una candidata construida después de ``D`` no pudo
    decidir en ``D`` y medirla sería look-ahead.
    """

    require_point_in_time: bool = True
    measure_forward: bool = True
    max_candidates: int = 1

    def __post_init__(self) -> None:
        if not self.require_point_in_time:
            raise VerificationProfileError(
                "requirePointInTime=false permitiría look-ahead: la candidata debe existir en D"
            )
        if int(self.max_candidates) < 0:
            raise VerificationProfileError("maxCandidates debe ser >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirePointInTime": True,
            "measureForward": bool(self.measure_forward),
            "maxCandidates": int(self.max_candidates),
        }


@dataclass(frozen=True, slots=True)
class VerificationThresholds:
    """Umbrales del veredicto, fijados antes de medir.

    * ``minExcessMeanR``: la operativa real debe superar al mejor brazo contrafactual en R
      medio. ``0`` exige empate o mejor, no una victoria aplastante.
    * ``minShareEpochsNotWorse``: proporción de épocas en las que ``as_run`` no quedó por
      debajo del mejor brazo. Evita coronar una media sostenida por una sola época.
    * ``maxEvidenceAgeDays``: TTL de frescura (``None`` = sin TTL, la edad se declara).
    """

    min_excess_mean_r: float = 0.0
    min_share_epochs_not_worse: float = 0.6
    max_drawdown_pct: float = 15.0
    min_hit_rate: float | None = None
    max_evidence_age_days: float | None = None

    def __post_init__(self) -> None:
        share = float(self.min_share_epochs_not_worse)
        if not 0.0 < share <= 1.0:
            raise VerificationProfileError("minShareEpochsNotWorse debe estar en (0, 1]")
        if float(self.max_drawdown_pct) <= 0:
            raise VerificationProfileError("maxDrawdownPct debe ser > 0")
        if self.min_hit_rate is not None and not 0.0 <= float(self.min_hit_rate) <= 1.0:
            raise VerificationProfileError("minHitRate debe estar en [0, 1]")
        if self.max_evidence_age_days is not None and float(self.max_evidence_age_days) < 0:
            raise VerificationProfileError("maxEvidenceAgeDays debe ser >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "minExcessMeanR": float(self.min_excess_mean_r),
            "minShareEpochsNotWorse": float(self.min_share_epochs_not_worse),
            "maxDrawdownPct": float(self.max_drawdown_pct),
            "minHitRate": None if self.min_hit_rate is None else float(self.min_hit_rate),
            "maxEvidenceAgeDays": (
                None if self.max_evidence_age_days is None else float(self.max_evidence_age_days)
            ),
        }


@dataclass(frozen=True, slots=True)
class VerificationDecisionPolicy:
    """Qué hace el sistema con el veredicto. Nunca activa nada."""

    version: str = DECISION_POLICY_VERSION
    watch_on_inconclusive: bool = True
    relab_on_arm_dominance: bool = True
    allow_auto_activation: bool = False

    def __post_init__(self) -> None:
        if self.allow_auto_activation:
            raise VerificationProfileError(
                "allowAutoActivation debe ser False: la verificación no autoriza operar"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "watchOnInconclusive": bool(self.watch_on_inconclusive),
            "relabOnArmDominance": bool(self.relab_on_arm_dominance),
            "allowAutoActivation": False,
        }


@dataclass(frozen=True, slots=True)
class StrategyVerificationProfileV1:
    """Perfil completo de verificación periódica de una cuenta."""

    profile_id: str
    account_scope: str
    universe_instruments: tuple[str, ...]
    cadence: VerificationCadence = field(default_factory=VerificationCadence)
    samples: VerificationSamples = field(default_factory=VerificationSamples)
    arms: tuple[str, ...] = (
        ARM_AS_RUN,
        "hold_structural",
        "engine_params",
        ARM_CASH,
        ARM_MARKET_BH,
        ARM_CANDIDATE,
    )
    candidate: VerificationCandidatePolicy = field(
        default_factory=VerificationCandidatePolicy
    )
    thresholds: VerificationThresholds = field(default_factory=VerificationThresholds)
    decision: VerificationDecisionPolicy = field(default_factory=VerificationDecisionPolicy)
    execution: AsRunExecutionModel = field(
        default_factory=lambda: AsRunExecutionModel(
            commission_bps=DEFAULT_COST_BPS / 2.0,
            max_participation_pct=DEFAULT_MAX_PARTICIPATION_PCT,
        )
    )
    version: str = PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not str(self.profile_id or "").strip():
            raise VerificationProfileError("profileId es obligatorio")
        if not str(self.account_scope or "").strip():
            raise VerificationProfileError("accountScope es obligatorio")
        declared = tuple(
            sorted({str(item).strip() for item in self.universe_instruments if str(item).strip()})
        )
        if not declared:
            raise VerificationProfileError(
                "universeInstruments es obligatorio: sin universo declarado en D no se certifica"
            )
        object.__setattr__(self, "universe_instruments", declared)

        arms = tuple(str(arm) for arm in self.arms)
        unknown = [arm for arm in arms if arm not in AS_RUN_ARMS]
        if unknown:
            raise VerificationProfileError(f"brazos no soportados: {', '.join(unknown)}")
        for required in (ARM_AS_RUN, ARM_CASH, ARM_MARKET_BH):
            if required not in arms:
                raise VerificationProfileError(
                    f"el brazo {required} es obligatorio (lo exige la certificación)"
                )
        object.__setattr__(self, "arms", arms)

        if self.execution.round_trip_bps <= 0:
            raise VerificationProfileError(
                "el modelo de ejecución debe declarar un round-trip > 0"
            )
        if self.candidate.max_candidates and ARM_CANDIDATE not in arms:
            raise VerificationProfileError(
                "maxCandidates > 0 exige el brazo 'candidate' en arms"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "profileId": str(self.profile_id),
            "accountScope": str(self.account_scope),
            "universeInstruments": list(self.universe_instruments),
            "cadence": self.cadence.to_dict(),
            "samples": self.samples.to_dict(),
            "arms": list(self.arms),
            "candidate": self.candidate.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "decision": self.decision.to_dict(),
            "execution": self.execution.to_dict(),
        }

    def hash(self) -> str:
        """Huella pre-registrada del perfil efectivo."""
        return profile_hash(self.to_dict())


def default_profile(
    *,
    profile_id: str,
    account_scope: str,
    universe_instruments: Sequence[str],
    every_days: int = 30,
    anchor_day: str | None = None,
    min_cohort_samples: int = DEFAULT_MIN_COHORT_SAMPLES,
    execution: AsRunExecutionModel | None = None,
) -> StrategyVerificationProfileV1:
    """Perfil conservador por defecto (validado; nunca autoriza activación)."""
    return StrategyVerificationProfileV1(
        profile_id=profile_id,
        account_scope=account_scope,
        universe_instruments=tuple(universe_instruments),
        cadence=VerificationCadence(every_days=every_days, anchor_day=anchor_day),
        samples=VerificationSamples(min_cohort_samples=min_cohort_samples),
        execution=execution
        or AsRunExecutionModel(
            commission_bps=DEFAULT_COST_BPS / 2.0,
            max_participation_pct=DEFAULT_MAX_PARTICIPATION_PCT,
        ),
    )
