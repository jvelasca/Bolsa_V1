"""Registros persistibles RFC-008 (sin dependencia de analytics)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DecisionMemoryRecord:
    id: str
    decision_id: str
    instrument_id: str
    outcome: str
    reasons: tuple[str, ...]
    policy_rule_ids: tuple[str, ...]
    reevaluate_when: tuple[str, ...]
    opportunity_intact: bool
    created_at: str
    account_id: str | None = None
    policy_id: str | None = None
    policy_version: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class TrialRecordPersist:
    id: str
    log_id: str
    strategy_family_ref: str
    hypothesis_ref: str
    params_hash: str
    created_at: str
    sharpe_is: float | None = None
    notes: str | None = None
    account_id: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConfidenceStateRecord:
    id: str
    decision_id: str
    instrument_id: str
    confidence_0: float
    confidence: float
    hint: str
    expired: bool
    events: tuple[dict[str, Any], ...]
    notes: tuple[str, ...]
    created_at: str
    updated_at: str
    expires_at: str | None = None
    account_id: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EdgeReportRecord:
    id: str
    version: str
    strategy_or_signal_ref: str
    credibility: float
    edge_score: float
    band: str
    suite: dict[str, Any]
    notes: tuple[str, ...]
    created_at: str
    instrument_universe_ref: str | None = None
    account_id: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class DecisionSessionRecord:
    """Índice + payload de ART-DECISION-SESSION."""

    id: str
    kind: str
    status: str
    instrument_id: str
    created_at: str
    account_id: str | None = None
    symbol: str | None = None
    recommendation_id: str | None = None
    decision_id: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ModelArtifactRecord:
    """Índice + payload ART-MODEL (sin binario)."""

    id: str
    model_id: str
    model_version: str
    framework: str
    feature_set_id: str
    created_at: str
    composition_hash: str | None = None
    model_checksum: str | None = None
    trained_at: str | None = None
    updated_at: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    """Índice + payload ART-PREDICTION."""

    id: str
    instrument_id: str
    model_id: str
    model_version: str
    created_at: str
    horizon: str | None = None
    value: float | None = None
    confidence: float | None = None
    as_of: str | None = None
    payload: dict[str, Any] | None = None
