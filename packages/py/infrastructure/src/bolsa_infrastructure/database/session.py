from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bolsa_infrastructure.config import Settings


def create_engine(settings: Settings, *, connect_timeout: int | None = None) -> AsyncEngine:
    url = settings.database_url
    if url is None:
        raise RuntimeError("database_url not configured")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    timeout = settings.db_connect_timeout_seconds if connect_timeout is None else connect_timeout
    connect_args: dict[str, Any] = {}
    # Tope de conexión. Sin él, un host inalcanzable agota el SYN del sistema (~130 s en
    # Windows cuando el puerto cae en un rango reservado, porque no llega ni un
    # ECONNREFUSED): el arranque, /health y /readiness se quedan COLGADOS en vez de fallar
    # rápido. `connect_timeout` es el nombre que acepta psycopg; 0/negativo = sin tope.
    if timeout > 0 and url.startswith("postgresql+psycopg://"):
        connect_args["connect_timeout"] = timeout
    return create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def check_database(engine: AsyncEngine) -> tuple[bool, str]:
    # El mensaje de error NO debe filtrar detalles internos de conexión (URL, host,
    # port, credenciales) en un endpoint público /api/health (P2.5). En fallo se
    # devuelve un mensaje genérico; el origen real queda en logs.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "PostgreSQL conectado"
    except Exception:  # noqa: BLE001 — health check (detalle redactado, ver P2.5)
        return False, "PostgreSQL inaccesible"


async def read_db_schema_current(engine: AsyncEngine) -> tuple[str | None, str]:
    """Revisión Alembic actual de la BD conectada (field `alembic_version`).

    Readiness schema-aware (V2.15 C2, hallazgo V2.15-03 del auditor): además de
    conectar, un backend financiero debe comprobar que el esquema ejecutado
    coincide con el head esperado por el código. Este helper devuelve
    ``(current, status)``:

      - ``(rev, "ok")``           la BD responde y ``alembic_version`` reporta ``rev``.
      - ``(None, "unmigrated")``  la BD responde pero el esquema no está migrado
                                  (tabla ausente / sin fila): NO listo contra el head.
      - ``(None, "error")``       la BD no responde (detalle redactado, ver P2.5).

    Ningún mensaje filtra host/URL/credenciales ni el detalle crudo de la excepción.
    """
    try:
        async with engine.connect() as conn:
            row = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        if row:
            return str(row).strip() or None, "ok"
        return None, "unmigrated"
    except Exception:  # noqa: BLE001
        # Distinguir "BD caída" de "BD arriba pero sin esquema migrado" con una 2.ª
        # sonda de conectividad (así las mensajes de readiness son precisos y seguros).
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return None, "unmigrated"
        except Exception:  # noqa: BLE001
            return None, "error"
