"""V2.92 · DÍA-D AUTO — ATRIBUCIÓN del OOS 2022 por dimensión (read-only, sin tocar motor).

Qué es
------
Corre el MISMO harness hermético (``v2.86``/``v2.87`` vía ``v2_91``) sobre una **ventana
contigua acotada** (por defecto el año natural 2022) con el **universo point-in-time**, y
**descompone** la expectativa OOS ya medida por ``v2_91``:

* por **régimen** (agregado trial por día de ``census_operable_days``),
* por **estrategia** (``strategyVersion`` del ciclo),
* por **sector** (el del catálogo actual; declarado aproximado),
* por **activo** (símbolo),
* y estudia la **excursión** (captura de MFE / severidad de MAE) y la **concentración**.

Responde *dónde* y *cómo* se pierde (o gana) el R de la ventana, no sólo *cuánto*. El artefacto
es JSON determinista y **advisory**: no cambia el motor, los umbrales, ``TOP_N`` ni la
allocation, y **no** escribe en PostgreSQL.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO** sustituye la ventana PAPER: ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO** es causal: la atribución es **descriptiva** sobre la muestra medida.
* **NO** ejecuta ventanas nuevas ni otros años (eso es multirregimen).
* Un hueco se declara ``None``/``NOT_MEASURED``; nunca se rellena con ``0``.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_92_dia_d_attribution.py \\
        --year 2022 --universe pit --json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import math
import os
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

#: Cuenta y versión de la ventana PAPER (MISMOS valores que ``v2_86``/``v2_87``/``v2_89``/``v2_91``).
_DEFAULT_ACCOUNT = "1484e253d2d54645945a6b1d7"
_DEFAULT_VERSION_A = "v283-window-a"
_DEFAULT_EDGE = 0.9

#: Días de historia previos a ``D0`` que se simulan para calentar régimen/ATR y contexto.
_DEFAULT_HISTORY_DAYS = 90
#: Días posteriores a ``D1`` que se simulan para medir el OOS real del ciclo abierto en ``D1``.
_DEFAULT_HORIZON_DAYS = 20

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"

logger = logging.getLogger("v2_92_dia_d_attribution")


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


def _load_cross_check(path: str | None) -> dict[str, Any] | None:
    """Referencia sellada de ``v2_91`` para cruzar el resumen (o ``None`` si no se pidió).

    Un fichero ausente o ilegible se declara, no se inventa: el artefacto publica el hueco.
    """
    if not path:
        return None
    target = pathlib.Path(path)
    if not target.is_absolute():
        target = _REPO_ROOT / target
    if not target.exists():
        return {"source": str(target), "available": False, "note": "referencia no encontrada"}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:  # noqa: BLE001 — un JSON roto es un hueco declarado.
        return {"source": str(target), "available": False, "note": f"referencia ilegible: {error}"}
    return {"source": str(target), "available": True, "reference": payload.get("summary") or {}}


#: Claves del cross-check que son floats: se comparan con tolerancia, no por igualdad exacta.
_FLOAT_DRIFT_KEYS = frozenset({"expectancyR", "hitRate"})
#: Tolerancia relativa/absoluta del cross-check de floats (una diferencia material es DRIFT).
_DRIFT_REL_TOL = 1e-12
_DRIFT_ABS_TOL = 1e-12


def _numbers_close(reference: Any, current: Any) -> bool:
    """Compara dos valores como floats con tolerancia; si no son numéricos, igualdad exacta.

    Un hueco (``None`` o texto) sólo coincide con su igual: si la referencia no es numérica NO se
    declara drift por una resta imposible. Evita que ``-0.5011`` y ``-0.5011000000000001`` marquen
    ``evidenceDrift`` sin diferencia material.
    """
    try:
        ref = float(reference)
        cur = float(current)
    except (TypeError, ValueError):
        return reference == current
    return math.isclose(ref, cur, rel_tol=_DRIFT_REL_TOL, abs_tol=_DRIFT_ABS_TOL)


def _summary_values_match(key: str, row: dict[str, Any]) -> bool:
    """¿Coincide una clave del resumen con su referencia sellada? (float tolerante, resto exacto)."""
    if key in _FLOAT_DRIFT_KEYS:
        return _numbers_close(row.get("reference"), row.get("current"))
    return row.get("reference") == row.get("current")


def _cross_check_summary(
    reference: dict[str, Any] | None,
    *,
    current: dict[str, Any],
) -> dict[str, Any]:
    """Cruza el resumen de ventana con la referencia sellada y declara ``evidenceDrift``."""
    if reference is None:
        return {"source": None, "note": "no se cruzó contra un artefacto longitudinal"}
    if not reference.get("available"):
        return {
            "source": reference.get("source"),
            "available": False,
            "note": reference.get("note") or "referencia no disponible",
        }
    expected = reference.get("reference") or {}
    keys = ("expectancyR", "hitRate", "measuredCycles", "verdict", "evidenceQuality")
    comparison = {
        key: {"reference": expected.get(key), "current": current.get(key)}
        for key in keys
    }
    drift = [key for key in keys if not _summary_values_match(key, comparison[key])]
    return {
        "source": reference.get("source"),
        "available": True,
        "comparison": comparison,
        "evidenceDrift": bool(drift),
        "driftedKeys": drift,
        "note": (
            "la BD local puede haber sincronizado barras después del sello: un drift se declara, "
            "no se corrige"
        ),
    }


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


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.dia_d_attribution import (
        DEFAULT_LIMITS,
        build_dia_d_attribution_artifact,
    )
    from bolsa_application.dia_d_longitudinal import excursions, longest_operable_run
    from bolsa_application.replay_oos import census_operable_days
    from bolsa_application.universe_point_in_time import candidate_ids
    from bolsa_application.universe_point_in_time_catalog import CatalogPointInTimeUniverse
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    v91 = _load_v91()
    v89 = v91._load_v89()  # noqa: SLF001 — MISMO harness.
    v86 = v89._load_v86()  # noqa: SLF001
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

        d0_index, d1_index = v91._resolve_window(args, days)  # noqa: SLF001
        census = census_operable_days(bars_by_symbol, days)
        operable_flags = [row.entries_allowed_long for row in census.days]
        operable_days = sum(1 for flag in operable_flags[d0_index : d1_index + 1] if flag)
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
        )
        horizon = replay.get("horizon") or {}
        fallback: dict[str, Any] | None = None
        if horizon.get("truncationReason") and bool(args.fallback):
            run = longest_operable_run(operable_flags, start_index=d0_index, end_index=d1_index)
            if run is not None and run != (d0_index, d1_index):
                logger.warning(
                    "la corrida truncó (%s); reintento sobre el tramo operable %s..%s",
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
            dict(row)
            for row in score.get("roundTrips", [])
            if str(row.get("entryDay") or "") in window_set
        ]
        excursion_rows = excursions(bars_by_symbol=bars_by_symbol, round_trips=round_trips)
        regime_by_day = {row.day: row.aggregate for row in census.days if row.day in window_set}
        operable_days = sum(1 for flag in operable_flags[d0_index : d1_index + 1] if flag)

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
            "windowFallback": fallback,
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

        artifact = build_dia_d_attribution_artifact(
            window_from=fallback["requestedFrom"] if fallback else window_from,
            window_to=fallback["requestedTo"] if fallback else window_to,
            days=window_days,
            operable_days=operable_days,
            round_trips=round_trips,
            excursions_rows=excursion_rows,
            regime_by_day=regime_by_day,
            sector_by_symbol=sectors,
            watch=watch,
            watch_source=watch_source,
            universe_coverage=universe_coverage,
            probe=probe,
            meta={
                "bump": "2.11.76-beta",
                "phase": "V2.92 DIA-D AUTO ATTRIBUTION",
                "nature": "INVESTIGACION",
                "account": str(args.account_id),
                "versionA": str(args.version_a),
                "venue": str(args.venue),
                "historyDays": int(args.history_days),
                "horizonDays": int(args.horizon_days),
                "topK": int(args.attribution_top_k),
                "pitHistorical": bool(args.pit_historical),
                "replayStart": replay.get("startDay"),
                "replayEnd": replay.get("endDay"),
                "replayTicks": replay.get("ticks"),
                "pitAnchoring": "per_day" if provider is not None else "not_applicable",
                "realPriceForcedOff": True,
            },
            top_k=int(args.attribution_top_k),
            limits=limits,
        )
        artifact["window"]["effectiveFrom"] = replay.get("startDay") or window_from
        artifact["window"]["effectiveTo"] = replay.get("endDay") or window_to
        reference = _load_cross_check(args.check_against)
        artifact["crossCheck"] = _cross_check_summary(reference, current=artifact["summary"])
        return artifact
    finally:
        await engine.dispose()


def _fmt(value: Any, spec: str = "+.3f") -> str:
    """Formatea un número o ``n/d`` si es un hueco declarado (nunca un ``0`` inventado)."""
    return "n/d" if value is None else format(float(value), spec)


def _print_text(artifact: dict[str, Any]) -> None:
    window = artifact["window"]
    summary = artifact["summary"]
    decomposition = artifact["decomposition"]
    print(f"DÍA-D AUTO · ATRIBUCIÓN OOS · {window['from']}..{window['to']}")
    print("=" * 72)
    print(f"veredicto                 {summary['verdict']} ({summary['verdictReason']})")
    print(f"calidad de evidencia      {summary['evidenceQuality']}")
    print(
        f"expectativa               {_fmt(summary['expectancyR'], '+.4f')} R/ciclo · "
        f"hit {_fmt(summary['hitRate'], '.2f')} · ciclos {summary['measuredCycles']}"
    )
    print(
        f"payoff                    win={_fmt(decomposition['avgWinR'])} "
        f"loss={_fmt(decomposition['avgLossR'])} ratio={_fmt(decomposition['payoffRatio'], '.2f')} "
        f"gap={_fmt(decomposition['identityGap'], '.2e')}"
    )
    concentration = artifact["concentration"]
    print(
        f"concentración             {concentration['classification']} "
        f"(peor {_fmt(concentration['worstContributionR'])} · "
        f"sin el peor {_fmt(concentration['expectancyWithoutWorstR'])})"
    )
    capture = artifact["capture"]
    print(
        f"excursión                 captura mediana {_fmt(capture['captureRatio']['median'], '.2f')} "
        f"(media {_fmt(capture['captureRatio']['mean'], '.2f')} · máx {_fmt(capture['captureRatio']['max'], '.2f')} "
        f"· >1 {capture['captureRatio']['aboveOneCount']})"
    )
    print(
        f"                          capturado {_fmt(capture['capturedR']['mean'])} R · "
        f"en la mesa {_fmt(capture['leftOnTableR']['mean'])} R · vueltas {capture['reversedCount']}"
    )
    severity = artifact["maeSeverity"]["populations"]

    def _breach(population: str) -> str:
        row = severity[population]
        breach = row["breaches"]["-1.00"]
        return f"{_fmt(breach['share'], '.2f')} ({breach['count']}/{row['cycles']})"

    print(
        f"                          MAE < -1R  todos {_breach('ALL')} · "
        f"ganadores {_breach('WINNERS')} · perdedores {_breach('LOSERS')}"
    )
    print()
    for key, title in (
        ("byRegime", "RÉGIMEN"),
        ("byStrategy", "ESTRATEGIA"),
        ("bySector", "SECTOR"),
    ):
        print(f"{title:<12} ETIQUETA                      R medio     hit      n")
        print("-" * 72)
        for row in artifact[key]:
            print(
                f"{'':<12} {row['label']:<28} {_fmt(row['expectancyR']):>8} "
                f"{_fmt(row['hitRate'], '.2f'):>5} {row['cycles']:>5}"
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
        "--check-against", default=None, help="artefacto longitudinal v2_91 para cruzar el resumen"
    )
    parser.add_argument("--account-id", default=_DEFAULT_ACCOUNT, help="cuenta de la ventana (etiqueta)")
    parser.add_argument("--version-a", default=_DEFAULT_VERSION_A, help="versión A de la ventana")
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
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
    if int(args.attribution_top_k) < 1:
        print("# uso incorrecto: --attribution-top-k debe ser >= 1", file=sys.stderr)
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
            f"# BLOQUEADO: no se pudo construir la atribución ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    window = artifact["window"]
    default_name = f"attribution-{window['from']}_{window['to']}.json"
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
