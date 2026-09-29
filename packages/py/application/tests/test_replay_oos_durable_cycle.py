"""V2.87 · AUTO-MATERIAL-15 — contratos de la instrumentación del libro y del horizonte.

Invariantes que se fijan aquí (todos fail-closed, ninguno se rellena con un valor
plausible):

* Un libro que no se puede medir se declara ``UNKNOWN``; JAMÁS ``COMPLETE``.
* Una retirada del libro cuenta por ``reservation_id`` que ANTES estaba vivo: se mide el
  ciclo real (alta → liberación), no el catálogo histórico de filas.
* Una reserva viva cuyas dimensiones no se declaran convierte la suma en un SUELO y eso
  viaja en la foto (``unquantifiedReservations``), en vez de presentarse como total exacto.
* Un horizonte incompleto SIEMPRE lleva motivo; sin causa publicada se declara
  ``undeclared_truncation`` en vez de dejar el hueco sin nombre.
* ``ScoreReport.by_year`` reparte la muestra por año de salida (o ``sin_fecha``), que es lo
  que permite leer si la ventana es multianual o un único episodio.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from bolsa_analytics.cognitive.portfolio_reservation import build_reservation
from bolsa_application.replay_oos import (
    HORIZON_UNDECLARED,
    ReplayFill,
    ReplayTick,
    book_is_declared_complete,
    count_releases,
    declare_book_measurement,
    declare_horizon,
    release_deltas,
    score_replay,
    snapshot_book,
    tally_releases,
)

# ── utilidades de construcción determinista ───────────────────────────────────────


def _reservation(
    reservation_id: str,
    *,
    cash: float | None = 1000.0,
    risk: float | None = 20.0,
    sector: str | None = "TECH",
    created_at: str = "2026-01-02T00:00:00Z",
):
    """Reserva VIVA del libro (compra) con los importes que el llamante declare."""
    return build_reservation(
        reservation_id=reservation_id,
        instrument_id="AAA",
        quantity=10.0,
        side="buy",
        account_id="acc",
        tick_id=created_at,
        sector=sector,
        entry=100.0,
        stop=95.0,
        reserved_cash=cash,
        reserved_risk=risk,
        created_at=created_at,
    )


def _released(reservation, *, status: str = "RELEASED_BY_CANCEL"):
    """La misma reserva ya liberada (cantidad viva a 0 y estado terminal declarado)."""
    return replace(reservation, status=status, remaining_qty=0.0)


def _tick(day: str, *, fills: tuple[ReplayFill, ...] = (), stops: dict[str, float] | None = None):
    return ReplayTick(
        day=day,
        regime="SIDEWAYS",
        prices={},
        open_positions={},
        entry_prices={},
        stops=stops or {},
        fill_rows=fills,
    )


# ── medición del libro: lo ilegible NO es COMPLETE ────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [None, "", "   ", "complete_ish", "0", "TRUE", "DONE"],
)
def test_declare_book_measurement_treats_unreadable_as_unknown(raw: object) -> None:
    """Un valor que no es una etiqueta de medición se declara ``UNKNOWN`` (nunca ``COMPLETE``)."""
    assert declare_book_measurement(raw) == "UNKNOWN"
    assert book_is_declared_complete(raw) is False


@pytest.mark.parametrize("raw", ["COMPLETE", " complete ", "Partial", "unknown"])
def test_declare_book_measurement_normalizes_known_labels(raw: str) -> None:
    assert declare_book_measurement(raw) in {"COMPLETE", "PARTIAL", "UNKNOWN"}


def test_book_is_declared_complete_only_for_complete() -> None:
    assert book_is_declared_complete("COMPLETE") is True
    assert book_is_declared_complete("PARTIAL") is False
    assert book_is_declared_complete(None) is False


# ── foto del libro: capital comprometido y su medición declarada ──────────────────


def test_snapshot_book_counts_only_live_reservations_and_sums_their_dimensions() -> None:
    alive = _reservation("RES-1", cash=1000.0, risk=20.0)
    also_alive = _reservation("RES-2", cash=500.0, risk=10.0)
    gone = _released(_reservation("RES-0", cash=999.0, risk=999.0))

    book = snapshot_book(
        "2026-01-02",
        reservations=[gone, alive, also_alive],
        pending_orders=[object(), object()],
        measurement="COMPLETE",
    )

    assert book.day == "2026-01-02"
    assert book.live_reservations == 2
    assert book.reserved_cash == pytest.approx(1500.0)  # la liberada NO cuenta
    assert book.reserved_risk == pytest.approx(30.0)
    assert book.pending_orders == 2
    assert book.measurement == "COMPLETE"
    assert book.is_measurable is True


def test_snapshot_book_declares_a_floor_when_a_live_reservation_is_unquantified() -> None:
    """Sin riesgo declarado la suma es un SUELO: la foto lo dice, no lo esconde."""
    complete = _reservation("RES-1", cash=1000.0, risk=20.0)
    opaque = _reservation("RES-2", cash=700.0, risk=None)

    book = snapshot_book(
        "2026-01-02",
        reservations=[complete, opaque],
        measurement="UNKNOWN",
    )

    assert book.live_reservations == 2
    assert book.unquantified_reservations == 1
    assert book.reserved_cash == pytest.approx(1700.0)
    assert book.reserved_risk == pytest.approx(20.0)  # solo lo cuantificable
    # La medición viaja NORMALIZADA: un valor no reconocido es UNKNOWN, no COMPLETE.
    assert book.measurement == "UNKNOWN"
    assert book.is_measurable is False


def test_snapshot_book_is_empty_and_complete_without_reservations() -> None:
    book = snapshot_book("2026-01-02", reservations=[], pending_orders=[], measurement="COMPLETE")
    assert book.live_reservations == 0
    assert book.reserved_cash == 0.0
    assert book.reserved_risk == 0.0
    assert book.is_measurable is True
    assert book.to_dict()["liveReservations"] == 0


def test_snapshot_book_ignores_an_unreadable_reservation_id_and_day() -> None:
    """Un día ilegible no se inventa: se publica en blanco (``""``)."""
    book = snapshot_book(None, reservations=[_reservation("RES-1")], measurement="COMPLETE")
    assert book.day == ""
    assert book.live_reservations == 1


# ── retiradas del libro: la firma del huérfano es ``CANCEL`` ──────────────────────


def test_release_deltas_counts_only_transitions_from_live() -> None:
    """Una reserva que YA estaba liberada no vuelve a contar: se mide el ciclo, no el catálogo."""
    before = [
        _released(_reservation("RES-OLD")),
        _reservation("RES-1"),
        _reservation("RES-2"),
    ]
    after = [
        _released(_reservation("RES-OLD")),
        _released(_reservation("RES-1"), status="RELEASED_BY_FILL"),
        _released(_reservation("RES-2"), status="RELEASED_BY_CANCEL"),
        _reservation("RES-3"),  # alta NUEVA del tick: no es una retirada
    ]

    delta = release_deltas(before, after)

    assert delta == {"RELEASED_BY_FILL": 1, "RELEASED_BY_CANCEL": 1}


def test_release_deltas_is_empty_when_nothing_was_retired() -> None:
    before = [_reservation("RES-1")]
    assert release_deltas(before, list(before)) == {}
    assert release_deltas([], []) == {}


def test_count_releases_tallies_the_whole_book_by_status() -> None:
    book = [
        _reservation("RES-1"),
        _released(_reservation("RES-2"), status="RELEASED_BY_FILL"),
        _released(_reservation("RES-3"), status="RELEASED_BY_FILL"),
        _released(_reservation("RES-4"), status="RELEASED_BY_CANCEL"),
        _released(_reservation("RES-5"), status="RELEASED_BY_RESTART"),
    ]

    counts = count_releases(book)

    assert counts == {
        "RELEASED_BY_FILL": 2,
        "RELEASED_BY_CANCEL": 1,
        "RELEASED_BY_RESTART": 1,
    }


def test_tally_releases_separates_the_log_total_from_the_tick_delta() -> None:
    """El acumulado lee el log entero; el delta solo las retiradas NUEVAS del tick."""
    first = {"reservationId": "RES-0", "status": "RELEASED_BY_FILL"}
    second = {"reservationId": "RES-1", "status": "RELEASED_BY_CANCEL"}

    tally = tally_releases([first], [first, second])

    assert tally.by_fill == 1  # acumulado del log
    assert tally.by_cancel == 1
    assert tally.delta_by_fill == 0  # el tick solo retiró el segundo
    assert tally.delta_by_cancel == 1
    assert tally.to_dict()["delta"] == {"RELEASED_BY_CANCEL": 1}


def test_tally_releases_delta_is_empty_when_no_new_event_arrived() -> None:
    log = [{"reservationId": "RES-0", "status": "RELEASED_BY_FILL"}]
    tally = tally_releases(log, log)
    assert tally.delta == {}
    assert tally.by_fill == 1


def test_release_deltas_ignores_rows_with_an_unreadable_status() -> None:
    """Un estado que no es una liberación reconocida NO cuenta: "no sé" ≠ "se retiró"."""
    weird = replace(_reservation("RES-X"), status="SOMETHING_ELSE")
    assert release_deltas([_reservation("RES-X")], [weird]) == {}
    assert count_releases([weird]) == {}


# ── horizonte: una truncación sin nombre se declara ───────────────────────────────


def test_declare_horizon_completes_only_with_every_tick_and_no_reason() -> None:
    horizon = declare_horizon(ticks=1224, total_ticks=1224, last_day="2026-09-28")
    assert horizon.completed is True
    assert horizon.truncation_reason is None
    assert horizon.last_day == "2026-09-28"


def test_declare_horizon_keeps_a_declared_reason_even_with_all_ticks() -> None:
    """Si el guardarraíl paró la corrida, manda la parada, no el conteo."""
    horizon = declare_horizon(
        ticks=500,
        total_ticks=500,
        last_day="2022-05-06",
        truncation_reason="book_measurement_unknown",
    )
    assert horizon.completed is False
    assert horizon.truncation_reason == "book_measurement_unknown"


def test_declare_horizon_names_an_undeclared_truncation() -> None:
    """Quedarse corto SIN causa publicada no se disfraza de ventana completa."""
    horizon = declare_horizon(ticks=13, total_ticks=1224, last_day="2022-05-06")
    assert horizon.completed is False
    assert horizon.truncation_reason == HORIZON_UNDECLARED


def test_declare_horizon_rejects_an_empty_reason_as_no_reason() -> None:
    horizon = declare_horizon(ticks=10, total_ticks=1224, truncation_reason="   ")
    assert horizon.truncation_reason == HORIZON_UNDECLARED
    assert horizon.completed is False


def test_declare_horizon_normalizes_counts_and_day() -> None:
    horizon = declare_horizon(ticks=5, total_ticks=5, last_day=" 2022-05-06T00:00:00Z ")
    assert horizon.ticks == 5
    assert horizon.total_ticks == 5
    assert horizon.last_day == "2022-05-06"
    assert horizon.completed is True


# ── puntuación: bucket por año ────────────────────────────────────────────────────


def test_score_replay_buckets_the_sample_by_exit_year() -> None:
    """Dos años ⇒ dos buckets: es la lectura de "multianual" frente a "un episodio"."""
    ticks = [
        _tick(
            "2022-03-01",
            fills=(ReplayFill("2022-03-01", "AAA", "buy", 10.0, 100.0),),
            stops={"AAA": 95.0},
        ),
        _tick("2022-04-01", fills=(ReplayFill("2022-04-01", "AAA", "sell", 10.0, 110.0),)),
        _tick(
            "2024-06-03",
            fills=(ReplayFill("2024-06-03", "BBB", "buy", 10.0, 100.0),),
            stops={"BBB": 90.0},
        ),
        _tick("2025-01-15", fills=(ReplayFill("2025-01-15", "BBB", "sell", 10.0, 95.0),)),
    ]

    report = score_replay(ticks)

    assert report.realized_count == 2
    by_year = report.by_year()
    assert set(by_year) == {"2022", "2025"}
    assert by_year["2022"]["count"] == 1
    assert by_year["2022"]["meanR"] == pytest.approx(2.0)
    assert by_year["2025"]["meanR"] == pytest.approx(-0.5)


def test_score_replay_declares_an_unreadable_exit_day_instead_of_guessing() -> None:
    ticks = [
        _tick(
            "2022-03-01",
            fills=(ReplayFill("2022-03-01", "AAA", "buy", 10.0, 100.0),),
            stops={"AAA": 95.0},
        ),
        _tick("weird", fills=(ReplayFill("weird", "AAA", "sell", 10.0, 110.0),)),
    ]

    report = score_replay(ticks)

    assert set(report.by_year()) == {"sin_fecha"}
    assert set(report.by_day()) == {"weird"}  # el día crudo se conserva; el año no se adivina
