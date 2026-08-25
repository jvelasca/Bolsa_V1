"""Alembic environment (F3b) — Alembic como autoridad de esquema PostgreSQL (D2).

Uso (desde packages/py/infrastructure):
    $env:PYTHONIOENCODING="utf-8"
    uv run alembic upgrade head
    uv run alembic revision --autogenerate -m "desc"

El URL se resuelve en este orden:
  1. variable de entorno DATABASE_URL (si el prefijo no es el de psycopg se normaliza),
  2. config `sqlalchemy.url` del alembic.ini (default local docker-compose).
`target_metadata` = metadatos SQLAlchemy (`Base`) para `autogenerate`.

Cuando se invoca programáticamente con `config.attributes["connection"]` ya
abierta (via `bolsa_infrastructure.database.migrations.ensure_migrated`), se usa
esa conexión en lugar de crear engine propio.
"""

from __future__ import annotations

import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from bolsa_infrastructure.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolved_url() -> str:
    default = config.get_main_option("sqlalchemy.url")
    url = default or ""
    if "DATABASE_URL" in config.attributes:
        url = config.attributes["DATABASE_URL"]
    url = re.sub(r"^\s*postgresql(\+psycopg)?://", "postgresql+psycopg://", url)
    if "?" in url:
        url = url.split("?", 1)[0]
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_resolved_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    injected = config.attributes.get("connection")
    if injected is not None:
        context.configure(connection=injected, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    engine.url = engine.url.set(drivername="postgresql+psycopg")
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
