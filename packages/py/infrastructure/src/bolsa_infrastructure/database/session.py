from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bolsa_infrastructure.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    url = settings.database_url
    if url is None:
        raise RuntimeError("database_url not configured")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_async_engine(url, pool_pre_ping=True)


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
