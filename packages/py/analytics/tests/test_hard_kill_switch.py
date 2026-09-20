"""V2.44 — HardKillSwitch: tipificado, latcheado e independiente del gobernador.

El ``OperationalGovernor`` ya sabía leer ``halted``; el hueco era que nadie lo producía.
Estos tests fijan la semántica del PRODUCTOR:

* Un motivo no canónico NO activa la parada (se rechaza en vez de guardar un string suelto).
* El latch no se auto-libera: reavisar cuenta el reintento y conserva el motivo original.
* Liberar exige reconciliación explícita.
* El motivo más severo no es "compensable" por un eje benigno del gobernador.
"""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.hard_kill_switch import (
    ENCODED_KILL_SWITCH_REASONS,
    HardKillSwitch,
    coerce_kill_switch_reason,
)
from bolsa_analytics.cognitive.operational_governor import resolve_operational_state


def test_non_canonical_reason_is_rejected() -> None:
    switch = HardKillSwitch()
    with pytest.raises(ValueError):
        switch.engage("because-i-said-so")
    assert switch.engaged is False
    assert coerce_kill_switch_reason("because-i-said-so") is None


def test_reason_is_case_insensitive_and_canonical() -> None:
    switch = HardKillSwitch()
    assert switch.engage("data_corruption", at="2026-09-19T09:00:00Z") is True
    assert switch.reason == "DATA_CORRUPTION"
    assert switch.engaged_at == "2026-09-19T09:00:00Z"


def test_latch_is_not_self_released_and_counts_reengagements() -> None:
    switch = HardKillSwitch()
    switch.engage("BROKER_DESYNC", at="t0")
    # Reavisar NO reinicia el latch: conserva el motivo original y cuenta el reintento.
    assert switch.engage("DATA_CORRUPTION", at="t1") is False
    assert switch.reason == "BROKER_DESYNC"
    assert switch.engaged_at == "t0"
    assert switch.reengagements == 1


def test_release_requires_explicit_reconciliation() -> None:
    switch = HardKillSwitch()
    switch.engage("RECONCILIATION_FAILURE")
    assert switch.release(reconciliation_ok=False) is False
    assert switch.engaged is True
    assert switch.release(reconciliation_ok=True) is True
    assert switch.engaged is False
    assert switch.reason is None


def test_blocks_new_entry_but_allows_protective_exits_by_default() -> None:
    switch = HardKillSwitch()
    switch.engage("STALE_DATA")
    assert switch.blocks_new_entry is True
    assert switch.force_protective_exits is True
    d = switch.to_dict()
    assert d["engaged"] is True
    assert d["blocksNewEntry"] is True
    assert d["reason"] == "STALE_DATA"


def test_halt_overrides_a_benign_governor_reading() -> None:
    """El halt es independiente de los umbrales: no lo compensa un eje benigno."""
    state = resolve_operational_state(
        market_regime="TREND_UP",
        risk_regime="RISK_ON",
        drawdown_band="FULL",
        volatility_band="NORMAL",
        liquidity_band="OK",
        halted=True,
    )
    assert state == "HALTED"


def test_all_encoded_reasons_are_accepted() -> None:
    for reason in ENCODED_KILL_SWITCH_REASONS:
        assert coerce_kill_switch_reason(reason) == reason
