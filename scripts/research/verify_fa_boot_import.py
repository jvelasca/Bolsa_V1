#!/usr/bin/env python3
"""Import API + comprueba rutas OpenAPI FA (usado por verify_fa_boot.mjs)."""

from __future__ import annotations

from bolsa_api.main import create_app

NEED = {
    "/api/health",
    "/api/paper-d/propose",
    "/api/paper-d/weekly-run",
    "/api/instruments/fundamentals/screener",
}


def main() -> int:
    app = create_app()
    paths = set(app.openapi()["paths"])
    missing = sorted(NEED - paths)
    if missing:
        print(f"FAIL missing routes: {missing}")
        return 1
    print(f"OK api import + FA openapi routes {len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
