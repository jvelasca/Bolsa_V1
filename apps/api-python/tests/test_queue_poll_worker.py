"""R12-SCHED / R-8C.2 — queue_poll_worker es la autoridad de poll no-ARQ.

Valida starters scan/optimize cuando el backend no es ``arq``, y lista vacía /
no-op cuando ``arq`` (autoridad = ``arq_worker``).
"""

from __future__ import annotations

from typing import Any

from bolsa_api.background.optimization_worker import (  # type: ignore[import-untyped]
    start_optimization_worker,
)
from bolsa_api.background.scan_worker import (  # type: ignore[import-untyped]
    start_scan_worker,
)
from bolsa_api.workers import queue_poll_worker  # type: ignore[import-untyped]


def _patch_backend(monkeypatch: Any, backend: str) -> None:
    class _Fake:
        scan_queue_backend = backend

    monkeypatch.setattr(queue_poll_worker, "get_settings", lambda: _Fake())


def test_queue_loop_starters_sin_arq_activa_scan_y_optimize(monkeypatch: Any) -> None:
    _patch_backend(monkeypatch, "postgres")
    assert queue_poll_worker._queue_loop_starters() == [
        start_scan_worker,
        start_optimization_worker,
    ]


def test_queue_loop_starters_con_arq_estan_vacios(monkeypatch: Any) -> None:
    _patch_backend(monkeypatch, "arq")
    assert queue_poll_worker._queue_loop_starters() == []


def test_run_con_arq_es_noop(monkeypatch: Any, caplog: Any) -> None:
    _patch_backend(monkeypatch, "arq")
    with caplog.at_level("INFO"):
        queue_poll_worker.run()
    assert any("no-op" in r.message for r in caplog.records)
