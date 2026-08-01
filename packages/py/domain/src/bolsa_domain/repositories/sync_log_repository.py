from typing import Literal, Protocol


class SyncLogRepository(Protocol):
    async def create_log(
        self,
        instrument_id: str,
        *,
        provider: Literal["yahoo", "xtb"],
        status: Literal["success", "partial", "failed"],
        bars_added: int,
        error: str | None = None,
    ) -> None: ...
