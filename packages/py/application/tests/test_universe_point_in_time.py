"""Contrato ``Universe(D)`` — elegibilidad point-in-time DEMOSTRABLE (D35-01).

Invariantes que se fijan aquí:

* Un miembro es elegible en ``D`` solo si ``D`` cae DENTRO de sus intervalos de actividad y
  de disponibilidad: un activo con fin de actividad (delistado) deja de ser elegible.
* Un inicio desconocido NO se puede demostrar ⇒ inelegible (fail-closed).
* Un id nulo/vacío NUNCA es un instrumento.
* ``universe_ids`` filtra por elegibilidad, deduplica y ordena (determinista).
"""

from __future__ import annotations

from collections.abc import Sequence

from bolsa_application.universe_point_in_time import (
    UniverseMember,
    eligible_at,
    universe_ids,
)


def _member(
    instrument_id: str = "AAA",
    *,
    active_from: str | None = "2018-01-01",
    active_until: str | None = None,
    availability_from: str | None = "2018-01-02",
    availability_until: str | None = None,
    sector_at: str | None = "Tech",
) -> UniverseMember:
    return UniverseMember(
        instrument_id=instrument_id,
        active_from=active_from,
        active_until=active_until,
        availability_from=availability_from,
        availability_until=availability_until,
        sector_at=sector_at,
    )


def test_member_within_open_intervals_is_eligible() -> None:
    assert eligible_at(_member(), "2025-06-01") is True


def test_delisted_member_is_not_eligible_after_active_until() -> None:
    # El hallazgo D35-01: sin fecha de fin no podíamos descartar un delistado.
    delisted = _member(active_until="2023-05-31")
    assert eligible_at(delisted, "2023-05-31") is True  # borde inclusivo
    assert eligible_at(delisted, "2023-06-01") is False
    assert eligible_at(delisted, "2025-06-01") is False


def test_member_is_not_eligible_before_active_from() -> None:
    assert eligible_at(_member(), "2017-12-31") is False


def test_unknown_start_cannot_be_demonstrated() -> None:
    assert eligible_at(_member(active_from=None), "2025-06-01") is False
    assert eligible_at(_member(availability_from=None), "2025-06-01") is False


def test_blank_id_or_unreadable_day_is_not_eligible() -> None:
    assert eligible_at(_member(instrument_id=""), "2025-06-01") is False
    assert eligible_at(_member(instrument_id="   "), "2025-06-01") is False
    assert eligible_at(_member(), "no-es-una-fecha") is False
    assert eligible_at(_member(), "") is False
    assert eligible_at(_member(), None) is False


def test_availability_window_bounds_eligibility() -> None:
    limited = _member(availability_until="2024-01-10")
    assert eligible_at(limited, "2024-01-10") is True
    assert eligible_at(limited, "2024-01-11") is False


class _FakeUniverse:
    def __init__(self, members: Sequence[UniverseMember]) -> None:
        self._members = list(members)

    def members(self, day: str) -> Sequence[UniverseMember]:
        return list(self._members)


def test_universe_ids_filters_ineligible_deduplicates_and_sorts() -> None:
    universe = _FakeUniverse(
        [
            _member("BBB"),
            _member("AAA"),
            _member("AAA"),  # duplicado
            _member("OLD", active_until="2020-01-01"),  # ya no elegible en D
            _member(""),  # id inválido
        ]
    )
    assert universe_ids(universe, "2025-06-01") == ["AAA", "BBB"]
