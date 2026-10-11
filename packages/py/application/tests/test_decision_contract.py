"""H1 — ``format_active_strategy_source``: formato canónico (una sola fuente de verdad).

Fija el contrato de transporte de la fuente de una propuesta de la estrategia ACTIVE,
que el worker AUTO parsea:

* sin ``preset_key`` (``None``/vacío/solo espacios) ⇒ ``active-strategy:<version_id>``
  (identidad histórica, sin cambios).
* con ``preset_key`` no vacío ⇒ ``active-strategy:<version_id>::<preset_key>``.
"""

from __future__ import annotations

from bolsa_application.decision_contract import format_active_strategy_source


def test_source_without_preset_is_unchanged() -> None:
    assert format_active_strategy_source("ver-1", None) == "active-strategy:ver-1"


def test_source_with_empty_preset_is_unchanged() -> None:
    assert format_active_strategy_source("ver-1", "") == "active-strategy:ver-1"


def test_whitespace_only_preset_is_treated_as_absent() -> None:
    assert format_active_strategy_source("ver-1", "   ") == "active-strategy:ver-1"


def test_source_with_preset_uses_double_colon_separator() -> None:
    assert (
        format_active_strategy_source("ver-1", "sma_crossover")
        == "active-strategy:ver-1::sma_crossover"
    )


def test_preset_is_stripped_before_encoding() -> None:
    assert (
        format_active_strategy_source("ver-1", "  sma_crossover  ")
        == "active-strategy:ver-1::sma_crossover"
    )


def test_empty_version_stays_as_today() -> None:
    assert format_active_strategy_source("", None) == "active-strategy:"
