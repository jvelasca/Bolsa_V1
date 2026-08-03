"""Explica informe Evidence sesión DÍA D (LLM opcional; heurística siempre).

Proxy First: ``prompt_dia_d_session_evidence_v1``.
Sin LLM / fallo → ``engine=heuristic`` con párrafos de
``build_dia_d_session_evidence``.
"""

from __future__ import annotations

from typing import Any

from bolsa_analytics.knowledge.dia_d_session_evidence import (
    build_dia_d_session_evidence,
    evidence_prompt_variables,
)


class ExplainDiaDSessionEvidence:
    """Explica / narra Dia D Session Evidence."""
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence = build_dia_d_session_evidence(payload)
        heuristic_payload = {
            "paragraphs": list(evidence.get("paragraphs") or []),
            "disclaimer": evidence.get("disclaimer"),
            "band": evidence.get("band"),
            "claims": evidence.get("claims"),
            "warnings": evidence.get("warnings"),
            "metrics": evidence.get("metrics"),
            "confidence": evidence.get("confidence"),
            "schemaVersion": evidence.get("schemaVersion"),
        }

        try:
            from bolsa_ai import get_default_proxy

            proxy = get_default_proxy()
            completion = proxy.complete_structured(
                prompt_template_id="prompt_dia_d_session_evidence_v1",
                variables=evidence_prompt_variables(evidence, payload),
            )
        except Exception:  # noqa: BLE001
            completion = None

        if completion is None:
            return {
                "engine": "heuristic",
                "payload": heuristic_payload,
                "provider": None,
                "model": None,
                "evidence": evidence,
            }

        raw = completion.payload if isinstance(completion.payload, dict) else None
        paragraphs = raw.get("paragraphs") if raw else None
        if not isinstance(paragraphs, list) or len(paragraphs) < 1:
            return {
                "engine": "heuristic",
                "payload": heuristic_payload,
                "provider": completion.provider,
                "model": completion.model_name,
                "evidence": evidence,
            }

        cleaned = [str(p).strip() for p in paragraphs if str(p).strip()][:3]
        while len(cleaned) < 3:
            cleaned.append(str(evidence["paragraphs"][len(cleaned)]))
        disclaimer = (
            str(raw.get("disclaimer")).strip()
            if raw and raw.get("disclaimer")
            else evidence["disclaimer"]
        )
        return {
            "engine": f"{completion.provider}_structured_v1",
            "payload": {
                **heuristic_payload,
                "paragraphs": cleaned,
                "disclaimer": disclaimer,
            },
            "provider": completion.provider,
            "model": completion.model_name,
            "evidence": evidence,
        }
