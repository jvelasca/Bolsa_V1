"""Warm-up matrix (Q0.3) — barras mínimas por familia de indicadores.

Documenta requisitos de calentamiento; no reescribe K histórico.
Ver research/observations/ISSUES.md (#warmup-audit).

Asserts (Q1.6): grids de campaña y `campaign_close_gate` fallan si
`bar_count < min_bars` del espacio de búsqueda / defaults del engine.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass


class WarmupInsufficientError(ValueError):
    """Series too short for the indicator family / param set."""

    def __init__(
        self,
        family: str,
        bar_count: int,
        required: int,
        *,
        detail: str = "",
    ) -> None:
        self.family = family
        self.bar_count = bar_count
        self.required = required
        msg = f"warm-up {family}: bars={bar_count} < required={required}"
        if detail:
            msg = f"{msg} ({detail})"
        super().__init__(msg)


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


_ENGINE_FAMILY: dict[str, str] = {
    "sma_grid_h0": "sma",
    "vectorbt_sma": "sma",
    "optuna_sma": "sma",
    "rsi_grid_h0": "rsi",
    "macd_grid_h0": "macd",
}


def family_from_engine(engine: str | None) -> str | None:
    """Map optimize/campaign engine label → warm-up family (or None if unknown)."""
    if not engine:
        return None
    key = engine.strip().lower()
    if key in _ENGINE_FAMILY:
        return _ENGINE_FAMILY[key]
    for prefix, family in (("sma", "sma"), ("rsi", "rsi"), ("macd", "macd")):
        if key.startswith(prefix):
            return family
    return None


def max_warmup_bars(family: str, param_rows: Iterable[Mapping[str, int]]) -> int:
    rows = list(param_rows)
    if not rows:
        return min_bars_for(family)
    return max(min_bars_for(family, dict(row)) for row in rows)


def assert_bars_cover_warmup(
    family: str,
    bar_count: int,
    params: dict[str, int] | None = None,
) -> int:
    """Raise ``WarmupInsufficientError`` if ``bar_count`` is below ``min_bars_for``."""
    required = min_bars_for(family, params)
    if int(bar_count) < required:
        raise WarmupInsufficientError(family, int(bar_count), required)
    return required


def assert_grid_warmup(
    family: str,
    bar_count: int,
    param_rows: Iterable[Mapping[str, int]],
) -> int:
    """Assert series covers the max warm-up across a grid param space."""
    rows = list(param_rows)
    required = max_warmup_bars(family, rows)
    if int(bar_count) < required:
        raise WarmupInsufficientError(
            family,
            int(bar_count),
            required,
            detail=f"{len(rows)} param rows",
        )
    return required


def check_manifest_warmup(data: Mapping[str, object]) -> list[str]:
    """Q1.6 warm-up checklist errors for a campaign manifest dict (empty = OK)."""
    engine = data.get("engine")
    family = family_from_engine(str(engine) if engine is not None else None)
    if family is None:
        return []
    raw = data.get("bar_count")
    if raw is None:
        raw = data.get("barCount")
    if raw is None:
        return []
    try:
        bar_count = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return [f"bar_count not an int: {raw!r}"]
    required = min_bars_for(family)
    if bar_count < required:
        return [
            f"warm-up {family}: bar_count={bar_count} < required={required} (engine={engine})"
        ]
    return []


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
