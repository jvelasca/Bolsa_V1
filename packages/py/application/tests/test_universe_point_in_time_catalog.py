"""``CatalogPointInTimeUniverse`` — proveedor PIT real (barras) + aproximaciones declaradas.

Invariantes que se fijan aquí (D35-01, capacidad operativa):

* ``availability_from`` / ``availability_until`` salen de las **barras** (fuente REAL).
* ``active_from`` (``created_at``) y ``active_until`` (``is_active``) y ``sector_at`` son
  **aproximaciones DECLARADAS**; un instrumento ``is_active=False`` deja de ser elegible tras
  su última barra.
* Un instrumento sin barras NO es demostrable ⇒ inelegible (fail-closed).
* ``members``/``ids`` filtran por elegibilidad, deduplican y ordenan (deterministas).
"""

from __future__ import annotations

from datetime import date

from bolsa_application.universe_point_in_time_catalog import (
    CatalogPointInTimeUniverse,
)

#: Filas crudas tipo ``instruments``: ``(id, sector, is_active, created_at)``.
_AAA = ("AAA", "Tech", True, date(2018, 1, 1))
_BBB = ("BBB", "Energy", True, date(2019, 6, 1))
_DELISTED = ("OLD", "Tech", False, date(2015, 1, 1))
_NO_BARS = ("NOBARS", "Tech", True, date(2020, 1, 1))


def _bars(instrument_id: str, first: date, last: date, count: int = 100) -> tuple:
    """Fila cruda tipo agregado de barras: ``(id, min_ts, max_ts, count)``."""
    return (instrument_id, first, last, count)


def _universe(*, min_bars: int = 60) -> CatalogPointInTimeUniverse:
    return CatalogPointInTimeUniverse.from_catalog_rows(
        [
            _bars("AAA", date(2018, 1, 2), date(2025, 12, 31)),
            _bars("OLD", date(2015, 1, 5), date(2023, 5, 31)),
        ],
        [_AAA, _DELISTED, _NO_BARS],
        min_bars=min_bars,
    )


def test_availability_comes_from_bars_and_active_member_is_eligible() -> None:
    universe = _universe()
    members = {member.instrument_id: member for member in universe.members("2020-01-01")}
    aaa = members["AAA"]
    assert aaa.availability_from == "2018-01-02"
    assert aaa.availability_until == "2025-12-31"
    assert aaa.active_from == "2018-01-01"  # DECLARADO (created_at), no fecha de listado
    assert aaa.active_until is None  # is_active=True ⇒ abierto


def test_delisted_member_is_not_eligible_after_last_bar() -> None:
    universe = _universe(min_bars=1)
    # Dentro de barras: elegible (borde final inclusivo).
    assert any(m.instrument_id == "OLD" for m in universe.members("2023-05-31"))
    # Después de la última barra (cota declarada de baja): inelegible.
    assert not any(m.instrument_id == "OLD" for m in universe.members("2023-06-01"))
    old = next(m for m in universe.members("2023-05-31") if m.instrument_id == "OLD")
    assert old.active_until == "2023-05-31"


def test_member_without_bars_is_excluded_and_ineligible() -> None:
    universe = _universe()
    assert universe.excluded_no_bars == 1
    assert not any(m.instrument_id == "NOBARS" for m in universe.members("2020-01-01"))


def test_insufficient_bars_are_excluded_not_invented() -> None:
    universe = CatalogPointInTimeUniverse.from_catalog_rows(
        [_bars("AAA", date(2018, 1, 2), date(2018, 1, 10), count=7)],
        [_AAA],
        min_bars=60,
    )
    assert universe.coverage()["membersMaterialized"] == 0
    assert universe.coverage()["excludedInsufficientBars"] == 1


def test_unknown_start_cannot_be_demonstrated() -> None:
    universe = CatalogPointInTimeUniverse.from_catalog_rows(
        [_bars("AAA", date(2018, 1, 2), date(2025, 12, 31))],
        [("AAA", "Tech", True, None)],
        min_bars=1,
    )
    # created_at desconocido ⇒ active_from None ⇒ inelegible (fail-closed), pero materializado.
    assert universe.members("2020-01-01") == []


def test_require_sector_excludes_missing_sector() -> None:
    universe = CatalogPointInTimeUniverse.from_catalog_rows(
        [_bars("AAA", date(2018, 1, 2), date(2025, 12, 31))],
        [("AAA", None, True, date(2018, 1, 1))],
        min_bars=1,
        require_sector=True,
    )
    assert universe.coverage()["excludedNoSector"] == 1
    assert universe.members("2020-01-01") == []


def test_members_and_ids_are_deterministic_sorted_and_deduplicated() -> None:
    universe = CatalogPointInTimeUniverse.from_catalog_rows(
        [
            _bars("ZZZ", date(2018, 1, 2), date(2025, 12, 31)),
            _bars("AAA", date(2018, 1, 2), date(2025, 12, 31)),
        ],
        [
            ("ZZZ", "Tech", True, date(2018, 1, 1)),
            ("AAA", "Tech", True, date(2018, 1, 1)),
        ],
        min_bars=1,
    )
    assert universe.ids("2020-01-01") == ["AAA", "ZZZ"]
    assert [m.instrument_id for m in universe.members("2020-01-01")] == ["AAA", "ZZZ"]


def test_coverage_declares_real_and_declared_provenance() -> None:
    coverage = _universe().coverage()
    assert coverage["provider"] == "CatalogPointInTimeUniverse"
    assert coverage["provenance"]["availability_from"].startswith("REAL")
    assert coverage["provenance"]["active_from"].startswith("DECLARADO")
    assert coverage["provenance"]["sector_at"].startswith("DECLARADO")
    assert coverage["instrumentsConsidered"] == 3
