#!/usr/bin/env python3
"""Verify OOS scoring uses IS warm-up (catch cold-start regressions).

Run from repo root:
  python scripts/research/verify_oos_warmup.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "py" / "analytics" / "src"))

from bolsa_analytics.backtest import BacktestBarInput  # noqa: E402
from bolsa_analytics.optimize.sma_grid import _simulate_sma_crossover  # noqa: E402


def main() -> int:
    start = datetime(2014, 1, 1, tzinfo=UTC)
    bars = [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + 0.1 * i + (3.0 if i % 19 < 9 else -1.5),
        )
        for i in range(400)
    ]
    split = 280
    is_bars, oos_bars = bars[:split], bars[split:]
    fast, slow, cash = 12, 35, 10_000.0

    cold = _simulate_sma_crossover(oos_bars, fast, slow, cash)
    warm = _simulate_sma_crossover(
        is_bars + oos_bars, fast, slow, cash, trade_from_index=split
    )

    print("=== verify_oos_warmup ===")
    print(f"bars={len(bars)} split={split} params={fast}/{slow}")
    print(
        f"COLD  (OOS only, no warm-up): score={cold['score']:.4f} "
        f"ret={cold['totalReturnPct']:.2f}% trades={cold['tradeCount']}"
    )
    print(
        f"WARM  (IS warm-up + trade OOS): score={warm['score']:.4f} "
        f"ret={warm['totalReturnPct']:.2f}% trades={warm['tradeCount']}"
    )
    same = (
        cold["score"] == warm["score"]
        and cold["tradeCount"] == warm["tradeCount"]
        and cold["totalReturnPct"] == warm["totalReturnPct"]
    )
    if same:
        print("FAIL: cold-start equals warm-up — unexpected for this series")
        return 1
    print("OK: warm-up changes OOS outcome (cold-start must not be used for adopt/UI)")
    print(
        "Policy: lab OOS metrics use warm-up; «Guardar Mejor y probar» re-runs full lab "
        "window (not dateFrom=split)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
