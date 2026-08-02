#!/usr/bin/env python3
"""Q1.3 — Δ ranking estabilidad entre dos campaign tags.

Compara tercios human Sharpe (SMA/RSI/MACD) de dos ventanas/campañas
y escribe un informe markdown.

Usage:
  python scripts/research/stability_ranking_delta.py \\
    --campaign-a ibex35-window-a --campaign-b ibex35-window-b \\
    --write-md research/observations/2026-08-02-stability-delta.md
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))

from cross_family_consolidation import (  # noqa: E402
    FAMILIES,
    _fetch_all_trials,
    _load_env,
    extract_marks_by_symbol,
)


def _delta_table(
    marks_a: dict[str, dict[str, str]],
    marks_b: dict[str, dict[str, str]],
) -> tuple[str, dict[str, int]]:
    symbols = sorted(set(marks_a) | set(marks_b))
    lines = [
        "| Activo | Familia | A | B | Δ |",
        "|--------|---------|---|---|---|",
    ]
    stats = {"same": 0, "changed": 0, "missing": 0}
    for symbol in symbols:
        for family in FAMILIES:
            a = marks_a.get(symbol, {}).get(family, "—")
            b = marks_b.get(symbol, {}).get(family, "—")
            if a == "—" and b == "—":
                continue
            if a == "—" or b == "—":
                delta = "missing"
                stats["missing"] += 1
            elif a == b:
                delta = "same"
                stats["same"] += 1
            else:
                delta = f"{a}→{b}"
                stats["changed"] += 1
            if delta == "same":
                continue
            lines.append(f"| {symbol} | {family} | {a} | {b} | {delta} |")
    if len(lines) == 2:
        lines.append("| — | — | — | — | (sin cambios ni huecos) |")
    return "\n".join(lines), stats


async def _run(args: argparse.Namespace) -> int:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)

    async with factory() as session:
        rows_a = await _fetch_all_trials(session, campaign=args.campaign_a)
        rows_b = await _fetch_all_trials(session, campaign=args.campaign_b)
    await engine.dispose()

    if not rows_a:
        print(f"ERROR: campaign A vacío: {args.campaign_a}", file=sys.stderr)
        return 1
    if not rows_b:
        print(f"ERROR: campaign B vacío: {args.campaign_b}", file=sys.stderr)
        return 1

    marks_a = extract_marks_by_symbol(rows_a)
    marks_b = extract_marks_by_symbol(rows_b)
    table, stats = _delta_table(marks_a, marks_b)

    md = "\n".join(
        [
            "# Informe estabilidad temporal (Q1.3)",
            "",
            f"- **Ventana A:** `{args.campaign_a}` (trials={len(rows_a)})",
            f"- **Ventana B:** `{args.campaign_b}` (trials={len(rows_b)})",
            f"- **Celdas same / changed / missing:** "
            f"{stats['same']} / {stats['changed']} / {stats['missing']}",
            "",
            "## Caveat",
            "",
            "Sharpe mediano cross-family ≠ verdad; mirar tradeCount/Calmar (Q0.4).",
            "Solo human IS; grid no entra en tercios.",
            "",
            "## Δ ranking (solo celdas changed/missing)",
            "",
            table,
            "",
            "## Gate C4",
            "",
            "Abrir C4 solo si hay hipótesis escrita **y** este Δ lo justifica "
            "(p.ej. patrón de fortaleza por activo se rompe con volatilidad).",
            "",
        ]
    )

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(md)

    if args.write_md:
        path = Path(args.write_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md, encoding="utf-8")
        print(f"Wrote → {path}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Stability ranking Δ between two campaigns")
    p.add_argument("--campaign-a", required=True)
    p.add_argument("--campaign-b", required=True)
    p.add_argument("--write-md", type=Path, default=None)
    args = p.parse_args()
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
