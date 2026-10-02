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
