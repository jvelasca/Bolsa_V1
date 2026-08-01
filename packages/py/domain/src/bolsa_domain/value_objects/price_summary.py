from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriceSummary:
    last_close: float
    previous_close: float | None
    change_abs: float | None
    change_pct: float | None
    period_low: float
    period_high: float
    bar_count: int
    first_date: str
    last_date: str
