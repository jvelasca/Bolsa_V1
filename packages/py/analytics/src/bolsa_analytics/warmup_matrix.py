"""Warm-up matrix (Q0.3) — barras mínimas por familia de indicadores.

Documenta requisitos de calentamiento; no reescribe K histórico.
Ver research/observations/ISSUES.md (#warmup-audit).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class WarmupSpec:
    family: str
    description: str
    # Parámetros típicos de referencia (no grid completo).
    default_params: dict[str, int]
    min_bars: Callable[[dict[str, int]], int]
    notes: str = ""


def _sma_min(p: dict[str, int]) -> int:
    return max(int(p.get("slow", p.get("period", 50))), int(p.get("fast", 1)))


def _ema_min(p: dict[str, int]) -> int:
    # EMA estabiliza ~3× period en la práctica; mínimo duro = period.
    return int(p.get("period", 20))


def _rsi_min(p: dict[str, int]) -> int:
    return int(p.get("period", 14)) + 1


def _macd_min(p: dict[str, int]) -> int:
    slow = int(p.get("slow", 26))
    signal = int(p.get("signal", 9))
    return slow + signal


def _bb_min(p: dict[str, int]) -> int:
    return int(p.get("period", 20))


def _adx_min(p: dict[str, int]) -> int:
    # Wilder ADX suele necesitar ~2× period antes de estabilizar.
    period = int(p.get("period", 14))
    return period * 2


def _atr_min(p: dict[str, int]) -> int:
    return int(p.get("period", 14))


WARMUP_MATRIX: tuple[WarmupSpec, ...] = (
    WarmupSpec(
        family="sma",
        description="SMA crossover / single SMA",
        default_params={"fast": 20, "slow": 50},
        min_bars=_sma_min,
        notes="trade_from_index ≥ slow; OOS debe usar IS warm-up",
    ),
    WarmupSpec(
        family="ema",
        description="EMA / SuperTrend proxy",
        default_params={"period": 20},
        min_bars=_ema_min,
    ),
    WarmupSpec(
        family="rsi",
        description="RSI mean-reversion / momentum",
        default_params={"period": 14},
        min_bars=_rsi_min,
    ),
    WarmupSpec(
        family="macd",
        description="MACD signal / zero-line",
        default_params={"fast": 12, "slow": 26, "signal": 9},
        min_bars=_macd_min,
        notes="ISSUE #macd-signal-ema-warmup — cold OOS false negatives",
    ),
    WarmupSpec(
        family="bollinger",
        description="Bollinger bands (no C4 aún)",
        default_params={"period": 20},
        min_bars=_bb_min,
    ),
    WarmupSpec(
        family="adx",
        description="ADX trend strength (no campaña activa)",
        default_params={"period": 14},
        min_bars=_adx_min,
    ),
    WarmupSpec(
        family="atr",
        description="ATR / stops",
        default_params={"period": 14},
        min_bars=_atr_min,
    ),
)


def min_bars_for(family: str, params: dict[str, int] | None = None) -> int:
    spec = next((s for s in WARMUP_MATRIX if s.family == family), None)
    if spec is None:
        raise KeyError(f"familia warm-up desconocida: {family}")
    return spec.min_bars(params or dict(spec.default_params))


def warmup_audit_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in WARMUP_MATRIX:
        mb = spec.min_bars(dict(spec.default_params))
        rows.append(
            {
                "family": spec.family,
                "description": spec.description,
                "defaultParams": dict(spec.default_params),
                "minBars": mb,
                "notes": spec.notes,
            }
        )
    return rows
