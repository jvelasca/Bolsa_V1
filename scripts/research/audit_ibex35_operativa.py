"""
Auditoría operativa live IBEX 35 — coherencia de datos / TOP / trials.

No re-ejecuta el embudo completo (caro). Lee lista `ibex35` + OHLCV + strategy_tops
(+ trials recientes) y emite hallazgos de calidad.

Usage (repo root, .env):
  python scripts/research/audit_ibex35_operativa.py
  python scripts/research/audit_ibex35_operativa.py --list-id ibex35 --write-md
  python scripts/research/audit_ibex35_operativa.py --timeframe 1d --min-bars 200
  python scripts/research/audit_ibex35_operativa.py --print-missing

Exit: 0 si sin critical; 1 si critical o lista ausente.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# Mirror packages/shared/src/constants.ts IBEX35_INSTRUMENTS symbols
EXPECTED_IBEX_SYMBOLS = [
    "SAN", "BBVA", "IBE", "ITX", "TEF", "REP", "FER", "ACS", "ENG", "GRF",
    "AENA", "IAG", "MAP", "MEL", "RED", "CLNX", "AMS", "CABK", "SAB", "LOG",
    "COL", "NTGY", "ACX", "FDR", "VIS", "ROVI", "PHM", "ALM", "UNI", "BKT",
    "SCYR", "IDR", "CAF", "ELE", "ANA",
]


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@dataclass
class Finding:
    code: str
    severity: str  # critical | warn | info | ok
    message: str
    detail: str | None = None


@dataclass
class InstrumentRow:
    instrument_id: str
    symbol: str
    bar_count: int
    last_bar: str | None
    top_status: str | None
    evidence_level: str | None
    slot_count: int
    top1_label: str | None
    top1_type: str | None
    slots_missing_run: int
    slots_missing_strategy: int
    recent_trials: int


@dataclass
class AuditReport:
    as_of: str
    list_id: str
    list_name: str
    instrument_count: int
    expected_count: int
    findings: list[Finding] = field(default_factory=list)
    rows: list[InstrumentRow] = field(default_factory=list)
    top1_frequency: dict[str, int] = field(default_factory=dict)
    sticky_top1_share: float = 0.0
    critical_count: int = 0
    warn_count: int = 0
    passed: bool = True


def _slot_type(slot: dict[str, Any]) -> str | None:
    for key in ("strategyType", "presetKey", "source"):
        v = slot.get(key)
        if isinstance(v, str) and v.strip():
            if key == "source":
                continue
            return v
    label = slot.get("label")
    return str(label) if label else None


async def _run(args: argparse.Namespace) -> AuditReport:
    from sqlalchemy import func, select

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import (
        InstrumentRow as DbInstrument,
        OhlcvBarRow,
        ResearchTrialRow,
    )
    from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
        SqlAlchemyInstrumentStrategyTopRepository,
    )
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    report = AuditReport(
        as_of=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        list_id=args.list_id,
        list_name="",
        instrument_count=0,
        expected_count=len(EXPECTED_IBEX_SYMBOLS),
    )

    async with factory() as session:
        lists = SqlAlchemyListRepository(session)
        detail = await lists.get_by_id(args.list_id)
        if detail is None:
            for summary in await lists.list_all():
                if summary.name.upper().startswith("IBEX"):
                    detail = await lists.get_by_id(summary.id)
                    break
        if detail is None or not detail.instrument_ids:
            report.findings.append(
                Finding(
                    "list_missing",
                    "critical",
                    f"Lista '{args.list_id}' no encontrada o vacía",
                )
            )
            report.critical_count = 1
            report.passed = False
            await engine.dispose()
            return report

        report.list_id = detail.id
        report.list_name = detail.name
        instrument_ids = list(detail.instrument_ids)
        if args.limit > 0:
            instrument_ids = instrument_ids[: args.limit]
        report.instrument_count = len(instrument_ids)

        if len(detail.instrument_ids) < 30:
            report.findings.append(
                Finding(
                    "list_thin",
                    "warn",
                    f"Lista con {len(detail.instrument_ids)} valores (esperado ~35)",
                )
            )

        tops = SqlAlchemyInstrumentStrategyTopRepository(session)
        top1_counter: Counter[str] = Counter()
        symbols_seen: set[str] = set()

        for iid in instrument_ids:
            inst = await session.get(DbInstrument, iid)
            symbol = (inst.symbol if inst else None) or iid[:8]
            symbols_seen.add(symbol.upper())

            bar_stmt = (
                select(func.count(), func.max(OhlcvBarRow.timestamp))
                .where(
                    OhlcvBarRow.instrument_id == iid,
                    OhlcvBarRow.timeframe == args.timeframe,
                )
            )
            bar_count, last_bar = (await session.execute(bar_stmt)).one()
            bar_count = int(bar_count or 0)
            last_iso = last_bar.isoformat() if last_bar is not None else None

            top = await tops.get(iid, args.timeframe)
            slots = list(top.slots) if top else []
            top1 = slots[0] if slots else None
            top1_label = (top1 or {}).get("label") if top1 else None
            top1_type = _slot_type(top1) if top1 else None
            if top1_type:
                top1_counter[top1_type] += 1

            missing_run = sum(1 for s in slots if not s.get("runId"))
            missing_strat = sum(1 for s in slots if not s.get("strategyDefinitionId"))

            trial_stmt = (
                select(func.count())
                .select_from(ResearchTrialRow)
                .where(ResearchTrialRow.instrument_id == iid)
            )
            try:
                recent_trials = int((await session.execute(trial_stmt)).scalar_one() or 0)
            except Exception:
                # Schema variants — don't fail the whole audit
                recent_trials = -1

            row = InstrumentRow(
                instrument_id=iid,
                symbol=symbol,
                bar_count=bar_count,
                last_bar=last_iso,
                top_status=top.status if top else None,
                evidence_level=top.evidence_level if top else None,
                slot_count=len(slots),
                top1_label=str(top1_label) if top1_label else None,
                top1_type=top1_type,
                slots_missing_run=missing_run,
                slots_missing_strategy=missing_strat,
                recent_trials=recent_trials,
            )
            report.rows.append(row)

            if bar_count == 0:
                report.findings.append(
                    Finding("no_ohlcv", "critical", f"{symbol}: sin barras {args.timeframe}")
                )
            elif bar_count < args.min_bars:
                report.findings.append(
                    Finding(
                        "thin_ohlcv",
                        "warn",
                        f"{symbol}: solo {bar_count} barras (min {args.min_bars})",
                    )
                )

            if top is None or not slots:
                report.findings.append(
                    Finding(
                        "no_top",
                        "info",
                        f"{symbol}: sin InstrumentStrategyTop ({args.timeframe})",
                    )
                )
            else:
                if missing_run == len(slots) and len(slots) > 0:
                    sev = (
                        "critical"
                        if top and top.evidence_level == "lab_validated"
                        else "warn"
                    )
                    report.findings.append(
                        Finding(
                            "top_without_runids",
                            sev,
                            f"{symbol}: TOP sin runId en ningún slot (Checklist Camino A roto)",
                        )
                    )
                if missing_strat:
                    report.findings.append(
                        Finding(
                            "top_without_strategy",
                            "warn",
                            f"{symbol}: {missing_strat} slot(s) sin strategyDefinitionId",
                        )
                    )
                if top.evidence_level == "lab_validated" and top.status != "active":
                    report.findings.append(
                        Finding(
                            "lab_validated_not_active",
                            "warn",
                            f"{symbol}: evidence=lab_validated pero status={top.status}",
                        )
                    )

        missing_expected = [s for s in EXPECTED_IBEX_SYMBOLS if s not in symbols_seen]
        extra = sorted(symbols_seen - set(EXPECTED_IBEX_SYMBOLS))
        if missing_expected:
            report.findings.append(
                Finding(
                    "symbols_missing_vs_catalog",
                    "warn",
                    f"Faltan vs constants.ts: {', '.join(missing_expected[:12])}"
                    + ("…" if len(missing_expected) > 12 else ""),
                    detail=json.dumps(missing_expected),
                )
            )
        if extra:
            report.findings.append(
                Finding(
                    "symbols_extra_vs_catalog",
                    "info",
                    f"Extra vs constants.ts: {', '.join(extra[:12])}",
                )
            )

        with_top = [r for r in report.rows if r.slot_count > 0]
        report.top1_frequency = dict(top1_counter)
        if with_top:
            max_c = max(top1_counter.values()) if top1_counter else 0
            report.sticky_top1_share = max_c / len(with_top)
            if len(with_top) >= 8 and report.sticky_top1_share >= 0.75:
                report.findings.append(
                    Finding(
                        "sticky_top1",
                        "critical",
                        f"TOP #1 pegajoso en {(report.sticky_top1_share * 100):.0f}% de valores con TOP",
                        detail=json.dumps(report.top1_frequency),
                    )
                )
            elif len(with_top) >= 8 and report.sticky_top1_share >= 0.5:
                report.findings.append(
                    Finding(
                        "sticky_top1",
                        "warn",
                        f"TOP #1 concentrado {(report.sticky_top1_share * 100):.0f}%",
                        detail=json.dumps(report.top1_frequency),
                    )
                )

        no_top_n = sum(1 for r in report.rows if r.slot_count == 0)
        no_bars_n = sum(1 for r in report.rows if r.bar_count == 0)
        if no_bars_n:
            report.findings.append(
                Finding(
                    "summary_no_bars",
                    "critical",
                    f"{no_bars_n}/{report.instrument_count} valores sin OHLCV {args.timeframe}",
                )
            )
        if no_top_n == report.instrument_count:
            report.findings.append(
                Finding(
                    "summary_no_tops",
                    "warn",
                    "Ningún valor tiene TOP — embudo Finalistas aún no corrido sobre la lista",
                )
            )
        elif no_top_n:
            report.findings.append(
                Finding(
                    "summary_partial_tops",
                    "info",
                    f"{no_top_n}/{report.instrument_count} sin TOP; {len(with_top)} con TOP",
                )
            )

        report.critical_count = sum(1 for f in report.findings if f.severity == "critical")
        report.warn_count = sum(1 for f in report.findings if f.severity == "warn")
        report.passed = report.critical_count == 0

        if report.passed and report.warn_count == 0:
            report.findings.append(
                Finding(
                    "live_healthy",
                    "ok",
                    f"Lista {report.list_name}: datos+TOP coherentes a primera vista",
                )
            )

    await engine.dispose()
    return report


def _print_missing(report: AuditReport) -> None:
    """Lista operativa: sin TOP / TOP sin runId (para Lista AUTO / backfill)."""
    no_top = sorted(r.symbol for r in report.rows if r.slot_count == 0)
    no_run = sorted(
        r.symbol
        for r in report.rows
        if r.slot_count > 0 and r.slots_missing_run == r.slot_count
    )
    partial_run = sorted(
        r.symbol
        for r in report.rows
        if r.slot_count > 0 and 0 < r.slots_missing_run < r.slot_count
    )
    with_top = sorted(r.symbol for r in report.rows if r.slot_count > 0)
    # ASCII-safe for Windows consoles (cp1252); avoid UnicodeEncodeError.
    dash = "-"
    print(f"# IBEX operativa gaps - {report.as_of} - lista={report.list_id}")
    print(f"con_TOP={len(with_top)}/{report.instrument_count}")
    print(f"sin_TOP ({len(no_top)}): {', '.join(no_top) if no_top else dash}")
    print(
        f"TOP_sin_runId ({len(no_run)}): {', '.join(no_run) if no_run else dash}"
    )
    if partial_run:
        print(f"TOP_runId_parcial ({len(partial_run)}): {', '.join(partial_run)}")
    print(
        "\nOps: Universo -> Lista IBEX -> Play (ciclo ON) = Lista AUTO. "
        "Reevaluar resto si hay Omitido. "
        "Backfill runId: pnpm backfill:top-runids -- --symbol AENA --dry-run"
    )


def _print_report(report: AuditReport) -> None:
    print(f"IBEX35 live operativa · {report.as_of}")
    print(f"lista={report.list_name} ({report.list_id}) · n={report.instrument_count}")
    print(
        f"stickyTop1={report.sticky_top1_share * 100:.1f}% · "
        f"passed={report.passed} · critical={report.critical_count} · warn={report.warn_count}"
    )
    if report.top1_frequency:
        print("TOP #1 freq:", json.dumps(report.top1_frequency, ensure_ascii=False))
    print("Findings:")
    for f in report.findings:
        print(f"  [{f.severity}] {f.code}: {f.message}")
    print("\nPor valor (muestra):")
    for row in report.rows[:15]:
        print(
            f"  {row.symbol:6} bars={row.bar_count:5} top={row.top_status or '—':10} "
            f"ev={row.evidence_level or '—':16} #1={row.top1_type or '—'} "
            f"missRun={row.slots_missing_run}"
        )
    if len(report.rows) > 15:
        print(f"  … +{len(report.rows) - 15} más")


def _write_md(report: AuditReport, path: Path) -> None:
    lines = [
        f"# Auditoría operativa IBEX 35 — {report.as_of}",
        "",
        f"- Lista: **{report.list_name}** (`{report.list_id}`)",
        f"- Valores: {report.instrument_count} (catálogo esperado {report.expected_count})",
        f"- sticky TOP #1: {report.sticky_top1_share * 100:.1f}%",
        f"- Resultado: **{'PASS' if report.passed else 'FAIL'}** "
        f"(critical={report.critical_count}, warn={report.warn_count})",
        "",
        "## Findings",
        "",
    ]
    for f in report.findings:
        lines.append(f"- **[{f.severity}]** `{f.code}` — {f.message}")
    lines += ["", "## TOP #1 frequency", "", "```json", json.dumps(report.top1_frequency, indent=2), "```", ""]
    lines += ["## Por valor", "", "| Symbol | Bars | TOP status | Evidence | #1 | miss runId |", "|---|---:|---|---|---|---:|"]
    for row in report.rows:
        lines.append(
            f"| {row.symbol} | {row.bar_count} | {row.top_status or '—'} | "
            f"{row.evidence_level or '—'} | {row.top1_type or '—'} | {row.slots_missing_run} |"
        )
    lines += [
        "",
        "## Notas",
        "",
        "- Offline coach/Lista AUTO: `pnpm test:coach` (incluye `ibex35-operativa-audit.test.ts`).",
        "- Batería de backtests: `python scripts/research/run_ibex35_battery.py`.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit IBEX35 operativa (live DB)")
    parser.add_argument("--list-id", default="ibex35")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--min-bars", type=int, default=200)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--write-md",
        action="store_true",
        help="Escribe research/observations/YYYY-MM-DD-ibex35-operativa-audit.md",
    )
    parser.add_argument("--json", action="store_true", help="Dump JSON al stdout")
    parser.add_argument(
        "--print-missing",
        action="store_true",
        help="Solo lista símbolos sin TOP / sin runId (ops Lista AUTO)",
    )
    args = parser.parse_args()

    _load_env()

    import asyncio

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    report = asyncio.run(_run(args))
    if args.print_missing:
        _print_missing(report)
    elif args.json:
        payload = asdict(report)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(report)

    if args.write_md:
        out = (
            ROOT
            / "research"
            / "observations"
            / f"{report.as_of}-ibex35-operativa-audit.md"
        )
        _write_md(report, out)

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
