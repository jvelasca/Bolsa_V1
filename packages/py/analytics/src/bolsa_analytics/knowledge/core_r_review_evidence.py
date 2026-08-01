"""Evidence cola CORE-R — facts deterministas; LLM solo narra.

Bandas: empty | attention | urgent.
Entrada: filas de cola ya juzgadas (verdict/reason/symbol).
Salida: schema ``core_r_review_evidence_v1`` (claims, warnings, paragraphs×3).

No FA, no Coach, no overwrite TOP, no auto-paper D.
API: ``POST /api/ai/core-r/review-evidence`` via ``ExplainCoreRReviewEvidence``.
"""

from __future__ import annotations

from typing import Any, Literal

CoreREvidenceBand = Literal["empty", "attention", "urgent"]

SCHEMA = "core_r_review_evidence_v1"

_URGENT = frozenset({"consider_replace", "profile_mismatch"})
_ATTENTION = frozenset({"review_lab", "skipped_weak"})


def resolve_band(rows: list[dict[str, Any]]) -> CoreREvidenceBand:
    if not rows:
        return "empty"
    verdicts = {str(r.get("verdict") or "") for r in rows}
    if verdicts & _URGENT:
        return "urgent"
    if verdicts & _ATTENTION:
        return "attention"
    # keep / fresh_ok shouldn't be enqueued; treat as empty noise
    return "empty"


def build_core_r_review_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensambla Evidence v1 desde filas de cola ya juzgadas (sin FA/Coach/TOP)."""
    list_id = str(payload.get("listId") or payload.get("list_id") or "")
    timeframe = str(payload.get("timeframe") or "1d")
    raw_rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    rows: list[dict[str, Any]] = [r for r in raw_rows if isinstance(r, dict)]
    band = resolve_band(rows)

    symbols = [str(r.get("symbol") or "?") for r in rows]
    by_verdict: dict[str, int] = {}
    for r in rows:
        v = str(r.get("verdict") or "unknown")
        by_verdict[v] = by_verdict.get(v, 0) + 1

    claims = [
        f"Lista {list_id or '—'} · TF {timeframe} · {len(rows)} en revisión",
        "Veredictos: "
        + (
            ", ".join(f"{k}×{v}" for k, v in sorted(by_verdict.items()))
            if by_verdict
            else "ninguno"
        ),
    ]
    if symbols:
        claims.append("Valores: " + ", ".join(symbols[:12]))

    warnings: list[str] = []
    if band == "empty":
        warnings.append("Cola vacía o sin veredictos de acción.")
    if by_verdict.get("consider_replace", 0) > 0:
        warnings.append("Hay 'Valorar cambio': no pisa TOP; humano decide en Lab/Finalistas.")
    if by_verdict.get("profile_mismatch", 0) > 0:
        warnings.append("Perfil ≠ TOP: re-Play recomendado (CORE-P), no auto-paper.")

    if band == "empty":
        p1 = (
            "No hay ítems abiertos que requieran revisión CORE-R. "
            "Mantén el Monitor; Encolar tras Lista AUTO o si el PnL DEMO cae ≤ −5%."
        )
        p2 = (
            "CORE-R no ejecuta ni despliega. Solo encola juicios OOS/PnL/Lista AUTO "
            "con deep-links a Lab, Finalistas o Checklist."
        )
        p3 = (
            "Si activas auto-sync, solo corre mientras el panel Monitor está abierto. "
            "No es consejo de inversión ni escribe DEMO."
        )
    elif band == "urgent":
        top = rows[0]
        p1 = (
            f"Prioridad alta: {len(rows)} valor(es) a revisar "
            f"(p. ej. {top.get('symbol')} · {top.get('verdict')}). "
            f"Motivo: {top.get('reason') or 'ver cola'}."
        )
        p2 = (
            "Abre Lab o Finalistas desde la cola. Un consider_replace / profile_mismatch "
            "no sustituye el TOP: tú confirmas el cambio."
        )
        p3 = (
            "Contrasta OOS/PnL DEMO con el embudo. Sandbox DÍA D y DEMO live son cuentas distintas."
        )
    else:
        top = rows[0]
        p1 = (
            f"Atención: {len(rows)} valor(es) piden Revisar Lab "
            f"(p. ej. {top.get('symbol')}). Motivo: {top.get('reason') or 'ver cola'}."
        )
        p2 = (
            "Suele venir de OOS débil, PnL DEMO ≤ −5% o TOP sin lab_validated. "
            "Checklist paper si hay run #1."
        )
        p3 = (
            "Tras revisar, marca Hecho en la cola. CORE-R no pisa active ni lanza auto-paper D."
        )

    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    if band == "empty":
        confidence = "LOW"
    elif len(rows) >= 3 or band == "urgent":
        confidence = "HIGH"
    else:
        confidence = "MEDIUM"

    return {
        "schemaVersion": SCHEMA,
        "band": band,
        "confidence": confidence,
        "claims": claims,
        "warnings": warnings,
        "metrics": {
            "listId": list_id,
            "timeframe": timeframe,
            "openCount": len(rows),
            "considerReplace": by_verdict.get("consider_replace", 0),
            "reviewLab": by_verdict.get("review_lab", 0),
            "profileMismatch": by_verdict.get("profile_mismatch", 0),
            "skippedWeak": by_verdict.get("skipped_weak", 0),
        },
        "paragraphs": [p1, p2, p3],
        "disclaimer": (
            "Interpretación Evidence de la cola CORE-R. "
            "No recalcula FA ni Coach ni pisa Finalistas. "
            "No es consejo de inversión ni auto-paper D."
        ),
    }


def evidence_prompt_variables(evidence: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    claims = evidence.get("claims") if isinstance(evidence.get("claims"), list) else []
    warnings = evidence.get("warnings") if isinstance(evidence.get("warnings"), list) else []
    paragraphs = evidence.get("paragraphs") if isinstance(evidence.get("paragraphs"), list) else []
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    symbols = [
        str(r.get("symbol"))
        for r in rows
        if isinstance(r, dict) and r.get("symbol")
    ]
    return {
        "listId": str(payload.get("listId") or payload.get("list_id") or ""),
        "timeframe": str(payload.get("timeframe") or "1d"),
        "band": str(evidence.get("band") or ""),
        "confidence": str(evidence.get("confidence") or ""),
        "symbols": ", ".join(symbols[:12]),
        "claims": " | ".join(str(c) for c in claims),
        "warnings": " | ".join(str(w) for w in warnings) if warnings else "(ninguno)",
        "heuristic": " || ".join(str(p) for p in paragraphs),
        "disclaimer": str(evidence.get("disclaimer") or ""),
    }
