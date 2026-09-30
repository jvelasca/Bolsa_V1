"""Granularidad operativa AUTO — relojes separados e independientes (ADR-010, diseño v2).

Value object **puro**: sin reloj de pared, sin IO, sin infraestructura. Modela la
*cadencia declarada* del motor AUTO como **relojes desacoplados** en vez de una única
cadencia global:

* ``DecisionClock`` — cuándo se **decide** (una evaluación por barra cerrada).
* ``ProtectionClock`` — con qué **resolución** se evalúa la protección.
* ``ExecutionModel`` — **cuándo** se ejecuta la señal (banco temporal del fill).
* ``EvidenceBucket`` — en qué **cubo de calendario** se agrega la evidencia.

El **heartbeat de infraestructura** (turno de 60 s, recovery, watchdog) NO vive aquí:
es deliberadamente ajeno al dominio de decisión y se mantiene fuera del value object
para que ningún cambio de granularidad operativa lo arrastre.

**Fail-closed por diseño:** una granularidad puede *declararse* sin estar *habilitada*
(p. ej. ``1wk``); el gate ``require_supported()`` la rechaza con un motivo tipado en
vez de degradarla en silencio a la cadencia por defecto.

Ver ``docs/engineering/rethink-granularidad-operativa-auto-v2-2026-09-30.md`` (diseño v2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from bolsa_domain.errors import UnsupportedGranularityError
from bolsa_domain.platform_kernel import validate_kernel_timeframe


class ProtectionModel(StrEnum):
    """Modelo de evaluación de la protección D1."""

    #: Modelo A — OHLC de la barra (``Low(D) <= stop``), sin necesidad de feed intradía.
    BAR_OHLC = "bar_ohlc"
    #: Modelo B — feed intradía real. **No soportado hoy** (no hay ingesta intradía).
    INTRADAY_FEED = "intraday_feed"


class ExecutionTiming(StrEnum):
    """Banco temporal del fill (cuándo se ejecuta la señal)."""

    #: Forma **histórica**: el fill se ancla a la barra de señal (``seed = minuto``).
    #: Declarada para poder nombrar el estado actual; su retirada es la **Fase B**.
    SIGNAL_BAR = "signal_bar"
    #: Contrato objetivo ``signal_bar = D`` → ``execution_bar = D+1`` → ``OPEN(D+1)``.
    #: **Declarado, NO habilitado** en este incremento (se habilita en la Fase B).
    NEXT_BAR_OPEN = "next_bar_open"


class EvidenceBucketUnit(StrEnum):
    """Unidad del cubo de calendario para la evidencia agregada."""

    DAY = "day"
    WEEK = "week"


class GranularityRejection(StrEnum):
    """Motivo tipado por el que una granularidad declarada NO se puede habilitar."""

    UNKNOWN_GRANULARITY = "unknown_granularity"
    DECISION_NOT_ENABLED = "decision_not_enabled"
    PROTECTION_MODEL_UNSUPPORTED = "protection_model_unsupported"
    PROTECTION_RESOLUTION_UNSUPPORTED = "protection_resolution_unsupported"
    EXECUTION_TIMING_NOT_ENABLED = "execution_timing_not_enabled"
    EVIDENCE_BUCKET_NOT_ENABLED = "evidence_bucket_not_enabled"


# --------------------------------------------------------------------------------------
# Matriz de capacidades (única fuente de verdad del gate).
#
# Hoy **solo** está habilitada la combinación que el motor implementa de verdad:
# decisión diaria + protección OHLC diaria + banco temporal histórico + cubo diario.
# Todo lo demás está **declarado** (para poder nombrarlo y probarlo) pero **NO habilitado**.
# --------------------------------------------------------------------------------------
_ENABLED_DECISION_TIMEFRAMES: frozenset[str] = frozenset({"1d"})
_ENABLED_PROTECTION_MODELS: frozenset[ProtectionModel] = frozenset({ProtectionModel.BAR_OHLC})
_ENABLED_PROTECTION_RESOLUTIONS: frozenset[str] = frozenset({"1d"})
_ENABLED_EXECUTION_TIMINGS: frozenset[ExecutionTiming] = frozenset({ExecutionTiming.SIGNAL_BAR})
_ENABLED_EVIDENCE_BUCKETS: frozenset[EvidenceBucketUnit] = frozenset({EvidenceBucketUnit.DAY})


@dataclass(frozen=True, slots=True)
class DecisionClock:
    """Cadencia de decisión: una evaluación por barra cerrada del ``timeframe``."""

    timeframe: str

    def __post_init__(self) -> None:
        # Estructural: el timeframe debe pertenecer al kernel (ADR-010). Un valor ajeno
        # (p. ej. ``"1m"``) no es una granularidad, es un error de configuración.
        object.__setattr__(self, "timeframe", validate_kernel_timeframe(self.timeframe))


@dataclass(frozen=True, slots=True)
class ProtectionClock:
    """Resolución con la que se evalúa la protección, y su modelo."""

    model: ProtectionModel = ProtectionModel.BAR_OHLC
    resolution: str = "1d"

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolution", validate_kernel_timeframe(self.resolution))


@dataclass(frozen=True, slots=True)
class ExecutionModel:
    """Banco temporal del fill y modelo de slippage declarado."""

    timing: ExecutionTiming = ExecutionTiming.NEXT_BAR_OPEN
    slippage_model: str = "none"

    def __post_init__(self) -> None:
        normalized = self.slippage_model.strip()
        if not normalized:
            raise ValueError("slippage_model no puede estar vacío")
        object.__setattr__(self, "slippage_model", normalized)


@dataclass(frozen=True, slots=True)
class EvidenceBucket:
    """Cubo de calendario con el que se agrega la evidencia."""

    unit: EvidenceBucketUnit = EvidenceBucketUnit.DAY


@dataclass(frozen=True, slots=True)
class OperativeGranularity:
    """Granularidad operativa declarada: cuatro relojes independientes + su gate.

    La construcción **no** falla por una combinación no habilitada: el rechazo es
    explícito y consultable (``reject_reason``) o exigible (``require_supported``).
    Así una configuración no soportada se puede *declarar* y *probar* sin que el
    simple hecho de nombrarla rompa el arranque.
    """

    decision: DecisionClock
    protection: ProtectionClock
    execution: ExecutionModel
    evidence: EvidenceBucket

    def reject_reason(self) -> GranularityRejection | None:
        """Primer motivo por el que la combinación NO está habilitada (``None`` si lo está)."""
        if self.decision.timeframe not in _ENABLED_DECISION_TIMEFRAMES:
            return GranularityRejection.DECISION_NOT_ENABLED
        if self.protection.model not in _ENABLED_PROTECTION_MODELS:
            return GranularityRejection.PROTECTION_MODEL_UNSUPPORTED
        if self.protection.resolution not in _ENABLED_PROTECTION_RESOLUTIONS:
            return GranularityRejection.PROTECTION_RESOLUTION_UNSUPPORTED
        if self.execution.timing not in _ENABLED_EXECUTION_TIMINGS:
            return GranularityRejection.EXECUTION_TIMING_NOT_ENABLED
        if self.evidence.unit not in _ENABLED_EVIDENCE_BUCKETS:
            return GranularityRejection.EVIDENCE_BUCKET_NOT_ENABLED
        return None

    def is_supported(self) -> bool:
        """``True`` si la combinación está habilitada. Fail-closed: por defecto, no."""
        return self.reject_reason() is None

    def require_supported(self) -> OperativeGranularity:
        """Devuelve ``self`` si está habilitada; si no, **rechaza** con motivo tipado.

        Nunca degrada a la cadencia por defecto: una granularidad no habilitada es un
        error de configuración que debe verse, no un silencio.
        """
        reason = self.reject_reason()
        if reason is not None:
            raise UnsupportedGranularityError(
                reason,
                f"granularidad no habilitada: decision={self.decision.timeframe!r}, "
                f"protection={self.protection.model.value}/{self.protection.resolution!r}, "
                f"execution={self.execution.timing.value!r}, "
                f"evidence={self.evidence.unit.value!r}",
            )
        return self


#: Granularidad **habilitada** hoy: decisión diaria + protección OHLC diaria + banco
#: temporal histórico + cubo diario. Es la que resuelve la configuración por defecto.
DAILY_GRANULARITY = OperativeGranularity(
    decision=DecisionClock(timeframe="1d"),
    protection=ProtectionClock(model=ProtectionModel.BAR_OHLC, resolution="1d"),
    execution=ExecutionModel(timing=ExecutionTiming.SIGNAL_BAR),
    evidence=EvidenceBucket(unit=EvidenceBucketUnit.DAY),
)

#: Granularidad semanal **declarada pero NO habilitada** (gap del lunes sin pruebas
#: temporales). Existe para poder nombrarla y probar que el gate la rechaza.
WEEKLY_GRANULARITY = OperativeGranularity(
    decision=DecisionClock(timeframe="1wk"),
    protection=ProtectionClock(model=ProtectionModel.BAR_OHLC, resolution="1wk"),
    execution=ExecutionModel(timing=ExecutionTiming.NEXT_BAR_OPEN),
    evidence=EvidenceBucket(unit=EvidenceBucketUnit.WEEK),
)

__all__ = [
    "DAILY_GRANULARITY",
    "WEEKLY_GRANULARITY",
    "DecisionClock",
    "EvidenceBucket",
    "EvidenceBucketUnit",
    "ExecutionModel",
    "ExecutionTiming",
    "GranularityRejection",
    "OperativeGranularity",
    "ProtectionClock",
    "ProtectionModel",
]
