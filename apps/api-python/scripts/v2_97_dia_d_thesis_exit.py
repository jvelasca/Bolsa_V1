"""V2.97 · DÍA-D AUTO — QUIRÓFANO DEL ``THESIS_EXIT`` (read-only).

Qué es
------
El diagnóstico del origen de la pérdida (``v2_96``) aisló que el grueso del ``R`` bruto negativo
vive en pocos ciclos cerrados por invalidación de tesis (``THESIS_EXIT``), pese a que el
``STOP_EJECUTADO`` domina en frecuencia con expectancy bruta ~0. Esta sonda abre esos ciclos:
consume los ``K`` ledgers de ciclos que ``v2_94 --cycles --cycle-detail`` dejó por sorteo
(``draw-XX/multi-cycles.json``, esquema ``dia-d-multi-cycle-ledger-v4``) y los pliega para saber
**dónde viven** —estrategia, dirección, año/régimen, edad, geometría (MAE/MFE/captura), calidad de
entrada y coste— con su dispersión entre sorteos y su fragilidad.

No re-ejecuta el harness: sólo LEE los artefactos ya producidos.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO** sustituye la ventana PAPER: ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO** decide: descompone la muestra medida; **no** cambia motor ni umbrales.
* **NO** es causal: el motivo crudo es el token colapsado ``thesis_exit``, no la condición que lo
  disparó (recuperarla exigiría capturar el contexto del plan, que hoy no llega al journal).
* **Δ motor = 0:** no toca ningún fichero de motor; consume la costura inerte ya existente.
* Un hueco es ``None``/``NOT_MEASURED``; nunca se rellena con ``0``. El R neto sólo se afirma con
  fricción ``COMPLETE`` (con ``PARTIAL`` es un SUELO y se declara).

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \\
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

logger = logging.getLogger("v2_97_dia_d_thesis_exit")


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


def _fold_line(label_key: str, block: dict[str, Any], width: int = 22) -> str:
    """Una línea de un cubo: etiqueta, ciclos, expectancy bruta, MAE/media y fragilidad."""
    gross = (block["realizedRGross"]["expectancyR"] or {})
    mae = (block["excursion"]["maeR"].get("mean") if block.get("excursion") else None)
    fragility = block["fragility"]
    return (
        f"{str(block[label_key]):<{width}} {block['drawsWithCell']:>2}/{block['drawsTotal']:<2} "
        f"n={block['cycles']:>3}  exp {_fmt(gross.get('mean'))}  "
        f"MAE {_fmt(mae)}  {','.join(fragility['reasons']) or '-'}"
    )


def _print_text(artifact: dict[str, Any]) -> None:
    coverage = artifact["coverage"]
    print()
    print(f"DÍA-D AUTO · QUIRÓFANO THESIS_EXIT · K = {artifact['draws']} sorteos")
    print("=" * 100)
    print(f"años pedidos              {coverage['yearsRequested']}")
    print(
        f"detalle capturado         {'sí' if coverage.get('detailCaptured') else 'NO'} · "
        f"ciclos THESIS_EXIT {coverage.get('cyclesTotal')} · con fricción COMPLETE "
        f"{coverage.get('cyclesWithCompleteFriction')}"
    )
    print()
    print("GLOBAL")
    print("-" * 100)
    print(_fold_line("label", artifact["global"]))
    for axis, label_key in (
        ("byStrategy", "strategy"),
        ("byDirection", "direction"),
        ("byYear", "year"),
        ("byRegime", "regime"),
        ("byOperationalRegime", "operationalRegime"),
        ("byAgeBucket", "ageBucket"),
    ):
        print()
        print(axis.upper())
        print("-" * 100)
        for block in artifact[axis]:
            print(_fold_line(label_key, block))
    print()
    print(f"motivos crudos            {artifact['rawReasonTokens']}")
    concentration = artifact["concentration"]
    print(
        f"concentración             símbolos {concentration['distinctSymbols']} · "
        f"top símbolo {concentration['topSymbol']} "
        f"({_fmt(concentration['topSymbolShare'], '.2f')}) · "
        f"top semana {concentration['topWeek']} "
        f"({_fmt(concentration['topWeekShare'], '.2f')})"
    )
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
    parser.add_argument("--out", default=None, help="ruta del JSON del quirófano")
    args = parser.parse_args(argv)

    if args.draws is not None and int(args.draws) < 1:
        print("# uso incorrecto: --draws debe ser >= 1", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    from bolsa_application.dia_d_thesis_exit import (
        DEFAULT_LIMITS,
        build_thesis_exit_artifact,
    )

    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir

    try:
        ledgers = _load_ledgers(out_dir, limit=int(args.draws) if args.draws else None)
    except Exception as error:  # noqa: BLE001 — sin sorteos no hay evidencia: se DECLARA.
        print(f"# BLOQUEADO: no se pudo leer los sorteos ({type(error).__name__}: {error})", file=sys.stderr)
        return 2

    artifact = build_thesis_exit_artifact(
        draw_ledgers=ledgers,
        meta={
            "bump": "2.11.46.1-beta",
            "phase": "V2.97 DIA-D AUTO THESIS EXIT",
            "nature": "INVESTIGACION",
            "drawsDir": str(out_dir),
        },
        limits=list(DEFAULT_LIMITS),
    )

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    years = (artifact.get("coverage") or {}).get("yearsRequested") or []
    first_year = str(years[0]) if years else "all"
    last_year = str(years[-1]) if years else "all"
    default_name = f"thesis-exit-{first_year}_{last_year}.json"
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_text(artifact)
        print()
        print(f"quirófano                  {out_path}")
        print(f"sorteos leídos             {len(ledgers)} de {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
