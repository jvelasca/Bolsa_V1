"""V2.91 · DÍA-D AUTO — ventana LONGITUDINAL OOS sobre el universo point-in-time.

Qué es
------
Corre el MISMO harness hermético (``v2.86``/``v2.87``) **una sola vez** sobre una **ventana
contigua y acotada** (por defecto el año natural 2022) usando el **universo point-in-time**
(``--universe pit``), y agrega el OOS por día ``D`` para medir la **estabilidad** del edge:
expectativa, acierto, series por cubo temporal y excursiones MAE/MFE por ciclo. El resultado es
un artefacto JSON determinista.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO sustituye la ventana PAPER.** El cubo de calendario sale del reloj de pared, así que un
  replay no fabrica cubos durables. ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO escribe en PostgreSQL**: el motor corre con stores en memoria (cuarentena). Las únicas
  lecturas son barras, sectores y el universo.
* **MAE/MFE son extremos ENTRE DÍAS** (barras D1); el día de entrada puede incluir excursión
  previa al fill. No se presentan como intradía.
* Un hueco se declara ``None``/``NOT_MEASURED``; nunca se rellena con ``0``.

Sonda de viabilidad (``probe``)
-------------------------------
La corrida larga puede truncar (libro de compromisos pendientes): el artefacto publica la ventana
**pedida** vs la **efectiva** y el ``truncationReason``. Si trunca y ``--fallback`` está activo,
se reintenta una vez sobre el **tramo contiguo más largo operable** dentro de la ventana y se
declara ``windowFallback`` (nunca se inventa la muestra).

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_91_dia_d_longitudinal.py \
        --year 2022 --universe pit --json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

#: Cuenta y versión de la ventana PAPER (MISMOS valores que ``v2.86``/``v2.87``/``v2.89``).
_DEFAULT_ACCOUNT = "1484e253d2d54645945a6b1d7"
_DEFAULT_VERSION_A = "v283-window-a"
_DEFAULT_EDGE = 0.9

#: Días de historia previos a ``D0`` que se simulan para calentar régimen/ATR y contexto.
_DEFAULT_HISTORY_DAYS = 90
#: Días posteriores a ``D1`` que se simulan para medir el OOS real del ciclo abierto en ``D1``.
_DEFAULT_HORIZON_DAYS = 20

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"

logger = logging.getLogger("v2_91_dia_d_longitudinal")


def _load_module(filename: str, name: str) -> Any:
    """Carga un runner hermano por ruta (mismo patrón que ``v2.89``→``v2.87``→``v2.86``)."""
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_v89() -> Any:
    return _load_module("v2_89_dia_d_auto_replay.py", "v2_89_dia_d_auto_replay")


# ── Resolución de la ventana ─────────────────────────────────────────────────────


def _resolve_window(args: argparse.Namespace, days: list[str]) -> tuple[int, int]:
    """Índices ``[d0, d1]`` (inclusivos) de la ventana pedida dentro del calendario de barras.

    Acepta ``--year YYYY`` (año natural completo) o ``--from/--to``. Se toman la primera y la
    última barra DENTRO del rango pedido: una ventana fuera del calendario se declara, no se
    recorta en silencio a un día arbitrario.
    """
    if args.year is not None:
        year = int(args.year)
        window_from, window_to = f"{year}-01-01", f"{year}-12-31"
    else:
        window_from, window_to = str(args.from_day or ""), str(args.to_day or "")
    if not window_from or not window_to:
        raise RuntimeError("indica --year o --from/--to")
    if window_from > window_to:
        raise RuntimeError(f"la ventana está invertida: {window_from} > {window_to}")

    inside = [index for index, day in enumerate(days) if window_from <= day <= window_to]
    if not inside:
        raise RuntimeError(
            f"la ventana {window_from}..{window_to} no tiene barras en el calendario "
            f"({days[0]}..{days[-1]})"
        )
    return inside[0], inside[-1]


def _prune_bars_to_eligibility(
    bars_by_symbol: dict[str, list[Any]],
    *,
    window_from: str,
    window_to: str,
    provider: Any,
    days: list[str],
) -> tuple[dict[str, list[Any]], int]:
    """Poda las barras IN-WINDOW de cada símbolo a sus días point-in-time elegibles.

    Devuelve ``(bars_by_symbol, días_medidos)``. Cinturón y tirantes del watch por día: un
    símbolo del watch no debe operar con una barra de un día en que NO era elegible. Las barras
    FUERA de la ventana (historia/horizonte) se conservan intactas. Un símbolo cuya
    elegibilidad no se pudo medir no se poda (no se inventa una ventana).
    """
    from bolsa_application.closed_bars import bar_day
    from bolsa_application.universe_point_in_time import eligible_days_by_symbol

    if not window_from or not window_to or window_from > window_to:
        return bars_by_symbol, 0
    window_days = [day for day in days if window_from <= day <= window_to]
    if not window_days:
        return bars_by_symbol, 0
    allowed_by_symbol = eligible_days_by_symbol(provider, window_days)
    pruned: dict[str, list[Any]] = {}
    for symbol, bars in bars_by_symbol.items():
        allowed = allowed_by_symbol.get(str(symbol))
        if allowed is None:
            pruned[str(symbol)] = list(bars)
            continue
        pruned[str(symbol)] = [
            bar
            for bar in bars
            if not (window_from <= bar_day(bar) <= window_to) or bar_day(bar) in allowed
        ]
    return pruned, len(window_days)


async def _run_pass(
    *,
    v87: Any,
    args: argparse.Namespace,
    watch: list[str],
    bars_by_symbol: dict[str, list[Any]],
    sectors: dict[str, str],
    days: list[str],
    operable_flags: list[bool],
    history_days: int,
    horizon_days: int,
    d0_index: int,
    d1_index: int,
    capture_cycle_detail: bool = False,
) -> dict[str, Any]:
    """Una corrida del harness hermético sobre ``[d0_index, d1_index]`` (con historia/horizonte).

    ``capture_cycle_detail`` (default ``False``) se propaga al harness para el diagnóstico de la
    pérdida; con él apagado el comportamiento es idéntico (costura inerte).
    """
    start_index = max(1, d0_index - max(1, history_days))
    end_index = min(len(days), d1_index + 1 + max(0, horizon_days))
    result: dict[str, Any] = await v87._run_durable_replay(  # noqa: SLF001 — harness hermético compartido.
        watch=watch,
        bars_by_symbol=bars_by_symbol,
        sectors=sectors,
        days=days,
        start_index=start_index,
        max_ticks=end_index - start_index,
        edge=float(args.edge),
        account_id=str(args.account_id),
        version_a=str(args.version_a),
        engine_id=f"dia-d-longitudinal-{os.urandom(3).hex()}",
        operable_days=operable_flags,
        durable_cycle=True,
        capture_cycle_detail=bool(capture_cycle_detail),
    )
    return result


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.dia_d_longitudinal import (
        DEFAULT_LIMITS,
        build_dia_d_longitudinal_artifact,
        excursions,
    )
    from bolsa_application.replay_oos import census_operable_days
    from bolsa_application.universe_point_in_time import candidate_ids
    from bolsa_application.universe_point_in_time_catalog import CatalogPointInTimeUniverse
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    v89 = _load_v89()
    v86 = v89._load_v86()  # noqa: SLF001 — MISMO harness.
    v87 = v89._load_v87()  # noqa: SLF001

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    try:
        explicit_watch = [s.strip() for s in (args.watch or "").split(",") if s.strip()]
        universe_coverage: dict[str, Any] | None = None
        provider: Any = None
        pit_from, pit_to = "", ""
        watch = explicit_watch
        if not watch and str(args.universe) == "pit":
            # D35-01: fuente point-in-time REAL (disponibilidad desde barras) + aproximaciones
            # DECLARADAS. Fail-closed: sin miembros NO se cae al catálogo actual.
            provider = await CatalogPointInTimeUniverse.load(
                factory,
                min_bars=int(args.min_bars),
                historical=bool(args.pit_historical),
            )
            universe_coverage = provider.coverage()
            if args.year is not None:
                pit_from, pit_to = f"{int(args.year)}-01-01", f"{int(args.year)}-12-31"
            else:
                pit_from, pit_to = str(args.from_day or ""), str(args.to_day or "")
            # Universo de la VENTANA (candidatos con algún día elegible), no de un solo día:
            # anclar al cierre excluía a los deslistados a mitad de ventana (D34-05/D35-01).
            watch = candidate_ids(provider.all_members, pit_from, pit_to)[
                : max(1, int(args.watch_size))
            ]
            if not watch:
                raise RuntimeError(
                    "el universo point-in-time no aportó ningún instrumento elegible en la ventana"
                )
        if not watch:
            v76 = v86._load_v76_module()  # noqa: SLF001 — MISMA derivación del watch.
            watch = await v76._watch_from_catalog(  # noqa: SLF001
                factory, int(args.watch_size), min_bars=int(args.min_bars)
            )
        if not watch:
            raise RuntimeError("el catálogo no aportó ningún instrumento con sector e historia")
        watch_source = (
            "explicit"
            if explicit_watch
            else ("pit" if universe_coverage is not None else "catalog")
        )

        v86._configure_env(watch=watch, venue=str(args.venue), edge=float(args.edge))  # noqa: SLF001
        # Determinismo: el precio del replay es el ``price_script`` histórico inyectado.
        os.environ["AUTO_ENGINE_SIM_REAL_PRICE"] = "0"

        bars_by_symbol = await v86._read_bars(factory, watch)  # noqa: SLF001
        days = v86._trading_days(bars_by_symbol)  # noqa: SLF001
        if not days:
            raise RuntimeError("no hay barras D1 para simular")
        if provider is not None:
            # Watch por DÍA (PIT): poda in-window cada símbolo a sus días elegibles; las barras
            # fuera de la ventana (historia/horizonte) quedan intactas.
            bars_by_symbol, _eligible_days = _prune_bars_to_eligibility(
                bars_by_symbol,
                window_from=pit_from,
                window_to=pit_to,
                provider=provider,
                days=days,
            )

        d0_index, d1_index = _resolve_window(args, days)
        census = census_operable_days(bars_by_symbol, days)
        operable_flags = [row.entries_allowed_long for row in census.days]
        operable_days = sum(1 for flag in operable_flags[d0_index : d1_index + 1] if flag)
        regime_counts: dict[str, int] = {}
        for row in census.days[d0_index : d1_index + 1]:
            key = str(row.aggregate or "sin_regimen")
            regime_counts[key] = regime_counts.get(key, 0) + 1
        sectors = await v86._load_sectors(factory, watch)  # noqa: SLF001

        replay = await _run_pass(
            v87=v87,
            args=args,
            watch=watch,
            bars_by_symbol=bars_by_symbol,
            sectors=sectors,
            days=days,
            operable_flags=operable_flags,
            history_days=int(args.history_days),
            horizon_days=int(args.horizon_days),
            d0_index=d0_index,
            d1_index=d1_index,
        )
        horizon = replay.get("horizon") or {}
        fallback: dict[str, Any] | None = None
        if horizon.get("truncationReason") and bool(args.fallback):
            from bolsa_application.dia_d_longitudinal import longest_operable_run

            run = longest_operable_run(operable_flags, start_index=d0_index, end_index=d1_index)
            if run is not None and run != (d0_index, d1_index):
                logger.warning(
                    "la corrida truncó (%s); reintento sobre el tramo operable %s..%s",
                    horizon.get("truncationReason"),
                    days[run[0]],
                    days[run[1]],
                )
                effective = await _run_pass(
                    v87=v87,
                    args=args,
                    watch=watch,
                    bars_by_symbol=bars_by_symbol,
                    sectors=sectors,
                    days=days,
                    operable_flags=operable_flags,
                    history_days=int(args.history_days),
                    horizon_days=int(args.horizon_days),
                    d0_index=run[0],
                    d1_index=run[1],
                )
                fallback = {
                    "reason": str(horizon.get("truncationReason")),
                    "requestedFrom": days[d0_index],
                    "requestedTo": days[d1_index],
                    "effectiveFrom": days[run[0]],
                    "effectiveTo": days[run[1]],
                }
                d0_index, d1_index = run
                replay = effective
                horizon = replay.get("horizon") or {}

        score = replay.get("score") or {}
        window_from, window_to = days[d0_index], days[d1_index]
        day_rows = {row.get("day") for row in replay.get("perDay", [])}
        window_days = [day for day in days[d0_index : d1_index + 1] if day in day_rows]
        if not window_days:
            raise RuntimeError("el replay no alcanzó ningún día de la ventana pedida")
        window_set = set(window_days)
        round_trips = [
            row
            for row in score.get("roundTrips", [])
            if str(row.get("entryDay") or "") in window_set
        ]
        open_positions = [
            row
            for row in score.get("openPositions", [])
            if str(row.get("entryDay") or "") in window_set
        ]
        unmeasured = [
            gap for gap in score.get("unmeasured", []) if str(gap).split(":", 1)[0] in window_set
        ]
        excursion_rows = excursions(bars_by_symbol=bars_by_symbol, round_trips=round_trips)

        probe = {
            "requestedFrom": window_from if fallback is None else fallback["requestedFrom"],
            "requestedTo": window_to if fallback is None else fallback["requestedTo"],
            "effectiveFrom": replay.get("startDay") or window_from,
            "effectiveTo": replay.get("endDay") or window_to,
            "daysDetected": len(window_days),
            "operableDays": operable_days,
            "cyclesMeasured": len(round_trips),
            "truncationReason": horizon.get("truncationReason"),
            "horizon": horizon,
        }

        limits = list(DEFAULT_LIMITS)
        if watch_source == "pit":
            limits.append(
                "Universe(D) point-in-time POR DIA en la ventana: el watch es el superconjunto "
                "de candidatos con algun dia elegible (candidate_ids) y las barras IN-WINDOW se "
                "podan a los dias elegibles (ids_by_day); availability_from/until son REALES "
                "(barras D1); active_from/active_until y sector_at son aproximaciones DECLARADAS. "
                "Ver meta.universeCoverage."
            )
        if fallback is not None:
            limits.append(
                "La corrida larga truncó; la ventana efectiva es el tramo operable declarado en probe/windowFallback."
            )

        artifact = build_dia_d_longitudinal_artifact(
            window_from=fallback["requestedFrom"] if fallback else window_from,
            window_to=fallback["requestedTo"] if fallback else window_to,
            days=window_days,
            operable_days=operable_days,
            round_trips=round_trips,
            open_positions=open_positions,
            unmeasured=unmeasured,
            excursions_rows=excursion_rows,
            regime_counts=regime_counts,
            watch=watch,
            watch_source=watch_source,
            universe_coverage=universe_coverage,
            probe={**probe, "windowFallback": fallback},
            meta={
                "bump": "2.11.55-beta",
                "phase": "V2.91 DIA-D AUTO LONGITUDINAL",
                "nature": "INVESTIGACION",
                "account": str(args.account_id),
                "versionA": str(args.version_a),
                "venue": str(args.venue),
                "historyDays": int(args.history_days),
                "horizonDays": int(args.horizon_days),
                "replayStart": replay.get("startDay"),
                "replayEnd": replay.get("endDay"),
                "replayTicks": replay.get("ticks"),
                "bucketPeriod": str(args.bucket),
                "pitAnchoring": "per_day" if provider is not None else "not_applicable",
                "realPriceForcedOff": True,
            },
            bucket_period=str(args.bucket),
            limits=limits,
        )
        artifact["window"]["effectiveFrom"] = replay.get("startDay") or window_from
        artifact["window"]["effectiveTo"] = replay.get("endDay") or window_to
        return artifact
    finally:
        await engine.dispose()


def _fmt(value: Any, spec: str = "+.3f") -> str:
    """Formatea un número o ``n/d`` si es un hueco declarado (nunca un ``0`` inventado)."""
    return "n/d" if value is None else format(float(value), spec)


def _print_text(artifact: dict[str, Any]) -> None:
    window = artifact["window"]
    summary = artifact["summary"]
    print(f"DÍA-D AUTO · LONGITUDINAL OOS · {window['from']}..{window['to']}")
    print("=" * 72)
    print(f"veredicto                 {summary['verdict']} ({summary['verdictReason']})")
    print(f"calidad de evidencia      {summary['evidenceQuality']}")
    print(
        f"expectativa               {_fmt(summary['expectancyR'], '+.4f')} R/ciclo · "
        f"hit {_fmt(summary['hitRate'], '.2f')} · ciclos {summary['measuredCycles']}"
    )
    stability = artifact["stability"]
    print(
        f"estabilidad ({stability['bucketPeriod']})   cubos={stability['measuredBuckets']} "
        f"+{stability['positiveBuckets']} −{stability['negativeBuckets']} · "
        f"min {_fmt(stability['minExpectancyR'])} · max {_fmt(stability['maxExpectancyR'])}"
    )
    excursion = artifact["excursions"]
    print(
        f"MAE/MFE                   medidos={excursion['measured']} n/d={excursion['unmeasured']} · "
        f"MAE medio {_fmt(excursion['meanMaeR'])} · MFE medio {_fmt(excursion['meanMfeR'])}"
    )
    if artifact.get("limits"):
        print()
        print("LÍMITES DECLARADOS")
        for item in artifact["limits"]:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=None, help="año natural completo (p. ej. 2022)")
    parser.add_argument("--from", dest="from_day", default=None, help="primer día D0 (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_day", default=None, help="último día D1 (YYYY-MM-DD)")
    parser.add_argument(
        "--watch", default=None, help="instrumentos separados por coma (si falta, universo)"
    )
    parser.add_argument(
        "--universe",
        default="pit",
        choices=("catalog", "pit"),
        help="fuente del watch si no hay --watch: 'pit' (Universe(D), por defecto) o 'catalog'",
    )
    parser.add_argument("--watch-size", type=int, default=20, help="tamaño del watch derivado")
    parser.add_argument(
        "--min-bars", type=int, default=60, help="barras D1 mínimas en el watch derivado"
    )
    parser.add_argument(
        "--pit-historical",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "modo histórico del proveedor PIT: usa la disponibilidad REAL de barras como suelo "
            "de elegibilidad (necesario para ventanas anteriores al alta en catálogo, p. ej. 2022)"
        ),
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=_DEFAULT_HISTORY_DAYS,
        help="días previos a D0 simulados",
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=_DEFAULT_HORIZON_DAYS,
        help="días posteriores a D1 simulados",
    )
    parser.add_argument(
        "--edge", type=float, default=_DEFAULT_EDGE, help="valor declarado del seam de edge"
    )
    parser.add_argument(
        "--account-id", default=_DEFAULT_ACCOUNT, help="cuenta de la ventana (etiqueta)"
    )
    parser.add_argument("--version-a", default=_DEFAULT_VERSION_A, help="versión A de la ventana")
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument(
        "--bucket",
        default="month",
        choices=("year", "quarter", "month"),
        help="cubo de estabilidad",
    )
    parser.add_argument(
        "--fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="si la corrida trunca, reintenta una vez sobre el tramo operable más largo",
    )
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args(argv)

    if int(args.watch_size) <= 0 or int(args.min_bars) <= 0:
        print("# uso incorrecto: --watch-size y --min-bars deben ser > 0", file=sys.stderr)
        return 1
    if int(args.history_days) < 1 or int(args.horizon_days) < 0:
        print("# uso incorrecto: --history-days >= 1 y --horizon-days >= 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        artifact = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo construir el estudio longitudinal ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    window = artifact["window"]
    default_name = f"longitudinal-{window['from']}_{window['to']}.json"
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_text(artifact)
        print()
        print(f"artefacto                 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
