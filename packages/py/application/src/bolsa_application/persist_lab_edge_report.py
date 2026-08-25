"""P8 — persist lab EdgeReport lite into cognitive edge_reports (no auto-live)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.edge_report import StatisticalSuiteResult
from bolsa_application.cognitive_persistence import CognitiveStore, PersistEdgeReport

LAB_PERSIST_NOTE = "lab_lite · provenance only · not auto-live · not production gate"


def lab_edge_report_to_suite(edge_report: dict[str, Any] | None) -> StatisticalSuiteResult | None:
    """Map lab lite JSON → StatisticalSuiteResult. None if unusable."""
    if not edge_report or not isinstance(edge_report, dict):
        return None
    suite = edge_report.get("suite")
    if not isinstance(suite, dict):
        return None
    trials_n = suite.get("trialsN")
    if not isinstance(trials_n, (int, float)) or int(trials_n) < 0:
        return None
    wfe_source = suite.get("wfeSource")
    if wfe_source not in ("lab_score", "sharpe", None):
        wfe_source = "lab_score"
    return StatisticalSuiteResult(
        trials_n=int(trials_n),
        walk_forward_efficiency=_finite(suite.get("walkForwardEfficiency")),
        wfe_source=wfe_source,  # type: ignore[arg-type]
        monte_carlo_p_value=_finite(suite.get("monteCarloPValue")),
        psr=_finite(suite.get("psr")),
        dsr=_finite(suite.get("dsr")),
        historical_win_rate=_finite(suite.get("historicalWinRate")),
        sample_trades_count=_int_or_none(suite.get("sampleTradesCount")),
    )


def lab_edge_report_notes(
    edge_report: dict[str, Any],
    *,
    optimization_run_id: str | None = None,
) -> tuple[str, ...]:
    notes: list[str] = [LAB_PERSIST_NOTE]
    mode = edge_report.get("mode")
    if isinstance(mode, str) and mode:
        notes.append(f"mode={mode}")
    if optimization_run_id:
        notes.append(f"optimizationRunId={optimization_run_id}")
    pbo = edge_report.get("pbo")
    if isinstance(pbo, (int, float)) and pbo == pbo:
        notes.append(f"pbo={float(pbo):.4f}")
    band = edge_report.get("band")
    if isinstance(band, str) and band:
        notes.append(f"band={band}")
    # Keep lab notes that are strings (truncate).
    for note in edge_report.get("notes") or []:
        if isinstance(note, str) and note and note not in notes:
            notes.append(note[:200])
        if len(notes) >= 12:
            break
    # Explicitly record that auto-live must stay off regardless of lab flag.
    notes.append("autoLiveEligible=ignored")
    return tuple(notes)


def stamp_persisted_edge_report_id(
    edge_report: dict[str, Any] | None,
    persisted_id: str | None,
) -> dict[str, Any] | None:
    if edge_report is None or not persisted_id:
        return edge_report
    stamped = dict(edge_report)
    stamped["persistedEdgeReportId"] = persisted_id
    # Never advertise auto-live from lab persist path.
    stamped["autoLiveEligible"] = False
    reasons = list(stamped.get("blockReasons") or [])
    if "lab_persist_no_auto_live" not in reasons:
        reasons.append("lab_persist_no_auto_live")
    stamped["blockReasons"] = reasons
    return stamped


async def persist_lab_edge_report_if_present(
    store: CognitiveStore | None,
    edge_report: dict[str, Any] | None,
    *,
    optimization_run_id: str | None = None,
    auto_trial: bool = False,
) -> str | None:
    """Append cognitive edge_reports row from lab lite. Returns persisted id or None.

    Does not enable auto-live, Belief, or production gates.
    """
    if store is None or not edge_report:
        return None
    suite = lab_edge_report_to_suite(edge_report)
    if suite is None:
        return None
    ref = edge_report.get("strategyOrSignalRef")
    if not isinstance(ref, str) or not ref.strip():
        ref = "lab:unknown"
    notes = lab_edge_report_notes(edge_report, optimization_run_id=optimization_run_id)
    rec = await PersistEdgeReport(store).execute(
        strategy_or_signal_ref=ref.strip(),
        suite=suite,
        notes=notes,
        auto_trial=auto_trial,
    )
    return rec.id


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value == value and abs(value) != float("inf"):
        return float(value)
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value == value:
        return int(value)
    return None
