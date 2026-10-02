"""Tests puros del vocabulario canónico del HECHO durable de protección (v2.88.26).

La regla de honestidad: un ``kind`` fuera del vocabulario se declara ``None`` ("no medido"),
nunca un literal inventado ni una cadena libre. El mismo hecho no debe viajar escrito de dos
formas, y el vocabulario es la composición declarada de las casas únicas (FSM + reason codes)
más la extensión ``T2_HIT``.
"""

from __future__ import annotations

import pytest

from bolsa_application.auto_reason_codes import PROTECT_REQUESTED, STOP_RATCHET_APPLIED
from bolsa_application.protection_event_kind import (
    PROTECTION_EVENT_KINDS,
    usable_protection_kind,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("PROTECT_APPLIED", "PROTECT_APPLIED"),
        ("protect_applied", "PROTECT_APPLIED"),
        ("  T1_HIT  ", "T1_HIT"),
        ("t2_hit", "T2_HIT"),
        ("TRAIL_ARMED", "TRAIL_ARMED"),
        ("trail_advanced", "TRAIL_ADVANCED"),
        ("TIME_EXIT", "TIME_EXIT"),
        ("THESIS_EXIT", "THESIS_EXIT"),
        ("EXIT_REQUESTED", "EXIT_REQUESTED"),
        (STOP_RATCHET_APPLIED, "STOP_RATCHET_APPLIED"),
        (PROTECT_REQUESTED, "PROTECT_REQUESTED"),
    ],
)
def test_usable_protection_kind_normalizes_the_vocabulary(raw: str, expected: str) -> None:
    assert usable_protection_kind(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "TOTALLY_MADE_UP", 0, 3.14, object()])
def test_usable_protection_kind_declares_unknown_as_none(raw: object) -> None:
    """Un valor inservible NO se convierte en un literal: se declara "no medido"."""
    assert usable_protection_kind(raw) is None


def test_vocabulary_is_closed_and_non_empty() -> None:
    assert PROTECTION_EVENT_KINDS  # no vacío
    for kind in PROTECTION_EVENT_KINDS:
        assert usable_protection_kind(kind) == kind


def test_vocabulary_carries_the_declared_extension_and_reused_houses() -> None:
    """Composición declarada: eventos del FSM + motivos de gestión + la extensión ``T2_HIT``."""
    assert "T2_HIT" in PROTECTION_EVENT_KINDS
    assert "T1_HIT" in PROTECTION_EVENT_KINDS
    assert "PROTECT_APPLIED" in PROTECTION_EVENT_KINDS
    # Los motivos de gestión (``auto_reason_codes``) viven en el vocabulario en forma canónica.
    assert STOP_RATCHET_APPLIED.upper() in PROTECTION_EVENT_KINDS
    assert PROTECT_REQUESTED.upper() in PROTECTION_EVENT_KINDS
