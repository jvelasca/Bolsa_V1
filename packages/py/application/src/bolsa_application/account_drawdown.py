"""F4 — telemetría de equity para circuit breakers daily/weekly/max."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_key(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _week_key(dt: datetime) -> str:
    iso = dt.astimezone(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@dataclass(frozen=True, slots=True)
class AccountDrawdowns:
    daily_pct: float | None
    weekly_pct: float | None
    max_pct: float | None
    day_open_equity: float | None
    week_open_equity: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dailyPct": self.daily_pct,
            "weeklyPct": self.weekly_pct,
            "maxPct": self.max_pct,
            "dayOpenEquity": self.day_open_equity,
            "weekOpenEquity": self.week_open_equity,
        }


def _dd_pct(reference: float, current: float) -> float:
    if reference <= 0:
        return 0.0
    return max(0.0, (reference - current) / reference * 100.0)


class EquityMarkBook:
    """
    Marcas de apertura día/semana por cuenta (proceso + opcional settings_json).
    Al primer equity del día/semana se fija la referencia; DD = caída desde esa marca.
    """

    def __init__(self) -> None:
        self._by_account: dict[str, dict[str, Any]] = {}

    def load_from_settings(self, account_id: str, settings: dict[str, Any] | None) -> None:
        if not settings:
            return
        marks = settings.get("equityMarks")
        if isinstance(marks, dict):
            self._by_account[account_id] = dict(marks)

    def export_settings_fragment(self, account_id: str) -> dict[str, Any]:
        return {"equityMarks": dict(self._by_account.get(account_id) or {})}

    def update(
        self,
        account_id: str,
        equity: float,
        *,
        initial_deposit: float | None = None,
        now: datetime | None = None,
    ) -> AccountDrawdowns:
        now_dt = now or _utc_now()
        day = _day_key(now_dt)
        week = _week_key(now_dt)
        state = self._by_account.setdefault(account_id, {})

        if state.get("dayKey") != day or state.get("dayOpen") is None:
            state["dayKey"] = day
            state["dayOpen"] = float(equity)
        if state.get("weekKey") != week or state.get("weekOpen") is None:
            state["weekKey"] = week
            state["weekOpen"] = float(equity)

        state["lastEquity"] = float(equity)
        state["updatedAt"] = now_dt.isoformat().replace("+00:00", "Z")

        day_open = float(state["dayOpen"])
        week_open = float(state["weekOpen"])
        max_dd = None
        if initial_deposit is not None and initial_deposit > 0:
            max_dd = _dd_pct(float(initial_deposit), float(equity))

        return AccountDrawdowns(
            daily_pct=round(_dd_pct(day_open, float(equity)), 4),
            weekly_pct=round(_dd_pct(week_open, float(equity)), 4),
            max_pct=None if max_dd is None else round(max_dd, 4),
            day_open_equity=day_open,
            week_open_equity=week_open,
        )


# Libro compartido en proceso (paper_auto / tests)
GLOBAL_EQUITY_MARK_BOOK = EquityMarkBook()
