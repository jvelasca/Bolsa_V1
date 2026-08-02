from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_api.api.dependencies import (
    get_backtest_run_use_case,
    get_db_session,
    get_deploy_paper_account_use_case,
    get_enqueue_optimization_run_use_case,
    get_list_backtests_use_case,
    get_list_optimization_runs_use_case,
    get_optimization_run_use_case,
    get_prune_backtests_use_case,
    get_run_backtest_use_case,
    get_run_sma_grid_optimize_and_save_use_case,
)
from bolsa_api.schemas.account_mappers import to_investment_account_dto
from bolsa_api.schemas.accounts import AccountResponseDto
from bolsa_api.schemas.backtests import (
    BacktestDetailResponseDto,
    BacktestListResponseDto,
    BacktestRunRequestDto,
    OptimizationRunDto,
    OptimizationRunResponseDto,
    OptimizationRunsListResponseDto,
    OptimizeSmaGridRequestDto,
    OptimizeSmaGridResponseDto,
    OptimizeSmaGridResultDto,
    PruneBacktestsRequestDto,
    PruneBacktestsResponseDto,
)
from bolsa_api.schemas.extra_mappers import (
    to_backtest_detail_dto,
    to_backtest_run_dto,
    to_optimize_sma_grid_dto,
)
from bolsa_api.schemas.paper_bridge import DeployPaperAccountRequestDto
from bolsa_application.backtests import (
    GetBacktestRun,
    ListBacktestRuns,
    PruneBacktestRuns,
    RunAndSaveBacktest,
)
from bolsa_application.optimization_runs import (
    EnqueueOptimizationRun,
    GetOptimizationRun,
    ListOptimizationRuns,
    RunSmaGridOptimizeAndSave,
)
from bolsa_application.paper_bridge import DeployStrategyToPaperAccount
from bolsa_infrastructure.database.repositories.optimization_run_repository import (
    OptimizationRunRecord,
)

router = APIRouter()


def _optimize_payload(body: OptimizeSmaGridRequestDto) -> dict[str, Any]:
    return {
        "instrumentId": body.instrument_id,
        "strategyFamily": body.strategy_family or "sma_crossover",
        "fastPeriods": body.fast_periods,
        "slowPeriods": body.slow_periods,
        "periods": body.periods,
        "oversoldLevels": body.oversold_levels,
        "overboughtLevels": body.overbought_levels,
        "macdTriples": body.macd_triples,
        "initialCash": body.initial_cash or 10000,
        "barLimit": body.bar_limit or 500,
        "timeframe": body.timeframe or "1d",
        "maxTrials": body.max_trials or 200,
        "engine": body.engine or "auto",
        "oosPct": body.oos_pct,
        "walkForwardFolds": body.walk_forward_folds,
        "cpcvGroups": body.cpcv_groups,
        "cpcvPurgeBars": body.cpcv_purge_bars,
        "cpcvEmbargoBars": body.cpcv_embargo_bars,
    }


def _run_dto(run: OptimizationRunRecord) -> OptimizationRunDto:
    result: OptimizeSmaGridResultDto | None = None
    if run.result is not None:
        try:
            result = OptimizeSmaGridResultDto.model_validate(run.result)
        except Exception:
            # Never 500 the poller: a bad/legacy payload must still surface status.
            result = None
    return OptimizationRunDto(
        id=run.id,
        instrument_id=run.instrument_id,
        symbol=run.symbol,
        status=run.status,
        payload=run.payload,
        result=result,
        error=run.error,
        engine=run.engine,
        best_score=run.best_score,
        trial_count=run.trial_count,
        bar_count=run.bar_count,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


@router.get("/backtests", response_model=BacktestListResponseDto)
async def list_backtests(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
) -> BacktestListResponseDto:
    use_case: ListBacktestRuns = get_list_backtests_use_case(session)
    runs = await use_case.execute(limit=limit)
    return BacktestListResponseDto(data=[to_backtest_run_dto(run) for run in runs])


@router.post("/backtests/prune", response_model=PruneBacktestsResponseDto)
async def prune_backtests(
    body: PruneBacktestsRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PruneBacktestsResponseDto:
    use_case: PruneBacktestRuns = get_prune_backtests_use_case(session)
    deleted = await use_case.execute(keep=body.keep)
    return PruneBacktestsResponseDto(deleted=deleted, keep=body.keep)


@router.get("/backtests/{run_id}", response_model=BacktestDetailResponseDto)
async def get_backtest(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BacktestDetailResponseDto:
    use_case: GetBacktestRun = get_backtest_run_use_case(session)
    run = await use_case.execute(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return BacktestDetailResponseDto(data=to_backtest_detail_dto(run))


@router.post("/backtests/run", response_model=BacktestDetailResponseDto)
async def run_backtest(
    body: BacktestRunRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BacktestDetailResponseDto:
    if body.strategy_type is None and body.strategy_definition_id is None:
        raise HTTPException(status_code=400, detail="Indica strategyType o strategyDefinitionId")
    if body.strategy_type is not None and not is_valid_preset_key(body.strategy_type):
        raise HTTPException(status_code=400, detail="Invalid backtest request")
    use_case: RunAndSaveBacktest = get_run_backtest_use_case(session)
    try:
        result = await use_case.execute(
            instrument_id=body.instrument_id,
            strategy_type=body.strategy_type,  # type: ignore[arg-type]
            strategy_definition_id=body.strategy_definition_id,
            initial_cash=body.initial_cash or 10000,
            limit=body.limit,
            date_from=body.date_from,
            date_to=body.date_to,
            timeframe=body.timeframe or "1d",
            commission_bps=body.commission_bps or 0,
            slippage_bps=body.slippage_bps or 0,
            spread_bps=body.spread_bps or 0,
            lab_evidence=body.lab_evidence,
            hypothesis_id=body.hypothesis_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BacktestDetailResponseDto(
        data=to_backtest_detail_dto(result.run),
        trial_id=result.trial_id,
        metrics=result.metrics,
    )


@router.post("/backtests/optimize", response_model=OptimizeSmaGridResponseDto)
async def optimize_backtest(
    body: OptimizeSmaGridRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OptimizeSmaGridResponseDto:
    use_case: RunSmaGridOptimizeAndSave = get_run_sma_grid_optimize_and_save_use_case(session)
    try:
        macd_triples = None
        if body.macd_triples:
            macd_triples = [
                (int(item[0]), int(item[1]), int(item[2])) for item in body.macd_triples
            ]
        result, saved = await use_case.execute(
            instrument_id=body.instrument_id,
            strategy_family=body.strategy_family or "sma_crossover",
            fast_periods=body.fast_periods,
            slow_periods=body.slow_periods,
            periods=body.periods,
            oversold_levels=body.oversold_levels,
            overbought_levels=body.overbought_levels,
            macd_triples=macd_triples,
            initial_cash=body.initial_cash or 10000,
            bar_limit=body.bar_limit or 500,
            timeframe=body.timeframe or "1d",
            max_trials=body.max_trials or 200,
            engine=body.engine or "auto",
            oos_pct=body.oos_pct,
            walk_forward_folds=body.walk_forward_folds,
            cpcv_groups=body.cpcv_groups,
            cpcv_purge_bars=body.cpcv_purge_bars,
            cpcv_embargo_bars=body.cpcv_embargo_bars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Surface a JSON error instead of an aborted connection (frontend TypeError).
        raise HTTPException(status_code=500, detail=f"Error al optimizar: {exc}") from exc
    return OptimizeSmaGridResponseDto(
        data=to_optimize_sma_grid_dto(result),
        run_id=saved.id,
    )


@router.post("/backtests/optimize/jobs", response_model=OptimizationRunResponseDto, status_code=202)
async def enqueue_optimize_job(
    body: OptimizeSmaGridRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OptimizationRunResponseDto:
    use_case: EnqueueOptimizationRun = get_enqueue_optimization_run_use_case(session)
    try:
        run = await use_case.execute(_optimize_payload(body))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OptimizationRunResponseDto(data=_run_dto(run))


@router.get("/backtests/optimize/runs", response_model=OptimizationRunsListResponseDto)
async def list_optimize_runs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OptimizationRunsListResponseDto:
    use_case: ListOptimizationRuns = get_list_optimization_runs_use_case(session)
    runs = await use_case.execute(limit=20)
    return OptimizationRunsListResponseDto(data=[_run_dto(run) for run in runs])


@router.get("/backtests/optimize/runs/{run_id}", response_model=OptimizationRunResponseDto)
async def get_optimize_run(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OptimizationRunResponseDto:
    use_case: GetOptimizationRun = get_optimization_run_use_case(session)
    run = await use_case.execute(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    return OptimizationRunResponseDto(data=_run_dto(run))


@router.post("/backtests/{run_id}/deploy-paper", response_model=AccountResponseDto, status_code=201)
async def deploy_backtest_paper_account(
    run_id: str,
    body: DeployPaperAccountRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccountResponseDto:
    run_use_case: GetBacktestRun = get_backtest_run_use_case(session)
    run = await run_use_case.execute(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    if not run.strategy_definition_id:
        raise HTTPException(
            status_code=400,
            detail="Este backtest no está vinculado a una estrategia guardada",
        )
    deploy: DeployStrategyToPaperAccount = get_deploy_paper_account_use_case(session)
    try:
        account = await deploy.execute(
            strategy_definition_id=run.strategy_definition_id,
            initial_deposit=body.initial_deposit,
            source_backtest_run_id=run_id,
            account_name=body.account_name,
            lab_evidence_hint=body.lab_evidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponseDto(data=to_investment_account_dto(account))
