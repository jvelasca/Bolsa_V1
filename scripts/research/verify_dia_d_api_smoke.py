#!/usr/bin/env python3
"""Optional live API smoke — DÍA D asOf + Evidence sesión C.

SKIP if API down unless OPERATIVA_API_REQUIRED=1 or DIA_D_API_REQUIRED=1.

Usage (repo root, API en :8000):
  python scripts/research/verify_dia_d_api_smoke.py
  OPERATIVA_API_REQUIRED=1 python scripts/research/verify_dia_d_api_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED = any(
    os.environ.get(k, "").strip().lower() in {"1", "true", "yes"}
    for k in ("OPERATIVA_API_REQUIRED", "DIA_D_API_REQUIRED")
)

# Past cut used for asOf contract (must not look-ahead).
AS_OF = os.environ.get("DIA_D_SMOKE_ASOF", "2024-06-28")


def _request(
    method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"API unreachable: {exc}") from exc


def _first_instrument_id(payload: Any) -> str | None:
    rows = payload if isinstance(payload, list) else (payload or {}).get("data")
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    return row.get("id") or row.get("instrumentId")


def main() -> int:
    print("=== verify_dia_d_api_smoke ===")
    print(f"API={API} required={REQUIRED} asOf={AS_OF}")
    try:
        status, health = _request("GET", "/api/health")
        if status != 200:
            raise RuntimeError(f"health HTTP {status}")
        print(f"OK health: {health if isinstance(health, dict) else status}")

        status, instruments = _request("GET", "/api/instruments")
        if status != 200:
            raise RuntimeError(f"instruments HTTP {status}")
        instrument_id = _first_instrument_id(instruments)
        if not instrument_id:
            print("SKIP: no instruments")
            return 0 if not REQUIRED else 1

        # FA asOf — must return 200 with asOf metadata or blocked/reconstructed pointInTime.
        status, fa_wrap = _request(
            "GET", f"/api/instruments/{instrument_id}/fundamentals?asOf={AS_OF}"
        )
        if status != 200:
            raise RuntimeError(f"fundamentals?asOf HTTP {status}")
        card = fa_wrap.get("data") if isinstance(fa_wrap, dict) else fa_wrap
        if not isinstance(card, dict):
            raise RuntimeError("FA card missing")
        meta = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
        as_of_date = card.get("asOfDate") or meta.get("asOfDate")
        pit = meta.get("pointInTime")
        print(
            f"OK FA asOf: ticker={card.get('ticker')} asOfDate={as_of_date} "
            f"pointInTime={pit}"
        )
        if as_of_date is None and pit is None:
            print(
                "WARN: FA asOf sin metadata (API antigua? reinicia api-python)"
            )

        status_c, comp = _request(
            "GET",
            f"/api/instruments/{instrument_id}/composite?horizon=swing&regime=neutral&asOf={AS_OF}",
        )
        if status_c == 404:
            print("WARN: composite?asOf 404 (API sin F3 asOf)")
        elif status_c != 200:
            raise RuntimeError(f"composite?asOf HTTP {status_c}")
        else:
            cdata = comp.get("data") if isinstance(comp, dict) else None
            if not isinstance(cdata, dict):
                raise RuntimeError("composite payload missing")
            cmeta = cdata.get("metadata") if isinstance(cdata.get("metadata"), dict) else {}
            print(
                f"OK composite asOf: display={cdata.get('scoreDisplay100')} "
                f"asOfDate={cdata.get('asOfDate')} pointInTime={cdata.get('pointInTime') or cmeta.get('pointInTime')}"
            )

        # Evidence sesión C — heuristic always (LLM optional).
        body = {
            "mode": "semi",
            "symbol": "ACS",
            "strategyLabel": "SMA smoke",
            "diaD": AS_OF,
            "endDate": "2024-12-31",
            "initialCash": 10_000,
            "auto": {
                "totalReturnPct": 8.0,
                "maxDrawdownPct": 6.0,
                "tradeCount": 4,
                "finalEquity": 10_800,
            },
            "gated": {
                "totalReturnPct": 5.0,
                "maxDrawdownPct": 5.0,
                "tradeCount": 2,
                "finalEquity": 10_500,
            },
            "gate": {"accepted": 2, "rejected": 2},
        }
        status_e, ev = _request("POST", "/api/ai/dia-d/session-evidence", body)
        if status_e == 404:
            print(
                "WARN: session-evidence 404 (API sin DÍA D Evidence — reinicia api-python)"
            )
        elif status_e != 200:
            raise RuntimeError(f"session-evidence HTTP {status_e}: {ev}")
        else:
            data = ev.get("data") if isinstance(ev, dict) else None
            if not isinstance(data, dict):
                raise RuntimeError("session-evidence data missing")
            payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
            paragraphs = payload.get("paragraphs")
            if not isinstance(paragraphs, list) or len(paragraphs) < 1:
                raise RuntimeError("session-evidence paragraphs missing")
            print(
                f"OK Evidence: engine={data.get('engine')} band={payload.get('band')} "
                f"paragraphs={len(paragraphs)}"
            )

        # CORE-R narración (si ruta desplegada).
        cr_body = {
            "listId": "smoke-list",
            "timeframe": "1d",
            "rows": [
                {
                    "instrumentId": "i1",
                    "symbol": "TEF",
                    "verdict": "review_lab",
                    "reason": "Demo/paper PnL -6.0% · revisar Lab / checklist",
                },
                {
                    "instrumentId": "i2",
                    "symbol": "SAN",
                    "verdict": "consider_replace",
                    "reason": "PBO OOS elevado (0.70)",
                },
            ],
        }
        status_cr, cr = _request("POST", "/api/ai/core-r/review-evidence", cr_body)
        if status_cr == 404:
            print(
                "WARN: CORE-R review-evidence 404 (reinicia API tras v1.3 narración)"
            )
        elif status_cr != 200:
            raise RuntimeError(f"core-r review-evidence HTTP {status_cr}: {cr}")
        else:
            cr_data = cr.get("data") if isinstance(cr, dict) else None
            if not isinstance(cr_data, dict):
                raise RuntimeError("core-r data missing")
            cr_payload = (
                cr_data.get("payload") if isinstance(cr_data.get("payload"), dict) else {}
            )
            cr_paras = cr_payload.get("paragraphs")
            if not isinstance(cr_paras, list) or len(cr_paras) < 1:
                raise RuntimeError("core-r paragraphs missing")
            print(
                f"OK CORE-R: engine={cr_data.get('engine')} "
                f"band={cr_payload.get('band')} paragraphs={len(cr_paras)}"
            )

        # Persist Evidence DÍA D → Fase 2 (optional route).
        persist_body = {
            "instrumentId": instrument_id,
            "symbol": "ACS",
            "mode": "semi",
            "strategyLabel": "SMA smoke",
            "diaD": AS_OF,
            "endDate": "2024-12-31",
            "engine": "heuristic",
            "evidence": {
                "schemaVersion": "dia_d_session_evidence_v1",
                "band": "mixed",
                "confidence": "MEDIUM",
                "claims": ["smoke"],
                "warnings": [],
                "metrics": {"returnPct": 5.0, "mode": "semi"},
                "paragraphs": ["p1", "p2", "p3"],
                "disclaimer": "smoke sandbox",
            },
        }
        status_p, persisted = _request(
            "POST", "/api/research/dia-d-session-evidence", persist_body
        )
        if status_p in {404, 405}:
            print(
                f"WARN: persist dia-d-session-evidence HTTP {status_p} "
                "(reinicia API tras Evidence archive)"
            )
        elif status_p != 200:
            raise RuntimeError(f"persist dia-d-session-evidence HTTP {status_p}: {persisted}")
        else:
            pdata = persisted.get("data") if isinstance(persisted, dict) else None
            if not isinstance(pdata, dict) or not pdata.get("id"):
                raise RuntimeError("persist dia-d-session-evidence missing id")
            if pdata.get("source") != "dia_d_session":
                raise RuntimeError(f"unexpected source {pdata.get('source')}")
            print(
                f"OK persist Evidence: id={pdata.get('id')} level={pdata.get('level')}"
            )

        print("PASS verify_dia_d_api_smoke")
        return 0
    except RuntimeError as exc:
        msg = str(exc)
        if "API unreachable" in msg and not REQUIRED:
            print(f"SKIP: {msg}")
            return 0
        print(f"FAIL: {msg}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
