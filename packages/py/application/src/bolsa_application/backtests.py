"""Use-cases de backtests (listar, obtener, run+save)."""

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput, BacktestCostModel, run_backtest
from bolsa_analytics.cost_model_v2 import cost_v2_from_fixed
from bolsa_analytics.research import BarFingerprint, build_run_manifest, compute_data_version
from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_application.dataset_metadata import (
    dataset_metadata_from_bars,
    merge_dataset_into_blocks,
)
from bolsa_application.paper_lab_evidence import trial_blocks_from_lab_evidence_snapshot
from bolsa_application.research_evidence import emit_evidence_for_trial
from bolsa_domain.entities.backtest import BacktestRun, BacktestRunDetail
from bolsa_domain.repositories.backtest_repository import BacktestRepository
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.repositories.research_trial_repository import ResearchTrialRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.ids import new_id


class ListBacktestRuns:
    """Lista Backtest Runs."""
    def __init__(self, repository: BacktestRepository) -> None:
        self._repository = repository

    async def execute(self, limit: int = 20) -> list[BacktestRun]:
        return await self._repository.list_runs(limit=limit)


class PruneBacktestRuns:
    """Keep only the newest `keep` runs; delete older ones."""

    def __init__(self, repository: BacktestRepository) -> None:
        self._repository = repository

    async def execute(self, keep: int = 20) -> int:
        keep_n = max(0, min(500, int(keep)))
        return await self._repository.prune_runs(keep_n)


class GetBacktestRun:
    """Obtiene Backtest Run."""
    def __init__(self, repository: BacktestRepository) -> None:
        self._repository = repository

    async def execute(self, run_id: str) -> BacktestRunDetail | None:
        return await self._repository.get_run(run_id)


@dataclass(frozen=True, slots=True)
class RunAndSaveBacktestResult:
    """Ejecuta And Save Backtest Result."""
    run: BacktestRunDetail
    trial_id: str
    metrics: dict[str, Any]


class RunAndSaveBacktest:
    """Ejecuta And Save Backtest."""
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        ohlcv_repository: OhlcvRepository,
        backtest_repository: BacktestRepository,
        strategy_repository: StrategyDefinitionRepository,
        research_trial_repository: ResearchTrialRepository,
        research_evidence_repository: Any | None = None,
        hypothesis_repository: Any | None = None,
        hypothesis_belief_repository: Any | None = None,
    ) -> None:
        self._instruments = instrument_repository
        self._ohlcv = ohlcv_repository
        self._backtests = backtest_repository
        self._strategies = strategy_repository
        self._trials = research_trial_repository
        self._evidence = research_evidence_repository
        self._hypotheses = hypothesis_repository
        self._beliefs = hypothesis_belief_repository

    async def execute(
        self,
        *,
        instrument_id: str,
        strategy_type: str | None = None,
        strategy_definition_id: str | None = None,
        campaign: str | None = None,
        initial_cash: float = 10000,
        limit: int | None = 500,
        date_from: str | None = None,
        date_to: str | None = None,
        timeframe: str = "1d",
        commission_bps: int = 0,
        slippage_bps: int = 0,
        spread_bps: int = 0,
        lab_evidence: dict[str, Any] | None = None,
        hypothesis_id: str | None = None,
    ) -> RunAndSaveBacktestResult:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        if hypothesis_id:
            if self._hypotheses is None:
                raise ValueError("Hypothesis repository no configurado")
            hyp = await self._hypotheses.get_by_id(hypothesis_id)
            if hyp is None:
                raise ValueError("Hypothesis not found")

        saved_strategy = None
        if strategy_definition_id:
            saved_strategy = await self._strategies.get_definition(strategy_definition_id)
            if saved_strategy is None:
                raise ValueError("Estrategia no encontrada")
            resolved = saved_strategy.preset_key
            if not is_valid_preset_key(resolved):
                nested = saved_strategy.definition.get("presetKey")
                resolved = str(nested) if isinstance(nested, str) else None
            # Client may also send strategyType (Finalistas re-run) as fallback.
            if not is_valid_preset_key(resolved) and is_valid_preset_key(strategy_type):
                resolved = strategy_type
            if not is_valid_preset_key(resolved):
                raise ValueError(
                    "Solo estrategias con preset ejecutable (catálogo Genéricas). "
                    f"preset_key={saved_strategy.preset_key!r}"
                )
            strategy_type = resolved
            timeframe = saved_strategy.timeframe
            execution = saved_strategy.definition.get("execution", {})
            if isinstance(execution, dict):
                commission_bps = int(execution.get("commissionBps", commission_bps))
                slippage_bps = int(execution.get("slippageBps", slippage_bps))
                spread_bps = int(execution.get("spreadBps", spread_bps))
        elif strategy_type is None:
            raise ValueError("Indica strategyType o strategyDefinitionId")
        elif not is_valid_preset_key(strategy_type):
            raise ValueError(f"Preset no reconocido: {strategy_type}")

        tf = TimeFrame(timeframe) if timeframe in {t.value for t in TimeFrame} else TimeFrame.D1
        resolved_limit = 10_000 if limit is None and (date_from or date_to) else (limit if limit is not None else 500)
        bars = await self._ohlcv.get_bars(
            instrument_id,
            timeframe=tf,
            limit=resolved_limit,
            date_from=date_from,
            date_to=date_to,
        )
        if len(bars) < 50:
            raise ValueError("Se necesitan al menos 50 barras. Sincroniza el instrumento primero.")

        fingerprints = [
            BarFingerprint(timestamp=bar.timestamp, close=bar.close) for bar in bars
        ]
        data_version = compute_data_version(fingerprints)

        costs = BacktestCostModel(
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            spread_bps=spread_bps,
        )
        settings = get_settings()
        cost_v2 = cost_v2_from_fixed(
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            spread_bps=spread_bps,
            enabled=bool(settings.cost_model_v2_enabled),
            illiquid_extra=int(settings.cost_model_v2_illiquid_extra_bps),
            volume_ratio_illiquid=float(settings.cost_model_v2_volume_ratio_illiquid),
        )
        result = run_backtest(
            [
                BacktestBarInput(
                    timestamp=bar.timestamp,
                    close=bar.close,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    volume=float(bar.volume),
                )
                for bar in bars
            ],
            strategy_type,
            initial_cash,
            costs=costs,
            cost_v2=cost_v2 if cost_v2.enabled else None,
            strategy_definition=saved_strategy.definition if saved_strategy else None,
        )

        run_id = new_id()
        strategy_payload = saved_strategy.definition if saved_strategy else None
        equity_curve_payload = [
            {"timestamp": point.timestamp, "equity": round(point.equity, 2)}
            for point in result.equity_curve
        ]
        manifest = build_run_manifest(
            run_id=run_id,
            instrument_id=instrument_id,
            strategy_type=strategy_type,
            bars=fingerprints,
            timeframe=tf.value,
            initial_cash=result.initial_cash,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            total_return_pct=result.total_return_pct,
            max_drawdown_pct=result.max_drawdown_pct,
            trade_count=result.trade_count,
            final_equity=result.final_equity,
            equity_curve=equity_curve_payload,
            strategy=strategy_payload,
        )
        # Enrich outputs with IS metrics (primary payload for research_trials.is_metrics).
        outputs = manifest.get("outputs")
        if isinstance(outputs, dict):
            outputs["isMetrics"] = result.is_metrics
            outputs["spreadBps"] = spread_bps
            outputs["tradeReasons"] = [trade.reason for trade in result.trades]

        run = await self._backtests.save_run(
            instrument_id=instrument_id,
            strategy_type=strategy_type,
            initial_cash=result.initial_cash,
            final_equity=result.final_equity,
            total_return_pct=result.total_return_pct,
            max_drawdown_pct=result.max_drawdown_pct,
            trade_count=result.trade_count,
            win_count=result.win_count,
            bar_count=result.bar_count,
            first_date=result.first_date,
            last_date=result.last_date,
            trades=[
                (trade.type, trade.timestamp, trade.price, trade.quantity, trade.equity_after)
                for trade in result.trades
            ],
            timeframe=tf.value,
            data_version=data_version,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            manifest=manifest,
            run_id=run_id,
            strategy_definition_id=strategy_definition_id,
        )

        blocks = trial_blocks_from_lab_evidence_snapshot(lab_evidence)
        dataset_meta = dataset_metadata_from_bars(bars)
        blocks = merge_dataset_into_blocks(blocks, dataset_meta)
        campaign_id = campaign.strip() if isinstance(campaign, str) and campaign.strip() else None
        trial_params: dict[str, Any] = {
            "initialCash": initial_cash,
            "timeframe": tf.value,
            "barLimit": resolved_limit,
            "dateFrom": date_from,
            "dateTo": date_to,
            "commissionBps": commission_bps,
            "slippageBps": slippage_bps,
            "spreadBps": spread_bps,
            "costModelV2": bool(cost_v2.enabled),
            "datasetStart": dataset_meta.get("datasetStart"),
            "datasetEnd": dataset_meta.get("datasetEnd"),
            "bars": dataset_meta.get("bars"),
        }
        if campaign_id:
            trial_params["campaign"] = campaign_id
        trial = await self._trials.insert_trial(
            instrument_id=instrument_id,
            backtest_run_id=run.id,
            strategy_definition_id=strategy_definition_id,
            preset_key=strategy_type,
            strategy_name=strategy_type,
            hypothesis_id=hypothesis_id,
            params=trial_params,
            is_metrics=result.is_metrics,
            is_score=result.total_return_pct,
            proposed_by="human",
            k_contribution=1,
            blocks=blocks,
            manifest_ref={
                "dataVersion": data_version,
                "engine": manifest.get("engine"),
                "runId": run.id,
                "datasetStart": dataset_meta.get("datasetStart"),
                "datasetEnd": dataset_meta.get("datasetEnd"),
                "barCount": dataset_meta.get("bars"),
                **({"campaign": campaign_id} if campaign_id else {}),
                **({"labEvidenceSource": "adopt"} if lab_evidence else {}),
            },
        )
        # Attach blocks / hypothesis for evidence classification (mocks may omit).
        from dataclasses import replace

        if trial.blocks is None and blocks is not None:
            trial = replace(trial, blocks=blocks)
        if trial.hypothesis_id is None and hypothesis_id is not None:
            trial = replace(trial, hypothesis_id=hypothesis_id)
        await emit_evidence_for_trial(
            self._evidence, trial, belief_repo=self._beliefs
        )

        return RunAndSaveBacktestResult(run=run, trial_id=trial.id, metrics=result.is_metrics)
