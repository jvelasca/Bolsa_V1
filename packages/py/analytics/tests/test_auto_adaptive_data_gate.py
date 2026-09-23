"""AUTO-13 — tests del Adaptive Data Gate puro (``auto_adaptive_data_gate``).

Lo que se prueba es el invariante del audit: **los datos incompletos se declaran y LIMITAN la
adaptación, nunca se convierten en un juicio sobre la estrategia.** De ahí los cuatro bloques:

* la tabla estado→efecto (``OK/DEGRADED/STALE/BLOCKED`` → ``ADAPTS/LIMITS/FREEZES/NO_ADAPT``) y
  que el efecto se **derive** del estado en vez de poder divergir;
* la precedencia ``BLOCKED > STALE > DEGRADED > OK``, con el grave **absorbiendo** los motivos
  menores (para que un ``BLOCKED`` no se publique con notas de ``DEGRADED``);
* que **sin evidencia aportada no se degrade** (``None`` es "no se pidió medir"): es lo que
  mantiene byte-idéntico el comportamiento cuando el gate no se pasa;
* que un hueco **explícito** (sink caído, lectura durable rota, régimen ausente, medición
  parcial) sí module el estado, y que el régimen ausente **nunca** se lea como adverso.
"""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.auto_adaptive_data_gate import (
    DATA_GATE_ADAPTS,
    DATA_GATE_BLOCKED,
    DATA_GATE_DEGRADED,
    DATA_GATE_EVALUATION_CYCLE_SECONDS_DEFAULT,
    DATA_GATE_FREEZES,
    DATA_GATE_LIMITS,
    DATA_GATE_NO_ADAPT,
    DATA_GATE_NOTE_DURABLE_UNREAD,
    DATA_GATE_NOTE_EVIDENCE_NOT_PROVIDED,
    DATA_GATE_NOTE_INSUFFICIENT_HISTORY,
    DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN,
    DATA_GATE_NOTE_JOURNAL_GAP,
    DATA_GATE_NOTE_MEASUREMENT_INCOMPLETE,
    DATA_GATE_NOTE_POLICY_MISMATCH,
    DATA_GATE_NOTE_RECENT_UNAVAILABLE,
    DATA_GATE_NOTE_REGIME_ABSENT,
    DATA_GATE_NOTE_SINK_FAILURES,
    DATA_GATE_NOTE_UNREADABLE_ROWS,
    DATA_GATE_OK,
    DATA_GATE_POLICY_VERSION,
    DATA_GATE_STALE,
    DataGatePolicy,
    assess_data_gate,
    journal_age_cycles,
)


def test_a_clean_reading_adapts() -> None:
    reading = assess_data_gate(sink_failures=0, journal_age_cycles=0, read_ok=True)
    assert reading.status == DATA_GATE_OK
    assert reading.effect == DATA_GATE_ADAPTS
    assert reading.adapts is True
    assert reading.limits_adaptation is False
    assert reading.blocks_adaptation is False


def test_a_single_sink_failure_degrades_without_freezing() -> None:
    """Un fallo aislado declara el problema pero NO quita la protección ni congela."""
    reading = assess_data_gate(sink_failures=1, journal_age_cycles=1)
    assert reading.status == DATA_GATE_DEGRADED
    assert reading.effect == DATA_GATE_LIMITS
    assert reading.limits_adaptation is True
    assert reading.blocks_adaptation is False
    assert DATA_GATE_NOTE_SINK_FAILURES in reading.notes


def test_consecutive_sink_failures_freeze_the_adaptation() -> None:
    reading = assess_data_gate(sink_failures=3, journal_age_cycles=1)
    assert reading.status == DATA_GATE_STALE
    assert reading.effect == DATA_GATE_FREEZES
    assert reading.limits_adaptation is True


def test_a_durable_read_failure_freezes_instead_of_blocking() -> None:
    """No poder leer la memoria (``read_ok=False``) congela; no borra la adaptación entera.

    Es la diferencia entre "no leí" y "el journal lleva ciclos muerto": la primera conserva lo
    vigente, la segunda es el ``BLOCKED`` del audit.
    """
    reading = assess_data_gate(read_ok=False, journal_age_cycles=1)
    assert reading.status == DATA_GATE_STALE
    assert reading.status != DATA_GATE_BLOCKED
    assert DATA_GATE_NOTE_DURABLE_UNREAD in reading.notes


def test_a_journal_gap_blocks_the_adaptation() -> None:
    """«Sin journal durante X ciclos → BLOCKED» (§21), con todo lo demás sano."""
    reading = assess_data_gate(journal_age_cycles=10, read_ok=True, sink_failures=0)
    assert reading.status == DATA_GATE_BLOCKED
    assert reading.effect == DATA_GATE_NO_ADAPT
    assert reading.blocks_adaptation is True
    assert reading.notes == (DATA_GATE_NOTE_JOURNAL_GAP,)


def test_blocked_absorbs_the_lesser_reasons() -> None:
    """El estado grave manda y NO se publica con las notas de los menores."""
    reading = assess_data_gate(
        journal_age_cycles=99,
        sink_failures=5,
        read_ok=False,
        regime_available=False,
        measurement_completeness="PARTIAL",
    )
    assert reading.status == DATA_GATE_BLOCKED
    assert reading.notes == (DATA_GATE_NOTE_JOURNAL_GAP,)


def test_stale_absorbs_degraded_reasons() -> None:
    reading = assess_data_gate(
        sink_failures=3, measurement_completeness="PARTIAL", regime_available=False
    )
    assert reading.status == DATA_GATE_STALE
    assert DATA_GATE_NOTE_SINK_FAILURES in reading.notes
    assert DATA_GATE_NOTE_MEASUREMENT_INCOMPLETE not in reading.notes
    assert DATA_GATE_NOTE_REGIME_ABSENT not in reading.notes


def test_an_unknown_journal_age_does_not_block() -> None:
    """Un instante que no se pudo medir no puede fabricar un bloqueo."""
    reading = assess_data_gate(journal_age_cycles=None)
    assert reading.status == DATA_GATE_OK
    assert DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN in reading.notes
    assert reading.blocks_adaptation is False


def test_stale_declares_an_unknown_journal_age() -> None:
    """Si se congela y la antigüedad no se pudo medir, se dice: no se supone juventud."""
    reading = assess_data_gate(read_ok=False, journal_age_cycles=None)
    assert reading.status == DATA_GATE_STALE
    assert DATA_GATE_NOTE_DURABLE_UNREAD in reading.notes
    assert DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN in reading.notes


def test_unreadable_rows_and_policy_mismatch_freeze() -> None:
    rows = assess_data_gate(unreadable_rows=1)
    assert rows.status == DATA_GATE_STALE
    assert DATA_GATE_NOTE_UNREADABLE_ROWS in rows.notes
    mismatch = assess_data_gate(policy_version_mismatch=True)
    assert mismatch.status == DATA_GATE_STALE
    assert DATA_GATE_NOTE_POLICY_MISMATCH in mismatch.notes


def test_insufficient_history_freezes() -> None:
    reading = assess_data_gate(insufficient_history=True)
    assert reading.status == DATA_GATE_STALE
    assert DATA_GATE_NOTE_INSUFFICIENT_HISTORY in reading.notes


def test_the_gate_declares_instead_of_degrading_when_no_evidence_is_provided() -> None:
    """Sin lectura aportada no se degrada: es la byte-identidad del comportamiento histórico."""
    reading = assess_data_gate(
        measurement_completeness=None,
        recent_available=None,
        regime_available=None,
    )
    assert reading.status == DATA_GATE_OK
    assert DATA_GATE_NOTE_EVIDENCE_NOT_PROVIDED in reading.notes


def test_an_incomplete_measurement_degrades_when_explicitly_provided() -> None:
    reading = assess_data_gate(measurement_completeness="PARTIAL")
    assert reading.status == DATA_GATE_DEGRADED
    assert DATA_GATE_NOTE_MEASUREMENT_INCOMPLETE in reading.notes


def test_a_complete_measurement_does_not_degrade() -> None:
    reading = assess_data_gate(measurement_completeness="COMPLETE")
    assert reading.status == DATA_GATE_OK
    assert DATA_GATE_NOTE_MEASUREMENT_INCOMPLETE not in reading.notes


def test_an_unavailable_recent_window_degrades() -> None:
    reading = assess_data_gate(recent_available=False)
    assert reading.status == DATA_GATE_DEGRADED
    assert DATA_GATE_NOTE_RECENT_UNAVAILABLE in reading.notes


def test_an_absent_regime_degrades_and_is_never_read_as_adverse() -> None:
    """§20: el hueco de régimen es evidencia incompleta declarada, no un régimen del mercado."""
    reading = assess_data_gate(regime_available=False)
    assert reading.status == DATA_GATE_DEGRADED
    assert DATA_GATE_NOTE_REGIME_ABSENT in reading.notes
    assert reading.blocks_adaptation is False


def test_the_effect_is_derived_from_the_status() -> None:
    """La tabla completa, estado a estado (y el efecto no es un campo que pueda divergir).

    Cada estado se **construye** con los hechos que lo producen; el par (estado, efecto) se
    compara entero, de modo que invertir la tabla rompe este test.
    """
    cases = (
        (assess_data_gate(), DATA_GATE_OK, DATA_GATE_ADAPTS),
        (assess_data_gate(sink_failures=1), DATA_GATE_DEGRADED, DATA_GATE_LIMITS),
        (assess_data_gate(sink_failures=3), DATA_GATE_STALE, DATA_GATE_FREEZES),
        (assess_data_gate(journal_age_cycles=10), DATA_GATE_BLOCKED, DATA_GATE_NO_ADAPT),
    )
    for reading, status, effect in cases:
        assert (reading.status, reading.effect) == (status, effect)


def test_thresholds_follow_the_policy() -> None:
    strict = DataGatePolicy(sink_failures_stale=2, journal_gap_blocked=5)
    assert assess_data_gate(sink_failures=2, policy=strict).status == DATA_GATE_STALE
    assert assess_data_gate(sink_failures=2).status == DATA_GATE_DEGRADED
    assert assess_data_gate(journal_age_cycles=5, policy=strict).status == DATA_GATE_BLOCKED
    assert assess_data_gate(journal_age_cycles=5).status == DATA_GATE_OK


def test_the_policy_refuses_non_positive_thresholds() -> None:
    with pytest.raises(ValueError):
        DataGatePolicy(sink_failures_stale=0)
    with pytest.raises(ValueError):
        DataGatePolicy(journal_gap_blocked=0)


def test_the_reading_publishes_the_facts_for_audit() -> None:
    reading = assess_data_gate(
        sink_failures=1,
        journal_age_cycles=2,
        measurement_completeness="PARTIAL",
        policy_version_mismatch=True,
    )
    payload = reading.as_dict()
    assert payload["status"] == DATA_GATE_STALE
    assert payload["effect"] == DATA_GATE_FREEZES
    assert payload["policyVersion"] == DATA_GATE_POLICY_VERSION
    assert payload["sinkFailures"] == 1
    assert payload["journalAgeCycles"] == 2
    assert payload["measurementCompleteness"] == "PARTIAL"
    assert payload["policyVersionMismatch"] is True
    assert isinstance(payload["notes"], list)


def test_the_gate_never_blocks_on_missing_evidence() -> None:
    """El invariante: la AUSENCIA de dato no puede producir el estado más grave."""
    reading = assess_data_gate(
        sink_failures=0,
        journal_age_cycles=None,
        read_ok=True,
        measurement_completeness=None,
        recent_available=None,
        regime_available=None,
    )
    assert reading.status != DATA_GATE_BLOCKED
    assert reading.blocks_adaptation is False


def test_the_journal_gap_is_measured_against_the_cycle_count() -> None:
    """Frontera exacta del umbral: ``gap - 1`` no bloquea, ``gap`` sí."""
    assert assess_data_gate(journal_age_cycles=9).status == DATA_GATE_OK
    assert assess_data_gate(journal_age_cycles=10).status == DATA_GATE_BLOCKED


# ── El ancla durable: antigüedad (segundos) → ciclos declarados (AUTO-13, paso 2) ───────


def test_the_journal_age_converts_seconds_into_declared_cycles() -> None:
    """600s a la cadencia declarada (60s) son 10 ciclos; 599s son 9 (no se redondea al alza)."""
    assert (
        journal_age_cycles(
            last_published_at="2026-09-23T10:00:00Z", now="2026-09-23T10:10:00Z"
        )
        == 10
    )
    assert (
        journal_age_cycles(
            last_published_at="2026-09-23T10:00:00Z", now="2026-09-23T10:09:59Z"
        )
        == 9
    )
    assert (
        journal_age_cycles(
            last_published_at="2026-09-23T10:00:00Z", now="2026-09-23T10:01:30Z"
        )
        == 1
    )


def test_the_age_feeds_the_gate_the_same_way_as_a_measured_count() -> None:
    """El ancla del journal ES el ``journal_age_cycles`` del gate: mismo umbral, mismo bloqueo."""
    age = journal_age_cycles(
        last_published_at="2026-09-23T10:00:00Z", now="2026-09-23T10:10:00Z"
    )
    assert assess_data_gate(journal_age_cycles=age).status == DATA_GATE_BLOCKED
    just_under = journal_age_cycles(
        last_published_at="2026-09-23T10:00:00Z", now="2026-09-23T10:09:00Z"
    )
    assert assess_data_gate(journal_age_cycles=just_under).status == DATA_GATE_OK


def test_the_cycle_cadence_is_declared_by_the_policy() -> None:
    """La cadencia es un dato DECLARADO: con 120s/ciclo la misma antigüedad vale la mitad."""
    slow = DataGatePolicy(evaluation_cycle_seconds=120.0)
    arguments: dict[str, str] = {
        "last_published_at": "2026-09-23T10:00:00Z",
        "now": "2026-09-23T10:10:00Z",
    }
    assert journal_age_cycles(**arguments, policy=slow) == 5
    assert journal_age_cycles(**arguments) == 10
    assert DATA_GATE_EVALUATION_CYCLE_SECONDS_DEFAULT == 60.0


def test_the_parse_accepts_offsets_and_naive_instants_as_utc() -> None:
    assert (
        journal_age_cycles(
            last_published_at="2026-09-23T12:00:00+02:00", now="2026-09-23T10:10:00Z"
        )
        == 10
    )
    assert (
        journal_age_cycles(
            last_published_at="2026-09-23T10:00:00", now="2026-09-23T10:10:00Z"
        )
        == 10
    )


def test_a_missing_or_unreadable_instant_does_not_invent_an_age() -> None:
    """Sin instante legible el ancla es ``None`` (no bloquea): no se supone juventud ni vejez."""
    assert journal_age_cycles(last_published_at=None, now="2026-09-23T10:00:00Z") is None
    assert (
        journal_age_cycles(last_published_at="no-es-una-fecha", now="2026-09-23T10:00:00Z")
        is None
    )
    assert (
        journal_age_cycles(last_published_at="2026-09-23T10:00:00Z", now="no-es-una-fecha")
        is None
    )
    assert journal_age_cycles(last_published_at="", now="") is None


def test_an_instant_in_the_future_does_not_invent_an_age() -> None:
    """Un reloj que va hacia atrás no fabrica una antigüedad: se declara ``None``."""
    assert (
        journal_age_cycles(
            last_published_at="2026-09-23T10:10:00Z", now="2026-09-23T10:00:00Z"
        )
        is None
    )


def test_the_cadence_must_be_positive() -> None:
    with pytest.raises(ValueError):
        DataGatePolicy(evaluation_cycle_seconds=0.0)
    with pytest.raises(ValueError):
        DataGatePolicy(evaluation_cycle_seconds=-1.0)
