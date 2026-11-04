"""P4 (auditoría .183) — el Data Gate de producción exige EVIDENCIA.

Antes de este cierre, un tick sin nada medido se publicaba ``OK``/``ADAPTS``: la política del
worker no pedía evidencia y el worker declaraba ``read_ok=True`` aunque no hubiera lectura
durable. ``OK`` ⇒ reparto completo, así que Adaptive repartía riesgo afirmando una salud de datos
que nadie había medido.

Aquí se prueba por el camino REAL del worker (``_v2_adaptive_data_gate``, el mismo método que usa
el tick), no por la tabla pura del gate —esa vive en
``packages/py/analytics/tests/test_auto_adaptive_data_gate.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_data_gate import (
    DATA_GATE_ADAPTS,
    DATA_GATE_DEGRADED,
    DATA_GATE_LIMITS,
    DATA_GATE_NOTE_EVIDENCE_NOT_PROVIDED,
    DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN,
    DATA_GATE_NOTE_READ_STATE_UNKNOWN,
    DATA_GATE_OK,
    DataGatePolicy,
)
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_adaptive_recovery import AdaptiveStateReading

_ACCOUNT = "acc-1"
_ENGINE = "auto-sim"
_REGIME = "BULL_TREND"
_FLOOR = 0.35


def _worker(*, reading: AdaptiveStateReading | None = None) -> AutoSimulationWorker:
    """Worker mínimo por el mismo camino real (sin ``__init__``)."""
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = _ENGINE
    worker._v2_adaptive_paused_cycles = {}
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_sink_failures = 0
    worker._v2_adaptive_sink_failures_durable = False
    worker._v2_adaptive_journal_anchor_age = None
    worker._v2_adaptive_state_reading = reading
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=True,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    return worker


def _gate(
    worker: AutoSimulationWorker,
    *,
    rows: tuple[Any, ...] = (),
    confidence_by_strategy: Any = None,
    recent_available: bool | None = None,
) -> Any:
    """La lectura del gate por el MISMO método que usa el tick, con el material que se declare."""
    return worker._v2_adaptive_data_gate(
        report=SimpleNamespace(by_strategy=rows),
        confidence=SimpleNamespace(
            by_strategy=confidence_by_strategy, recent_available=recent_available
        ),
        regime=_REGIME,
    )


def test_the_production_policy_requires_evidence() -> None:
    """El gate del worker es el ESTRICTO: un solo sitio, y declara que exige evidencia."""
    assert _worker()._v2_data_gate_policy() == DataGatePolicy(require_evidence=True)
    assert _worker()._v2_data_gate_policy().require_evidence is True


def test_a_tick_without_material_degrades_instead_of_adapting() -> None:
    """Sin ``by_strategy`` no hay nada medido: ``DEGRADED``/``LIMITS``, nunca ``OK``/``ADAPTS``."""
    reading = _gate(_worker())

    assert reading.status == DATA_GATE_DEGRADED
    assert reading.effect == DATA_GATE_LIMITS
    assert reading.adapts is False
    assert DATA_GATE_NOTE_EVIDENCE_NOT_PROVIDED in reading.notes


def test_a_tick_without_a_durable_read_declares_unknown_instead_of_ok() -> None:
    """No tener lectura durable ya no se publica como ``read_ok=True``: es ``unknown``."""
    reading = _gate(_worker(reading=None))

    assert reading.read_state == "unknown"
    assert DATA_GATE_NOTE_READ_STATE_UNKNOWN in reading.notes
    assert DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN in reading.notes


def test_a_tick_with_measured_facts_and_a_healthy_read_adapts() -> None:
    """El control positivo: con completitud, ventana y lectura sana el gate sigue abriendo."""
    row = SimpleNamespace(
        risk_measurement="COMPLETE",
        results_measurement="COMPLETE",
    )
    reading = _gate(
        _worker(reading=AdaptiveStateReading()),
        rows=(row,),
        confidence_by_strategy=("v42",),
        recent_available=True,
    )

    assert reading.status == DATA_GATE_OK
    assert reading.effect == DATA_GATE_ADAPTS
    assert reading.read_state == "ok"
