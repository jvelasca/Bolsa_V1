"""V2.101 · LÍNEAS BASE FALSABLES (read-only): ¿algún brazo razonable gana en 2021-2026?

Qué es
------
La evidencia DÍA-D respondió «¿AUTO cumple la política de la cuenta?» y salió ``REFUTED``.
Esa respuesta, sola, no distingue «la señal no aporta» de «con estos costes nada gana».
Este runner mide, con los CINCO umbrales **fijados antes de correr**
(``baseline_arms.BASELINE_THRESHOLDS``), tres brazos sobre la MISMA ventana:

1. ``buyHold``: comprar y mantener equiponderado el mismo watch.
2. ``trendRegime``: largo si la cesta cierra sobre su SMA(N), caja si no, ejecución al open
   siguiente y costes 10/5/2 bps.
3. ``autoV2``: la corrida DÍA-D real (``v2_93``) consumida desde su artefacto JSON, con el
   edge que la estrategia DECLARÓ (``--edge`` obligatorio) y su coste de ida y vuelta medido.

Qué NO es
---------
* No es un motor nuevo: reutiliza el harness/herramientas existentes y las mismas funciones
  de medición (``dia_d_equity_evidence``).
* No cambia defaults ni enciende AUTO: es advisory y read-only.
* Un dato ausente se declara ``None``/``NOT_MEASURED``; nunca se rellena con ``0``.
* Sin ``--auto-artifact`` el brazo AUTO queda ``NOT_MEASURED`` y el veredicto no lo inventa.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_101_baseline_arms.py \\
        --from-year 2021 --to-year 2026 --edge 0.62 \\
        --auto-artifact operability_runs/dia-d-auto/multi-2021_2026.json --json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import pathlib
import sys
from datetime import UTC, datetime
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"
_OUT_SUBDIR = pathlib.Path("operability_runs") / "baseline"
_DEFAULT_YEARS = "2021,2022,2023,2024,2025,2026"

logger = logging.getLogger("v2_101_baseline_arms")


def _load_module(filename: str, name: str) -> Any:
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _resolve_years(args: argparse.Namespace) -> list[int]:
    if args.years:
        raw = [chunk.strip() for chunk in str(args.years).split(",") if chunk.strip()]
        return sorted({int(chunk) for chunk in raw})
    if int(args.from_year) > int(args.to_year):
        raise RuntimeError(f"rango invertido: {args.from_year} > {args.to_year}")
    return list(range(int(args.from_year), int(args.to_year) + 1))


def _window_holdout(
    curve: list[tuple[str, float]], days: list[str], holdout_pct: float
) -> dict[str, Any]:
    """Corta la curva en in-sample/out-of-sample por día; ambos tramos se miden aparte."""
    from bolsa_application.dia_d_equity_evidence import (
        holdout_split,
        max_drawdown_pct,
        net_return_pct,
    )

    split = holdout_split(days, holdout_pct=holdout_pct)
    cut_day = split.get("cutDay") or ""
    inside = [(day, equity) for day, equity in curve if cut_day and day < cut_day]
    outside = [(day, equity) for day, equity in curve if cut_day and day >= cut_day]
    return {
        "holdoutPct": holdout_pct,
        **split,
        "inSampleDays": len(inside),
        "inSampleNetReturnPct": net_return_pct(inside),
        "inSampleMaxDrawdownPct": max_drawdown_pct(inside),
        "outOfSampleDays": len(outside),
        "outOfSampleNetReturnPct": net_return_pct(outside),
        "outOfSampleMaxDrawdownPct": max_drawdown_pct(outside),
    }


def _arm_from_curve(
    *,
    curve: list[tuple[str, float]],
    benchmark: list[tuple[str, float]],
    days: list[str],
    realized_cost_round_trip_bps: float | None,
    holdout_pct: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from bolsa_application.baseline_arms import evaluate_baseline, summarize_curve

    summary = summarize_curve(curve, buy_hold_curve=benchmark)
    evaluation = evaluate_baseline(
        summary, realized_cost_round_trip_bps=realized_cost_round_trip_bps
    )
    return {
        "summary": summary,
        "holdout": _window_holdout(curve, days, holdout_pct),
        "evaluation": evaluation,
        **(extra or {}),
    }


def _auto_arm(artifact: dict[str, Any], *, holdout_pct: float) -> dict[str, Any]:
    """Brazo AUTO desde el artefacto DÍA-D: su curva, su benchmark y su coste MEDIDO."""
    from bolsa_application.baseline_arms import evaluate_baseline

    equity = artifact.get("equityEvidence")
    if not isinstance(equity, dict) or not equity.get("curve"):
        return {
            "verdict": "NOT_MEASURED",
            "reason": "el artefacto DÍA-D no trae equityEvidence.curve (corre con --equity-evidence)",
        }
    curve = [
        (str(point["day"]), float(point["equity"]))
        for point in equity["curve"]
        if point.get("day") and point.get("equity") is not None
    ]
    buy_hold = equity.get("buyHold") or {}
    summary = {
        "points": len(curve),
        "netReturnPct": equity.get("netReturnPct"),
        "maxDrawdownPct": equity.get("maxDrawdownPct"),
        "positiveWindowPct": equity.get("positiveWindowPct"),
        "measuredWindows": (equity.get("positiveWindows") or {}).get("measuredWindows"),
        "buyHoldNetReturnPct": buy_hold.get("pct"),
        "excessVsBuyHoldPct": buy_hold.get("excessPct"),
    }
    cost = equity.get("realizedCostRoundTripBps")
    evaluation = evaluate_baseline(summary, realized_cost_round_trip_bps=cost)
    holdout = equity.get("holdout") or {}
    return {
        "summary": summary,
        "holdout": {
            "holdoutPct": holdout.get("holdoutPct", holdout_pct),
            "cutDay": holdout.get("cutDay"),
            "inSampleDays": holdout.get("inSampleDays"),
            "inSampleNetReturnPct": holdout.get("inSampleNetReturnPct"),
            "inSampleMaxDrawdownPct": holdout.get("inSampleMaxDrawdownPct"),
            "outOfSampleDays": holdout.get("outOfSampleDays"),
            "outOfSampleNetReturnPct": holdout.get("outOfSampleNetReturnPct"),
            "outOfSampleMaxDrawdownPct": holdout.get("outOfSampleMaxDrawdownPct"),
        },
        "evaluation": evaluation,
        "realizedCostBpsPerSide": equity.get("realizedCostBpsPerSide"),
        "declaredEdge": (artifact.get("meta") or {}).get("declaredEdge"),
        "source": {
            "kind": (artifact.get("meta") or {}).get("phase"),
            "startDay": equity.get("startDay"),
            "endDay": equity.get("endDay"),
        },
        "notMeasured": equity.get("notMeasured") or [],
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.baseline_arms import (
        BASELINE_THRESHOLDS,
        BaselineCosts,
        buy_hold_curve,
        trend_regime_curve,
    )
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    years = _resolve_years(args)
    first_day, last_day = f"{years[0]}-01-01", f"{years[-1]}-12-31"

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        v86 = _load_module("v2_86_replay_oos_viability.py", "v2_86_replay_oos_viability")
        explicit = [chunk.strip() for chunk in (args.watch or "").split(",") if chunk.strip()]
        if explicit:
            watch, watch_source = explicit, "explicit"
        else:
            v76 = v86._load_v76_module()  # noqa: SLF001 — MISMA derivación del watch.
            watch = await v76._watch_from_catalog(  # noqa: SLF001
                factory, int(args.watch_size), min_bars=int(args.min_bars)
            )
            watch_source = "catalog"
        if not watch:
            raise RuntimeError("no hay watch: ni --watch ni el catálogo aportaron instrumentos")

        bars_by_symbol = await v86._read_bars(factory, watch)  # noqa: SLF001
        all_days = v86._trading_days(bars_by_symbol)  # noqa: SLF001
        days = [day for day in all_days if first_day <= day <= last_day]
        if len(days) < 2:
            raise RuntimeError(f"sin barras suficientes en {first_day}..{last_day}")

        costs = BaselineCosts()
        benchmark = buy_hold_curve(bars_by_symbol=bars_by_symbol, watch=watch, days=days)
        trend, trend_meta = trend_regime_curve(
            bars_by_symbol=bars_by_symbol,
            watch=watch,
            days=days,
            costs=costs,
            sma_window=int(args.sma_window),
        )

        arms: dict[str, Any] = {
            "buyHold": _arm_from_curve(
                curve=benchmark,
                benchmark=benchmark,
                days=days,
                realized_cost_round_trip_bps=costs.round_trip_bps,
                holdout_pct=float(args.holdout_pct),
                extra={"note": "pasivo: paga un round-trip declarado, no opera gratis"},
            ),
            "trendRegime": _arm_from_curve(
                curve=trend,
                benchmark=benchmark,
                days=days,
                realized_cost_round_trip_bps=costs.round_trip_bps,
                holdout_pct=float(args.holdout_pct),
                extra={"signal": trend_meta},
            ),
        }

        auto_path = pathlib.Path(args.auto_artifact) if args.auto_artifact else None
        if auto_path is not None:
            if not auto_path.is_absolute():
                auto_path = _REPO_ROOT / auto_path
            artifact = json.loads(auto_path.read_text(encoding="utf-8"))
            arms["autoV2"] = _auto_arm(artifact, holdout_pct=float(args.holdout_pct))
            arms["autoV2"]["artifactPath"] = str(auto_path)
            declared = arms["autoV2"].get("declaredEdge")
            if (
                args.edge is not None
                and declared is not None
                and float(args.edge) != float(declared)
            ):
                arms["autoV2"]["edgeMismatch"] = {
                    "requested": float(args.edge),
                    "artifact": float(declared),
                }
        else:
            arms["autoV2"] = {
                "verdict": "NOT_MEASURED",
                "reason": "sin --auto-artifact: el brazo AUTO no se mide ni se supone",
            }

        accredited = [
            name
            for name, arm in arms.items()
            if (arm.get("evaluation") or {}).get("verdict") == "ACCREDITED"
        ]
        return {
            "kind": "dia-d-baseline-arms-v1",
            "generatedAt": datetime.now(UTC).isoformat(),
            "window": {
                "years": years,
                "firstDay": days[0],
                "lastDay": days[-1],
                "tradingDays": len(days),
                "holdoutPct": float(args.holdout_pct),
            },
            "thresholds": dict(BASELINE_THRESHOLDS),
            "costs": costs.to_dict(),
            "watch": {
                "source": watch_source,
                "size": len(watch),
                "symbols": list(watch),
                "symbolsWithBars": sum(1 for s in watch if bars_by_symbol.get(s)),
            },
            "declaredEdge": float(args.edge) if args.edge is not None else None,
            "arms": arms,
            "decision": {
                "accreditedArms": accredited,
                "action": "PROMOTE_WITH_PAPER" if accredited else "AUTO_STAYS_OFF",
                "rule": (
                    "ningún brazo pasa los cinco umbrales ⇒ el cuello de botella es la señal "
                    "(no se toca AUTO ni se añade gobernanza)"
                    if not accredited
                    else "algún brazo pasa los cinco ⇒ promover con ventana PAPER, no por default"
                ),
            },
        }
    finally:
        await engine.dispose()


def _fmt(value: Any, spec: str = "+.3f") -> str:
    return "n/d" if value is None else format(float(value), spec)


def _print_text(artifact: dict[str, Any]) -> None:
    window = artifact["window"]
    print(
        f"LÍNEAS BASE · {window['firstDay']} .. {window['lastDay']} ({window['tradingDays']} días)"
    )
    print("=" * 78)
    print(
        f"watch {artifact['watch']['source']} · {artifact['watch']['size']} símbolos "
        f"({artifact['watch']['symbolsWithBars']} con barras)"
    )
    print(
        f"costes {artifact['costs']['commissionBps']:.0f}/"
        f"{artifact['costs']['slippageBps']:.0f}/{artifact['costs']['spreadBps']:.0f} bps "
        f"⇒ round-trip {artifact['costs']['roundTripBps']:.2f} bps"
    )
    print()
    for name, arm in artifact["arms"].items():
        evaluation = arm.get("evaluation")
        if not evaluation:
            print(f"{name:<12} NOT_MEASURED · {arm.get('reason')}")
            continue
        summary = arm["summary"]
        holdout = arm.get("holdout") or {}
        print(
            f"{name:<12} {evaluation['verdict']:<13} "
            f"neto {_fmt(summary.get('netReturnPct'))} % · "
            f"DD {_fmt(summary.get('maxDrawdownPct'), '.2f')} % · "
            f"ventanas+ {_fmt(summary.get('positiveWindowPct'), '.2f')} % · "
            f"exceso {_fmt(summary.get('excessVsBuyHoldPct'))} %"
        )
        print(
            f"{'':<12} OOS {holdout.get('outOfSampleDays')} días · "
            f"{_fmt(holdout.get('outOfSampleNetReturnPct'))} %"
        )
        for check in evaluation["checks"]:
            print(
                f"{'':<12}   {check['name']:<26} {check['verdict']:<13} "
                f"medido {_fmt(check['measured'])} · umbral {_fmt(check['limit'])}"
            )
    print()
    decision = artifact["decision"]
    print(f"DECISIÓN: {decision['action']} ({decision['rule']})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years", default=None, help=f"años separados por coma (def. {_DEFAULT_YEARS})"
    )
    parser.add_argument("--from-year", type=int, default=2021)
    parser.add_argument("--to-year", type=int, default=2026)
    parser.add_argument("--watch", default=None, help="instrumentos separados por coma")
    parser.add_argument("--watch-size", type=int, default=20)
    parser.add_argument("--min-bars", type=int, default=60)
    parser.add_argument(
        "--edge",
        type=float,
        default=None,
        help="edge DECLARADO por la estrategia para el brazo AUTO (obligatorio si hay artefacto)",
    )
    parser.add_argument(
        "--auto-artifact",
        default=None,
        help="JSON de v2_93 con equityEvidence: el brazo AUTO se mide desde ahí, no se inventa",
    )
    parser.add_argument("--sma-window", type=int, default=200, help="ventana SMA del filtro")
    parser.add_argument(
        "--holdout-pct", type=float, default=30.0, help="%% de días fuera de muestra"
    )
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args(argv)

    if not (0.0 <= float(args.holdout_pct) < 100.0):
        print("# uso incorrecto: --holdout-pct debe estar en [0, 100)", file=sys.stderr)
        return 1
    if int(args.sma_window) < 2:
        print("# uso incorrecto: --sma-window debe ser >= 2", file=sys.stderr)
        return 1
    if args.edge is None and args.auto_artifact:
        print(
            "# uso incorrecto: declara --edge con el edge REAL de la estrategia; sin él no se "
            "puede contrastar el artefacto AUTO ni evitar la circularidad del 0.9 de fábrica",
            file=sys.stderr,
        )
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        artifact = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay línea base: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo medir la línea base ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str))
    else:
        _print_text(artifact)

    out_path = pathlib.Path(args.out) if args.out else None
    if out_path is None:
        window = artifact["window"]
        out_path = _OUT_SUBDIR / f"baseline-arms-{window['firstDay']}_{window['lastDay']}.json"
    if not out_path.is_absolute():
        out_path = _REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"# artefacto: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
