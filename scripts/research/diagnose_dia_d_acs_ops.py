#!/usr/bin/env python3
"""
Diagnóstico operativo DÍA D completo — ACS (u otro ticker).

Replica la estrategia de producto (ADR-021):
  A/B) Embudo ≤ D (IS as-of D) con presets típicos del Coach
  C)   Verificar D→hoy (OOS) con cada candidata
  R)   Compara tradeCount / retorno IS vs OOS y señala causas de 0 ops

Uso (API :8000):
  python scripts/research/diagnose_dia_d_acs_ops.py
  python scripts/research/diagnose_dia_d_acs_ops.py --symbol ACS --dia-d 2025-08-01
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

API = "http://127.0.0.1:8000"

# Presets alineados con embudo / Finalistas roundtrip.
PRESETS: list[tuple[str, str]] = [
    ("sma_crossover", "Cruce SMA 20/50"),
    ("ema_crossover", "Cruce EMA"),
    ("rsi_mean_reversion", "RSI mean-reversion"),
    ("macd_crossover", "MACD"),
    ("bollinger_mean_reversion", "Bollinger MR"),
]


def http_json(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 300) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {detail[:800]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"API no alcanzable en {API}: {e}") from e


def find_instrument(symbol: str) -> dict[str, Any]:
    q = urllib.parse.urlencode({"q": symbol, "limit": 50})
    payload = http_json("GET", f"/api/instruments?{q}")
    rows = payload.get("data") or []
    for row in rows:
        if str(row.get("symbol", "")).upper() == symbol.upper():
            return row
    raise SystemExit(f"Instrumento {symbol!r} no encontrado")


def run_bt(
    *,
    instrument_id: str,
    strategy_type: str,
    date_from: str | None,
    date_to: str | None,
    label: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "instrumentId": instrument_id,
        "strategyType": strategy_type,
        "timeframe": "1d",
        "initialCash": 10_000,
        "commissionBps": 5,
        "slippageBps": 5,
        "limit": 10_000,
    }
    if date_from:
        body["dateFrom"] = date_from
    if date_to:
        body["dateTo"] = date_to
    wrap = http_json("POST", "/api/backtests/run", body)
    data = wrap.get("data") if isinstance(wrap, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError(f"run sin data ({label})")
    return data


def summarize(run: dict[str, Any], phase: str) -> dict[str, Any]:
    trades = run.get("trades") or []
    first_ts = trades[0].get("timestamp") if trades else None
    last_ts = trades[-1].get("timestamp") if trades else None
    return {
        "phase": phase,
        "id": run.get("id"),
        "bars": run.get("barCount"),
        "trades": run.get("tradeCount"),
        "retPct": run.get("totalReturnPct"),
        "ddPct": run.get("maxDrawdownPct"),
        "dateFrom": (run.get("outputs") or {}).get("dateFrom")
        if isinstance(run.get("outputs"), dict)
        else None,
        "dateTo": (run.get("outputs") or {}).get("dateTo")
        if isinstance(run.get("outputs"), dict)
        else None,
        "firstTrade": first_ts,
        "lastTrade": last_ts,
        "reasonsSample": [
            t.get("reason") for t in trades[:3] if isinstance(t, dict)
        ],
    }


def ohlcv_probe(instrument_id: str, date_from: str, date_to: str) -> dict[str, Any]:
    """Cuenta velas en ventana vía backtest buy&hold-ish: usamos run SMA y miramos bars."""
    # Preferir endpoint ohlcv si existe
    try:
        q = urllib.parse.urlencode({"limit": 10000, "timeframe": "1d"})
        wrap = http_json("GET", f"/api/instruments/{instrument_id}/ohlcv?{q}")
        bars = wrap.get("data") if isinstance(wrap, dict) else None
        if not isinstance(bars, list):
            return {"ok": False, "error": "ohlcv sin lista"}
        in_win = [
            b
            for b in bars
            if isinstance(b, dict)
            and date_from <= str(b.get("timestamp", ""))[:10] <= date_to
        ]
        all_dates = sorted(
            str(b.get("timestamp", ""))[:10]
            for b in bars
            if isinstance(b, dict) and b.get("timestamp")
        )
        return {
            "ok": True,
            "totalBarsFetched": len(bars),
            "barsInWindow": len(in_win),
            "firstBar": all_dates[0] if all_dates else None,
            "lastBar": all_dates[-1] if all_dates else None,
            "windowFirst": in_win[0].get("timestamp") if in_win else None,
            "windowLast": in_win[-1].get("timestamp") if in_win else None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def diagnose_row(is_sum: dict[str, Any], oos_sum: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if (is_sum.get("bars") or 0) < 60:
        notes.append(
            f"IS ≤D con pocas barras ({is_sum.get('bars')}) — warmup puede comerse señales"
        )
    if (oos_sum.get("bars") or 0) < 20:
        notes.append(
            f"OOS D→hoy con pocas barras ({oos_sum.get('bars')}) — ventana corta o sin datos"
        )
    if (oos_sum.get("trades") or 0) == 0:
        notes.append("OOS sin trades: estrategia no cruzó / sin señales en D→hoy")
        if (is_sum.get("trades") or 0) == 0:
            notes.append("IS también 0 trades → preset/params poco activos en este valor")
        else:
            notes.append(
                f"IS sí tuvo {is_sum.get('trades')} trades ≤D → el freeze a D→hoy "
                "simplemente no generó cruces nuevos (posible, no bug de vacío de datos)"
            )
    if (oos_sum.get("bars") or 0) == 0:
        notes.append("CRITICAL: 0 barras OOS — dateFrom/dateTo mal resueltos o sin OHLCV")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ACS")
    parser.add_argument(
        "--dia-d",
        default=None,
        help="YYYY-MM-DD (default: hace ~365 días)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Fin V (default: hoy)",
    )
    args = parser.parse_args()
    symbol = args.symbol.upper()
    today = date.today().isoformat()
    dia_d = args.dia_d or (date.today() - timedelta(days=365)).isoformat()
    end = args.end or today

    print("=" * 72)
    print(f"Diagnóstico DÍA D operativo · {symbol}")
    print(f"D (as-of) = {dia_d} · fin V = {end} · API = {API}")
    print("=" * 72)

    health = http_json("GET", "/api/health")
    print(f"health: {health.get('status')}")

    inst = find_instrument(symbol)
    iid = inst["id"]
    print(f"instrument: {inst.get('symbol')} · {inst.get('name')} · {iid}")

    # TOP operativo actual (F-hoy)
    top_wrap = http_json("GET", f"/api/instruments/{iid}/strategy-top?timeframe=1d")
    top = top_wrap.get("data") if isinstance(top_wrap, dict) else None
    if isinstance(top, dict) and top.get("slots"):
        slots = sorted(top["slots"], key=lambda s: s.get("rank", 99))
        print("\nF-hoy (BD Finalistas):")
        for s in slots:
            print(
                f"  #{s.get('rank')} {s.get('label')} "
                f"type={s.get('strategyType')} id={str(s.get('strategyDefinitionId') or '')[:8]}…"
            )
    else:
        print("\nF-hoy: (sin TOP en BD)")

    ohlcv = ohlcv_probe(iid, dia_d, end)
    print("\nOHLCV probe D→hoy:")
    print(json.dumps(ohlcv, indent=2, ensure_ascii=False))

    rows: list[dict[str, Any]] = []
    print("\n--- Runs por preset ---")
    for preset, label in PRESETS:
        print(f"\n[{preset}] {label}")
        try:
            is_run = run_bt(
                instrument_id=iid,
                strategy_type=preset,
                date_from=None,
                date_to=dia_d,
                label=f"IS≤{dia_d}",
            )
            is_sum = summarize(is_run, "IS≤D")
            print(
                f"  IS≤D: bars={is_sum['bars']} trades={is_sum['trades']} "
                f"ret={is_sum['retPct']} dd={is_sum['ddPct']}"
            )

            oos_run = run_bt(
                instrument_id=iid,
                strategy_type=preset,
                date_from=dia_d,
                date_to=end,
                label=f"OOS {dia_d}→{end}",
            )
            oos_sum = summarize(oos_run, "OOS D→hoy")
            print(
                f"  OOS:  bars={oos_sum['bars']} trades={oos_sum['trades']} "
                f"ret={oos_sum['retPct']} dd={oos_sum['ddPct']} "
                f"first={oos_sum['firstTrade']} last={oos_sum['lastTrade']}"
            )
            notes = diagnose_row(is_sum, oos_sum)
            for n in notes:
                print(f"  !! {n}")
            rows.append(
                {
                    "preset": preset,
                    "label": label,
                    "is": is_sum,
                    "oos": oos_sum,
                    "notes": notes,
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL: {exc}")
            rows.append({"preset": preset, "label": label, "error": str(exc)})

    # Si hay F-hoy #1 con definitionId, también V con esa estrategia
    if isinstance(top, dict) and top.get("slots"):
        slot1 = sorted(top["slots"], key=lambda s: s.get("rank", 99))[0]
        sid = slot1.get("strategyDefinitionId")
        if sid:
            print(f"\n--- V con F-hoy #1 congelada ({slot1.get('label')}) ---")
            try:
                body = {
                    "instrumentId": iid,
                    "strategyDefinitionId": sid,
                    "timeframe": "1d",
                    "initialCash": 10_000,
                    "commissionBps": 5,
                    "slippageBps": 5,
                    "limit": 10_000,
                    "dateFrom": dia_d,
                    "dateTo": end,
                }
                wrap = http_json("POST", "/api/backtests/run", body)
                data = wrap.get("data") if isinstance(wrap, dict) else {}
                s = summarize(data if isinstance(data, dict) else {}, "F-hoy#1 OOS")
                print(
                    f"  OOS F-hoy#1: bars={s['bars']} trades={s['trades']} "
                    f"ret={s['retPct']} dd={s['ddPct']}"
                )
                rows.append({"preset": "F-hoy#1", "label": slot1.get("label"), "oos": s})
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL F-hoy#1: {exc}")

    # --- Cold vs warm (bug histórico Verify dateFrom=D) ---
    print("\n--- Cold (dateFrom=D) vs Warm (lookback 3y) · trades con ts≥D ---")
    lookback = (date.fromisoformat(dia_d) - timedelta(days=365 * 3)).isoformat()

    def oos_count(run: dict[str, Any]) -> tuple[int, float]:
        trades = run.get("trades") or []
        oos = [t for t in trades if str(t.get("timestamp", ""))[:10] >= dia_d]
        shares = 0.0
        for t in trades:
            if str(t.get("timestamp", ""))[:10] >= dia_d:
                break
            shares += float(t["quantity"]) if t["type"] == "buy" else -float(t["quantity"])
        return len(oos), shares

    warm_cases: list[tuple[str, dict[str, Any]]] = [
        ("sma_crossover", {"strategyType": "sma_crossover"}),
    ]
    if isinstance(top, dict) and top.get("slots"):
        for s in sorted(top["slots"], key=lambda x: x.get("rank", 99))[:2]:
            sid = s.get("strategyDefinitionId")
            if sid:
                warm_cases.append(
                    (f"F-hoy#{s.get('rank')} {s.get('label')}", {"strategyDefinitionId": sid})
                )

    cold_zero_warm_pos = 0
    for label, base in warm_cases:
        try:
            cold = run_bt(
                instrument_id=iid,
                strategy_type=base.get("strategyType") or "sma_crossover",
                date_from=dia_d,
                date_to=end,
                label="cold",
            )
            # Prefer definitionId when present
            if base.get("strategyDefinitionId"):
                body = {
                    "instrumentId": iid,
                    "strategyDefinitionId": base["strategyDefinitionId"],
                    "timeframe": "1d",
                    "initialCash": 10_000,
                    "limit": 10_000,
                    "dateFrom": dia_d,
                    "dateTo": end,
                }
                cold = (http_json("POST", "/api/backtests/run", body) or {}).get("data") or cold
                body_w = {**body, "dateFrom": lookback}
                warm = (http_json("POST", "/api/backtests/run", body_w) or {}).get("data") or {}
            else:
                warm = run_bt(
                    instrument_id=iid,
                    strategy_type=str(base["strategyType"]),
                    date_from=lookback,
                    date_to=end,
                    label="warm",
                )
            c_n, _ = oos_count(cold if isinstance(cold, dict) else {})
            w_n, w_pos = oos_count(warm if isinstance(warm, dict) else {})
            flag = ""
            if c_n == 0 and (w_n > 0 or w_pos > 0):
                cold_zero_warm_pos += 1
                flag = " ← BUG frío (0 ops) vs continuidad"
            print(
                f"  {label}: cold_OOS={c_n} warm_OOS={w_n} pos@D≈{w_pos:.0f}{flag}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: FAIL {exc}")

    # Resumen ejecutivo
    print("\n" + "=" * 72)
    print("RESUMEN")
    oos_zero = [
        r
        for r in rows
        if isinstance(r.get("oos"), dict) and (r["oos"].get("trades") or 0) == 0
    ]
    oos_ok = [
        r
        for r in rows
        if isinstance(r.get("oos"), dict) and (r["oos"].get("trades") or 0) > 0
    ]
    print(f"Presets OOS frío con trades: {len(oos_ok)} / {len([r for r in rows if 'oos' in r])}")
    print(f"Presets OOS frío a 0 trades: {len(oos_zero)}")
    if cold_zero_warm_pos:
        print(
            f"ROOT CAUSE: Verify en frío (dateFrom=D) → {cold_zero_warm_pos} caso(s) "
            "con 0 ops aunque la estrategia iba en posición / sí opera con lookback. "
            "Fix app: lookback 3y + slice D→hoy (dia-d-verify-continuity)."
        )
        print("=" * 72)
        return 0

    bars_oos = [
        r["oos"].get("bars")
        for r in rows
        if isinstance(r.get("oos"), dict) and r["oos"].get("bars") is not None
    ]
    if bars_oos and max(bars_oos) == 0:
        print("ROOT CAUSE probable: ventana D→hoy sin barras OHLCV (datos / dateTo).")
        return 2
    if ohlcv.get("ok") and (ohlcv.get("barsInWindow") or 0) == 0:
        print("ROOT CAUSE probable: OHLCV sin velas en [D, hoy].")
        return 2
    if len(oos_zero) == len([r for r in rows if "oos" in r]) and bars_oos and min(bars_oos) > 50:
        print(
            "ROOT CAUSE probable: hay barras pero NINGÚN preset cruzó en D→hoy "
            "(régimen / params)."
        )
        return 3
    if oos_ok:
        best = max(oos_ok, key=lambda r: r["oos"].get("trades") or 0)
        print(
            f"Mejor OOS en trades: {best.get('preset')} · "
            f"trades={best['oos'].get('trades')} ret={best['oos'].get('retPct')}"
        )
    print("=" * 72)
    return 0 if oos_ok else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        print(f"FAIL: {e}")
        raise SystemExit(1) from e
