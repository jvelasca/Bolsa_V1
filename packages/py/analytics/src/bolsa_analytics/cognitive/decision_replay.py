"""Decision Replay — timeline auditable desde ART-DECISION-SESSION."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReplayStep:
    step_id: str
    title: str
    detail: str
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stepId": self.step_id,
            "title": self.title,
            "detail": self.detail,
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class DecisionReplay:
    session_id: str
    instrument_id: str
    symbol: str | None
    created_at: str | None
    kind: str | None
    steps: tuple[ReplayStep, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "createdAt": self.created_at,
            "kind": self.kind,
            "steps": [s.to_dict() for s in self.steps],
        }


def _pct(w: float | None) -> str:
    if w is None:
        return "—"
    return f"{round(float(w) * 100):.0f}%"


def build_decision_replay(session: dict[str, Any]) -> DecisionReplay:
    """
    Proyecta una DecisionSession (payload) a pasos de caja negra.
    No re-ejecuta motores: reproduce lo que se fotografió.
    """
    session_id = str(session.get("sessionId") or "")
    instrument_id = str(session.get("instrumentId") or "")
    symbol = session.get("symbol")
    steps: list[ReplayStep] = []

    # 1. Contexto
    ctx_bits = [
        f"kind={session.get('kind')}",
        f"status={session.get('status')}",
        f"tf={session.get('timeframe') or '—'}",
        f"horizon={session.get('horizon') or '—'}",
        f"regime={session.get('marketRegime') or '—'}",
    ]
    steps.append(
        ReplayStep(
            step_id="context",
            title="Contexto de sesión",
            detail=" · ".join(ctx_bits),
            payload={
                "profileSnapshotRef": session.get("profileSnapshotRef"),
                "policySnapshot": session.get("policySnapshot"),
                "lineage": session.get("lineage"),
            },
        )
    )

    # 2. Assessments
    assessments = session.get("assessments") or []
    if isinstance(assessments, list) and assessments:
        lines: list[str] = []
        for a in assessments:
            if not isinstance(a, dict):
                continue
            t = a.get("type") or a.get("assessmentType") or "?"
            score = a.get("score")
            bias = (a.get("metadata") or {}).get("bias") if isinstance(a.get("metadata"), dict) else a.get("bias")
            score_s = f"{float(score):+.3f}" if isinstance(score, (int, float)) else "—"
            lines.append(f"{t}: score={score_s}" + (f" bias={bias}" if bias else ""))
        steps.append(
            ReplayStep(
                step_id="assessments",
                title=f"Assessments ({len(lines)})",
                detail=" · ".join(lines) if lines else "Sin detalle tipado",
                payload={"assessments": assessments},
            )
        )
    else:
        steps.append(
            ReplayStep(
                step_id="assessments",
                title="Assessments",
                detail="Sin assessments en la fotografía",
                payload=None,
            )
        )

    # 3. Evidence / Predictions (auxiliares)
    evidence = session.get("evidence")
    if evidence:
        steps.append(
            ReplayStep(
                step_id="evidence",
                title="Evidence (no vota dirección)",
                detail="Edge/Evidence presente en sesión",
                payload=evidence if isinstance(evidence, dict) else {"raw": evidence},
            )
        )
    predictions = session.get("predictions") or []
    if isinstance(predictions, list) and predictions:
        first = predictions[0] if isinstance(predictions[0], dict) else {}
        mid = first.get("modelId") or "?"
        val = first.get("value")
        detail = f"{mid} · value={val} · no ordenan / no pesan"
        steps.append(
            ReplayStep(
                step_id="predictions",
                title=f"Predictions ({len(predictions)}) — no ordenan",
                detail=detail,
                payload={"predictions": predictions},
            )
        )

    # 4. WeightContext
    wc = session.get("weightContext")
    if isinstance(wc, dict):
        weights = wc.get("weights") or {}
        detail = (
            f"v{wc.get('ruleVersion', '?')} · {wc.get('horizon')}/{wc.get('regime')} · "
            f"TA {_pct(weights.get('ta'))} · FUND {_pct(weights.get('fund'))} · "
            f"Macro {_pct(weights.get('macro'))} · News {_pct(weights.get('news'))}"
        )
        missing = wc.get("missingAssessments") or []
        if missing:
            detail += f" · faltan: {', '.join(missing)}"
        steps.append(
            ReplayStep(
                step_id="weights",
                title="WeightContext",
                detail=detail,
                payload=wc,
            )
        )

    # 5. Runtime
    runtime = session.get("runtime")
    if isinstance(runtime, dict):
        cs = runtime.get("combinedScore")
        cs_s = f"{float(cs):+.3f}" if isinstance(cs, (int, float)) else "—"
        steps.append(
            ReplayStep(
                step_id="runtime",
                title="DecisionRuntime",
                detail=f"combinedScore={cs_s}",
                payload=runtime,
            )
        )

    # 6. Recommendation
    rec = session.get("recommendation")
    if isinstance(rec, dict):
        action = rec.get("action") or rec.get("side") or "?"
        rid = rec.get("recommendationId") or session.get("recommendationId") or "—"
        steps.append(
            ReplayStep(
                step_id="recommendation",
                title="Recommendation",
                detail=f"{action} · id={rid}",
                payload=rec,
            )
        )

    # 7. Gate
    gate = session.get("policyGate")
    if gate is not None:
        if isinstance(gate, dict):
            status = gate.get("status") or gate.get("mode") or "recorded"
            detail = f"status={status}"
            if gate.get("message"):
                detail += f" — {gate['message']}"
        else:
            detail = str(gate)
        steps.append(
            ReplayStep(
                step_id="gate",
                title="Policy Gate",
                detail=detail,
                payload=gate if isinstance(gate, dict) else {"raw": gate},
            )
        )

    # 8. Execution
    execution = session.get("execution")
    if execution:
        steps.append(
            ReplayStep(
                step_id="execution",
                title="Execution",
                detail="Resultado de ejecución fotografiado",
                payload=execution if isinstance(execution, dict) else {"raw": execution},
            )
        )
    else:
        steps.append(
            ReplayStep(
                step_id="execution",
                title="Execution",
                detail="Sin ejecución (propose / dry-run / no confirmado)",
                payload=None,
            )
        )

    # 9. Outcome
    outcome = session.get("outcome")
    if isinstance(outcome, dict):
        verdict = outcome.get("verdict") or "?"
        ret = outcome.get("returnPct")
        ret_s = f"{ret:+.2f}%" if isinstance(ret, (int, float)) else "n/a"
        steps.append(
            ReplayStep(
                step_id="outcome",
                title="Outcome",
                detail=f"{verdict} · return {ret_s} · {outcome.get('source') or '—'}"
                + (
                    " · maduro"
                    if outcome.get("mature") is True
                    else (
                        " · prematuro"
                        if outcome.get("mature") is False
                        else ""
                    )
                ),
                payload=outcome,
            )
        )
    elif outcome:
        steps.append(
            ReplayStep(
                step_id="outcome",
                title="Outcome",
                detail="Desenlace registrado",
                payload={"raw": outcome},
            )
        )
    else:
        steps.append(
            ReplayStep(
                step_id="outcome",
                title="Outcome",
                detail="Pendiente — ciclo Learning aún no cerrado",
                payload=None,
            )
        )

    return DecisionReplay(
        session_id=session_id,
        instrument_id=instrument_id,
        symbol=str(symbol) if symbol else None,
        created_at=session.get("createdAt"),
        kind=session.get("kind"),
        steps=tuple(steps),
    )
