#!/usr/bin/env python3
"""Q1.2 smoke — dos ventanas RSI (limit pequeño) + Δ ranking.

Usage (repo root, API/DB up):
  python scripts/research/stability_windows_smoke.py --limit 3
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Ventanas con solape parcial (ACS tiene datos desde ~2021).
WINDOW_A = ("2021-07-01", "2023-12-31", "ibex35-rsi-win-a")
WINDOW_B = ("2023-01-01", "2025-12-31", "ibex35-rsi-win-b")


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


async def _main() -> int:
    p = argparse.ArgumentParser(description="Stability windows smoke (RSI human-only)")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--skip-run", action="store_true", help="Solo Δ (asume campaigns ya en ledger)")
    args = p.parse_args()

    py = sys.executable
    if not args.skip_run:
        for date_from, date_to, campaign in (WINDOW_A, WINDOW_B):
            code = _run(
                [
                    py,
                    "scripts/research/run_ibex35_rsi_campaign.py",
                    "--limit",
                    str(args.limit),
                    "--human-only",
                    "--no-skip-existing-human",
                    "--campaign-id",
                    campaign,
                    "--date-from",
                    date_from,
                    "--date-to",
                    date_to,
                    "--presets",
                    "rsi_mean_reversion",
                ]
            )
            if code != 0:
                print(f"WARN: campaign {campaign} exit={code}", file=sys.stderr)

    out = ROOT / "research" / "observations" / "2026-08-02-stability-delta-smoke.md"
    code = _run(
        [
            py,
            "scripts/research/stability_ranking_delta.py",
            "--campaign-a",
            WINDOW_A[2],
            "--campaign-b",
            WINDOW_B[2],
            "--write-md",
            str(out),
        ]
    )
    return code


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(_main()))
