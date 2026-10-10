"""V2.93 · DÍA-D AUTO — ATRIBUCIÓN MULTIRREGIMEN por año (read-only, sin tocar motor).

Qué es
------
Corre el MISMO harness hermético (``v2.86``/``v2.87`` vía ``v2_91``) **una vez por año** sobre
una ventana acotada (por defecto 2021-2026) con el **universo point-in-time derivado POR DÍA**
dentro de cada año (superconjunto de candidatos + poda in-window de barras a los días
elegibles),
y pliega la atribución por:

* **año** (``byYear``), **régimen** (``byRegime``/``byOperationalRegime``) y **celda año ×
  régimen** (``byYearByRegime``);
* **resultado** — cada cubo con la severidad de MAE por POBLACIÓN (ALL/WINNERS/LOSERS);
* **excursión** — cada cubo con la captura de MFE (``capture_study``) y las reversiones.

Responde *dónde* y *cómo* se pierde (o gana) el R a lo largo de varios regímenes, no sólo en un
año. El artefacto es JSON determinista y **advisory**: no cambia el motor, los umbrales,
``TOP_N`` ni la allocation, y **no** escribe en PostgreSQL.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO** sustituye la ventana PAPER: ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO** es causal: la atribución es **descriptiva** sobre la muestra medida.
* Un año sin universo PIT elegible o sin barras se declara en ``coverage.yearsNotMeasured``.
* Un hueco se declara ``None``/``NOT_MEASURED``; nunca se rellena con ``0``.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_93_dia_d_multi.py \\
        --from-year 2021 --to-year 2026 --universe pit --json
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

#: Cuenta y versión de la ventana PAPER (MISMOS valores que ``v2_86``/``v2_87``/``v2_91``/``v2_92``).
_DEFAULT_ACCOUNT = "1484e253d2d54645945a6b1d7"
_DEFAULT_VERSION_A = "v283-window-a"
_DEFAULT_EDGE = 0.9

#: Días de historia previos a ``D0`` que se simulan para calentar régimen/ATR y contexto.
_DEFAULT_HISTORY_DAYS = 90
#: Días posteriores a ``D1`` que se simulan para medir el OOS real del ciclo abierto en ``D1``.
_DEFAULT_HORIZON_DAYS = 20

#: Barras D1 de la ventana de excursión adversa TEMPRANA post-entrada (diagnóstico de la pérdida).
#: MISMO valor que ``dia_d_longitudinal.DEFAULT_ENTRY_WINDOW_DAYS`` (lo fija el guardián).
_DEFAULT_ENTRY_WINDOW_DAYS = 3

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"

logger = logging.getLogger("v2_93_dia_d_multi")


def _load_module(filename: str, name: str) -> Any:
    """Carga un runner hermano por ruta (mismo patrón que ``v2.89``→``v2.90``→``v2.91``)."""
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_v91() -> Any:
    return _load_module("v2_91_dia_d_longitudinal.py", "v2_91_dia_d_longitudinal")


def _load_v92() -> Any:
    return _load_module("v2_92_dia_d_attribution.py", "v2_92_dia_d_attribution")


# ── Resolución de años y ventana ─────────────────────────────────────────────────


def _resolve_years(args: argparse.Namespace) -> list[int]:
    """Años pedidos: ``--years 2021,2022`` o el rango ``--from-year/--to-year`` (ordenados)."""
    if args.years:
        raw = [chunk.strip() for chunk in str(args.years).split(",") if chunk.strip()]
        years = sorted({int(chunk) for chunk in raw})
    elif args.from_year is not None and args.to_year is not None:
        if int(args.from_year) > int(args.to_year):
            raise RuntimeError(f"rango invertido: {args.from_year} > {args.to_year}")
        years = list(range(int(args.from_year), int(args.to_year) + 1))
    else:
        raise RuntimeError("indica --years o --from-year/--to-year")
    if not years:
        raise RuntimeError("no se pidió ningún año")
    return years


def _resolve_year_window(year: int, days: list[str]) -> tuple[int, int] | None:
    """Índices ``[d0, d1]`` (inclusivos) del año natural dentro del calendario de barras.

    Un año sin barras en el calendario se declara (``None``), no se recorta en silencio.
    """
    window_from, window_to = f"{int(year)}-01-01", f"{int(year)}-12-31"
    inside = [index for index, day in enumerate(days) if window_from <= day <= window_to]
    return (inside[0], inside[-1]) if inside else None


def _year_watch(
    *,
    year: int,
    args: argparse.Namespace,
    provider: Any,
    explicit_watch: list[str],
    catalog_watch: list[str] | None,
) -> tuple[str, list[str], dict[str, Any] | None]:
    """Watch del año y su procedencia declarada (``explicit``/``pit``/``catalog``).

    Con ``pit`` el watch es el SUPERCONJUNTO de candidatos con algún día elegible dentro del
    año (``candidate_ids``), NO el universo del ÚLTIMO día: anclar al cierre excluía a los
    instrumentos deslistados a mitad de año (el sesgo D34-05/D35-01 a granularidad anual). El
    filtro por día concreto lo aplica después la poda de barras (``ids_by_day``).
    """
    if explicit_watch:
        return "explicit", explicit_watch, None
    if provider is not None:
        from bolsa_application.universe_point_in_time import candidate_ids

        candidates = candidate_ids(
            provider.all_members, f"{int(year)}-01-01", f"{int(year)}-12-31"
        )
        watch = candidates[: max(1, int(args.watch_size))]
        return "pit", watch, provider.coverage()
    return "catalog", list(catalog_watch or []), None


def _prune_bars_to_eligibility(
    bars_by_symbol: dict[str, list[Any]],
    *,
    year: int,
    provider: Any,
    days: list[str],
) -> tuple[dict[str, list[Any]], int]:
    """Poda las barras IN-WINDOW de cada símbolo a sus días point-in-time elegibles.

    Devuelve ``(bars_by_symbol, días_medidos)``. Cinturón y tirantes del watch por día: un
    símbolo incluido en el watch del año no debe operar con una barra de un día del año en que
    NO era elegible. Las barras FUERA del año (historia/horizonte) se conservan intactas: la
    ventana de elegibilidad sólo se aplica DENTRO del año evaluado. Un símbolo cuya
    elegibilidad no se pudo medir no se poda (no se inventa una ventana).
    """
    from bolsa_application.closed_bars import bar_day
    from bolsa_application.universe_point_in_time import eligible_days_by_symbol

    year_from, year_to = f"{int(year)}-01-01", f"{int(year)}-12-31"
    window_days = [day for day in days if year_from <= day <= year_to]
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
            if not (year_from <= bar_day(bar) <= year_to) or bar_day(bar) in allowed
        ]
    return pruned, len(window_days)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.dia_d_longitudinal import (
        early_excursion_for_cycle,
        excursions,
        longest_operable_run,
    )
    from bolsa_application.dia_d_multi import (
        DEFAULT_LIMITS,
        build_dia_d_multi_artifact,
    )
    from bolsa_application.dia_d_multi_sampling import build_cycle_ledger
    from bolsa_application.replay_oos import census_operable_days
    from bolsa_application.universe_point_in_time_catalog import CatalogPointInTimeUniverse
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    v91 = _load_v91()
    v89 = v91._load_v89()  # noqa: SLF001 — MISMO harness.
    v86 = v89._load_v86()  # noqa: SLF001
    v87 = v89._load_v87()  # noqa: SLF001

    years = _resolve_years(args)
    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    try:
        explicit_watch = [s.strip() for s in (args.watch or "").split(",") if s.strip()]
        provider: Any = None
        catalog_watch: list[str] | None = None
        if not explicit_watch:
            if str(args.universe) == "pit":
                provider = await CatalogPointInTimeUniverse.load(
                    factory,
                    min_bars=int(args.min_bars),
                    historical=True,
                )
            else:
                v76 = v86._load_v76_module()  # noqa: SLF001 — MISMA derivación del watch.
                catalog_watch = await v76._watch_from_catalog(  # noqa: SLF001
                    factory, int(args.watch_size), min_bars=int(args.min_bars)
                )
                if not catalog_watch:
                    raise RuntimeError("el catálogo no aportó ningún instrumento con sector e historia")

        # Determinismo: el precio del replay es el ``price_script`` histórico inyectado.
        os.environ["AUTO_ENGINE_SIM_REAL_PRICE"] = "0"

        windows: list[dict[str, Any]] = []
        all_trips: list[dict[str, Any]] = []
        all_excursions: list[Any] = []
        all_entry_excursions: list[Any] = []
        all_cost_rows: list[Any] = []
        all_close_rows: list[Any] = []
        # Capa v4: geometría de la invalidación por ciclo (una entrada por ``cycle_id``, acumulada
        # entre ventanas). Sin ``--cycle-detail`` queda vacía y el ledger declara el hueco.
        all_invalidation_by_cycle: dict[str, Any] = {}
        # Capa v5: secuencia día a día por ciclo (mark/stop/MAE persistido), acumulada entre
        # ventanas. Es la materia prima de la desambiguación THESIS_EXIT vs STOP.
        all_cycle_sequences_by_cycle: dict[str, Any] = {}
        # Capa v6 (DÍA-D-3g): eventos de gestión (``auto_position_management``) unidos a su
        # ``cycle_id`` (join por instrumento+día hecho en la costura). Acumulados entre ventanas.
        all_management_by_cycle: dict[str, list[dict[str, Any]]] = {}
        regime_all: dict[str, Any] = {}
        operational_all: dict[str, Any] = {}

        for year in years:
            year_label = str(year)
            watch_source, watch, universe_coverage = _year_watch(
                year=year,
                args=args,
                provider=provider,
                explicit_watch=explicit_watch,
                catalog_watch=catalog_watch,
            )
            if not watch:
                windows.append({"year": year_label, "measured": False, "reason": "sin_universo_pit"})
                continue
            v86._configure_env(watch=watch, venue=str(args.venue), edge=float(args.edge))  # noqa: SLF001
            bars_by_symbol = await v86._read_bars(factory, watch)  # noqa: SLF001
            days = v86._trading_days(bars_by_symbol)  # noqa: SLF001
            if not days:
                windows.append({"year": year_label, "measured": False, "reason": "sin_barras"})
                continue
            # Watch por DÍA (PIT): el universo del año es el superconjunto de candidatos; aquí
            # se poda in-window cada símbolo a los días del año en que SÍ era elegible. Las
            # barras fuera del año (historia/horizonte) quedan intactas.
            eligible_days = 0
            if provider is not None:
                bars_by_symbol, eligible_days = _prune_bars_to_eligibility(
                    bars_by_symbol, year=int(year), provider=provider, days=days
                )
            window = _resolve_year_window(int(year), days)
            if window is None:
                windows.append(
                    {"year": year_label, "measured": False, "reason": "ventana_sin_barras"}
                )
                continue
            d0_index, d1_index = window
            census = census_operable_days(bars_by_symbol, days)
            operable_flags = [row.entries_allowed_long for row in census.days]
            sectors = await v86._load_sectors(factory, watch)  # noqa: SLF001

            replay = await v91._run_pass(  # noqa: SLF001 — harness hermético compartido.
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
                capture_cycle_detail=bool(args.cycle_detail),
            )
            horizon = replay.get("horizon") or {}
            fallback: dict[str, Any] | None = None
            if horizon.get("truncationReason") and bool(args.fallback):
                run = longest_operable_run(operable_flags, start_index=d0_index, end_index=d1_index)
                if run is not None and run != (d0_index, d1_index):
                    logger.warning(
                        "la corrida de %s truncó (%s); reintento sobre el tramo operable %s..%s",
                        year_label,
                        horizon.get("truncationReason"),
                        days[run[0]],
                        days[run[1]],
                    )
                    effective = await v91._run_pass(  # noqa: SLF001
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
                        capture_cycle_detail=bool(args.cycle_detail),
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
                windows.append({"year": year_label, "measured": False, "reason": "replay_sin_dias"})
                continue
            window_set = set(window_days)
            round_trips = [
                dict(row)
                for row in score.get("roundTrips", [])
                if str(row.get("entryDay") or "") in window_set
            ]
            excursion_rows = excursions(bars_by_symbol=bars_by_symbol, round_trips=round_trips)
            entry_excursion_rows = [
                early_excursion_for_cycle(
                    bars_by_symbol=bars_by_symbol,
                    round_trip=trip,
                    window_days=int(args.entry_window_days),
                )
                for trip in round_trips
            ]
            detail = replay.get("cycleDetail") or {}
            all_cost_rows.extend(detail.get("costRows") or [])
            all_close_rows.extend(detail.get("closeRows") or [])
            all_invalidation_by_cycle.update(detail.get("invalidationByCycle") or {})
            all_cycle_sequences_by_cycle.update(detail.get("cycleTimeline") or {})
            # Capa v6: agrupa los eventos de gestión por ``cycle_id`` (los del día de entrada
            # sin ciclo previo quedan fuera: hueco declarado, nunca un ciclo inventado).
            for management_row in detail.get("managementRows") or []:
                management_cycle = str(
                    (management_row or {}).get("cycleId") or ""
                ).strip()
                if not management_cycle:
                    continue
                all_management_by_cycle.setdefault(management_cycle, []).append(
                    dict(management_row)
                )
            operable_days = sum(1 for flag in operable_flags[d0_index : d1_index + 1] if flag)
            for row in census.days:
                if row.day in window_set:
                    regime_all[row.day] = row.aggregate
                    operational_all[row.day] = row.operational

            all_trips.extend(round_trips)
            all_excursions.extend(excursion_rows)
            all_entry_excursions.extend(entry_excursion_rows)
            windows.append(
                {
                    "year": year_label,
                    "measured": True,
                    "requestedFrom": fallback["requestedFrom"] if fallback else window_from,
                    "requestedTo": fallback["requestedTo"] if fallback else window_to,
                    "effectiveFrom": replay.get("startDay") or window_from,
                    "effectiveTo": replay.get("endDay") or window_to,
                    "days": window_days,
                    "operableDays": operable_days,
                    "cyclesMeasured": len(round_trips),
                    "truncationReason": horizon.get("truncationReason"),
                    "windowFallback": fallback,
                    "watchSource": watch_source,
                    "universeCoverage": universe_coverage,
                    "watch": watch,
                    # Días del año con elegibilidad PIT materializada (watch por día).
                    "pitEligibleDays": eligible_days,
                }
            )

        limits = list(DEFAULT_LIMITS)
        if provider is not None:
            limits.append(
                "Universe(D) point-in-time POR DIA dentro del ano: el watch es el superconjunto "
                "de candidatos con algun dia elegible (candidate_ids) y las barras IN-WINDOW se "
                "podan a los dias elegibles (ids_by_day); availability_from/until son REALES "
                "(barras D1); active_from/active_until y sector_at son aproximaciones DECLARADAS. "
                "Un ano sin miembros elegibles no cae al catalogo actual (fail-closed)."
            )
        if any(window.get("windowFallback") for window in windows):
            limits.append(
                "Al menos un ano truncó; su ventana efectiva es el tramo operable declarado en windows[].windowFallback."
            )

        artifact = build_dia_d_multi_artifact(
            years=years,
            windows=windows,
            round_trips=all_trips,
            excursions_rows=all_excursions,
            regime_by_day=regime_all,
            operational_regime_by_day=operational_all,
            meta={
                "bump": "2.11.104-beta",
                "phase": "V2.93 DIA-D AUTO MULTI ATTRIBUTION",
                "nature": "INVESTIGACION",
                "account": str(args.account_id),
                "versionA": str(args.version_a),
                "venue": str(args.venue),
                "historyDays": int(args.history_days),
                "horizonDays": int(args.horizon_days),
                "topK": int(args.attribution_top_k),
                "universe": str(args.universe),
                "pitAnchoring": "per_day" if provider is not None else "not_applicable",
                "realPriceForcedOff": True,
            },
            top_k=int(args.attribution_top_k),
            limits=limits,
        )
        v92 = _load_v92()
        reference = v92._load_cross_check(args.check_against)  # noqa: SLF001 — MISMA tolerancia.
        artifact["crossCheck"] = v92._cross_check_summary(  # noqa: SLF001
            reference, current=artifact["summary"]
        )
        if args.cycles_out:
            # Ledger de ciclos (muestra cruda del sorteo): lo consume el bootstrap de ``v2_95``.
            # No cambia la forma del artefacto ``dia-d-multi-v1``.
            ledger = build_cycle_ledger(
                round_trips=all_trips,
                excursions_rows=all_excursions,
                entry_excursions_rows=all_entry_excursions,
                regime_by_day=regime_all,
                operational_regime_by_day=operational_all,
                cost_rows=all_cost_rows,
                close_rows=all_close_rows,
                invalidation_by_cycle=all_invalidation_by_cycle,
                cycle_sequences_by_cycle=all_cycle_sequences_by_cycle,
                management_by_cycle=all_management_by_cycle,
                entry_window_days=int(args.entry_window_days),
            )
            ledger_path = pathlib.Path(args.cycles_out)
            if not ledger_path.is_absolute():
                ledger_path = _REPO_ROOT / ledger_path
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text(
                json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
                encoding="utf-8",
            )
        return artifact
    finally:
        await engine.dispose()


def _fmt(value: Any, spec: str = "+.3f") -> str:
    """Formatea un número o ``n/d`` si es un hueco declarado (nunca un ``0`` inventado)."""
    return "n/d" if value is None else format(float(value), spec)


def _breach(population: dict[str, Any]) -> str:
    """Texto de la brecha ``-1R`` de una población (share y conteo), o ``n/d`` sin muestra."""
    breach = (population.get("breaches") or {}).get("-1.00") or {}
    return f"{_fmt(breach.get('share'), '.2f')} ({breach.get('count')}/{population.get('cycles')})"


def _print_text(artifact: dict[str, Any]) -> None:
    coverage = artifact["coverage"]
    summary = artifact["summary"]
    print(f"DÍA-D AUTO · ATRIBUCIÓN MULTIRREGIMEN · años {coverage['yearsRequested']}")
    print("=" * 78)
    print(f"veredicto                 {summary['verdict']} ({summary['verdictReason']})")
    print(f"calidad de evidencia      {summary['evidenceQuality']}")
    print(
        f"expectativa               {_fmt(summary['expectancyR'], '+.4f')} R/ciclo · "
        f"hit {_fmt(summary['hitRate'], '.2f')} · ciclos {summary['measuredCycles']}"
    )
    not_measured = [row["year"] for row in coverage["yearsNotMeasured"]]
    print(f"cobertura                 medidos {coverage['yearsMeasured']} · no medidos {not_measured}")
    print()
    for key, title, dim in (
        ("byYear", "AÑO", "year"),
        ("byRegime", "RÉGIMEN", "regime"),
    ):
        print(f"{title:<10} ETIQUETA            CICLOS   R/CICLO     HIT   MAE MED   CAPTURA   -1R (perdedores)")
        print("-" * 78)
        for row in artifact[key]:
            populations = (row.get("maeSeverity") or {}).get("populations") or {}
            print(
                f"{'':<10} {str(row[dim]):<18} {row['cycles']:>6} "
                f"{_fmt(row['expectancyR'], '+.4f'):>8} {_fmt(row['hitRate'], '.2f'):>6} "
                f"{_fmt(row['meanMaeR']):>8} {_fmt(row['capture']['captureRatio']['mean'], '.2f'):>9} "
                f"{_breach(populations.get('LOSERS') or {})}"
            )
        print()
    print("AÑO × RÉGIMEN (celdas medidas)")
    print("-" * 78)
    for row in artifact["byYearByRegime"]:
        print(
            f"{row['year']:<6} {row['regime']:<18} {row['cycles']:>6} "
            f"{_fmt(row['expectancyR'], '+.4f'):>8} {_fmt(row['hitRate'], '.2f'):>6} "
            f"{_fmt(row['meanMaeR']):>8}"
        )
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
    parser.add_argument(
        "--watch", default=None, help="instrumentos separados por coma (si falta, universo)"
    )
    parser.add_argument(
        "--universe",
        default="pit",
        choices=("catalog", "pit"),
        help="fuente del watch si no hay --watch: 'pit' (Universe(D) por año, por defecto) o 'catalog'",
    )
    parser.add_argument("--watch-size", type=int, default=20, help="tamaño del watch derivado")
    parser.add_argument(
        "--min-bars", type=int, default=60, help="barras D1 mínimas en el watch derivado"
    )
    parser.add_argument(
        "--history-days", type=int, default=_DEFAULT_HISTORY_DAYS, help="días previos a D0 simulados"
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=_DEFAULT_HORIZON_DAYS,
        help="días posteriores a D1 simulados",
    )
    parser.add_argument("--edge", type=float, default=_DEFAULT_EDGE, help="valor declarado del seam de edge")
    parser.add_argument(
        "--attribution-top-k", type=int, default=5, help="mejores/peores ciclos de la concentración"
    )
    parser.add_argument(
        "--check-against", default=None, help="artefacto sellado para cruzar el resumen global"
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
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    parser.add_argument(
        "--cycles-out",
        default=None,
        help="ruta del ledger de ciclos (dia-d-multi-cycle-ledger-v2) que consumen v2_95/v2_96",
    )
    parser.add_argument(
        "--cycle-detail",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "captura el detalle por ciclo (fricción/reference_mid + motivo de cierre) que consume "
            "el diagnóstico de la pérdida (v2_96); INERTE por defecto (Δ motor = 0)"
        ),
    )
    parser.add_argument(
        "--entry-window-days",
        type=int,
        default=_DEFAULT_ENTRY_WINDOW_DAYS,
        help="barras D1 de la ventana de excursión adversa TEMPRANA post-entrada",
    )
    args = parser.parse_args(argv)

    if int(args.watch_size) <= 0 or int(args.min_bars) <= 0:
        print("# uso incorrecto: --watch-size y --min-bars deben ser > 0", file=sys.stderr)
        return 1
    if int(args.attribution_top_k) < 1:
        print("# uso incorrecto: --attribution-top-k debe ser >= 1", file=sys.stderr)
        return 1
    if int(args.history_days) < 1 or int(args.horizon_days) < 0:
        print("# uso incorrecto: --history-days >= 1 y --horizon-days >= 0", file=sys.stderr)
        return 1
    if int(args.entry_window_days) < 1:
        print("# uso incorrecto: --entry-window-days debe ser >= 1", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        artifact = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo construir la atribución multirregimen "
            f"({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    coverage = artifact["coverage"]
    years = coverage["yearsRequested"]
    default_name = f"multi-{years[0]}_{years[-1]}.json" if years else "multi.json"
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
