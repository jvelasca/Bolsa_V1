"""AUTO-10 — tests del contrato de régimen por ciclo (paso 1: puro).

Lo que se prueba es la DISCIPLINA, no la aritmética: que la identidad de la decisión se
**derive** del ciclo (o se declare no derivable, sin fingir), que sin ciclo **no** haya
entrada, y que un régimen ausente viaje declarado (``None`` + ``UNKNOWN``) en vez de
rellenarse con un ``UNKNOWN`` que parezca un valor medido.
"""

from __future__ import annotations

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.auto_cycle_journal import (
    AUTO_CYCLE_REGIME_EVENT,
    build_auto_cycle_regime_entry,
    cycle_decision_id,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord


def _entry(**overrides: object) -> DecisionJournalEntryRecord:
    base: dict[str, object] = {
        "cycle_id": "cyc-abc123def456",
        "market_regime": "RISK_ON",
        "actor": "auto-sim",
        "as_of": "2026-09-22T10:00:00Z",
        "account_id": "acc-1",
        "instrument_id": "AAPL",
        "strategy_version": "trend-v3",
    }
    base.update(overrides)
    built = build_auto_cycle_regime_entry(**base)  # type: ignore[arg-type]
    assert built is not None
    return built


def test_decision_id_is_derived_by_prefix_swap() -> None:
    assert cycle_decision_id("cyc-abc123def456") == "dec-abc123def456"
    # El fallback aleatorio tiene la misma forma: también se deriva, sin recalcular digest.
    assert cycle_decision_id("cyc-0123456789ab") == "dec-0123456789ab"


def test_decision_id_declares_when_it_cannot_derive() -> None:
    assert cycle_decision_id(None) is None
    assert cycle_decision_id("") is None
    assert cycle_decision_id("cyc-") is None
    assert cycle_decision_id("opaque-cycle-id") is None
    # ``dec-`` no se re-deriva: solo el prefijo del ciclo tiene el contrato.
    assert cycle_decision_id("dec-abc123def456") is None


def test_entry_derives_the_decision_id_from_its_cycle() -> None:
    entry = _entry()
    assert entry.decision_id == "dec-abc123def456"
    assert entry.event_type == AUTO_CYCLE_REGIME_EVENT
    assert entry.payload is not None
    assert entry.payload["cycleId"] == "cyc-abc123def456"
    assert entry.payload["cycleIdDerived"] is True


def test_entry_without_a_derivable_cycle_declares_it_instead_of_faking_it() -> None:
    entry = _entry(cycle_id="opaque-cycle-id")
    assert entry.payload is not None
    assert entry.payload["cycleId"] == "opaque-cycle-id"
    assert entry.payload["cycleIdDerived"] is False
    assert entry.decision_id.startswith("dec-")
    assert entry.decision_id != "dec-opaque-cycle-id"


def test_without_a_cycle_there_is_no_entry() -> None:
    for cycle_id in (None, "", "   "):
        assert (
            build_auto_cycle_regime_entry(
                cycle_id=cycle_id,
                market_regime="RISK_ON",
                actor="auto-sim",
                as_of="2026-09-22T10:00:00Z",
            )
            is None
        )


def test_absent_regime_is_declared_not_disguised() -> None:
    for regime in (None, "", "   "):
        entry = _entry(market_regime=regime)
        assert entry.payload is not None
        assert entry.payload["marketRegime"] is None
        assert entry.payload["regimeMeasurement"] == MEASUREMENT_UNKNOWN


def test_measured_regime_is_complete_and_normalized() -> None:
    entry = _entry(market_regime="  RISK_OFF  ")
    assert entry.payload is not None
    assert entry.payload["marketRegime"] == "RISK_OFF"
    assert entry.payload["regimeMeasurement"] == MEASUREMENT_COMPLETE


def test_payload_is_stable_and_omits_absent_strategy() -> None:
    entry = _entry()
    assert entry.payload == {
        "event": AUTO_CYCLE_REGIME_EVENT,
        "cycleId": "cyc-abc123def456",
        "marketRegime": "RISK_ON",
        "regimeMeasurement": MEASUREMENT_COMPLETE,
        "cycleIdDerived": True,
        "strategyVersion": "trend-v3",
    }
    without = _entry(strategy_version=None, market_regime=None)
    assert without.payload == {
        "event": AUTO_CYCLE_REGIME_EVENT,
        "cycleId": "cyc-abc123def456",
        "marketRegime": None,
        "regimeMeasurement": MEASUREMENT_UNKNOWN,
        "cycleIdDerived": True,
    }


def test_same_cycle_keeps_its_identity_across_entries() -> None:
    first = _entry()
    second = _entry(market_regime=None)
    # La identidad de la DECISIÓN es estable (es la clave de lectura por índice)...
    assert first.decision_id == second.decision_id == "dec-abc123def456"
    # ...y la de la ENTRADA es única: dos publicaciones son dos filas append-only.
    assert first.id != second.id


def test_blank_metadata_is_absent_not_empty() -> None:
    entry = _entry(account_id="  ", instrument_id="")
    assert entry.account_id is None
    assert entry.instrument_id is None
