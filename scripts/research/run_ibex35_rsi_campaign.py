"""
Campaign 2 — IBEX 35 RSI family (human presets + RSI mean-reversion grid).

Same methodology as SMA campaign: list-scoped, ledger K, lab notebook afterwards.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RSI_PRESETS = ("rsi_mean_reversion", "rsi_momentum", "rsi_oversold_bounce")


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="IBEX35 Campaign 2 — RSI family")
    parser.add_argument("--list-id", default="ibex35")
    parser.add_argument("--presets", nargs="+", default=list(RSI_PRESETS))
    parser.add_argument("--limit", type=int, default=0, help="Max instruments (0 = all)")
    parser.add_argument("--bar-limit", type=int, default=500)
    parser.add_argument("--initial-cash", type=float, default=10000.0)
    parser.add_argument("--commission-bps", type=int, default=10)
    parser.add_argument("--slippage-bps", type=int, default=5)
    parser.add_argument("--spread-bps", type=int, default=2)
    parser.add_argument("--max-grid-trials", type=int, default=25)
    parser.add_argument(
        "--skip-existing-human",
        action="store_true",
        default=True,
        help="Skip human preset if instrument already has that preset_key (default on)",
    )
    parser.add_argument("--no-skip-existing-human", action="store_true")
    parser.add_argument("--human-only", action="store_true")
    parser.add_argument("--grid-only", action="store_true")
    parser.add_argument(
        "--campaign-id",
        default="ibex35-rsi-c2",
        help="Tag params.campaign + campaign_manifest_v0 (Q0.2 / Q1.2)",
    )
    parser.add_argument("--date-from", default=None, help="Dataset window start (ISO date)")
    parser.add_argument("--date-to", default=None, help="Dataset window end (ISO date)")
    parser.add_argument(
        "--write-manifest",
        type=Path,
        default=None,
        help="Write campaign_manifest_v0 JSON (default research/campaigns/<id>.json if set)",
    )
    args = parser.parse_args()
    skip_existing = args.skip_existing_human and not args.no_skip_existing_human

    _load_env()

    from bolsa_analytics.backtest import BacktestBarInput
    from bolsa_analytics.optimize.rsi_grid import run_rsi_mean_reversion_grid
    from bolsa_analytics.warmup_matrix import WarmupInsufficientError
    from bolsa_application.backtests import RunAndSaveBacktest
    from bolsa_application.campaign_manifest import (
        build_campaign_manifest,
        write_campaign_manifest,
    )
    from bolsa_application.research_trials import GetLaboratoryResearchSummary
    from bolsa_domain.value_objects.timeframe import TimeFrame
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.backtest_repository import (
        SqlAlchemyBacktestRepository,
    )
    from bolsa_infrastructure.database.repositories.instrument_repository import (
        SqlAlchemyInstrumentRepository,
    )
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (
        SqlAlchemyOhlcvRepository,
    )
    from bolsa_infrastructure.database.repositories.optimization_run_repository import (
        SqlAlchemyOptimizationRunRepository,
    )
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )
    from bolsa_infrastructure.database.repositories.strategy_definition_repository import (
        SqlAlchemyStrategyDefinitionRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)

    human_ok = 0
    human_skip = 0
    grid_ok = 0
    grid_trials_total = 0
    failed = 0

    async with factory() as session:
        lists = SqlAlchemyListRepository(session)
        detail = await lists.get_by_id(args.list_id)
        if detail is None:
            for summary in await lists.list_all():
                if summary.name.upper().startswith("IBEX"):
                    detail = await lists.get_by_id(summary.id)
                    break
        if detail is None or not detail.instrument_ids:
            print(f"ERROR: lista '{args.list_id}' vacía", file=sys.stderr)
            await engine.dispose()
            return 1

        instrument_ids = list(detail.instrument_ids)
        if args.limit and args.limit > 0:
            instrument_ids = instrument_ids[: args.limit]

        instruments = SqlAlchemyInstrumentRepository(session)
        ohlcv = SqlAlchemyOhlcvRepository(session)
        backtests = SqlAlchemyBacktestRepository(session)
        strategies = SqlAlchemyStrategyDefinitionRepository(session)
        trials = SqlAlchemyResearchTrialRepository(session)
        opt_runs = SqlAlchemyOptimizationRunRepository(session)
        run_bt = RunAndSaveBacktest(instruments, ohlcv, backtests, strategies, trials)

        print(
            f"Campaign 2 RSI · {detail.name} · {len(instrument_ids)} instruments · "
            f"presets={args.presets} · grid_max={args.max_grid_trials}"
        )

        if not args.grid_only:
            for idx, instrument_id in enumerate(instrument_ids, start=1):
                inst = await instruments.get_by_id(instrument_id)
                symbol = inst.symbol if inst else instrument_id[:8]
                for preset in args.presets:
                    if skip_existing:
                        existing, _ = await trials.list_trials(
                            instrument_id=instrument_id,
                            preset_key=preset,
                            proposed_by="human",
                            limit=1,
                        )
                        if existing:
                            human_skip += 1
                            print(f"[{idx}] {symbol:6} {preset:22} SKIP human (exists)")
                            continue
                    try:
                        result = await run_bt.execute(
                            instrument_id=instrument_id,
                            strategy_type=preset,  # type: ignore[arg-type]
                            campaign=args.campaign_id,
                            initial_cash=args.initial_cash,
                            limit=None if (args.date_from or args.date_to) else args.bar_limit,
                            date_from=args.date_from,
                            date_to=args.date_to,
                            timeframe="1d",
                            commission_bps=args.commission_bps,
                            slippage_bps=args.slippage_bps,
                            spread_bps=args.spread_bps,
                        )
                        await session.commit()
                        human_ok += 1
                        print(
                            f"[{idx}] {symbol:6} {preset:22} "
                            f"trial={result.trial_id[:12]}… "
                            f"PnL={result.metrics.get('totalReturnPct')} "
                            f"Sharpe={result.metrics.get('sharpeRatio')}"
                        )
                    except ValueError as exc:
                        human_skip += 1
                        print(f"[{idx}] {symbol:6} {preset:22} SKIP: {exc}")
                        await session.rollback()
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        print(f"[{idx}] {symbol:6} {preset:22} FAIL: {exc}", file=sys.stderr)
                        await session.rollback()

        if not args.human_only:
            print("\nRSI mean-reversion grid…")
            for idx, instrument_id in enumerate(instrument_ids, start=1):
                inst = await instruments.get_by_id(instrument_id)
                symbol = inst.symbol if inst else instrument_id[:8]
                try:
                    bars = await ohlcv.get_bars(
                        instrument_id,
                        timeframe=TimeFrame.D1,
                        limit=None if (args.date_from or args.date_to) else args.bar_limit,
                        date_from=args.date_from,
                        date_to=args.date_to,
                    )
                    inputs = [
                        BacktestBarInput(timestamp=bar.timestamp, close=bar.close) for bar in bars
                    ]
                    try:
                        grid_trials = run_rsi_mean_reversion_grid(
                            inputs,
                            initial_cash=args.initial_cash,
                            max_trials=args.max_grid_trials,
                        )
                    except WarmupInsufficientError as exc:
                        human_skip += 1
                        print(f"  GRID {symbol:6} SKIP: {exc}")
                        continue
                    grid_trials = sorted(grid_trials, key=lambda t: t.score, reverse=True)
                    campaign_manifest = build_campaign_manifest(
                        campaign_id=args.campaign_id,
                        universe=args.list_id,
                        engine="rsi_grid_h0",
                        dataset_start=args.date_from or (bars[0].timestamp if bars else None),
                        dataset_end=args.date_to or (bars[-1].timestamp if bars else None),
                        bar_count=len(bars),
                        commission_bps=args.commission_bps,
                        slippage_bps=args.slippage_bps,
                        spread_bps=args.spread_bps,
                        presets=list(args.presets),
                        repo_root=ROOT,
                    )
                    # Traceability: one optimization_runs row for the campaign job
                    payload = {
                        "instrumentId": instrument_id,
                        "family": "rsi_mean_reversion",
                        "campaign": args.campaign_id,
                        "maxTrials": args.max_grid_trials,
                        "engine": "rsi_grid_h0",
                    }
                    result_payload = {
                        "instrumentId": instrument_id,
                        "barCount": len(bars),
                        "engine": "rsi_grid_h0",
                        "trials": [
                            {
                                "period": t.period,
                                "oversold": t.oversold,
                                "overbought": t.overbought,
                                "totalReturnPct": t.total_return_pct,
                                "maxDrawdownPct": t.max_drawdown_pct,
                                "tradeCount": t.trade_count,
                                "score": t.score,
                            }
                            for t in grid_trials
                        ],
                    }
                    saved = await opt_runs.create_completed(payload, result_payload)
                    for trial in grid_trials:
                        await trials.insert_trial(
                            instrument_id=instrument_id,
                            optimization_run_id=saved.id,
                            preset_key="rsi_mean_reversion",
                            strategy_name="rsi_mean_reversion",
                            params={
                                "period": trial.period,
                                "oversold": trial.oversold,
                                "overbought": trial.overbought,
                                "engine": "rsi_grid_h0",
                                "campaign": args.campaign_id,
                                "barCount": len(bars),
                            },
                            is_metrics=dict(trial.is_metrics),
                            is_score=trial.score,
                            proposed_by="grid",
                            k_contribution=1,
                            manifest_ref={
                                **campaign_manifest.to_manifest_ref(),
                                "optimizationRunId": saved.id,
                            },
                        )
                    await session.commit()
                    grid_ok += 1
                    grid_trials_total += len(grid_trials)
                    best = max(grid_trials, key=lambda t: t.score) if grid_trials else None
                    best_s = f"{best.score:.2f}" if best else "—"
                    print(
                        f"  GRID {symbol:6} run={saved.id[:12]}… "
                        f"trials={len(grid_trials)} bestScore={best_s}"
                    )
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  GRID {symbol:6} FAIL: {exc}", file=sys.stderr)
                    await session.rollback()

        lab = await GetLaboratoryResearchSummary(trials).execute()
        print("\n=== Laboratorio ===")
        print(
            f"totalTrials={lab['totalTrials']} totalK={lab['totalK']} "
            f"instruments={lab['activeInstruments']}"
        )
        print(f"byOrigin={lab['byOrigin']}")
        print(
            f"\nCampaign {args.campaign_id} done: human_ok={human_ok} human_skip={human_skip} "
            f"grid_instruments={grid_ok} grid_trials={grid_trials_total} failed={failed}"
        )

        manifest_path = args.write_manifest
        if manifest_path is None and args.campaign_id:
            manifest_path = ROOT / "research" / "campaigns" / f"{args.campaign_id}.json"
        if manifest_path is not None:
            m = build_campaign_manifest(
                campaign_id=args.campaign_id,
                universe=args.list_id,
                engine="rsi_grid_h0",
                dataset_start=args.date_from,
                dataset_end=args.date_to,
                bar_count=args.bar_limit,
                commission_bps=args.commission_bps,
                slippage_bps=args.slippage_bps,
                spread_bps=args.spread_bps,
                presets=list(args.presets),
                notes=f"human_ok={human_ok} grid_trials={grid_trials_total}",
                repo_root=ROOT,
            )
            write_campaign_manifest(m, Path(manifest_path))
            print(f"Wrote manifest → {manifest_path}")

    await engine.dispose()
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(_main()))
