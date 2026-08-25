"""P8 — lab EdgeReport lite → cognitive edge_reports (no auto-live)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_analytics.cognitive.edge_report import StatisticalSuiteResult

from bolsa_application.optimization_runs import ProcessOptimizationRun
from bolsa_application.optimize import OptimizeGridTrial, OptimizeSmaGridResult
from bolsa_application.persist_lab_edge_report import (
    LAB_PERSIST_NOTE,
    lab_edge_report_notes,
    lab_edge_report_to_suite,
    persist_lab_edge_report_if_present,
    stamp_persisted_edge_report_id,
)


def _lab_edge_report(**overrides):
    base = {
        "artifactType": "ART-EDGE-REPORT",
        "schemaVersion": "1.0.0",
        "edgeReportId": "EDGE-lab-temp",
        "strategyOrSignalRef": "sma_crossover:inst-1",
        "credibility": 62.0,
        "edgeScore": 55.0,
        "band": "uncertain",
        "notes": ["lab suite"],
        "autoLiveEligible": True,
        "blockReasons": ["sample"],
        "suite": {
            "trialsN": 12,
            "walkForwardEfficiency": 0.7,
            "wfeSource": "lab_score",
            "monteCarloPValue": 0.02,
            "psr": 0.6,
            "dsr": 0.55,
            "historicalWinRate": 0.5,
            "sampleTradesCount": 8,
        },
        "sampleTradesCount": 8,
        "mode": "lab_lite",
        "pbo": 0.4,
    }
    base.update(overrides)
    return base


def test_lab_edge_report_to_suite_maps_fields():
    suite = lab_edge_report_to_suite(_lab_edge_report())
    assert isinstance(suite, StatisticalSuiteResult)
    assert suite.trials_n == 12
    assert suite.walk_forward_efficiency == 0.7
    assert suite.wfe_source == "lab_score"
    assert suite.monte_carlo_p_value == 0.02
    assert suite.dsr == 0.55


def test_lab_edge_report_to_suite_rejects_empty():
    assert lab_edge_report_to_suite(None) is None
    assert lab_edge_report_to_suite({"band": "luck"}) is None


def test_notes_mark_no_auto_live():
    notes = lab_edge_report_notes(
        _lab_edge_report(),
        optimization_run_id="opt-1",
    )
    joined = " ".join(notes)
    assert LAB_PERSIST_NOTE in notes
    assert "optimizationRunId=opt-1" in notes
    assert "autoLiveEligible=ignored" in notes
    assert "pbo=" in joined


def test_stamp_clears_auto_live():
    stamped = stamp_persisted_edge_report_id(_lab_edge_report(autoLiveEligible=True), "EDGE-pg-1")
    assert stamped is not None
    assert stamped["persistedEdgeReportId"] == "EDGE-pg-1"
    assert stamped["autoLiveEligible"] is False
    assert "lab_persist_no_auto_live" in stamped["blockReasons"]


@pytest.mark.asyncio
async def test_persist_lab_edge_report_calls_store_without_auto_trial():
    store = AsyncMock()
    store.append_edge_report = AsyncMock(
        side_effect=lambda rec: MagicMock(id=rec.id or "EDGE-saved"),
    )
    # PersistEdgeReport builds report then calls append_edge_report with EdgeReportRecord
    store.append_edge_report = AsyncMock(
        side_effect=lambda rec: MagicMock(
            id=rec.id,
            notes=rec.notes,
            suite=rec.suite,
        )
    )
    store.append_trial = AsyncMock()

    persisted = await persist_lab_edge_report_if_present(
        store,
        _lab_edge_report(),
        optimization_run_id="run-9",
        auto_trial=False,
    )
    assert persisted is not None
    store.append_edge_report.assert_awaited_once()
    store.append_trial.assert_not_awaited()
    rec = store.append_edge_report.await_args.args[0]
    assert rec.strategy_or_signal_ref == "sma_crossover:inst-1"
    assert rec.suite["trialsN"] == 12
    assert rec.suite.get("wfeSource") == "lab_score"
    assert any("not auto-live" in n for n in rec.notes)


@pytest.mark.asyncio
async def test_process_optimization_run_persists_edge_report():
    trial = OptimizeGridTrial(
        total_return_pct=5.0,
        max_drawdown_pct=2.0,
        trade_count=8,
        score=4.5,
        params={"fastPeriod": 10, "slowPeriod": 50},
        is_metrics={"sharpeRatio": 1.0},
        oos_metrics={"score": 2.0, "totalReturnPct": 1.0, "maxDrawdownPct": 1.0, "tradeCount": 3},
    )
    optimize_result = OptimizeSmaGridResult(
        instrument_id="inst-1",
        bar_count=100,
        engine="sma_grid_h0",
        trials_total=1,
        baseline=trial,
        trials=[trial],
        strategy_family="sma_crossover",
        oos_pct=0.2,
        is_bar_count=80,
        oos_bar_count=20,
        edge_report=_lab_edge_report(),
    )

    run = MagicMock()
    run.id = "run-1"
    run.payload = {
        "instrumentId": "inst-1",
        "engine": "h0",
        "initialCash": 10000,
        "barLimit": 100,
        "timeframe": "1d",
        "maxTrials": 10,
        "strategyFamily": "sma_crossover",
        "oosPct": 0.2,
    }

    repo = MagicMock()
    repo.claim_by_id = AsyncMock(return_value=run)
    repo.update_progress = AsyncMock()
    repo.mark_completed = AsyncMock(return_value=run)
    optimize = MagicMock()
    optimize.execute = AsyncMock(return_value=optimize_result)
    trials = MagicMock()
    trials.insert_trial = AsyncMock()

    cognitive = AsyncMock()
    cognitive.append_edge_report = AsyncMock(
        side_effect=lambda rec: MagicMock(id=rec.id, notes=rec.notes, suite=rec.suite)
    )
    cognitive.append_trial = AsyncMock()

    use_case = ProcessOptimizationRun(repo, optimize, trials, cognitive)
    out = await use_case.execute("run-1")
    assert out.status == "completed"
    cognitive.append_edge_report.assert_awaited_once()
    cognitive.append_trial.assert_not_awaited()
    saved = repo.mark_completed.await_args.kwargs["result"]
    assert saved["edgeReport"]["persistedEdgeReportId"]
    assert saved["edgeReport"]["autoLiveEligible"] is False
    blocks = trials.insert_trial.await_args.kwargs["blocks"]
    assert blocks["edgeReport"]["persistedEdgeReportId"]
