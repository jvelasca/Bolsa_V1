"""Validación mínima de hints LLM (golden / adapters) — sin Pydantic obligatorio en F1."""

from __future__ import annotations

from typing import Any


def validate_strategy_hint(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "presetKey" not in payload and "draftKind" not in payload:
        errors.append("falta presetKey o draftKind")
    timeframe = payload.get("timeframe")
    if timeframe is not None and timeframe not in {"1d", "1wk", "1h", "4h"}:
        errors.append(f"timeframe inválido: {timeframe!r}")
    min_score = payload.get("minScore")
    if min_score is not None:
        try:
            score = int(min_score)
            if score < 0 or score > 100:
                errors.append("minScore fuera de 0-100")
        except (TypeError, ValueError):
            errors.append("minScore no numérico")
    return errors


def validate_indicator_hint(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not payload.get("definitionId"):
        errors.append("falta definitionId")
    period = payload.get("period")
    if period is not None:
        try:
            if int(period) < 1:
                errors.append("period debe ser >= 1")
        except (TypeError, ValueError):
            errors.append("period no numérico")
    return errors
