#!/usr/bin/env python3
"""
Smoke live: embudo mínimo → Finalistas en BD para un ticker (default UNI).

Qué prueba:
  1) Localiza instrumento por símbolo
  2) Crea 3 estrategias from-preset (vivas en Biblioteca)
  3) Lanza 3 backtests H0
  4) PUT strategy-top (Finalistas active · lab_validated)
  5) Verifica GET top + que las defs existen (Biblioteca no queda en 0)

Uso (API :8000 arriba):
  python scripts/research/verify_finalists_roundtrip_smoke.py
  python scripts/research/verify_finalists_roundtrip_smoke.py --symbol TEF
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "http://127.0.0.1:8000"

# Tres presets genéricos estables del catálogo.
PRESETS: list[tuple[str, str]] = [
    ("sma_crossover", "Cruce SMA"),
    ("rsi_mean_reversion", "RSI mean-reversion"),
    ("ema_crossover", "Cruce EMA"),
]


def http_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {method} {path}: {detail}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"API no alcanzable en {API}: {e}") from e


def find_instrument(symbol: str) -> dict[str, Any]:
    q = urllib.parse.urlencode({"q": symbol, "limit": 50})
    payload = http_json("GET", f"/api/instruments?{q}")
    rows = payload.get("data") or []
    for row in rows:
        if str(row.get("symbol", "")).upper() == symbol.upper():
            return row
    raise SystemExit(f"Instrumento {symbol!r} no encontrado")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="UNI", help="Ticker (default UNI = Unicaja)")
    parser.add_argument("--replace", action="store_true", help="DELETE TOP previo antes de grabar")
    args = parser.parse_args()
    symbol = args.symbol.upper()

    print(f"Bolsa V1 — Finalistas roundtrip smoke · {symbol}")
    health = http_json("GET", "/api/health")
    print(f"health: {health.get('status', health)}")

    inst = find_instrument(symbol)
    instrument_id = inst["id"]
    print(f"instrument: {inst.get('symbol')} · {inst.get('name')} · {instrument_id}")

    if args.replace:
        try:
            http_json(
                "DELETE",
                f"/api/instruments/{instrument_id}/strategy-top?timeframe=1d",
            )
            print("TOP previo eliminado")
        except SystemExit as e:
            print(f"(delete TOP): {e}")

    slots: list[dict[str, Any]] = []
    for rank, (preset, label) in enumerate(PRESETS, start=1):
        name = f"{symbol} · smoke · {label}"
        created = http_json(
            "POST",
            "/api/strategies/from-preset",
            {
                "name": name,
                "presetKey": preset,
                "timeframe": "1d",
            },
        )
        strat = created["data"]
        sid = strat["id"]
        print(f"  strategy #{rank}: {sid} · {name}")

        run = http_json(
            "POST",
            "/api/backtests/run",
            {
                "instrumentId": instrument_id,
                "strategyDefinitionId": sid,
                "strategyType": preset,
                "timeframe": "1d",
                "initialCash": 10_000,
                "commissionBps": 0,
                "slippageBps": 0,
            },
        )
        detail = run.get("data") or run
        run_id = detail["id"]
        metrics = detail.get("metrics") or {}
        ret = metrics.get("totalReturnPct")
        print(f"  backtest #{rank}: {run_id} · ret={ret}")

        slots.append(
            {
                "rank": rank,
                "label": label,
                "strategyType": preset,
                "strategyDefinitionId": sid,
                "stars": 3.0,
                "score": 60.0,
                "runId": run_id,
                "source": "optimized",
                "totalReturnPct": ret,
            }
        )

    upsert = http_json(
        "PUT",
        f"/api/instruments/{instrument_id}/strategy-top",
        {
            "instrumentId": instrument_id,
            "symbol": symbol,
            "timeframe": "1d",
            "periodLabel": "smoke roundtrip",
            "status": "active",
            "evidenceLevel": "lab_validated",
            "slots": slots,
            "coachHeadline": f"{symbol}: smoke Finalistas roundtrip",
            "coachFacts": {"engine": "verify_finalists_roundtrip_smoke", "symbol": symbol},
        },
    )
    top = upsert["data"]
    print(f"TOP upserted: v{top.get('version')} · slots={len(top.get('slots') or [])}")

    # Verify
    got = http_json(
        "GET",
        f"/api/instruments/{instrument_id}/strategy-top?timeframe=1d",
    )["data"]
    assert got and len(got["slots"]) == 3, got

    strategies = http_json("GET", "/api/strategies")["data"]
    by_id = {s["id"]: s for s in strategies}
    missing = [s["strategyDefinitionId"] for s in got["slots"] if s["strategyDefinitionId"] not in by_id]
    if missing:
        # Algunas APIs truncan el listado; probar GET por id
        still = []
        for mid in missing:
            try:
                one = http_json("GET", f"/api/strategies/{mid}")["data"]
                if not one:
                    still.append(mid)
            except SystemExit:
                still.append(mid)
        missing = still

    if missing:
        print(f"FAIL: estrategias del TOP no resolubles: {missing}")
        return 1

    for s in got["slots"]:
        rid = s.get("runId")
        http_json("GET", f"/api/backtests/{rid}")
        print(f"  OK slot #{s['rank']} · def={s['strategyDefinitionId'][:10]}… · run={rid[:10]}…")

    print("\nPASS: Finalistas en BD + estrategias + runs vivos")
    print(f"  UI: Biblioteca -> Finalistas · {symbol} deberia listar 3 (no 0).")
    print("  Si ves TOP huerfano antiguo: Eliminar Finalistas y re-Play, o este smoke con --replace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
