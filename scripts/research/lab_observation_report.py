"""One-shot lab observation report from research_trials (exploitation)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _fmt_metric(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


async def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.instrument_repository import (
        SqlAlchemyInstrumentRepository,
    )
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)

    async with factory() as session:
        trials_repo = SqlAlchemyResearchTrialRepository(session)
        instruments = SqlAlchemyInstrumentRepository(session)
        lab = await trials_repo.laboratory_summary()

        print("=== LAB SUMMARY ===")
        print(
            f"trials={lab['totalTrials']} K={lab['totalK']} "
            f"instruments={lab['activeInstruments']} avgSharpe={lab['avgSharpe']}"
        )
        print("byOrigin:", lab["byOrigin"])
        print("byPreset:", lab["byPreset"][:8])
        print("top instruments:")
        for row in lab["byInstrument"][:10]:
            print(
                f"  {row['symbol']:6} trials={row['trials']} "
                f"K={row['kConsumed']} avgS={row['avgSharpe']}"
            )

        # sort=sharpe uses NULLS LAST in repository — nulls no longer pollute Top/Bottom.
        top, _ = await trials_repo.list_trials(
            proposed_by="human", sort="sharpe", sort_dir="desc", limit=8
        )
        print("\n=== TOP Sharpe (human, nulls last) ===")
        for t in top:
            inst = await instruments.get_by_id(t.instrument_id)
            sym = inst.symbol if inst else "?"
            print(
                f"  {sym:6} {(t.preset_key or '-'):22} "
                f"Sharpe={_fmt_metric(t.is_metrics.get('sharpeRatio'))} "
                f"PnL={_fmt_metric(t.is_metrics.get('totalReturnPct'))}"
            )

        bottom, _ = await trials_repo.list_trials(
            proposed_by="human", sort="sharpe", sort_dir="asc", limit=8
        )
        print("\n=== BOTTOM Sharpe (human, nulls last) ===")
        for t in bottom:
            inst = await instruments.get_by_id(t.instrument_id)
            sym = inst.symbol if inst else "?"
            print(
                f"  {sym:6} {(t.preset_key or '-'):22} "
                f"Sharpe={_fmt_metric(t.is_metrics.get('sharpeRatio'))} "
                f"PnL={_fmt_metric(t.is_metrics.get('totalReturnPct'))}"
            )

    await engine.dispose()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
