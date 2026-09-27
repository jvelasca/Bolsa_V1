"""V2.80 · AUTO-MATERIAL-8 — MARKET WINDOW: contratos puros de la serie diaria.

Lo que se fija aquí (sin red ni PostgreSQL):

* La fila diaria publica el LINAJE (cuenta, instrumentos, versiones, ``cycle_id``) y declara sus
  huecos como ``None``/``UNKNOWN`` — nunca un ``0`` inventado.
* Los dos canales siguen separados: VETOS de entrada por un lado, eventos de POSICIÓN por otro.
* El gate cuenta **cubos de CALENDARIO** (días distintos), no filas, y exige ≥2 episodios de
  régimen y ≥32 ciclos medibles; si falta algo, el veredicto es ``INCONCLUSIVE``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE, MEASUREMENT_UNKNOWN
from bolsa_application.market_operability import (
    ENTRY_DECISION_EVENT,
    POSITION_JOURNAL_EVENTS,
    STATE_OPERATED,
    STATE_UNKNOWN,
    STATE_UNRESOLVED,
)
from bolsa_application.operability_window import (
    FUNNEL_STEPS,
    MARKET_WINDOW_INCONCLUSIVE,
    MARKET_WINDOW_MIN_CYCLES,
    MARKET_WINDOW_MIN_DAYS,
    MARKET_WINDOW_MIN_EPISODES,
    MARKET_WINDOW_READY,
    UNRESOLVED_AGE_BUCKETS,
    build_window_row,
    render_window_html,
    render_window_series,
    unresolved_age,
    window_gate,
)

_ENTRY_EVENT = ENTRY_DECISION_EVENT
_POSITION_EVENT = sorted(POSITION_JOURNAL_EVENTS)[0]


def _entry(
    *reason_codes: str, event: str = _ENTRY_EVENT, at: datetime | None = None
) -> dict[str, Any]:
    """Entrada de journal con la MISMA forma que el registro durable: el evento vive en ``payload``."""
    entry: dict[str, Any] = {"payload": {"event": event, "reasonCodes": list(reason_codes)}}
    if at is not None:
        entry["created_at"] = at
    return entry


def _cycle(
    cycle_id: str,
    *,
    pnl: float = 10.0,
    risk: float = 5.0,
    regime: str = "trend_up",
    version: str = "vA",
    instrument: str = "AAA",
) -> dict[str, Any]:
    return {
        "cycleId": cycle_id,
        "pnl": pnl,
        "riskAmount": risk,
        "regime": regime,
        "strategyVersion": version,
        "instrumentId": instrument,
    }


def test_build_window_row_publishes_lineage_and_the_two_channels() -> None:
    row = build_window_row(
        "2026-09-27",
        account="acc-1",
        entries=[
            _entry("regime_invalid", "approved"),
            _entry("protect_requested", event=_POSITION_EVENT),
        ],
        cycles=[_cycle("cyc-1")],
        fills=1,
        versions=["vA"],
        captured_at="2026-09-27T20:00:00Z",
    )
    assert row["day"] == "2026-09-27"
    assert row["account"] == "acc-1"
    assert row["capturedAt"] == "2026-09-27T20:00:00Z"
    assert row["measured"] is True
    assert row["decided"] == 2
    assert row["proposals"] == 1
    assert row["vetoes"] == 1
    assert row["vetoCounted"] == 1
    assert row["otherCount"] == 0
    assert row["contractViolation"] is False
    assert row["positionEventByCode"] == {"protect_requested": 1}
    assert row["positionEventCounted"] == 1
    assert row["cycles"] == 1
    assert row["measurableCycles"] == 1
    assert row["rMean"] == 2.0
    assert row["rMeasurement"] == MEASUREMENT_COMPLETE
    assert row["cycleIds"] == ["cyc-1"]
    assert row["instruments"] == ["AAA"]
    assert row["versions"] == ["vA"]
    assert row["regimes"] == ["trend_up"]
    assert row["regime"] == "trend_up"
    assert row["state"] == STATE_OPERATED
    assert row["reasonCatalogCoverage"]["unknown"] == 0


def test_build_window_row_declares_unmeasured_dimensions_as_none_never_zero() -> None:
    """`pairCapable`/`pairActive`/`priceSources` no se miden de esta fuente: se declaran ausentes."""
    row = build_window_row(
        "2026-09-27",
        entries=[_entry("approved")],
        cycles=[_cycle("cyc-1")],
        fills=1,
    )
    assert row["priceSources"] is None
    assert row["pairCapable"] is None
    assert row["pairActive"] is None


def test_build_window_row_without_cycles_declares_unknown_r_not_zero() -> None:
    row = build_window_row("2026-09-27", entries=[_entry("approved")], cycles=[], fills=0)
    assert row["measurableCycles"] == 0
    assert row["rSum"] is None
    assert row["rMean"] is None
    assert row["rMeasurement"] == MEASUREMENT_UNKNOWN


def test_build_window_row_without_proposals_or_vetoes_is_no_signal_unless_nothing_measured() -> None:
    row = build_window_row("2026-09-27", entries=[_entry("approved")], cycles=[], fills=0)
    assert row["proposals"] == 1
    assert row["vetoes"] == 0
    assert row["state"] == STATE_UNRESOLVED


def test_build_window_row_without_any_data_is_declared_unknown() -> None:
    row = build_window_row("2026-09-27")
    assert row["measured"] is False
    assert row["state"] == STATE_UNKNOWN


def test_build_window_row_uses_the_same_r_reader_as_the_report() -> None:
    """El R del ciclo sale de `measured_r` (mismo cociente que el informe, sin regla paralela)."""
    row = build_window_row(
        "2026-09-27",
        cycles=[_cycle("cyc-1", pnl=30.0, risk=10.0), _cycle("cyc-2", pnl=0.0, risk=4.0)],
    )
    assert row["measurableCycles"] == 2
    assert row["rSum"] == 3.0
    assert row["rMean"] == 1.5


# ── window_gate ────────────────────────────────────────────────────────────────────────────────


def _gate_row(day: str, regime: str, cycles: int) -> dict[str, Any]:
    return {"day": day, "regimes": [regime], "regime": regime, "measurableCycles": cycles}


def test_window_gate_counts_calendar_days_not_rows() -> None:
    """Cuatro filas del MISMO día son un solo cubo de calendario: la ventana NO está lista."""
    rows = [_gate_row("2026-09-27", "trend_up", 10) for _ in range(4)]
    gate = window_gate(rows)
    assert gate["days"] == 1
    assert gate["ready"] is False
    assert gate["verdict"] == MARKET_WINDOW_INCONCLUSIVE


def test_window_gate_is_ready_with_days_episodes_and_cycles() -> None:
    rows = [
        _gate_row("2026-09-24", "trend_up", 8),
        _gate_row("2026-09-25", "trend_up", 8),
        _gate_row("2026-09-26", "trend_down", 8),
        _gate_row("2026-09-27", "trend_down", 8),
    ]
    gate = window_gate(rows)
    assert gate["days"] == MARKET_WINDOW_MIN_DAYS
    assert gate["episodes"] == MARKET_WINDOW_MIN_EPISODES
    assert gate["cycles"] == MARKET_WINDOW_MIN_CYCLES
    assert gate["ready"] is True
    assert gate["verdict"] == MARKET_WINDOW_READY


def test_window_gate_is_inconclusive_with_one_episode() -> None:
    rows = [_gate_row(f"2026-09-2{index}", "trend_up", 8) for index in range(4, 8)]
    gate = window_gate(rows)
    assert gate["days"] == 4
    assert gate["episodes"] == 1
    assert gate["ready"] is False


def test_window_gate_is_inconclusive_without_enough_cycles() -> None:
    rows = [
        _gate_row("2026-09-24", "trend_up", 4),
        _gate_row("2026-09-25", "trend_up", 4),
        _gate_row("2026-09-26", "trend_down", 4),
        _gate_row("2026-09-27", "trend_down", 4),
    ]
    gate = window_gate(rows)
    assert gate["cycles"] == 16
    assert gate["ready"] is False


def test_window_gate_declares_unmeasured_when_there_are_no_rows() -> None:
    gate = window_gate([])
    assert gate["measured"] is False
    assert gate["verdict"] == MARKET_WINDOW_INCONCLUSIVE


# ── render_window_series ───────────────────────────────────────────────────────────────────────


def test_render_window_series_is_deterministic_and_separates_the_channels() -> None:
    row = build_window_row(
        "2026-09-27",
        account="acc-1",
        entries=[
            _entry("risk_exit", "approved"),
            _entry("protect_requested", event=_POSITION_EVENT),
        ],
        cycles=[_cycle("cyc-1")],
        fills=1,
    )
    rendered = render_window_series([row])
    assert "2026-09-27" in rendered
    assert "ENTRY" in rendered
    assert "aprobaciones/salidas (NO son vetos): approved=1 risk_exit=1" in rendered
    assert "eventos/posicion (NO son vetos): protect_requested=1" in rendered
    assert rendered == render_window_series([row])


def test_render_window_series_warns_on_a_contract_violation() -> None:
    row = build_window_row("2026-09-27", entries=[_entry("nuevo_motivo")], fills=0)
    rendered = render_window_series([row])
    assert "ALERTA CONTRATO: other>0" in rendered
    assert "nuevo_motivo=1" in rendered


# ── Funnel de operabilidad (v2.81) ─────────────────────────────────────────────────────────────


def test_build_operability_funnel_declares_upper_steps_without_evidence() -> None:
    """Sin `--forward`, los escalones que sólo mide el runner se DECLARAN, nunca se inventan a 0."""
    row = build_window_row(
        "2026-09-27",
        entries=[
            _entry("regime_invalid", "top_n_excluded", "risk_budget_exceeded"),
            _entry("approved"),
        ],
        fills=0,
    )
    funnel = row["funnel"]
    assert set(funnel) == set(FUNNEL_STEPS)
    for step in ("universe", "marketData", "regimeAllowed", "orders"):
        assert funnel[step]["count"] is None
        assert funnel[step]["measured"] is False
    assert funnel["signals"]["count"] == 4
    assert funnel["topN"]["count"] == 3
    assert funnel["risk"]["count"] == 2
    assert funnel["reservation"]["count"] == 2
    assert funnel["fills"]["count"] == 0
    assert funnel["cycles"]["count"] == 0


def test_build_operability_funnel_with_evidence_is_complete() -> None:
    evidence = {
        "watchSize": 8,
        "priceSources": {"a": "market_close", "b": "market_live", "c": "missing"},
        "sample": {"pricesServed": 2},
        "marketRegime": {"counts": {"trend_down": 6, "range": 2}},
        "turnTotals": {"orders": 1},
    }
    row = build_window_row("2026-09-27", entries=[_entry("approved")], fills=0, evidence=evidence)
    funnel = row["funnel"]
    assert funnel["universe"]["count"] == 8
    assert funnel["marketData"]["count"] == 2
    assert funnel["regimeAllowed"]["count"] == 2
    assert funnel["orders"]["count"] == 1
    assert row["symbolsObserved"] == 8
    assert row["pairCapable"] is True
    assert row["pairActive"] is False


def test_build_operability_funnel_never_fabricates_a_step_without_its_predecessor() -> None:
    """Un día no medido deja TODOS los escalones durables en ``None`` (no un cero de relleno)."""
    row = build_window_row("2026-09-27")
    funnel = row["funnel"]
    for step in ("signals", "topN", "risk", "reservation", "fills", "cycles"):
        assert funnel[step]["count"] is None


def test_render_window_series_publishes_funnel_and_age() -> None:
    row = build_window_row("2026-09-27", entries=[_entry("regime_invalid")], fills=0)
    rendered = render_window_series([row])
    assert "Funnel de operabilidad" in rendered
    assert "signals=1" in rendered
    assert "universe=n/d" in rendered
    assert "unresolved_age" in rendered


# ── unresolved_age (v2.81) ─────────────────────────────────────────────────────────────────────


def test_unresolved_age_buckets_by_dwell_within_the_day() -> None:
    reference = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    entries = [
        _entry("approved", at=reference - timedelta(seconds=30)),
        _entry("approved", at=reference - timedelta(minutes=3)),
        _entry("approved", at=reference - timedelta(minutes=10)),
        _entry("approved", at=reference - timedelta(minutes=45)),
        _entry("regime_invalid", at=reference),
    ]
    age = unresolved_age(entries)
    assert age["measured"] is True
    assert age["proposals"] == 4
    assert age["resolutionJoined"] is False
    assert age["reference"] == reference.isoformat()
    assert age["buckets"] == {"lt1m": 1, "1to5m": 1, "5to20m": 1, "gt20m": 1, "unknown": 0}


def test_unresolved_age_declares_not_measured_without_timestamps() -> None:
    age = unresolved_age([_entry("approved")])
    assert age["measured"] is False
    assert age["proposals"] == 1
    assert all(age["buckets"][name] is None for name in UNRESOLVED_AGE_BUCKETS)


def test_unresolved_age_is_measured_zero_when_there_are_no_proposals() -> None:
    age = unresolved_age([_entry("regime_invalid", at=datetime(2026, 9, 27, 12, 0, tzinfo=UTC))])
    assert age["measured"] is True
    assert age["proposals"] == 0
    assert age["buckets"] == {name: 0 for name in UNRESOLVED_AGE_BUCKETS}


def test_build_window_row_marks_age_unmeasured_when_the_day_is_unmeasured() -> None:
    row = build_window_row("2026-09-27")
    assert row["unresolvedAge"]["measured"] is False
    assert row["unresolvedAge"]["proposals"] is None


# ── render_window_html (v2.81) ─────────────────────────────────────────────────────────────────


def test_render_window_html_is_deterministic_and_escapes_reason_codes() -> None:
    row = build_window_row("2026-09-27", entries=[_entry("<b>evil</b>")], fills=0)
    meta = {
        "header": {"account": "acc<script>", "versions": ["vA"], "capturedAt": "2026-09-27T20:00:00Z"},
        "gate": window_gate([row]),
    }
    rendered = render_window_html([row], meta)
    assert rendered == render_window_html([row], meta)
    assert "<b>evil</b>" not in rendered
    assert "&lt;b&gt;evil&lt;/b&gt;" in rendered
    assert "acc&lt;script&gt;" in rendered


def test_render_window_html_publishes_gate_verdict_and_contract_alert() -> None:
    row = build_window_row("2026-09-27", entries=[_entry("nuevo_motivo")], fills=0)
    meta = {"header": {"account": "acc", "versions": [], "capturedAt": "x"}, "gate": window_gate([row])}
    rendered = render_window_html([row], meta)
    assert "GATE: INCONCLUSIVE" in rendered
    assert "ALERTA CONTRATO: other&gt;0" in rendered
