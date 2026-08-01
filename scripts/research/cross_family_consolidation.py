"""
Campaign 3.5 — Cross-family consolidation from research_trials only.

No new entities, scores, Discovery Score, or Belief.
Tertiles ▲ / ○ / ▼ within each family from human IS Sharpe (ledger read).
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# Preset → family (Campaigns 1–3). Extend only when a closed campaign lands.
FAMILY_PRESETS: dict[str, tuple[str, ...]] = {
    "SMA": ("sma_crossover",),
    "RSI": ("rsi_mean_reversion", "rsi_momentum", "rsi_oversold_bounce"),
    "MACD": ("macd_signal_cross", "macd_zero_line"),
}

FAMILIES = tuple(FAMILY_PRESETS.keys())
PRESET_TO_FAMILY: dict[str, str] = {
    preset: family for family, presets in FAMILY_PRESETS.items() for preset in presets
}


@dataclass(frozen=True, slots=True)
class TrialLite:
    instrument_id: str
    symbol: str
    preset_key: str | None
    proposed_by: str
    k: int
    sharpe: float | None
    pnl: float | None
    trade_count: int | None
    score: float | None


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _tertiale_marks(ranked_ids: list[str]) -> dict[str, str]:
    """Assign ▲ / ○ / ▼ by rank position (equal thirds). No new score."""
    n = len(ranked_ids)
    if n == 0:
        return {}
    # Ceiling splits so n=35 → 12 / 12 / 11
    top_end = math.ceil(n / 3)
    mid_end = math.ceil(2 * n / 3)
    marks: dict[str, str] = {}
    for index, instrument_id in enumerate(ranked_ids):
        if index < top_end:
            marks[instrument_id] = "▲"
        elif index < mid_end:
            marks[instrument_id] = "○"
        else:
            marks[instrument_id] = "▼"
    return marks


def _observation(marks: dict[str, str]) -> str:
    values = [marks[f] for f in FAMILIES if f in marks]
    if not values:
        return "sin human IS en familias"
    ups = values.count("▲")
    downs = values.count("▼")
    mids = values.count("○")
    if ups == len(FAMILIES):
        return "fuerte en 3 familias"
    if downs == len(FAMILIES):
        return "débil consistente"
    if ups >= 2 and downs == 0:
        return "fuerte mayoritario"
    if downs >= 2 and ups == 0:
        return "débil mayoritario"
    if ups >= 1 and downs >= 1:
        return "depende de familia"
    if mids == len(values):
        return "zona media en todas"
    return "mixto / no extremo"


async def _fetch_all_trials(session: Any) -> list[TrialLite]:
    from bolsa_infrastructure.database.repositories.instrument_repository import (
        SqlAlchemyInstrumentRepository,
    )
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )

    trials_repo = SqlAlchemyResearchTrialRepository(session)
    instruments = SqlAlchemyInstrumentRepository(session)

    symbol_by_id: dict[str, str] = {}
    page_size = 500
    offset = 0
    rows: list[TrialLite] = []
    while True:
        page, total = await trials_repo.list_trials(limit=page_size, offset=offset)
        if not page:
            break
        for trial in page:
            if trial.instrument_id not in symbol_by_id:
                inst = await instruments.get_by_id(trial.instrument_id)
                symbol_by_id[trial.instrument_id] = (
                    inst.symbol if inst else trial.instrument_id[:8]
                )
            metrics = trial.is_metrics or {}
            rows.append(
                TrialLite(
                    instrument_id=trial.instrument_id,
                    symbol=symbol_by_id[trial.instrument_id],
                    preset_key=trial.preset_key,
                    proposed_by=trial.proposed_by,
                    k=int(trial.k_contribution or 0),
                    sharpe=_as_float(metrics.get("sharpeRatio")),
                    pnl=_as_float(metrics.get("totalReturnPct")),
                    trade_count=_as_int(metrics.get("tradeCount")),
                    score=_as_float(metrics.get("score")),
                )
            )
        offset += len(page)
        if offset >= total:
            break
    return rows


def _build_report(rows: list[TrialLite]) -> str:
    lines: list[str] = []
    total_k = sum(r.k for r in rows)
    null_sharpe = sum(1 for r in rows if r.sharpe is None)
    null_human = sum(1 for r in rows if r.proposed_by == "human" and r.sharpe is None)
    null_grid = sum(1 for r in rows if r.proposed_by == "grid" and r.sharpe is None)
    n_human = sum(1 for r in rows if r.proposed_by == "human")
    n_grid = sum(1 for r in rows if r.proposed_by == "grid")
    empty_trades = sum(1 for r in rows if r.trade_count == 0)
    empty_human = sum(1 for r in rows if r.proposed_by == "human" and r.trade_count == 0)
    empty_grid = sum(1 for r in rows if r.proposed_by == "grid" and r.trade_count == 0)

    lines.append("=== Campaña 3.5 — Consolidación cross-family (ledger only) ===")
    lines.append(f"trials={len(rows)} K={total_k} human={n_human} grid={n_grid}")
    lines.append(
        f"Sharpe nulo total: {null_sharpe}/{len(rows)} "
        f"({100.0 * null_sharpe / len(rows):.1f}%) "
        f"— human {null_human}/{n_human} · grid {null_grid}/{n_grid} "
        f"(grid H0 a menudo sin sharpeRatio en is_metrics)"
    )
    lines.append(
        f"tradeCount=0: {empty_trades}/{len(rows)} "
        f"({100.0 * empty_trades / len(rows):.1f}%) "
        f"— human {empty_human}/{n_human} · grid {empty_grid}/{n_grid}"
    )
    # K by instrument
    k_by_inst: dict[str, int] = defaultdict(int)
    trials_by_inst: dict[str, int] = defaultdict(int)
    symbol_by_id: dict[str, str] = {}
    for row in rows:
        k_by_inst[row.instrument_id] += row.k
        trials_by_inst[row.instrument_id] += 1
        symbol_by_id[row.instrument_id] = row.symbol

    # Human sharpes per family × instrument
    human_sharpes: dict[str, dict[str, list[float]]] = {
        family: defaultdict(list) for family in FAMILIES
    }
    human_by_preset: dict[str, list[TrialLite]] = defaultdict(list)
    for row in rows:
        if row.preset_key:
            human_by_preset[row.preset_key].append(row)
        if row.proposed_by != "human" or row.preset_key is None:
            continue
        family = PRESET_TO_FAMILY.get(row.preset_key)
        if family is None or row.sharpe is None:
            continue
        human_sharpes[family][row.instrument_id].append(row.sharpe)

    # Median Sharpe per instrument × family; tertiles within family
    median_by_family: dict[str, dict[str, float]] = {f: {} for f in FAMILIES}
    marks_by_family: dict[str, dict[str, str]] = {}
    dispersion: dict[str, float] = {}
    for family in FAMILIES:
        medians: list[tuple[str, float]] = []
        for instrument_id, values in human_sharpes[family].items():
            med = statistics.median(values)
            median_by_family[family][instrument_id] = med
            medians.append((instrument_id, med))
        medians.sort(key=lambda item: item[1], reverse=True)
        ranked = [instrument_id for instrument_id, _ in medians]
        marks_by_family[family] = _tertiale_marks(ranked)
        if len(medians) >= 2:
            dispersion[family] = statistics.pstdev(v for _, v in medians)
        elif medians:
            dispersion[family] = 0.0
        else:
            dispersion[family] = float("nan")

    lines.append("\n--- Dispersión human Sharpe (pstdev de medianas por activo) ---")
    for family in FAMILIES:
        value = dispersion[family]
        lines.append(
            f"  {family:4} pstdev={value:.4f}" if not math.isnan(value) else f"  {family:4} n/a"
        )

    # Matrix rows
    all_ids = sorted(symbol_by_id.keys(), key=lambda i: symbol_by_id[i])
    lines.append("\n--- Matriz Activo × Familia (tercios human Sharpe) ---")
    header = (
        f"{'Activo':6}  {'SMA':3}  {'RSI':3}  {'MACD':4}  "
        f"{'Trials':>6}  {'K':>5}  Observación"
    )
    lines.append(header)
    lines.append("-" * len(header))

    matrix_rows: list[tuple[str, dict[str, str], int, int, str]] = []
    for instrument_id in all_ids:
        marks = {
            family: marks_by_family[family].get(instrument_id, "—") for family in FAMILIES
        }
        obs = _observation({f: m for f, m in marks.items() if m != "—"})
        matrix_rows.append(
            (
                symbol_by_id[instrument_id],
                marks,
                trials_by_inst[instrument_id],
                k_by_inst[instrument_id],
                obs,
            )
        )

    # Sort: strong first, weak last, then symbol
    def sort_key(item: tuple[str, dict[str, str], int, int, str]) -> tuple[int, str]:
        marks = item[1]
        ups = sum(1 for f in FAMILIES if marks[f] == "▲")
        downs = sum(1 for f in FAMILIES if marks[f] == "▼")
        return (-ups, downs, item[0])

    matrix_rows.sort(key=sort_key)
    for symbol, marks, n_trials, k, obs in matrix_rows:
        lines.append(
            f"{symbol:6}  {marks['SMA']:3}  {marks['RSI']:3}  {marks['MACD']:4}  "
            f"{n_trials:6}  {k:5}  {obs}"
        )

    # Systematic strong / weak
    strong = [r for r in matrix_rows if r[4] in {"fuerte en 3 familias", "fuerte mayoritario"}]
    weak = [r for r in matrix_rows if r[4] in {"débil consistente", "débil mayoritario"}]
    depends = [r for r in matrix_rows if r[4] == "depende de familia"]

    lines.append("\n--- Respuestas del laboratorio ---")
    lines.append(
        "Sistemáticamente fuertes: "
        + (", ".join(r[0] for r in strong) if strong else "—")
    )
    lines.append(
        "Sistemáticamente débiles: "
        + (", ".join(r[0] for r in weak) if weak else "—")
    )
    lines.append(
        "Dependen de familia: "
        + (", ".join(r[0] for r in depends) if depends else "—")
    )

    # K concentration
    k_ranked = sorted(
        ((symbol_by_id[i], k_by_inst[i], trials_by_inst[i]) for i in k_by_inst),
        key=lambda x: x[1],
        reverse=True,
    )
    lines.append("\n--- Top K por activo ---")
    for symbol, k, n in k_ranked[:8]:
        lines.append(f"  {symbol:6} K={k} trials={n}")
    lines.append("--- Bottom K por activo ---")
    for symbol, k, n in k_ranked[-5:]:
        lines.append(f"  {symbol:6} K={k} trials={n}")

    # Empty experiments by preset (human + grid)
    lines.append("\n--- Presets: experimentos vacíos (tradeCount=0) ---")
    preset_stats: list[tuple[str, int, int, float]] = []
    for preset, items in sorted(human_by_preset.items()):
        empty = sum(1 for t in items if t.trade_count == 0)
        n = len(items)
        pct = 100.0 * empty / n if n else 0.0
        preset_stats.append((preset, empty, n, pct))
    preset_stats.sort(key=lambda x: (-x[3], -x[1], x[0]))
    for preset, empty, n, pct in preset_stats:
        lines.append(f"  {preset:22} empty={empty:4}/{n:<4} ({pct:5.1f}%)")

    # Median Sharpe table (numeric, for notebook — not a new score)
    lines.append("\n--- Median human Sharpe por activo × familia (referencia) ---")
    lines.append(f"{'Activo':6}  {'SMA':>8}  {'RSI':>8}  {'MACD':>8}")
    for symbol, marks, _, _, _ in matrix_rows:
        instrument_id = next(i for i, s in symbol_by_id.items() if s == symbol)
        cells = []
        for family in FAMILIES:
            med = median_by_family[family].get(instrument_id)
            cells.append(f"{med:8.3f}" if med is not None else f"{'—':>8}")
        lines.append(f"{symbol:6}  {cells[0]}  {cells[1]}  {cells[2]}")

    return "\n".join(lines) + "\n"


def _markdown_matrix(report: str) -> str:
    """Extract the matrix block into a markdown table."""
    capture = False
    rows: list[str] = []
    for line in report.splitlines():
        if line.startswith("--- Matriz"):
            capture = True
            continue
        if capture and line.startswith("--- ") and not line.startswith("--- Matriz"):
            break
        if not capture or not line.strip():
            continue
        if line.startswith("Activo"):
            rows.append("| Activo | SMA | RSI | MACD | Trials | K | Observación |")
            rows.append("|--------|-----|-----|------|--------|---|-------------|")
            continue
        if set(line.strip()) <= {"-"}:
            continue
        parts = line.split()
        # symbol mark mark mark trials k observation...
        if len(parts) < 6:
            continue
        symbol, sma, rsi, macd, trials, k = parts[:6]
        obs = " ".join(parts[6:])
        rows.append(f"| {symbol} | {sma} | {rsi} | {macd} | {trials} | {k} | {obs} |")
    return "\n".join(rows)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="IBEX35 Campaign 3.5 — cross-family consolidation")
    parser.add_argument(
        "--write-md",
        type=Path,
        default=None,
        help="Optional path to write markdown matrix fragment",
    )
    args = parser.parse_args()

    _load_env()

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)

    async with factory() as session:
        rows = await _fetch_all_trials(session)

    await engine.dispose()

    if not rows:
        print("ERROR: research_trials vacío", file=sys.stderr)
        return 1

    report = _build_report(rows)
    # Windows consoles often default to cp1252 — force UTF-8 for ▲/○/▼.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)

    if args.write_md is not None:
        args.write_md.parent.mkdir(parents=True, exist_ok=True)
        args.write_md.write_text(_markdown_matrix(report) + "\n", encoding="utf-8")
        print(f"Wrote matrix fragment → {args.write_md}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(_main()))
