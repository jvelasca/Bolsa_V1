"""F0.6 Decision Board — vista SOLO LECTURA del spine de decisiones.

Agrupa las oportunidades pendientes de decidir de una cuenta:
  - Cola SEMI_F3 (dictamen por confirmar por el humano).
  - Decision sessions recientes (propose / gate / execution) con el outcome
    del gate extraído de ``payload``.

Esta vista NO decide, NO muta estado y NO invoca el orquestador ni ExecuteTrade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

# Estados de sesión que consideramos oportunidad aún abierta / por reevaluar.
# Fuera de este conjunto la sesión se considera "decidida" (no entra en buckets
# de pendientes). Criterio documentado: ver ``_classify_session``.
_OPEN_STATUS = frozenset({"open", "pending"})

GateOutcome = Literal["PASS", "VETO", "DEFERRED", "unknown"]


def extract_gate_outcome(payload: dict[str, Any] | None) -> GateOutcome:
    """Extrae el resultado del gate de decisión de un payload de sesión.

    Fuente principal (SoT de la rebanada): ``payload["compliance_check"]`` (si
    es dict). Por robustez ante los shapes reales persistidos (el package vive
    bajo ``runtime.decisionPackage.complianceCheck`` y ``to_dict()`` emite
    ``complianceCheck``), también contemplamos ``complianceCheck`` de nivel
    superior.

    Fallback final para sesiones AUTO del hot-path (``paper_auto`` /
    ``live_dry_run``): su persistencia NO usa ``compliance_check`` sino el
    bloque top-level ``payload["policyGate"]`` / ``payload["policy_gate"]`` con
    ``runtime=None``. Su shape es cualquiera de:

      - ``{"allowed": bool}`` (señal main del CognitiveGuardResult).
      - ``{"gate": {"passed": bool}}`` (PolicyGateResult anidado).
      - ``{"riskEngine": {"verdict": "ALLOW"|"DENY", "allowed": bool}}``.

    Reglas:
      - payload None o sin gate → "unknown". El fallback policyGate solo se
        intenta si el shape de compliance no arrojó un resultado (sin ``passed``).
      - ``compliance_check``: ``passed`` True → "PASS", False → "VETO".
      - ``skipped`` True con ``passed`` True y `reason` "deferred"/"no_opening" →
        "DEFERRED" (no hubo apertura de posición, no es un veto de oportunidad).
      - policyGate: ``allowed``/``passed`` True → "PASS", False → "VETO";
        ``verdict`` "DENY" → "VETO", "ALLOW" → "PASS". Sin señal → "unknown".

    Devuelve siempre una de: "PASS" | "VETO" | "DEFERRED" | "unknown".
    """
    if not isinstance(payload, dict):
        return "unknown"

    raw = payload.get("compliance_check")
    if not isinstance(raw, dict):
        # Fallback por robustez al shape canónico del DecisionPackage.
        raw = payload.get("complianceCheck")
    if not isinstance(raw, dict):
        runtime = payload.get("runtime")
        if isinstance(runtime, dict):
            pkg = runtime.get("decisionPackage")
            if isinstance(pkg, dict):
                candidate = pkg.get("complianceCheck")
                if isinstance(candidate, dict):
                    raw = candidate

    if isinstance(raw, dict):
        passed = raw.get("passed")
        if passed is True:
            if raw.get("skipped") is True:
                reason = str(raw.get("reason") or "")
                # Sin apertura de posición → oportunidad diferida, no ejecutable.
                if "deferr" in reason or "no_opening" in reason:
                    return "DEFERRED"
            return "PASS"
        if passed is False:
            return "VETO"

    # Fallback para sesiones AUTO del hot-path que persisten ``policyGate``
    # top-level (con ``runtime=None``) en lugar de ``compliance_check``.
    gate = payload.get("policyGate")
    if not isinstance(gate, dict):
        gate = payload.get("policy_gate")
    resolved = _resolve_policy_gate(gate)
    if resolved is not None:
        return resolved

    return "unknown"


def _resolve_policy_gate(gate: dict[str, Any] | None) -> GateOutcome | None:
    """Deriva PASS/VETO de un bloque ``policyGate`` persistido, o ``None``.

    ``None`` indica que el bloque no contenía una señal reconocida y el caller
    debe degradar a "unknown". Los shapes soportados están documentados en
    ``extract_gate_outcome``. La precedencia: campo ``allowed`` directo, luego el
    ``gate`` anidado (PolicyGateResult), luego ``riskEngine``.
    """
    if not isinstance(gate, dict):
        return None

    allowed = gate.get("allowed")
    if isinstance(allowed, bool):
        return "PASS" if allowed else "VETO"

    nested = gate.get("gate")
    if isinstance(nested, dict):
        passed = nested.get("passed")
        if isinstance(passed, bool):
            return "PASS" if passed else "VETO"

    risk = gate.get("riskEngine")
    if isinstance(risk, dict):
        verdict = risk.get("verdict")
        if isinstance(verdict, str):
            if verdict.upper() == "DENY":
                return "VETO"
            if verdict.upper() == "ALLOW":
                return "PASS"
        risk_allowed = risk.get("allowed")
        if isinstance(risk_allowed, bool):
            return "PASS" if risk_allowed else "VETO"

    return None


def _session_runtime(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """``payload.runtime`` dict o ``None`` (Ciclo 4.9 Board echo)."""
    if not isinstance(payload, dict):
        return None
    runtime = payload.get("runtime")
    return runtime if isinstance(runtime, dict) else None


def extract_session_trade_plan(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Lee ``runtime.tradePlan`` (camel o snake) para echo Hoy. Sin inventar."""
    runtime = _session_runtime(payload)
    if runtime is None:
        return None
    raw = runtime.get("tradePlan")
    if not isinstance(raw, dict):
        raw = runtime.get("trade_plan")
    if isinstance(raw, dict) and raw:
        return dict(raw)
    return None


def extract_session_wyckoff_anchor(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Lee ``runtime.wyckoffSpringAnchor`` para Setup thin en sesiones."""
    runtime = _session_runtime(payload)
    if runtime is None:
        return None
    raw = runtime.get("wyckoffSpringAnchor")
    if not isinstance(raw, dict):
        raw = runtime.get("wyckoff_spring_anchor")
    if isinstance(raw, dict) and raw:
        return dict(raw)
    return None


@dataclass(frozen=True, slots=True)
class DecisionSessionView:
    """Una sesión de decisión reciente expuesta en el tablero."""

    session_id: str
    kind: str
    status: str
    instrument_id: str
    symbol: str | None
    decision_id: str | None
    created_at: str
    gate: GateOutcome
    trade_plan: dict[str, Any] | None = None
    wyckoff_spring_anchor: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "sessionId": self.session_id,
            "kind": self.kind,
            "status": self.status,
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "decisionId": self.decision_id,
            "createdAt": self.created_at,
            "gate": self.gate,
        }
        if self.trade_plan is not None:
            data["tradePlan"] = self.trade_plan
        if self.wyckoff_spring_anchor is not None:
            data["wyckoffSpringAnchor"] = self.wyckoff_spring_anchor
        return data


@dataclass(frozen=True, slots=True)
class SemiF3View:
    """Un item de la cola SEMI_F3 pendiente de confirmación humana."""

    instrument_id: str | None
    symbol: str | None
    status: str = "pending_confirm"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        instrument_id: str | None = None,
        symbol: str | None = None,
        status: str = "pending_confirm",
        extra: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "instrument_id", instrument_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "extra", dict(extra or {}))

    def to_dict(self) -> dict[str, Any]:
        # Nested ``extra`` matches SemiF3ViewDto / Hoy (payload+tradePlan+anchor).
        data: dict[str, Any] = {
            "status": self.status,
            "extra": dict(self.extra),
        }
        if self.instrument_id:
            data["instrumentId"] = self.instrument_id
        if self.symbol:
            data["symbol"] = self.symbol
        return data


@dataclass(frozen=True, slots=True)
class DecisionBoardBucketCounts:
    """Contadores del tablero."""

    pending_confirm: int = 0
    vetoed: int = 0
    deferred: int = 0
    auto_waiting: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "pendingConfirm": self.pending_confirm,
            "vetoed": self.vetoed,
            "deferred": self.deferred,
            "autoWaiting": self.auto_waiting,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class DecisionBoardBundle:
    """Resultado del use-case (la ruta mapea a DTO HTTP)."""

    account_id: str
    generated_at: str
    semi_f3: list[SemiF3View]
    decision_sessions: list[DecisionSessionView]
    buckets: DecisionBoardBucketCounts
    equity: float | None = None
    free_margin: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "accountId": self.account_id,
            "generatedAt": self.generated_at,
            "buckets": self.buckets.to_dict(),
            "semiF3Queue": [s.to_dict() for s in self.semi_f3],
            "decisionSessions": [s.to_dict() for s in self.decision_sessions],
        }
        if self.equity is not None:
            data["equity"] = self.equity
        if self.free_margin is not None:
            data["freeMargin"] = self.free_margin
        return data


def _classify_session(status: str, gate: GateOutcome) -> str | None:
    """Clasifica una sesión de decisión en un bucket de pendiente o ``None``.

    Criterio de la vista (F0.6a, "tablero de acción"):
      - Sesión "decidida": ``status`` fuera de {open, pending} → ``None``
        (no es oportunidad pendiente; se sigue listando, pero no cuenta en buckets).
      - gate "VETO" y status abierto → bucket ``vetoed`` (AUTO vetado, oportunidad
        intacta, por reevaluar).
      - gate "DEFERRED" → bucket ``deferred`` (oportunidad diferida, sin apertura).
      - resto de abiertas (PASS o unknown) → bucket ``auto_waiting`` (AUTO en
        espera de decidir/ejecutar).
    """
    if status not in _OPEN_STATUS:
        return None
    if gate == "VETO":
        return "vetoed"
    if gate == "DEFERRED":
        return "deferred"
    return "auto_waiting"


class GetDecisionBoard:
    """Compone la vista de solo lectura del Decision Board para una cuenta."""

    def __init__(
        self,
        cognitive_repo: Any,
        f3_repo: Any,
        get_account_summary: Any | None = None,
        *,
        session_limit: int = 50,
    ) -> None:
        # ``get_account_summary`` es OPCIONAL: si se inyecta (UseCase GetAccountSummary),
        # se añade equity/exposición al bundle; si no, la vista no lleva esos campos.
        self._cognitive_repo = cognitive_repo
        self._f3_repo = f3_repo
        self._get_account_summary = get_account_summary
        self._session_limit = session_limit

    async def execute(self, account_id: str) -> DecisionBoardBundle:
        sessions = await self._cognitive_repo.list_decision_sessions(
            account_id=account_id, limit=self._session_limit
        )
        f3_state = await self._f3_repo.get(account_id)
        semi_items = list(f3_state.queue) if f3_state is not None else []

        counts = DecisionBoardBucketCounts()
        semi: list[SemiF3View] = []
        for item in semi_items:
            counts = _add_bucket(counts, "pending_confirm")
            semi.append(
                SemiF3View(
                    instrument_id=item.get("instrument_id") or item.get("instrumentId"),
                    symbol=item.get("symbol"),
                    extra={
                        k: v
                        for k, v in item.items()
                        if k not in {"instrument_id", "instrumentId", "symbol"}
                    },
                )
            )

        views: list[DecisionSessionView] = []
        for rec in sessions:
            gate = extract_gate_outcome(rec.payload)
            bucket = _classify_session(rec.status, gate)
            if bucket is not None:
                counts = _add_bucket(counts, bucket)
            views.append(
                DecisionSessionView(
                    session_id=rec.id,
                    kind=rec.kind,
                    status=rec.status,
                    instrument_id=rec.instrument_id,
                    symbol=rec.symbol,
                    decision_id=rec.decision_id,
                    created_at=rec.created_at,
                    gate=gate,
                    trade_plan=extract_session_trade_plan(rec.payload),
                    wyckoff_spring_anchor=extract_session_wyckoff_anchor(rec.payload),
                )
            )

        total = (
            counts.pending_confirm
            + counts.vetoed
            + counts.deferred
            + counts.auto_waiting
        )
        counts = DecisionBoardBucketCounts(
            pending_confirm=counts.pending_confirm,
            vetoed=counts.vetoed,
            deferred=counts.deferred,
            auto_waiting=counts.auto_waiting,
            total=total,
        )

        equity: float | None = None
        free_margin: float | None = None
        if self._get_account_summary is not None:
            try:
                summary = await self._get_account_summary.execute(account_id=account_id)
                equity = float(getattr(summary, "total_equity", None) or 0)
                free_margin = float(getattr(summary, "free_margin", None) or 0)
            except Exception:  # noqa: BLE001 — la vista de lectura no debe caer por exposición
                equity = None
                free_margin = None

        return DecisionBoardBundle(
            account_id=account_id,
            generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            semi_f3=semi,
            decision_sessions=views,
            buckets=counts,
            equity=equity,
            free_margin=free_margin,
        )


def _add_bucket(counts: DecisionBoardBucketCounts, key: str) -> DecisionBoardBucketCounts:
    """Retorna una copia del contador incrementando ``key`` (dataclass frozen)."""
    values = counts.to_dict()
    camel = {
        "pending_confirm": "pendingConfirm",
        "vetoed": "vetoed",
        "deferred": "deferred",
        "auto_waiting": "autoWaiting",
    }
    assert key in camel
    values[camel[key]] += 1
    return DecisionBoardBucketCounts(
        pending_confirm=values["pendingConfirm"],
        vetoed=values["vetoed"],
        deferred=values["deferred"],
        auto_waiting=values["autoWaiting"],
        total=values["total"],
    )


__all__ = [
    "DecisionBoardBundle",
    "DecisionBoardBucketCounts",
    "DecisionSessionView",
    "GetDecisionBoard",
    "SemiF3View",
    "extract_gate_outcome",
    "extract_session_trade_plan",
    "extract_session_wyckoff_anchor",
]
