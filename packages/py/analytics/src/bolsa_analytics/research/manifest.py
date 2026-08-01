"""Run manifest builder for backtest reproducibility."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any, Literal

from bolsa_analytics.research.data_snapshot import (
    BarFingerprint,
    build_data_snapshot_id,
    compute_data_version,
)

RUN_MANIFEST_VERSION = "1.0"
ENGINE_NAME = "bolsa_event_backtest"
ENGINE_VERSION = "0.3.0"


def metrics_hash(
    *,
    total_return_pct: float,
    max_drawdown_pct: float,
    trade_count: int,
    final_equity: float,
) -> str:
    payload = json.dumps(
        {
            "totalReturnPct": round(total_return_pct, 4),
            "maxDrawdownPct": round(max_drawdown_pct, 4),
            "tradeCount": trade_count,
            "finalEquity": round(final_equity, 2),
        },
        sort_keys=True,
    )
    return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def strategy_definition_from_preset(
    preset_key: str,
    instrument_ids: list[str],
    *,
    timeframe: str = "1d",
    commission_bps: int = 0,
    slippage_bps: int = 0,
) -> dict[str, Any]:
    from bolsa_analytics.signals.preset_catalog import (
        strategy_definition_from_preset as catalog_definition_from_preset,
    )

    definition = catalog_definition_from_preset(preset_key, instrument_ids, timeframe=timeframe)  # type: ignore[arg-type]
    execution = dict(definition.get("execution") or {})
    execution["commissionBps"] = commission_bps
    execution["slippageBps"] = slippage_bps
    definition["execution"] = execution
    return definition


def build_run_manifest(
    *,
    run_id: str,
    instrument_id: str,
    strategy_type: str,
    bars: list[BarFingerprint],
    timeframe: str,
    initial_cash: float,
    commission_bps: int,
    slippage_bps: int,
    total_return_pct: float,
    max_drawdown_pct: float,
    trade_count: int,
    final_equity: float,
    equity_curve: list[dict[str, float | str]] | None = None,
    strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not bars:
        raise ValueError("Cannot build manifest without bars")

    data_version = compute_data_version(bars)
    snapshot_id = build_data_snapshot_id(instrument_id, timeframe, data_version)
    resolved_strategy = strategy or strategy_definition_from_preset(
        strategy_type,
        [instrument_id],
        timeframe=timeframe,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    if strategy is not None:
        resolved_strategy = {
            **resolved_strategy,
            "universe": {"instrumentIds": [instrument_id]},
        }
    origin = str(resolved_strategy.get("origin", "preset"))
    outputs_hash = metrics_hash(
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=trade_count,
        final_equity=final_equity,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    outputs: dict[str, Any] = {
        "metricsHash": outputs_hash,
        "tradeCount": trade_count,
    }
    if equity_curve:
        outputs["equityCurve"] = equity_curve

    return {
        "manifestVersion": RUN_MANIFEST_VERSION,
        "runId": run_id,
        "runType": "backtest",
        "createdAt": created_at,
        "engine": {"name": ENGINE_NAME, "version": ENGINE_VERSION},
        "dataSnapshot": {
            "id": snapshot_id,
            "instrumentIds": [instrument_id],
            "timeframe": timeframe,
            "from": bars[0].timestamp,
            "to": bars[-1].timestamp,
            "barCount": len(bars),
            "dataVersion": data_version,
            "source": "postgres",
        },
        "strategy": resolved_strategy,
        "indicatorSpecs": resolved_strategy["indicatorSpecs"],
        "executionParams": {"initialCash": initial_cash},
        "environment": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "bolsaAnalytics": ENGINE_VERSION,
        },
        "outputs": outputs,
        "provenance": {"origin": origin},
    }
