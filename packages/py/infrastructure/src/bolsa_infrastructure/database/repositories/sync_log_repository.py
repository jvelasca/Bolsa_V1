from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import DataSyncLogRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemySyncLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_log(
        self,
        instrument_id: str,
        *,
        provider: Literal["yahoo", "xtb"],
        status: Literal["success", "partial", "failed"],
        bars_added: int,
        error: str | None = None,
    ) -> None:
        self._session.add(
            DataSyncLogRow(
                id=new_id(),
                instrument_id=instrument_id,
                provider=provider,
                status=status,
                bars_added=bars_added,
                error=error,
                synced_at=datetime.now(UTC),
            ),
        )
        await self._session.flush()
