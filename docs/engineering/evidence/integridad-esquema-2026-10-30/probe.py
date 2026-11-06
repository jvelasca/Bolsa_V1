"""Sonda de evidencia — Expediente A (integridad de esquema).

Mide, sobre PostgreSQL real y con bases **desechables**, las dos rutas que exige el
dictamen y que el gate de CI debe cubrir:

1. **BD nueva** — ``migrate_to("head")`` con el árbol corregido: la baseline crea la
   columna del intervalo desde los metadatos y la ``060`` corregida crea el ``CHECK``
   (la ``062`` es un no-op).
2. **BD heredada defectuosa** — se lleva la base a ``061`` con el árbol **anterior**
   (``06653971``: la ``060`` con el ``CHECK`` dentro del bloque de la columna) para
   reproducir el drift REAL, y después se aplica el árbol corregido: la ``062`` crea el
   ``CHECK`` que faltaba.

Tras cada ruta se ejecutan las dos comprobaciones del gate:

* ``compare_metadata`` de Alembic (con la allowlist) debe quedar vacío;
* las acciones ``ON DELETE`` / ``ON UPDATE`` de TODAS las FK deben coincidir con
  ``Base.metadata`` (lo que Alembic NO compara).

Uso (desde la raíz del worktree, con ``DATABASE_URL`` apuntando al servidor):

    uv run python docs/engineering/evidence/integridad-esquema-2026-10-30/probe.py

No toca ``bolsa_v1`` ni ``bolsa_v1_integracion``: crea ``bolsa_ev_a_new`` y
``bolsa_ev_a_legacy`` y las deja para inspección (``--drop`` las elimina al final).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from bolsa_infrastructure.database.migrations import alembic_head, migrate_to
from bolsa_infrastructure.database.models import Base
from bolsa_infrastructure.database.schema_contract import alembic_include_object

REPO_ROOT = Path(__file__).resolve().parents[4]
INFRA = REPO_ROOT / "packages" / "py" / "infrastructure"
OLD_COMMIT = "06653971"
LEGACY_REVISION = "061_profile_delete_restrict"
CHECK_NAME = "sync_settings_provider_check_interval_check"
FK_NAME = "investment_accounts_active_profile_id_fkey"

_FK_ACTIONS = {"a": None, "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def admin_url() -> str:
    raw = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("postgresql") else None
    if raw is None:
        import os

        raw = os.environ["DATABASE_URL"]
    url = re.sub(r"^\s*postgresql(\+psycopg)?://", "postgresql://", raw.strip()).split("?", 1)[0]
    return url.rsplit("/", 1)[0] + "/postgres"


def db_url(name: str) -> str:
    base = admin_url().rsplit("/", 1)[0]
    return f"{base}/{name}"


def recreate(name: str) -> str:
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
        conn.execute(f'CREATE DATABASE "{name}"')
    return db_url(name)


def check_definition(url: str) -> str | None:
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = %s AND contype = 'c' AND conrelid = 'sync_settings'::regclass",
            (CHECK_NAME,),
        ).fetchone()
    return None if row is None else str(row[0])


def revision(url: str) -> str | None:
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    return None if row is None else str(row[0])


def fk_actions(url: str) -> tuple[str, str]:
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT confdeltype, confupdtype FROM pg_constraint "
            "WHERE conname = %s AND contype = 'f' AND conrelid = 'investment_accounts'::regclass",
            (FK_NAME,),
        ).fetchone()
    assert row is not None, f"falta la FK {FK_NAME}"
    return str(row[0]), str(row[1])


def _old_alembic_dir() -> Path:
    """Copia de ``alembic/`` del árbol ANTERIOR: 060 con el defecto y sin la 062."""
    tmp = Path(tempfile.mkdtemp(prefix="alembic_old_060_")) / "alembic"
    shutil.copytree(INFRA / "alembic", tmp)
    old_060 = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "show",
            f"{OLD_COMMIT}:packages/py/infrastructure/alembic/versions/060_provider_check_policy.py",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (tmp / "versions" / "060_provider_check_policy.py").write_text(old_060, encoding="utf-8")
    (tmp / "versions" / "062_sync_settings_check_backfill.py").unlink()
    return tmp


def migrate_with_old_tree(url: str, target: str) -> None:
    script_dir = _old_alembic_dir()
    cfg = Config()
    cfg.set_main_option("script_location", str(script_dir))
    cfg.attributes["configure_logger"] = False
    cfg.attributes["DATABASE_URL"] = re.sub(r"^postgresql://", "postgresql+psycopg://", url)
    engine = create_engine(cfg.attributes["DATABASE_URL"], poolclass=NullPool)
    try:
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, target)
    finally:
        engine.dispose()


def metadata_diff(url: str) -> list[Any]:
    engine = create_engine(re.sub(r"^postgresql://", "postgresql+psycopg://", url), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"include_object": alembic_include_object()}
            )
            return list(compare_metadata(context, Base.metadata))
    finally:
        engine.dispose()


def fk_diff(url: str) -> list[tuple[str, str, str, str]]:
    expected: dict[tuple[str, str], tuple[str | None, str | None]] = {}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            expected[(table.name, fk.parent.name)] = (fk.ondelete, fk.onupdate)

    with psycopg.connect(url, autocommit=True) as conn:
        rows = conn.execute(
            """
            SELECT rel.relname, att.attname, c.confdeltype, c.confupdtype
            FROM pg_constraint c
            JOIN pg_class rel ON rel.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = rel.relnamespace
            JOIN pg_attribute att ON att.attrelid = c.conrelid AND att.attnum = c.conkey[1]
            WHERE c.contype = 'f' AND n.nspname = 'public'
            ORDER BY rel.relname, att.attname
            """
        ).fetchall()

    problems: list[tuple[str, str, str, str]] = []
    for table, column, deltype, updtype in rows:
        key = (table, column)
        if key not in expected:
            if table == "custody_obligation":
                continue
            problems.append(("*", f"{table}.{column}", "FK en BD", "sin metadata"))
            continue
        exp_del, exp_upd = expected[key]
        if (exp_del or None) != _FK_ACTIONS.get(str(deltype), f"?{deltype}"):
            problems.append((table, column, f"ON DELETE metadata={exp_del!r}", f"BD={deltype!r}"))
        if (exp_upd or None) != _FK_ACTIONS.get(str(updtype), f"?{updtype}"):
            problems.append((table, column, f"ON UPDATE metadata={exp_upd!r}", f"BD={updtype!r}"))
    return problems


def report(label: str, url: str) -> None:
    print(f"\n=== {label} ===")
    print("alembic_version        :", revision(url))
    print("check definición        :", check_definition(url))
    print("FK confdeltype/updtype  :", fk_actions(url))
    print("compare_metadata        :", metadata_diff(url) or "SIN DIFERENCIAS")
    print("acciones de FK          :", fk_diff(url) or "SIN DIFERENCIAS")


def main() -> int:
    drop = "--drop" in sys.argv
    print("head del árbol corregido :", alembic_head())

    legacy = recreate("bolsa_ev_a_legacy")
    print("\n[1/2] BD heredada: árbol ANTERIOR ->", LEGACY_REVISION)
    migrate_with_old_tree(legacy, LEGACY_REVISION)
    print("revisión tras árbol viejo:", revision(legacy))
    print("CHECK tras árbol viejo   :", check_definition(legacy), "  <-- defecto reproducido")
    assert check_definition(legacy) is None, "el árbol anterior ya tenía el CHECK: sonda inválida"

    migrate_to("head", database_url=legacy)
    report("BD heredada tras aplicar el árbol corregido", legacy)

    fresh = recreate("bolsa_ev_a_new")
    print("\n[2/2] BD nueva: árbol corregido -> head")
    migrate_to("head", database_url=fresh)
    report("BD nueva tras el árbol corregido", fresh)

    if drop:
        with psycopg.connect(admin_url(), autocommit=True) as conn:
            for name in ("bolsa_ev_a_legacy", "bolsa_ev_a_new"):
                conn.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (name,),
                )
                conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
        print("\n[bases de la sonda eliminadas]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
