"""F3a (D3) — el scheduler worker reúne los workers programados fuera de FastAPI.

Valida que el proceso dedicado ``bolsa_api.workers.scheduler_worker`` active los
loops periódicos y que los loops scan/optimize inline solo se activen cuando el
backend de cola NO es ``arq`` (si es ``arq``, los gestiona ``arq_worker``).
"""

from __future__ import annotations

from typing import Any

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
from bolsa_api.background.fa_weekly_worker import (  # type: ignore[import-untyped]
    start_fa_weekly_worker,
)
from bolsa_api.background.index_subscribe_worker import (  # type: ignore[import-untyped]
    start_index_subscribe_worker,
)
from bolsa_api.background.optimization_worker import (  # type: ignore[import-untyped]
    start_optimization_worker,
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
    }
    assert set(starters) == expected


def _patch_backend(monkeypatch: Any, backend: str) -> None:
    class _Fake:
        scan_queue_backend = backend

    monkeypatch.setattr(scheduler_worker, "get_settings", lambda: _Fake())


def test_queue_loop_starters_sin_arq_activa_scan_y_optimize(monkeypatch: Any) -> None:
    _patch_backend(monkeypatch, "postgres")
    assert scheduler_worker._queue_loop_starters() == [
        start_scan_worker,
        start_optimization_worker,
    ]


def test_queue_loop_starters_con_arq_estan_vacios(monkeypatch: Any) -> None:
    _patch_backend(monkeypatch, "arq")
    assert scheduler_worker._queue_loop_starters() == []
