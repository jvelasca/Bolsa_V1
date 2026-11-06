"""F3a (D3) + R12-SCHED — scheduler worker = crons only, fuera de FastAPI.

Valida que el proceso dedicado ``bolsa_api.workers.scheduler_worker`` active los
loops periódicos y que **nunca** embeba scan/optimize (autoridad de colas:
``arq_worker`` o ``queue_poll_worker`` según backend).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from bolsa_api.background.alert_delivery_worker import (  # type: ignore[import-untyped]
    start_alert_delivery_worker,
)
from bolsa_api.background.auto_ops_job_worker import (  # type: ignore[import-untyped]
    start_auto_ops_job_worker,
)
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
from bolsa_api.background.paper_evidence_snapshot_worker import (  # type: ignore[import-untyped]
    start_paper_evidence_snapshot_worker,
)
from bolsa_api.background.scan_queue_health import (  # type: ignore[import-untyped]
    start_scan_queue_health_worker,
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
from bolsa_api.background.window_day_watch_worker import (  # type: ignore[import-untyped]
    start_window_day_watch,
)
from bolsa_api.workers import scheduler_worker  # type: ignore[import-untyped]


def test_event_loop_starters_reunen_todos_los_workers_periodicos() -> None:
    starters = scheduler_worker._event_loop_starters()
    expected = {
        start_daily_alert_evaluator,
        start_signal_alert_evaluator,
        # v2.88.137 (AUDITORIA3): drena el OUTBOX de alertas (reintentos + DEAD_LETTER).
        start_alert_delivery_worker,
        start_tracker_schedule_worker,
        start_fa_weekly_worker,
        start_core_r_cron_worker,
        start_estudio_eod_opinion_worker,
        # v2.88.145: cola durable de trabajos AUTO (estudio_daily | dia_d_replay).
        start_auto_ops_job_worker,
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
        # Frente B (ADR-046): driver periódico de la foto durable PAPER.
        start_paper_evidence_snapshot_worker,
        # V2.22/A9 (M5): AUTO bucle continuo SIM-ONLY (env-gated, default OFF).
        start_auto_sim_worker,
        # V2.26/A10: orquestador del Strategy Lifecycle (env-gated, default OFF,
        # SIM-only). Promociona solo por Promotion Gate + hold-out estricto.
        start_auto_orchestrator,
        # v2.88.140: vigía diario de la ventana PAPER (alerta de "día perdido"), ON.
        start_window_day_watch,
        # DS-1: vigía periódico de ``scan_jobs`` (declara autoridad y recupera huérfanos).
        start_scan_queue_health_worker,
    }
    assert set(starters) == expected


def test_scheduler_no_embebe_scan_ni_optimize() -> None:
    """R12-SCHED: el scheduler no exporta ni reúne starters de cola."""
    starters = scheduler_worker._event_loop_starters()
    assert start_scan_worker not in starters
    assert start_optimization_worker not in starters
    assert not hasattr(scheduler_worker, "_queue_loop_starters")


def test_auto_identity_failure_does_not_take_down_the_other_workers(monkeypatch) -> None:
    """R-4 (verificación 2026-10-26 §8): blast radius acotado al worker AUTO.

    AUTO ON + composición PG (session_factory no nulo) sin ``AUTO_ENGINE_SIM_ENGINE_ID``:
    ``start_auto_sim_worker`` falla con ``EngineIdentityMissingError``. El scheduler debe
    registrarlo y seguir arrancando el resto; AUTO queda simplemente ausente.
    """
    from bolsa_api.background import auto_simulation_worker as auto_module  # noqa: PLC0415
    from bolsa_api.background.auto_simulation_worker import (  # noqa: PLC0415
        EngineIdentityMissingError,
    )

    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.delenv("AUTO_ENGINE_SIM_ENGINE_ID", raising=False)
    # La cuenta SIM se lee del módulo al llamar: se fija para llegar a la comprobación de
    # identidad (si no, el worker se apaga antes por «sin cuenta» y no se probaría nada).
    monkeypatch.setattr(auto_module, "SIM_ACCOUNT_ID", "00000000-0000-0000-0000-000000000001")

    started: list[str] = []

    def _healthy(name: str):
        def _start(_session_factory):
            started.append(name)
            return None

        return _start

    tasks = scheduler_worker._start_workers(
        [start_auto_sim_worker, _healthy("alertas"), _healthy("custodia")],
        object(),  # type: ignore[arg-type] — el AUTO falla antes de tocar la sesión.
    )

    assert tasks == []
    assert started == ["alertas", "custodia"], (
        "el fallo de identidad de AUTO no puede abortar los demás starters"
    )

    # Y el arranque DIRECTO sigue siendo explícito (no se silencia en el worker).
    import pytest  # noqa: PLC0415

    with pytest.raises(EngineIdentityMissingError):
        start_auto_sim_worker(
            session_factory=object(),
            account_id="00000000-0000-0000-0000-000000000001",
            interval_seconds=60.0,
        )


# ── T-1: quién drena ``scan_jobs`` y qué pasa si nadie lo hace ────────────────────


class _StubResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)

    def scalars(self) -> _StubResult:
        return self

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None


class _StubSession:
    """Sesión mínima: devuelve filas ``(status, created_at, updated_at)`` de ``scan_jobs``."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    async def __aenter__(self) -> _StubSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, _stmt: object) -> _StubResult:
        return _StubResult(self._rows)


def _factory(rows: list[object]):
    return lambda: _StubSession(rows)


def test_scheduler_declares_the_scan_queue_authority(monkeypatch, caplog) -> None:
    """T-1: el arranque dice QUIÉN drena la cola (inline ⇒ proceso dedicado)."""
    from bolsa_api.background.scan_queue_health import report_scan_queue_health

    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "inline"})(),
    )
    with caplog.at_level("INFO", logger="bolsa_api.background.scan_queue_health"):
        health = asyncio.run(report_scan_queue_health(_factory([])))

    assert health is not None
    assert health.authority == "queue_poll_worker"
    assert health.reason == "scan_queue_healthy"
    record = caplog.records[-1]
    assert record.levelname == "INFO"
    assert "authority=queue_poll_worker" in record.getMessage()
    assert "reason=scan_queue_healthy" in record.getMessage()


def test_arq_backend_names_the_other_authority(monkeypatch, caplog) -> None:
    from bolsa_api.background.scan_queue_health import report_scan_queue_health

    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "arq"})(),
    )
    with caplog.at_level("INFO", logger="bolsa_api.background.scan_queue_health"):
        health = asyncio.run(report_scan_queue_health(_factory([])))

    assert health is not None
    assert health.authority == "arq_worker"


def test_stalled_scan_queue_is_an_error_with_actionable_reason(monkeypatch, caplog) -> None:
    """T-1: un ``pending`` viejo ⇒ ERROR con ``scan_queue_stalled`` y la acción concreta."""
    from bolsa_api.background.scan_queue_health import report_scan_queue_health

    sixty_minutes_ago = datetime.now(UTC) - timedelta(minutes=60)
    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "inline"})(),
    )
    with caplog.at_level("INFO", logger="bolsa_api.background.scan_queue_health"):
        health = asyncio.run(
            report_scan_queue_health(
                _factory([("pending", sixty_minutes_ago, sixty_minutes_ago)])
            )
        )

    assert health is not None
    assert health.pending == 1
    assert health.stalled is True
    error = caplog.records[-1]
    assert error.levelname == "ERROR"
    message = error.getMessage()
    assert "reason=scan_queue_stalled" in message
    assert "bolsa-queue-poll-worker" in message


def test_unreadable_scan_queue_is_declared_and_does_not_abort(monkeypatch, caplog) -> None:
    """T-1: si la cola no se puede leer, se declara ``scan_queue_unknown`` y se sigue."""
    from bolsa_api.background.scan_queue_health import report_scan_queue_health

    def _boom():
        raise RuntimeError("db caída")

    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "inline"})(),
    )
    with caplog.at_level("INFO", logger="bolsa_api.background.scan_queue_health"):
        health = asyncio.run(report_scan_queue_health(_boom))  # type: ignore[arg-type]

    assert health is None
    assert caplog.records[-1].levelname == "WARNING"
    assert "reason=scan_queue_unknown" in caplog.records[-1].getMessage()


# ── DS-1: el ``processing`` huérfano deja de ser invisible ────────────────────────


def test_stale_processing_is_declared_as_stalled(monkeypatch, caplog) -> None:
    """DS-1: un ``processing`` sin latido es atasco aunque no haya ningún ``pending``.

    Ese estado cuenta en el dedupe del scan diario, así que bloqueaba el reintento del día y
    no aparecía en ningún aviso (antes solo se miraba ``pending``).
    """
    from bolsa_api.background.scan_queue_health import report_scan_queue_health

    two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "inline"})(),
    )
    with caplog.at_level("INFO", logger="bolsa_api.background.scan_queue_health"):
        health = asyncio.run(
            report_scan_queue_health(
                _factory([("processing", two_hours_ago, two_hours_ago)])
            )
        )

    assert health is not None
    assert health.pending == 0
    assert health.processing == 1
    assert health.stale_processing == 1
    assert health.stalled is True
    assert health.reason == "scan_queue_processing_stale"
    error = caplog.records[-1]
    assert error.levelname == "ERROR"
    assert "reason=scan_queue_processing_stale" in error.getMessage()


def test_fresh_processing_is_not_stale(monkeypatch) -> None:
    """DS-1: un ``processing`` reciente es un scan en curso, no un huérfano."""
    from bolsa_api.background.scan_queue_health import report_scan_queue_health

    now = datetime.now(UTC)
    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "inline"})(),
    )
    health = asyncio.run(
        report_scan_queue_health(_factory([("processing", now, now)]))
    )

    assert health is not None
    assert health.stale_processing == 0
    assert health.stalled is False
    assert health.reason == "scan_queue_healthy"


def test_reconcile_requeues_only_when_the_inline_poller_is_the_authority(
    monkeypatch,
) -> None:
    """DS-1: la recuperación depende de la AUTORIDAD (inline reencola, arq declara `failed`)."""
    from bolsa_api.background import scan_queue_health as health_module

    calls: list[dict[str, object]] = []

    class _FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def reap_stale_processing(self, **kwargs: object) -> list[object]:
            calls.append(kwargs)
            return []

    class _Session(_StubSession):
        def __init__(self) -> None:
            super().__init__([])

        async def commit(self) -> None:
            return None

    monkeypatch.setattr(health_module, "SqlAlchemyScanJobRepository", _FakeRepository)
    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "inline"})(),
    )
    health = asyncio.run(health_module.reconcile_scan_queue(lambda: _Session()))

    assert health is not None
    assert calls and calls[0]["requeue"] is True

    monkeypatch.setattr(
        "bolsa_api.background.scan_queue_health.get_settings",
        lambda: type("S", (), {"scan_queue_backend": "arq"})(),
    )
    asyncio.run(health_module.reconcile_scan_queue(lambda: _Session()))
    assert calls[-1]["requeue"] is False

# ── DS-1: el vigía periódico no solapa ciclos ──────────────────────────────────


def _stub_health_settings(**overrides: object):
    """``get_settings`` de mentira con los campos que consume el vigía."""
    base = {
        "scan_queue_backend": "inline",
        "scan_job_processing_stale_seconds": 3600.0,
        "scan_job_processing_max_reaps": 3,
        "scan_queue_health_interval_seconds": 300.0,
    }
    base.update(overrides)
    return lambda: type("S", (), base)()


def test_health_watchdog_never_overlaps_reconcile_cycles(monkeypatch) -> None:
    """DS-1: una reconciliación más lenta que el intervalo NO lanza un ciclo en paralelo.

    El dictamen lo pide explícitamente: dos reconciliadores solapados reencolarían el mismo
    job dos veces. El vigía es secuencial (``await`` dentro del ``while``), y este test lo
    blinda: la concurrencia observada es exactamente 1.
    """
    from bolsa_api.background import scan_queue_health as health_module

    state = {"active": 0, "max_active": 0, "calls": 0}

    async def _slow_reconcile(*_args: object, **_kwargs: object):
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        state["calls"] += 1
        try:
            # Más lento que el intervalo para forzar el solape si el vigía lo permitiera.
            await asyncio.sleep(0.02)
        finally:
            state["active"] -= 1
        return None

    monkeypatch.setattr(health_module, "reconcile_scan_queue", _slow_reconcile)
    monkeypatch.setattr(health_module, "get_settings", _stub_health_settings())
    # Se rebaja el suelo SOLO en el test: el punto es la secuencialidad, no la cadencia.
    monkeypatch.setattr(health_module, "_MIN_HEALTH_INTERVAL_SECONDS", 0.0)

    async def _run() -> None:
        task = asyncio.create_task(
            health_module.scan_queue_health_worker_loop(lambda: None, interval_seconds=0.001)
        )
        await asyncio.sleep(0.3)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(_run())

    assert state["calls"] >= 2, "el vigía debe haber completado más de un ciclo"
    assert state["max_active"] == 1, "nunca dos reconciliaciones simultáneas"


def test_health_watchdog_respects_the_interval_floor(monkeypatch) -> None:
    """DS-1: aunque el settings pida 0.001s, el vigía duerme al menos el suelo (60s)."""
    from bolsa_api.background import scan_queue_health as health_module

    slept: list[float] = []

    class _StopLoop(Exception):
        pass

    async def _reconcile(*_args: object, **_kwargs: object):
        return None

    async def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        raise _StopLoop

    monkeypatch.setattr(health_module, "reconcile_scan_queue", _reconcile)
    monkeypatch.setattr(
        health_module,
        "get_settings",
        _stub_health_settings(scan_queue_health_interval_seconds=0.001),
    )
    monkeypatch.setattr(health_module.asyncio, "sleep", _fake_sleep)

    with pytest.raises(_StopLoop):
        asyncio.run(health_module.scan_queue_health_worker_loop(lambda: None))

    assert slept == [60.0], "el suelo de cadencia es 60s (un loop más rápido solo gasta BD)"
