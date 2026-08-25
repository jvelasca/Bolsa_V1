"""Use-cases de optimization runs (cola + process)."""

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.optimize.cpcv import estimate_cpcv_path_count, normalize_cpcv_groups
from bolsa_analytics.optimize.macd_grid import (
    DEFAULT_MACD_TRIPLES,
    estimate_macd_grid_trial_total,
)
from bolsa_analytics.optimize.rsi_grid import estimate_rsi_grid_trial_total
from bolsa_analytics.optimize.sma_grid import estimate_sma_grid_trial_total
from bolsa_application.cognitive_persistence import CognitiveStore
from bolsa_application.optimize import (
    STRATEGY_FAMILY_MACD,
    STRATEGY_FAMILY_RSI,
    STRATEGY_FAMILY_SMA,
    OptimizeGridTrial,
    OptimizeSmaGridResult,
    RunSmaGridOptimize,
    normalize_strategy_family,
)
from bolsa_application.persist_lab_edge_report import (
    persist_lab_edge_report_if_present,
    stamp_persisted_edge_report_id,
)
from bolsa_application.research_evidence import emit_evidence_for_trial
from bolsa_domain.repositories.research_trial_repository import ResearchTrialRepository
from bolsa_infrastructure.database.repositories.optimization_run_repository import (
    OptimizationRunRecord,
    SqlAlchemyOptimizationRunRepository,
)
from bolsa_infrastructure.queue.scan_job_arq import OPTIMIZE_JOB_ARQ_TASK, ScanJobArqQueue


def _trial_dict(trial: OptimizeGridTrial) -> dict[str, Any]:
    metrics = trial.is_metrics or {}
    payload: dict[str, Any] = {
        **trial.params,
        "totalReturnPct": trial.total_return_pct,
        "maxDrawdownPct": trial.max_drawdown_pct,
        "tradeCount": trial.trade_count,
        "score": trial.score,
        "sharpeRatio": metrics.get("sharpeRatio"),
        "isMetrics": metrics,
    }
    # SMA backward-compat: always expose fast/slow keys (0 when N/A).
    payload.setdefault("fastPeriod", trial.params.get("fastPeriod", 0))
    payload.setdefault("slowPeriod", trial.params.get("slowPeriod", 0))
    if trial.oos_metrics is not None:
        payload["oosMetrics"] = trial.oos_metrics
    return payload


def optimize_result_to_dict(result: OptimizeSmaGridResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instrumentId": result.instrument_id,
        "barCount": result.bar_count,
        "engine": result.engine,
        "trialsTotal": result.trials_total,
        "strategyFamily": result.strategy_family,
        "baseline": _trial_dict(result.baseline),
        "trials": [_trial_dict(trial) for trial in result.trials],
    }
    if result.oos_pct is not None:
        payload["oosPct"] = result.oos_pct
        payload["isBarCount"] = result.is_bar_count
        payload["oosBarCount"] = result.oos_bar_count
        payload["splitTimestamp"] = result.split_timestamp
    if result.walk_forward is not None:
        payload["walkForward"] = result.walk_forward
    if result.cpcv is not None:
        payload["cpcv"] = result.cpcv
    if result.edge_report is not None:
        payload["edgeReport"] = result.edge_report
    if result.pbo is not None:
        payload["pbo"] = result.pbo
    return payload


def estimate_trials_total_from_payload(payload: dict[str, Any]) -> int:
    family = normalize_strategy_family(str(payload.get("strategyFamily") or STRATEGY_FAMILY_SMA))
    max_trials = int(payload.get("maxTrials") or 200)
    engine = str(payload.get("engine") or "auto").lower()
    cpcv_n = normalize_cpcv_groups(payload.get("cpcvGroups"))
    cpcv_paths = estimate_cpcv_path_count(cpcv_n) if cpcv_n else 0
    wf_raw = payload.get("walkForwardFolds")
    wf_folds = int(wf_raw) if wf_raw is not None and int(wf_raw) > 0 else 0
    # CPCV overrides WF when both present (same priority as execute).
    path_mult = cpcv_paths if cpcv_paths else (max(1, min(5, wf_folds)) if wf_folds else 1)
    multi_path = cpcv_paths > 0 or wf_folds > 0

    if family == STRATEGY_FAMILY_RSI:
        periods = payload.get("periods") or [10, 12, 14, 16, 18, 20]
        oversold = payload.get("oversoldLevels") or [20.0, 25.0, 30.0, 35.0]
        overbought = payload.get("overboughtLevels") or [65.0, 70.0, 75.0, 80.0]
        per_fold = estimate_rsi_grid_trial_total(
            [int(v) for v in periods],
            [float(v) for v in oversold],
            [float(v) for v in overbought],
            max_trials=min(max_trials, 60 if multi_path else 80),
        )
        return per_fold * path_mult
    if family == STRATEGY_FAMILY_MACD:
        raw_triples = payload.get("macdTriples")
        if raw_triples:
            triples = [
                (int(item[0]), int(item[1]), int(item[2])) for item in raw_triples
            ]
        else:
            triples = list(DEFAULT_MACD_TRIPLES)
        per_fold = estimate_macd_grid_trial_total(
            triples, max_trials=min(max_trials, 60 if multi_path else 80)
        )
        return per_fold * path_mult

    fast = payload.get("fastPeriods") or [10, 15, 20, 25, 30]
    slow = payload.get("slowPeriods") or [40, 50, 60, 80, 100]
    if multi_path:
        per_fold = estimate_sma_grid_trial_total(
            [int(v) for v in fast],
            [int(v) for v in slow],
            max_trials=min(max_trials, 80),
        )
        return per_fold * path_mult
    if engine == "optuna":
        return min(max_trials, 100)
    return estimate_sma_grid_trial_total(
        [int(v) for v in fast],
        [int(v) for v in slow],
        max_trials=max_trials,
    )


def _payload_to_execute_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    macd_triples = None
    raw_triples = payload.get("macdTriples")
    if raw_triples:
        macd_triples = [(int(item[0]), int(item[1]), int(item[2])) for item in raw_triples]

    return {
        "instrument_id": str(payload["instrumentId"]),
        "fast_periods": payload.get("fastPeriods"),
        "slow_periods": payload.get("slowPeriods"),
        "periods": payload.get("periods"),
        "oversold_levels": payload.get("oversoldLevels"),
        "overbought_levels": payload.get("overboughtLevels"),
        "macd_triples": macd_triples,
        "initial_cash": float(payload.get("initialCash") or 10000),
        "bar_limit": int(payload.get("barLimit") or 500),
        "timeframe": str(payload.get("timeframe") or "1d"),
        "max_trials": int(payload.get("maxTrials") or 200),
        "engine": str(payload.get("engine") or "auto"),
        "strategy_family": str(payload.get("strategyFamily") or STRATEGY_FAMILY_SMA),
        "oos_pct": payload.get("oosPct"),
        "walk_forward_folds": payload.get("walkForwardFolds"),
        "cpcv_groups": payload.get("cpcvGroups"),
        "cpcv_purge_bars": payload.get("cpcvPurgeBars"),
        "cpcv_embargo_bars": payload.get("cpcvEmbargoBars"),
    }


async def _persist_optimize_research_trials(
    trials_repo: ResearchTrialRepository,
    *,
    result: OptimizeSmaGridResult,
    optimization_run_id: str,
    proposed_by: str,
    evidence_repo: Any | None = None,
    belief_repo: Any | None = None,
) -> None:
    """Append one research_trials row per grid trial (ledger K) + Evidence/Belief."""
    family = result.strategy_family or STRATEGY_FAMILY_SMA
    for trial in result.trials:
        params = {
            **trial.params,
            "engine": result.engine,
            "barCount": result.bar_count,
            "strategyFamily": family,
        }
        if result.oos_pct is not None:
            params["oosPct"] = result.oos_pct
            params["isBarCount"] = result.is_bar_count
            params["oosBarCount"] = result.oos_bar_count

        blocks = None
        if (
            trial.oos_metrics is not None
            or result.walk_forward is not None
            or result.cpcv is not None
        ):
            blocks = {
                "oosMetrics": trial.oos_metrics,
                "oosPct": result.oos_pct,
                "isBarCount": result.is_bar_count,
                "oosBarCount": result.oos_bar_count,
                "splitTimestamp": result.split_timestamp,
            }
            if result.walk_forward is not None:
                blocks["walkForward"] = {
                    "nFolds": result.walk_forward.get("nFolds"),
                    "mode": result.walk_forward.get("mode"),
                    "meanOosScore": result.walk_forward.get("meanOosScore"),
                    "stdOosScore": result.walk_forward.get("stdOosScore"),
                    "meanIsScore": result.walk_forward.get("meanIsScore"),
                    "walkForwardEfficiency": result.walk_forward.get(
                        "walkForwardEfficiency"
                    ),
                    "positiveOosFoldShare": result.walk_forward.get(
                        "positiveOosFoldShare"
                    ),
                    "oosCv": result.walk_forward.get("oosCv"),
                }
                blocks["labEvidence"] = {
                    "wfeSource": "lab_score",
                    "mode": "walkforward",
                    "walkForwardEfficiency": result.walk_forward.get(
                        "walkForwardEfficiency"
                    ),
                }
            if result.cpcv is not None:
                blocks["cpcv"] = {
                    "nGroups": result.cpcv.get("nGroups"),
                    "nTestGroups": result.cpcv.get("nTestGroups"),
                    "purgeBars": result.cpcv.get("purgeBars"),
                    "embargoBars": result.cpcv.get("embargoBars"),
                    "pathCount": result.cpcv.get("pathCount"),
                    "mode": result.cpcv.get("mode"),
                    "meanOosScore": result.cpcv.get("meanOosScore"),
                    "stdOosScore": result.cpcv.get("stdOosScore"),
                    "meanIsScore": result.cpcv.get("meanIsScore"),
                    "walkForwardEfficiency": result.cpcv.get("walkForwardEfficiency"),
                    "positiveOosFoldShare": result.cpcv.get("positiveOosFoldShare"),
                    "oosCv": result.cpcv.get("oosCv"),
                    "pbo": result.cpcv.get("pbo"),
                }
                blocks["labEvidence"] = {
                    "wfeSource": "lab_score",
                    "mode": "cpcv",
                    "walkForwardEfficiency": result.cpcv.get("walkForwardEfficiency"),
                    "pbo": (result.cpcv.get("pbo") or {}).get("pbo"),
                }
            if result.pbo is not None:
                blocks["pbo"] = result.pbo
            if result.edge_report is not None:
                blocks["edgeReport"] = {
                    "credibility": result.edge_report.get("credibility"),
                    "band": result.edge_report.get("band"),
                    "mode": result.edge_report.get("mode"),
                    "suite": result.edge_report.get("suite"),
                    "blockReasons": result.edge_report.get("blockReasons"),
                    "persistedEdgeReportId": result.edge_report.get("persistedEdgeReportId"),
                    "edgeReportId": result.edge_report.get("edgeReportId"),
                    "strategyOrSignalRef": result.edge_report.get("strategyOrSignalRef"),
                }
                if "labEvidence" not in blocks:
                    suite = result.edge_report.get("suite") or {}
                    blocks["labEvidence"] = {
                        "wfeSource": suite.get("wfeSource") or "lab_score",
                        "mode": "edge_report",
                        "walkForwardEfficiency": suite.get("walkForwardEfficiency"),
                    }

        saved = await trials_repo.insert_trial(
            instrument_id=result.instrument_id,
            optimization_run_id=optimization_run_id,
            preset_key=family,
            strategy_name=family,
            params=params,
            is_metrics=dict(trial.is_metrics),
            is_score=trial.score,
            proposed_by=proposed_by,
            k_contribution=1,
            blocks=blocks,
            manifest_ref={
                "optimizationRunId": optimization_run_id,
                "engine": result.engine,
                "strategyFamily": family,
            },
        )
        if saved.blocks is None and blocks is not None:
            from dataclasses import replace

            saved = replace(saved, blocks=blocks)
        await emit_evidence_for_trial(
            evidence_repo, saved, belief_repo=belief_repo
        )


@dataclass(frozen=True, slots=True)
class ProcessOptimizationRunResult:
    """Procesa Optimization Run Result."""
    processed: bool
    run_id: str | None = None
    status: str | None = None
    error: str | None = None


class EnqueueOptimizationRun:
    """Encola Optimization Run."""
    def __init__(
        self,
        repo: SqlAlchemyOptimizationRunRepository,
        arq_queue: ScanJobArqQueue | None = None,
    ) -> None:
        self._runs = repo
        self._arq_queue = arq_queue

    async def execute(self, payload: dict[str, Any]) -> OptimizationRunRecord:
        if not payload.get("instrumentId"):
            raise ValueError("instrumentId es obligatorio")
        enriched = dict(payload)
        enriched["trialsTotal"] = estimate_trials_total_from_payload(enriched)
        run = await self._runs.create_pending(enriched)
        if self._arq_queue is not None:
            await self._arq_queue.enqueue(run.id, task_name=OPTIMIZE_JOB_ARQ_TASK)
        return run


class GetOptimizationRun:
    """Obtiene Optimization Run."""
    def __init__(self, repo: SqlAlchemyOptimizationRunRepository) -> None:
        self._runs = repo

    async def execute(self, run_id: str) -> OptimizationRunRecord | None:
        return await self._runs.get_by_id(run_id)


class ListOptimizationRuns:
    """Lista Optimization Runs."""
    def __init__(self, repo: SqlAlchemyOptimizationRunRepository) -> None:
        self._runs = repo

    async def execute(self, *, limit: int = 20) -> list[OptimizationRunRecord]:
        return await self._runs.list_recent(limit=limit)


class ProcessOptimizationRun:
    """Procesa Optimization Run."""
    def __init__(
        self,
        repo: SqlAlchemyOptimizationRunRepository,
        run_optimize: RunSmaGridOptimize,
        research_trials: ResearchTrialRepository,
        cognitive_store: CognitiveStore | None = None,
        research_evidence: Any | None = None,
        research_beliefs: Any | None = None,
    ) -> None:
        self._runs = repo
        self._run_optimize = run_optimize
        self._trials = research_trials
        self._cognitive = cognitive_store
        self._evidence = research_evidence
        self._beliefs = research_beliefs

    async def execute(self, run_id: str | None = None) -> ProcessOptimizationRunResult:
        if run_id is not None:
            run = await self._runs.claim_by_id(run_id)
        else:
            run = await self._runs.claim_next()
        if run is None:
            return ProcessOptimizationRunResult(processed=False)

        await self._runs.update_progress(run.id, trial_count=0, best_score=None)

        async def on_progress(done: int, _total: int, best: float | None) -> None:
            await self._runs.update_progress(
                run.id,
                trial_count=done,
                best_score=best,
            )

        try:
            result = await self._run_optimize.execute(
                **_payload_to_execute_kwargs(run.payload),
                on_progress=on_progress,
            )
        except ValueError as exc:
            await self._runs.mark_failed(run.id, error=str(exc))
            return ProcessOptimizationRunResult(
                processed=True,
                run_id=run.id,
                status="failed",
                error=str(exc),
            )
        except Exception as exc:
            await self._runs.mark_failed(run.id, error=str(exc))
            return ProcessOptimizationRunResult(
                processed=True,
                run_id=run.id,
                status="failed",
                error=str(exc),
            )

        result = await self._stamp_cognitive_edge_report(result, optimization_run_id=run.id)
        await self._runs.mark_completed(run.id, result=optimize_result_to_dict(result))
        engine = (result.engine or "grid").lower()
        proposed_by = "optuna" if "optuna" in engine else "grid"
        await _persist_optimize_research_trials(
            self._trials,
            result=result,
            optimization_run_id=run.id,
            proposed_by=proposed_by,
            evidence_repo=self._evidence,
            belief_repo=self._beliefs,
        )
        return ProcessOptimizationRunResult(processed=True, run_id=run.id, status="completed")

    async def _stamp_cognitive_edge_report(
        self,
        result: OptimizeSmaGridResult,
        *,
        optimization_run_id: str,
    ) -> OptimizeSmaGridResult:
        from dataclasses import replace

        persisted_id = await persist_lab_edge_report_if_present(
            self._cognitive,
            result.edge_report,
            optimization_run_id=optimization_run_id,
            auto_trial=False,
        )
        stamped = stamp_persisted_edge_report_id(result.edge_report, persisted_id)
        if stamped is result.edge_report:
            return result
        return replace(result, edge_report=stamped)


class RunSmaGridOptimizeAndSave:
    """Ejecuta Sma Grid Optimize And Save."""
    def __init__(
        self,
        run_optimize: RunSmaGridOptimize,
        repo: SqlAlchemyOptimizationRunRepository,
        research_trials: ResearchTrialRepository,
        cognitive_store: CognitiveStore | None = None,
        research_evidence: Any | None = None,
        research_beliefs: Any | None = None,
    ) -> None:
        self._run_optimize = run_optimize
        self._runs = repo
        self._trials = research_trials
        self._cognitive = cognitive_store
        self._evidence = research_evidence
        self._beliefs = research_beliefs

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
    ) -> tuple[OptimizeSmaGridResult, OptimizationRunRecord]:
        result = await self._run_optimize.execute(
            instrument_id=instrument_id,
            fast_periods=fast_periods,
            slow_periods=slow_periods,
            periods=periods,
            oversold_levels=oversold_levels,
            overbought_levels=overbought_levels,
            macd_triples=macd_triples,
            initial_cash=initial_cash,
            bar_limit=bar_limit,
            timeframe=timeframe,
            max_trials=max_trials,
            engine=engine,
            strategy_family=strategy_family,
            oos_pct=oos_pct,
            walk_forward_folds=walk_forward_folds,
            cpcv_groups=cpcv_groups,
            cpcv_purge_bars=cpcv_purge_bars,
            cpcv_embargo_bars=cpcv_embargo_bars,
        )
        payload = {
            "instrumentId": instrument_id,
            "fastPeriods": fast_periods,
            "slowPeriods": slow_periods,
            "periods": periods,
            "oversoldLevels": oversold_levels,
            "overboughtLevels": overbought_levels,
            "macdTriples": (
                [[a, b, c] for a, b, c in macd_triples] if macd_triples else None
            ),
            "initialCash": initial_cash,
            "barLimit": bar_limit,
            "timeframe": timeframe,
            "maxTrials": max_trials,
            "engine": engine,
            "strategyFamily": result.strategy_family,
            "oosPct": oos_pct,
            "walkForwardFolds": walk_forward_folds,
            "cpcvGroups": cpcv_groups,
            "cpcvPurgeBars": cpcv_purge_bars,
            "cpcvEmbargoBars": cpcv_embargo_bars,
            "trialsTotal": result.trials_total,
        }
        from dataclasses import replace

        # Persist cognitive edge_reports before create_completed so the saved
        # optimize result JSON includes persistedEdgeReportId (run id goes in notes later via async path).
        persisted_id = await persist_lab_edge_report_if_present(
            self._cognitive,
            result.edge_report,
            optimization_run_id=None,
            auto_trial=False,
        )
        stamped_report = stamp_persisted_edge_report_id(result.edge_report, persisted_id)
        if stamped_report is not result.edge_report:
            result = replace(result, edge_report=stamped_report)

        run = await self._runs.create_completed(
            payload=payload,
            result=optimize_result_to_dict(result),
        )
        engine_label = (result.engine or "grid").lower()
        proposed_by = "optuna" if "optuna" in engine_label else "grid"
        await _persist_optimize_research_trials(
            self._trials,
            result=result,
            optimization_run_id=run.id,
            proposed_by=proposed_by,
            evidence_repo=self._evidence,
            belief_repo=self._beliefs,
        )
        return result, run
