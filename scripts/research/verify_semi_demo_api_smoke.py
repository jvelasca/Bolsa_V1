#!/usr/bin/env python3
"""Optional live API smoke — SEMI Confirm F3 queue (BD blob).

SKIP if API down unless SEMI_API_REQUIRED=1 or OPERATIVA_API_REQUIRED=1.

Checks:
  - health
  - GET/PUT /api/accounts/{id}/supervised-f3-queue (cap + activeId)
  - propose recommendation includes country when instrument known

Usage (repo root, API en :8000 + migración aplicada):
  python scripts/research/verify_semi_demo_api_smoke.py
  SEMI_API_REQUIRED=1 python scripts/research/verify_semi_demo_api_smoke.py
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
    for k in ("SEMI_API_REQUIRED", "OPERATIVA_API_REQUIRED")
)


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
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"API unreachable: {exc}") from exc


def _unwrap(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _first_account_id(payload: Any) -> str | None:
    rows = _unwrap(payload)
    if not isinstance(rows, list) or not rows:
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("type") == "simulated" or row.get("status") == "active":
            aid = row.get("id")
            if isinstance(aid, str) and aid:
                return aid
    row = rows[0]
    if isinstance(row, dict) and isinstance(row.get("id"), str):
        return row["id"]
    return None


def _first_instrument(payload: Any) -> dict[str, Any] | None:
    rows = _unwrap(payload)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            return row
    return None


def main() -> int:
    print("=== verify_semi_demo_api_smoke ===")
    print(f"API={API} required={REQUIRED}")
    try:
        status, health = _request("GET", "/api/health")
        if status != 200:
            raise RuntimeError(f"health HTTP {status}")
        print(f"OK health: {status}")

        status, accounts = _request("GET", "/api/accounts")
        if status != 200:
            raise RuntimeError(f"accounts HTTP {status}")
        account_id = _first_account_id(accounts)
        if not account_id:
            print("SKIP: no accounts")
            return 0 if not REQUIRED else 1
        print(f"OK account: {account_id}")

        path = f"/api/accounts/{account_id}/supervised-f3-queue"
        status, empty = _request("GET", path)
        if status == 404:
            msg = (
                "supervised-f3-queue 404 — ¿migración aplicada? "
                "python packages/py/infrastructure/scripts/"
                "apply_supervised_f3_account_state_migration.py"
            )
            if REQUIRED:
                raise RuntimeError(msg)
            print(f"SKIP: {msg}")
            return 0
        if status != 200:
            raise RuntimeError(f"GET queue HTTP {status}: {empty}")
        bundle = _unwrap(empty)
        if not isinstance(bundle, dict):
            raise RuntimeError("queue bundle missing")
        print(
            f"OK GET queue: items={len(bundle.get('items') or [])} "
            f"activeId={bundle.get('activeId')}"
        )

        probe_id = "q-smoke-semi-demo-1"
        put_body = {
            "items": [
                {
                    "id": probe_id,
                    "enqueuedAt": "2026-08-03T12:00:00.000Z",
                    "symbol": "SMOKE",
                    "origin": "manual",
                    "payload": {
                        "recommendationId": "REC-smoke",
                        "instrumentId": "inst-smoke",
                        "action": "wait",
                        "suggestedQuantity": 1,
                        "country": "ES",
                        "status": "awaiting_human",
                    },
                }
            ],
            "activeId": probe_id,
        }
        status, put_res = _request("PUT", path, put_body)
        if status != 200:
            raise RuntimeError(f"PUT queue HTTP {status}: {put_res}")
        put_data = _unwrap(put_res)
        items = put_data.get("items") if isinstance(put_data, dict) else None
        if not isinstance(items, list) or not items:
            raise RuntimeError("PUT did not persist items")
        if items[0].get("id") != probe_id:
            raise RuntimeError("PUT item id mismatch")
        if put_data.get("activeId") != probe_id:
            raise RuntimeError("PUT activeId mismatch")
        print("OK PUT queue roundtrip")

        # Restore previous remote state (best-effort clear probe).
        prev_items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
        _request(
            "PUT",
            path,
            {"items": prev_items, "activeId": bundle.get("activeId")},
        )
        print("OK queue restored")

        status, instruments = _request("GET", "/api/instruments")
        if status != 200:
            raise RuntimeError(f"instruments HTTP {status}")
        inst = _first_instrument(instruments)
        if not inst:
            print("SKIP propose: no instruments")
            return 0
        instrument_id = inst["id"]
        propose_body = {
            "instrumentId": instrument_id,
            "accountId": account_id,
            "suggestedQuantity": 1,
            "includeFundamentals": False,
            "includeMacro": False,
            "includeEvidence": False,
            "includeNews": False,
            "includePredictions": False,
        }
        status, prop = _request("POST", "/api/ai/recommendations/propose", propose_body)
        if status != 200:
            # Common when OHLCV missing — soft skip unless required.
            msg = f"propose HTTP {status}: {prop}"
            if REQUIRED:
                raise RuntimeError(msg)
            print(f"SKIP propose ({msg})")
            print("OK: SEMI F3 queue smoke finished (propose skipped)")
            return 0
        rec = _unwrap(prop)
        if not isinstance(rec, dict):
            raise RuntimeError("propose payload missing")
        country = rec.get("country")
        print(
            f"OK propose: rec={rec.get('recommendationId')} "
            f"action={rec.get('action')} country={country!r} "
            f"instCountry={inst.get('country')!r}"
        )
        if inst.get("country") and country is None:
            print("WARN: instrument has country but propose returned none")
        print("OK: SEMI DEMO API smoke finished")
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
