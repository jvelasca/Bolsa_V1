#!/usr/bin/env python3
"""Optional live API smoke for Fase 2 routes.

SKIP if API down unless FASE2_API_REQUIRED=1.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED = os.environ.get("FASE2_API_REQUIRED", "").strip() in {"1", "true", "TRUE", "yes"}


def _get(path: str) -> tuple[int, dict | list | None]:
    req = urllib.request.Request(f"{API}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body) if body else None
        return resp.status, data


def main() -> int:
    print("=== verify_fase2_api_smoke ===")
    print(f"API={API} required={REQUIRED}")
    try:
        status, _ = _get("/api/research/hypotheses?limit=1")
        if status != 200:
            raise RuntimeError(f"hypotheses list HTTP {status}")
        status, _ = _get("/api/research/evidence?limit=1")
        if status != 200:
            raise RuntimeError(f"evidence list HTTP {status}")
        status, _ = _get("/api/research/knowledge?limit=1")
        if status != 200:
            raise RuntimeError(f"knowledge list HTTP {status}")
        status, _ = _get("/api/research/tree/edges?limit=1")
        if status != 200:
            raise RuntimeError(f"tree edges list HTTP {status}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        msg = f"SKIP: API no contactable: {exc}"
        print(msg)
        if REQUIRED:
            print("FAIL: FASE2_API_REQUIRED=1")
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1

    print("OK: Fase 2 list endpoints reachable (hypotheses/evidence/knowledge/tree)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
