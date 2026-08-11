"""Migrations Alembic — aplica pendientes hasta ``head`` de forma idempotente (F3b).

F3b hace a **Alembic la única autoridad de esquema PostgreSQL** (D2) para el DDL
nuevo. ``ensure_migrated`` es la vía programática para llevar la BD a ``head``:
aplica las migraciones pendientes (controladas por la tabla ``alembic_version``)
y es idempotente por construcción.

Se invoca UNA vez al arrancar el proceso (lifespan), NUNCA en el path caliente de
una petición (resuelve P1.2: `ensure_migrated` destructivo/backfill por request).
"""

from __future__ import annotations

import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from bolsa_infrastructure.config import get_settings

_INFRA_ROOT = Path(__file__).resolve().parents[3]


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
