"""
IBEX 35 research battery — Baseline v1.5 exploitation.

Uses the same application use-cases as POST /backtests/run (causal H0 engine:
bar-by-bar gated signals; no future peek). Writes backtest_runs + research_trials.

Usage (repo root, .env loaded):
  python scripts/research/run_ibex35_battery.py
  python scripts/research/run_ibex35_battery.py --limit 10 --presets sma_crossover
  python scripts/research/run_ibex35_battery.py --optimize-top 3

Future: this is the seed of a professional ResearchBattery job (list-scoped,
cost-aware, ledger-first). Day-by-day paper simulation with order rationale
belongs to a later GUI/forward layer — not this script.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
    parser = argparse.ArgumentParser(description="Run IBEX 35 research battery into ledger K")
    parser.add_argument("--list-id", default="ibex35", help="Catalog list id (default ibex35)")
    parser.add_argument(
        "--presets",
        nargs="+",
        default=["sma_crossover", "rsi_mean_reversion"],
        help="Strategy presets to run per instrument",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max instruments (0 = all)")
    parser.add_argument("--bar-limit", type=int, default=500)
    parser.add_argument("--initial-cash", type=float, default=10000.0)
    parser.add_argument("--commission-bps", type=int, default=10)
    parser.add_argument("--slippage-bps", type=int, default=5)
    parser.add_argument("--spread-bps", type=int, default=2)
    parser.add_argument(
        "--optimize-top",
        type=int,
        default=0,
        help="Also run SMA grid optimize on first N instruments with data",
    )
    parser.add_argument("--optimize-max-trials", type=int, default=40)
    parser.add_argument(
        "--optimize-only",
        action="store_true",
        help="Skip per-preset backtests; only run optimize grids",
    )
    parser.add_argument(
        "--skip-if-grid",
        action="store_true",
        help="Skip optimize on instruments that already have proposed_by=grid trials",
    )
    args = parser.parse_args()

    _load_env()

    from bolsa_application.backtests import RunAndSaveBacktest
    from bolsa_application.optimization_runs import RunSmaGridOptimizeAndSave
    from bolsa_application.optimize import RunSmaGridOptimize
    from bolsa_application.research_trials import GetLaboratoryResearchSummary
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
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    ok = 0
    skipped = 0
    failed = 0
    optimize_ok = 0
    results: list[dict] = []

    async with factory() as session:
        lists = SqlAlchemyListRepository(session)
        detail = await lists.get_by_id(args.list_id)
        if detail is None:
            # Fallback: find by name
            for summary in await lists.list_all():
                if summary.name.upper().startswith("IBEX"):
                    detail = await lists.get_by_id(summary.id)
                    break
        if detail is None or not detail.instrument_ids:
            print(f"ERROR: lista '{args.list_id}' no encontrada o vacía", file=sys.stderr)
            await engine.dispose()
            return 1

        instrument_ids = detail.instrument_ids
        if args.limit > 0:
            instrument_ids = instrument_ids[: args.limit]

        print(
            f"Lista {detail.name} ({detail.id}): {len(instrument_ids)} instrumentos · "
            f"presets={args.presets} · costes "
            f"c={args.commission_bps}/s={args.slippage_bps}/sp={args.spread_bps} bps"
        )

        instruments = SqlAlchemyInstrumentRepository(session)
        ohlcv = SqlAlchemyOhlcvRepository(session)
        backtests = SqlAlchemyBacktestRepository(session)
        strategies = SqlAlchemyStrategyDefinitionRepository(session)
        trials = SqlAlchemyResearchTrialRepository(session)

        run_bt = RunAndSaveBacktest(instruments, ohlcv, backtests, strategies, trials)

        ready_for_optimize: list[str] = []

        if args.optimize_only:
            ready_for_optimize = list(instrument_ids)
            print("Mode: optimize-only (no per-preset backtests)")
        else:
            for idx, instrument_id in enumerate(instrument_ids, start=1):
                inst = await instruments.get_by_id(instrument_id)
                symbol = inst.symbol if inst else instrument_id[:8]
                for preset in args.presets:
                    try:
                        result = await run_bt.execute(
                            instrument_id=instrument_id,
                            strategy_type=preset,  # type: ignore[arg-type]
                            initial_cash=args.initial_cash,
                            limit=args.bar_limit,
                            timeframe="1d",
                            commission_bps=args.commission_bps,
                            slippage_bps=args.slippage_bps,
                            spread_bps=args.spread_bps,
                        )
                        await session.commit()
                        ok += 1
                        sharpe = result.metrics.get("sharpeRatio")
                        pnl = result.metrics.get("totalReturnPct")
                        print(
                            f"[{idx}/{len(instrument_ids)}] {symbol:6} {preset:22} "
                            f"trial={result.trial_id[:12]}… "
                            f"PnL={pnl} Sharpe={sharpe} K+=1"
                        )
                        results.append(
                            {
                                "symbol": symbol,
                                "preset": preset,
                                "trialId": result.trial_id,
                                "runId": result.run.id,
                                "pnl": pnl,
                                "sharpe": sharpe,
                            }
                        )
                        if instrument_id not in ready_for_optimize:
                            ready_for_optimize.append(instrument_id)
                    except ValueError as exc:
                        skipped += 1
                        print(f"[{idx}/{len(instrument_ids)}] {symbol:6} {preset:22} SKIP: {exc}")
                        await session.rollback()
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        print(
                            f"[{idx}/{len(instrument_ids)}] {symbol:6} {preset:22} FAIL: {exc}",
                            file=sys.stderr,
                        )
                        await session.rollback()

        optimize_n = args.optimize_top if args.optimize_top > 0 else (len(ready_for_optimize) if args.optimize_only else 0)
        if optimize_n > 0 and ready_for_optimize:
            targets = ready_for_optimize[:optimize_n]
            print(
                f"\nOptimize SMA grid on up to {len(targets)} instruments "
                f"(maxTrials={args.optimize_max_trials}, skip_if_grid={args.skip_if_grid})…"
            )
            optimize_uc = RunSmaGridOptimize(instruments, ohlcv)
            save_uc = RunSmaGridOptimizeAndSave(
                optimize_uc,
                SqlAlchemyOptimizationRunRepository(session),
                trials,
            )
            for instrument_id in targets:
                inst = await instruments.get_by_id(instrument_id)
                symbol = inst.symbol if inst else instrument_id[:8]
                if args.skip_if_grid:
                    existing, _ = await trials.list_trials(
                        instrument_id=instrument_id,
                        proposed_by="grid",
                        limit=1,
                        offset=0,
                    )
                    if existing:
                        skipped += 1
                        print(f"  OPT {symbol:6} SKIP: already has grid trials")
                        continue
                try:
                    result, saved = await save_uc.execute(
                        instrument_id=instrument_id,
                        initial_cash=args.initial_cash,
                        bar_limit=args.bar_limit,
                        timeframe="1d",
                        max_trials=args.optimize_max_trials,
                        engine="h0",
                    )
                    await session.commit()
                    optimize_ok += 1
                    print(
                        f"  OPT {symbol:6} run={saved.id[:12]}… "
                        f"trials={len(result.trials)} bestScore={result.baseline.score:.2f}"
                    )
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  OPT {symbol:6} FAIL: {exc}", file=sys.stderr)
                    await session.rollback()

        lab = await GetLaboratoryResearchSummary(trials).execute()
        print("\n=== Laboratorio (summary) ===")
        print(
            f"totalTrials={lab['totalTrials']}  totalK={lab['totalK']}  "
            f"instruments={lab['activeInstruments']}  avgSharpe={lab['avgSharpe']}"
        )
        print(f"byOrigin={lab['byOrigin']}")
        print(
            f"\nBattery done: ok={ok} skipped={skipped} failed={failed} optimize_ok={optimize_ok}"
        )

    await engine.dispose()
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(_main()))
