"""Lab EdgeReport lite — MC + PSR/DSR + lab WFE from optimize champion trades."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bolsa_analytics.cognitive.evidence_engine import (
    EvidenceEngineInput,
    run_evidence_suite,
)
from bolsa_analytics.cognitive.trials_log import TrialsLog

LAB_MC_PERMUTATIONS = 400
MIN_TRADES_FOR_MC = 3


def trade_returns_from_pnls(
    pnls: Sequence[float],
    *,
    initial_cash: float,
) -> list[float]:
    """Convert cash round-trip PnLs to fractional returns vs initial cash."""
    if initial_cash <= 0:
        return []
    return [float(p) / float(initial_cash) for p in pnls]


def build_lab_edge_report_lite(
    *,
    strategy_ref: str,
    trade_returns: Sequence[float],
    trials_n: int,
    lab_walk_forward_efficiency: float | None,
    family: str = "",
    monte_carlo_permutations: int = LAB_MC_PERMUTATIONS,
    seed: int = 42,
) -> dict[str, Any] | None:
    """Run evidence suite for the lab champion; return compact JSON-ready report.

    Returns None when there are too few trades for a meaningful suite.
    """
    returns = [float(r) for r in trade_returns if r is not None]
    if len(returns) < MIN_TRADES_FOR_MC:
        return None

    log = TrialsLog(strategy_family_ref=family or strategy_ref)
    n = max(1, int(trials_n))
    for i in range(n):
        log.record(f"lab-hyp-{i}", params_hash=f"lab-{i}", sharpe_is=None)

    result = run_evidence_suite(
        EvidenceEngineInput(
            strategy_or_signal_ref=strategy_ref,
            trade_returns=returns,
            trials_log=log,
            lab_walk_forward_efficiency=lab_walk_forward_efficiency,
            monte_carlo_permutations=monte_carlo_permutations,
            seed=seed,
        )
    )
    report = result.edge_report
    suite = report.suite
    return {
        "artifactType": report.artifact_type,
        "schemaVersion": report.schema_version,
        "edgeReportId": report.edge_report_id,
        "strategyOrSignalRef": report.strategy_or_signal_ref,
        "credibility": report.credibility,
        "edgeScore": report.edge_score,
        "band": report.band,
        "notes": list(report.notes),
        "autoLiveEligible": result.auto_live_eligible,
        "blockReasons": list(result.block_reasons),
        "suite": {
            "trialsN": suite.trials_n,
            "walkForwardEfficiency": suite.walk_forward_efficiency,
            "wfeSource": suite.wfe_source,
            "monteCarloPValue": suite.monte_carlo_p_value,
            "psr": suite.psr,
            "dsr": suite.dsr,
            "historicalWinRate": suite.historical_win_rate,
            "sampleTradesCount": suite.sample_trades_count,
        },
        "sampleTradesCount": len(returns),
        "mode": "lab_lite",
    }
