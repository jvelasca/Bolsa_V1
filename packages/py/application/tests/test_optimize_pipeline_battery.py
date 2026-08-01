"""Battery: optimize pipeline pieces + assembly (no DB / no HTTP).

Covers hold-out, OOS warm-up, IS vs OOS ranking, walk-forward folds,
result serialization and trial-total estimates for WF payloads.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.holdout import split_holdout_bars
from bolsa_analytics.optimize.sma_grid import run_sma_grid_search
from bolsa_analytics.optimize.walk_forward import (
    aggregate_walk_forward_metrics,
    split_walk_forward_bars,
)
from bolsa_application.optimization_runs import (
    estimate_trials_total_from_payload,
    optimize_result_to_dict,
)
from bolsa_application.optimize import (
    STRATEGY_FAMILY_SMA,
    OptimizeGridTrial,
    OptimizeSmaGridResult,
    _attach_oos,
    _eval_oos_for_grid,
    _sma_to_grid,
    attach_lab_edge_report,
    rank_trials_for_result,
)


def _bars(n: int) -> list[BacktestBarInput]:
    start = datetime(2014, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + 0.1 * i + (3.0 if i % 19 < 9 else -1.5),
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Part 1 — pieces
# ---------------------------------------------------------------------------


def test_part_holdout_split_chronological() -> None:
    split = split_holdout_bars(_bars(300), 0.2)
    assert split is not None
    assert split.is_bar_count + split.oos_bar_count == 300
    assert split.is_bars[-1].timestamp < split.oos_bars[0].timestamp
    assert split.split_timestamp is not None


def test_part_sma_grid_sorted_by_is_score() -> None:
    trials = run_sma_grid_search(
        _bars(180),
        fast_periods=[8, 12, 16],
        slow_periods=[30, 40, 50],
        initial_cash=10_000,
        max_trials=40,
    )
    assert trials
    scores = [t.score for t in trials]
    assert scores == sorted(scores, reverse=True)


def test_part_oos_warmup_changes_cold_start() -> None:
    bars = _bars(400)
    split = 280
    cold = _eval_oos_for_grid(
        OptimizeGridTrial(
            total_return_pct=0,
            max_drawdown_pct=0,
            trade_count=0,
            score=0,
            params={"fastPeriod": 12, "slowPeriod": 35},
        ),
        family=STRATEGY_FAMILY_SMA,
        is_bars=[],
        oos_bars=bars[split:],
        initial_cash=10_000,
    )
    warm = _eval_oos_for_grid(
        OptimizeGridTrial(
            total_return_pct=0,
            max_drawdown_pct=0,
            trade_count=0,
            score=0,
            params={"fastPeriod": 12, "slowPeriod": 35},
        ),
        family=STRATEGY_FAMILY_SMA,
        is_bars=bars[:split],
        oos_bars=bars[split:],
        initial_cash=10_000,
    )
    assert cold.oos_metrics is not None
    assert warm.oos_metrics is not None
    assert cold.oos_metrics["score"] != warm.oos_metrics["score"] or cold.oos_metrics[
        "tradeCount"
    ] != warm.oos_metrics["tradeCount"]


def test_part_walk_forward_expanding_trains() -> None:
    folds = split_walk_forward_bars(_bars(400), 3)
    assert len(folds) == 3
    assert folds[0].train_bar_count < folds[1].train_bar_count < folds[2].train_bar_count
    assert folds[-1].train_bar_count + folds[-1].test_bar_count == 400


def test_part_aggregate_oos_scores() -> None:
    summary = aggregate_walk_forward_metrics(
        is_scores=[8.0, 10.0, 12.0],
        oos_scores=[4.0, 6.0, 5.0],
    )
    assert summary["foldCount"] == 3
    assert summary["meanOosScore"] == 5.0
    assert summary["stdOosScore"] > 0
    assert summary["meanIsScore"] == 10.0
    assert summary["walkForwardEfficiency"] == 0.5
    assert summary["positiveOosFoldShare"] == 1.0


def _trial(
    *,
    score: float,
    oos_score: float | None = None,
    oos_trades: int = 5,
    params: dict | None = None,
) -> OptimizeGridTrial:
    oos = None
    if oos_score is not None:
        oos = {
            "totalReturnPct": oos_score,
            "maxDrawdownPct": 0.0,
            "tradeCount": oos_trades,
            "score": oos_score,
        }
    return OptimizeGridTrial(
        total_return_pct=score,
        max_drawdown_pct=0.0,
        trade_count=10,
        score=score,
        params=params or {"fastPeriod": 10, "slowPeriod": 30},
        oos_metrics=oos,
    )


def test_part_rank_trials_prefers_oos_when_present() -> None:
    ranked = rank_trials_for_result(
        [
            _trial(score=90.0, oos_score=-5.0, params={"id": "is"}),
            _trial(score=10.0, oos_score=12.0, params={"id": "oos"}),
        ]
    )
    assert ranked[0].params["id"] == "oos"


def test_part_rank_trials_penalizes_sparse_oos() -> None:
    ranked = rank_trials_for_result(
        [
            _trial(score=50.0, oos_score=20.0, oos_trades=1, params={"id": "sparse"}),
            _trial(score=40.0, oos_score=8.0, oos_trades=5, params={"id": "dense"}),
        ]
    )
    assert ranked[0].params["id"] == "dense"


def test_part_rank_trials_falls_back_to_is() -> None:
    ranked = rank_trials_for_result(
        [
            _trial(score=5.0, params={"id": "low"}),
            _trial(score=40.0, params={"id": "high"}),
        ]
    )
    assert ranked[0].params["id"] == "high"


# ---------------------------------------------------------------------------
# Part 2 — assembly (lab flow without HTTP)
# ---------------------------------------------------------------------------


def test_assembly_holdout_grid_then_rank_by_oos() -> None:
    """IS search → attach warmed OOS → API order = Mejor OOS (not peak IS)."""
    bars = _bars(360)
    holdout = split_holdout_bars(bars, 0.25)
    assert holdout is not None

    raw = run_sma_grid_search(
        holdout.is_bars,
        fast_periods=[8, 12, 16, 20],
        slow_periods=[30, 40, 50, 60],
        initial_cash=10_000,
        max_trials=30,
    )
    assert len(raw) >= 3
    trials = [_sma_to_grid(t) for t in raw]
    baseline = trials[0]
    _, with_oos = _attach_oos(
        baseline,
        trials,
        family=STRATEGY_FAMILY_SMA,
        holdout=holdout,
        initial_cash=10_000,
    )
    assert all(t.oos_metrics is not None for t in with_oos)

    ranked = rank_trials_for_result(with_oos)
    top = ranked[0]
    assert top.oos_metrics is not None
    top_key = float(top.oos_metrics["score"])
    if int(top.oos_metrics.get("tradeCount") or 0) < 2:
        top_key -= 1000.0
    for trial in ranked[1:]:
        assert trial.oos_metrics is not None
        key = float(trial.oos_metrics["score"])
        if int(trial.oos_metrics.get("tradeCount") or 0) < 2:
            key -= 1000.0
        assert top_key >= key

    result = OptimizeSmaGridResult(
        instrument_id="inst-battery",
        bar_count=len(bars),
        baseline=with_oos[0],
        trials=ranked,
        engine="h0",
        trials_total=len(with_oos),
        strategy_family=STRATEGY_FAMILY_SMA,
        oos_pct=holdout.oos_pct,
        is_bar_count=holdout.is_bar_count,
        oos_bar_count=holdout.oos_bar_count,
        split_timestamp=holdout.split_timestamp,
        walk_forward=None,
    )
    payload = optimize_result_to_dict(result)
    assert payload["oosPct"] == holdout.oos_pct
    assert payload["splitTimestamp"] == holdout.split_timestamp
    assert payload["trials"][0]["oosMetrics"]["score"] is not None
    assert "fastPeriod" in payload["trials"][0]


def test_assembly_walk_forward_selected_bests() -> None:
    """Each fold: search train → eval best on test with warm-up → aggregate."""
    bars = _bars(420)
    folds = split_walk_forward_bars(bars, 3)
    oos_scores: list[float] = []
    is_scores: list[float] = []
    reports: list[dict] = []

    for fold in folds:
        raw = run_sma_grid_search(
            fold.train_bars,
            fast_periods=[10, 14],
            slow_periods=[30, 45],
            initial_cash=10_000,
            max_trials=12,
        )
        assert raw
        best = _sma_to_grid(raw[0])
        evaluated = _eval_oos_for_grid(
            best,
            family=STRATEGY_FAMILY_SMA,
            is_bars=fold.train_bars,
            oos_bars=fold.test_bars,
            initial_cash=10_000,
        )
        assert evaluated.oos_metrics is not None
        oos_scores.append(float(evaluated.oos_metrics["score"]))
        is_scores.append(float(best.score))
        reports.append(
            {
                "index": fold.index,
                "isScore": best.score,
                "oosScore": evaluated.oos_metrics["score"],
                "bestParams": evaluated.params,
            }
        )

    summary = aggregate_walk_forward_metrics(is_scores=is_scores, oos_scores=oos_scores)
    assert summary["foldCount"] == 3
    assert len(reports) == 3
    assert "walkForwardEfficiency" in summary
    assert "oosCv" in summary

    result = OptimizeSmaGridResult(
        instrument_id="inst-wf",
        bar_count=len(bars),
        baseline=OptimizeGridTrial(0, 0, 0, 0, params={"fastPeriod": 20, "slowPeriod": 50}),
        trials=[],
        engine="wf_h0",
        trials_total=36,
        strategy_family=STRATEGY_FAMILY_SMA,
        walk_forward={"nFolds": 3, "mode": "expanding", "folds": reports, **summary},
    )
    payload = optimize_result_to_dict(result)
    assert payload["walkForward"]["nFolds"] == 3
    assert payload["walkForward"]["meanOosScore"] == summary["meanOosScore"]
    assert payload["walkForward"]["walkForwardEfficiency"] == summary["walkForwardEfficiency"]


def test_assembly_lab_edge_report_on_holdout_champion() -> None:
    bars = _bars(360)
    holdout = split_holdout_bars(bars, 0.25)
    assert holdout is not None
    raw = run_sma_grid_search(
        holdout.is_bars,
        fast_periods=[8, 12, 16],
        slow_periods=[30, 40, 50],
        initial_cash=10_000,
        max_trials=20,
    )
    trials = [_sma_to_grid(t) for t in raw]
    _, with_oos = _attach_oos(
        trials[0],
        trials,
        family=STRATEGY_FAMILY_SMA,
        holdout=holdout,
        initial_cash=10_000,
    )
    ranked = rank_trials_for_result(with_oos)
    result = OptimizeSmaGridResult(
        instrument_id="inst-edge",
        bar_count=len(bars),
        baseline=ranked[0],
        trials=ranked,
        engine="h0",
        trials_total=len(ranked),
        strategy_family=STRATEGY_FAMILY_SMA,
        oos_pct=holdout.oos_pct,
    )
    with_edge = attach_lab_edge_report(
        result,
        family=STRATEGY_FAMILY_SMA,
        is_bars=holdout.is_bars,
        oos_bars=holdout.oos_bars,
        initial_cash=10_000,
    )
    # EdgeReport requires ≥3 closed round-trips on champion OOS; may be None on sparse series.
    if with_edge.edge_report is not None:
        assert with_edge.edge_report["mode"] == "lab_lite"
        assert "suite" in with_edge.edge_report
        payload = optimize_result_to_dict(with_edge)
        assert payload["edgeReport"]["band"] in {"skill", "uncertain", "luck"}


def test_assembly_trials_total_scales_with_walk_forward() -> None:
    base = {
        "strategyFamily": "sma_crossover",
        "fastPeriods": [10, 15, 20],
        "slowPeriods": [40, 50, 60],
        "maxTrials": 80,
        "engine": "h0",
    }
    without = estimate_trials_total_from_payload(base)
    with_wf = estimate_trials_total_from_payload({**base, "walkForwardFolds": 3})
    assert with_wf == without * 3


def test_assembly_trials_total_scales_with_cpcv() -> None:
    base = {
        "strategyFamily": "sma_crossover",
        "fastPeriods": [10, 15, 20],
        "slowPeriods": [40, 50, 60],
        "maxTrials": 80,
        "engine": "h0",
    }
    without = estimate_trials_total_from_payload(base)
    with_cpcv = estimate_trials_total_from_payload({**base, "cpcvGroups": 5})
    assert with_cpcv == without * 10  # C(5,2)


def test_assembly_pbo_cscv_from_score_matrix() -> None:
    from bolsa_analytics.optimize.pbo import estimate_pbo_cscv
    import numpy as np

    matrix = np.zeros((4, 5))
    matrix[:, 0] = 10.0
    matrix[:, 1:] = np.linspace(-1, 1, 4 * 4).reshape(4, 4)
    summary = estimate_pbo_cscv(matrix)
    assert summary["mode"] == "cscv_lab"
    assert summary["splitCount"] == 6
    payload = {"pbo": summary}
    assert payload["pbo"]["pbo"] <= 0.5


def test_assembly_cpcv_summary_serializes() -> None:
    from bolsa_analytics.optimize.cpcv import aggregate_cpcv_metrics

    summary = aggregate_cpcv_metrics(is_scores=[8.0, 10.0], oos_scores=[4.0, 6.0])
    result = OptimizeSmaGridResult(
        instrument_id="inst-cpcv",
        bar_count=600,
        baseline=OptimizeGridTrial(0, 0, 0, 0, params={"fastPeriod": 12, "slowPeriod": 40}),
        trials=[],
        engine="cpcv_h0",
        trials_total=100,
        strategy_family=STRATEGY_FAMILY_SMA,
        cpcv={
            "nGroups": 5,
            "nTestGroups": 2,
            "purgeBars": 5,
            "embargoBars": 5,
            "pathCount": 2,
            "mode": "combinatorial_purged",
            "paths": [],
            **summary,
        },
    )
    payload = optimize_result_to_dict(result)
    assert payload["cpcv"]["mode"] == "combinatorial_purged"
    assert payload["cpcv"]["walkForwardEfficiency"] == summary["walkForwardEfficiency"]


def test_assembly_payload_to_kwargs_includes_walk_forward() -> None:
    from bolsa_application.optimization_runs import _payload_to_execute_kwargs

    kwargs = _payload_to_execute_kwargs(
        {
            "instrumentId": "x",
            "oosPct": 0.2,
            "walkForwardFolds": 4,
            "strategyFamily": "sma_crossover",
        }
    )
    assert kwargs["oos_pct"] == 0.2
    assert kwargs["walk_forward_folds"] == 4
    assert kwargs["instrument_id"] == "x"


def test_assembly_payload_to_kwargs_includes_cpcv() -> None:
    from bolsa_application.optimization_runs import _payload_to_execute_kwargs

    kwargs = _payload_to_execute_kwargs(
        {
            "instrumentId": "y",
            "cpcvGroups": 5,
            "cpcvPurgeBars": 8,
            "cpcvEmbargoBars": 3,
            "strategyFamily": "sma_crossover",
        }
    )
    assert kwargs["cpcv_groups"] == 5
    assert kwargs["cpcv_purge_bars"] == 8
    assert kwargs["cpcv_embargo_bars"] == 3
