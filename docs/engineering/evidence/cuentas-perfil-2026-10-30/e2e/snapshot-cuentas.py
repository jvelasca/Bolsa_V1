"""Snapshot read-only de cuentas y perfiles (para comparar antes/después del E2E).

Uso:  uv run --project apps/api-python python <ruta>de/este/f-ichero> > salida.json
Lee DATABASE_URL del .env de la raíz del worktree.
"""
from __future__ import annotations

import json
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


snapshot = {
    "account_count": len(accounts),
    "profile_count": len(profiles),
    "accounts": [{k: enc(v) for k, v in a.items()} for a in accounts],
    "profiles": [{k: enc(v) for k, v in p.items()} for p in profiles],
    "residue_like": [
        i
        for i in [a["id"] for a in accounts] + [p["id"] for p in profiles]
        if str(i).startswith("CU-") or "EVIDENCIA" in str(i)
    ],
}
print(json.dumps(snapshot, indent=2, ensure_ascii=False))
