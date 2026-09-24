#!/usr/bin/env python3
"""AUTO-19A — imprime el informe del REPLAY estadístico OOS (``statistical_oos_v1``).

Qué hace, exactamente: lee un JSON de ciclos (por defecto el fixture determinista
``auto_replay_cycles.json``) y emite por **stdout** el ``ReplayReport`` completo —las celdas
medidas y las cuatro respuestas con su veredicto y su muestra—. Es un instrumento PURO: no toca
Postgres, no re-simula órdenes y no mueve el reparto. Sin ``--cycles`` el fixture es SINTÉTICO: los
veredictos que salgan miden el instrumento, no la estrategia real.

Uso:

  python scripts/research/auto_replay_battery.py
  python scripts/research/auto_replay_battery.py --cycles /ruta/ciclos.json --oos-pct 0.25
  python scripts/research/auto_replay_battery.py --cycles ciclos.json > replay.json

El JSON de entrada puede ser una LISTA de ciclos o un OBJETO ``{"cycles": [...], "note": "..."}``:
la nota del fixture (si la trae) se copia a stderr, nunca al JSON de stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "py" / "analytics" / "src"))

from bolsa_analytics.cognitive.auto_adaptive_replay import (  # noqa: E402
    REPLAY_OOS_PCT_DEFAULT,
    build_replay_report,
)

DEFAULT_FIXTURE = (
    ROOT / "packages" / "py" / "analytics" / "tests" / "fixtures" / "auto_replay_cycles.json"
)


def _load(path: Path) -> tuple[list[Any], str]:
    """Ciclos y nota del JSON, con el contrato declarado (lista u objeto ``{"cycles": [...]}``)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        cycles = raw.get("cycles", [])
        note = str(raw.get("note", "") or "")
    else:
        cycles = raw
        note = ""
    if not isinstance(cycles, list):
        raise SystemExit(f"{path}: se esperaba una lista de ciclos o {{'cycles': [...]}}")
    return cycles, note


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=Path, default=DEFAULT_FIXTURE, help="JSON de ciclos")
    parser.add_argument(
        "--oos-pct", type=float, default=REPLAY_OOS_PCT_DEFAULT, help="fracción OOS (0.1–0.4)"
    )
    parser.add_argument("--seed", type=int, default=42, help="semilla del bootstrap declarada")
    parser.add_argument("--level", type=float, default=0.90, help="nivel del intervalo (0.5–0.99)")
    parser.add_argument("--resamples", type=int, default=2000, help="remuestreos del bootstrap")
    args = parser.parse_args(argv)

    if not args.cycles.exists():
        raise SystemExit(f"no existe el JSON de ciclos: {args.cycles}")
    cycles, note = _load(args.cycles)
    if note:
        print(f"# nota del material: {note}", file=sys.stderr)
    if args.cycles == DEFAULT_FIXTURE:
        print("# material SINTÉTICO por defecto: mide el instrumento, no la estrategia", file=sys.stderr)

    report = build_replay_report(
        cycles,
        oos_pct=args.oos_pct,
        seed=args.seed,
        interval_level=args.level,
        resamples=args.resamples,
    )
    json.dump(report.as_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
