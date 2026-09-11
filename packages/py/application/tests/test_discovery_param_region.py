"""V2.38 (incremento 3) — tests del bucket de region de parametros (hermeticos).

Certifica la pieza pura que da granularidad a la evidencia adaptativa:

* determinismo (mismo grid + mismo punto ⇒ misma region),
* estabilidad ante reordenacion del mapping de entrada,
* fail-closed (punto fuera del grid ⇒ sin region),
* ida y vuelta de la clave compuesta,
* compatibilidad: sin region la clave es exactamente la familia,
* el espacio de busqueda NO cambia (anti-explosion intacto).
"""

from __future__ import annotations

from bolsa_application.discovery_catalog import (
    DISCOVERY_FAMILIES,
    iter_param_points,
)
from bolsa_application.discovery_param_region import (
    MATH_VERSION_PARAM_REGION_V0,
    compose_granularity_key,
    granularity_key_dimension,
    param_region_for_point,
    param_region_label,
    split_granularity_key,
)

_SPACE = {"fastPeriod": (10, 20), "slowPeriod": (50, 100)}


def _point(**kwargs: int) -> dict[str, int]:
    return dict(kwargs)


# ── Determinismo ────────────────────────────────────────────────────────────────


def test_same_point_yields_same_region() -> None:
    point = _point(fastPeriod=10, slowPeriod=50)
    assert param_region_for_point(_SPACE, point) == param_region_for_point(_SPACE, point)


def test_distinct_points_yield_distinct_regions() -> None:
    a = param_region_for_point(_SPACE, _point(fastPeriod=10, slowPeriod=50))
    b = param_region_for_point(_SPACE, _point(fastPeriod=20, slowPeriod=100))
    assert a and b and a != b


def test_region_is_stable_under_mapping_reordering() -> None:
    forward = {"fastPeriod": (10, 20), "slowPeriod": (50, 100)}
    reversed_space = {"slowPeriod": (50, 100), "fastPeriod": (10, 20)}
    point = _point(fastPeriod=10, slowPeriod=50)
    assert param_region_for_point(forward, point) == param_region_for_point(
        reversed_space, point
    )


def test_math_version_is_declared() -> None:
    assert MATH_VERSION_PARAM_REGION_V0 == "discovery_param_region_v0"


# ── Fail-closed ─────────────────────────────────────────────────────────────────


def test_point_outside_grid_has_no_region() -> None:
    assert param_region_for_point(_SPACE, _point(fastPeriod=7, slowPeriod=50)) == ""


def test_unknown_key_has_no_region() -> None:
    assert param_region_for_point(_SPACE, _point(period=14)) == ""


def test_empty_grid_has_no_region() -> None:
    assert param_region_for_point({}, {}) == ""


# ── Clave compuesta ─────────────────────────────────────────────────────────────


def test_compose_without_region_is_exactly_family() -> None:
    """Compatibilidad byte a byte con la agregacion historica (solo familia)."""
    assert compose_granularity_key("ema_crossover") == "ema_crossover"
    assert split_granularity_key("ema_crossover") == ("ema_crossover", "")


def test_compose_and_split_roundtrip() -> None:
    region = param_region_for_point(_SPACE, _point(fastPeriod=20, slowPeriod=100))
    key = compose_granularity_key("ema_crossover", region)
    assert key == f"ema_crossover|{region}"
    assert split_granularity_key(key) == ("ema_crossover", region)


def test_dimension_label() -> None:
    assert granularity_key_dimension("ema_crossover") == "family"
    assert granularity_key_dimension("ema_crossover|r01:abc") == "family+param_region"


def test_region_label_is_human_readable() -> None:
    label = param_region_label(_point(fastPeriod=10, slowPeriod=50))
    assert label == "fastPeriod=10,slowPeriod=50"


# ── Anti-explosion intacta ──────────────────────────────────────────────────────


def test_param_region_does_not_change_search_space() -> None:
    """Etiquetar no anade puntos: el grid de cada familia y el total son los mismos."""
    before = sum(len(family.param_points()) for family in DISCOVERY_FAMILIES)
    for family in DISCOVERY_FAMILIES:
        for point in iter_param_points(family.param_space):
            param_region_for_point(family.param_space, point)
    after = sum(len(family.param_points()) for family in DISCOVERY_FAMILIES)
    assert after == before
