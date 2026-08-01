"""
Backfill runId en slots de InstrumentStrategyTop (deuda AENA / Checklist).

Empareja cada slot sin runId con el backtest_run más reciente del mismo
instrumento + (strategyDefinitionId | strategyType) + timeframe.

Usage (repo root, .env):
  python scripts/research/backfill_top_runids.py --symbol AENA --dry-run
  python scripts/research/backfill_top_runids.py --symbol AENA --apply
  python scripts/research/backfill_top_runids.py --all-missing --dry-run

Exit: 0 si ok / nada que hacer; 1 si apply falló o quedan slots sin match.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _slot_type(slot: dict[str, Any] | None) -> str | None:
    if not slot:
        return None
    t = slot.get("strategyType") or slot.get("strategy_type")
    return str(t) if t else None


async def _find_run_id(
    session: Any,
    *,
    instrument_id: str,
    timeframe: str,
    strategy_definition_id: str | None,
    strategy_type: str | None,
) -> str | None:
    from sqlalchemy import select

    from bolsa_infrastructure.database.models import BacktestRunRow

    if strategy_definition_id:
        stmt = (
            select(BacktestRunRow.id)
            .where(
                BacktestRunRow.instrument_id == instrument_id,
                BacktestRunRow.timeframe == timeframe,
                BacktestRunRow.strategy_definition_id == strategy_definition_id,
            )
            .order_by(BacktestRunRow.created_at.desc())
            .limit(1)
        )
        found = (await session.execute(stmt)).scalar_one_or_none()
        if found:
            return str(found)

    if strategy_type:
        stmt = (
            select(BacktestRunRow.id)
            .where(
                BacktestRunRow.instrument_id == instrument_id,
                BacktestRunRow.timeframe == timeframe,
                BacktestRunRow.strategy_type == strategy_type,
            )
            .order_by(BacktestRunRow.created_at.desc())
            .limit(1)
        )
        found = (await session.execute(stmt)).scalar_one_or_none()
        if found:
            return str(found)
    return None


async def _run(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from bolsa_application.instrument_strategy_tops import (
        assert_lab_validated_slots_have_run_id,
    )
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import InstrumentRow as DbInstrument
    from bolsa_infrastructure.database.models import InstrumentStrategyTopRow
    from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
        SqlAlchemyInstrumentStrategyTopRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    patched = 0
    unresolved = 0
    skipped_ok = 0

    async with factory() as session:
        tops = SqlAlchemyInstrumentStrategyTopRepository(session)

        if args.symbol:
            inst_stmt = select(DbInstrument).where(
                DbInstrument.symbol == args.symbol.upper()
            )
            inst = (await session.execute(inst_stmt)).scalar_one_or_none()
            if inst is None:
                print(f"ERROR: símbolo {args.symbol} no encontrado")
                await engine.dispose()
                return 1
            targets = [inst]
        elif args.all_missing:
            stmt = select(InstrumentStrategyTopRow).where(
                InstrumentStrategyTopRow.timeframe == args.timeframe
            )
            rows = (await session.execute(stmt)).scalars().all()
            targets = []
            for row in rows:
                slots = list(row.slots or [])
                if any(not (s.get("runId") or s.get("run_id")) for s in slots):
                    inst = await session.get(DbInstrument, row.instrument_id)
                    if inst:
                        targets.append(inst)
        else:
            print("Usa --symbol AENA o --all-missing")
            await engine.dispose()
            return 1

        for inst in targets:
            top = await tops.get(inst.id, args.timeframe)
            if top is None:
                print(f"{inst.symbol}: sin TOP · skip")
                continue
            slots = [dict(s) for s in top.slots]
            changed = False
            for slot in slots:
                if slot.get("runId") or slot.get("run_id"):
                    continue
                run_id = await _find_run_id(
                    session,
                    instrument_id=inst.id,
                    timeframe=args.timeframe,
                    strategy_definition_id=slot.get("strategyDefinitionId")
                    or slot.get("strategy_definition_id"),
                    strategy_type=_slot_type(slot),
                )
                label = slot.get("label") or "?"
                if not run_id:
                    print(
                        f"{inst.symbol}: sin match run para «{label}» "
                        f"(type={_slot_type(slot)} def={slot.get('strategyDefinitionId')})"
                    )
                    unresolved += 1
                    continue
                slot["runId"] = run_id
                changed = True
                print(f"{inst.symbol}: {label} → runId={run_id}")

            if not changed:
                if all(s.get("runId") or s.get("run_id") for s in slots):
                    skipped_ok += 1
                    print(f"{inst.symbol}: ya OK")
                continue

            try:
                assert_lab_validated_slots_have_run_id(
                    evidence_level=top.evidence_level,
                    status=top.status,
                    slots=slots,
                )
            except ValueError as exc:
                print(f"{inst.symbol}: aún incompleto tras match · {exc}")
                unresolved += 1
                continue

            facts = dict(top.coach_facts or {})
            facts["runIdBackfill"] = {
                "at": datetime.now(timezone.utc).isoformat(),
                "engine": "backfill-top-runids-v1",
            }

            if args.apply:
                await tops.upsert(
                    instrument_id=inst.id,
                    timeframe=args.timeframe,
                    slots=slots,
                    symbol=top.symbol or inst.symbol,
                    period_label=top.period_label,
                    status=top.status,
                    evidence_level=top.evidence_level,
                    coach_headline=top.coach_headline,
                    coach_facts=facts,
                )
                await session.commit()
                patched += 1
                print(f"{inst.symbol}: APPLY ok (v{top.version}+1)")
            else:
                patched += 1
                print(f"{inst.symbol}: DRY-RUN ok (no escrito)")

    await engine.dispose()
    print(
        f"\nResumen: patched={patched} unresolved={unresolved} already_ok={skipped_ok} "
        f"mode={'apply' if args.apply else 'dry-run'}"
    )
    return 1 if unresolved else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill runId en Finalistas TOP")
    parser.add_argument("--symbol", help="p.ej. AENA")
    parser.add_argument(
        "--all-missing",
        action="store_true",
        help="Todos los TOP del TF con algún slot sin runId",
    )
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribe en DB (por defecto solo dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alias explícito (default)",
    )
    args = parser.parse_args()
    if args.apply and args.dry_run:
        print("Elige --apply o --dry-run, no ambos")
        return 1

    _load_env()
    import asyncio

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
