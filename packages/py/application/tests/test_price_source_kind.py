"""Tests puros del vocabulario canónico de FUENTE de precio (v2.88.25, migración 047).

La regla de honestidad: un valor fuera del vocabulario se declara ``None`` ("no medido"), nunca un
literal inventado ni una cadena libre. El mismo hecho no debe viajar escrito de dos formas.
"""

from __future__ import annotations

import pytest

from bolsa_application.price_source_kind import (
    PRICE_SOURCE_KINDS,
    PRICE_SOURCE_MAPPING,
    PRICE_SOURCE_MARKET_CLOSE,
    PRICE_SOURCE_SCRIPT,
    PRICE_SOURCE_SYNTHETIC,
    canonical_price_source,
    price_source_snapshot_disagrees,
    usable_price_source,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("MARKET_CLOSE", PRICE_SOURCE_MARKET_CLOSE),
        ("market_close", PRICE_SOURCE_MARKET_CLOSE),
        ("  Synthetic  ", PRICE_SOURCE_SYNTHETIC),
        ("SCRIPT", PRICE_SOURCE_SCRIPT),
        ("MAPPING", PRICE_SOURCE_MAPPING),
    ],
)
def test_usable_price_source_normalizes_the_vocabulary(raw: str, expected: str) -> None:
    assert usable_price_source(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "TOTALLY_MADE_UP", 0, 3.14, object()])
def test_usable_price_source_declares_unknown_as_none(raw: object) -> None:
    """Un valor inservible NO se convierte en un literal: se declara "no medido"."""
    assert usable_price_source(raw) is None


def test_vocabulary_is_closed_and_non_empty() -> None:
    assert PRICE_SOURCE_KINDS  # no vacío
    for kind in PRICE_SOURCE_KINDS:
        assert usable_price_source(kind) == kind


def test_canonical_authority_is_the_fill_not_the_audit_snapshot() -> None:
    """v2.88.27 — si el fill y su snapshot difieren, GANA EL FILL (la autoridad declarada)."""
    assert (
        canonical_price_source(PRICE_SOURCE_MARKET_CLOSE, PRICE_SOURCE_SYNTHETIC)
        == PRICE_SOURCE_MARKET_CLOSE
    )
    # Un fill NO medido tampoco se rellena con el snapshot: la ausencia también es autoridad.
    assert canonical_price_source(None, PRICE_SOURCE_MARKET_CLOSE) is None


def test_snapshot_disagreement_requires_two_measurements() -> None:
    assert price_source_snapshot_disagrees(PRICE_SOURCE_MARKET_CLOSE, PRICE_SOURCE_SYNTHETIC) is True
    assert price_source_snapshot_disagrees(PRICE_SOURCE_MARKET_CLOSE, "market_close") is False
    # "No medido" NO es una discrepancia: faltaría una de las dos medidas.
    assert price_source_snapshot_disagrees(None, PRICE_SOURCE_SYNTHETIC) is None
    assert price_source_snapshot_disagrees(PRICE_SOURCE_MARKET_CLOSE, "TOTALLY_MADE_UP") is None
