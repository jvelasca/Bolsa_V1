#!/usr/bin/env python3

"""Smoke live: stamps de frescura Finalistas en strategy-tops.



Comprueba que los TOP `active` de una lista tienen (o no) `coachFacts.freshness`

coherente. No re-ejecuta el embudo.



SKIP (exit 0) si la API no responde, salvo FRESHNESS_API_REQUIRED=1.



Usage (repo root, API en :8000):

  python scripts/research/verify_finalists_freshness_smoke.py

  python scripts/research/verify_finalists_freshness_smoke.py --list-id ibex35

  FRESHNESS_API_REQUIRED=1 python scripts/research/verify_finalists_freshness_smoke.py



Exit: 0 OK / skip · 1 fallo de contrato o API requerida caída.

"""



from __future__ import annotations



import argparse

import json

import os

import sys

import urllib.error

import urllib.request

from typing import Any



API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")

REQUIRED = os.environ.get("FRESHNESS_API_REQUIRED", "").strip() in {

    "1",

    "true",

    "TRUE",

    "yes",

}





def _get(path: str) -> tuple[int, Any]:

    req = urllib.request.Request(f"{API}{path}", method="GET")

    with urllib.request.urlopen(req, timeout=8) as resp:

        body = resp.read().decode("utf-8")

        return resp.status, json.loads(body) if body else None





def _get_optional(path: str) -> tuple[int, Any] | None:

    try:

        return _get(path)

    except urllib.error.URLError:

        return None

    except TimeoutError:

        return None





def main() -> int:

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(

        "--list-id",

        default="",

        help="Si se indica, solo instrumentos de esa lista (GET /api/lists/{id})",

    )

    parser.add_argument(

        "--timeframe",

        default="1d",

        help="TF del strategy-top (default 1d)",

    )

    parser.add_argument(

        "--limit",

        type=int,

        default=40,

        help="Máx. instrumentos a inspeccionar",

    )

    args = parser.parse_args()



    print("=== verify_finalists_freshness_smoke ===")

    print(f"API={API} required={REQUIRED} list={args.list_id or '(all sample)'} tf={args.timeframe}")



    health = _get_optional("/api/health")

    if health is None:

        msg = "API unreachable — skip smoke"

        if REQUIRED:

            print(f"FAIL: {msg} (FRESHNESS_API_REQUIRED=1)")

            return 1

        print(f"SKIP: {msg}")

        return 0



    instrument_ids: list[str] = []

    symbols: dict[str, str] = {}



    if args.list_id:

        status, list_body = _get(f"/api/lists/{args.list_id}")

        if status != 200 or not isinstance(list_body, dict):

            print(f"FAIL: list {args.list_id} HTTP {status}")

            return 1

        data = list_body.get("data") or list_body

        instrument_ids = list(data.get("instrumentIds") or [])[: args.limit]

        for inst in data.get("instruments") or []:

            if isinstance(inst, dict) and inst.get("id"):

                symbols[str(inst["id"])] = str(inst.get("symbol") or inst["id"][:8])

    else:

        status, inst_body = _get("/api/instruments")

        if status != 200 or not isinstance(inst_body, dict):

            print(f"FAIL: instruments HTTP {status}")

            return 1

        rows = inst_body.get("data") or []

        for row in rows[: args.limit]:

            if isinstance(row, dict) and row.get("id"):

                iid = str(row["id"])

                instrument_ids.append(iid)

                symbols[iid] = str(row.get("symbol") or iid[:8])



    if not instrument_ids:

        print("OK: no instruments to inspect")

        return 0



    active = 0

    with_stamp = 0

    without_stamp: list[str] = []

    bad_stamp: list[str] = []



    for iid in instrument_ids:

        status, body = _get(

            f"/api/instruments/{iid}/strategy-top?timeframe={args.timeframe}"

        )

        if status != 200 or not isinstance(body, dict):

            continue

        top = body.get("data")

        if not top or not isinstance(top, dict):

            continue

        if top.get("status") != "active":

            continue

        active += 1

        sym = symbols.get(iid) or top.get("symbol") or iid[:8]

        facts = top.get("coachFacts") or top.get("coach_facts") or {}

        freshness = facts.get("freshness") if isinstance(facts, dict) else None

        if not isinstance(freshness, dict):

            without_stamp.append(str(sym))

            continue

        fp = freshness.get("inputFingerprint") or freshness.get("input_fingerprint")

        at = freshness.get("lastSearchAt") or freshness.get("last_search_at")

        if not fp or not at:

            bad_stamp.append(str(sym))

            continue

        with_stamp += 1



    print(f"inspected={len(instrument_ids)} active_tops={active} with_stamp={with_stamp}")

    if without_stamp:

        print(f"active_without_stamp ({len(without_stamp)}): {', '.join(without_stamp[:20])}")

        print(

            "  note: primera pasada Lista AUTO tras el fix de frescura debería curarlos"

        )

    if bad_stamp:

        print(f"FAIL: stamp incompleto: {', '.join(bad_stamp)}")

        return 1



    print("OK: freshness smoke finished")

    return 0





if __name__ == "__main__":

    sys.exit(main())


