"""Dataset metadata helpers for trials/campaigns (Q1.1)."""

from __future__ import annotations

from typing import Any, Sequence


def dataset_metadata_from_bars(
    bars: Sequence[Any],
    *,
    market_regime: str | None = None,
) -> dict[str, Any]:
    """
    Extrae dataset_start/end/bars desde barras con ``.timestamp`` o dict.
    ``market_regime`` queda null salvo heurística explícita del caller.
    """
    if not bars:
        return {
            "datasetStart": None,
            "datasetEnd": None,
            "bars": 0,
            "marketRegime": market_regime,
        }

    def _ts(bar: Any) -> str | None:
        if isinstance(bar, dict):
            v = bar.get("timestamp") or bar.get("date")
            return str(v) if v is not None else None
        v = getattr(bar, "timestamp", None)
        return str(v) if v is not None else None

    stamps = [t for t in (_ts(b) for b in bars) if t]
    return {
        "datasetStart": stamps[0] if stamps else None,
        "datasetEnd": stamps[-1] if stamps else None,
        "bars": len(bars),
        "marketRegime": market_regime,
    }


def merge_dataset_into_blocks(
    blocks: dict[str, Any] | None,
    meta: dict[str, Any],
) -> dict[str, Any]:
    out = dict(blocks or {})
    out["dataset"] = {
        "schemaVersion": "dataset_meta_v0",
        **meta,
    }
    return out
