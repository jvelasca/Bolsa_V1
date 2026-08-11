"""Vuelca el contrato OpenAPI de la API FastAPI a un fichero versionable.

Sin arrancar un servidor ni tocar la BD: construye la app con ``create_app()``
(la validación de migraciones corre en el *lifespan*, que NO se ejecuta aquí)
y serializa ``app.openapi()`` a ``apps/web/api/openapi.json``.

Uso (desde la raíz del repo, con el venv de ``apps/api-python``):

    uv run --project apps/api-python python apps/api-python/scripts/dump_openapi.py

El resultado es la fuente de verdad del contrato FE/BE (P1.5 / ADR-003): el FE
genera tipos TS con ``openapi-typescript`` a partir de este fichero. Se versiona
para que los cambios de contrato sean revisables en diff y se cuelga un check
de coherencia (que este fichero vuelva a generarse idéntico) en la fase cerrada.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    # bolsa_api es primera parte en el repo pero sin `py.typed` en el punto de
    # montaje edictable; mypy lo ve como instalado-sin-stubs. Es un script de
    # tooling offline (no forma parte del gate de la app), así que se ignora.
    from bolsa_api.main import create_app  # type: ignore[import-untyped]

    app = create_app()
    schema = app.openapi()

    repo_root = Path(__file__).resolve().parents[3]
    out_dir = repo_root / "apps" / "web" / "api"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "openapi.json"
    payload = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    n_schemas = len(schema.get("components", {}).get("schemas", {}))
    n_paths = len(schema.get("paths", {}))
    print(f"OpenAPI volcado → {out_path} ({n_paths} paths, {n_schemas} schemas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
