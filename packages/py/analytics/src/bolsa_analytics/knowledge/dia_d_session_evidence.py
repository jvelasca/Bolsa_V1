"""Evidence informe sesión C DÍA D — facts deterministas; LLM solo narra.

Bandas: favorable | mixed | adverse | incomplete.
Entrada: métricas auto/gated + gate (accept/reject) del sandbox D→hoy.
Salida: schema ``dia_d_session_evidence_v1`` (claims, warnings, paragraphs×3).

No FA, no Coach, no Belief, no DEMO live.
API narración: ``POST /api/ai/dia-d/session-evidence``.
Persist Fase 2: ``POST /api/research/dia-d-session-evidence`` (source=dia_d_session).
"""

from __future__ import annotations

from typing import Any, Literal

DiaDEvidenceBand = Literal["favorable", "mixed", "adverse", "incomplete"]

SCHEMA = "dia_d_session_evidence_v1"


def _fmt_pct(n: float) -> str:
    sign = "+" if n > 0 else ""
    return f"{sign}{n:.2f}%"


def resolve_band(payload: dict[str, Any]) -> DiaDEvidenceBand:
    mode = str(payload.get("mode") or "auto")
    auto = payload.get("auto") if isinstance(payload.get("auto"), dict) else {}
    gated = payload.get("gated") if isinstance(payload.get("gated"), dict) else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    accepted = int(gate.get("accepted") or 0)
    rejected = int(gate.get("rejected") or 0)
    auto_trades = int(auto.get("tradeCount") or 0)
    gated_ret = float(gated.get("totalReturnPct") or 0)
    auto_ret = float(auto.get("totalReturnPct") or 0)
    gated_dd = float(gated.get("maxDrawdownPct") or 0)
    auto_dd = float(auto.get("maxDrawdownPct") or 0)

    if mode != "auto" and accepted + rejected == 0 and auto_trades > 0:
        return "incomplete"
    delta = gated_ret - auto_ret
    if gated_ret <= -8 or delta <= -6:
        return "adverse"
    if gated_ret >= 0 and (delta >= -1 or rejected == 0) and gated_dd <= max(auto_dd, 15) + 2:
        return "favorable"
    if gated_ret >= 2 and delta >= 0:
        return "favorable"
    return "mixed"


def build_dia_d_session_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensambla Evidence v1 desde métricas ya calculadas (sin FA/Coach)."""
    mode = str(payload.get("mode") or "auto")
    symbol = str(payload.get("symbol") or "?")
    strategy = str(payload.get("strategyLabel") or "#1")
    dia_d = str(payload.get("diaD") or "")
    end_date = str(payload.get("endDate") or "")
    auto = payload.get("auto") if isinstance(payload.get("auto"), dict) else {}
    gated = payload.get("gated") if isinstance(payload.get("gated"), dict) else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    accepted = int(gate.get("accepted") or 0)
    rejected = int(gate.get("rejected") or 0)
    gated_ret = float(gated.get("totalReturnPct") or 0)
    auto_ret = float(auto.get("totalReturnPct") or 0)
    gated_dd = float(gated.get("maxDrawdownPct") or 0)
    gated_ops = int(gated.get("tradeCount") or 0)
    auto_ops = int(auto.get("tradeCount") or 0)
    final_eq = float(gated.get("finalEquity") or 0)
    delta = gated_ret - auto_ret
    band = resolve_band(payload)

    claims = [
        f"Modo {mode} · {symbol} · #1 {strategy}",
        f"Ventana {dia_d} → {end_date}",
        f"Retorno sesión {_fmt_pct(gated_ret)} · DD {_fmt_pct(gated_dd)} · {gated_ops} ops",
    ]
    if mode != "auto":
        claims.append(
            f"Vs Auto: retorno {_fmt_pct(delta)} · ops {gated_ops}/{auto_ops} · "
            f"gate OK/KO {accepted}/{rejected}"
        )
    else:
        claims.append(f"Trayectoria Auto (#1 congelada) · capital fin {final_eq:.2f}")
    if band == "incomplete":
        claims.append("Aún no hay decisiones de gate: el informe es provisional.")

    warnings: list[str] = []
    if band == "incomplete":
        warnings.append("Informe incompleto: sin decisiones Semi/Manual aún.")
    if gated_ops == 0 and mode == "auto" and auto_ops == 0:
        warnings.append("El run Auto no generó operaciones en D→hoy.")
    if gated_dd >= 20:
        warnings.append("Max DD ≥ 20%: revisar tamaño y filtros.")

    if band == "incomplete":
        p1 = (
            f"Sesión DÍA D de {symbol} en modo {mode}: hay {auto_ops} señales Auto "
            "pendientes de Aceptar/Rechazar. Hasta decidir, el equity gated no refleja tu criterio."
        )
    elif band == "favorable":
        p1 = (
            f"En {dia_d}→{end_date}, la sesión {mode} de {symbol} cierra con retorno "
            f"{_fmt_pct(gated_ret)} (DD {_fmt_pct(gated_dd)}). Coherente o mejor que el Auto."
        )
    elif band == "adverse":
        p1 = (
            f"La sesión {mode} de {symbol} termina con retorno {_fmt_pct(gated_ret)} y DD "
            f"{_fmt_pct(gated_dd)}. Respecto al Auto ({_fmt_pct(auto_ret)}) el delta es {_fmt_pct(delta)}."
        )
    else:
        p1 = (
            f"Resultado mixto en {symbol}: retorno {_fmt_pct(gated_ret)} vs Auto "
            f"{_fmt_pct(auto_ret)} (delta {_fmt_pct(delta)}), con {gated_ops} ops."
        )

    if mode == "auto":
        p2 = (
            "Modo Auto ejecuta todas las señales de #1 sin filtro humano. "
            "Úsalo como referencia; Semi/Manual miden el valor de tus vetos."
        )
    elif rejected > 0:
        p2 = (
            f"Gate: {accepted} aceptadas y {rejected} rechazadas. "
            "Un buy rechazado anula su sell; el equity se reescribe solo con accepts."
        )
    else:
        p2 = (
            f"Gate: {accepted} aceptadas y ninguna rechazo. "
            "La trayectoria se acerca al Auto; conviene contrastar DD y nº de ops."
        )

    if band == "incomplete":
        p3 = (
            "Siguiente: recorre la película, decide cada señal y vuelve a este informe. "
            "No es consejo de inversión ni despliegue DEMO."
        )
    elif band == "adverse":
        p3 = (
            "Revisa si los rechazos evitaron pérdidas o cortaron winners. "
            "Contrasta con el embudo ≤ D. Sandbox ≠ DEMO live."
        )
    else:
        p3 = (
            "Guarda el aprendizaje: qué señales vetaste y por qué. "
            "El embudo ≤ D es otro informe; este solo cubre D→hoy. Sandbox ≠ DEMO live."
        )

    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    if band == "incomplete":
        confidence = "LOW"
    elif mode == "auto" or accepted + rejected >= 3:
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
            "mode": mode,
            "returnPct": gated_ret,
            "maxDrawdownPct": gated_dd,
            "tradeCount": gated_ops,
            "finalEquity": final_eq,
            "autoReturnPct": auto_ret,
            "returnDeltaVsAutoPct": delta,
            "accepted": accepted,
            "rejected": rejected,
        },
        "paragraphs": [p1, p2, p3],
        "disclaimer": (
            "Interpretación Evidence de la sesión sandbox DÍA D. "
            "No recalcula FA ni Coach. No es consejo de inversión ni escribe la DEMO live."
        ),
    }


def evidence_prompt_variables(evidence: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    claims = evidence.get("claims") if isinstance(evidence.get("claims"), list) else []
    warnings = evidence.get("warnings") if isinstance(evidence.get("warnings"), list) else []
    paragraphs = evidence.get("paragraphs") if isinstance(evidence.get("paragraphs"), list) else []
    return {
        "symbol": str(payload.get("symbol") or ""),
        "mode": str(payload.get("mode") or ""),
        "band": str(evidence.get("band") or ""),
        "confidence": str(evidence.get("confidence") or ""),
        "claims": " | ".join(str(c) for c in claims),
        "warnings": " | ".join(str(w) for w in warnings) or "(ninguno)",
        "heuristic": " || ".join(str(p) for p in paragraphs),
        "disclaimer": str(evidence.get("disclaimer") or ""),
    }
