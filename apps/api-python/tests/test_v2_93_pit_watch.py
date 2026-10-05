"""V2.93 — watch point-in-time POR DÍA (corrección del sesgo de anclaje al cierre).

Qué fija esta suite
-------------------
El defecto corregido: ``_year_watch`` resolvía el universo UNA vez por año anclado al
``YYYY-12-31``, así que un instrumento deslistado a mitad de año (elegible ene-may) quedaba
FUERA del watch de todo el año. Estos tests fijan las dos mitades del arreglo:

* ``_year_watch`` devuelve el SUPERCONJUNTO de candidatos (incluye al deslistado intra-año).
* ``_prune_bars_to_eligibility`` respeta la ventana: conserva las barras IN-WINDOW de los días
  elegibles y las FUERA del año (historia/horizonte) intactas.
"""

from __future__ import annotations

import importlib.util
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_application.universe_point_in_time import UniverseMember
from bolsa_application.universe_point_in_time_catalog import CatalogPointInTimeUniverse

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_V93_SCRIPT = _ROOT / "apps" / "api-python" / "scripts" / "v2_93_dia_d_multi.py"


def _load(path: pathlib.Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def v93() -> Any:
    return _load(_V93_SCRIPT, "v2_93_dia_d_multi")


def _member(instrument_id: str, *, active_until: str | None = None) -> UniverseMember:
    return UniverseMember(
        instrument_id=instrument_id,
        active_from="2018-01-01",
        active_until=active_until,
        availability_from="2018-01-02",
        availability_until=active_until,
        sector_at="Tech",
    )


def _bar(day: str) -> SimpleNamespace:
    return SimpleNamespace(timestamp=f"{day}T00:00:00")


def test_year_watch_keeps_intra_year_delisted_member(v93: Any) -> None:
    provider = CatalogPointInTimeUniverse.from_members(
        [
            _member("SURVIVOR"),
            _member("LEFT", active_until="2023-05-31"),
        ],
        historical=True,
    )
    source, watch, coverage = v93._year_watch(
        year=2023,
        args=SimpleNamespace(watch_size=10),
        provider=provider,
        explicit_watch=[],
        catalog_watch=None,
    )
    assert source == "pit"
    assert "LEFT" in watch  # el anclaje a 2023-12-31 lo habría excluido
    assert "SURVIVOR" in watch
    assert coverage is not None


def test_prune_keeps_eligible_days_and_out_of_window_bars(v93: Any) -> None:
    provider = CatalogPointInTimeUniverse.from_members(
        [_member("LEFT", active_until="2023-05-31")],
        historical=True,
    )
    days = ["2022-12-30", "2023-03-01", "2023-06-01", "2024-01-02"]
    bars = {
        "LEFT": [_bar(day) for day in days],
    }
    pruned, measured = v93._prune_bars_to_eligibility(
        bars, year=2023, provider=provider, days=days
    )
    kept = [bar.timestamp[:10] for bar in pruned["LEFT"]]
    # 2023-06-01 es IN-WINDOW no elegible ⇒ se poda; la historia y el horizonte se conservan.
    assert kept == ["2022-12-30", "2023-03-01", "2024-01-02"]
    assert measured == 2  # 2023-03-01 y 2023-06-01


def test_prune_does_not_invent_window_for_unmeasured_symbol(v93: Any) -> None:
    provider = CatalogPointInTimeUniverse.from_members([], historical=True)
    days = ["2023-03-01"]
    bars = {"MYSTERY": [_bar("2023-03-01")]}
    pruned, measured = v93._prune_bars_to_eligibility(
        bars, year=2023, provider=provider, days=days
    )
    assert [bar.timestamp[:10] for bar in pruned["MYSTERY"]] == ["2023-03-01"]
    assert measured == 1
