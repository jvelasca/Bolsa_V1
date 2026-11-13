"""Validación mínima de hints LLM (golden / adapters) — sin Pydantic obligatorio en F1."""

from __future__ import annotations

from typing import Any

#: ADR-049 §2.3 — **enum cerrado** de mutaciones que la IA puede proponer. Cualquier valor
#: fuera de esta lista invalida la propuesta completa: la IA no improvisa operaciones.
ADAPTATION_MUTATIONS: tuple[str, ...] = (
    "tighten_stop_atr",
    "loosen_stop_atr",
    "raise_payoff_target",
    "lower_payoff_target",
    "add_regime_filter",
    "remove_regime_filter",
    "disable_family",
    "enable_family",
    "adjust_entry_confirmation",
    "adjust_position_sizing_cap",
)

#: Claves admitidas en una propuesta. Una clave extra invalida TODO el payload.
ADAPTATION_PROPOSAL_KEYS = frozenset(
    {
        "mutation",
        "rationale",
        "expectedEffect",
        "evidenceRefs",
        "boundsRespected",
        "riskNote",
    }
)

#: Claves admitidas en la raíz del payload del proxy.
ADAPTATION_PAYLOAD_KEYS = frozenset({"proposals"})


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


def validate_adaptation_proposal_payload(payload: Any) -> list[str]:
    """Valida ``AdaptationProposalV1`` del proxy (ADR-049 §2.2–§2.3).

    Fallos ⇒ el caller descarta el payload y declara ``heuristic_fallback``; la IA no puede
    colar una mutación fuera del enum ni un campo inventado. Se validan **todas** las
    propuestas: una sola inválida tumba el payload completo.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload debe ser objeto JSON"]

    extra_root = sorted(set(payload) - ADAPTATION_PAYLOAD_KEYS)
    if extra_root:
        errors.append(f"claves no permitidas en la raíz: {', '.join(extra_root)}")

    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        return [*errors, "proposals debe ser lista"]
    if not proposals:
        return [*errors, "proposals no puede estar vacío"]

    for index, proposal in enumerate(proposals):
        prefix = f"proposals[{index}]"
        if not isinstance(proposal, dict):
            errors.append(f"{prefix} debe ser objeto")
            continue
        extra = sorted(set(proposal) - ADAPTATION_PROPOSAL_KEYS)
        if extra:
            errors.append(f"{prefix}: claves no permitidas: {', '.join(extra)}")

        mutation = proposal.get("mutation")
        if mutation not in ADAPTATION_MUTATIONS:
            errors.append(f"{prefix}.mutation inválida: {mutation!r}")

        for key in ("rationale", "expectedEffect", "riskNote"):
            value = proposal.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{key} debe ser texto no vacío")

        refs = proposal.get("evidenceRefs")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(ref, str) and ref.strip() for ref in refs
        ):
            errors.append(f"{prefix}.evidenceRefs debe ser lista de referencias no vacía")

        if proposal.get("boundsRespected") is not True:
            # Booleano estricto: ``"true"`` o ``1`` no demuestran que se respetaron las cotas.
            errors.append(f"{prefix}.boundsRespected debe ser true")

    return errors
