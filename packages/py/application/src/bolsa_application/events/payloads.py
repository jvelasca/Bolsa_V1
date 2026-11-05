"""Payloads tipados de eventos de plataforma."""

from typing import Any

from bolsa_analytics.signals.strategy import SignalEventV1


def signal_event_payload(signal: SignalEventV1, **extra: Any) -> dict[str, Any]:
    return {
        "instrumentId": signal.instrument_id,
        "kind": str(signal.kind),
        "price": signal.price,
        "timestamp": signal.timestamp,
        "strategyDefinitionId": signal.strategy_definition_id,
        "strategyVersion": signal.strategy_version,
        "barIndex": signal.bar_index,
        # S4 — contrato de tiempo explícito en el evento: señal en ``t``, ejecución
        # en ``t + 1``. Los consumidores no tienen que adivinarlo a partir de barIndex.
        "signalBar": signal.resolved_signal_bar,
        "executionBar": signal.resolved_execution_bar,
        **extra,
    }


def scan_completed_payload(result: Any) -> dict[str, Any]:
    return {
        "scanId": result.scan_id,
        "hitCount": result.hit_count,
        "scannedCount": result.scanned_count,
        "timeframe": result.timeframe,
        "strategyDefinitionId": result.strategy_definition_id,
        "listId": result.list_id,
    }
