#!/usr/bin/env python3
"""Optional live API smoke for FA routes (card / chips).

SKIP if API down unless FA_API_REQUIRED=1.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED = os.environ.get("FA_API_REQUIRED", "").strip() in {"1", "true", "TRUE", "yes"}


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed


def main() -> int:
    print("=== verify_fa_api_smoke ===")
    print(f"API={API} required={REQUIRED}")
    try:
        status, instruments = _request("GET", "/api/instruments")
        if status != 200:
            raise RuntimeError(f"instruments HTTP {status}")
        rows = instruments if isinstance(instruments, list) else (instruments or {}).get("data")
        if not isinstance(rows, list) or not rows:
            print("SKIP: no instruments in API")
            return 0 if not REQUIRED else 1
        instrument_id = rows[0].get("id") or rows[0].get("instrumentId")
        if not instrument_id:
            raise RuntimeError("instrument row without id")

        status, card_wrap = _request("GET", f"/api/instruments/{instrument_id}/fundamentals")
        if status != 200:
            raise RuntimeError(f"fundamentals card HTTP {status}")
        card = card_wrap.get("data") if isinstance(card_wrap, dict) else card_wrap
        if not isinstance(card, dict):
            raise RuntimeError("card payload missing")
        for key in ("scoreDisplay100", "facts", "derived", "metadata", "pillars"):
            if key not in card:
                raise RuntimeError(f"card missing {key}")
        derived = card["derived"]
        if "piotroski" not in derived or "piotroskiMethod" not in derived:
            raise RuntimeError("card.derived missing piotroski fields")
        print(
            f"OK card {card.get('ticker')}: "
            f"score={card.get('scoreDisplay100')} "
            f"piotroski={derived.get('piotroski')} "
            f"conf={card['metadata'].get('confidence')}"
        )

        status, chips = _request(
            "POST",
            "/api/instruments/fundamentals/query",
            {"instrumentIds": [instrument_id]},
        )
        if status != 200:
            raise RuntimeError(f"fundamentals query HTTP {status}")
        chip_rows = chips.get("data") if isinstance(chips, dict) else chips
        if not isinstance(chip_rows, list) or not chip_rows:
            raise RuntimeError("chips empty")
        print(f"OK chips: {len(chip_rows)} row(s)")

        status_c, comp = _request(
            "GET",
            f"/api/instruments/{instrument_id}/composite?horizon=swing&regime=neutral",
        )
        if status_c == 404:
            print("WARN: composite endpoint 404 (reinicia API para F3)")
        elif status_c != 200:
            raise RuntimeError(f"composite HTTP {status_c}")
        else:
            cdata = comp.get("data") if isinstance(comp, dict) else None
            if not isinstance(cdata, dict) or not cdata.get("metadata", {}).get("paperDUnlocked"):
                raise RuntimeError("composite missing paperDUnlocked")
            print(
                f"OK composite: display={cdata.get('scoreDisplay100')} "
                f"ver={cdata.get('metadata', {}).get('scoreVersion')}"
            )

        status_sc, _sc = _request(
            "POST",
            "/api/instruments/fundamentals/screener",
            {
                "universe": {"instrumentIds": [instrument_id]},
                "fundamentalGate": {
                    "operator": "all",
                    "conditions": [{"metric": "trailingPe", "operator": "lte", "value": 100}],
                    "maxAgeDays": 365,
                },
                "refreshStale": False,
                "maxResults": 5,
            },
        )
        if status_sc == 404:
            print("WARN: FA screener 404 (reinicia API para F4)")
        elif status_sc != 200:
            raise RuntimeError(f"FA screener HTTP {status_sc}")
        else:
            print("OK FA screener endpoint")

        status_pd, pd_body = _request(
            "POST",
            "/api/paper-d/propose",
            {
                "universe": {"instrumentIds": [instrument_id]},
                "minScoreDisplay100": 0,
                "execute": False,
            },
        )
        if status_pd == 404:
            print("WARN: paper-d/propose 404 (reinicia API)")
        elif status_pd != 200:
            raise RuntimeError(f"paper-d propose HTTP {status_pd}")
        else:
            pdata = pd_body.get("data") if isinstance(pd_body, dict) else pd_body
            if isinstance(pdata, dict):
                if pdata.get("executeStatus") not in {None, "dry_run", "skipped", "blocked"}:
                    # dry_run esperado con execute=false
                    if pdata.get("executeRequested") is True:
                        raise RuntimeError("propose smoke must not request execute")
                print(
                    f"OK paper-d propose: status={pdata.get('executeStatus')} "
                    f"ver={pdata.get('proposeVersion')}"
                )
            else:
                print("OK paper-d propose endpoint")

        status_wk, _wk = _request(
            "POST",
            "/api/paper-d/weekly-run",
            {
                "universe": {"instrumentIds": [instrument_id]},
                "fundamentalGate": {
                    "operator": "all",
                    "conditions": [{"metric": "trailingPe", "operator": "lte", "value": 100}],
                    "maxAgeDays": 365,
                },
                "refreshStale": False,
                "execute": False,
                "persist": {"name": "FA smoke weekly (no persist id)"},
            },
        )
        if status_wk == 404:
            print("WARN: paper-d/weekly-run 404 (reinicia API)")
        elif status_wk in {200, 400, 422}:
            # 400 ok si el use-case exige lista; 422 validación
            print(f"OK paper-d weekly-run endpoint (HTTP {status_wk})")
        else:
            raise RuntimeError(f"paper-d weekly-run HTTP {status_wk}")

        # Derived keys (si el instrumento ya tiene fundamentals frescos)
        if isinstance(card, dict):
            der = card.get("derived") if isinstance(card.get("derived"), dict) else {}
            present = [k for k in ("roic", "beneishM", "waccMethod", "advUsd", "dcfScenarios") if der.get(k) is not None]
            print(f"OK card.derived keys present: {present or '(none - refresh Yahoo)'}")

        status, _filings = _request("GET", f"/api/instruments/{instrument_id}/filings")
        if status == 404:
            print("WARN: filings endpoint 404 (reinicia API para cargar F2b+)")
            if REQUIRED:
                print("FAIL: FA_API_REQUIRED=1")
                return 1
        elif status != 200:
            raise RuntimeError(f"filings list HTTP {status}")
        else:
            print("OK filings list endpoint")
            # sec-fetch existe (puede 400 en no-US; no fallar smoke)
            status_sec, _ = _request(
                "POST",
                f"/api/instruments/{instrument_id}/filings/sec-fetch?kind=10-K",
            )
            if status_sec in {200, 400, 502}:
                print(f"OK sec-fetch endpoint (HTTP {status_sec})")
            elif status_sec == 404:
                print("WARN: sec-fetch 404 (reinicia API para F2b+)")
            else:
                raise RuntimeError(f"sec-fetch HTTP {status_sec}")
            # ask endpoint existe (404 filing vacío ok vía body validation 422/400)
            status_ask, _ = _request(
                "POST",
                "/api/ai/fundamentals/filings/ask",
                body={
                    "instrumentId": instrument_id,
                    "filingId": "fil_smoke_missing",
                    "question": "smoke risk factors",
                },
            )
            if status_ask in {404, 400, 422}:
                print(f"OK filings/ask endpoint (HTTP {status_ask})")
            elif status_ask == 200:
                print("OK filings/ask endpoint")
            else:
                print(f"WARN: filings/ask HTTP {status_ask} (reinicia API para F2b++)")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        msg = f"SKIP: API no contactable: {exc}"
        print(msg)
        if REQUIRED:
            print("FAIL: FA_API_REQUIRED=1")
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1

    print("OK: FA API smoke")
    return 0


if __name__ == "__main__":
    sys.exit(main())
