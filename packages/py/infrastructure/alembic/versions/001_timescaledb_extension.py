"""TimescaleDB extension — baseline (Prisma) sin recreo de tablas.

La extensión TimescaleDB es OPCIONAL en el despliegue real (el docker-compose usa
``postgres:16-alpine`` plano, sin la extensión). Esta migración baseline la
habilita si está disponible en el servidor y NO falla si no lo está, para que la
cadena Alembic (autoridad D2/F3b) sea ejecutable en el entorno real sin romper el
``upgrade head``.
"""

from __future__ import annotations

from sqlalchemy import text

from alembic import op

revision = "001_timescaledb_extension"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    available = conn.scalar(
        text(
            "SELECT count(*) FROM pg_available_extensions "
            "WHERE name = 'timescaledb'"
        )
    )
    if available:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP EXTENSION IF EXISTS timescaledb CASCADE"))
