"""V2.95 · DÍA-D AUTO — BOOTSTRAP DE CICLOS: la banda TOTAL (venue × sampling) (read-only).

Qué es
------
La banda del sorteo del venue (``v2_94``) mide UN eje de la incertidumbre del instrumento: cuánto
mueve el resultado la realización del venue simulador. Faltaba la otra mitad: cuánto puede variar
el resultado según **qué operaciones entran en la muestra**. Esta sonda la mide con un **bootstrap
no paramétrico** sobre los ciclos observados y compone ambos ejes en la **banda TOTAL**.

No re-ejecuta el harness: consume los ``K`` sorteos que ``v2_94`` ya dejó en ``--out-dir``
(``draw-XX/multi.json`` + ``draw-XX/multi-cycles.json``), reconstruye la banda del venue con la
MISMA función pura (``build_band_artifact``) y añade el bootstrap.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO** sustituye la ventana PAPER: ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO** decide: mide dos ejes de ruido del MISMO dato; **no** cambia motor ni umbrales.
* **Δ motor = 0:** no toca ningún fichero de motor; sólo LEE artefactos de sorteos.
* ``K`` sorteos **no** son ``K`` muestras independientes de mercado: son ``K`` realizaciones del
  MISMO experimento histórico con distinto sorteo del venue.
* Un hueco es ``None``/``NOT_MEASURED``; nunca se rellena con ``0``.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_95_dia_d_multi_bootstrap.py \\
        --out-dir operability_runs/dia-d-auto-band --resamples 2000
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Cruce tolerante contra el sello multirregimen (MISMA tolerancia que ``v2_92``/``v2_93``/``v2_94``).
_V92 = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_92_dia_d_attribution.py"

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"
_DRAWS_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto-band"

#: Remuestreos y semilla declarados del bootstrap (viajan en el artefacto).
_DEFAULT_RESAMPLES = 2000
_DEFAULT_SEED = 20261003

logger = logging.getLogger("v2_95_dia_d_multi_bootstrap")


def _load_v92() -> Any:
    """Carga el runner hermano ``v2_92`` por ruta (MISMO cross-check tolerante)."""
    spec = importlib.util.spec_from_file_location("v2_92_dia_d_attribution", _V92)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {_V92}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── Lectura de los K sorteos (multi.json + multi-cycles.json) ─────────────────────


def _draw_dirs(out_dir: pathlib.Path) -> list[pathlib.Path]:
    """Carpetas ``draw-XX`` presentes, en orden determinista (no se inventa ninguna)."""
    return sorted(path for path in out_dir.glob("draw-*") if path.is_dir())


def _load_draws(out_dir: pathlib.Path, *, limit: int | None) -> tuple[list[Any], list[Any]]:
    """Carga los artefactos del venue y sus ledgers de ciclos (fail-closed si falta uno)."""
    artifacts: list[Any] = []
    ledgers: list[Any] = []
    for directory in _draw_dirs(out_dir):
        if limit is not None and len(artifacts) >= limit:
            break
        artifact_path = directory / "multi.json"
        cycles_path = directory / "multi-cycles.json"
        if not artifact_path.is_file():
            raise RuntimeError(f"{directory.name}: falta {artifact_path.name}; ABORTO")
        if not cycles_path.is_file():
            raise RuntimeError(
                f"{directory.name}: falta {cycles_path.name} (¿se corrió v2_94 con --cycles?); ABORTO"
            )
        artifacts.append(json.loads(artifact_path.read_text(encoding="utf-8")))
        ledgers.append(json.loads(cycles_path.read_text(encoding="utf-8")))
    if not artifacts:
        raise RuntimeError(f"no hay sorteos en {out_dir}; ABORTO")
    return artifacts, ledgers


# ── Presentación (nunca un 0 inventado donde hay hueco) ──────────────────────────


def _fmt(value: Any, spec: str = "+.4f") -> str:
    """Formatea un número o ``n/d`` si es un hueco declarado (nunca un ``0`` inventado)."""
    return "n/d" if value is None else format(float(value), spec)


def _print_text(artifact: dict[str, Any]) -> None:
    coverage = artifact["coverage"]
    print()
    print(
        f"DÍA-D AUTO · BOOTSTRAP DE CICLOS · K = {artifact['draws']} sorteos · "
        f"B = {artifact['resamples']} (semilla {artifact['seed']})"
    )
    print("=" * 96)
    print(f"años pedidos              {coverage['yearsRequested']}")
    for row in coverage["perYear"]:
        print(
            f"  {row['year']}  medidos {row['measured']}/{coverage['drawsTotal']} · "
            f"vacíos {row['empty']} · no medidos {row['notMeasured']}"
            + (f" · motivos {row['reasons']}" if row["reasons"] else "")
        )
    cross = artifact.get("venueBandCrossCheck") or {}
    if cross.get("available"):
        print(
            f"cruce banda del venue      drift={cross.get('evidenceDrift')} "
            f"({cross.get('driftedKeys')})"
        )
    print()
    header = (
        f"{'DIMENSIÓN':<14} {'ETIQUETA':<24} {'n':>3} {'R medio':>9} "
        f"{'var venue':>10} {'var samp':>10} {'se total':>9}  venue  samp  total  frágil"
    )
    print(header)
    print("-" * 96)

    def _row(title: str, label: str, cell: dict[str, Any]) -> None:
        metric = (cell.get("metrics") or {}).get("realizedRTotal") or {}
        venue = metric.get("venue") or {}
        sampling = metric.get("sampling") or {}
        total = metric.get("total") or {}
        validity = cell.get("validity") or {}
        fragility = cell.get("fragility") or {}
        print(
            f"{title:<14} {label:<24} {cell['drawsWithCell']:>3} {_fmt(metric.get('mean')):>9} "
            f"{_fmt(venue.get('var'), '.4f'):>10} {_fmt(sampling.get('var'), '.4f'):>10} "
            f"{_fmt(total.get('se'), '.4f'):>9}  "
            f"{str(validity.get('venuePointCitable')):>5} "
            f"{str(validity.get('samplingPointCitable')):>5} "
            f"{str(validity.get('totalPointCitable')):>5}  "
            f"{','.join(fragility.get('reasons') or []) or '-'}"
        )

    print("GLOBAL")
    _row("GLOBAL", "todos", artifact["global"])
    for key, title, dim in (
        ("byYear", "AÑO", "year"),
        ("byRegime", "RÉGIMEN", "regime"),
        ("byOperationalRegime", "RÉG. OPERATIVO", "regime"),
        ("byYearByRegime", "AÑO × RÉGIMEN", None),
    ):
        print(title)
        for cell in artifact[key]:
            label = str(cell.get(dim, "")) if dim else f"{cell.get('year')} × {cell.get('regime')}"
            _row("", label, cell)
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
        help="carpeta de los K sorteos de v2_94 (draw-XX/multi.json + multi-cycles.json)",
    )
    parser.add_argument("--draws", type=int, default=None, help="tope de sorteos a leer (por defecto, todos)")
    parser.add_argument("--resamples", type=int, default=_DEFAULT_RESAMPLES, help="remuestreos B del bootstrap")
    parser.add_argument("--seed", type=int, default=_DEFAULT_SEED, help="semilla declarada del bootstrap")
    parser.add_argument(
        "--check-against", default=None, help="artefacto multirregimen sellado para cruzar el sorteo 0"
    )
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON combinado (venue × sampling)")
    args = parser.parse_args(argv)

    if args.draws is not None and int(args.draws) < 1:
        print("# uso incorrecto: --draws debe ser >= 1", file=sys.stderr)
        return 1
    if int(args.resamples) < 0:
        print("# uso incorrecto: --resamples debe ser >= 0", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    from bolsa_application.dia_d_multi_sampling import (
        DEFAULT_LIMITS,
        build_sampling_artifact,
    )
    from bolsa_application.dia_d_multi_uncertainty import build_band_artifact

    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir

    try:
        artifacts, ledgers = _load_draws(out_dir, limit=int(args.draws) if args.draws else None)
    except Exception as error:  # noqa: BLE001 — sin sorteos no hay evidencia: se DECLARA.
        print(f"# BLOQUEADO: no se pudo leer los sorteos ({type(error).__name__}: {error})", file=sys.stderr)
        return 2

    # La componente venue se reconstruye con la MISMA función pura del sello (autochequeo interno).
    venue_band = build_band_artifact(draws=artifacts)

    v92 = _load_v92()
    reference = v92._load_cross_check(args.check_against)  # noqa: SLF001 — MISMA tolerancia.
    venue_cross_check = v92._cross_check_summary(  # noqa: SLF001
        reference, current=artifacts[0].get("summary") or {}
    )

    limits = list(DEFAULT_LIMITS)
    if venue_cross_check.get("available"):
        limits.append(
            "El sorteo 0 se cruzó contra el sello multirregimen: el instrumento no compara otra cosa."
        )

    artifact = build_sampling_artifact(
        draw_ledgers=ledgers,
        resamples=int(args.resamples),
        seed=int(args.seed),
        venue_band=venue_band,
        meta={
            "bump": "2.11.49-beta",
            "phase": "V2.95 DIA-D AUTO MULTI BOOTSTRAP",
            "nature": "INVESTIGACION",
            "venueBandDraws": int(venue_band.get("draws") or 0),
            "venueCrossCheck": dict(venue_cross_check),
        },
        limits=limits,
    )

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    years = (artifact.get("coverage") or {}).get("yearsRequested") or []
    first_year = str(years[0]) if years else "all"
    last_year = str(years[-1]) if years else "all"
    default_name = f"multi-sampling-{first_year}_{last_year}.json"
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_text(artifact)
        print()
        print(f"banda combinada           {out_path}")
        print(f"sorteos leídos            {len(ledgers)} de {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
