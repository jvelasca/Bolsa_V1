"""Lectura de solo lectura del estado de la cuenta tras «Quitar perfil» (cierre del E2E).

Uso:  uv run python db-active-profile.py <accountId> <profileId>

Comprueba, directamente en PostgreSQL, que la desasignación desde la UI dejó
``active_profile_id = NULL`` (no el perfil por defecto) y que el perfil sigue existiendo
(no se borró como efecto colateral). La salida es JSON y se guarda como
``db-active-profile-null.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def database_url() -> str:
    root = Path(__file__).resolve()
    while root != root.parent and not (root / ".env").exists():
        root = root.parent
    env = (root / ".env").read_text(encoding="utf-8")
    for line in env.splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    else:
        sys.exit("DATABASE_URL no encontrada")
    url = url.split("?", 1)[0]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("uso: db-active-profile.py <accountId> <profileId>")
    account_id, profile_id = sys.argv[1], sys.argv[2]
    engine = create_engine(database_url())
    with engine.connect() as conn:
        account = conn.execute(
            text(
                "select id, name, status, active_profile_id from investment_accounts "
                "where id = :id"
            ),
            {"id": account_id},
        ).mappings().one_or_none()
        profile = conn.execute(
            text("select id, name from investor_profiles where id = :id"),
            {"id": profile_id},
        ).mappings().one_or_none()
    payload = {
        "accountId": account_id,
        "profileId": profile_id,
        "account": None if account is None else dict(account),
        "profile": None if profile is None else dict(profile),
        "active_profile_id_is_null": account is not None and account["active_profile_id"] is None,
        "profile_still_exists": profile is not None,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    ok = payload["active_profile_id_is_null"] and payload["profile_still_exists"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
