"""Arnés compartido (PostgreSQL real) para la integración de ``061_profile_delete_restrict``.

Lo usan las dos verificaciones que exige el dictamen de Cuentas / Perfil inversor antes
de integrar:

* ``test_061_profile_delete_restrict_pg.py`` — ciclo de vida de la migración (base nueva,
  base heredada con perfiles asignados, downgrade) sobre una BD **scratch efímera**;
* ``test_investor_profile_delete_race_pg.py`` — carrera real asignación/borrado con dos
  transacciones PostgreSQL de orden determinista.

Por qué una BD scratch y no ``DATABASE_URL``: el ``downgrade`` de la 061 devuelve la FK a
``SET NULL``, es decir, reabre la desasignación silenciosa. Ejecutarlo contra la BD de
desarrollo mezclaría el estado bajo prueba con el que la API está usando. La scratch la
crea y la borra el propio test: nunca toca la base de ``DATABASE_URL`` más allá de
conectarse a ``postgres`` como administrador para ``CREATE/DROP DATABASE``.

Todo el módulo es **síncrono** (psycopg 3 + Alembic síncrono): evita el
``ProactorEventLoop`` de Windows, que psycopg async no soporta.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
_DOTENV = REPO_ROOT / ".env"

#: Nombre real del constraint que crean la baseline, el SQL de Prisma y la 061.
FK_NAME = "investment_accounts_active_profile_id_fkey"
_TABLE = "investment_accounts"

#: Tope de conexión: un host inalcanzable falla en segundos, no agota el SYN del sistema.
_CONNECT_TIMEOUT = 10


def load_env() -> None:
    """Carga ``.env`` sin pisar variables ya exportadas (convención del repo)."""
    if not _DOTENV.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv es dev-dependency
        return
    load_dotenv(_DOTENV, override=False)


def require_or_skip(exc: Exception, *, required_env: str, what: str) -> None:
    """Skip honesto sin PostgreSQL; FALLO duro si el job PG exige la certificación."""
    if os.environ.get(required_env) == "1":
        raise AssertionError(f"PostgreSQL requerido para {what} pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL ({what}) no disponible: {exc}")


def _split_url(raw: str) -> tuple[str, str]:
    """``(admin_url, dbname)`` a partir de una URL SQLAlchemy o psycopg."""
    url = re.sub(r"^\s*postgresql(\+psycopg)?://", "postgresql://", raw.strip())
    url = url.split("?", 1)[0]
    parts = urlsplit(url)
    dbname = parts.path.lstrip("/") or "bolsa_v1"
    admin = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    return admin, dbname


def database_url() -> str:
    """``DATABASE_URL`` normalizada a ``postgresql://`` (psycopg síncrono)."""
    load_env()
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        from bolsa_infrastructure.config import get_settings

        get_settings.cache_clear()
        raw = get_settings().database_url
    if not raw:
        raise RuntimeError("DATABASE_URL no configurado")
    return re.sub(r"^\s*postgresql(\+psycopg)?://", "postgresql://", raw.strip()).split("?", 1)[0]


def admin_url() -> str:
    """URL de mantenimiento (BD ``postgres``); ``SCRATCH_ADMIN_URL`` la sobrescribe."""
    override = os.environ.get("SCRATCH_ADMIN_URL")
    if override:
        return re.sub(r"^\s*postgresql(\+psycopg)?://", "postgresql://", override).split("?", 1)[0]
    admin, _ = _split_url(database_url())
    return admin


def _url_for_database(name: str) -> str:
    parts = urlsplit(database_url())
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", "", ""))


def _quote_ident(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"nombre de BD inválido: {name!r}")
    return f'"{name}"'


def _connect(url: str) -> Any:
    """Conexión psycopg síncrona en autocommit con tope de conexión."""
    import psycopg

    return psycopg.connect(url, autocommit=True, connect_timeout=_CONNECT_TIMEOUT)


@contextmanager
def scratch_database(prefix: str = "bolsa_profile_061") -> Iterator[str]:
    """Crea una BD vacía efímera y la borra al salir. Devuelve su URL."""
    name = f"{prefix}_{uuid4().hex[:10]}"
    ident = _quote_ident(name)
    with _connect(admin_url()) as conn:
        conn.execute(f"CREATE DATABASE {ident}")  # noqa: S608 — identificador validado
    try:
        yield _url_for_database(name)
    finally:
        with _connect(admin_url()) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (name,),
            )
            conn.execute(f"DROP DATABASE IF EXISTS {ident}")  # noqa: S608


def fk_delete_action(url: str) -> str | None:
    """``confdeltype`` de la FK (``r`` = RESTRICT, ``n`` = SET NULL, ``None`` = no existe)."""
    with _connect(url) as conn:
        row = conn.execute(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conname = %s AND contype = 'f' AND conrelid = %s::regclass",
            (FK_NAME, _TABLE),
        ).fetchone()
    return None if row is None else str(row[0])


def fk_constraint_oid(url: str) -> int | None:
    """``oid`` del constraint: cambia si la migración hizo DROP + CREATE."""
    with _connect(url) as conn:
        row = conn.execute(
            "SELECT oid FROM pg_constraint WHERE conname = %s AND conrelid = %s::regclass",
            (FK_NAME, _TABLE),
        ).fetchone()
    return None if row is None else int(row[0])


def current_revision(url: str) -> str | None:
    with _connect(url) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    return None if row is None else str(row[0])


def force_fk_to_set_null(url: str) -> None:
    """Devuelve la FK a la semántica heredada (``ON DELETE SET NULL``).

    Modela fielmente una base provisionada **antes** del endurecimiento: la 061 no mira
    ``alembic_version`` para decidir, solo ``pg_constraint.confdeltype``, así que basta
    con recrear el constraint con la acción vieja sobre el esquema en 060.
    """
    with _connect(url) as conn:
        conn.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT {FK_NAME}")
        conn.execute(
            f"ALTER TABLE {_TABLE} ADD CONSTRAINT {FK_NAME} "
            "FOREIGN KEY (active_profile_id) REFERENCES investor_profiles(id) "
            "ON DELETE SET NULL ON UPDATE CASCADE"
        )


def seed_assigned_profile(
    url: str,
    *,
    tag: str = "seed",
) -> tuple[str, str]:
    """Siembra un perfil y una cuenta que lo tiene asignado. Devuelve ``(account, profile)``."""
    account_id = f"acc_aud03_{tag}_{uuid4().hex[:10]}"
    profile_id = f"PROF-AUD03-{tag}-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    with _connect(url) as conn:
        conn.execute(
            "INSERT INTO investor_profiles (id, name, version, user_id, horizon, objectives, "
            "risk_tolerance, experience, suggested_policy_template_id, "
            "selected_policy_template_id, observed_json, updated_by, created_at, updated_at) "
            "VALUES (%s, %s, '1.0.0', NULL, 'swing', '[\"growth\"]'::jsonb, 'moderate', "
            "'intermediate', 'moderate', 'moderate', NULL, 'user', %s, %s)",
            (profile_id, f"AUD-03 {tag}", now, now),
        )
        conn.execute(
            "INSERT INTO investment_accounts (id, user_id, name, type, status, currency, "
            "base_currency, initial_deposit, leverage, is_default, created_at, updated_at) "
            "VALUES (%s, NULL, %s, 'simulated', 'active', 'EUR', 'EUR', 0, 1, false, %s, %s)",
            (account_id, f"AUD-03 {tag}", now, now),
        )
        conn.execute(
            f"UPDATE {_TABLE} SET active_profile_id = %s WHERE id = %s",
            (profile_id, account_id),
        )
    return account_id, profile_id


def assigned_profile(url: str, account_id: str) -> str | None:
    with _connect(url) as conn:
        row = conn.execute(
            f"SELECT active_profile_id FROM {_TABLE} WHERE id = %s",  # noqa: S608
            (account_id,),
        ).fetchone()
    if row is None:
        raise AssertionError(f"la cuenta {account_id} desapareció")
    return None if row[0] is None else str(row[0])


def counts(url: str) -> tuple[int, int]:
    """``(cuentas, perfiles)``: detecta borrados o desasignaciones colaterales."""
    with _connect(url) as conn:
        accounts = conn.execute("SELECT count(*) FROM investment_accounts").fetchone()
        profiles = conn.execute("SELECT count(*) FROM investor_profiles").fetchone()
    assert accounts is not None and profiles is not None
    return int(accounts[0]), int(profiles[0])


def orphan_accounts(url: str) -> list[tuple[str, str]]:
    """Cuentas que apuntan a un perfil inexistente (violación de integridad referencial)."""
    with _connect(url) as conn:
        rows = conn.execute(
            "SELECT a.id, a.active_profile_id FROM investment_accounts a "
            "LEFT JOIN investor_profiles p ON p.id = a.active_profile_id "
            "WHERE a.active_profile_id IS NOT NULL AND p.id IS NULL"
        ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


def account_ids_with_profile(url: str) -> dict[str, str | None]:
    """Mapa ``cuenta -> active_profile_id`` (incluye ``None``): foto para comparar."""
    with _connect(url) as conn:
        rows = conn.execute(
            "SELECT id, active_profile_id FROM investment_accounts ORDER BY id"
        ).fetchall()
    return {str(row[0]): (None if row[1] is None else str(row[1])) for row in rows}
