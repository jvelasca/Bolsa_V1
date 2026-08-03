from fastapi import APIRouter

from bolsa_api.api.v1.routes import (
    accounts,
    ai_governance,
    alerts,
    auth,
    backtests,
    core_r,
    database,
    drawing_replay,
    execution_policies,
    features,
    health,
    indicators_compute,
    indicators_draft,
    instrument_strategy_tops,
    instruments,
    investor_profiles,
    lists,
    mandates,
    market,
    market_indices,
    paper_d,
    pending_orders,
    platform_events,
    portfolio,
    position_policies,
    predictions,
    research,
    scans,
    signal_alerts,
    signals_evaluate,
    strategies,
    supervised_f3,
    sync,
    trackers,
    workspaces,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(ai_governance.router, tags=["ai"])
api_v1_router.include_router(features.router, tags=["features"])
api_v1_router.include_router(predictions.router, tags=["predictions"])
api_v1_router.include_router(database.router, tags=["database"])
api_v1_router.include_router(auth.router, tags=["auth"])
api_v1_router.include_router(instruments.router, tags=["instruments"])
api_v1_router.include_router(instrument_strategy_tops.router, tags=["instrument-strategy-tops"])
api_v1_router.include_router(indicators_compute.router, tags=["indicators"])
api_v1_router.include_router(indicators_draft.router, tags=["indicators"])
api_v1_router.include_router(signals_evaluate.router, tags=["signals"])
api_v1_router.include_router(scans.router, tags=["scans"])
api_v1_router.include_router(paper_d.router, tags=["paper-d"])
api_v1_router.include_router(signal_alerts.router, tags=["signal-alerts"])
api_v1_router.include_router(drawing_replay.router, tags=["drawings"])
api_v1_router.include_router(lists.router, tags=["lists"])
api_v1_router.include_router(market_indices.router, tags=["market-indices"])
api_v1_router.include_router(alerts.router, tags=["alerts"])
api_v1_router.include_router(accounts.router, tags=["accounts"])
api_v1_router.include_router(mandates.router, tags=["mandates"])
api_v1_router.include_router(core_r.router, tags=["core-r"])
api_v1_router.include_router(supervised_f3.router, tags=["supervised-f3"])
api_v1_router.include_router(investor_profiles.router, tags=["investor-profiles"])
api_v1_router.include_router(portfolio.router, tags=["portfolio"])
api_v1_router.include_router(backtests.router, tags=["backtests"])
api_v1_router.include_router(research.router, tags=["research"])
api_v1_router.include_router(strategies.router, tags=["strategies"])
api_v1_router.include_router(trackers.router, tags=["trackers"])
api_v1_router.include_router(execution_policies.router, tags=["execution-policies"])
api_v1_router.include_router(position_policies.router, tags=["position-policies"])
api_v1_router.include_router(platform_events.router, tags=["platform-events"])
api_v1_router.include_router(market.router, tags=["market"])
api_v1_router.include_router(workspaces.router, tags=["workspaces"])
api_v1_router.include_router(sync.router, tags=["sync"])
api_v1_router.include_router(pending_orders.router, tags=["pending-orders"])
