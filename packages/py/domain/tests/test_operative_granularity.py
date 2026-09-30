"""Tests del value object puro de granularidad operativa (diseño v2, ADR-010).

Cubren la matriz de capacidades y el gate **fail-closed**: lo declarado-no-habilitado
(``1wk``, banco temporal ``next_bar_open``, cubo semanal, protección intradía) se
rechaza con motivo tipado; nunca se degrada en silencio.
"""

from __future__ import annotations

import dataclasses

import pytest

from bolsa_domain.errors import UnsupportedGranularityError
from bolsa_domain.operative_granularity import (
    DAILY_GRANULARITY,
    WEEKLY_GRANULARITY,
    DecisionClock,
    EvidenceBucket,
    EvidenceBucketUnit,
    ExecutionModel,
    ExecutionTiming,
    GranularityRejection,
    OperativeGranularity,
    ProtectionClock,
    ProtectionModel,
)


def test_daily_granularity_is_enabled() -> None:
    assert DAILY_GRANULARITY.reject_reason() is None
    assert DAILY_GRANULARITY.is_supported() is True
    assert DAILY_GRANULARITY.require_supported() is DAILY_GRANULARITY
    assert DAILY_GRANULARITY.decision.timeframe == "1d"


def test_weekly_granularity_is_declared_but_not_enabled() -> None:
    # Existe (se puede nombrar y probar), pero el gate la rechaza: gap del lunes.
    assert WEEKLY_GRANULARITY.decision.timeframe == "1wk"
    assert WEEKLY_GRANULARITY.is_supported() is False
    assert WEEKLY_GRANULARITY.reject_reason() is GranularityRejection.DECISION_NOT_ENABLED


def test_require_supported_raises_with_typed_reason() -> None:
    with pytest.raises(UnsupportedGranularityError) as excinfo:
        WEEKLY_GRANULARITY.require_supported()
    assert excinfo.value.reason is GranularityRejection.DECISION_NOT_ENABLED
    assert "1wk" in excinfo.value.detail


def test_decision_clock_rejects_non_kernel_timeframe() -> None:
    with pytest.raises(ValueError, match="1d"):
        DecisionClock(timeframe="1h")


def test_protection_model_b_is_rejected() -> None:
    granularity = OperativeGranularity(
        decision=DecisionClock(timeframe="1d"),
        protection=ProtectionClock(model=ProtectionModel.INTRADAY_FEED, resolution="1d"),
        execution=ExecutionModel(timing=ExecutionTiming.SIGNAL_BAR),
        evidence=EvidenceBucket(unit=EvidenceBucketUnit.DAY),
    )
    assert granularity.reject_reason() is GranularityRejection.PROTECTION_MODEL_UNSUPPORTED


def test_protection_resolution_rejects_intraday() -> None:
    with pytest.raises(ValueError):
        ProtectionClock(model=ProtectionModel.BAR_OHLC, resolution="5m")


def test_next_bar_open_timing_is_declared_but_not_enabled() -> None:
    granularity = OperativeGranularity(
        decision=DecisionClock(timeframe="1d"),
        protection=ProtectionClock(model=ProtectionModel.BAR_OHLC, resolution="1d"),
        execution=ExecutionModel(timing=ExecutionTiming.NEXT_BAR_OPEN),
        evidence=EvidenceBucket(unit=EvidenceBucketUnit.DAY),
    )
    assert granularity.reject_reason() is GranularityRejection.EXECUTION_TIMING_NOT_ENABLED


def test_weekly_evidence_bucket_is_not_enabled() -> None:
    granularity = OperativeGranularity(
        decision=DecisionClock(timeframe="1d"),
        protection=ProtectionClock(model=ProtectionModel.BAR_OHLC, resolution="1d"),
        execution=ExecutionModel(timing=ExecutionTiming.SIGNAL_BAR),
        evidence=EvidenceBucket(unit=EvidenceBucketUnit.WEEK),
    )
    assert granularity.reject_reason() is GranularityRejection.EVIDENCE_BUCKET_NOT_ENABLED


def test_slippage_model_cannot_be_blank() -> None:
    with pytest.raises(ValueError, match="slippage_model"):
        ExecutionModel(timing=ExecutionTiming.SIGNAL_BAR, slippage_model="   ")


def test_granularity_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        DAILY_GRANULARITY.decision = DecisionClock(timeframe="1d")  # type: ignore[misc]


def test_heartbeat_is_not_part_of_the_value_object() -> None:
    # El reloj de infraestructura (60 s, recovery, watchdog) vive FUERA del VO.
    names = {field.name for field in dataclasses.fields(OperativeGranularity)}
    assert names == {"decision", "protection", "execution", "evidence"}
