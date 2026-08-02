"""Execution cost model v2 (Q3.5) — tip vs volume/spread aware.

v1: commission/slippage/spread en bps fijos.
v2 (gated ``enabled``): slippage extra si volumen relativo bajo; spread tip/wide.
Defaults: ``enabled=False`` — no cambia paper/Lab hasta ``COST_MODEL_V2_ENABLED``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True, slots=True)
class CostModelV1:
    commission_bps: int = 10
    slippage_bps: int = 5
    spread_bps: int = 2


@dataclass(frozen=True, slots=True)
class CostModelV2Config:
    """Config tip — wire via Settings / run_backtest(cost_v2=...)."""

    schema_version: str = "cost_model_v2"
    commission_bps: int = 10
    slippage_bps_base: int = 5
    slippage_bps_illiquid_extra: int = 8
    volume_ratio_illiquid: float = 0.35
    spread_bps_tip: int = 2
    spread_bps_wide: int = 6
    enabled: bool = False


def effective_slippage_bps(cfg: CostModelV2Config, *, volume_ratio: float | None) -> int:
    if not cfg.enabled or volume_ratio is None:
        return cfg.slippage_bps_base
    if volume_ratio < cfg.volume_ratio_illiquid:
        return cfg.slippage_bps_base + cfg.slippage_bps_illiquid_extra
    return cfg.slippage_bps_base


def effective_spread_bps(cfg: CostModelV2Config, *, wide_book: bool = False) -> int:
    if not cfg.enabled:
        return cfg.spread_bps_tip
    return cfg.spread_bps_wide if wide_book else cfg.spread_bps_tip


def median_volume(volumes: Sequence[float]) -> float | None:
    vals = [float(v) for v in volumes if v is not None and float(v) > 0]
    if not vals:
        return None
    return float(median(vals))


def volume_ratio(volume: float, med: float | None) -> float | None:
    if med is None or med <= 0:
        return None
    return float(volume) / med


def resolve_bar_costs_v2(
    cfg: CostModelV2Config,
    *,
    volume: float,
    median_vol: float | None,
) -> tuple[int, int, int]:
    """Returns (commission_bps, slippage_bps, spread_bps) for one fill."""
    ratio = volume_ratio(volume, median_vol)
    wide = ratio is not None and ratio < cfg.volume_ratio_illiquid
    return (
        cfg.commission_bps,
        effective_slippage_bps(cfg, volume_ratio=ratio),
        effective_spread_bps(cfg, wide_book=wide),
    )


def cost_v2_from_fixed(
    *,
    commission_bps: int,
    slippage_bps: int,
    spread_bps: int,
    enabled: bool,
    illiquid_extra: int = 8,
    volume_ratio_illiquid: float = 0.35,
    spread_wide: int | None = None,
) -> CostModelV2Config:
    """Build v2 config seeded from the caller's fixed bps (Lab/API defaults)."""
    return CostModelV2Config(
        commission_bps=max(0, int(commission_bps)),
        slippage_bps_base=max(0, int(slippage_bps)),
        slippage_bps_illiquid_extra=max(0, int(illiquid_extra)),
        volume_ratio_illiquid=float(volume_ratio_illiquid),
        spread_bps_tip=max(0, int(spread_bps)),
        spread_bps_wide=max(0, int(spread_wide if spread_wide is not None else max(spread_bps * 3, spread_bps))),
        enabled=bool(enabled),
    )
