"""Política de consolidación OHLCV — evitar pisar velas ya consolidadas."""

from __future__ import annotations

from dataclasses import dataclass

from bolsa_domain.entities.ohlcv_bar import OhlcvBar

DEFAULT_MAX_CLOSE_DEVIATION_PCT = 2.0


@dataclass(frozen=True, slots=True)
class ConsolidationPlan:
    to_write: tuple[OhlcvBar, ...]
    inserted: int
    updated: int
    skipped: int
    skip_reasons: tuple[str, ...]


def _bar_date_key(timestamp: str) -> str:
    return timestamp[:10]


def plan_daily_consolidation(
    existing_by_date: dict[str, OhlcvBar],
    incoming: list[OhlcvBar],
    *,
    max_close_deviation_pct: float = DEFAULT_MAX_CLOSE_DEVIATION_PCT,
) -> ConsolidationPlan:
    """Clasifica velas entrantes: insertar, actualizar (ajuste menor) o conservar existente."""
    to_write: list[OhlcvBar] = []
    inserted = 0
    updated = 0
    skipped = 0
    skip_reasons: list[str] = []

    for bar in incoming:
        key = _bar_date_key(bar.timestamp)
        existing = existing_by_date.get(key)
        if existing is None:
            to_write.append(bar)
            inserted += 1
            continue

        if existing.close == 0:
            to_write.append(bar)
            updated += 1
            continue

        deviation_pct = abs((bar.close - existing.close) / existing.close) * 100
        if deviation_pct > max_close_deviation_pct:
            skipped += 1
            if len(skip_reasons) < 5:
                skip_reasons.append(
                    f"{key}: conservada BD ({existing.close:.4f}) vs Yahoo ({bar.close:.4f}), "
                    f"Δ{deviation_pct:.2f}%",
                )
            continue

        to_write.append(bar)
        updated += 1

    return ConsolidationPlan(
        to_write=tuple(to_write),
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        skip_reasons=tuple(skip_reasons),
    )
