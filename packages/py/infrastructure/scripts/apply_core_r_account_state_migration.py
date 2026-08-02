"""Script ops: tabla core_r_account_state (Q3.4 CORE-R multi-dispositivo)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SQL_PATH = (
    REPO_ROOT
    / "packages"
    / "database"
    / "prisma"
    / "migrations"
    / "20260802230000_core_r_account_state"
    / "migration.sql"
)


def _load_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    env_path = REPO_ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("DATABASE_URL="):
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"DATABASE_URL no encontrado (buscado en {env_path})")


def main() -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("psycopg requerido: pip install 'psycopg[binary]'") from exc

    if not SQL_PATH.is_file():
        raise SystemExit(f"SQL no encontrado: {SQL_PATH}")

    raw = _load_database_url()
    dsn = raw.replace("postgresql+psycopg://", "postgresql://", 1)
    if "?" in dsn:
        dsn = dsn.split("?", 1)[0]
    sql = SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(sql)
        conn.commit()
    print(f"OK: applied {SQL_PATH.parent.name}")


if __name__ == "__main__":
    main()
    sys.exit(0)
