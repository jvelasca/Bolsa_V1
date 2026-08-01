#!/usr/bin/env python3
"""Prep FA: refresh Yahoo + cobertura Piotroski/ROIC/Beneish/beta/ADV.

Uso (repo root, DB up):
  python scripts/research/audit_fa_coverage.py
  python scripts/research/audit_fa_coverage.py --symbols AAPL,MSFT,SAN.MC,BBVA.MC
  python scripts/research/audit_fa_coverage.py --no-refresh   # solo lee BD
  python scripts/research/audit_fa_coverage.py --json

Exit: 0 siempre que haya filas; 1 si no resuelve ningún símbolo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "packages" / "py" / "domain" / "src"),
    str(ROOT / "packages" / "py" / "analytics" / "src"),
    str(ROOT / "packages" / "py" / "market" / "src"),
    str(ROOT / "packages" / "py" / "infrastructure" / "src"),
    str(ROOT / "packages" / "py" / "application" / "src"),
]

# Mix US + ES para la prep de prueba (≤8)
DEFAULT_SYMBOLS = [
    "AAPL",
    "MSFT",
    "JNJ",
    "SAN.MC",
    "BBVA.MC",
    "ITX.MC",
    "IBE.MC",
    "ACS.MC",
]

COVERAGE_KEYS = (
    "piotroski",
    "roic",
    "beneishM",
    "beta",
    "advUsd",
    "wacc",
    "dcfUpside",
    "grahamNumber",
    "altmanZ",
)


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 1) if total else 0.0


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from bolsa_application.refresh_instrument_fundamentals import RefreshInstrumentFundamentals
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.instrument_repository import (
        SqlAlchemyInstrumentRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []

    async with factory() as session:
        instruments = SqlAlchemyInstrumentRepository(session)
        refresher = RefreshInstrumentFundamentals(instruments)
        id_map = await instruments.get_ids_by_yahoo_symbols(symbols)

        for sym in symbols:
            iid = id_map.get(sym)
            if not iid:
                # fallback: search catalog
                hits = await instruments.search_catalog(sym, limit=3)
                match = next(
                    (h for h in hits if h.yahoo_symbol.upper() == sym.upper() or h.symbol.upper() == sym.upper()),
                    hits[0] if hits and len(hits) == 1 else None,
                )
                if match is None:
                    unresolved.append(sym)
                    continue
                iid = match.id
                yahoo = match.yahoo_symbol
                ticker = match.symbol
            else:
                inst = await instruments.get_by_id(iid)
                yahoo = inst.yahoo_symbol if inst else sym
                ticker = inst.symbol if inst else sym

            fund: dict[str, Any] | None = None
            refresh_status = "skipped"
            if not args.no_refresh:
                before = await instruments.get_fundamentals(iid)
                fund = await refresher.execute(iid)
                await session.commit()
                if fund is None:
                    refresh_status = "failed"
                    fund = before
                elif before is None or fund.get("fetchedAt") != (before or {}).get("fetchedAt"):
                    refresh_status = "refreshed"
                else:
                    refresh_status = "unchanged"
            else:
                fund = await instruments.get_fundamentals(iid)
                refresh_status = "read_only"

            fund = fund or {}
            row = {
                "instrumentId": iid,
                "symbol": ticker,
                "yahooSymbol": yahoo,
                "refresh": refresh_status,
                "fetchedAt": fund.get("fetchedAt"),
                "sourceVersion": fund.get("sourceVersion"),
                "sector": fund.get("sector"),
                "waccMethod": fund.get("waccMethod"),
                "metrics": {k: fund.get(k) for k in COVERAGE_KEYS},
            }
            rows.append(row)

    await engine.dispose()

    total = len(rows)
    coverage = {
        k: {
            "present": sum(1 for r in rows if r["metrics"].get(k) is not None),
            "pct": _pct(sum(1 for r in rows if r["metrics"].get(k) is not None), total),
        }
        for k in COVERAGE_KEYS
    }
    capm = sum(1 for r in rows if r.get("waccMethod") == "fund_capm_v1")
    sector_wacc = sum(1 for r in rows if r.get("waccMethod") == "fund_wacc_sector_v1")

    return {
        "asOf": datetime.now(timezone.utc).isoformat(),
        "requested": symbols,
        "resolved": total,
        "unresolved": unresolved,
        "refreshed": sum(1 for r in rows if r["refresh"] == "refreshed"),
        "failedRefresh": sum(1 for r in rows if r["refresh"] == "failed"),
        "coverage": coverage,
        "waccMethod": {"fund_capm_v1": capm, "fund_wacc_sector_v1": sector_wacc},
        "rows": rows,
    }


def _print_human(report: dict[str, Any]) -> None:
    print("=== audit_fa_coverage ===")
    print(
        f"resolved={report['resolved']}/{len(report['requested'])} "
        f"refreshed={report['refreshed']} failed={report['failedRefresh']}"
    )
    if report["unresolved"]:
        print(f"UNRESOLVED: {', '.join(report['unresolved'])}")
    print("--- coverage % (non-null) ---")
    for k, v in report["coverage"].items():
        print(f"  {k}: {v['present']}/{report['resolved']} ({v['pct']}%)")
    wm = report["waccMethod"]
    print(f"  waccMethod CAPM={wm['fund_capm_v1']} sector={wm['fund_wacc_sector_v1']}")
    print("--- per ticker ---")
    for r in report["rows"]:
        m = r["metrics"]
        flags = []
        for k in ("piotroski", "roic", "beneishM", "beta", "advUsd"):
            flags.append(f"{k[0].upper()}={'Y' if m.get(k) is not None else '-'}")
        print(
            f"  {r['yahooSymbol']:10} {r['refresh']:10} "
            f"F={m.get('piotroski')} ROIC={_fmt(m.get('roic'))} "
            f"M={_fmt(m.get('beneishM'))} beta={_fmt(m.get('beta'))} "
            f"wacc={r.get('waccMethod') or '-'} [{' '.join(flags)}]"
        )


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def main() -> int:
    _load_env()
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description="FA coverage prep (Yahoo refresh)")
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Yahoo symbols comma-separated",
    )
    parser.add_argument("--no-refresh", action="store_true", help="Solo leer BD")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    report = asyncio.run(_run(args))
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_human(report)

    if report["resolved"] == 0:
        print("FAIL: ningun simbolo resuelto")
        return 1
    print("OK: FA coverage audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
