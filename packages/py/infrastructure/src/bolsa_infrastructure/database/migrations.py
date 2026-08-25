"""Migrations Alembic — aplica pendientes hasta ``head`` de forma idempotente (F3b).

F3b hace a **Alembic la única autoridad de esquema PostgreSQL** (D2) para el DDL
nuevo. ``ensure_migrated`` es la vía programática para llevar la BD a ``head``:
aplica las migraciones pendientes (controladas por la tabla ``alembic_version``)
y es idempotente por construcción.

``database_bootstrap`` (R-8A) serializa el arranque de BD entre los N procesos
(workers FastAPI + scheduler) con un advisory lock PostgreSQL, evitando las carreras
de bootstrap concurrente (P0-A).

Se invoca UNA vez al arrancar el proceso (lifespan), NUNCA en el path caliente de
una petición (resuelve P1.2: `ensure_migrated` destructivo/backfill por request).
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.account_migration import run_account_data_migration
from bolsa_infrastructure.database.user_bootstrap import ensure_bootstrap_user

_INFRA_ROOT = Path(__file__).resolve().parents[3]

# Clave global del advisory lock de bootstrap. DEBE ser idéntica en todos los
# procesos (API workers + scheduler) para que se serialicen entre sí (P0-A).
BOOTSTRAP_ADVISORY_LOCK_KEY = 774_104_253


def _alembic_config() -> Config:
    cfg = Config(str(_INFRA_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_INFRA_ROOT / "alembic"))
    return cfg


def _normalized_url(database_url: str) -> str:
    url = re.sub(r"^\s*postgresql(\+psycopg)?://", "postgresql+psycopg://", database_url)
    return url.split("?", 1)[0]


def ensure_migrated() -> bool:
    """Aplica migraciones Alembic pendientes hasta ``head`` y devuelve True si todo ok.

    Idempotente: si la BD ya está en ``head`` no re-aplica nada. Lanza RuntimeError
    (u otra excepción de la BD) si el upgrade falla.
    """
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no configurado; no puedo migrar")
    url = _normalized_url(settings.database_url)

    cfg = _alembic_config()
    cfg.attributes["DATABASE_URL"] = url
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)
    finally:
        engine.dispose()
    return True


async def database_bootstrap(
    *,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    lock_key: int = BOOTSTRAP_ADVISORY_LOCK_KEY,
) -> None:
    """Serializa el arranque de BD (migraciones + migración de datos) entre procesos.

    R-8A/P0-A: FastAPI con ``--workers N`` ejecuta su ``lifespan`` en cada worker, y el
    proceso ``scheduler_worker`` corre también la migración de datos; sin serialización
    las migraciones Alembic y los backfills se ejecutan N veces en paralelo (carreras en
    ``_ensure_default_account`` y en el `upgrade head`). Un advisory lock PostgreSQL con
    la MISMA ``lock_key`` en todos los procesos hace que solo uno entre al bootstrap y
    el resto espere a que libere (``pg_advisory_unlock``) o cierre la conexión.

    El lock es a nivel de *sesión* (no se revierte con ROLLBACK) y libera en ``finally``.
    Aunque ``ensure_migrated`` use su propio engine síncrono y la migración de datos una
    sesión async distinta, el lock global serializa el bloque completo entre tomadores de
    la misma clave.
    """
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT pg_advisory_lock(:key)"),
            {"key": lock_key},
        )
        try:
            await asyncio.to_thread(ensure_migrated)
            async with session_factory() as session:
                await run_account_data_migration(session)
                await ensure_bootstrap_user(session)
        finally:
            try:
                await conn.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": lock_key},
                )
            finally:
                await conn.close()
