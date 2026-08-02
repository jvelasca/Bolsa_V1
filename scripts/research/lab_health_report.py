"""Q0.1 — Lab Health report from research_trials (coverage / zero-trades / campaigns).

Usage (repo root):
  python scripts/research/lab_health_report.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


async def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)

    from bolsa_application.research_trials import GetLabHealth
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)

    async with factory() as session:
        health = await GetLabHealth(SqlAlchemyResearchTrialRepository(session)).execute()

    print("=== LAB HEALTH (Q0.1) ===")
    print(f"trials={health['totalTrials']}")
    cov = health["coverage"]
    for key in ("sharpeRatio", "sortinoRatio", "calmarRatio"):
        row = cov[key]
        print(f"  {key}: {row['present']} ({row['pct']}%)")
    print(f"zeroTradeCount={health['zeroTradeCount']} ({health['zeroTradePct']}%)")
    print(
        f"instruments: withTrials={health['instrumentsWithTrials']} "
        f"active={health['activeInstruments']} "
        f"without={health['instrumentsWithoutTrials']}"
    )
    print(f"campaigns={health['campaignCount']}")
    for c in health["campaigns"][:12]:
        print(f"  {c['campaignId']}: {c['trials']}")
    print(f"caveat: {health['caveat']}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
