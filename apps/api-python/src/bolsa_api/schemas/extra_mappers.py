"""Mappers auxiliares dominio ↔ DTO (extras)."""

from typing import Any

from bolsa_application.optimize import OptimizeGridTrial, OptimizeSmaGridResult
from bolsa_domain.entities.backtest import BacktestRun, BacktestRunDetail
from bolsa_domain.entities.portfolio import PortfolioSummary, TradeResult, Transaction
from bolsa_domain.value_objects.market import InstrumentLiveQuote, MarketProviderStatus, SyncResult

from bolsa_api.schemas.backtests import (
    BacktestEquityPointDto,
    BacktestRunDetailDto,
    BacktestRunDto,
    BacktestTradeDto,
    OptimizeSmaGridResultDto,
    SmaGridTrialDto,
)
from bolsa_api.schemas.market import (
    LiveQuoteResponseDto,
    LiveQuoteSourceDto,
    MarketProviderStatusDto,
    SyncResultDto,
    XtbQuoteDto,
)
from bolsa_api.schemas.portfolio import (
    OperationalExitPlanDto,
    OperationalPositionDto,
    PortfolioDto,
    PortfolioSummaryDto,
    PositionDto,
    TransactionDto,
)


def to_sync_result_dto(result: SyncResult) -> SyncResultDto:
    return SyncResultDto(
        bars_added=result.bars_added,
        status=result.status,
        error=result.error,
        bars_inserted=result.bars_inserted,
        bars_updated=result.bars_updated,
        bars_skipped=result.bars_skipped,
        consolidation_notes=list(result.consolidation_notes),
    )


def to_live_quote_dto(quote: InstrumentLiveQuote) -> LiveQuoteResponseDto:
    return LiveQuoteResponseDto(
        instrument_id=quote.instrument_id,
        symbol=quote.symbol,
        reference=(
            LiveQuoteSourceDto(
                price=quote.reference.price,
                timestamp=quote.reference.timestamp,
                source=quote.reference.source,
            )
            if quote.reference
            else None
        ),
        xtb=(
            XtbQuoteDto(
                symbol=quote.xtb.symbol,
                bid=quote.xtb.bid,
                ask=quote.xtb.ask,
                last=quote.xtb.last,
                timestamp=quote.xtb.timestamp,
            )
            if quote.xtb
            else None
        ),
        spread_pct=quote.spread_pct,
        xtb_available=quote.xtb_available,
    )


def to_market_provider_dto(provider: MarketProviderStatus) -> MarketProviderStatusDto:
    return MarketProviderStatusDto(
        id=provider.id,
        label=provider.label,
        enabled=provider.enabled,
        healthy=provider.healthy,
        message=provider.message,
    )


def to_portfolio_summary_dto(summary: PortfolioSummary) -> PortfolioSummaryDto:
    return PortfolioSummaryDto(
        portfolio=PortfolioDto(
            id=summary.portfolio.id,
            name=summary.portfolio.name,
            currency=summary.portfolio.currency,
            cash=summary.portfolio.cash,
        ),
        positions=[
            PositionDto(
                id=position.id,
                instrument_id=position.instrument_id,
                symbol=position.symbol,
                name=position.name,
                quantity=position.quantity,
                avg_cost=position.avg_cost,
                last_price=position.last_price,
                market_value=position.market_value,
                unrealized_pnl=position.unrealized_pnl,
                unrealized_pnl_pct=position.unrealized_pnl_pct,
            )
            for position in summary.positions
        ],
        total_market_value=summary.total_market_value,
        total_cost=summary.total_cost,
        total_unrealized_pnl=summary.total_unrealized_pnl,
        total_equity=summary.total_equity,
    )


def attach_operational_positions(
    dto: PortfolioSummaryDto,
    records: list[Any],
) -> PortfolioSummaryDto:
    """P1 — adjunta snapshot de autoridad al holding, por instrumento."""
    from bolsa_application.evaluate_exit_plan import advisory_exit_plan

    by_instrument: dict[str, Any] = {}
    for rec in records:
        iid = getattr(rec, "instrument_id", None)
        if isinstance(iid, str) and iid:
            by_instrument[iid] = rec
    for pos in dto.positions:
        rec = by_instrument.get(pos.instrument_id)
        if rec is None:
            continue
        state = getattr(rec, "position_state", None) or {}
        adv = advisory_exit_plan(state if isinstance(state, dict) else None, mark_price=pos.last_price)
        exit_plan = None
        if isinstance(adv, dict):
            exit_plan = OperationalExitPlanDto(
                status=str(adv.get("status") or ""),
                suggested_action=str(adv.get("suggestedAction") or "hold"),
                primary_reason=adv.get("primaryReason")
                if isinstance(adv.get("primaryReason"), str)
                else None,
            )
        pos.operational = OperationalPositionDto(
            status=str(state.get("status") or getattr(rec, "status", "") or ""),
            direction=str(state.get("direction") or ""),
            current_stop=_finite_or_none(state.get("currentStop")),
            target1=_finite_or_none(state.get("target1")),
            target2=_finite_or_none(state.get("target2")),
            trade_plan_id=str(
                state.get("tradePlanId") or getattr(rec, "trade_plan_id", "") or ""
            ),
            unrealized_r=_finite_or_none(state.get("unrealizedR")),
            exit_plan=exit_plan,
        )
    return dto


def _finite_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    n = float(value)
    if n != n:  # NaN
        return None
    return n


def to_transaction_dto(transaction: Transaction) -> TransactionDto:
    return TransactionDto(
        id=transaction.id,
        type=transaction.type,
        instrument_id=transaction.instrument_id,
        symbol=transaction.symbol,
        quantity=transaction.quantity,
        price=transaction.price,
        total=transaction.total,
        executed_at=transaction.executed_at,
    )


def to_trade_response_data(result: TradeResult) -> dict[str, Any]:
    return {
        "transaction": to_transaction_dto(result.transaction).model_dump(by_alias=True),
        "summary": to_portfolio_summary_dto(result.summary).model_dump(by_alias=True),
    }


def to_backtest_run_dto(run: BacktestRun) -> BacktestRunDto:
    return BacktestRunDto(
        id=run.id,
        instrument_id=run.instrument_id,
        symbol=run.symbol,
        name=run.name,
        strategy_type=run.strategy_type,
        initial_cash=run.initial_cash,
        final_equity=run.final_equity,
        total_return_pct=run.total_return_pct,
        max_drawdown_pct=run.max_drawdown_pct,
        trade_count=run.trade_count,
        win_count=run.win_count,
        bar_count=run.bar_count,
        first_date=run.first_date,
        last_date=run.last_date,
        created_at=run.created_at,
        timeframe=run.timeframe,
        data_version=run.data_version,
        commission_bps=run.commission_bps,
        slippage_bps=run.slippage_bps,
        strategy_definition_id=run.strategy_definition_id,
        manifest=run.manifest,
    )


def _equity_curve_from_manifest(manifest: dict[str, Any] | None) -> list[BacktestEquityPointDto]:
    if not manifest:
        return []
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        return []
    raw = outputs.get("equityCurve")
    if not isinstance(raw, list):
        return []
    points: list[BacktestEquityPointDto] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        timestamp = item.get("timestamp")
        equity = item.get("equity")
        if isinstance(timestamp, str) and isinstance(equity, (int, float)):
            points.append(BacktestEquityPointDto(timestamp=timestamp, equity=float(equity)))
    return points


def _trade_reasons_from_manifest(manifest: dict[str, Any] | None) -> list[dict[str, Any] | None]:
    if not manifest:
        return []
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        return []
    raw = outputs.get("tradeReasons")
    if not isinstance(raw, list):
        return []
    return [item if isinstance(item, dict) else None for item in raw]


def to_backtest_detail_dto(run: BacktestRunDetail) -> BacktestRunDetailDto:
    equity_curve = _equity_curve_from_manifest(run.manifest)
    reasons = _trade_reasons_from_manifest(run.manifest)
    return BacktestRunDetailDto(
        **to_backtest_run_dto(run).model_dump(),
        trades=[
            BacktestTradeDto(
                id=trade.id,
                type=trade.type,
                timestamp=trade.timestamp,
                price=trade.price,
                quantity=trade.quantity,
                equity_after=trade.equity_after,
                reason=reasons[index] if index < len(reasons) else None,
            )
            for index, trade in enumerate(run.trades)
        ],
        equity_curve=equity_curve or None,
    )


def _to_sma_grid_trial_dto(trial: OptimizeGridTrial) -> SmaGridTrialDto:
    params = getattr(trial, "params", None) or {}
    oos = getattr(trial, "oos_metrics", None)
    return SmaGridTrialDto(
        fast_period=params.get("fastPeriod", getattr(trial, "fast_period", None)),
        slow_period=params.get("slowPeriod", getattr(trial, "slow_period", None)),
        signal_period=params.get("signalPeriod"),
        period=params.get("period"),
        oversold=params.get("oversold"),
        overbought=params.get("overbought"),
        total_return_pct=trial.total_return_pct,
        max_drawdown_pct=trial.max_drawdown_pct,
        trade_count=trial.trade_count,
        score=trial.score,
        oos_metrics=oos,
    )


def to_optimize_sma_grid_dto(result: OptimizeSmaGridResult) -> OptimizeSmaGridResultDto:
    return OptimizeSmaGridResultDto(
        instrument_id=result.instrument_id,
        bar_count=result.bar_count,
        baseline=_to_sma_grid_trial_dto(result.baseline),
        trials=[_to_sma_grid_trial_dto(trial) for trial in result.trials],
        engine=result.engine,
        trials_total=result.trials_total,
        strategy_family=result.strategy_family,
        oos_pct=result.oos_pct,
        is_bar_count=result.is_bar_count,
        oos_bar_count=result.oos_bar_count,
        split_timestamp=result.split_timestamp,
        walk_forward=result.walk_forward,
        cpcv=result.cpcv,
        edge_report=result.edge_report,
        pbo=result.pbo,
    )
