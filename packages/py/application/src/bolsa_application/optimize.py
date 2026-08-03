"""Optimización de grids (SMA / RSI / MACD) — hold-out OOS opcional.

Importante: no importar ``vectorbt`` / ``numba`` / ``llvmlite`` a nivel de módulo.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput, run_backtest
from bolsa_analytics.optimize.cpcv import (
    CPCV_EMBARGO_DEFAULT,
    CPCV_EMBARGO_MAX,
    CPCV_PURGE_DEFAULT,
    CPCV_PURGE_MAX,
    CPCV_TEST_GROUPS,
    aggregate_cpcv_metrics,
    normalize_cpcv_gap,
    normalize_cpcv_groups,
    split_cpcv_paths,
)
from bolsa_analytics.optimize.engines import engine_result_label, resolve_optimize_engine
from bolsa_analytics.optimize.holdout import (
    HoldoutSplit,
    metrics_to_oos_summary,
    split_holdout_bars,
)
from bolsa_analytics.optimize.lab_edge_report import (
    build_lab_edge_report_lite,
    trade_returns_from_pnls,
)
from bolsa_analytics.optimize.macd_grid import (
    DEFAULT_MACD_TRIPLES,
    MacdGridTrial,
    _simulate_macd_signal_cross,
    estimate_macd_grid_trial_total,
    run_macd_signal_cross_grid,
)
from bolsa_analytics.optimize.pbo import (
    equal_segment_ranges,
    estimate_pbo_cscv,
    pbo_segment_count,
)
from bolsa_analytics.optimize.rsi_grid import (
    RsiGridTrial,
    _simulate_rsi_mean_reversion,
    estimate_rsi_grid_trial_total,
    run_rsi_mean_reversion_grid,
)
from bolsa_analytics.optimize.sma_grid import (
    SmaGridTrial,
    _simulate_sma_crossover,
    estimate_sma_grid_trial_total,
    run_baseline_preset_backtest,
)
from bolsa_analytics.optimize.walk_forward import (
    aggregate_walk_forward_metrics,
    fold_walk_forward_efficiency,
    normalize_walk_forward_folds,
    split_walk_forward_bars,
)
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.value_objects.timeframe import TimeFrame

AsyncProgressCallback = Callable[[int, int, float | None], Awaitable[None]]

STRATEGY_FAMILY_SMA = "sma_crossover"
STRATEGY_FAMILY_RSI = "rsi_mean_reversion"
STRATEGY_FAMILY_MACD = "macd_signal_cross"
SUPPORTED_FAMILIES = {STRATEGY_FAMILY_SMA, STRATEGY_FAMILY_RSI, STRATEGY_FAMILY_MACD}


@dataclass(frozen=True, slots=True)
class OptimizeGridTrial:
    """Family-agnostic trial (params camelCase)."""

    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    score: float
    params: dict[str, Any] = field(default_factory=dict)
    is_metrics: dict[str, Any] = field(default_factory=dict)
    oos_metrics: dict[str, Any] | None = None

    @property
    def fast_period(self) -> int:
        return int(self.params.get("fastPeriod") or 0)

    @property
    def slow_period(self) -> int:
        return int(self.params.get("slowPeriod") or 0)


@dataclass(frozen=True, slots=True)
class OptimizeSmaGridResult:
    """Resultado de Optimize Sma Grid."""
    instrument_id: str
    bar_count: int
    baseline: OptimizeGridTrial
    trials: list[OptimizeGridTrial]
    engine: str
    trials_total: int
    strategy_family: str = STRATEGY_FAMILY_SMA
    oos_pct: float | None = None
    is_bar_count: int | None = None
    oos_bar_count: int | None = None
    split_timestamp: str | None = None
    # Expanding walk-forward summary (selected-best OOS per fold).
    walk_forward: dict[str, Any] | None = None
    # Combinatorial purged CV summary (selected-best OOS per path).
    cpcv: dict[str, Any] | None = None
    # Lab EdgeReport lite (MC + PSR/DSR + lab WFE) for champion trades.
    edge_report: dict[str, Any] | None = None
    # CSCV PBO lab lite (usually nested under cpcv too).
    pbo: dict[str, Any] | None = None


def normalize_strategy_family(raw: str | None) -> str:
    family = (raw or STRATEGY_FAMILY_SMA).strip().lower()
    if family in {
        "sma",
        "sma_crossover",
        "golden_cross",
        "death_cross",
        "ema_crossover",
        "ma_stack_bullish",
        "donchian_breakout",
        "adx_di_trend",
        "ichimoku_tk_cross",
        "vwap_reclaim",
        "supertrend_follow",
    }:
        return STRATEGY_FAMILY_SMA
    if family in {
        "rsi",
        "rsi_mean_reversion",
        "rsi_momentum",
        "rsi_oversold_bounce",
        "pullback_in_uptrend",
        "stoch_oversold",
        "cci_oversold",
    }:
        return STRATEGY_FAMILY_RSI
    if family in {"macd", "macd_signal_cross", "macd_zero_line"}:
        return STRATEGY_FAMILY_MACD
    raise ValueError(
        f"strategyFamily no soportada: {raw!r} "
        f"(usa sma_crossover | rsi_mean_reversion | macd_signal_cross)"
    )


def _sma_to_grid(trial: SmaGridTrial) -> OptimizeGridTrial:
    return OptimizeGridTrial(
        total_return_pct=trial.total_return_pct,
        max_drawdown_pct=trial.max_drawdown_pct,
        trade_count=trial.trade_count,
        score=trial.score,
        params={"fastPeriod": trial.fast_period, "slowPeriod": trial.slow_period},
        is_metrics=dict(trial.is_metrics or {}),
        oos_metrics=trial.oos_metrics,
    )


def _rsi_to_grid(trial: RsiGridTrial) -> OptimizeGridTrial:
    return OptimizeGridTrial(
        total_return_pct=trial.total_return_pct,
        max_drawdown_pct=trial.max_drawdown_pct,
        trade_count=trial.trade_count,
        score=trial.score,
        params={
            "period": trial.period,
            "oversold": trial.oversold,
            "overbought": trial.overbought,
        },
        is_metrics=dict(trial.is_metrics or {}),
        oos_metrics=trial.oos_metrics,
    )


def _macd_to_grid(trial: MacdGridTrial) -> OptimizeGridTrial:
    return OptimizeGridTrial(
        total_return_pct=trial.total_return_pct,
        max_drawdown_pct=trial.max_drawdown_pct,
        trade_count=trial.trade_count,
        score=trial.score,
        params={
            "fastPeriod": trial.fast_period,
            "slowPeriod": trial.slow_period,
            "signalPeriod": trial.signal_period,
        },
        is_metrics=dict(trial.is_metrics or {}),
        oos_metrics=trial.oos_metrics,
    )


def _baseline_for_family(
    bars: list[BacktestBarInput],
    family: str,
    initial_cash: float,
) -> OptimizeGridTrial:
    if family == STRATEGY_FAMILY_SMA:
        return _sma_to_grid(run_baseline_preset_backtest(bars, initial_cash))
    result = run_backtest(bars, family, initial_cash)
    metrics = {**result.is_metrics}
    score = float(metrics["totalReturnPct"]) - float(metrics["maxDrawdownPct"]) * 0.25
    metrics["score"] = round(score, 6)
    if family == STRATEGY_FAMILY_RSI:
        params: dict[str, Any] = {"period": 14, "oversold": 30.0, "overbought": 70.0}
    else:
        params = {"fastPeriod": 12, "slowPeriod": 26, "signalPeriod": 9}
    return OptimizeGridTrial(
        total_return_pct=result.total_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        trade_count=result.trade_count,
        score=round(score, 4),
        params=params,
        is_metrics=metrics,
    )


def _simulate_family_metrics(
    trial: OptimizeGridTrial,
    *,
    family: str,
    bars: list[BacktestBarInput],
    initial_cash: float,
    trade_from_index: int = 0,
    attach_round_trips: bool = False,
) -> dict[str, Any]:
    if family == STRATEGY_FAMILY_SMA:
        return _simulate_sma_crossover(
            bars,
            int(trial.params["fastPeriod"]),
            int(trial.params["slowPeriod"]),
            initial_cash,
            trade_from_index=trade_from_index,
            attach_round_trips=attach_round_trips,
        )
    if family == STRATEGY_FAMILY_RSI:
        return _simulate_rsi_mean_reversion(
            bars,
            period=int(trial.params["period"]),
            oversold=float(trial.params["oversold"]),
            overbought=float(trial.params["overbought"]),
            initial_cash=initial_cash,
            trade_from_index=trade_from_index,
            attach_round_trips=attach_round_trips,
        )
    return _simulate_macd_signal_cross(
        bars,
        fast_period=int(trial.params["fastPeriod"]),
        slow_period=int(trial.params["slowPeriod"]),
        signal_period=int(trial.params["signalPeriod"]),
        initial_cash=initial_cash,
        trade_from_index=trade_from_index,
        attach_round_trips=attach_round_trips,
    )


def _champion_trade_returns(
    trial: OptimizeGridTrial,
    *,
    family: str,
    is_bars: list[BacktestBarInput],
    oos_bars: list[BacktestBarInput] | None,
    initial_cash: float,
) -> list[float]:
    """Fractional returns of closed round-trips (prefer OOS window when present)."""
    if oos_bars:
        bars = list(is_bars) + list(oos_bars)
        trade_from = len(is_bars)
    else:
        bars = list(is_bars)
        trade_from = 0
    try:
        metrics = _simulate_family_metrics(
            trial,
            family=family,
            bars=bars,
            initial_cash=initial_cash,
            trade_from_index=trade_from,
            attach_round_trips=True,
        )
    except (ValueError, KeyError):
        return []
    pnls = metrics.get("roundTripPnls") or []
    return trade_returns_from_pnls(pnls, initial_cash=initial_cash)


def build_lab_pbo_summary(
    candidates: list[OptimizeGridTrial],
    *,
    family: str,
    bars: list[BacktestBarInput],
    n_groups: int,
    initial_cash: float,
    max_candidates: int = 40,
) -> dict[str, Any] | None:
    """CSCV PBO from (segment × strategy) lab scores. Needs even S≥4 and N≥2."""
    s_count = pbo_segment_count(n_groups)
    if s_count < 4 or len(candidates) < 2:
        return None
    cands = candidates[:max_candidates]
    ranges = equal_segment_ranges(len(bars), s_count)
    if len(ranges) != s_count:
        return None

    import numpy as np

    matrix = np.zeros((s_count, len(cands)), dtype=float)
    for g, (start, end) in enumerate(ranges):
        slice_bars = bars[:end]
        for j, trial in enumerate(cands):
            try:
                metrics = _simulate_family_metrics(
                    trial,
                    family=family,
                    bars=slice_bars,
                    initial_cash=initial_cash,
                    trade_from_index=start,
                )
                matrix[g, j] = float(metrics["score"])
            except (ValueError, KeyError):
                matrix[g, j] = float("-inf")

    # Keep strategies with at least one finite score.
    finite_cols = [j for j in range(matrix.shape[1]) if np.isfinite(matrix[:, j]).any()]
    if len(finite_cols) < 2:
        return None
    matrix = matrix[:, finite_cols]
    # Replace -inf with column min - 1 for ranking stability.
    for j in range(matrix.shape[1]):
        col = matrix[:, j]
        finite = col[np.isfinite(col)]
        fill = (finite.min() - 1.0) if finite.size else -1e9
        col[~np.isfinite(col)] = fill
        matrix[:, j] = col

    try:
        return estimate_pbo_cscv(matrix)
    except ValueError:
        return None


def _lab_wfe_from_summaries(
    *,
    walk_forward: dict[str, Any] | None,
    cpcv: dict[str, Any] | None,
    champion: OptimizeGridTrial | None,
) -> float | None:
    if walk_forward and walk_forward.get("walkForwardEfficiency") is not None:
        return float(walk_forward["walkForwardEfficiency"])
    if cpcv and cpcv.get("walkForwardEfficiency") is not None:
        return float(cpcv["walkForwardEfficiency"])
    if champion is None or not isinstance(champion.oos_metrics, dict):
        return None
    oos_score = champion.oos_metrics.get("score")
    if oos_score is None or champion.score <= 1e-9:
        return None
    return round(float(oos_score) / float(champion.score), 4)


def _eval_oos_for_grid(
    trial: OptimizeGridTrial,
    *,
    family: str,
    is_bars: list[BacktestBarInput],
    oos_bars: list[BacktestBarInput],
    initial_cash: float,
) -> OptimizeGridTrial:
    """Evaluate frozen params on OOS with IS bars as indicator warm-up (flat start on OOS)."""
    if not oos_bars:
        return trial
    combined = list(is_bars) + list(oos_bars)
    trade_from = len(is_bars)
    try:
        metrics = _simulate_family_metrics(
            trial,
            family=family,
            bars=combined,
            initial_cash=initial_cash,
            trade_from_index=trade_from,
        )
    except (ValueError, KeyError):
        return trial
    return replace(trial, oos_metrics=metrics_to_oos_summary(metrics))


def attach_lab_edge_report(
    result: OptimizeSmaGridResult,
    *,
    family: str,
    is_bars: list[BacktestBarInput],
    oos_bars: list[BacktestBarInput] | None,
    initial_cash: float,
) -> OptimizeSmaGridResult:
    """Attach EdgeReport lite for the ranked champion (OOS trades preferred)."""
    champion = result.trials[0] if result.trials else result.baseline
    returns = _champion_trade_returns(
        champion,
        family=family,
        is_bars=is_bars,
        oos_bars=oos_bars,
        initial_cash=initial_cash,
    )
    lab_wfe = _lab_wfe_from_summaries(
        walk_forward=result.walk_forward,
        cpcv=result.cpcv,
        champion=champion,
    )
    report = build_lab_edge_report_lite(
        strategy_ref=f"{family}:{result.instrument_id}",
        trade_returns=returns,
        trials_n=result.trials_total,
        lab_walk_forward_efficiency=lab_wfe,
        family=family,
    )
    if report is None:
        return result
    pbo = result.pbo or (result.cpcv or {}).get("pbo")
    if isinstance(pbo, dict) and pbo.get("pbo") is not None:
        notes = list(report.get("notes") or [])
        notes.append(
            f"PBO CSCV lab={pbo['pbo']:.2f} "
            f"(S={pbo.get('segmentCount')}, splits={pbo.get('splitCount')}); "
            "not full Bailey event CPCV"
        )
        report = {**report, "notes": notes, "pbo": pbo.get("pbo")}
    return replace(result, edge_report=report)


def _attach_oos(
    baseline: OptimizeGridTrial,
    trials: list[OptimizeGridTrial],
    *,
    family: str,
    holdout: HoldoutSplit,
    initial_cash: float,
) -> tuple[OptimizeGridTrial, list[OptimizeGridTrial]]:
    baseline_oos = _eval_oos_for_grid(
        baseline,
        family=family,
        is_bars=holdout.is_bars,
        oos_bars=holdout.oos_bars,
        initial_cash=initial_cash,
    )
    trials_oos = [
        _eval_oos_for_grid(
            trial,
            family=family,
            is_bars=holdout.is_bars,
            oos_bars=holdout.oos_bars,
            initial_cash=initial_cash,
        )
        for trial in trials
    ]
    return baseline_oos, trials_oos


# Match UI MIN_OOS_TRADES_FOR_RANK — sparse OOS is weak evidence.
_MIN_OOS_TRADES_FOR_RANK = 2


def _oos_rank_key(trial: OptimizeGridTrial) -> float:
    metrics = trial.oos_metrics
    if not isinstance(metrics, dict) or metrics.get("score") is None:
        return float("-inf")
    score = float(metrics["score"])
    trades = int(metrics.get("tradeCount") or 0)
    if trades < _MIN_OOS_TRADES_FOR_RANK:
        return score - 1000.0
    return score


def rank_trials_for_result(trials: list[OptimizeGridTrial]) -> list[OptimizeGridTrial]:
    """Prefer OOS score when every trial has oosMetrics; otherwise IS score."""
    if not trials:
        return trials
    if all(isinstance(t.oos_metrics, dict) and t.oos_metrics.get("score") is not None for t in trials):
        return sorted(trials, key=_oos_rank_key, reverse=True)
    return sorted(trials, key=lambda trial: trial.score, reverse=True)


async def _run_in_thread_with_live_progress[T](
    fn: Callable[..., T],
    /,
    *args: object,
    trials_total: int,
    on_progress: AsyncProgressCallback | None,
    poll_seconds: float = 0.4,
    **kwargs: object,
) -> T:
    """Run a sync optimizer in a worker thread and flush progress to the event loop."""
    if on_progress is None:
        return await asyncio.to_thread(fn, *args, **kwargs)

    latest: dict[str, object] = {"done": 0, "best": None}
    stop = asyncio.Event()

    def sync_progress(done: int, _total: int, best: float | None) -> None:
        latest["done"] = done
        latest["best"] = best

    async def flush_loop() -> None:
        last_done = -1
        while not stop.is_set():
            done = int(latest["done"] or 0)
            best = latest["best"]
            if done != last_done:
                await on_progress(done, trials_total, best)  # type: ignore[arg-type]
                last_done = done
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass
        done = int(latest["done"] or 0)
        if done != last_done:
            await on_progress(done, trials_total, latest["best"])  # type: ignore[arg-type]

    flusher = asyncio.create_task(flush_loop())
    try:
        return await asyncio.to_thread(fn, *args, on_progress=sync_progress, **kwargs)
    finally:
        stop.set()
        await flusher


class RunSmaGridOptimize:
    """Ejecuta Sma Grid Optimize."""
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        ohlcv_repository: OhlcvRepository,
    ) -> None:
        self._instruments = instrument_repository
        self._ohlcv = ohlcv_repository

    async def execute(
        self,
        *,
        instrument_id: str,
        fast_periods: list[int] | None = None,
        slow_periods: list[int] | None = None,
        periods: list[int] | None = None,
        oversold_levels: list[float] | None = None,
        overbought_levels: list[float] | None = None,
        macd_triples: list[tuple[int, int, int]] | None = None,
        initial_cash: float = 10000.0,
        bar_limit: int = 500,
        timeframe: str = "1d",
        max_trials: int = 200,
        engine: str | None = "auto",
        strategy_family: str | None = STRATEGY_FAMILY_SMA,
        oos_pct: float | None = None,
        walk_forward_folds: int | None = None,
        cpcv_groups: int | None = None,
        cpcv_purge_bars: int | None = None,
        cpcv_embargo_bars: int | None = None,
        on_progress: AsyncProgressCallback | None = None,
    ) -> OptimizeSmaGridResult:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        family = normalize_strategy_family(strategy_family)
        tf = TimeFrame(timeframe) if timeframe in {t.value for t in TimeFrame} else TimeFrame.D1
        bars = await self._ohlcv.get_bars(instrument_id, timeframe=tf, limit=bar_limit)
        if len(bars) < 50:
            raise ValueError("Se necesitan al menos 50 barras")

        def _as_ts(value: object) -> str:
            return value.isoformat() if hasattr(value, "isoformat") else str(value)

        inputs = [
            BacktestBarInput(
                timestamp=_as_ts(bar.timestamp),
                close=bar.close,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                volume=float(bar.volume),
            )
            for bar in bars
        ]

        cpcv_n = normalize_cpcv_groups(cpcv_groups)
        if cpcv_n is not None:
            return await self._run_cpcv(
                instrument_id=instrument_id,
                bars=inputs,
                family=family,
                n_groups=cpcv_n,
                purge_bars=cpcv_purge_bars,
                embargo_bars=cpcv_embargo_bars,
                fast_periods=fast_periods,
                slow_periods=slow_periods,
                periods=periods,
                oversold_levels=oversold_levels,
                overbought_levels=overbought_levels,
                macd_triples=macd_triples,
                initial_cash=initial_cash,
                max_trials=max_trials,
                timeframe=timeframe,
                on_progress=on_progress,
            )

        wf_n = normalize_walk_forward_folds(walk_forward_folds)
        if wf_n is not None:
            return await self._run_walk_forward(
                instrument_id=instrument_id,
                bars=inputs,
                family=family,
                n_folds=wf_n,
                fast_periods=fast_periods,
                slow_periods=slow_periods,
                periods=periods,
                oversold_levels=oversold_levels,
                overbought_levels=overbought_levels,
                macd_triples=macd_triples,
                initial_cash=initial_cash,
                max_trials=max_trials,
                timeframe=timeframe,
                on_progress=on_progress,
            )

        # Hold-out is best-effort: never abort the whole optimize if the split
        # cannot fit (short windows from a prior backtest are common).
        holdout = None
        if oos_pct is not None and float(oos_pct) > 0:
            try:
                holdout = split_holdout_bars(inputs, oos_pct)
            except Exception:
                holdout = None
        search_bars = holdout.is_bars if holdout is not None else inputs

        if family == STRATEGY_FAMILY_RSI:
            return await self._run_rsi(
                instrument_id=instrument_id,
                bars=inputs,
                search_bars=search_bars,
                holdout=holdout,
                periods=periods,
                oversold_levels=oversold_levels,
                overbought_levels=overbought_levels,
                initial_cash=initial_cash,
                max_trials=min(max_trials, 80),
                on_progress=on_progress,
            )
        if family == STRATEGY_FAMILY_MACD:
            return await self._run_macd(
                instrument_id=instrument_id,
                bars=inputs,
                search_bars=search_bars,
                holdout=holdout,
                macd_triples=macd_triples,
                initial_cash=initial_cash,
                max_trials=min(max_trials, 80),
                on_progress=on_progress,
            )
        return await self._run_sma(
            instrument_id=instrument_id,
            bars=inputs,
            search_bars=search_bars,
            holdout=holdout,
            fast_periods=fast_periods,
            slow_periods=slow_periods,
            initial_cash=initial_cash,
            max_trials=max_trials,
            engine=engine,
            timeframe=timeframe,
            on_progress=on_progress,
        )

    async def _run_h0_partial_on_bars(
        self,
        *,
        instrument_id: str,
        train_bars: list[BacktestBarInput],
        family: str,
        fold_max: int,
        fast_periods: list[int] | None,
        slow_periods: list[int] | None,
        periods: list[int] | None,
        oversold_levels: list[float] | None,
        overbought_levels: list[float] | None,
        macd_triples: list[tuple[int, int, int]] | None,
        initial_cash: float,
        timeframe: str,
        on_progress: AsyncProgressCallback | None,
    ) -> OptimizeSmaGridResult:
        if family == STRATEGY_FAMILY_RSI:
            return await self._run_rsi(
                instrument_id=instrument_id,
                bars=train_bars,
                search_bars=train_bars,
                holdout=None,
                periods=periods,
                oversold_levels=oversold_levels,
                overbought_levels=overbought_levels,
                initial_cash=initial_cash,
                max_trials=fold_max,
                on_progress=on_progress,
            )
        if family == STRATEGY_FAMILY_MACD:
            return await self._run_macd(
                instrument_id=instrument_id,
                bars=train_bars,
                search_bars=train_bars,
                holdout=None,
                macd_triples=macd_triples,
                initial_cash=initial_cash,
                max_trials=fold_max,
                on_progress=on_progress,
            )
        return await self._run_sma(
            instrument_id=instrument_id,
            bars=train_bars,
            search_bars=train_bars,
            holdout=None,
            fast_periods=fast_periods,
            slow_periods=slow_periods,
            initial_cash=initial_cash,
            max_trials=fold_max,
            engine="h0",
            timeframe=timeframe,
            on_progress=on_progress,
        )

    async def _run_cpcv(
        self,
        *,
        instrument_id: str,
        bars: list[BacktestBarInput],
        family: str,
        n_groups: int,
        purge_bars: int | None,
        embargo_bars: int | None,
        fast_periods: list[int] | None,
        slow_periods: list[int] | None,
        periods: list[int] | None,
        oversold_levels: list[float] | None,
        overbought_levels: list[float] | None,
        macd_triples: list[tuple[int, int, int]] | None,
        initial_cash: float,
        max_trials: int,
        timeframe: str,
        on_progress: AsyncProgressCallback | None,
    ) -> OptimizeSmaGridResult:
        """CPCV ligero: H0 per combinatorial path; OOS = selected best."""
        purge = normalize_cpcv_gap(
            purge_bars, default=CPCV_PURGE_DEFAULT, upper=CPCV_PURGE_MAX
        )
        embargo = normalize_cpcv_gap(
            embargo_bars, default=CPCV_EMBARGO_DEFAULT, upper=CPCV_EMBARGO_MAX
        )
        paths = split_cpcv_paths(
            bars,
            n_groups,
            purge_bars=purge,
            embargo_bars=embargo,
        )
        path_max = min(max_trials, 80) if family == STRATEGY_FAMILY_SMA else min(max_trials, 60)
        path_reports: list[dict[str, Any]] = []
        last_baseline: OptimizeGridTrial | None = None
        last_trials: list[OptimizeGridTrial] = []
        last_path = paths[-1]
        engine_label = "h0"
        trials_total = 0
        progress_total = max(1, path_max * len(paths))

        if on_progress is not None:
            await on_progress(0, progress_total, None)

        for path_i, path in enumerate(paths):
            progress_base = path_i * path_max

            async def _path_progress(
                done: int,
                _total: int,
                best: float | None,
                *,
                _base: int = progress_base,
            ) -> None:
                if on_progress is not None:
                    await on_progress(min(progress_total, _base + done), progress_total, best)

            partial = await self._run_h0_partial_on_bars(
                instrument_id=instrument_id,
                train_bars=path.train_bars,
                family=family,
                fold_max=path_max,
                fast_periods=fast_periods,
                slow_periods=slow_periods,
                periods=periods,
                oversold_levels=oversold_levels,
                overbought_levels=overbought_levels,
                macd_triples=macd_triples,
                initial_cash=initial_cash,
                timeframe=timeframe,
                on_progress=_path_progress,
            )
            best = partial.trials[0] if partial.trials else partial.baseline
            best_oos = _eval_oos_for_grid(
                best,
                family=family,
                is_bars=path.train_bars,
                oos_bars=path.test_bars,
                initial_cash=initial_cash,
            )
            oos_score = (
                float(best_oos.oos_metrics["score"])
                if isinstance(best_oos.oos_metrics, dict)
                and best_oos.oos_metrics.get("score") is not None
                else None
            )
            path_reports.append(
                {
                    "index": path.index,
                    "testGroupIndices": list(path.test_group_indices),
                    "trainBarCount": path.train_bar_count,
                    "testBarCount": path.test_bar_count,
                    "testStartTimestamp": path.test_start_timestamp,
                    "bestParams": dict(best.params),
                    "isScore": best.score,
                    "oosMetrics": best_oos.oos_metrics,
                    "walkForwardEfficiency": (
                        fold_walk_forward_efficiency(best.score, oos_score)
                        if oos_score is not None
                        else None
                    ),
                }
            )
            last_baseline = partial.baseline
            last_trials = list(partial.trials)
            last_path = path
            engine_label = f"cpcv_{partial.engine}"
            trials_total = partial.trials_total * len(paths)

        assert last_baseline is not None
        holdout = HoldoutSplit(
            is_bars=last_path.train_bars,
            oos_bars=last_path.test_bars,
            oos_pct=round(last_path.test_bar_count / len(bars), 4),
            is_bar_count=last_path.train_bar_count,
            oos_bar_count=last_path.test_bar_count,
            split_timestamp=last_path.test_start_timestamp,
        )
        baseline, trials = _attach_oos(
            last_baseline,
            last_trials,
            family=family,
            holdout=holdout,
            initial_cash=initial_cash,
        )
        trials = rank_trials_for_result(trials)
        selected_oos: list[float] = []
        selected_is: list[float] = []
        for report in path_reports:
            metrics = report.get("oosMetrics")
            if isinstance(metrics, dict) and metrics.get("score") is not None:
                selected_oos.append(float(metrics["score"]))
                selected_is.append(float(report["isScore"]))
        metrics = aggregate_cpcv_metrics(is_scores=selected_is, oos_scores=selected_oos)
        # PBO CSCV lab: score matrix from last-path candidates × equal segments.
        pbo_summary = build_lab_pbo_summary(
            last_trials if last_trials else trials,
            family=family,
            bars=bars,
            n_groups=n_groups,
            initial_cash=initial_cash,
        )
        cpcv = {
            "nGroups": n_groups,
            "nTestGroups": CPCV_TEST_GROUPS,
            "purgeBars": purge,
            "embargoBars": embargo,
            "pathCount": len(paths),
            "mode": "combinatorial_purged",
            "paths": path_reports,
            **metrics,
        }
        if pbo_summary is not None:
            cpcv["pbo"] = pbo_summary
        if on_progress is not None:
            best_mean = cpcv.get("meanOosScore")
            await on_progress(
                progress_total,
                progress_total,
                float(best_mean) if best_mean is not None else None,
            )

        result = OptimizeSmaGridResult(
            instrument_id=instrument_id,
            bar_count=len(bars),
            baseline=baseline,
            trials=trials,
            engine=engine_label,
            trials_total=trials_total,
            strategy_family=family,
            oos_pct=holdout.oos_pct,
            is_bar_count=holdout.is_bar_count,
            oos_bar_count=holdout.oos_bar_count,
            split_timestamp=holdout.split_timestamp,
            walk_forward=None,
            cpcv=cpcv,
            pbo=pbo_summary,
        )
        return attach_lab_edge_report(
            result,
            family=family,
            is_bars=last_path.train_bars,
            oos_bars=last_path.test_bars,
            initial_cash=initial_cash,
        )

    async def _run_walk_forward(
        self,
        *,
        instrument_id: str,
        bars: list[BacktestBarInput],
        family: str,
        n_folds: int,
        fast_periods: list[int] | None,
        slow_periods: list[int] | None,
        periods: list[int] | None,
        oversold_levels: list[float] | None,
        overbought_levels: list[float] | None,
        macd_triples: list[tuple[int, int, int]] | None,
        initial_cash: float,
        max_trials: int,
        timeframe: str,
        on_progress: AsyncProgressCallback | None,
    ) -> OptimizeSmaGridResult:
        """Anchored expanding WF: re-optimize H0 per fold; OOS = selected best."""
        folds = split_walk_forward_bars(bars, n_folds)
        # Cap per-fold search — WF multiplies cost by n_folds.
        fold_max = min(max_trials, 80) if family == STRATEGY_FAMILY_SMA else min(max_trials, 60)
        fold_reports: list[dict[str, Any]] = []
        last_baseline: OptimizeGridTrial | None = None
        last_trials: list[OptimizeGridTrial] = []
        engine_label = "h0"
        trials_total = 0
        progress_total = max(1, fold_max * len(folds))

        if on_progress is not None:
            await on_progress(0, progress_total, None)

        for fold_i, fold in enumerate(folds):
            fold_progress_base = fold_i * fold_max

            async def _fold_progress(
                done: int,
                _total: int,
                best: float | None,
                *,
                _base: int = fold_progress_base,
            ) -> None:
                if on_progress is not None:
                    await on_progress(min(progress_total, _base + done), progress_total, best)

            partial = await self._run_h0_partial_on_bars(
                instrument_id=instrument_id,
                train_bars=fold.train_bars,
                family=family,
                fold_max=fold_max,
                fast_periods=fast_periods,
                slow_periods=slow_periods,
                periods=periods,
                oversold_levels=oversold_levels,
                overbought_levels=overbought_levels,
                macd_triples=macd_triples,
                initial_cash=initial_cash,
                timeframe=timeframe,
                on_progress=_fold_progress,
            )

            best = partial.trials[0] if partial.trials else partial.baseline
            best_oos = _eval_oos_for_grid(
                best,
                family=family,
                is_bars=fold.train_bars,
                oos_bars=fold.test_bars,
                initial_cash=initial_cash,
            )
            oos_score = (
                float(best_oos.oos_metrics["score"])
                if isinstance(best_oos.oos_metrics, dict)
                and best_oos.oos_metrics.get("score") is not None
                else None
            )
            fold_reports.append(
                {
                    "index": fold.index,
                    "trainBarCount": fold.train_bar_count,
                    "testBarCount": fold.test_bar_count,
                    "testStartTimestamp": fold.test_start_timestamp,
                    "bestParams": dict(best.params),
                    "isScore": best.score,
                    "oosMetrics": best_oos.oos_metrics,
                    "walkForwardEfficiency": (
                        fold_walk_forward_efficiency(best.score, oos_score)
                        if oos_score is not None
                        else None
                    ),
                }
            )
            last_baseline = partial.baseline
            last_trials = list(partial.trials)
            engine_label = f"wf_{partial.engine}"
            trials_total = partial.trials_total * len(folds)

        assert last_baseline is not None
        last_fold = folds[-1]
        holdout = HoldoutSplit(
            is_bars=last_fold.train_bars,
            oos_bars=last_fold.test_bars,
            oos_pct=round(last_fold.test_bar_count / len(bars), 4),
            is_bar_count=last_fold.train_bar_count,
            oos_bar_count=last_fold.test_bar_count,
            split_timestamp=last_fold.test_start_timestamp,
        )
        baseline, trials = _attach_oos(
            last_baseline,
            last_trials,
            family=family,
            holdout=holdout,
            initial_cash=initial_cash,
        )
        trials = rank_trials_for_result(trials)
        selected_oos: list[float] = []
        selected_is: list[float] = []
        for report in fold_reports:
            metrics = report.get("oosMetrics")
            if isinstance(metrics, dict) and metrics.get("score") is not None:
                selected_oos.append(float(metrics["score"]))
                selected_is.append(float(report["isScore"]))
        walk_forward = {
            "nFolds": len(folds),
            "mode": "expanding",
            "folds": fold_reports,
            **aggregate_walk_forward_metrics(
                is_scores=selected_is,
                oos_scores=selected_oos,
            ),
        }
        if on_progress is not None:
            best_mean = walk_forward.get("meanOosScore")
            await on_progress(
                progress_total,
                progress_total,
                float(best_mean) if best_mean is not None else None,
            )

        result = OptimizeSmaGridResult(
            instrument_id=instrument_id,
            bar_count=len(bars),
            baseline=baseline,
            trials=trials,
            engine=engine_label,
            trials_total=trials_total,
            strategy_family=family,
            oos_pct=holdout.oos_pct,
            is_bar_count=holdout.is_bar_count,
            oos_bar_count=holdout.oos_bar_count,
            split_timestamp=holdout.split_timestamp,
            walk_forward=walk_forward,
            cpcv=None,
        )
        return attach_lab_edge_report(
            result,
            family=family,
            is_bars=last_fold.train_bars,
            oos_bars=last_fold.test_bars,
            initial_cash=initial_cash,
        )

    async def _run_sma(
        self,
        *,
        instrument_id: str,
        bars: list[BacktestBarInput],
        search_bars: list[BacktestBarInput],
        holdout: HoldoutSplit | None,
        fast_periods: list[int] | None,
        slow_periods: list[int] | None,
        initial_cash: float,
        max_trials: int,
        engine: str | None,
        timeframe: str,
        on_progress: AsyncProgressCallback | None,
    ) -> OptimizeSmaGridResult:
        resolved_fast = fast_periods or [10, 15, 20, 25, 30]
        resolved_slow = slow_periods or [40, 50, 60, 80, 100]
        resolved_engine = resolve_optimize_engine(engine)
        trials_total = estimate_sma_grid_trial_total(
            resolved_fast, resolved_slow, max_trials=max_trials
        )
        if resolved_engine == "optuna":
            trials_total = min(max_trials, 100)

        if on_progress is not None:
            await on_progress(0, trials_total, None)

        baseline = _baseline_for_family(search_bars, STRATEGY_FAMILY_SMA, initial_cash)

        if resolved_engine == "optuna":
            from bolsa_analytics.optimize.optuna_sma import run_optuna_sma_search

            trial_limit = min(max_trials, 100)
            raw = await _run_in_thread_with_live_progress(
                run_optuna_sma_search,
                search_bars,
                trials_total=trials_total,
                on_progress=on_progress,
                fast_periods=resolved_fast,
                slow_periods=resolved_slow,
                initial_cash=initial_cash,
                max_trials=trial_limit,
                timeframe=timeframe,
            )
            trials = [_sma_to_grid(item) for item in raw]
        elif resolved_engine == "vectorbt":
            from bolsa_analytics.optimize.vectorbt_sma import run_vectorbt_sma_grid

            raw = await _run_in_thread_with_live_progress(
                run_vectorbt_sma_grid,
                search_bars,
                trials_total=trials_total,
                on_progress=on_progress,
                fast_periods=resolved_fast,
                slow_periods=resolved_slow,
                initial_cash=initial_cash,
                max_trials=max_trials,
                timeframe=timeframe,
            )
            trials = [_sma_to_grid(item) for item in raw]
        else:
            trials = []
            best_score: float | None = None
            for fast in resolved_fast:
                for slow in resolved_slow:
                    if fast >= slow:
                        continue
                    if len(trials) >= max_trials:
                        break
                    try:
                        metrics = _simulate_sma_crossover(
                            search_bars, fast, slow, initial_cash
                        )
                    except ValueError:
                        continue
                    score = float(metrics["score"])
                    trials.append(
                        OptimizeGridTrial(
                            total_return_pct=float(metrics["totalReturnPct"]),
                            max_drawdown_pct=float(metrics["maxDrawdownPct"]),
                            trade_count=int(metrics["tradeCount"]),
                            score=score,
                            params={"fastPeriod": fast, "slowPeriod": slow},
                            is_metrics=metrics,
                        )
                    )
                    if best_score is None or score > best_score:
                        best_score = score
                    if on_progress is not None and (
                        len(trials) == 1
                        or len(trials) % 2 == 0
                        or len(trials) >= trials_total
                    ):
                        await on_progress(len(trials), trials_total, best_score)
                        await asyncio.sleep(0)
                if len(trials) >= max_trials:
                    break
            trials.sort(key=lambda trial: trial.score, reverse=True)

        return self._finalize(
            instrument_id=instrument_id,
            bars=bars,
            baseline=baseline,
            trials=trials,
            engine=engine_result_label(resolved_engine),
            trials_total=trials_total,
            family=STRATEGY_FAMILY_SMA,
            holdout=holdout,
            initial_cash=initial_cash,
        )

    async def _run_rsi(
        self,
        *,
        instrument_id: str,
        bars: list[BacktestBarInput],
        search_bars: list[BacktestBarInput],
        holdout: HoldoutSplit | None,
        periods: list[int] | None,
        oversold_levels: list[float] | None,
        overbought_levels: list[float] | None,
        initial_cash: float,
        max_trials: int,
        on_progress: AsyncProgressCallback | None,
    ) -> OptimizeSmaGridResult:
        resolved_periods = periods or [10, 12, 14, 16, 18, 20]
        resolved_os = oversold_levels or [20.0, 25.0, 30.0, 35.0]
        resolved_ob = overbought_levels or [65.0, 70.0, 75.0, 80.0]
        trials_total = estimate_rsi_grid_trial_total(
            resolved_periods, resolved_os, resolved_ob, max_trials=max_trials
        )
        if on_progress is not None:
            await on_progress(0, trials_total, None)

        baseline = _baseline_for_family(search_bars, STRATEGY_FAMILY_RSI, initial_cash)
        raw = await _run_in_thread_with_live_progress(
            run_rsi_mean_reversion_grid,
            search_bars,
            trials_total=trials_total,
            on_progress=on_progress,
            periods=resolved_periods,
            oversold_levels=resolved_os,
            overbought_levels=resolved_ob,
            initial_cash=initial_cash,
            max_trials=max_trials,
        )
        trials = [_rsi_to_grid(item) for item in raw]
        return self._finalize(
            instrument_id=instrument_id,
            bars=bars,
            baseline=baseline,
            trials=trials,
            engine="rsi_grid_h0",
            trials_total=trials_total,
            family=STRATEGY_FAMILY_RSI,
            holdout=holdout,
            initial_cash=initial_cash,
        )

    async def _run_macd(
        self,
        *,
        instrument_id: str,
        bars: list[BacktestBarInput],
        search_bars: list[BacktestBarInput],
        holdout: HoldoutSplit | None,
        macd_triples: list[tuple[int, int, int]] | None,
        initial_cash: float,
        max_trials: int,
        on_progress: AsyncProgressCallback | None,
    ) -> OptimizeSmaGridResult:
        resolved = macd_triples or list(DEFAULT_MACD_TRIPLES)
        trials_total = estimate_macd_grid_trial_total(resolved, max_trials=max_trials)
        if on_progress is not None:
            await on_progress(0, trials_total, None)

        baseline = _baseline_for_family(search_bars, STRATEGY_FAMILY_MACD, initial_cash)
        raw = await _run_in_thread_with_live_progress(
            run_macd_signal_cross_grid,
            search_bars,
            trials_total=trials_total,
            on_progress=on_progress,
            triples=resolved,
            initial_cash=initial_cash,
            max_trials=max_trials,
        )
        trials = [_macd_to_grid(item) for item in raw]
        return self._finalize(
            instrument_id=instrument_id,
            bars=bars,
            baseline=baseline,
            trials=trials,
            engine="macd_grid_h0",
            trials_total=trials_total,
            family=STRATEGY_FAMILY_MACD,
            holdout=holdout,
            initial_cash=initial_cash,
        )

    def _finalize(
        self,
        *,
        instrument_id: str,
        bars: list[BacktestBarInput],
        baseline: OptimizeGridTrial,
        trials: list[OptimizeGridTrial],
        engine: str,
        trials_total: int,
        family: str,
        holdout: HoldoutSplit | None,
        initial_cash: float,
    ) -> OptimizeSmaGridResult:
        oos_pct = None
        is_bar_count = None
        oos_bar_count = None
        split_timestamp = None
        if holdout is not None:
            baseline, trials = _attach_oos(
                baseline,
                trials,
                family=family,
                holdout=holdout,
                initial_cash=initial_cash,
            )
            oos_pct = holdout.oos_pct
            is_bar_count = holdout.is_bar_count
            oos_bar_count = holdout.oos_bar_count
            split_timestamp = holdout.split_timestamp

        trials = rank_trials_for_result(trials)

        result = OptimizeSmaGridResult(
            instrument_id=instrument_id,
            bar_count=len(bars),
            baseline=baseline,
            trials=trials,
            engine=engine,
            trials_total=trials_total,
            strategy_family=family,
            oos_pct=oos_pct,
            is_bar_count=is_bar_count,
            oos_bar_count=oos_bar_count,
            split_timestamp=split_timestamp,
            walk_forward=None,
            cpcv=None,
        )
        is_bars = holdout.is_bars if holdout is not None else bars
        oos_bars = holdout.oos_bars if holdout is not None else None
        return attach_lab_edge_report(
            result,
            family=family,
            is_bars=is_bars,
            oos_bars=oos_bars,
            initial_cash=initial_cash,
        )
