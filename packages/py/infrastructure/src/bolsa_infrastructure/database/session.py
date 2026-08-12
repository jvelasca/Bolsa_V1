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
