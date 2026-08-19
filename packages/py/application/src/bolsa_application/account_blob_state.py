"""Use-cases de estado por cuenta (blobs JSON): CoreR, SupervisedF3, Mandates.

Encapsulan la sanitización + persistencia para que las rutas FastAPI queden
delgadas (P1.9 API thin). La BD es la fuente de verdad; cliente = cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_infrastructure.database.repositories.core_r_repository import (
    CoreRAccountStateRecord,
    SqlAlchemyCoreRRepository,
)
from bolsa_infrastructure.database.repositories.mandate_repository import (
    MandateTenureRecord,
    MandateTradeLinkRecord,
    SqlAlchemyMandateRepository,
)
from bolsa_infrastructure.database.repositories.supervised_f3_repository import (
    SqlAlchemySupervisedF3Repository,
    SupervisedF3AccountStateRecord,
)


class GetAccountCoreRState:
    """Lee el blob CoreR de una cuenta."""

    def __init__(self, repo: SqlAlchemyCoreRRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: str) -> CoreRAccountStateRecord | None:
        return await self._repo.get(account_id)


class SyncAccountCoreRState:
    """Persiste el blob CoreR recibido del cliente con sanitización."""

    def __init__(self, repo: SqlAlchemyCoreRRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        account_id: str,
        *,
        queue: list[dict[str, Any]],
        reports: dict[str, Any],
        scheduler: dict[str, Any],
    ) -> CoreRAccountStateRecord:
        sanitized_queue = [q for q in queue if isinstance(q, dict)][:40]
        sanitized_reports = reports if isinstance(reports, dict) else {}
        sanitized_scheduler = scheduler if isinstance(scheduler, dict) else {}
        return await self._repo.upsert(
            account_id,
            queue=sanitized_queue,
            reports=sanitized_reports,
            scheduler=sanitized_scheduler,
        )


class GetAccountSupervisedF3State:
    """Lee el blob SupervisedF3 de una cuenta."""

    def __init__(self, repo: SqlAlchemySupervisedF3Repository) -> None:
        self._repo = repo

    async def execute(self, account_id: str) -> SupervisedF3AccountStateRecord | None:
        return await self._repo.get(account_id)


class SyncAccountSupervisedF3State:
    """Persiste el blob SupervisedF3 del cliente con sanitización del active_id."""

    def __init__(self, repo: SqlAlchemySupervisedF3Repository) -> None:
        self._repo = repo

    async def execute(
        self,
        account_id: str,
        *,
        items: list[dict[str, Any]],
        active_id: str | None,
    ) -> SupervisedF3AccountStateRecord:
        sanitized_items = [q for q in items if isinstance(q, dict)][:40]
        sanitized_active = active_id if isinstance(active_id, str) else None
        if sanitized_active and not any(i.get("id") == sanitized_active for i in sanitized_items):
            sanitized_active = sanitized_items[0].get("id") if sanitized_items else None
            if not isinstance(sanitized_active, str):
                sanitized_active = None
        return await self._repo.upsert(
            account_id,
            queue=sanitized_items,
            active_id=sanitized_active,
        )


@dataclass(frozen=True, slots=True)
class MandateBundle:
    tenures: list[MandateTenureRecord]
    links: list[MandateTradeLinkRecord]


class GetAccountMandates:
    """Lista los mandatos operativos de una cuenta."""

    def __init__(self, repo: SqlAlchemyMandateRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: str, *, instrument_id: str | None = None) -> MandateBundle:
        return MandateBundle(
            tenures=await self._repo.list_tenures(account_id, instrument_id=instrument_id),
            links=await self._repo.list_links(account_id, instrument_id=instrument_id),
        )


class SyncAccountMandates:
    """Reemplaza los mandatos de una cuenta con el payload del cliente."""

    def __init__(self, repo: SqlAlchemyMandateRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        account_id: str,
        *,
        tenures: list[dict[str, Any]],
        links: list[dict[str, Any]],
    ) -> MandateBundle:
        tenures_out, links_out = await self._repo.sync_account(account_id, tenures, links)
        return MandateBundle(tenures=tenures_out, links=links_out)
