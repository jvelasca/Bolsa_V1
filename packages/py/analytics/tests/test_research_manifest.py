from bolsa_analytics.research.data_snapshot import BarFingerprint, compute_data_version
from bolsa_analytics.research.manifest import build_run_manifest


def test_compute_data_version_stable() -> None:
    bars = [
        BarFingerprint(timestamp="2024-01-01", close=100.0),
        BarFingerprint(timestamp="2024-01-02", close=101.5),
    ]
    v1 = compute_data_version(bars)
    v2 = compute_data_version(bars)
    assert v1 == v2
    assert v1.startswith("sha256:")


def test_build_run_manifest_shape() -> None:
    bars = [BarFingerprint(timestamp=f"2024-01-{d:02d}", close=100.0 + d) for d in range(1, 61)]
    manifest = build_run_manifest(
        run_id="run_test",
        instrument_id="inst_1",
        strategy_type="sma_crossover",
        bars=bars,
        timeframe="1d",
        initial_cash=10000,
        commission_bps=10,
        slippage_bps=5,
        total_return_pct=5.5,
        max_drawdown_pct=2.1,
        trade_count=4,
        final_equity=10550,
    )
    assert manifest["manifestVersion"] == "1.0"
    assert manifest["runId"] == "run_test"
    assert manifest["dataSnapshot"]["barCount"] == 60
    assert manifest["strategy"]["presetKey"] == "sma_crossover"
    assert manifest["strategy"]["execution"]["commissionBps"] == 10
    assert manifest["outputs"]["tradeCount"] == 4


def test_build_run_manifest_includes_equity_curve() -> None:
    bars = [BarFingerprint(timestamp=f"2024-01-{d:02d}", close=100.0 + d) for d in range(1, 4)]
    curve = [
        {"timestamp": "2024-01-01", "equity": 10000},
        {"timestamp": "2024-01-02", "equity": 10050},
        {"timestamp": "2024-01-03", "equity": 10100},
    ]
    manifest = build_run_manifest(
        run_id="run_test",
        instrument_id="inst_1",
        strategy_type="sma_crossover",
        bars=bars,
        timeframe="1d",
        initial_cash=10000,
        commission_bps=0,
        slippage_bps=0,
        total_return_pct=1.0,
        max_drawdown_pct=0.0,
        trade_count=0,
        final_equity=10100,
        equity_curve=curve,
    )
    assert manifest["outputs"]["equityCurve"] == curve
