"""UNIQUE parcial en ledger_entries por (account_id, reference_type, reference_id, type) — Fase 3 (L-M3/M-5).

Cierra la ventana de concurrencia de la idempotencia:
- A-2 (deposit/withdraw ``external``): el guard ``find_cash_movement_by_reference``
  (ledger_repository.py:148-168) es account-agnostic y es la primera línea de
  defensa; este índice es el backstop por-cuenta para el mismo movimiento
  concurrente.
- A-1/M-7 (custodia ``custody-{year}``): única por cuenta/año, dedup time-only.

No rompe los trades con fees (``ExecuteTrade`` → ``append_trade`` + ``append_fee``),
que escriben el MISMO ``(account_id, reference_type="transaction",
reference_id=tx.id)`` y solo difieren en ``type`` (``"buy"/"sell"`` vs ``"fee"``)
— por eso ``type`` forma parte del único.

Por-cuenta (incluye ``account_id``) evita las colisiones globales de:
- custodia ``("custody","custody-YYYY")`` en DOS cuentas del mismo año, y
- migración ``("migration","initial-deposit")`` multi-cuenta.

Índice PARCIAL (``WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL``):
PostgreSQL trata los NULL como distintos en UNIQUE, y hay filas seed con references
``(None,None)`` (p. ej. test_daily_ops_report.py:35-36) que no deben romperse.

Sobre duplicados existentes: la migración FALLA (no dedup automático). Ajustar a
mano los ledger_entries duplicados reales es una decisión de dinero/verdad que no
puede hacerse a ciegas; el error es descriptivo y pide reconciliación manual.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "004_ledger_reference_unique"
down_revision = "003_prisma_schema_baseline"
branch_labels = None
depends_on = None

_INDEX_NAME = "uq_ledger_entries_account_reference"


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = (
        "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' "
        "AND indexname = :n"
    )
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _duplicated_rows(bind: sa.engine.Connection) -> list[tuple[str, str, str, str, int]]:
    sql = """
        SELECT account_id, reference_type, reference_id, type, count(*) AS n
        FROM ledger_entries
        WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL
        GROUP BY account_id, reference_type, reference_id, type
        HAVING count(*) > 1
        ORDER BY n DESC
        LIMIT 20
    """
    rows = list(bind.execute(sa.text(sql)).all())
    return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def upgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, _INDEX_NAME):
        return
    dups = _duplicated_rows(bind)
    if dups:
        sample = "; ".join(
            f"{r[0]}/{r[1]}/{r[2]}/{r[3]} x{r[4]}" for r in dups
        )
        raise RuntimeError(
            "ledger_entries tiene N filas duplicadas bajo "
            "(account_id, reference_type, reference_id, type): " + sample
            + "Reconcilia los duplicados a mano antes de aplicar el UNIQUE; "
            "no se eliminan datos automáticamente."
        )
    op.execute(
        f"CREATE UNIQUE INDEX {_INDEX_NAME} ON ledger_entries "
        "(account_id, reference_type, reference_id, type) "
        "WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(f'DROP INDEX IF EXISTS "{_INDEX_NAME}"')
