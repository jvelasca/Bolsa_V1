"""ART-EDGE-REPORT + Credibility (RFC-008 D3 skeleton)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

EdgeBand = Literal["skill", "uncertain", "luck"]


WfeSource = Literal["lab_score", "sharpe"]


@dataclass(frozen=True, slots=True)
class StatisticalSuiteResult:
    trials_n: int
    walk_forward_efficiency: float | None = None
    # Provenance: lab optimize score ratio vs Sharpe_OOS/Sharpe_IS.
    wfe_source: WfeSource | None = None
    monte_carlo_p_value: float | None = None
    psr: float | None = None
    dsr: float | None = None
    bootstrap_alpha_ci_lower: float | None = None
    bootstrap_alpha_ci_upper: float | None = None
    stress_survival_rate: float | None = None
    historical_win_rate: float | None = None
    sample_trades_count: int | None = None


@dataclass(frozen=True, slots=True)
class CredibilityWeights:
    w_monte_carlo: float = 0.25
    w_wfe: float = 0.25
    w_dsr: float = 0.2
    w_bootstrap: float = 0.15
    w_stress: float = 0.15


DEFAULT_CREDIBILITY_WEIGHTS = CredibilityWeights()


def _clamp01(n: float) -> float:
    return min(1.0, max(0.0, n))


def compute_credibility(
    suite: StatisticalSuiteResult,
    weights: CredibilityWeights = DEFAULT_CREDIBILITY_WEIGHTS,
) -> tuple[float, float, EdgeBand]:
    """Return (credibility, edge_score, band). DSR ignored if trials_n < 1."""
    if suite.monte_carlo_p_value is None:
        mc = None
    else:
        mc = _clamp01(1.0 - suite.monte_carlo_p_value / 0.05) * (
            1.0 if suite.monte_carlo_p_value <= 0.05 else 0.3
        )

    wfe = None if suite.walk_forward_efficiency is None else _clamp01(suite.walk_forward_efficiency)
    dsr = None if suite.trials_n < 1 or suite.dsr is None else _clamp01(suite.dsr)

    bootstrap: float | None = None
    if suite.bootstrap_alpha_ci_lower is not None and suite.bootstrap_alpha_ci_upper is not None:
        bootstrap = 1.0 if suite.bootstrap_alpha_ci_lower > 0 else 0.35

    stress = None if suite.stress_survival_rate is None else _clamp01(suite.stress_survival_rate)

    weighted: list[tuple[float, float]] = []
    if mc is not None:
        weighted.append((weights.w_monte_carlo, mc))
    if wfe is not None:
        weighted.append((weights.w_wfe, wfe))
    if dsr is not None:
        weighted.append((weights.w_dsr, dsr))
    if bootstrap is not None:
        weighted.append((weights.w_bootstrap, bootstrap))
    if stress is not None:
        weighted.append((weights.w_stress, stress))

    sum_w = sum(w for w, _ in weighted)
    if sum_w <= 0:
        score01 = 0.0
    else:
        score01 = sum(w * v for w, v in weighted) / sum_w

    credibility = round(score01 * 1000) / 10
    edge_score = credibility
    if credibility >= 85:
        band: EdgeBand = "skill"
    elif credibility >= 65:
        band = "uncertain"
    else:
        band = "luck"
    return credibility, edge_score, band


@dataclass(frozen=True, slots=True)
class EdgeReport:
    edge_report_id: str
    version: str
    strategy_or_signal_ref: str
    created_at: str
    suite: StatisticalSuiteResult
    credibility: float
    edge_score: float
    band: EdgeBand
    artifact_type: str = "ART-EDGE-REPORT"
    schema_version: str = "1.0.0"
    instrument_universe_ref: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        s = self.suite
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "edgeReportId": self.edge_report_id,
            "version": self.version,
            "strategyOrSignalRef": self.strategy_or_signal_ref,
            "instrumentUniverseRef": self.instrument_universe_ref,
            "createdAt": self.created_at,
            "suite": {
                "walkForwardEfficiency": s.walk_forward_efficiency,
                "wfeSource": s.wfe_source,
                "monteCarloPValue": s.monte_carlo_p_value,
                "psr": s.psr,
                "dsr": s.dsr,
                "bootstrapAlphaCiLower": s.bootstrap_alpha_ci_lower,
                "bootstrapAlphaCiUpper": s.bootstrap_alpha_ci_upper,
                "stressSurvivalRate": s.stress_survival_rate,
                "historicalWinRate": s.historical_win_rate,
                "sampleTradesCount": s.sample_trades_count,
                "trialsN": s.trials_n,
            },
            "credibility": self.credibility,
            "edgeScore": self.edge_score,
            "band": self.band,
            "notes": list(self.notes),
        }


def build_edge_report(
    strategy_or_signal_ref: str,
    suite: StatisticalSuiteResult,
    *,
    version: str = "1.0.0",
    notes: tuple[str, ...] = (),
) -> EdgeReport:
    credibility, edge_score, band = compute_credibility(suite)
    extra_notes = list(notes)
    if suite.trials_n < 1:
        extra_notes.append("DSR inválido: trialsN < 1")
    return EdgeReport(
        edge_report_id=f"EDGE-{uuid4().hex[:12]}",
        version=version,
        strategy_or_signal_ref=strategy_or_signal_ref,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        suite=suite,
        credibility=credibility,
        edge_score=edge_score,
        band=band,
        notes=tuple(extra_notes),
    )
