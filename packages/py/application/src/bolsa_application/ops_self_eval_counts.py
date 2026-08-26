"""OE-1 — carga counts DB para ops self-eval (read-only)."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models.tables import (
    DecisionJournalEntryRow,
    DecisionSessionRow,
    LedgerEntryRow,
)


async def load_semi_account_counts(
    session: AsyncSession, *, account_id: str
) -> dict[str, int | float]:
    """Confirm / journal / buys / trade_like / cash MaxDD proxy para una cuenta."""

    confirm_q = await session.execute(
        select(func.count())
        .select_from(DecisionSessionRow)
        .where(
            DecisionSessionRow.kind == "confirm",
            DecisionSessionRow.account_id == account_id,
        )
    )
    confirm_seed = int(confirm_q.scalar_one() or 0)

    journal_q = await session.execute(
        select(func.count())
        .select_from(DecisionJournalEntryRow)
        .where(DecisionJournalEntryRow.account_id == account_id)
    )
    journal_seed = int(journal_q.scalar_one() or 0)

    buys_q = await session.execute(
        select(func.count())
        .select_from(LedgerEntryRow)
        .where(
            LedgerEntryRow.account_id == account_id,
            LedgerEntryRow.type.ilike("%buy%"),
        )
    )
    buys_seed = int(buys_q.scalar_one() or 0)

    trade_q = await session.execute(
        select(func.count())
        .select_from(LedgerEntryRow)
        .where(
            LedgerEntryRow.account_id == account_id,
            LedgerEntryRow.type.notin_(("deposit", "fee", "withdraw")),
        )
    )
    trade_like = int(trade_q.scalar_one() or 0)

    # Cash MaxDD proxy (misma idea que thaw snapshot).
    dd_sql = text(
        """
        WITH cash AS (
          SELECT executed_at, balance_after::float AS bal
          FROM ledger_entries
          WHERE account_id = :aid
          ORDER BY executed_at, created_at
        ),
        peaks AS (
          SELECT bal,
                 MAX(bal) OVER (
                   ORDER BY executed_at
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                 ) AS peak
          FROM cash
        )
        SELECT COALESCE(
          MAX(CASE WHEN peak > 0 THEN (peak - bal) / peak ELSE 0 END),
          0
        )
        FROM peaks
        """
    )
    dd_res = await session.execute(dd_sql, {"aid": account_id})
    cash_max_dd_frac = float(dd_res.scalar_one() or 0.0)

    return {
        "confirmSeed": confirm_seed,
        "journalSeed": journal_seed,
        "buysSeed": buys_seed,
        "tradeLike": trade_like,
        "cashMaxDdFrac": cash_max_dd_frac,
    }
