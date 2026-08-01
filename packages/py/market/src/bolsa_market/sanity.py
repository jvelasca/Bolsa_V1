from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from bolsa_market.ingest import OhlcvBarIngest


@dataclass(frozen=True, slots=True)
class DataSanityReport:
    valid: bool
    bar_count: int
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _pct_change(prev: Decimal, curr: Decimal) -> Decimal:
    if prev == 0:
        return Decimal("0")
    return abs((curr - prev) / prev) * Decimal("100")


def run_sanity_checks(
    bars: list[OhlcvBarIngest],
    *,
    max_single_day_move_pct: Decimal = Decimal("50"),
    max_gap_days: int = 10,
) -> DataSanityReport:
    """
    Comprobaciones post-Pydantic antes de pandas/indicadores/backtest.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not bars:
        return DataSanityReport(valid=False, bar_count=0, errors=("lista de barras vacía",))

    seen: set[date] = set()
    for bar in bars:
        if bar.timestamp in seen:
            errors.append(f"timestamp duplicado: {bar.timestamp.isoformat()}")
        seen.add(bar.timestamp)

    for prev, curr in zip(bars, bars[1:], strict=False):
        gap = (curr.timestamp - prev.timestamp).days
        if gap > max_gap_days:
            warnings.append(
                f"gap de {gap} días entre {prev.timestamp} y {curr.timestamp}",
            )

        move = _pct_change(prev.close, curr.close)
        if move > max_single_day_move_pct:
            warnings.append(
                f"movimiento {move:.2f}% en {curr.timestamp} — revisar split/dividendo",
            )

        if curr.volume == 0:
            warnings.append(f"volumen cero en {curr.timestamp.isoformat()}")

    return DataSanityReport(
        valid=len(errors) == 0,
        bar_count=len(bars),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
