"""Evidence Engine v1 — suite estadística + ART-EDGE-REPORT (RFC-008 D3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from bolsa_analytics.cognitive.edge_report import (
    EdgeReport,
    StatisticalSuiteResult,
    build_edge_report,
)
from bolsa_analytics.cognitive.psr_dsr import psr_dsr_from_returns
from bolsa_analytics.cognitive.stats_suite import (
    monte_carlo_permutation_p_value,
    walk_forward_efficiency,
)
from bolsa_analytics.cognitive.trials_log import TrialsLog


@dataclass(frozen=True, slots=True)
class EvidenceEngineInput:
    strategy_or_signal_ref: str
    trade_returns: Sequence[float]
    trials_log: TrialsLog
    in_sample_sharpe: float | None = None
    out_of_sample_sharpe: float | None = None
    # Lab optimize WFE (score OOS/IS). Preferred over Sharpe WFE when set.
    lab_walk_forward_efficiency: float | None = None
    stress_survival_rate: float | None = None
    bootstrap_alpha_ci_lower: float | None = None
    bootstrap_alpha_ci_upper: float | None = None
    monte_carlo_permutations: int = 1000
    seed: int = 42


@dataclass(frozen=True, slots=True)
class EvidenceEngineResult:
    edge_report: EdgeReport
    trials_n: int
    trials_log_id: str
    auto_live_eligible: bool
    block_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edgeReport": self.edge_report.to_dict(),
            "trialsN": self.trials_n,
            "trialsLogId": self.trials_log_id,
            "autoLiveEligible": self.auto_live_eligible,
            "blockReasons": list(self.block_reasons),
        }


def _win_rate(returns: Sequence[float]) -> float | None:
    arr = np.asarray(list(returns), dtype=float)
    if arr.size == 0:
        return None
    return float(np.mean(arr > 0))


def run_evidence_suite(inp: EvidenceEngineInput) -> EvidenceEngineResult:
    """
    Ejecuta WFE + Monte Carlo + PSR/DSR (+ opcionales) y emite EdgeReport.
    Sin trials_n >= 1 el DSR no es válido → auto_live_eligible = False.
    """
    trials_n = inp.trials_log.trials_n
    returns = list(inp.trade_returns)
    notes: list[str] = []

    if trials_n < 1:
        notes.append("TrialsLog vacío — DSR inválido; auto-live bloqueado")
        suite = StatisticalSuiteResult(
            trials_n=0,
            sample_trades_count=len(returns),
            historical_win_rate=_win_rate(returns),
        )
        report = build_edge_report(inp.strategy_or_signal_ref, suite, notes=tuple(notes))
        return EvidenceEngineResult(
            edge_report=report,
            trials_n=0,
            trials_log_id=inp.trials_log.log_id,
            auto_live_eligible=False,
            block_reasons=("missing_trials_log",),
        )

    wfe = None
    wfe_source = None
    if inp.lab_walk_forward_efficiency is not None:
        wfe = float(inp.lab_walk_forward_efficiency)
        wfe_source = "lab_score"
        notes.append(
            "WFE from optimize lab (score OOS/IS ratio), not Sharpe_OOS/Sharpe_IS"
        )
    elif inp.in_sample_sharpe is not None and inp.out_of_sample_sharpe is not None:
        wfe = walk_forward_efficiency(inp.in_sample_sharpe, inp.out_of_sample_sharpe)
        wfe_source = "sharpe"

    mc_p = (
        monte_carlo_permutation_p_value(
            returns,
            permutations=inp.monte_carlo_permutations,
            seed=inp.seed,
        )
        if len(returns) >= 3
        else 1.0
    )

    _sr, psr, dsr = psr_dsr_from_returns(returns, trials_n=trials_n)

    suite = StatisticalSuiteResult(
        trials_n=trials_n,
        walk_forward_efficiency=wfe,
        wfe_source=wfe_source,
        monte_carlo_p_value=mc_p,
        psr=round(psr, 4),
        dsr=round(dsr, 4),
        bootstrap_alpha_ci_lower=inp.bootstrap_alpha_ci_lower,
        bootstrap_alpha_ci_upper=inp.bootstrap_alpha_ci_upper,
        stress_survival_rate=inp.stress_survival_rate,
        historical_win_rate=_win_rate(returns),
        sample_trades_count=len(returns),
    )
    report = build_edge_report(inp.strategy_or_signal_ref, suite, notes=tuple(notes))

    block: list[str] = []
    if report.band == "luck":
        block.append("edge_band_luck")
    if report.credibility < 65:
        block.append("credibility_below_65")
    if dsr < 0.5:
        block.append("dsr_below_0.5")
    if mc_p > 0.05:
        block.append("monte_carlo_p_above_0.05")
    if wfe is not None and wfe < 0.5:
        block.append("wfe_below_0.5")

    eligible = len(block) == 0 and report.band in {"skill", "uncertain"}
    # uncertain may still be paper-only; auto-live requires skill by default
    if report.band != "skill":
        block.append("band_not_skill_for_auto_live")
        eligible = False

    return EvidenceEngineResult(
        edge_report=report,
        trials_n=trials_n,
        trials_log_id=inp.trials_log.log_id,
        auto_live_eligible=eligible,
        block_reasons=tuple(block),
    )
