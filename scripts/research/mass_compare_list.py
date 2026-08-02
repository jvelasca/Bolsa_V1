#!/usr/bin/env python3
"""Q3.3 — comparación masiva CLI: lista × presets → ranking Sharpe.

Usage:
  python scripts/research/mass_compare_list.py --list-id ibex35 --limit 5 \\
    --presets sma_crossover rsi_mean_reversion --date-from 2022-01-01 --date-to 2023-12-31
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
    p = argparse.ArgumentParser(description="Mass compare list × presets")
    p.add_argument("--list-id", default="ibex35")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument(
        "--presets",
        nargs="+",
        default=["sma_crossover", "rsi_mean_reversion", "macd_signal_cross"],
    )
    p.add_argument("--date-from", default=None)
    p.add_argument("--date-to", default=None)
    p.add_argument("--bar-limit", type=int, default=500)
    p.add_argument("--initial-cash", type=float, default=10_000.0)
    p.add_argument("--commission-bps", type=int, default=10)
    p.add_argument("--slippage-bps", type=int, default=5)
    p.add_argument("--spread-bps", type=int, default=2)
    args = p.parse_args()

    _load_env()
    from bolsa_application.backtests import RunAndSaveBacktest
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

    rows: list[tuple[str, str, str, float | None, float | None, int | None]] = []

    async with factory() as session:
        lists = SqlAlchemyListRepository(session)
        detail = await lists.get_by_id(args.list_id)
        if detail is None or not detail.instrument_ids:
            print(f"ERROR: lista vacía {args.list_id}", file=sys.stderr)
            await engine.dispose()
            return 1
        ids = list(detail.instrument_ids)[: max(1, args.limit)]
        instruments = SqlAlchemyInstrumentRepository(session)
        run_bt = RunAndSaveBacktest(
            instruments,
            SqlAlchemyOhlcvRepository(session),
            SqlAlchemyBacktestRepository(session),
            SqlAlchemyStrategyDefinitionRepository(session),
            SqlAlchemyResearchTrialRepository(session),
        )
        for instrument_id in ids:
            inst = await instruments.get_by_id(instrument_id)
            symbol = inst.symbol if inst else instrument_id[:8]
            for preset in args.presets:
                try:
                    result = await run_bt.execute(
                        instrument_id=instrument_id,
                        strategy_type=preset,
                        campaign=f"mass-compare-{args.list_id}",
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
                    m = result.metrics
                    rows.append(
                        (
                            symbol,
                            preset,
                            result.trial_id[:12],
                            m.get("sharpeRatio") if isinstance(m.get("sharpeRatio"), (int, float)) else None,
                            m.get("totalReturnPct") if isinstance(m.get("totalReturnPct"), (int, float)) else None,
                            m.get("tradeCount") if isinstance(m.get("tradeCount"), (int, float)) else None,
                        )
                    )
                    print(
                        f"OK {symbol:6} {preset:22} Sharpe={rows[-1][3]} PnL={rows[-1][4]}"
                    )
                except Exception as exc:  # noqa: BLE001
                    await session.rollback()
                    print(f"FAIL {symbol:6} {preset:22} {exc}", file=sys.stderr)

    await engine.dispose()

    # Ranking by avg Sharpe per symbol
    from collections import defaultdict

    by_sym: dict[str, list[float]] = defaultdict(list)
    for symbol, _p, _t, sharpe, _pnl, _tc in rows:
        if sharpe is not None:
            by_sym[symbol].append(float(sharpe))
    ranking = sorted(
        ((s, sum(v) / len(v), len(v)) for s, v in by_sym.items() if v),
        key=lambda x: x[1],
        reverse=True,
    )
    print("\n=== Ranking Sharpe medio ===")
    for symbol, avg, n in ranking:
        print(f"  {symbol:6} avgSharpe={avg:.3f} (n={n})")
    return 0


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(_main()))
