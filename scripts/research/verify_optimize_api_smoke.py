#!/usr/bin/env python3
"""Optional HTTP smoke for optimize lab (API + DB required).

Skip (exit 0) if API is down — unless OPTIMIZE_API_REQUIRED=1.

Usage:
  python scripts/research/verify_optimize_api_smoke.py
  OPTIMIZE_API_REQUIRED=1 python scripts/research/verify_optimize_api_smoke.py

Env:
  BOLSA_API_URL   default http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED = os.environ.get("OPTIMIZE_API_REQUIRED", "").strip() in {"1", "true", "yes"}


def _get(path: str) -> tuple[int, object]:
    req = urllib.request.Request(f"{API}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=8) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body) if body else None


def _post(path: str, payload: dict) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body) if body else None


def main() -> int:
    print("=== verify_optimize_api_smoke ===")
    print(f"API={API} required={REQUIRED}")
    try:
        status, health = _get("/api/health")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        msg = f"API no contactable: {exc}"
        if REQUIRED:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIP: {msg}")
        return 0

    if status != 200:
        print(f"FAIL: /api/health status={status}")
        return 1 if REQUIRED else 0
    print(f"OK health: {health}")

    try:
        status, instruments = _get("/api/instruments")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"FAIL: instruments: {exc}")
        return 1

    rows = instruments.get("data") if isinstance(instruments, dict) else None
    if not rows:
        print("FAIL: no instruments in DB (seed/sync required)")
        return 1
    instrument_id = rows[0]["id"]
    symbol = rows[0].get("symbol", "?")
    print(f"OK instrument: {symbol} ({instrument_id})")

    payload = {
        "instrumentId": instrument_id,
        "strategyFamily": "sma_crossover",
        "fastPeriods": [10, 15],
        "slowPeriods": [40, 50],
        "initialCash": 10000,
        "barLimit": 400,
        "timeframe": "1d",
        "maxTrials": 8,
        "engine": "h0",
        "oosPct": 0.2,
    }
    try:
        status, result = _post("/api/backtests/optimize", payload)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"FAIL: optimize HTTP {exc.code}: {detail[:500]}")
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"FAIL: optimize request: {exc}")
        return 1

    if status != 200 or not isinstance(result, dict):
        print(f"FAIL: unexpected optimize response status={status}")
        return 1

    data = result.get("data") or {}
    trials = data.get("trials") or []
    if not trials:
        print("FAIL: optimize returned zero trials (need synced OHLCV?)")
        return 1
    if not data.get("oosPct"):
        print("FAIL: expected oosPct on result when oosPct=0.2 was requested")
        return 1
    if trials[0].get("oosMetrics") is None:
        print("FAIL: expected oosMetrics on trials (warmed OOS)")
        return 1

    def _oos_rank_key(trial: dict) -> float:
        metrics = trial.get("oosMetrics") or {}
        score = metrics.get("score")
        if score is None:
            return float("-inf")
        key = float(score)
        trades = int(metrics.get("tradeCount") or 0)
        if trades < 2:
            key -= 1000.0
        return key

    top_key = _oos_rank_key(trials[0])
    for trial in trials[1:]:
        if _oos_rank_key(trial) > top_key + 1e-9:
            print(
                "FAIL: trials[0] is not best by OOS rank "
                f"(top={top_key} beaten by {_oos_rank_key(trial)})"
            )
            return 1

    print(
        f"OK optimize: engine={data.get('engine')} trials={len(trials)} "
        f"oosPct={data.get('oosPct')} trials0_IS={trials[0].get('score')} "
        f"trials0_OOS={trials[0].get('oosMetrics', {}).get('score')} "
        f"(API ordered by OOS)"
    )
    print("OK API smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
