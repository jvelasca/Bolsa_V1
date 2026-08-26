"""DEX-4 — Confirm coordinators (Confirm = orquestador; ADR-035)."""

from __future__ import annotations

_OPENING_ACTIONS = {"recommend_long", "recommend_short"}
_CLOSING_ACTIONS = {"exit_hint", "reduce"}
# Acciones transaccionales que pueden llegar a ExecuteTrade (solo estas).
# `wait` NO está: una tesis `wait` no abre ni cierra posición (Bug 1).
_TRADE_ACTIONS = _OPENING_ACTIONS | _CLOSING_ACTIONS

# ADR-031 — banda de revalidación de precio (último close vs suggestedPrice).
PRICE_REVALIDATION_MAX_REL_DEVIATION = 0.02


def is_opening_action(action: str) -> bool:
    """¿La recommendation abre una posición (sujeta al VETO de cesta en SEMI)?"""
    return action in _OPENING_ACTIONS


def is_closing_action(action: str) -> bool:
    """¿La recommendation cierra o reduce (cadena P3, no cesta)?"""
    return action in _CLOSING_ACTIONS
