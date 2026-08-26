"""DEX-4 — ExitGate coordinator (ExitPermission + protect)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_application.evaluate_exit_plan import semi_exit_permission, semi_protect_permission
from bolsa_application.persist_position_from_exit import row_position_state
from bolsa_application.persist_position_from_protect import PersistPositionFromProtectInput


class ExitGateCoordinator:
    """P3 ExitPermission + OI-1/PH-1 protect (cero ledger)."""

    def __init__(
        self,
        *,
        position_from_exit: Any | None = None,
        position_from_protect: Any | None = None,
    ) -> None:
        self._position_from_exit = position_from_exit
        self._position_from_protect = position_from_protect

    async def semi_exit_permission(
        self,
        *,
        rec: Recommendation,
        intent: Any,
        price: float,
        account_id: str,
    ) -> Any | None:
        if self._position_from_exit is None:
            return None
        row = await self._position_from_exit.get_open(
            account_id, str(intent.instrument_id or rec.instrument_id)
        )
        if row is None:
            return None
        return semi_exit_permission(
            row_position_state(row),
            mark_price=price,
        )

    def protect_permission(
        self,
        state_blob: dict[str, Any] | None,
        *,
        suggested_stop: float,
    ) -> Any:
        return semi_protect_permission(state_blob, suggested_stop=suggested_stop)

    async def get_open_for_protect(
        self,
        *,
        account_id: str,
        instrument_id: str,
    ) -> Any | None:
        if self._position_from_protect is None:
            return None
        return await self._position_from_protect.get_open(account_id, instrument_id)

    async def persist_protect(
        self,
        *,
        account_id: str,
        instrument_id: str,
        suggested_stop: float,
        override_reason: str | None,
    ) -> Any | None:
        assert self._position_from_protect is not None
        return await self._position_from_protect.persist(
            PersistPositionFromProtectInput(
                account_id=account_id,
                instrument_id=instrument_id,
                suggested_stop=suggested_stop,
                override_reason=override_reason,
            )
        )

    @property
    def protect_configured(self) -> bool:
        return self._position_from_protect is not None
