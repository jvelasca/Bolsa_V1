"""Compact lab evidence snapshot for paper accounts (P7). Provenance only — not a prod gate."""

from __future__ import annotations

from typing import Any


LAB_EVIDENCE_SETTINGS_KEY = "labEvidence"

LAB_EVIDENCE_NOTE = (
    "Lab provenance at paper deploy — not a production gate, Belief, or auto-live."
)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value == value and abs(value) != float("inf"):
        return float(value)
    return None


def _as_record(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def lab_evidence_snapshot_from_blocks(
    blocks: dict[str, Any] | None,
    *,
    trial_id: str | None = None,
    source_backtest_run_id: str | None = None,
) -> dict[str, Any]:
    """Build a compact snapshot from research_trials.blocks (or empty none)."""
    base: dict[str, Any] = {
        "kind": "none",
        "note": LAB_EVIDENCE_NOTE,
    }
    if trial_id:
        base["trialId"] = trial_id
    if source_backtest_run_id:
        base["sourceBacktestRunId"] = source_backtest_run_id

    if not blocks:
        return base

    edge = _as_record(blocks.get("edgeReport"))
    pbo_block = _as_record(blocks.get("pbo"))
    cpcv = _as_record(blocks.get("cpcv"))
    cpcv_pbo = _as_record(cpcv.get("pbo")) if cpcv else None
    suite = _as_record(edge.get("suite")) if edge else None

    edge_band = edge.get("band") if edge and isinstance(edge.get("band"), str) else None
    credibility = _finite(edge.get("credibility")) if edge else None
    monte_carlo = _finite(suite.get("monteCarloPValue")) if suite else None
    dsr = _finite(suite.get("dsr")) if suite else None
    pbo = (
        _finite(pbo_block.get("pbo"))
        if pbo_block
        else _finite(cpcv_pbo.get("pbo"))
        if cpcv_pbo
        else _finite(edge.get("pbo"))
        if edge
        else None
    )

    def with_edge(snap: dict[str, Any]) -> dict[str, Any]:
        if credibility is not None:
            snap["credibility"] = credibility
        if edge_band:
            snap["edgeBand"] = edge_band
        if monte_carlo is not None:
            snap["monteCarloPValue"] = monte_carlo
        if dsr is not None:
            snap["dsr"] = dsr
        if pbo is not None:
            snap["pbo"] = pbo
        return snap

    if cpcv:
        mean = _finite(cpcv.get("meanOosScore"))
        if mean is not None:
            return with_edge(
                {
                    **base,
                    "kind": "cpcv",
                    "meanOosScore": mean,
                    "oosScore": mean,
                    "pathCount": _finite(cpcv.get("pathCount")),
                    "walkForwardEfficiency": _finite(cpcv.get("walkForwardEfficiency")),
                    "oosCv": _finite(cpcv.get("oosCv")),
                    "positiveOosFoldShare": _finite(cpcv.get("positiveOosFoldShare")),
                    "wfeSource": "lab_score",
                }
            )

    wf = _as_record(blocks.get("walkForward"))
    if wf:
        mean = _finite(wf.get("meanOosScore"))
        if mean is not None:
            return with_edge(
                {
                    **base,
                    "kind": "walkforward",
                    "meanOosScore": mean,
                    "oosScore": mean,
                    "nFolds": _finite(wf.get("nFolds")) or _finite(wf.get("foldCount")),
                    "walkForwardEfficiency": _finite(wf.get("walkForwardEfficiency")),
                    "oosCv": _finite(wf.get("oosCv")),
                    "positiveOosFoldShare": _finite(wf.get("positiveOosFoldShare")),
                    "wfeSource": "lab_score",
                }
            )

    oos = _as_record(blocks.get("oosMetrics"))
    if oos:
        score = _finite(oos.get("score"))
        if score is not None:
            return with_edge(
                {
                    **base,
                    "kind": "holdout",
                    "oosScore": score,
                    "oosReturnPct": _finite(oos.get("totalReturnPct")),
                }
            )

    # Edge/PBO alone (IS optimize with EdgeReport) still worth stamping.
    if edge_band or credibility is not None or pbo is not None:
        return with_edge({**base, "kind": "none"})

    return base


def merge_lab_evidence_snapshots(
    from_blocks: dict[str, Any],
    client_hint: dict[str, Any] | None,
) -> dict[str, Any]:
    """Prefer non-none ledger snapshot; else client hint; else blocks-none."""
    if from_blocks.get("kind") and from_blocks.get("kind") != "none":
        return from_blocks
    if client_hint and isinstance(client_hint, dict):
        kind = client_hint.get("kind")
        if kind and kind != "none":
            merged = {**client_hint, "note": LAB_EVIDENCE_NOTE}
            # Keep server provenance ids when present.
            if from_blocks.get("trialId") and not merged.get("trialId"):
                merged["trialId"] = from_blocks["trialId"]
            if from_blocks.get("sourceBacktestRunId") and not merged.get("sourceBacktestRunId"):
                merged["sourceBacktestRunId"] = from_blocks["sourceBacktestRunId"]
            return merged
    return from_blocks


def trial_blocks_from_lab_evidence_snapshot(
    snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build research_trials.blocks from a PaperLabEvidence / OOS snapshot (P9 adopt).

    Lets adopt→H0 trials carry durable lab provenance (not only session stash).
    """
    if not snapshot or not isinstance(snapshot, dict):
        return None
    kind = snapshot.get("kind") or "none"
    if kind == "none" and snapshot.get("edgeBand") is None and snapshot.get("pbo") is None:
        # Still stamp empty provenance note if caller sent source ids only.
        if not snapshot.get("sourceBacktestRunId") and not snapshot.get("trialId"):
            return None

    blocks: dict[str, Any] = {
        "labEvidence": {
            "wfeSource": snapshot.get("wfeSource") or "lab_score",
            "mode": "adopt_provenance",
            "note": "Copied from Optimizar evidence at adopt — not re-validated on this H0 run.",
        }
    }
    if kind == "cpcv":
        mean = _finite(snapshot.get("meanOosScore")) or _finite(snapshot.get("oosScore"))
        if mean is not None:
            cpcv: dict[str, Any] = {
                "meanOosScore": mean,
                "pathCount": _finite(snapshot.get("pathCount")),
                "walkForwardEfficiency": _finite(snapshot.get("walkForwardEfficiency")),
                "oosCv": _finite(snapshot.get("oosCv")),
                "positiveOosFoldShare": _finite(snapshot.get("positiveOosFoldShare")),
            }
            pbo = _finite(snapshot.get("pbo"))
            if pbo is not None:
                cpcv["pbo"] = {"pbo": pbo}
                blocks["pbo"] = {"pbo": pbo}
            blocks["cpcv"] = cpcv
            blocks["labEvidence"]["walkForwardEfficiency"] = cpcv.get("walkForwardEfficiency")
            blocks["labEvidence"]["pbo"] = pbo
    elif kind == "walkforward":
        mean = _finite(snapshot.get("meanOosScore")) or _finite(snapshot.get("oosScore"))
        if mean is not None:
            blocks["walkForward"] = {
                "meanOosScore": mean,
                "nFolds": _finite(snapshot.get("nFolds")),
                "walkForwardEfficiency": _finite(snapshot.get("walkForwardEfficiency")),
                "oosCv": _finite(snapshot.get("oosCv")),
                "positiveOosFoldShare": _finite(snapshot.get("positiveOosFoldShare")),
            }
            blocks["labEvidence"]["walkForwardEfficiency"] = blocks["walkForward"].get(
                "walkForwardEfficiency"
            )
    elif kind == "holdout":
        score = _finite(snapshot.get("oosScore"))
        if score is not None:
            blocks["oosMetrics"] = {
                "score": score,
                "totalReturnPct": _finite(snapshot.get("oosReturnPct")),
            }

    edge: dict[str, Any] = {}
    if snapshot.get("edgeBand"):
        edge["band"] = snapshot["edgeBand"]
    cred = _finite(snapshot.get("credibility"))
    if cred is not None:
        edge["credibility"] = cred
    suite: dict[str, Any] = {}
    mc = _finite(snapshot.get("monteCarloPValue"))
    if mc is not None:
        suite["monteCarloPValue"] = mc
    dsr = _finite(snapshot.get("dsr"))
    if dsr is not None:
        suite["dsr"] = dsr
    if suite:
        edge["suite"] = suite
    persisted = snapshot.get("persistedEdgeReportId")
    if isinstance(persisted, str) and persisted:
        edge["persistedEdgeReportId"] = persisted
    if edge:
        edge["mode"] = "lab_lite"
        blocks["edgeReport"] = edge
        blocks["labEvidence"]["mode"] = blocks["labEvidence"].get("mode") or "adopt_provenance"

    pbo_only = _finite(snapshot.get("pbo"))
    if pbo_only is not None and "pbo" not in blocks:
        blocks["pbo"] = {"pbo": pbo_only}

    # Need at least one validation block beyond the provenance marker.
    if not any(k in blocks for k in ("cpcv", "walkForward", "oosMetrics", "edgeReport", "pbo")):
        return None
    return blocks


def format_lab_evidence_compact(snapshot: dict[str, Any] | None) -> str:
    """Human one-liner for UI / tests."""
    if not snapshot:
        return "—"
    kind = snapshot.get("kind") or "none"
    if kind == "none" and not snapshot.get("edgeBand") and snapshot.get("pbo") is None:
        return "Sin validación lab"
    parts: list[str] = []
    if kind == "holdout":
        parts.append("Hold-out")
        score = _finite(snapshot.get("oosScore"))
        if score is not None:
            parts.append(f"OOS {score:.1f}")
    elif kind == "walkforward":
        parts.append("WF")
    elif kind == "cpcv":
        parts.append("CPCV")
    else:
        parts.append("Lab")
    wfe = _finite(snapshot.get("walkForwardEfficiency"))
    if wfe is not None:
        parts.append(f"WFE {wfe:.2f}")
    pbo = _finite(snapshot.get("pbo"))
    if pbo is not None:
        parts.append(f"PBO {pbo:.2f}")
    band = snapshot.get("edgeBand")
    if isinstance(band, str) and band:
        parts.append(f"Edge {band}")
    return " · ".join(parts) if parts else "—"
