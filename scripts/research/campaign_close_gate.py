#!/usr/bin/env python3
"""Q1.6 — gate de cierre de campaña (checklist automática).

Lee Lab Health + manifest JSON y falla si umbrales no se cumplen.

Usage:
  python scripts/research/campaign_close_gate.py --campaign ibex35-rsi-c2 \\
    --manifest research/campaigns/ibex35-rsi-c2.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


async def _run(args: argparse.Namespace) -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)

    from bolsa_application.campaign_manifest import validate_campaign_manifest
    from bolsa_application.research_trials import GetLabHealth
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    errors: list[str] = []

    if args.manifest:
        path = Path(args.manifest)
        if not path.is_file():
            errors.append(f"manifest not found: {path}")
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            errors.extend(validate_campaign_manifest(data))

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    async with factory() as session:
        health = await GetLabHealth(SqlAlchemyResearchTrialRepository(session)).execute()
    await engine.dispose()

    if health["zeroTradePct"] > args.max_zero_trade_pct:
        errors.append(
            f"zeroTradePct={health['zeroTradePct']} > max={args.max_zero_trade_pct}"
        )

    cov = health["coverage"]
    if cov["sharpeRatio"]["pct"] < args.min_sharpe_coverage_pct:
        errors.append(
            f"sharpe coverage {cov['sharpeRatio']['pct']}% < min {args.min_sharpe_coverage_pct}%"
        )

    campaigns = {c["campaignId"] for c in health["campaigns"]}
    if args.campaign and args.campaign not in campaigns and not args.allow_missing_campaign:
        errors.append(f"campaign '{args.campaign}' not found in ledger tags")

    print("=== CAMPAIGN CLOSE GATE (Q1.6) ===")
    print(f"zeroTradePct={health['zeroTradePct']} sharpeCov={cov['sharpeRatio']['pct']}%")
    if errors:
        print("FAIL:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK: gate passed")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Campaign close gate")
    p.add_argument("--campaign", default="", help="Campaign id expected in ledger")
    p.add_argument("--manifest", default="", help="Path to campaign_manifest_v0 JSON")
    p.add_argument("--max-zero-trade-pct", type=float, default=25.0)
    p.add_argument("--min-sharpe-coverage-pct", type=float, default=0.0)
    p.add_argument(
        "--allow-missing-campaign",
        action="store_true",
        help="Skip ledger campaign tag check (manifest-only)",
    )
    args = p.parse_args()
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
