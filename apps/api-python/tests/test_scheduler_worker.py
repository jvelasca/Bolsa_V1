"""F3a (D3) + R12-SCHED — scheduler worker = crons only, fuera de FastAPI.

Valida que el proceso dedicado ``bolsa_api.workers.scheduler_worker`` active los
loops periódicos y que **nunca** embeba scan/optimize (autoridad de colas:
``arq_worker`` o ``queue_poll_worker`` según backend).
"""

from __future__ import annotations

from bolsa_api.background.auto_orchestrator_worker import (  # type: ignore[import-untyped]
    start_auto_orchestrator,
)
from bolsa_api.background.auto_simulation_worker import (  # type: ignore[import-untyped]
    start_auto_sim_worker,
)
from bolsa_api.background.auto_sync_worker import (  # type: ignore[import-untyped]
    start_auto_sync_worker,
)
from bolsa_api.background.core_r_cron_worker import (  # type: ignore[import-untyped]
    start_core_r_cron_worker,
)
from bolsa_api.background.custody_job_worker import (  # type: ignore[import-untyped]
    start_custody_job_worker,
)
from bolsa_api.background.daily_alert_evaluator import (  # type: ignore[import-untyped]
    start_daily_alert_evaluator,
)
from bolsa_api.background.estudio_eod_opinion_worker import (  # type: ignore[import-untyped]
    start_estudio_eod_opinion_worker,
)
from bolsa_api.background.execution_event_reaper_worker import (  # type: ignore[import-untyped]
    start_execution_event_reaper_worker,
)
from bolsa_api.background.fa_weekly_worker import (  # type: ignore[import-untyped]
    start_fa_weekly_worker,
)
from bolsa_api.background.index_subscribe_worker import (  # type: ignore[import-untyped]
    start_index_subscribe_worker,
)
from bolsa_api.background.lifecycle_outbox_worker import (  # type: ignore[import-untyped]
    start_lifecycle_outbox_worker,
)
from bolsa_api.background.live_order_recovery_worker import (  # type: ignore[import-untyped]
    start_live_order_recovery_worker,
)
from bolsa_api.background.opportunity_daily_scan_worker import (  # type: ignore[import-untyped]
    start_opportunity_daily_scan_worker,
)
from bolsa_api.background.optimization_worker import (  # type: ignore[import-untyped]
    start_optimization_worker,
)
from bolsa_api.background.paper_auto_engine_worker import (  # type: ignore[import-untyped]
    start_paper_auto_engine_worker,
)
from bolsa_api.background.scan_worker import (  # type: ignore[import-untyped]
    start_scan_worker,
)
from bolsa_api.background.signal_alert_evaluator import (  # type: ignore[import-untyped]
    start_signal_alert_evaluator,
)
from bolsa_api.background.tracker_schedule_worker import (  # type: ignore[import-untyped]
    start_tracker_schedule_worker,
)
from bolsa_api.workers import scheduler_worker  # type: ignore[import-untyped]


def test_event_loop_starters_reunen_todos_los_workers_periodicos() -> None:
    starters = scheduler_worker._event_loop_starters()
    expected = {
        start_daily_alert_evaluator,
        start_signal_alert_evaluator,
        start_tracker_schedule_worker,
        start_fa_weekly_worker,
        start_core_r_cron_worker,
        start_estudio_eod_opinion_worker,
        start_auto_sync_worker,
        start_index_subscribe_worker,
        start_custody_job_worker,
        start_opportunity_daily_scan_worker,
        start_lifecycle_outbox_worker,
        start_live_order_recovery_worker,
        # V2.21/A8 (M2): reaper autónomo de APPLYING stale.
        start_execution_event_reaper_worker,
        # V2.21/A8 (M4): AUTO Engine continuo SAFE/dry.
        start_paper_auto_engine_worker,
        # V2.22/A9 (M5): AUTO bucle continuo SIM-ONLY (env-gated, default OFF).
        start_auto_sim_worker,
        # V2.26/A10: orquestador del Strategy Lifecycle (env-gated, default OFF,
        # SIM-only). Promociona solo por Promotion Gate + hold-out estricto.
        start_auto_orchestrator,
    }
    assert set(starters) == expected


def test_scheduler_no_embebe_scan_ni_optimize() -> None:
    """R12-SCHED: el scheduler no exporta ni reúne starters de cola."""
    starters = scheduler_worker._event_loop_starters()
    assert start_scan_worker not in starters
    assert start_optimization_worker not in starters
    assert not hasattr(scheduler_worker, "_queue_loop_starters")
