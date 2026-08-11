"""
Recálculo idempotente de trials/runs con el motor ``next_open`` (F2).

Tras corregir el look-ahead/same-bar (P0.1), los trials y resultados históricos
(CORE-R, Finalistas, Lista AUTO, DÍA D) deben recalcularse con ``execution_model=
"next_open"``. El Protocol de trials es insert-only (no hay update): este script
re-ejecuta cada preset por instrumento en el nuevo motor y **inserta un run+trial
nuevo** por combinación, saltando las que ya existen bajo la nueva ``data_version``
y ``engine.version`` (idempotente).

Usage (repo root, .env):
  python scripts/research/recalc_trials_next_open.py --dry-run
  python scripts/research/recalc_trials_next_open.py --symbol AENA --dry-run
  python scripts/research/recalc_trials_next_open.py --campaign CORE-R --dry-run
  python scripts/research/recalc_trials_next_open.py --apply
  python scripts/research/recalc_trials_next_open.py --apply --reset

Exit: 0 si ok; 1 si apply falló o quedan combinaciones sin recalcular.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DATA_EPOCH_LEGACY = "legacy"
DATA_EPOCH_NEXT_OPEN = "next_open"


def _old_theme(row: Any, *, engine_version: str) -> bool:
    """Un run es old-theme si su manifest.engine.version no es el actual (F2 next_open)."""
    engine = (row.manifest or {}).get("engine") or {}
    return engine.get("version") != engine_version


async def _mark_legacy(session: Any, *, engine_version: str) -> int:
    """Etiqueta ``data_epoch`` de backtest_runs/research_trials (old ↔ next_open).

    Los runs con ``manifest.engine.version`` actual (F2 ``next_open``) se marcan
    ``next_open``; los restantes (old-theme, previos a la corrección) se marcan
    ``legacy`` y sus trials se propagan. Devuelve el nº de runs cuya etiqueta
    cambió. Idempotente.
    """
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import BacktestRunRow, ResearchTrialRow

    runs = (await session.execute(select(BacktestRunRow))).scalars().all()
    changed = 0
    for run in runs:
        target = (
            DATA_EPOCH_NEXT_OPEN
            if not _old_theme(run, engine_version=engine_version)
            else DATA_EPOCH_LEGACY
        )
        if run.data_epoch != target:
            run.data_epoch = target
            changed += 1
    await session.flush()

    trials = (await session.execute(select(ResearchTrialRow))).scalars().all()
    run_by_id = {r.id: r for r in runs}
    for trial in trials:
        run = run_by_id.get(trial.backtest_run_id)
        if run is not None and trial.data_epoch != run.data_epoch:
            trial.data_epoch = run.data_epoch
    await session.flush()
    return changed


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


async def _targets(
    session: Any,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Distinct (instrument_id, strategy_type, timeframe) de trials existentes."""
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import BacktestRunRow, ResearchTrialRow

    stmt = (
        select(
            BacktestRunRow.instrument_id,
            BacktestRunRow.strategy_type,
            BacktestRunRow.timeframe,
        )
        .join(ResearchTrialRow, ResearchTrialRow.backtest_run_id == BacktestRunRow.id)
        .where(
            BacktestRunRow.strategy_type.is_not(None),
            BacktestRunRow.timeframe.is_not(None),
        )
        .distinct()
    )
    if args.symbol:
        from bolsa_infrastructure.database.models.tables import InstrumentRow

        symbol = args.symbol.upper()
        inst_row = (
            await session.execute(select(InstrumentRow).where(InstrumentRow.symbol == symbol))
        ).scalar_one_or_none()
        if inst_row is None:
            print(f"ERROR: símbolo {args.symbol} no encontrado")
            sys.exit(1)
        stmt = stmt.where(BacktestRunRow.instrument_id == inst_row.id)

    rows = (await session.execute(stmt)).all()
    targets = [
        {
            "instrument_id": r[0],
            "strategy_type": r[1],
            "timeframe": r[2],
        }
        for r in rows
    ]

    if args.campaign:
        # Filtra por campaign legible (param) entre los trials alcanzados.
        filtered: list[dict[str, Any]] = []
        from sqlalchemy import select as sel

        for t in targets:
            trial_rows = (
                await session.execute(
                    sel(ResearchTrialRow.id, ResearchTrialRow.params)
                    .join(
                        BacktestRunRow,
                        BacktestRunRow.id == ResearchTrialRow.backtest_run_id,
                    )
                    .where(
                        BacktestRunRow.instrument_id == t["instrument_id"],
                        BacktestRunRow.strategy_type == t["strategy_type"],
                        BacktestRunRow.timeframe == t["timeframe"],
                    )
                )
            ).all()
            if any(
                str((r.params or {}).get("campaign", "")).strip() == args.campaign
                for r in trial_rows
            ):
                filtered.append(t)
        targets = filtered

    return targets


async def _new_theme_run_exists(
    session: Any,
    *,
    instrument_id: str,
    strategy_type: str,
    timeframe: str,
    data_version: str,
    engine_version: str,
) -> bool:
    """Un run nuevo-theme (data_version + engine.version actuales) ya existe → skip."""
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import BacktestRunRow

    stmt = select(BacktestRunRow.id).where(
        BacktestRunRow.instrument_id == instrument_id,
        BacktestRunRow.strategy_type == strategy_type,
        BacktestRunRow.timeframe == timeframe,
        BacktestRunRow.data_version == data_version,
    )
    rows = (await session.execute(stmt)).scalars().all()
    for run_id in rows:
        row = await session.get(BacktestRunRow, run_id)
        manifest = row.manifest or {}
        engine = manifest.get("engine") or {}
        snapshot = manifest.get("dataSnapshot") or {}
        if engine.get("version") == engine_version and snapshot.get("dataVersion") == data_version:
            return True
    return False


async def _recalc_one(
    session: Any,
    *,
    instrument_id: str,
    strategy_type: str,
    timeframe: str,
    args: argparse.Namespace,
    dry_run: bool,
) -> tuple[str, bool]:
    """Re-ejecuta un preset en next_open. Devuelve (estado, hizo_cambio)."""
    from bolsa_analytics.research import BarFingerprint
    from bolsa_analytics.research.data_snapshot import compute_data_version
    from bolsa_analytics.research.manifest import ENGINE_VERSION
    from bolsa_application.backtests import RunAndSaveBacktest
    from bolsa_domain.value_objects.timeframe import TimeFrame
    from bolsa_infrastructure.database.repositories.backtest_repository import (
        SqlAlchemyBacktestRepository,
    )
    from bolsa_infrastructure.database.repositories.instrument_repository import (
        SqlAlchemyInstrumentRepository,
    )
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (
        SqlAlchemyOhlcvRepository,
    )
    from bolsa_infrastructure.database.repositories.research_evidence_repository import (
        SqlAlchemyResearchEvidenceRepository,
    )
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )
    from bolsa_infrastructure.database.repositories.strategy_definition_repository import (
        SqlAlchemyStrategyDefinitionRepository,
    )

    ohlcv = SqlAlchemyOhlcvRepository(session)
    tf = TimeFrame(timeframe) if timeframe in {t.value for t in TimeFrame} else TimeFrame.D1
    bars = await ohlcv.get_bars(instrument_id, timeframe=tf, limit=args.limit)
    if len(bars) < 30:
        return ("skipped_short", False)

    data_version = compute_data_version(
        [
            BarFingerprint(
                timestamp=b.timestamp,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=float(b.volume),
            )
            for b in bars
        ]
    )

    if not args.reset and await _new_theme_run_exists(
        session,
        instrument_id=instrument_id,
        strategy_type=strategy_type,
        timeframe=timeframe,
        data_version=data_version,
        engine_version=ENGINE_VERSION,
    ):
        return ("already_new", False)

    if dry_run:
        return ("would_recalc", True)

    use_case = RunAndSaveBacktest(
        instrument_repository=SqlAlchemyInstrumentRepository(session),
        ohlcv_repository=ohlcv,
        backtest_repository=SqlAlchemyBacktestRepository(session),
        strategy_repository=SqlAlchemyStrategyDefinitionRepository(session),
        research_trial_repository=SqlAlchemyResearchTrialRepository(session),
        research_evidence_repository=SqlAlchemyResearchEvidenceRepository(session),
        hypothesis_repository=None,
        hypothesis_belief_repository=None,
    )
    await use_case.execute(
        instrument_id=instrument_id,
        strategy_type=strategy_type,
        timeframe=timeframe,
        initial_cash=args.initial_cash,
        limit=args.limit,
    )
    await session.commit()
    return ("recalced", True)


async def _run(args: argparse.Namespace) -> int:
    from bolsa_analytics.research.manifest import ENGINE_VERSION
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    dry_run = not args.apply
    get_settings.cache_clear()
    settings = get_settings()
    if args.mark_legacy and not dry_run:
        # La columna data_epoch debe existir (Alembic F3b). Idempotente.
        ensure_migrated()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    counts = {
        "recalced": 0,
        "would_recalc": 0,
        "already_new": 0,
        "skipped_short": 0,
        "errors": 0,
        "marked": 0,
    }

    async with factory() as session:
        targets = await _targets(session, args)
        print(f"Targets a revisar: {len(targets)}")
        for t in targets:
            try:
                status, _changed = await _recalc_one(
                    session,
                    instrument_id=t["instrument_id"],
                    strategy_type=t["strategy_type"],
                    timeframe=t["timeframe"],
                    args=args,
                    dry_run=dry_run,
                )
                counts[status] += 1
                print(f"  {t['instrument_id']} {t['strategy_type']} {t['timeframe']} → {status}")
            except Exception as exc:  # noqa: BLE001
                counts["errors"] += 1
                print(f"  ERROR {t['instrument_id']} {t['strategy_type']}: {exc}")

        if args.mark_legacy:
            if dry_run:
                print("INFO: --mark-legacy en dry-run: no escribe (pasa --apply para etiquetar).")
            else:
                marked_runs = await _mark_legacy(session, engine_version=ENGINE_VERSION)
                await session.commit()
                counts["marked"] += marked_runs
                print(
                    f"Marcado data_epoch: {marked_runs} runs con data_epoch distinto "
                    "(legacy/next_open)."
                )

    await engine.dispose()

    print(
        f"\nResumen: recalced={counts['recalced']} would_recalc={counts['would_recalc']} "
        f"already_new={counts['already_new']} skipped_short={counts['skipped_short']} "
        f"marked={counts['marked']} errors={counts['errors']} "
        f"mode={'apply' if args.apply else 'dry-run'}"
    )
    return 1 if (counts["errors"] or (args.apply and counts["recalced"] == 0 and counts["already_new"] == 0)) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Recálculo idempotente trials next_open")
    parser.add_argument("--symbol", help="Filtra a un instrumento por símbolo (p.ej. AENA)")
    parser.add_argument("--campaign", help="Filtra trials por campaign (CORE-R|Finalistas|AUTO|DIA_D)")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--limit", type=int, default=500, help="Nº de barras por backtest")
    parser.add_argument("--initial-cash", type=float, default=10000.0)
    parser.add_argument("--apply", action="store_true", help="Escribe en DB (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Alias explícito (default)")
    parser.add_argument("--reset", action="store_true", help="Re-ejecuta aunque ya exista run nuevo-theme")
    parser.add_argument("--mark-legacy", action="store_true", help="Marca runs/trials old-theme como data_epoch='legacy' (runs next_open='next_open')")
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
