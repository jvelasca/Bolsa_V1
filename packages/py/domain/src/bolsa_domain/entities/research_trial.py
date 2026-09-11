"""Entidad de dominio de ensayo/experimento de investigación — sin dependencias externas."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResearchTrial:
    id: str
    instrument_id: str
    params: dict[str, Any]
    is_metrics: dict[str, Any]
    proposed_by: str
    k_contribution: int
    created_at: str
    hypothesis_id: str | None = None
    research_question_id: str | None = None
    backtest_run_id: str | None = None
    optimization_run_id: str | None = None
    strategy_definition_id: str | None = None
    preset_key: str | None = None
    strategy_name: str | None = None
    # V2.38 (incremento 3): region de parametros determinista (bucket v0) del trial, o
    # ``None`` si no aplica (sin grid / flag OFF / trial historico). Ver
    # ``bolsa_application.discovery_param_region``.
    param_region: str | None = None
    blocks: dict[str, Any] | None = None
    is_score: float | None = None
    parent_trial_id: str | None = None
    fail_code: str | None = None
    manifest_ref: dict[str, Any] | None = None
