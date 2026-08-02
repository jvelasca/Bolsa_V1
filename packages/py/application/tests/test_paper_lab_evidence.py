"""P7 — lab evidence snapshot for paper deploy (piece tests)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_domain.entities.account import AccountScope, InvestmentAccount, InvestmentPortfolio

from bolsa_application.paper_bridge import DeployStrategyToPaperAccount
from bolsa_application.paper_lab_evidence import (
    LAB_EVIDENCE_SETTINGS_KEY,
    format_lab_evidence_compact,
    lab_evidence_snapshot_from_blocks,
    merge_lab_evidence_snapshots,
    trial_blocks_from_lab_evidence_snapshot,
)


def test_snapshot_cpcv_with_pbo_and_edge():
    snap = lab_evidence_snapshot_from_blocks(
        {
            "cpcv": {
                "meanOosScore": 2.4,
                "pathCount": 10,
                "walkForwardEfficiency": 0.65,
            },
            "pbo": {"pbo": 0.55},
            "edgeReport": {
                "credibility": 58,
                "band": "uncertain",
                "suite": {"monteCarloPValue": 0.02, "dsr": 0.7},
            },
        },
        trial_id="trial-1",
        source_backtest_run_id="run-1",
    )
    assert snap["kind"] == "cpcv"
    assert snap["meanOosScore"] == 2.4
    assert snap["pbo"] == 0.55
    assert snap["edgeBand"] == "uncertain"
    assert snap["trialId"] == "trial-1"
    assert "production" in snap["note"].lower() or "gate" in snap["note"].lower()
    assert "CPCV" in format_lab_evidence_compact(snap)


def test_snapshot_holdout():
    snap = lab_evidence_snapshot_from_blocks(
        {"oosMetrics": {"score": 4.2, "totalReturnPct": 3.1}},
    )
    assert snap["kind"] == "holdout"
    assert snap["oosScore"] == 4.2


def test_snapshot_none_without_blocks():
    snap = lab_evidence_snapshot_from_blocks(None, source_backtest_run_id="run-x")
    assert snap["kind"] == "none"
    assert snap["sourceBacktestRunId"] == "run-x"
    assert format_lab_evidence_compact(snap) == "Sin validación lab"


def test_merge_prefers_ledger_over_client_hint():
    from_blocks = lab_evidence_snapshot_from_blocks(
        {"cpcv": {"meanOosScore": 3.0, "walkForwardEfficiency": 0.7}},
        trial_id="t-ledger",
    )
    hint = {"kind": "holdout", "oosScore": 9.9}
    merged = merge_lab_evidence_snapshots(from_blocks, hint)
    assert merged["kind"] == "cpcv"
    assert merged["trialId"] == "t-ledger"


def test_merge_uses_client_hint_when_ledger_empty():
    from_blocks = lab_evidence_snapshot_from_blocks(None, source_backtest_run_id="run-1")
    hint = {"kind": "walkforward", "meanOosScore": 2.0, "walkForwardEfficiency": 0.8}
    merged = merge_lab_evidence_snapshots(from_blocks, hint)
    assert merged["kind"] == "walkforward"
    assert merged["sourceBacktestRunId"] == "run-1"


def test_trial_blocks_from_adopt_snapshot_cpcv():
    blocks = trial_blocks_from_lab_evidence_snapshot(
        {
            "kind": "cpcv",
            "meanOosScore": 2.4,
            "pathCount": 10,
            "walkForwardEfficiency": 0.65,
            "pbo": 0.55,
            "edgeBand": "uncertain",
            "credibility": 58,
            "persistedEdgeReportId": "EDGE-abc123",
        }
    )
    assert blocks is not None
    assert blocks["cpcv"]["meanOosScore"] == 2.4
    assert blocks["pbo"]["pbo"] == 0.55
    assert blocks["edgeReport"]["persistedEdgeReportId"] == "EDGE-abc123"
    assert blocks["labEvidence"]["mode"] == "adopt_provenance"


@pytest.mark.asyncio
async def test_deploy_merges_lab_evidence_from_trial_blocks():
    account = InvestmentAccount(
        id="acc-1",
        user_id=None,
        name="Paper",
        description=None,
        type="paper",
        status="active",
        currency="EUR",
        base_currency="EUR",
        initial_deposit=10_000.0,
        leverage=1.0,
        margin_call_level_pct=100.0,
        is_default=False,
        settings=None,
        strategy_definition_id="strat-1",
        source_backtest_run_id="run-1",
        created_at="2026-07-27T00:00:00Z",
        updated_at="2026-07-27T00:00:00Z",
        last_activity_at=None,
        lab_evidence=None,
    )
    portfolio = InvestmentPortfolio(
        id="port-1",
        account_id="acc-1",
        legacy_portfolio_id=None,
        name="p",
        description=None,
        strategy_tag="paper",
        sort_order=0,
        is_default=True,
    )
    account_repo = AsyncMock()
    account_repo.create_paper_account = AsyncMock(
        return_value=AccountScope(account=account, portfolio=portfolio, legacy_portfolio_id="leg"),
    )
    account_repo.merge_settings_json = AsyncMock(return_value={})
    account_repo.get_account = AsyncMock(
        return_value=InvestmentAccount(
            id="acc-1",
            user_id=None,
            name="Paper",
            description=None,
            type="paper",
            status="active",
            currency="EUR",
            base_currency="EUR",
            initial_deposit=10_000.0,
            leverage=1.0,
            margin_call_level_pct=100.0,
            is_default=False,
            settings=None,
            strategy_definition_id="strat-1",
            source_backtest_run_id="run-1",
            created_at="2026-07-27T00:00:00Z",
            updated_at="2026-07-27T00:00:00Z",
            last_activity_at=None,
            lab_evidence={"kind": "holdout", "oosScore": 1.5},
        ),
    )

    strategy = MagicMock()
    strategy.id = "strat-1"
    strategy.name = "SMA"
    strategy.preset_key = "sma_crossover"
    strategy.definition = {"execution": {"commissionBps": 5, "slippageBps": 2}}
    strategy_repo = AsyncMock()
    strategy_repo.get_definition = AsyncMock(return_value=strategy)

    run = MagicMock()
    run.strategy_definition_id = "strat-1"
    run.initial_cash = 10_000.0
    backtest_repo = AsyncMock()
    backtest_repo.get_run = AsyncMock(return_value=run)

    trial = MagicMock()
    trial.id = "trial-9"
    trial.blocks = {"oosMetrics": {"score": 1.5, "totalReturnPct": 2}}
    trial_repo = AsyncMock()
    trial_repo.list_trials = AsyncMock(return_value=([trial], 1))

    use_case = DeployStrategyToPaperAccount(
        account_repo,
        strategy_repo,
        backtest_repo,
        trial_repo,
    )
    result = await use_case.execute(
        strategy_definition_id="strat-1",
        source_backtest_run_id="run-1",
    )

    account_repo.merge_settings_json.assert_awaited_once()
    args = account_repo.merge_settings_json.await_args
    assert args.args[0] == "acc-1"
    fragment = args.args[1]
    assert LAB_EVIDENCE_SETTINGS_KEY in fragment
    assert fragment[LAB_EVIDENCE_SETTINGS_KEY]["kind"] == "holdout"
    assert fragment[LAB_EVIDENCE_SETTINGS_KEY]["oosScore"] == 1.5
    assert fragment[LAB_EVIDENCE_SETTINGS_KEY]["trialId"] == "trial-9"
    assert result.lab_evidence is not None
