"""V2.96 · DÍA-D AUTO — DIAGNÓSTICO DE DÓNDE NACE LA PÉRDIDA (read-only).

Qué es
------
La banda TOTAL (``v2_95``) midió cuánta varianza aporta el sorteo del venue y cuánta el muestreo
de ciclos. Esta sonda responde a la pregunta siguiente: **¿por qué se cierra cada ciclo y cuánto
pesa cada causa?** Consume los ``K`` ledgers de ciclos que ``v2_94 --cycles --cycle-detail`` dejó
por sorteo (``draw-XX/multi-cycles.json``) y los pliega en tres ejes:

* **mecanismo de salida** — R bruto (y neto) por clase de cierre, con su dispersión entre sorteos;
* **coste aplicado** — R bruto vs neto y cuánto come la fricción del simulador;
* **calidad de entrada** — excursión adversa TEMPRANA y desvío de ejecución (bps).

No re-ejecuta el harness: sólo LEE los artefactos ya producidos.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO** sustituye la ventana PAPER: ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO** decide: descompone la muestra medida; **no** cambia motor ni umbrales.
* **Δ motor = 0:** no toca ningún fichero de motor; el detalle se captura con la costura inerte.
* La banda por mecanismo es la **dispersión entre sorteos del venue**, no el bootstrap de ciclos.
* Un hueco es ``None``/``NOT_MEASURED``; nunca se rellena con ``0``.
* Sin ``--cycle-detail`` en la generación, el coste queda ``UNKNOWN`` (declarado, no en blanco).

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_96_dia_d_loss_origin.py \\
        --out-dir operability_runs/dia-d-auto-band
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"
_DRAWS_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto-band"

logger = logging.getLogger("v2_96_dia_d_loss_origin")


def _draw_dirs(out_dir: pathlib.Path) -> list[pathlib.Path]:
    """Carpetas ``draw-XX`` presentes, en orden determinista (no se inventa ninguna)."""
    return sorted(path for path in out_dir.glob("draw-*") if path.is_dir())


def _load_ledgers(out_dir: pathlib.Path, *, limit: int | None) -> list[Any]:
    """Carga los ledgers de ciclos por sorteo (fail-closed si falta alguno)."""
    ledgers: list[Any] = []
    for directory in _draw_dirs(out_dir):
        if limit is not None and len(ledgers) >= limit:
            break
        cycles_path = directory / "multi-cycles.json"
        if not cycles_path.is_file():
            raise RuntimeError(
                f"{directory.name}: falta {cycles_path.name} "
                "(¿se corrió v2_94 con --cycles?); ABORTO"
            )
        ledgers.append(json.loads(cycles_path.read_text(encoding="utf-8")))
    if not ledgers:
        raise RuntimeError(f"no hay sorteos en {out_dir}; ABORTO")
    return ledgers


# ── Presentación (nunca un 0 inventado donde hay hueco) ──────────────────────────


def _fmt(value: Any, spec: str = "+.4f") -> str:
    """Formatea un número o ``n/d`` si es un hueco declarado (nunca un ``0`` inventado)."""
    return "n/d" if value is None else format(float(value), spec)


def _disp(value: Any, spec: str = "+.4f") -> str:
    """``mean [min, max]`` de una dispersión, o ``n/d`` sin muestra."""
    if not isinstance(value, dict):
        return "n/d"
    return f"{_fmt(value.get('mean'), spec)} [{_fmt(value.get('min'), spec)}, {_fmt(value.get('max'), spec)}]"


def _print_text(artifact: dict[str, Any]) -> None:
    coverage = artifact["coverage"]
    print()
    print(f"DÍA-D AUTO · DÓNDE NACE LA PÉRDIDA · K = {artifact['draws']} sorteos")
    print("=" * 96)
    print(f"años pedidos              {coverage['yearsRequested']}")
    print(
        f"detalle capturado         {'sí' if coverage.get('detailCaptured') else 'NO'} · "
        f"ciclos {coverage.get('cyclesTotal')} · con fricción COMPLETE "
        f"{coverage.get('cyclesWithCompleteFriction')}"
    )
    print()
    print(f"{'MECANISMO':<18} {'n':>3} {'ciclos':>7} {'R bruto (media [min,max])':>28}  frágil")
    print("-" * 96)
    for row in artifact["byExitMechanism"]:
        gross = (row["realizedRGross"]["total"] or {})
        fragility = row["fragility"]
        print(
            f"{row['mechanism']:<18} {row['drawsWithCell']:>3} {row['cycles']:>7} "
            f"{_disp(gross):>28}  {','.join(fragility['reasons']) or '-'}"
        )
    print()
    costs = artifact["costImpact"]
    print(f"R bruto total (por sorteo)   {_disp(costs['realizedRGrossTotal'])}")
    print(f"R neto total (por sorteo)    {_disp(costs['realizedRNetTotal'])}"
          f"{'  [SUELO: hay ciclos sin fricción COMPLETE]' if costs['netIsLowerBound'] else ''}")
    print(f"fricción total (moneda)      {_disp(costs['frictionCostTotal'])}")
    print(f"fricción total (R)           {_disp(costs['frictionRTotal'])}")
    print(f"medición de fricción         {costs['frictionMeasurement']}")
    print()
    entry = artifact["entryQuality"]
    adverse = entry["adverseExcursion"]
    print(f"excursión adversa temprana   ventana {entry['windowDays']} días D1 · "
          f"medidos {adverse['measured']} · media {_fmt(adverse['meanR'])} R · "
          f"< -0.5R {_fmt(adverse['shareBelowHalfR'], '.2f')} · < -1R {_fmt(adverse['shareBelowOneR'], '.2f')}")
    slip = entry["entrySlippageBps"]
    print(f"desvío de entrada            medidos {slip['measured']} · media {_fmt(slip['mean'], '.2f')} bps "
          f"· >0 {_fmt(slip['shareAboveZero'], '.2f')}")
    if artifact.get("limits"):
        print()
        print("LÍMITES DECLARADOS")
        for item in artifact["limits"]:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=str(_DRAWS_SUBDIR),
        help="carpeta de los K sorteos de v2_94 (draw-XX/multi-cycles.json)",
    )
    parser.add_argument("--draws", type=int, default=None, help="tope de sorteos a leer (por defecto, todos)")
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON del diagnóstico")
    args = parser.parse_args(argv)

    if args.draws is not None and int(args.draws) < 1:
        print("# uso incorrecto: --draws debe ser >= 1", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    from bolsa_application.dia_d_loss_origin import (
        DEFAULT_LIMITS,
        build_loss_origin_artifact,
    )

    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir

    try:
        ledgers = _load_ledgers(out_dir, limit=int(args.draws) if args.draws else None)
    except Exception as error:  # noqa: BLE001 — sin sorteos no hay evidencia: se DECLARA.
        print(f"# BLOQUEADO: no se pudo leer los sorteos ({type(error).__name__}: {error})", file=sys.stderr)
        return 2

    artifact = build_loss_origin_artifact(
        draw_ledgers=ledgers,
        meta={
            "bump": "2.11.86-beta",
            "phase": "V2.96 DIA-D AUTO LOSS ORIGIN",
            "nature": "INVESTIGACION",
            "drawsDir": str(out_dir),
        },
        limits=list(DEFAULT_LIMITS),
    )

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    years = (artifact.get("coverage") or {}).get("yearsRequested") or []
    first_year = str(years[0]) if years else "all"
    last_year = str(years[-1]) if years else "all"
    default_name = f"loss-origin-{first_year}_{last_year}.json"
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_text(artifact)
        print()
        print(f"diagnóstico                {out_path}")
        print(f"sorteos leídos             {len(ledgers)} de {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
