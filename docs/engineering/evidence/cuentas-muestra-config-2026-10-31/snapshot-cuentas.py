"""Snapshot read-only de cuentas y perfiles (antes/después del E2E de /cuentas).

Uso:  uv run --project apps/api-python python <ruta>de/este-fichero > salida.json

Lee DATABASE_URL del .env de la raíz del repo. NO escribe nada: la comparación
byte a byte de ``db-before.json`` y ``db-after.json`` es la prueba de 0 residuos.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path.cwd()
while not (ROOT / ".env").exists() and ROOT.parent != ROOT:
    ROOT = ROOT.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        url = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
else:
    sys.exit("DATABASE_URL no encontrada")

if "?" in url:
    url = url.split("?", 1)[0]

if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(url)
with engine.connect() as conn:
    accounts = [
        dict(r._mapping)
        for r in conn.execute(
            text(
                "select id, name, type, status, is_default, active_profile_id, user_id "
                "from investment_accounts order by id"
            )
        )
    ]
    profiles = [
        dict(r._mapping)
        for r in conn.execute(
            text(
                "select id, name, user_id, "
                "coalesce(selected_policy_template_id, suggested_policy_template_id) as template "
                "from investor_profiles order by id"
            )
        )
    ]


def enc(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


#: Tablas realmente leídas. La igualdad byte a byte de before/after solo prueba
#: ausencia de residuos EN ESTAS TABLAS; no es una foto de toda la base.
TABLES = ("investment_accounts", "investor_profiles")


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # la procedencia nunca debe tumbar el snapshot
        return None


def _version() -> str | None:
    try:
        data = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        return data.get("version")
    except Exception:  # la versión nunca debe tumbar el snapshot
        return None


# Sin timestamps A PROPÓSITO: before y after deben poder compararse byte a byte.
provenance = {
    "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
    "head": _git("rev-parse", "HEAD"),
    "headShort": _git("rev-parse", "--short", "HEAD"),
    "version": _version(),
    "dirty": bool(_git("status", "--porcelain")),
}

snapshot = {
    "tables": list(TABLES),
    "provenance": provenance,
    "account_count": len(accounts),
    "profile_count": len(profiles),
    "accounts": [{k: enc(v) for k, v in a.items()} for a in accounts],
    "profiles": [{k: enc(v) for k, v in p.items()} for p in profiles],
    "residue_like": [
        i
        for i in [a["id"] for a in accounts] + [p["id"] for p in profiles]
        if str(i).startswith("CU-") or "EVIDENCIA" in str(i) or str(i).startswith("PROF-REV")
    ],
}
print(json.dumps(snapshot, indent=2, ensure_ascii=False))
