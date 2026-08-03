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


def validate_backtest_coach_payload(payload: Any) -> list[str]:
    """Valida payload estructurado del coach de batería (narrate / adversary).

    Fallos → el caller debe degradar a heurística (payload None).
    No exige todos los campos: la prosa es opcional; tipado sí.
    """
    errors: list[str] = []
    if payload is None:
        return errors
    if not isinstance(payload, dict):
        return ["payload debe ser objeto JSON"]

    for key in ("headline", "regimeNarrative", "disclaimer"):
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            errors.append(f"{key} debe ser string")

    for key in ("analysis", "outlook"):
        if key not in payload or payload[key] is None:
            continue
        if not isinstance(payload[key], list):
            errors.append(f"{key} debe ser lista")
            continue
        if not all(isinstance(item, str) for item in payload[key]):
            errors.append(f"{key} debe contener solo strings")

    if "recommendations" in payload and payload["recommendations"] is not None:
        if not isinstance(payload["recommendations"], list):
            errors.append("recommendations debe ser lista")
        else:
            for i, rec in enumerate(payload["recommendations"]):
                if not isinstance(rec, dict):
                    errors.append(f"recommendations[{i}] debe ser objeto")
                    continue
                if "score" in rec and rec["score"] is not None:
                    try:
                        float(rec["score"])
                    except (TypeError, ValueError):
                        errors.append(f"recommendations[{i}].score no numérico")
                if "reasons" in rec and rec["reasons"] is not None:
                    if not isinstance(rec["reasons"], list) or not all(
                        isinstance(r, str) for r in rec["reasons"]
                    ):
                        errors.append(f"recommendations[{i}].reasons inválido")

    audit = payload.get("audit")
    if audit is not None:
        if not isinstance(audit, dict):
            errors.append("audit debe ser objeto")
        else:
            findings = audit.get("findings")
            if findings is not None:
                if not isinstance(findings, list):
                    errors.append("audit.findings debe ser lista")
                else:
                    for i, finding in enumerate(findings):
                        if not isinstance(finding, dict):
                            errors.append(f"audit.findings[{i}] debe ser objeto")
                            continue
                        action = finding.get("action")
                        if action is not None and action not in {
                            "veto",
                            "downgrade",
                            "confirm",
                            "note",
                        }:
                            errors.append(f"audit.findings[{i}].action inválido: {action!r}")
    return errors
