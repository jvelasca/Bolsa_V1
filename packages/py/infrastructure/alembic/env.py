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

import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from bolsa_infrastructure.database.models import Base
from bolsa_infrastructure.database.schema_contract import alembic_include_object

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    # ``disable_existing_loggers=False``: cuando Alembic corre EN PROCESO (p.ej.
    # ``ensure_migrated`` durante el bootstrap de un worker o en tests PG), el default
    # de ``fileConfig`` (True) deshabilitaría los loggers de la app ya creados —
    # silenciando el logging del proceso. No queremos eso: las migraciones no deben
    # mutar el estado de logging de la aplicación.
    #
    # ``configure_logger``: ``disable_existing_loggers=False`` NO basta. ``fileConfig``
    # sigue aplicando ``[logger_root] level = WARN`` de ``alembic.ini`` al logger raíz
    # del proceso, así que todo ``logger.info`` posterior al bootstrap desaparece.
    # Medido en el tag ``v2.88.162-beta`` (job ``playwright (live AUTO daily chain)``):
    # el gate de disponibilidad esperaba ``Worker AUTO_OPS_JOB iniciado`` y nunca llegó,
    # aunque el worker estaba vivo (su siguiente ``logger.warning`` sí se vio). El
    # bootstrap en proceso marca ``configure_logger=False`` y el CLI de Alembic sigue
    # configurando el logging como siempre (atributo ausente ⇒ True).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _resolved_url() -> str:
    default = config.get_main_option("sqlalchemy.url")
    url = os.environ.get("DATABASE_URL") or default or ""
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
        # La allowlist es deuda declarada: ``alembic check`` y ``--autogenerate`` dejan
        # de proponer DROP de objetos históricos que siguen en uso. Una divergencia
        # nueva (no listada) sigue apareciendo.
        include_object=alembic_include_object(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    injected = config.attributes.get("connection")
    if injected is not None:
        context.configure(
            connection=injected,
            target_metadata=target_metadata,
            include_object=alembic_include_object(),
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    # ``_resolved_url()`` SE USA TAMBIÉN AQUÍ (no solo en modo offline): si la ruta
    # online se construyera desde ``alembic.ini`` a secas, la precedencia documentada
    # arriba (``DATABASE_URL`` > ``config.attributes["DATABASE_URL"]`` > ini) sería
    # mentira y ``alembic upgrade head`` migraría una BD DISTINTA de aquella sobre la
    # que consulta el proceso — con la BD de desarrollo como destino silencioso. El
    # resto de la sección se preserva tal cual para no perder otras opciones del ini.
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _resolved_url()
    engine = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=alembic_include_object(),
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
