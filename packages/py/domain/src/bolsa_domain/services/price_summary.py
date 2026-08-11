"""Servicio de dominio para construir resumen de precios a partir de barras OHLCV."""
from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.value_objects.price_summary import PriceSummary


def build_price_summary(bars: list[OhlcvBar], *, summary_limit: int = 500) -> PriceSummary | None:
    if not bars:
        return None

    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    recent = ordered[-summary_limit:]
    last = recent[-1]
    previous = recent[-2] if len(recent) >= 2 else None

    last_close = last.close
    previous_close = previous.close if previous else None
    change_abs = (last_close - previous_close) if previous_close is not None else None
    change_pct = (
        (change_abs / previous_close) * 100
        if change_abs is not None and previous_close
        else None
    )

    return PriceSummary(
        last_close=last_close,
        previous_close=previous_close,
        change_abs=change_abs,
        change_pct=change_pct,
        period_low=min(bar.low for bar in recent),
        period_high=max(bar.high for bar in recent),
        bar_count=len(recent),
        first_date=recent[0].timestamp,
        last_date=last.timestamp,
    )
