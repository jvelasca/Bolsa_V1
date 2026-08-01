"""TimescaleDB extension — tablas existentes vía Prisma (baseline sin recreate)."""

from alembic import op

revision = "001_timescaledb_extension"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
