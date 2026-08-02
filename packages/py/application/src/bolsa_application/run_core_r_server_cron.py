"""Use case — CORE-R cron sobre todos los account blobs (Q3.4 / v1.11 PnL)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_application.accounts import ListAccountSummaries
from bolsa_application.core_r_server_tick import apply_server_tick, scheduler_due
from bolsa_application.fetch_core_r_pnl_extra_rows import fetch_core_r_pnl_extra_rows
from bolsa_application.lists import GetInstrumentList
from bolsa_infrastructure.database.repositories.account_repository import SqlAlchemyAccountRepository
from bolsa_infrastructure.database.repositories.core_r_repository import SqlAlchemyCoreRRepository
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    SqlAlchemyInstrumentStrategyTopRepository,
)
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import SqlAlchemyPortfolioRepository


class RunCoreRServerCron:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SqlAlchemyCoreRRepository(session)

    async def execute(self, *, force: bool = False, include_pnl: bool = True) -> dict[str, Any]:
        states = await self._repo.list_all()
        results: list[dict[str, Any]] = []
        total_added = 0
        ticked = 0
        pnl_extras_cache: dict[str, list[dict[str, Any]]] = {}

        get_list = GetInstrumentList(SqlAlchemyListRepository(self._session))
        list_summaries = ListAccountSummaries(
            SqlAlchemyAccountRepository(self._session),
            SqlAlchemyPortfolioRepository(self._session),
        )
        top_repo = SqlAlchemyInstrumentStrategyTopRepository(self._session)

        for state in states:
            scheduler = state.scheduler if isinstance(state.scheduler, dict) else {}
            list_id_raw = scheduler.get("listId")
            list_id = list_id_raw.strip() if isinstance(list_id_raw, str) else ""

            if not scheduler.get("enabled") and not force:
                results.append(
                    {
                        "accountId": state.account_id,
                        "skipped": True,
                        "added": 0,
                        "listId": list_id,
                        "reason": "disabled",
                    }
                )
                continue
            if not list_id:
                results.append(
                    {
                        "accountId": state.account_id,
                        "skipped": True,
                        "added": 0,
                        "listId": "",
                        "reason": "no_list",
                    }
                )
                continue
            if not force and not scheduler_due(scheduler):
                results.append(
                    {
                        "accountId": state.account_id,
                        "skipped": True,
                        "added": 0,
                        "listId": list_id,
                        "reason": "not_due",
                    }
                )
                continue

            extras: list[dict[str, Any]] = []
            if include_pnl:
                if list_id not in pnl_extras_cache:
                    pnl_extras_cache[list_id] = await fetch_core_r_pnl_extra_rows(
                        list_id=list_id,
                        get_list=get_list,
                        list_summaries=list_summaries,
                        top_repo=top_repo,
                    )
                extras = pnl_extras_cache[list_id]

            blob = {
                "queue": state.queue,
                "reports": state.reports,
                "scheduler": state.scheduler,
            }
            new_blob, meta = apply_server_tick(blob, force=force, extra_rows=extras)
            if meta.get("skipped"):
                results.append({"accountId": state.account_id, **meta})
                continue
            await self._repo.upsert(
                state.account_id,
                queue=list(new_blob["queue"]),
                reports=dict(new_blob["reports"]),
                scheduler=dict(new_blob["scheduler"]),
            )
            added = int(meta.get("added") or 0)
            total_added += added
            ticked += 1
            results.append(
                {
                    "accountId": state.account_id,
                    **meta,
                    "pnlExtras": len(extras),
                }
            )
        return {
            "accounts": len(states),
            "ticked": ticked,
            "totalAdded": total_added,
            "results": results,
        }
