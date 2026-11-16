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

    # R6 — experimento TOP DÍA D: solo si el build desplegado ya trae la ruta.
    # Un 404 significa servidor anterior (no es un fallo del contrato): se avisa.
    status, payload = _probe_dia_d()
    if status == 404:
        print("SKIP: servidor sin /api/research/dia-d-experiment-top (build anterior)")
    elif status != 200:
        print(f"FAIL: dia-d-experiment-top HTTP {status}")
        return 1
    elif not isinstance(payload, dict) or "data" not in payload:
        print(f"FAIL: dia-d-experiment-top sin clave `data`: {payload!r}")
        return 1
    else:
        present = "objeto" if payload["data"] is not None else "null (hueco declarado)"
        print(f"OK: dia-d-experiment-top data = {present}")
    return 0


def _probe_dia_d() -> tuple[int, dict | list | None]:
    """Sondea la ruta DÍA D con un instrumento que no existe → 200 con ``data: null``."""
    path = (
        "/api/research/dia-d-experiment-top"
        "?instrumentId=00000000-0000-0000-0000-000000000000"
        "&timeframe=1d&asOfDiaD=2024-01-02"
    )
    try:
        return _get(path)
    except urllib.error.HTTPError as exc:
        return exc.code, None


if __name__ == "__main__":
    sys.exit(main())
