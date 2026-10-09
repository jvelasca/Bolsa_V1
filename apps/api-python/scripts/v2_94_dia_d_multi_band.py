"""V2.94 · DÍA-D AUTO — DE PUNTO A BANDA: la incertidumbre del SORTEO del venue (read-only).

Qué es
------
La atribución multirregimen (``v2_93``) publica un PUNTO por año/régimen (``expectancyR``).
Esta sonda corre el MISMO harness ``K`` veces, cada sorteo con el **ancla temporal del seed del
fill** desplazada (``fill_seed(bar_tick_now + k, symbol)``, la MISMA técnica sellada por ``W3.3``
en ``v2_88_16_3``), restaura el árbol **byte a byte** tras cada sorteo y pliega los ``K``
artefactos en una **banda**:

* ``min``/``median``/``max``/``mean``/``stdev`` por cubo (año / régimen / año × régimen / global);
* ``validity``: ``crossesZeroR`` y ``pointCitable`` con el criterio de ``W3.3``
  (``point_citable`` sólo si la banda de R NO cruza cero y ``|media| > 1.96·SE``).

``k = 0`` es la realización de PRODUCCIÓN (sin parchear): el autochequeo del instrumento. La sonda
lo cruza contra el artefacto sellado que se le pase con ``--check-against`` (tolerante, de ``v2_92``).

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO** sustituye la ventana PAPER: ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO** decide: mide el ruido del sorteo del MISMO dato; **no** cambia motor ni umbrales.
* **Δ motor = 0:** el ``seed`` se inyecta y se restaura byte a byte; ningún fichero de motor queda
  modificado (se VERIFICA tras cada sorteo).
* Un hueco es ``None``/``NOT_MEASURED``; nunca se rellena con ``0``.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \\
        --from-year 2021 --to-year 2026 --universe pit --draws 12
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import pathlib
import subprocess
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

#: Runner de la atribución multirregimen (una pasada por año) y su cruce tolerante.
_V93 = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_93_dia_d_multi.py"
_V92 = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_92_dia_d_attribution.py"
#: Matriz de mutaciones: presta ``_apply``/``_restore``/``_drop_bytecode`` (restauración byte a byte).
_MUTATIONS = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_44_mutation_audit.py"

#: Sorteo del venue, en su ÚNICA fuente (``auto_simulation_worker.py``): el ancla temporal del
#: ``seed`` del book SIM. La sonda la desplaza por sorteo y la restaura byte a byte.
_WORKER_REL = "apps/api-python/src/bolsa_api/background/auto_simulation_worker.py"
_SEED_LINE = "                seed=fill_seed(bar_tick_now, symbol),\n"

#: Cuenta y versión de la ventana (MISMOS valores que ``v2_86``/``v2_91``/``v2_92``/``v2_93``).
_DEFAULT_ACCOUNT = "1484e253d2d54645945a6b1d7"
_DEFAULT_VERSION_A = "v283-window-a"
_DEFAULT_EDGE = 0.9
#: Sorteos declarados (``k = 0`` es producción y NO se parchea). ``K`` = ``--draws``.
_DEFAULT_DRAWS = 12
#: Ventana por defecto de la excursión adversa TEMPRANA (misma que ``DEFAULT_ENTRY_WINDOW_DAYS``).
_DEFAULT_ENTRY_WINDOW_DAYS = 3

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"
_DRAWS_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto-band"

#: Nota declarada del determinismo del precio (el replay inyecta ``price_script`` histórico).
AUTO_REAL_PRICE_NOTE = "AUTO_ENGINE_SIM_REAL_PRICE=0 (price_script historico inyectado)"

logger = logging.getLogger("v2_94_dia_d_multi_band")


def _load_module(filename: str, name: str) -> Any:
    """Carga un runner hermano por ruta (mismo patrón que ``v2.89``→…→``v2.93``)."""
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_v92() -> Any:
    return _load_module("v2_92_dia_d_attribution.py", "v2_92_dia_d_attribution")


def _load_mutations() -> Any:
    """Matriz de mutaciones (restauración byte a byte); no se ejecuta ninguna mutación."""
    spec = importlib.util.spec_from_file_location("v2_44_mutation_audit", _MUTATIONS)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {_MUTATIONS}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── Comando del runner multirregimen (v2_93) ─────────────────────────────────────


def _v93_command(
    args: argparse.Namespace,
    out_path: pathlib.Path,
    *,
    cycles_out: pathlib.Path | None = None,
) -> list[str]:
    """Argv del runner ``v2_93`` para UN sorteo (el seed no viaja aquí: se parchea el árbol)."""
    command = [sys.executable, str(_V93)]
    if args.years:
        command += ["--years", str(args.years)]
    elif args.from_year is not None and args.to_year is not None:
        command += ["--from-year", str(args.from_year), "--to-year", str(args.to_year)]
    else:
        raise RuntimeError("indica --years o --from-year/--to-year")
    command += [
        "--universe",
        str(args.universe),
        "--watch-size",
        str(args.watch_size),
        "--min-bars",
        str(args.min_bars),
        "--history-days",
        str(args.history_days),
        "--horizon-days",
        str(args.horizon_days),
        "--edge",
        str(args.edge),
        "--account-id",
        str(args.account_id),
        "--version-a",
        str(args.version_a),
        "--venue",
        str(args.venue),
        "--attribution-top-k",
        str(args.attribution_top_k),
    ]
    if args.watch:
        command += ["--watch", str(args.watch)]
    command += ["--fallback" if args.fallback else "--no-fallback"]
    command += ["--out", str(out_path)]
    if cycles_out is not None:
        command += ["--cycles-out", str(cycles_out)]
    if bool(getattr(args, "cycle_detail", False)):
        # Costura inerte (Δ motor = 0): sólo se propaga cuando el diagnóstico lo pide.
        command += ["--cycle-detail", "--entry-window-days", str(int(args.entry_window_days))]
    return command


def _run_v93(
    args: argparse.Namespace,
    out_path: pathlib.Path,
    *,
    cycles_out: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Corre ``v2_93`` en un proceso NUEVO (el árbol parcheado del seed debe cargarse fresco)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(  # noqa: S603 — argv construido, no hay shell.
        _v93_command(args, out_path, cycles_out=cycles_out),
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=7200,
        env=env,
    )
    if result.returncode != 0 or not out_path.is_file():
        raise RuntimeError(
            f"v2_93 no produjo artefacto (exit {result.returncode}):\n"
            f"{(result.stdout or '')[-2000:]}\n{(result.stderr or '')[-2000:]}"
        )
    return json.loads(out_path.read_text(encoding="utf-8"))


#: Esquema del ledger que se considera "con detalle" para reutilizar un sorteo. Se sube con cada
#: capa aditiva (v2: fricción/mecanismo; v3: estrategia/dirección; v4: geometría de la invalidación;
#: v5: desambiguación THESIS_EXIT vs STOP; v6: correlación decisión↔ciclo) para forzar la
#: REEJECUCIÓN de un ledger antiguo y no mezclar esquemas en el diagnóstico.
_DETAIL_LEDGER_SCHEMA = "dia-d-multi-cycle-ledger-v7"


def _ledger_has_detail(cycles_path: pathlib.Path) -> bool:
    """True si el ledger existente ya trae el detalle vigente (v5). Si no, se re-corre."""
    if not cycles_path.is_file():
        return False
    try:
        payload = json.loads(cycles_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return str(payload.get("schemaVersion") or "") == _DETAIL_LEDGER_SCHEMA


def _draw(args: argparse.Namespace, *, k: int, out_dir: pathlib.Path, mutations: Any) -> dict[str, Any]:
    """Un sorteo: parchea el seed (si ``k > 0``), corre ``v2_93``, restaura byte a byte."""
    draw_path = out_dir / f"draw-{k:02d}" / "multi.json"
    cycles_path = out_dir / f"draw-{k:02d}" / "multi-cycles.json"
    # Con ``--cycle-detail`` sólo se reutiliza un sorteo cuyo ledger YA es v2: un ledger v1 (sin
    # detalle) se re-corre para no mezclar esquemas en el diagnóstico.
    reusable = args.reuse and draw_path.is_file() and (
        not args.cycles or (cycles_path.is_file() and (not args.cycle_detail or _ledger_has_detail(cycles_path)))
    )
    if reusable:
        print(f"### draw {k:02d}  (reutilizado de {draw_path.name})")
        return json.loads(draw_path.read_text(encoding="utf-8"))
    draw_path.parent.mkdir(parents=True, exist_ok=True)

    worker = _REPO_ROOT / _WORKER_REL
    original = ""
    restored = True
    try:
        if k > 0:
            original = worker.read_text(encoding="utf-8")
            hits = original.count(_SEED_LINE)
            if hits != 1:
                raise RuntimeError(f"el ancla del seed aparece {hits} veces en {_WORKER_REL}; ABORTO")
            patched = original.replace(
                _SEED_LINE,
                f"                seed=fill_seed(bar_tick_now + {k}, symbol),\n",
                1,
            ).encode("utf-8")
            if not mutations._apply(worker, patched):  # noqa: SLF001 — sonda
                raise RuntimeError(f"draw {k:02d}: no se pudo escribir el sorteo; ABORTO")
            mutations._drop_bytecode((_WORKER_REL,))  # noqa: SLF001
            live = worker.read_text(encoding="utf-8")
            if f"fill_seed(bar_tick_now + {k}, symbol)" not in live:  # vivacidad del EDIT
                raise RuntimeError(f"draw {k:02d}: el desplazamiento no está en el fichero; ABORTO")
            print(f"### draw {k:02d}  (re-sorteo: seed=fill_seed(bar_tick_now + {k}, ...))")
        else:
            print("### draw 00  (realización de PRODUCCIÓN, sin tocar el árbol)")
        payload = _run_v93(args, draw_path, cycles_out=cycles_path if args.cycles else None)
    finally:
        if k > 0:
            restored = mutations._restore(worker, _WORKER_REL, original)  # noqa: SLF001
            mutations._drop_bytecode((_WORKER_REL,))  # noqa: SLF001
            if restored and worker.read_text(encoding="utf-8") != original:
                restored = False
    if not restored:
        raise RuntimeError(f"{_WORKER_REL} NO se restauró byte a byte; ABORTO (árbol en riesgo)")
    summary = payload.get("summary") or {}
    print(
        f"    veredicto {summary.get('verdict')} · ciclos {summary.get('measuredCycles')} · "
        f"R {_fmt(summary.get('expectancyR'), '+.4f')} · R total {_fmt(summary.get('realizedRTotal'))}"
    )
    return payload


def _fmt(value: Any, spec: str = "+.3f") -> str:
    """Formatea un número o ``n/d`` si es un hueco declarado (nunca un ``0`` inventado)."""
    return "n/d" if value is None else format(float(value), spec)


def _print_text(artifact: dict[str, Any]) -> None:
    coverage = artifact["coverage"]
    print()
    print(f"DÍA-D AUTO · BANDA MULTIRREGIMEN · K = {artifact['draws']} sorteos")
    print("=" * 78)
    print(f"años pedidos              {coverage['yearsRequested']}")
    for row in coverage["perYear"]:
        print(
            f"  {row['year']}  medidos {row['measured']}/{coverage['drawsTotal']} · "
            f"vacíos {row['empty']} · no medidos {row['notMeasured']}"
            + (f" · motivos {row['reasons']}" if row["reasons"] else "")
        )
    cross = artifact.get("crossCheck") or {}
    if cross.get("available"):
        print(
            f"cruce contra sello        drift={cross.get('evidenceDrift')} "
            f"({cross.get('driftedKeys')})"
        )
    print()
    header = f"{'DIMENSIÓN':<14} {'ETIQUETA':<24} {'n':>3}  {'R medio':>9} {'R banda':>22}  citable"
    print(header)
    print("-" * 78)

    def _row(title: str, label: str, cell: dict[str, Any]) -> None:
        expectancy = cell["bands"]["expectancyR"]
        total = cell["bands"]["realizedRTotal"]
        validity = cell["validity"]
        band_text = (
            "n/d"
            if total is None
            else f"[{_fmt(total['min'])}, {_fmt(total['max'])}]"
        )
        print(
            f"{title:<14} {label:<24} {cell['drawsWithCell']:>3}  "
            f"{_fmt(expectancy['mean'] if expectancy else None):>9} "
            f"{band_text:>22}  {validity['pointCitable']}"
        )

    print("GLOBAL")
    _row("GLOBAL", "todos", artifact["global"])
    for key, title, dim in (
        ("byYear", "AÑO", "year"),
        ("byRegime", "RÉGIMEN", "regime"),
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
    parser.add_argument("--from-year", type=int, default=None, help="primer año (YYYY) del rango")
    parser.add_argument("--to-year", type=int, default=None, help="último año (YYYY) del rango")
    parser.add_argument("--years", default=None, help="años separados por coma (alternativa a --from/--to)")
    parser.add_argument("--watch", default=None, help="instrumentos separados por coma (si falta, universo)")
    parser.add_argument(
        "--universe",
        default="pit",
        choices=("catalog", "pit"),
        help="fuente del watch si no hay --watch: 'pit' (Universe(D) por año, por defecto) o 'catalog'",
    )
    parser.add_argument("--watch-size", type=int, default=20, help="tamaño del watch derivado")
    parser.add_argument("--min-bars", type=int, default=60, help="barras D1 mínimas en el watch derivado")
    parser.add_argument("--history-days", type=int, default=90, help="días previos a D0 simulados")
    parser.add_argument("--horizon-days", type=int, default=20, help="días posteriores a D1 simulados")
    parser.add_argument("--edge", type=float, default=_DEFAULT_EDGE, help="valor declarado del seam de edge")
    parser.add_argument(
        "--attribution-top-k", type=int, default=5, help="mejores/peores ciclos de la concentración"
    )
    parser.add_argument("--account-id", default=_DEFAULT_ACCOUNT, help="cuenta de la ventana (etiqueta)")
    parser.add_argument("--version-a", default=_DEFAULT_VERSION_A, help="versión A de la ventana")
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument(
        "--fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="si una corrida trunca, reintenta una vez sobre el tramo operable más largo",
    )
    parser.add_argument("--draws", type=int, default=_DEFAULT_DRAWS, help="numero K de sorteos del venue")
    parser.add_argument(
        "--cycles",
        action="store_true",
        help="persiste el ledger de ciclos por sorteo (multi-cycles.json) para el bootstrap de v2_95",
    )
    parser.add_argument(
        "--cycle-detail",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "captura el detalle por ciclo (fricción/reference_mid + motivo de cierre) que consume "
            "el diagnóstico de la pérdida (v2_96); INERTE por defecto (Δ motor = 0). Con --reuse, "
            "un sorteo cuyo ledger sea v1 (sin detalle) se re-corre para no mezclar esquemas"
        ),
    )
    parser.add_argument(
        "--entry-window-days",
        type=int,
        default=_DEFAULT_ENTRY_WINDOW_DAYS,
        help="barras D1 de la ventana de excursión adversa TEMPRANA post-entrada",
    )
    parser.add_argument(
        "--check-against", default=None, help="artefacto multirregimen sellado para cruzar el sorteo 0"
    )
    parser.add_argument(
        "--reuse", action="store_true", help="reutiliza los sorteos ya presentes en --out-dir"
    )
    parser.add_argument(
        "--out-dir",
        default=str(_DRAWS_SUBDIR),
        help="carpeta de los K sorteos (gitignored)",
    )
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de la banda")
    args = parser.parse_args(argv)

    if int(args.draws) < 1:
        print("# uso incorrecto: --draws debe ser >= 1", file=sys.stderr)
        return 1
    if int(args.entry_window_days) < 1:
        print("# uso incorrecto: --entry-window-days debe ser >= 1", file=sys.stderr)
        return 1
    if int(args.watch_size) <= 0 or int(args.min_bars) <= 0:
        print("# uso incorrecto: --watch-size y --min-bars deben ser > 0", file=sys.stderr)
        return 1
    if args.years is None and (args.from_year is None or args.to_year is None):
        print("# uso incorrecto: indica --years o --from-year/--to-year", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    from bolsa_application.dia_d_multi_uncertainty import (
        DEFAULT_LIMITS,
        build_band_artifact,
    )

    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir
    mutations = _load_mutations()

    try:
        draws = [_draw(args, k=k, out_dir=out_dir, mutations=mutations) for k in range(int(args.draws))]
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay evidencia: se DECLARA.
        print(f"# BLOQUEADO: no se pudo construir la banda ({type(error).__name__}: {error})", file=sys.stderr)
        return 2

    years_requested = (draws[0].get("coverage") or {}).get("yearsRequested") or []
    limits = list(DEFAULT_LIMITS)
    v92 = _load_v92()
    reference = v92._load_cross_check(args.check_against)  # noqa: SLF001 — MISMA tolerancia.
    cross_check = v92._cross_check_summary(reference, current=draws[0].get("summary") or {})  # noqa: SLF001

    artifact = build_band_artifact(
        draws=draws,
        seed_shift={
            "env": AUTO_REAL_PRICE_NOTE,
            "k0": "produccion (sin parchear)",
            "kGreaterThanZero": "fill_seed(bar_tick_now + k, symbol)",
            "source": f"{_WORKER_REL}:seed",
            "K": int(args.draws),
        },
        cross_check=cross_check,
        meta={
                "bump": "2.11.96-beta",
            "phase": "V2.94 DIA-D AUTO MULTI BAND",
            "nature": "INVESTIGACION",
            "account": str(args.account_id),
            "versionA": str(args.version_a),
            "venue": str(args.venue),
            "historyDays": int(args.history_days),
            "horizonDays": int(args.horizon_days),
            "topK": int(args.attribution_top_k),
            "universe": str(args.universe),
            "realPriceForcedOff": True,
        },
        limits=limits,
    )

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    first_year = str(years_requested[0]) if years_requested else "band"
    last_year = str(years_requested[-1]) if years_requested else "band"
    default_name = f"multi-band-{first_year}_{last_year}.json"
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_text(artifact)
        print()
        print(f"banda                     {out_path}")
        print(f"sorteos                   {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
