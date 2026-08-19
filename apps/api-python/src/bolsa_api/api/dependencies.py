from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, cast

from fastapi import Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from bolsa_application.daily_ops_report import GetDailyOpsReport
    from bolsa_application.fa_weekly_pipeline import RunFaWeeklyPipeline
    from bolsa_application.get_instrument_composite import GetInstrumentComposite
    from bolsa_application.paper_d_propose import ProposePaperDPlan
    from bolsa_application.run_fundamental_screener import RunFundamentalScreener
    from bolsa_infrastructure.database.repositories.prediction_repository import (
        SqlAlchemyPredictionRepository,
    )

from bolsa_analytics.features.online_adapter import OnlineFeatureAdapter
from bolsa_application.account_blob_state import (
    GetAccountCoreRState,
    GetAccountMandates,
    GetAccountSupervisedF3State,
    SyncAccountCoreRState,
    SyncAccountMandates,
    SyncAccountSupervisedF3State,
)
from bolsa_application.account_lifecycle import (
    ListClosedSimulatedAccounts,
    PurgeClosedSimulatedAccounts,
)
from bolsa_application.accounts import (
    CloseAccount,
    CreateSimulatedAccount,
    DeleteAccount,
    DepositCashToAccount,
    ExecuteTrade,
    GetAccount,
    GetAccountSummary,
    GetPortfolioSummary,
    GetTaxReport,
    ListAccounts,
    ListAccountSummaries,
    ListLedgerEntries,
    ListTransactions,
    SetDefaultAccount,
    UpdateAccount,
    UpdateAccountSettings,
    WithdrawCashFromAccount,
)
from bolsa_application.alerts import EvaluatePriceAlerts
from bolsa_application.backtests import (
    GetBacktestRun,
    ListBacktestRuns,
    PruneBacktestRuns,
    RunAndSaveBacktest,
)
from bolsa_application.daily_opinion_service import DailyOpinionService
from bolsa_application.daily_opinion_telemetry import DailyOpinionTelemetryService
from bolsa_application.events.platform_event_bus import PlatformEventBus
from bolsa_application.execution_policies import (
    CreateExecutionPolicy,
    DeleteExecutionPolicy,
    GetExecutionPolicy,
    ListExecutionPolicies,
    UpdateExecutionPolicy,
)
from bolsa_application.execution_router import ExecuteScanJobHits, ExecutionRouter
from bolsa_application.fx import GetFxRate
from bolsa_application.get_database_summary import GetDatabaseSummary
from bolsa_application.get_instrument_data_status import GetInstrumentDataStatus
from bolsa_application.get_instrument_db_inventory import GetInstrumentDbInventory
from bolsa_application.get_instrument_detail import GetInstrumentDetail
from bolsa_application.get_instrument_fundamentals import GetInstrumentFundamentals
from bolsa_application.get_instrument_indicators import GetInstrumentIndicators
from bolsa_application.get_instrument_profile import GetInstrumentProfile
from bolsa_application.get_instrument_quotes import GetInstrumentQuotes
from bolsa_application.get_ohlcv_bars import GetOhlcvBars
from bolsa_application.import_instrument import ImportInstrument
from bolsa_application.indicator_draft import DraftIndicatorFromPrompt
from bolsa_application.instrument_lifecycle import GetInstrumentRemovalPreview
from bolsa_application.instruments import ListInstrumentsWithMeta
from bolsa_application.market import (
    GetInstrumentLiveQuote,
    GetInstrumentLiveQuotes,
    GetMarketStatus,
)
from bolsa_application.optimization_runs import (
    EnqueueOptimizationRun,
    GetOptimizationRun,
    ListOptimizationRuns,
    ProcessOptimizationRun,
    RunSmaGridOptimizeAndSave,
)
from bolsa_application.optimize import RunSmaGridOptimize
from bolsa_application.paper_bridge import DeployStrategyToPaperAccount
from bolsa_application.pending_orders import (
    CreatePendingOrder,
    DeletePendingOrder,
    ListPendingOrders,
)
from bolsa_application.platform_events import ListPlatformEvents
from bolsa_application.position_exit_evaluator import EvaluatePositionExits
from bolsa_application.position_policies import (
    CreatePositionPolicy,
    DeletePositionPolicy,
    GetPositionPolicy,
    GetPositionPolicyForHolding,
    ListPositionPolicies,
    UpdatePositionPolicy,
)
from bolsa_application.refresh_instrument_fundamentals import RefreshFundamentalsBatch
from bolsa_application.remove_list_instrument import (
    DeleteInstrument,
    ListOrphanInstruments,
    PurgeOrphanInstruments,
    RemoveInstrumentFromList,
)
from bolsa_application.scan_jobs import (
    EnqueueScanJob,
    GetScanJob,
    ListScanJobs,
    ProcessScanJob,
)
from bolsa_application.scan_manifests import GetScanManifest, PersistScanManifest
from bolsa_application.scans import RunScan
from bolsa_application.search_instruments import SearchInstruments
from bolsa_application.signal_alerts import (
    CreateSignalAlertSubscription,
    DeleteSignalAlertSubscription,
    EvaluateSignalAlertSubscriptions,
    ListSignalAlertSubscriptions,
    ResetSignalAlertDedupe,
)
from bolsa_application.strategies import (
    CreateStrategyDefinition,
    CreateStrategyFromPreset,
    DeleteStrategyDefinition,
    GetStrategyDefinition,
    ListStrategyDefinitions,
    UpdateStrategyDefinition,
)
from bolsa_application.strategy_draft import DraftStrategyFromPrompt
from bolsa_application.sync_instrument import SyncInstrumentDailyBars
from bolsa_application.sync_scheduler import (
    EnqueueStaleInstruments,
    GetSyncSettings,
    ListSyncQueue,
    ProcessNextSyncQueueItem,
    UpdateSyncSettings,
)
from bolsa_application.tracker_schedule import ProcessTrackerSchedules
from bolsa_application.trackers import (
    CreateTrackerDefinition,
    DeleteTrackerDefinition,
    EnqueueTrackerScanJob,
    GetTrackerDefinition,
    ListTrackerDefinitions,
    ListTrackerDefinitionsForList,
    RunTrackerScan,
    UpdateTrackerDefinition,
)
from bolsa_application.validate_instrument_xtb import ValidateInstrumentWithXtb
from bolsa_infrastructure.cache.feature_cache_factory import get_feature_cache
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.alert_repository import SqlAlchemyAlertRepository
from bolsa_infrastructure.database.repositories.backtest_repository import (
    SqlAlchemyBacktestRepository,
)
from bolsa_infrastructure.database.repositories.cognitive_repository import (
    SqlAlchemyCognitiveRepository,
)
from bolsa_infrastructure.database.repositories.core_r_repository import SqlAlchemyCoreRRepository
from bolsa_infrastructure.database.repositories.execution_policy_repository import (
    SqlAlchemyExecutionPolicyRepository,
)
from bolsa_infrastructure.database.repositories.hypothesis_belief_repository import (
    SqlAlchemyHypothesisBeliefRepository,
)
from bolsa_infrastructure.database.repositories.hypothesis_repository import (
    SqlAlchemyHypothesisRepository,
)
from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
    SqlAlchemyInstrumentDailyOpinionRepository,
)
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    SqlAlchemyInstrumentStrategyTopRepository,
)
from bolsa_infrastructure.database.repositories.investor_profile_repository import (
    SqlAlchemyInvestorProfileRepository,
)
from bolsa_infrastructure.database.repositories.knowledge_node_repository import (
    SqlAlchemyKnowledgeNodeRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository
from bolsa_infrastructure.database.repositories.mandate_repository import (
    SqlAlchemyMandateRepository,
)
from bolsa_infrastructure.database.repositories.mkl_sync_repository import (
    SqlAlchemyMklSyncRepository,
)
from bolsa_infrastructure.database.repositories.ohlcv_repository import SqlAlchemyOhlcvRepository
from bolsa_infrastructure.database.repositories.optimization_run_repository import (
    SqlAlchemyOptimizationRunRepository,
)
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    SqlAlchemyPendingOrderRepository,
)
from bolsa_infrastructure.database.repositories.platform_event_repository import (
    SqlAlchemyPlatformEventRepository,
)
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)
from bolsa_infrastructure.database.repositories.position_policy_repository import (
    SqlAlchemyPositionPolicyRepository,
)
from bolsa_infrastructure.database.repositories.research_evidence_repository import (
    SqlAlchemyResearchEvidenceRepository,
)
from bolsa_infrastructure.database.repositories.research_tree_repository import (
    SqlAlchemyResearchTreeRepository,
)
from bolsa_infrastructure.database.repositories.research_trial_repository import (
    SqlAlchemyResearchTrialRepository,
)
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    SqlAlchemyScanJobRepository,
)
from bolsa_infrastructure.database.repositories.scan_manifest_repository import (
    SqlAlchemyDataSnapshotRepository,
    SqlAlchemyScanManifestRepository,
)
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SqlAlchemySignalAlertRepository,
)
from bolsa_infrastructure.database.repositories.strategy_definition_repository import (
    SqlAlchemyStrategyDefinitionRepository,
)
from bolsa_infrastructure.database.repositories.supervised_f3_repository import (
    SqlAlchemySupervisedF3Repository,
)
from bolsa_infrastructure.database.repositories.sync_log_repository import (
    SqlAlchemySyncLogRepository,
)
from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
    SqlAlchemySyncSchedulerRepository,
)
from bolsa_infrastructure.database.repositories.tracker_definition_repository import (
    SqlAlchemyTrackerDefinitionRepository,
)
from bolsa_infrastructure.database.repositories.workspace_repository import (
    SqlAlchemyWorkspaceRepository,
)
from bolsa_infrastructure.queue.scan_job_arq import ScanJobArqQueue
from bolsa_infrastructure.queue.scan_job_redis import ScanJobRedisQueue


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)


async def get_db_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory(request)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_account_repository(session: AsyncSession) -> SqlAlchemyAccountRepository:
    return SqlAlchemyAccountRepository(session)


def get_ledger_repository(session: AsyncSession) -> SqlAlchemyLedgerRepository:
    return SqlAlchemyLedgerRepository(session)


def get_core_r_repository(session: AsyncSession) -> SqlAlchemyCoreRRepository:
    return SqlAlchemyCoreRRepository(session)


def get_supervised_f3_repository(session: AsyncSession) -> SqlAlchemySupervisedF3Repository:
    return SqlAlchemySupervisedF3Repository(session)


def get_mandate_repository(session: AsyncSession) -> SqlAlchemyMandateRepository:
    return SqlAlchemyMandateRepository(session)


def get_account_id_header(
    x_account_id: str | None = Header(default=None, alias="X-Account-Id"),
) -> str | None:
    return x_account_id


def get_list_accounts_use_case(session: AsyncSession) -> ListAccounts:
    return ListAccounts(get_account_repository(session))


def get_create_account_use_case(session: AsyncSession) -> CreateSimulatedAccount:
    return CreateSimulatedAccount(get_account_repository(session))


def get_ensure_account_investor_profile_use_case(
    session: AsyncSession,
) -> Any:
    """Wizard ART-PROFILE al crear cuenta (crea/asigna/default) sobre el profile store."""
    from bolsa_application.investor_profiles import EnsureAccountInvestorProfile

    return EnsureAccountInvestorProfile(get_investor_profile_repository(session))  # type: ignore[arg-type]


def get_update_account_settings_use_case(session: AsyncSession) -> UpdateAccountSettings:
    return UpdateAccountSettings(get_account_repository(session))


def get_get_account_use_case(session: AsyncSession) -> GetAccount:
    return GetAccount(get_account_repository(session))


def get_get_account_summary_use_case(session: AsyncSession) -> GetAccountSummary:
    return GetAccountSummary(
        get_account_repository(session),
        get_portfolio_repository(session),
        get_ledger_repository(session),
    )


def get_list_account_summaries_use_case(session: AsyncSession) -> ListAccountSummaries:
    return ListAccountSummaries(
        get_account_repository(session),
        get_portfolio_repository(session),
    )


def get_list_ledger_use_case(session: AsyncSession) -> ListLedgerEntries:
    return ListLedgerEntries(get_ledger_repository(session))


def get_daily_ops_report_use_case(session: AsyncSession) -> GetDailyOpsReport:
    """R1 — resumen operativo diario."""
    from bolsa_application.daily_ops_report import GetDailyOpsReport

    return GetDailyOpsReport(
        get_get_account_summary_use_case(session),
        get_list_ledger_use_case(session),
        SqlAlchemySupervisedF3Repository(session),
        SqlAlchemyInstrumentDailyOpinionRepository(session),
    )


def get_portfolio_summary_use_case(session: AsyncSession) -> GetPortfolioSummary:
    return GetPortfolioSummary(get_account_repository(session), get_portfolio_repository(session))


def get_list_transactions_use_case(session: AsyncSession) -> ListTransactions:
    return ListTransactions(get_account_repository(session), get_portfolio_repository(session))


def get_update_account_use_case(session: AsyncSession) -> UpdateAccount:
    return UpdateAccount(get_account_repository(session))


def get_set_default_account_use_case(session: AsyncSession) -> SetDefaultAccount:
    return SetDefaultAccount(get_account_repository(session))


def get_close_account_use_case(session: AsyncSession) -> CloseAccount:
    return CloseAccount(get_account_repository(session))


def get_delete_account_use_case(session: AsyncSession) -> DeleteAccount:
    return DeleteAccount(get_account_repository(session))


def get_deposit_cash_use_case(session: AsyncSession) -> DepositCashToAccount:
    return DepositCashToAccount(
        get_account_repository(session),
        get_portfolio_repository(session),
        get_ledger_repository(session),
    )


def get_withdraw_cash_use_case(session: AsyncSession) -> WithdrawCashFromAccount:
    return WithdrawCashFromAccount(
        get_account_repository(session),
        get_portfolio_repository(session),
        get_ledger_repository(session),
    )


def get_tax_report_use_case(session: AsyncSession) -> GetTaxReport:
    return GetTaxReport(
        get_account_repository(session),
        get_portfolio_repository(session),
        get_ledger_repository(session),
    )


def get_execute_trade_use_case(session: AsyncSession) -> ExecuteTrade:
    return ExecuteTrade(
        get_account_repository(session),
        get_portfolio_repository(session),
        get_ledger_repository(session),
    )


def get_instrument_repository(session: AsyncSession) -> SqlAlchemyInstrumentRepository:
    return SqlAlchemyInstrumentRepository(session)


def get_ohlcv_repository(session: AsyncSession) -> SqlAlchemyOhlcvRepository:
    return SqlAlchemyOhlcvRepository(session)


_FEATURE_PORT: OnlineFeatureAdapter | None = None


def get_feature_port() -> OnlineFeatureAdapter:
    """Singleton process-local IFeaturePort (online adapter)."""
    global _FEATURE_PORT
    if _FEATURE_PORT is None:
        _FEATURE_PORT = OnlineFeatureAdapter(cache=get_feature_cache())
    return _FEATURE_PORT


def get_workspace_repository(session: AsyncSession) -> SqlAlchemyWorkspaceRepository:
    return SqlAlchemyWorkspaceRepository(session)


def get_sync_log_repository(session: AsyncSession) -> SqlAlchemySyncLogRepository:
    return SqlAlchemySyncLogRepository(session)


def get_portfolio_repository(session: AsyncSession) -> SqlAlchemyPortfolioRepository:
    return SqlAlchemyPortfolioRepository(session)


def get_deploy_paper_account_use_case(session: AsyncSession) -> DeployStrategyToPaperAccount:
    return DeployStrategyToPaperAccount(
        get_account_repository(session),
        SqlAlchemyStrategyDefinitionRepository(session),
        get_backtest_repository(session),
        get_research_trial_repository(session),
    )


def get_backtest_repository(session: AsyncSession) -> SqlAlchemyBacktestRepository:
    return SqlAlchemyBacktestRepository(session)


def get_research_trial_repository(session: AsyncSession) -> SqlAlchemyResearchTrialRepository:
    return SqlAlchemyResearchTrialRepository(session)


def get_research_evidence_repository(
    session: AsyncSession,
) -> SqlAlchemyResearchEvidenceRepository:
    return SqlAlchemyResearchEvidenceRepository(session)


def get_hypothesis_repository(session: AsyncSession) -> SqlAlchemyHypothesisRepository:
    return SqlAlchemyHypothesisRepository(session)


def get_hypothesis_belief_repository(
    session: AsyncSession,
) -> SqlAlchemyHypothesisBeliefRepository:
    return SqlAlchemyHypothesisBeliefRepository(session)


def get_knowledge_node_repository(
    session: AsyncSession,
) -> SqlAlchemyKnowledgeNodeRepository:
    return SqlAlchemyKnowledgeNodeRepository(session)


def get_research_tree_repository(
    session: AsyncSession,
) -> SqlAlchemyResearchTreeRepository:
    return SqlAlchemyResearchTreeRepository(session)


def get_mkl_sync_repository(session: AsyncSession) -> SqlAlchemyMklSyncRepository:
    return SqlAlchemyMklSyncRepository(session)


def get_list_repository(session: AsyncSession) -> SqlAlchemyListRepository:
    return SqlAlchemyListRepository(session)


def get_alert_repository(session: AsyncSession) -> SqlAlchemyAlertRepository:
    return SqlAlchemyAlertRepository(session)


def get_evaluate_alerts_use_case(session: AsyncSession) -> EvaluatePriceAlerts:
    return EvaluatePriceAlerts(
        get_alert_repository(session),
        get_instrument_repository(session),
        get_live_quote_use_case(session),
    )


def get_signal_alert_repository(session: AsyncSession) -> SqlAlchemySignalAlertRepository:
    return SqlAlchemySignalAlertRepository(session)


def get_list_signal_alerts_use_case(session: AsyncSession) -> ListSignalAlertSubscriptions:
    return ListSignalAlertSubscriptions(get_signal_alert_repository(session))


def get_create_signal_alert_use_case(session: AsyncSession) -> CreateSignalAlertSubscription:
    return CreateSignalAlertSubscription(
        get_signal_alert_repository(session),
        get_strategy_definition_repository(session),
    )


def get_delete_signal_alert_use_case(session: AsyncSession) -> DeleteSignalAlertSubscription:
    return DeleteSignalAlertSubscription(get_signal_alert_repository(session))


def get_reset_signal_alert_use_case(session: AsyncSession) -> ResetSignalAlertDedupe:
    return ResetSignalAlertDedupe(get_signal_alert_repository(session))


def get_evaluate_signal_alerts_use_case(session: AsyncSession) -> EvaluateSignalAlertSubscriptions:
    return EvaluateSignalAlertSubscriptions(
        get_signal_alert_repository(session),
        get_strategy_definition_repository(session),
        get_ohlcv_repository(session),
    )


def get_list_instruments_use_case(session: AsyncSession) -> ListInstrumentsWithMeta:
    return ListInstrumentsWithMeta(get_instrument_repository(session))


def get_instrument_quotes_use_case(session: AsyncSession) -> GetInstrumentQuotes:
    return GetInstrumentQuotes(get_instrument_repository(session))


def get_instrument_profile_use_case(session: AsyncSession) -> GetInstrumentProfile:
    return GetInstrumentProfile(get_instrument_repository(session))


def get_instrument_fundamentals_use_case(session: AsyncSession) -> GetInstrumentFundamentals:
    return GetInstrumentFundamentals(
        get_instrument_repository(session),
        get_ohlcv_bars_use_case(session),  # type: ignore[arg-type]
    )


def get_instrument_composite_use_case(session: AsyncSession) -> GetInstrumentComposite:
    from bolsa_application.get_instrument_composite import GetInstrumentComposite

    return GetInstrumentComposite(
        get_instrument_repository(session),
        get_ohlcv_bars_use_case(session),  # type: ignore[arg-type]
    )


def get_run_fundamental_screener_use_case(session: AsyncSession) -> RunFundamentalScreener:
    from bolsa_application.refresh_instrument_fundamentals import RefreshFundamentalsBatch
    from bolsa_application.run_fundamental_screener import RunFundamentalScreener

    instruments = get_instrument_repository(session)
    return RunFundamentalScreener(
        instruments,
        get_list_repository(session),
        refresher=RefreshFundamentalsBatch(instruments),
    )


def get_propose_paper_d_use_case(session: AsyncSession) -> ProposePaperDPlan:
    from bolsa_application.paper_d_propose import ProposePaperDPlan

    return ProposePaperDPlan(
        get_instrument_repository(session),
        get_list_repository(session),
        router=get_execution_router_use_case(session),
        policies=get_execution_policy_repository(session),
    )


def get_run_fa_weekly_pipeline_use_case(session: AsyncSession) -> RunFaWeeklyPipeline:
    from bolsa_application.fa_weekly_pipeline import RunFaWeeklyPipeline

    return RunFaWeeklyPipeline(
        get_run_fundamental_screener_use_case(session),
        get_propose_paper_d_use_case(session),
    )


def get_instrument_db_inventory_use_case(session: AsyncSession) -> GetInstrumentDbInventory:
    return GetInstrumentDbInventory(session)


def get_validate_instrument_xtb_use_case(session: AsyncSession) -> ValidateInstrumentWithXtb:
    settings = get_settings()
    return ValidateInstrumentWithXtb(
        get_instrument_repository(session),
        get_instrument_detail_use_case(session),
        get_sync_log_repository(session),
        settings.xtb_bridge_url,
    )


def get_search_instruments_use_case(session: AsyncSession) -> SearchInstruments:
    return SearchInstruments(get_instrument_repository(session))


def get_import_instrument_use_case(session: AsyncSession) -> ImportInstrument:
    return ImportInstrument(
        get_instrument_repository(session),
        get_sync_instrument_use_case(session),
    )


def get_instrument_detail_use_case(session: AsyncSession) -> GetInstrumentDetail:
    return GetInstrumentDetail(get_instrument_repository(session), get_ohlcv_repository(session))


def get_ohlcv_bars_use_case(session: AsyncSession) -> GetOhlcvBars:
    return GetOhlcvBars(get_instrument_repository(session), get_ohlcv_repository(session))


def get_instrument_indicators_use_case(session: AsyncSession) -> GetInstrumentIndicators:
    return GetInstrumentIndicators(get_ohlcv_bars_use_case(session))


def get_sync_instrument_use_case(session: AsyncSession) -> SyncInstrumentDailyBars:
    return SyncInstrumentDailyBars(
        get_instrument_repository(session),
        get_ohlcv_repository(session),
        get_sync_log_repository(session),
    )


def get_database_summary_use_case(session: AsyncSession) -> GetDatabaseSummary:
    return GetDatabaseSummary(session)


def get_instrument_removal_preview_use_case(session: AsyncSession) -> GetInstrumentRemovalPreview:
    return GetInstrumentRemovalPreview(session)


def get_remove_instrument_from_list_use_case(session: AsyncSession) -> RemoveInstrumentFromList:
    return RemoveInstrumentFromList(session)


def get_delete_instrument_use_case(session: AsyncSession) -> DeleteInstrument:
    return DeleteInstrument(session)


def get_list_orphan_instruments_use_case(session: AsyncSession) -> ListOrphanInstruments:
    return ListOrphanInstruments(session)


def get_purge_orphan_instruments_use_case(session: AsyncSession) -> PurgeOrphanInstruments:
    return PurgeOrphanInstruments(session)


def get_list_closed_simulated_accounts_use_case(
    session: AsyncSession,
) -> ListClosedSimulatedAccounts:
    return ListClosedSimulatedAccounts(session)


def get_purge_closed_simulated_accounts_use_case(
    session: AsyncSession,
) -> PurgeClosedSimulatedAccounts:
    return PurgeClosedSimulatedAccounts(session)


def get_instrument_data_status_use_case(session: AsyncSession) -> GetInstrumentDataStatus:
    settings = get_settings()
    return GetInstrumentDataStatus(
        get_instrument_repository(session),
        get_ohlcv_repository(session),
        get_instrument_detail_use_case(session),
        settings.xtb_bridge_url,
    )


def get_live_quote_use_case(session: AsyncSession) -> GetInstrumentLiveQuote:
    settings = get_settings()
    return GetInstrumentLiveQuote(
        get_instrument_repository(session),
        settings.xtb_bridge_url,
    )


def get_live_quotes_use_case(session: AsyncSession) -> GetInstrumentLiveQuotes:
    settings = get_settings()
    return GetInstrumentLiveQuotes(
        get_instrument_repository(session),
        settings.xtb_bridge_url,
    )


def get_market_status_use_case() -> GetMarketStatus:
    return GetMarketStatus(get_settings().xtb_bridge_url)


def get_fx_rate_use_case() -> GetFxRate:
    return GetFxRate()


def get_list_backtests_use_case(session: AsyncSession) -> ListBacktestRuns:
    return ListBacktestRuns(get_backtest_repository(session))


def get_prune_backtests_use_case(session: AsyncSession) -> PruneBacktestRuns:
    return PruneBacktestRuns(get_backtest_repository(session))


def get_backtest_run_use_case(session: AsyncSession) -> GetBacktestRun:
    return GetBacktestRun(get_backtest_repository(session))


def get_run_backtest_use_case(session: AsyncSession) -> RunAndSaveBacktest:
    return RunAndSaveBacktest(
        get_instrument_repository(session),
        get_ohlcv_repository(session),
        get_backtest_repository(session),
        get_strategy_definition_repository(session),
        get_research_trial_repository(session),
        get_research_evidence_repository(session),
        get_hypothesis_repository(session),
        get_hypothesis_belief_repository(session),
    )


def get_run_scan_use_case(session: AsyncSession) -> RunScan:
    instruments = get_instrument_repository(session)
    return RunScan(
        instruments,
        get_ohlcv_repository(session),
        get_strategy_definition_repository(session),
        get_list_repository(session),
        feature_cache=get_feature_cache(),
        feature_port=get_feature_port(),
        event_bus=get_platform_event_bus(session),
        fundamentals_batch_refresher=RefreshFundamentalsBatch(instruments),
    )


def get_scan_job_repository(session: AsyncSession) -> SqlAlchemyScanJobRepository:
    return SqlAlchemyScanJobRepository(session)


def get_data_snapshot_repository(session: AsyncSession) -> SqlAlchemyDataSnapshotRepository:
    return SqlAlchemyDataSnapshotRepository(session)


def get_scan_manifest_repository(session: AsyncSession) -> SqlAlchemyScanManifestRepository:
    return SqlAlchemyScanManifestRepository(session)


def get_persist_scan_manifest_use_case(session: AsyncSession) -> PersistScanManifest:
    return PersistScanManifest(
        get_data_snapshot_repository(session),
        get_scan_manifest_repository(session),
    )


def get_scan_manifest_use_case(session: AsyncSession) -> GetScanManifest:
    return GetScanManifest(get_scan_manifest_repository(session))


def get_enqueue_scan_job_use_case(session: AsyncSession) -> EnqueueScanJob:
    settings = get_settings()
    backend = settings.scan_queue_backend.lower()
    redis_queue = None
    arq_queue = None
    if backend == "redis":
        redis_queue = ScanJobRedisQueue(settings.redis_url)
    elif backend == "arq":
        arq_queue = ScanJobArqQueue(settings.redis_url)
    return EnqueueScanJob(
        get_scan_job_repository(session),
        get_list_repository(session),
        redis_queue=redis_queue,
        arq_queue=arq_queue,
    )


def get_scan_job_use_case(session: AsyncSession) -> GetScanJob:
    return GetScanJob(get_scan_job_repository(session))


def get_list_scan_jobs_use_case(session: AsyncSession) -> ListScanJobs:
    return ListScanJobs(get_scan_job_repository(session))


def get_process_scan_job_use_case(session: AsyncSession) -> ProcessScanJob:
    return ProcessScanJob(
        get_scan_job_repository(session),
        get_run_scan_use_case(session),
        get_feature_cache(),
        get_persist_scan_manifest_use_case(session),
        tracker_repository=get_tracker_definition_repository(session),
        policy_repository=get_execution_policy_repository(session),
        execution_router=get_execution_router_use_case(session),
    )


def get_run_sma_grid_optimize_use_case(session: AsyncSession) -> RunSmaGridOptimize:
    return RunSmaGridOptimize(
        get_instrument_repository(session),
        get_ohlcv_repository(session),
    )


def get_optimization_run_repository(session: AsyncSession) -> SqlAlchemyOptimizationRunRepository:
    return SqlAlchemyOptimizationRunRepository(session)


def get_run_sma_grid_optimize_and_save_use_case(session: AsyncSession) -> RunSmaGridOptimizeAndSave:
    return RunSmaGridOptimizeAndSave(
        get_run_sma_grid_optimize_use_case(session),
        get_optimization_run_repository(session),
        get_research_trial_repository(session),
        get_cognitive_repository(session),
        get_research_evidence_repository(session),
        get_hypothesis_belief_repository(session),
    )


def get_enqueue_optimization_run_use_case(session: AsyncSession) -> EnqueueOptimizationRun:
    settings = get_settings()
    arq_queue = None
    if settings.scan_queue_backend.lower() == "arq":
        arq_queue = ScanJobArqQueue(settings.redis_url)
    return EnqueueOptimizationRun(get_optimization_run_repository(session), arq_queue=arq_queue)


def get_optimization_run_use_case(session: AsyncSession) -> GetOptimizationRun:
    return GetOptimizationRun(get_optimization_run_repository(session))


def get_list_optimization_runs_use_case(session: AsyncSession) -> ListOptimizationRuns:
    return ListOptimizationRuns(get_optimization_run_repository(session))


def get_process_optimization_run_use_case(session: AsyncSession) -> ProcessOptimizationRun:
    return ProcessOptimizationRun(
        get_optimization_run_repository(session),
        get_run_sma_grid_optimize_use_case(session),
        get_research_trial_repository(session),
        get_cognitive_repository(session),
        get_research_evidence_repository(session),
        get_hypothesis_belief_repository(session),
    )


def get_strategy_definition_repository(
    session: AsyncSession,
) -> SqlAlchemyStrategyDefinitionRepository:
    return SqlAlchemyStrategyDefinitionRepository(session)


def get_list_strategies_use_case(session: AsyncSession) -> ListStrategyDefinitions:
    return ListStrategyDefinitions(get_strategy_definition_repository(session))


def get_strategy_definition_use_case(session: AsyncSession) -> GetStrategyDefinition:
    return GetStrategyDefinition(get_strategy_definition_repository(session))


def get_create_strategy_from_preset_use_case(session: AsyncSession) -> CreateStrategyFromPreset:
    return CreateStrategyFromPreset(get_strategy_definition_repository(session))


def get_create_strategy_use_case(session: AsyncSession) -> CreateStrategyDefinition:
    return CreateStrategyDefinition(get_strategy_definition_repository(session))


def get_update_strategy_use_case(session: AsyncSession) -> UpdateStrategyDefinition:
    return UpdateStrategyDefinition(get_strategy_definition_repository(session))


def get_delete_strategy_use_case(session: AsyncSession) -> DeleteStrategyDefinition:
    return DeleteStrategyDefinition(get_strategy_definition_repository(session))


def get_tracker_definition_repository(
    session: AsyncSession,
) -> SqlAlchemyTrackerDefinitionRepository:
    return SqlAlchemyTrackerDefinitionRepository(session)


def get_list_trackers_use_case(session: AsyncSession) -> ListTrackerDefinitions:
    return ListTrackerDefinitions(get_tracker_definition_repository(session))


def get_list_trackers_for_list_use_case(session: AsyncSession) -> ListTrackerDefinitionsForList:
    return ListTrackerDefinitionsForList(get_tracker_definition_repository(session))


def get_tracker_definition_use_case(session: AsyncSession) -> GetTrackerDefinition:
    return GetTrackerDefinition(get_tracker_definition_repository(session))


def get_create_tracker_use_case(session: AsyncSession) -> CreateTrackerDefinition:
    return CreateTrackerDefinition(
        get_tracker_definition_repository(session),
        get_strategy_definition_repository(session),
    )


def get_update_tracker_use_case(session: AsyncSession) -> UpdateTrackerDefinition:
    return UpdateTrackerDefinition(
        get_tracker_definition_repository(session),
        get_strategy_definition_repository(session),
    )


def get_delete_tracker_use_case(session: AsyncSession) -> DeleteTrackerDefinition:
    return DeleteTrackerDefinition(get_tracker_definition_repository(session))


def get_run_tracker_scan_use_case(session: AsyncSession) -> RunTrackerScan:
    return RunTrackerScan(
        get_tracker_definition_repository(session),
        get_run_scan_use_case(session),
        policy_repository=get_execution_policy_repository(session),
        execution_router=get_execution_router_use_case(session),
    )


def get_enqueue_tracker_scan_job_use_case(session: AsyncSession) -> EnqueueTrackerScanJob:
    return EnqueueTrackerScanJob(
        get_tracker_definition_repository(session),
        get_enqueue_scan_job_use_case(session),
    )


def get_process_tracker_schedules_use_case(session: AsyncSession) -> ProcessTrackerSchedules:
    return ProcessTrackerSchedules(
        get_tracker_definition_repository(session),
        get_list_repository(session),
        get_ohlcv_repository(session),
        get_enqueue_tracker_scan_job_use_case(session),
    )


def get_execution_policy_repository(session: AsyncSession) -> SqlAlchemyExecutionPolicyRepository:
    return SqlAlchemyExecutionPolicyRepository(session)


def get_list_execution_policies_use_case(session: AsyncSession) -> ListExecutionPolicies:
    return ListExecutionPolicies(get_execution_policy_repository(session))


def get_execution_policy_use_case(session: AsyncSession) -> GetExecutionPolicy:
    return GetExecutionPolicy(get_execution_policy_repository(session))


def get_create_execution_policy_use_case(session: AsyncSession) -> CreateExecutionPolicy:
    return CreateExecutionPolicy(
        get_execution_policy_repository(session),
        get_strategy_definition_repository(session),
        get_account_repository(session),
    )


def get_update_execution_policy_use_case(session: AsyncSession) -> UpdateExecutionPolicy:
    return UpdateExecutionPolicy(
        get_execution_policy_repository(session),
        get_strategy_definition_repository(session),
        get_account_repository(session),
    )


def get_delete_execution_policy_use_case(session: AsyncSession) -> DeleteExecutionPolicy:
    return DeleteExecutionPolicy(get_execution_policy_repository(session))


def get_cognitive_repository(session: AsyncSession) -> SqlAlchemyCognitiveRepository:
    return SqlAlchemyCognitiveRepository(session)


class _EdgeReportAdapter:
    """Un EDGE report lookup port que envuelve el CognitiveStore (record→domain)."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def latest_edge_report(
        self,
        *,
        strategy_or_signal_ref: str | None = None,
        account_id: str | None = None,
    ) -> Any:
        from bolsa_application.cognitive_persistence import record_to_edge_report

        rec = await self._store.latest_edge_report(
            strategy_or_signal_ref=strategy_or_signal_ref,
            account_id=account_id,
        )
        if rec is None and strategy_or_signal_ref and account_id:
            # Fallback: último del account si no hay match por estrategia
            rec = await self._store.latest_edge_report(account_id=account_id)
        if rec is None:
            return None
        return record_to_edge_report(rec)


def get_propose_recommendation_use_case(session: AsyncSession) -> Any:
    """F3 propose — wiring completo del pipeline (ports flag-safe, sin cambio de wire)."""
    from bolsa_application.propose_recommendation import ProposeRecommendationFromTa
    from bolsa_application.shared_event_calendar import get_shared_market_event_calendar
    from bolsa_market.macro_snapshot import YahooMacroSnapshotPort
    from bolsa_market.news_snapshot import YahooNewsEventPort

    instruments = get_instrument_repository(session)
    calendar = get_shared_market_event_calendar()
    cognitive = get_cognitive_repository(session)
    return ProposeRecommendationFromTa(
        get_ohlcv_repository(session),
        get_feature_port(),
        instruments,
        fundamentals=instruments,
        macro_port=YahooMacroSnapshotPort(),
        edge_reports=_EdgeReportAdapter(cognitive),
        event_calendar=calendar,
        news_port=YahooNewsEventPort(calendar),
        cognitive_store=cognitive,
        prediction_store=get_prediction_repository(session),
    )


def get_confirm_intent_use_case(session: AsyncSession) -> Any:
    """F3 confirm — wiring del ConfirmRecommendationIntent (execute_trade flag-safe)."""
    from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent

    return ConfirmRecommendationIntent(
        cognitive_store=get_cognitive_repository(session),
        execute_trade=get_execute_trade_use_case(session),
    )


def get_prediction_repository(session: AsyncSession) -> SqlAlchemyPredictionRepository:
    from bolsa_infrastructure.database.repositories.prediction_repository import (
        SqlAlchemyPredictionRepository,
    )

    return SqlAlchemyPredictionRepository(session)


def get_investor_profile_repository(
    session: AsyncSession,
) -> SqlAlchemyInvestorProfileRepository:
    return SqlAlchemyInvestorProfileRepository(session)


def get_execution_router_use_case(session: AsyncSession) -> ExecutionRouter:
    from bolsa_application.shared_event_calendar import get_shared_market_event_calendar

    return ExecutionRouter(
        get_execution_policy_repository(session),
        get_account_repository(session),
        get_strategy_definition_repository(session),
        get_backtest_repository(session),
        get_execute_trade_use_case(session),
        get_portfolio_summary_use_case(session),
        event_bus=get_platform_event_bus(session),
        event_calendar=get_shared_market_event_calendar(),
        cognitive_store=get_cognitive_repository(session),
        profile_store=get_investor_profile_repository(session),  # type: ignore[arg-type]
    )


def get_platform_event_repository(session: AsyncSession) -> SqlAlchemyPlatformEventRepository:
    return SqlAlchemyPlatformEventRepository(session)


def get_platform_event_bus(session: AsyncSession) -> PlatformEventBus:
    return PlatformEventBus(get_platform_event_repository(session))


def get_list_platform_events_use_case(session: AsyncSession) -> ListPlatformEvents:
    return ListPlatformEvents(get_platform_event_repository(session))


def get_execute_scan_job_hits_use_case(session: AsyncSession) -> ExecuteScanJobHits:
    return ExecuteScanJobHits(
        get_scan_job_repository(session),
        get_execution_router_use_case(session),
    )


def get_position_policy_repository(session: AsyncSession) -> SqlAlchemyPositionPolicyRepository:
    return SqlAlchemyPositionPolicyRepository(session)


def get_list_position_policies_use_case(session: AsyncSession) -> ListPositionPolicies:
    return ListPositionPolicies(get_position_policy_repository(session))


def get_position_policy_use_case(session: AsyncSession) -> GetPositionPolicy:
    return GetPositionPolicy(get_position_policy_repository(session))


def get_position_policy_for_holding_use_case(session: AsyncSession) -> GetPositionPolicyForHolding:
    return GetPositionPolicyForHolding(get_position_policy_repository(session))


def get_create_position_policy_use_case(session: AsyncSession) -> CreatePositionPolicy:
    return CreatePositionPolicy(
        get_position_policy_repository(session),
        get_account_repository(session),
        get_instrument_repository(session),
        get_strategy_definition_repository(session),
        get_execution_policy_repository(session),
    )


def get_update_position_policy_use_case(session: AsyncSession) -> UpdatePositionPolicy:
    return UpdatePositionPolicy(
        get_position_policy_repository(session),
        get_strategy_definition_repository(session),
        get_execution_policy_repository(session),
    )


def get_delete_position_policy_use_case(session: AsyncSession) -> DeletePositionPolicy:
    return DeletePositionPolicy(get_position_policy_repository(session))


def get_evaluate_position_exits_use_case(session: AsyncSession) -> EvaluatePositionExits:
    return EvaluatePositionExits(
        get_portfolio_summary_use_case(session),
        get_position_policy_for_holding_use_case(session),
        get_strategy_definition_repository(session),
        get_execution_policy_repository(session),
        get_ohlcv_bars_use_case(session),
        get_execution_router_use_case(session),
    )


def get_draft_strategy_from_prompt_use_case() -> DraftStrategyFromPrompt:
    return DraftStrategyFromPrompt()


def get_draft_indicator_from_prompt_use_case() -> DraftIndicatorFromPrompt:
    return DraftIndicatorFromPrompt()


def get_sync_scheduler_repository(session: AsyncSession) -> SqlAlchemySyncSchedulerRepository:
    return SqlAlchemySyncSchedulerRepository(session)


def get_sync_settings_use_case(session: AsyncSession) -> GetSyncSettings:
    return GetSyncSettings(get_sync_scheduler_repository(session))


def get_update_sync_settings_use_case(session: AsyncSession) -> UpdateSyncSettings:
    return UpdateSyncSettings(get_sync_scheduler_repository(session))


def get_list_sync_queue_use_case(session: AsyncSession) -> ListSyncQueue:
    return ListSyncQueue(get_sync_scheduler_repository(session))


def get_enqueue_stale_use_case(session: AsyncSession) -> EnqueueStaleInstruments:
    return EnqueueStaleInstruments(
        get_instrument_repository(session),
        get_sync_scheduler_repository(session),
        get_instrument_data_status_use_case(session),
    )


def get_process_sync_queue_use_case(session: AsyncSession) -> ProcessNextSyncQueueItem:
    return ProcessNextSyncQueueItem(
        get_sync_scheduler_repository(session),
        get_sync_instrument_use_case(session),
    )


def get_pending_order_repository(session: AsyncSession) -> SqlAlchemyPendingOrderRepository:
    return SqlAlchemyPendingOrderRepository(session)


def get_list_pending_orders_use_case(session: AsyncSession) -> ListPendingOrders:
    return ListPendingOrders(get_pending_order_repository(session), get_account_repository(session))


def get_create_pending_order_use_case(session: AsyncSession) -> CreatePendingOrder:
    return CreatePendingOrder(
        get_pending_order_repository(session),
        get_account_repository(session),
    )


def get_delete_pending_order_use_case(session: AsyncSession) -> DeletePendingOrder:
    return DeletePendingOrder(
        get_pending_order_repository(session),
        get_account_repository(session),
    )


def get_account_core_r_state_use_case(session: AsyncSession) -> GetAccountCoreRState:
    return GetAccountCoreRState(get_core_r_repository(session))


def get_sync_core_r_state_use_case(session: AsyncSession) -> SyncAccountCoreRState:
    return SyncAccountCoreRState(get_core_r_repository(session))


def get_account_supervised_f3_state_use_case(
    session: AsyncSession,
) -> GetAccountSupervisedF3State:
    return GetAccountSupervisedF3State(get_supervised_f3_repository(session))


def get_sync_supervised_f3_state_use_case(session: AsyncSession) -> SyncAccountSupervisedF3State:
    return SyncAccountSupervisedF3State(get_supervised_f3_repository(session))


def get_account_mandates_use_case(session: AsyncSession) -> GetAccountMandates:
    return GetAccountMandates(get_mandate_repository(session))


def get_sync_account_mandates_use_case(session: AsyncSession) -> SyncAccountMandates:
    return SyncAccountMandates(get_mandate_repository(session))


def get_daily_opinion_service(session: AsyncSession) -> DailyOpinionService:
    return DailyOpinionService(
        SqlAlchemyInstrumentDailyOpinionRepository(session),
        SqlAlchemyInstrumentStrategyTopRepository(session),
        get_ohlcv_repository(session),
        get_instrument_repository(session),
    )


def get_daily_opinion_telemetry_service(session: AsyncSession) -> DailyOpinionTelemetryService:
    return DailyOpinionTelemetryService(
        SqlAlchemyInstrumentDailyOpinionRepository(session),
        get_ohlcv_repository(session),
    )
