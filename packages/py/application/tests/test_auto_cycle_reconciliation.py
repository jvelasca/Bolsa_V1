"""AUTO-11 — reconciliación del rastro de ciclo: capital reservado vs traza de régimen (puro).

Lo que se prueba es que los CUATRO desajustes no se confundan entre sí: un ciclo con capital y sin
traza confirmada (el hueco ``RESERVATION COMMITTED → CRASH → NO JOURNAL``), un ciclo que ni se
preguntó, un ``cycle_id`` que la lectura por índice no puede alcanzar, y una traza sin reserva. Un
solo contador mentiría en alguno, y el punto de la reconciliación es justo ese: decir CUÁL de los
cuatro pasó.
"""

from __future__ import annotations

from types import SimpleNamespace

from bolsa_application.auto_cycle_reconciliation import (
    CYCLE_TRACE_MISSING,
    CYCLE_TRACE_NOT_DERIVABLE,
    CYCLE_TRACE_ORPHAN,
    CYCLE_TRACE_UNREQUESTED,
    CycleTraceReconciliation,
    cycle_ids_with_reservations,
    reconcile_cycle_trace,
)
from bolsa_application.auto_cycle_regime_reader import CycleRegimeReading


def _reading(
    *,
    regime_by_cycle: dict[str, str] | None = None,
    unconfirmed: tuple[str, ...] = (),
    absent: tuple[str, ...] = (),
    not_derivable: tuple[str, ...] = (),
    requested: int = 0,
) -> CycleRegimeReading:
    return CycleRegimeReading(
        regime_by_cycle=regime_by_cycle or {},
        unconfirmed=unconfirmed,
        absent=absent,
        not_derivable=not_derivable,
        requested=requested,
    )


def _reservation(cycle_id: str | None) -> SimpleNamespace:
    return SimpleNamespace(cycle_id=cycle_id, reservation_id="RES-1")


# ── El caso limpio ──────────────────────────────────────────────────────────────────


def test_a_reserved_cycle_with_a_confirmed_trace_is_clean() -> None:
    report = reconcile_cycle_trace(
        reservation_cycle_ids=["cyc-aaa"],
        reading=_reading(regime_by_cycle={"cyc-aaa": "TREND_UP"}, requested=1),
    )

    assert report.missing == ()
    assert report.orphan == ()
    assert report.gaps == 0
    assert report.clean is True
    assert report.reserved == 1


# ── Los cuatro desajustes, cada uno con su nombre ───────────────────────────────────


def test_a_reserved_cycle_without_a_trace_is_declared_missing() -> None:
    """El hueco del crash entre el commit de la reserva y la traza: capital sin régimen."""
    report = reconcile_cycle_trace(
        reservation_cycle_ids=["cyc-aaa"],
        reading=_reading(absent=("cyc-aaa",), requested=1),
    )

    assert report.missing == ("cyc-aaa",)
    assert report.missing_reasons == {"cyc-aaa": "regime_absent"}
    assert report.gaps == 1
    assert report.clean is False


def test_a_reserved_cycle_with_an_unbelievable_row_declares_the_other_reason() -> None:
    """"Hay fila y no se cree" es DISTINTO de "no hay fila": el motivo viaja con el hueco."""
    report = reconcile_cycle_trace(
        reservation_cycle_ids=["cyc-aaa"],
        reading=_reading(unconfirmed=("cyc-aaa",), requested=1),
    )

    assert report.missing == ("cyc-aaa",)
    assert report.missing_reasons == {"cyc-aaa": "regime_unconfirmed"}


def test_a_reserved_cycle_that_was_never_asked_is_declared_unrequested() -> None:
    """Un hueco OPERATIVO (no se preguntó por el ciclo) no se disfraza de journal roto."""
    report = reconcile_cycle_trace(
        reservation_cycle_ids=["cyc-aaa"],
        reading=_reading(absent=("cyc-other",), requested=1),
    )

    assert report.unrequested == ("cyc-aaa",)
    assert report.missing == (), "no se preguntó: llamarlo 'missing' culparía al journal"
    assert report.missing_reasons == {}


def test_a_reserved_cycle_without_a_derivable_id_is_declared_not_derivable() -> None:
    report = reconcile_cycle_trace(
        reservation_cycle_ids=["legacy-cycle"],
        reading=_reading(not_derivable=("legacy-cycle",), requested=1),
    )

    assert report.not_derivable == ("legacy-cycle",)
    assert report.missing == ()


def test_a_confirmed_trace_without_a_reservation_is_an_orphan() -> None:
    """El caso inverso: hay régimen y ningún capital que lo respalde. También se declara."""
    report = reconcile_cycle_trace(
        reservation_cycle_ids=["cyc-aaa"],
        reading=_reading(
            regime_by_cycle={"cyc-aaa": "TREND_UP", "cyc-ghost": "RANGE"}, requested=2
        ),
    )

    assert report.orphan == ("cyc-ghost",)
    assert report.missing == ()
    assert report.gaps == 1


def test_a_reservation_without_a_cycle_does_not_invent_a_cycle() -> None:
    """``cycle_id = None`` es "anterior a 2.47", no un ciclo: contarlo ensuciaría el cruce."""
    assert cycle_ids_with_reservations([_reservation(None), _reservation("cyc-aaa")]) == ("cyc-aaa",)


def test_a_repeated_cycle_is_counted_once_in_the_order_of_appearance() -> None:
    reservations = [_reservation("cyc-bbb"), _reservation("cyc-aaa"), _reservation("cyc-bbb")]

    assert cycle_ids_with_reservations(reservations) == ("cyc-bbb", "cyc-aaa")


def test_the_summary_publishes_each_disagreement_by_its_name() -> None:
    report = reconcile_cycle_trace(
        reservation_cycle_ids=["cyc-missing", "cyc-unasked", "raw", "cyc-ok"],
        reading=_reading(
            regime_by_cycle={"cyc-ok": "TREND_UP", "cyc-orphan": "RANGE"},
            absent=("cyc-missing",),
            not_derivable=("raw",),
            requested=4,
        ),
    )
    summary = report.as_dict()

    assert summary["reserved"] == 4
    assert summary["missing"] == ["cyc-missing"]
    assert summary["missingReasons"] == {"cyc-missing": "regime_absent"}
    assert summary["unrequested"] == ["cyc-unasked"]
    assert summary["notDerivable"] == ["raw"]
    assert summary["orphan"] == ["cyc-orphan"]
    assert summary["gaps"] == 4
    assert CYCLE_TRACE_MISSING == "cycle_trace_missing"
    assert CYCLE_TRACE_UNREQUESTED == "cycle_trace_unrequested"
    assert CYCLE_TRACE_NOT_DERIVABLE == "cycle_trace_not_derivable"
    assert CYCLE_TRACE_ORPHAN == "cycle_trace_orphan"


def test_an_empty_reservation_window_is_clean_with_nothing_reserved() -> None:
    report = reconcile_cycle_trace(reservation_cycle_ids=[], reading=_reading())

    assert report == CycleTraceReconciliation()
    assert report.clean is True
