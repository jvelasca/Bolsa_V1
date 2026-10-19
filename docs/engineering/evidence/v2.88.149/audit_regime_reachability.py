#!/usr/bin/env python3
"""Instrumento READ-ONLY de alcanzabilidad del gate de regimen (auditoria 2026-10-19).

No escribe nada: no toca ledger, journal, pin ni la BD (solo SELECT). Responde tres
preguntas con las MISMAS piezas que el tick del motor:

1. Que regimen declara hoy el watch de la ventana (`classify_market_regime` ->
   `aggregate_trial_regime` -> `map_trial_regime` -> `regime_allows_entry_for`).
2. Por que ese eje veta: medidas crudas por simbolo (media 10/40 barras, volatilidad
   relativa y pendiente normalizada), para poder falsar un detector sesgado.
3. Si el gate es ALCANZABLE: backtest **as-of** (cada simbolo se clasifica solo con
   `bars[:t+1]`) y recuento de fechas en las que NINGUN simbolo esta bajista, que es
   la condicion necesaria para que el eje global permita LONG.
4. Cuanto abriria el gate PROPUESTO por ADR-047 (gate **por simbolo**): por la MISMA
   pasada as-of, cuantos simbolos serian operables cada dia. Es una **simulacion
   read-only**: el motor no cambia y no se escribe nada; mide el techo del cambio, no
   lo implementa.

Uso (desde la raiz del repo)::

    # Watch canonico de la ventana (universo ESTUDIO, fail-closed).
    uv run --no-sync python \\
        docs/engineering/evidence/v2.88.149/audit_regime_reachability.py \\
        --watch-from-estudio

    # Watch explicito y salida JSON.
    uv run --no-sync python \\
        docs/engineering/evidence/v2.88.149/audit_regime_reachability.py \\
        --symbols id1,id2 --json

Reglas duras: **no** baja umbrales, **no** fuerza regimen, **no** escribe evidencia y
**no** promociona nada; solo mide. Limite declarado: el backtest alinea las barras por
indice desde el final de cada simbolo (no por calendario) y usa el watch ACTUAL, de modo
que mide **alcanzabilidad** del gate, no el historico de la ventana.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_WATCH_SIZE = 20
_DEFAULT_MIN_BARS = 60


async def _resolve_watch(
    factory: Any,
    *,
    from_estudio: bool,
    symbols: Sequence[str],
    watch_size: int,
) -> tuple[list[str], str]:
    """Resuelve el watch como el preflight de `v2_76` y DECLARA su origen."""
    explicit = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
    if explicit:
        return explicit, "cli"
    if from_estudio:
        from bolsa_api.background.estudio_watch import (  # noqa: PLC0415
            SessionScopedEstudioList,
            resolve_daily_watch,
        )

        resolution = await resolve_daily_watch(SessionScopedEstudioList(factory))
        if not resolution.instrument_ids:
            raise RuntimeError(
                f"watch ESTUDIO vacio y fail-closed (status={resolution.status!r})"
            )
        return list(resolution.instrument_ids), "estudio"

    from sqlalchemy import func, select  # noqa: PLC0415

    from bolsa_infrastructure.database.models.tables import (  # noqa: PLC0415
        InstrumentRow,
        OhlcvBarRow,
    )

    async with factory() as session:
        with_history = (
            select(OhlcvBarRow.instrument_id)
            .where(OhlcvBarRow.timeframe == "1d")
            .group_by(OhlcvBarRow.instrument_id)
            .having(func.count() >= max(2, int(_DEFAULT_MIN_BARS)))
            .subquery()
        )
        stmt = (
            select(InstrumentRow.id)
            .join(with_history, with_history.c.instrument_id == InstrumentRow.id)
            .where(
                InstrumentRow.is_active.is_(True),
                InstrumentRow.sector.isnot(None),
            )
            .order_by(InstrumentRow.id)
            .limit(max(1, int(watch_size)))
        )
        watch = [str(row[0]) for row in (await session.execute(stmt)).all()]
    if not watch:
        raise RuntimeError("el catalogo no aporto ningun instrumento con sector y barras")
    return watch, "catalog"


async def _load_snapshot(factory: Any, watch: Sequence[str]) -> dict[str, list[Any]]:
    """Barras D1 por simbolo con el MISMO loader que compone el regimen del tick."""
    from bolsa_application.active_strategy_signal_evaluator import (  # noqa: PLC0415
        make_bar_snapshot_loader,
    )
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (  # noqa: PLC0415
        SqlAlchemyOhlcvRepository,
    )

    async with factory() as session:
        loader = make_bar_snapshot_loader(SqlAlchemyOhlcvRepository(session), list(watch))
        return await loader()


def _bar_day(bar: Any) -> str:
    for attribute in ("date", "day", "timestamp", "ts"):
        value = getattr(bar, attribute, None)
        if value is not None:
            return str(value)[:10]
    return "n/d"


def _symbol_rows(snapshot: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Etiqueta y MEDIDAS crudas por simbolo (para falsar un detector sesgado)."""
    from bolsa_application.discovery_market_regime import (  # noqa: PLC0415
        _LONG_WINDOW,
        _SHORT_WINDOW,
        _mean,
        _normalized_slope,
        _range_ratio,
        classify_market_regime,
    )

    rows: list[dict[str, Any]] = []
    for symbol, bars in snapshot.items():
        series = list(bars or [])
        closes = [float(bar.close) for bar in series if getattr(bar, "close", None) is not None]
        vol_ratio = _range_ratio(series) if series else None
        slope = (
            _normalized_slope(closes, vol_ratio=vol_ratio)
            if (len(closes) >= _LONG_WINDOW and vol_ratio is not None)
            else None
        )
        move = None
        if len(closes) >= _LONG_WINDOW and vol_ratio is not None:
            short = _mean(closes[-_SHORT_WINDOW:])
            long = _mean(closes[-_LONG_WINDOW:])
            if long > 0:
                move = (short - long) / long
        rows.append(
            {
                "symbol": symbol,
                "label": classify_market_regime(series),
                "bars": len(series),
                "first": _bar_day(series[0]) if series else "n/d",
                "last": _bar_day(series[-1]) if series else "n/d",
                "volRatio": None if vol_ratio is None else round(float(vol_ratio), 6),
                "movePct": None if move is None else round(float(move) * 100, 4),
                "slope": None if slope is None else round(float(slope), 4),
            }
        )
    return rows


def _reachability(snapshot: dict[str, list[Any]]) -> dict[str, Any]:
    """Backtest AS-OF: eje global (hoy) y gate por simbolo (ADR-047, simulado)."""
    from bolsa_analytics.cognitive.market_regime_gate import (  # noqa: PLC0415
        map_trial_regime,
        regime_allows_entry_for,
    )
    from bolsa_application.auto_v2_entry import aggregate_trial_regime  # noqa: PLC0415
    from bolsa_application.discovery_market_regime import (  # noqa: PLC0415
        MIN_REGIME_BARS,
        classify_market_regime,
    )

    length = min((len(list(bars or [])) for bars in snapshot.values()), default=0)
    open_days = 0
    aggregates: Counter[str] = Counter()
    operational_counts: Counter[str] = Counter()
    best_share = 0.0
    best_index = -1
    total = 0
    any_operable_days = 0
    all_operable_days = 0
    single_operable_days = 0
    operable_per_day: list[int] = []
    symbol_operable_days: Counter[str] = Counter()
    for index in range(MIN_REGIME_BARS - 1, length):
        labels = {
            symbol: classify_market_regime(list(bars or [])[: index + 1])
            for symbol, bars in snapshot.items()
        }
        aggregate = aggregate_trial_regime(labels.values())
        operational = map_trial_regime(aggregate)
        aggregates[aggregate] += 1
        operational_counts[operational] += 1
        total += 1
        if regime_allows_entry_for(operational, "long"):
            open_days += 1
        operable = [
            symbol
            for symbol, label in labels.items()
            if regime_allows_entry_for(map_trial_regime(label), "long")
        ]
        operable_per_day.append(len(operable))
        symbol_operable_days.update(operable)
        if operable:
            any_operable_days += 1
        if len(operable) == len(labels):
            all_operable_days += 1
        if len(operable) == 1:
            single_operable_days += 1
        non_down = sum(
            1 for value in labels.values() if value in ("trend_up", "range", "low_vol")
        )
        share = non_down / max(1, len(labels))
        if share > best_share:
            best_share, best_index = share, index

    ordered = sorted(operable_per_day)
    if ordered:
        def _pct(fraction: float) -> int:
            position = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
            return ordered[position]

        distribution = {
            "min": ordered[0],
            "p25": _pct(0.25),
            "median": ordered[len(ordered) // 2] if len(ordered) % 2 else (
                ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]
            )
            / 2,
            "p75": _pct(0.75),
            "max": ordered[-1],
        }
    else:
        distribution = {"min": None, "p25": None, "median": None, "p75": None, "max": None}

    return {
        "asOfDays": total,
        "alignedBars": length,
        "daysLongAllowed": open_days,
        "aggregateCounts": dict(aggregates),
        "operationalCounts": dict(operational_counts),
        "maxNonDownShare": round(best_share, 4),
        "maxNonDownIndex": best_index,
        "perSymbol": {
            "hypothesis": "ADR-047 (gate direccional por simbolo) SIMULADO; el motor no cambia",
            "daysWithAnyOperable": any_operable_days,
            "daysWithAllOperable": all_operable_days,
            "daysWithSingleOperable": single_operable_days,
            "operablePerDay": distribution,
            "symbolOperableDays": dict(sorted(symbol_operable_days.items())),
            "symbolsNeverOperable": sorted(
                symbol for symbol in snapshot if symbol_operable_days[symbol] == 0
            ),
            "criterion": (
                "necesario, NO suficiente: un dia medible exige ademas senal/ciclo; "
                "un simbolo operable es el que pasaria regime_allows_entry_for(long)"
            ),
        },
    }


def _summary(snapshot: dict[str, list[Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    from bolsa_analytics.cognitive.market_regime_gate import (  # noqa: PLC0415
        map_trial_regime,
        regime_allows_entry_for,
    )
    from bolsa_application.auto_v2_entry import aggregate_trial_regime  # noqa: PLC0415

    labels = {str(row["symbol"]): str(row["label"]) for row in rows}
    counts = Counter(labels.values())
    aggregate = aggregate_trial_regime(labels.values())
    operational = map_trial_regime(aggregate)
    return {
        "watchSize": len(labels),
        "barsLoaded": len(snapshot),
        "counts": dict(counts),
        "aggregateTrialRegime": aggregate,
        "operationalRegime": operational,
        "entriesAllowedLong": bool(regime_allows_entry_for(operational, "long")),
    }


def _print_report(payload: dict[str, Any]) -> None:
    summary = payload["regime"]
    print("AUDITORIA READ-ONLY · ALCANZABILIDAD DEL GATE DE REGIMEN")
    print("-" * 72)
    print(f"watch                    {summary['watchSize']} simbolos ({payload['watchSource']})")
    print(f"barras servidas          {summary['barsLoaded']}")
    print(f"regimen por simbolo      {summary['counts']}")
    print(f"agregado (mas conserv.)  {summary['aggregateTrialRegime']}")
    print(f"eje operativo            {summary['operationalRegime']}")
    print(
        "entradas LONG            "
        + ("PERMITIDAS" if summary["entriesAllowedLong"] else "VETADAS (regime_invalid)")
    )
    print()
    print("simbolo,label,bars,primera,ultima,volRatio,movePct,slope")
    for row in sorted(payload["symbols"], key=lambda item: (item["label"], item["movePct"] or 0)):
        print(
            f"{row['symbol']},{row['label']},{row['bars']},{row['first']},{row['last']},"
            f"{row['volRatio']},{row['movePct']},{row['slope']}"
        )
    reach = payload["reachability"]
    print()
    print(
        f"as-of: dias={reach['asOfDays']} barras_alineadas={reach['alignedBars']} "
        f"LONG_permitida={reach['daysLongAllowed']}/{reach['asOfDays']}"
    )
    print(f"as-of agregado           {reach['aggregateCounts']}")
    print(f"as-of eje operativo      {reach['operationalCounts']}")
    print(
        f"as-of max no-bajista     {reach['maxNonDownShare']:.3f} "
        f"(indice {reach['maxNonDownIndex']})"
    )
    post = reach.get("perSymbol") or {}
    if post:
        dist = post.get("operablePerDay") or {}
        print()
        print("as-of POST (ADR-047 simulado: gate por simbolo; el motor NO cambia)")
        print(
            f"dias con >=1 operable    {post['daysWithAnyOperable']}/{reach['asOfDays']} "
            f"(hoy, eje global: {reach['daysLongAllowed']}/{reach['asOfDays']})"
        )
        print(f"dias con 1 solo operable {post['daysWithSingleOperable']} (fragiles)")
        print(f"dias con TODOS operables {post['daysWithAllOperable']}")
        print(
            "operables por dia        "
            f"min {dist.get('min')} · p25 {dist.get('p25')} · mediana {dist.get('median')} · "
            f"p75 {dist.get('p75')} · max {dist.get('max')}"
        )
        never = post.get("symbolsNeverOperable") or []
        print(f"simbolos nunca operables {len(never)}{(': ' + ','.join(never)) if never else ''}")


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv  # noqa: PLC0415

    load_dotenv(_REPO_ROOT / ".env", override=False)

    from bolsa_infrastructure.config import get_settings  # noqa: PLC0415
    from bolsa_infrastructure.database.session import (  # noqa: PLC0415
        create_engine,
        create_session_factory,
    )

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        watch, source = await _resolve_watch(
            factory,
            from_estudio=bool(args.watch_from_estudio),
            symbols=[symbol for symbol in str(args.symbols or "").split(",") if symbol.strip()],
            watch_size=int(args.watch_size),
        )
        snapshot = await _load_snapshot(factory, watch)
    finally:
        await engine.dispose()

    rows = _symbol_rows(snapshot)
    return {
        "bump": "v2.88.149-beta",
        "mode": "audit-regime-reachability",
        "watchSource": source,
        "watch": list(watch),
        "regime": _summary(snapshot, rows),
        "symbols": rows,
        "reachability": _reachability(snapshot),
        "limits": [
            "solo SELECT: el instrumento no escribe ledger, journal, pin ni BD",
            "backtest as-of por indice desde el final de cada simbolo (no por calendario)",
            "usa el watch ACTUAL: mide ALCANZABILIDAD del gate, no el historico de la ventana",
            "POST simulado (ADR-047): mide el TECHO del gate por simbolo; no implementa nada",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="", help="watch explicito separado por comas")
    parser.add_argument(
        "--watch-from-estudio",
        action="store_true",
        help="watch canonico ESTUDIO (fail-closed; el de la ventana)",
    )
    parser.add_argument("--watch-size", type=int, default=_DEFAULT_WATCH_SIZE)
    parser.add_argument("--json", action="store_true", help="emite el payload como JSON")
    args = parser.parse_args(argv)

    if sys.platform == "win32":  # pragma: no cover - psycopg async exige SelectorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    payload = asyncio.run(_run(args))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
