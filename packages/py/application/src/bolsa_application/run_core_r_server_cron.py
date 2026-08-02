"""Use case — CORE-R cron sobre todos los account blobs (Q3.4)."""

from __future__ import annotations

from typing import Any

from bolsa_application.core_r_server_tick import apply_server_tick
from bolsa_infrastructure.database.repositories.core_r_repository import SqlAlchemyCoreRRepository


class RunCoreRServerCron:
    def __init__(self, repository: SqlAlchemyCoreRRepository) -> None:
        self._repo = repository

    async def execute(self, *, force: bool = False) -> dict[str, Any]:
        states = await self._repo.list_all()
        results: list[dict[str, Any]] = []
        total_added = 0
        ticked = 0
        for state in states:
            blob = {
                "queue": state.queue,
                "reports": state.reports,
                "scheduler": state.scheduler,
            }
            new_blob, meta = apply_server_tick(blob, force=force)
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
            results.append({"accountId": state.account_id, **meta})
        return {
            "accounts": len(states),
            "ticked": ticked,
            "totalAdded": total_added,
            "results": results,
        }
