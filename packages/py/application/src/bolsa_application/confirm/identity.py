"""DEX-4 — Identity coordinator (contrato, side, TTL, orphan, precio)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_analytics.cognitive.trade_plan import (
    WYCKOFF_SPRING_ANCHOR_KEY,
    build_v0_trade_plan_dict,
    parse_wyckoff_spring_anchor,
)
from bolsa_application.confirm.actions import (
    _CLOSING_ACTIONS,
    _TRADE_ACTIONS,
    PRICE_REVALIDATION_MAX_REL_DEVIATION,
    is_closing_action,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord


def resolve_session_decision_package(
    session_record: DecisionSessionRecord | None,
) -> dict[str, Any] | None:
    """Extrae el DecisionPackage de una sesión `propose` persistida, si existe."""
    if session_record is None or not session_record.payload:
        return None
    runtime = session_record.payload.get("runtime") or {}
    pkg = runtime.get("decisionPackage")
    return pkg if isinstance(pkg, dict) else None


def required_fill_side(action: str, package_action: str | None) -> tuple[bool, str | None]:
    """Lado de llenado requerido para `action` dado el `action` de la sesión."""
    if action in {"recommend_long", "recommend_short"}:
        if package_action not in (None, action):
            return False, None
        return True, "buy" if action == "recommend_long" else "sell"
    if action in _CLOSING_ACTIONS:
        if package_action == "recommend_long":
            return True, "sell"
        if package_action == "recommend_short":
            return True, "buy"
        return False, None
    return True, None


def package_action_from_position_direction(
    direction: object,
    *,
    instrument_id: str,
) -> dict[str, Any] | None:
    """P4 — inferir tesis de cierre desde Position persistida."""
    if direction == "long":
        return {"action": "recommend_long", "instrumentId": instrument_id}
    if direction == "short":
        return {"action": "recommend_short", "instrumentId": instrument_id}
    return None


def reject_reason_for_execute(
    *,
    action: str,
    intent_side: str,
    intent_instrument_id: str,
    package: dict[str, Any] | None,
) -> str | None:
    """Motivo de rechazo fail-closed antes del fill, o `None` si procede."""
    if action not in _TRADE_ACTIONS:
        return "non_trade_action"
    pkg_action = None if package is None else package.get("action")
    determinable, required = required_fill_side(action, pkg_action)
    if not determinable:
        return "decision_package_conflict" if package is not None else "unknown_position_side"
    if intent_side != required:
        return "decision_package_conflict"
    if package is not None:
        pkg_instrument = package.get("instrumentId")
        if pkg_instrument is not None and pkg_instrument != intent_instrument_id:
            return "decision_package_conflict"
    return None


def parse_expires_at(raw: str | None) -> datetime | None:
    """ISO-8601 → datetime UTC; None si vacío o ilegible."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def recommendation_is_expired(expires_at: str | None, *, now: datetime | None = None) -> bool:
    """True si ``expiresAt`` está en el pasado (TTL ADR-031). Sin fecha → no caduca."""
    parsed = parse_expires_at(expires_at)
    if parsed is None:
        return False
    moment = now if now is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    return parsed < moment


def resolve_confirm_trade_plan(
    *,
    raw: dict[str, Any],
    rec: Recommendation,
    package: dict[str, Any] | None,
    session_record: DecisionSessionRecord | None,
) -> dict[str, Any]:
    """PLAN layer on confirm: echo propose payload, else rebuild v0."""
    incoming = raw.get("tradePlan")
    if isinstance(incoming, dict):
        return incoming

    runtime: dict[str, Any] | None = None
    if session_record is not None and session_record.payload:
        maybe_runtime = session_record.payload.get("runtime")
        if isinstance(maybe_runtime, dict):
            runtime = maybe_runtime
            session_plan = runtime.get("tradePlan")
            if isinstance(session_plan, dict):
                return session_plan

    opportunity: float | None = None
    wyckoff_prior: dict[str, object] | None = None
    if runtime is not None:
        raw_score = runtime.get("combinedScore")
        if isinstance(raw_score, int | float):
            opportunity = float(raw_score)
        wyckoff_prior = parse_wyckoff_spring_anchor(runtime.get(WYCKOFF_SPRING_ANCHOR_KEY))

    compliance = None if package is None else package.get("complianceCheck")
    entry: float | None = None
    if rec.suggested_price is not None:
        try:
            entry = float(rec.suggested_price)
        except (TypeError, ValueError):
            entry = None

    return build_v0_trade_plan_dict(
        decision_id=rec.decision_id,
        instrument_id=rec.instrument_id,
        action=str(rec.action),
        compliance_check=compliance,
        entry=entry,
        opportunity_score=opportunity,
        expires_at=rec.expires_at,
        expired=recommendation_is_expired(rec.expires_at),
        wyckoff_prior=wyckoff_prior,
    )


def price_revalidation_reason(
    suggested_price: float,
    last_close: float | None,
    *,
    max_rel_deviation: float = PRICE_REVALIDATION_MAX_REL_DEVIATION,
) -> str | None:
    """``stale_price`` si el close conocido se desvía más de la banda; None si no aplica."""
    if last_close is None:
        return None
    if last_close <= 0 or suggested_price <= 0:
        return "stale_price"
    rel = abs(suggested_price - last_close) / last_close
    if rel > max_rel_deviation:
        return "stale_price"
    return None


def extract_operativa_protect_meta(raw: dict[str, Any]) -> dict[str, Any] | None:
    """OI-1 — meta protect desde Consola (``wait`` + ``operativaIntent=protect``)."""
    pkg = raw.get("decisionPackage")
    if not isinstance(pkg, dict):
        return None
    if pkg.get("operativaIntent") != "protect":
        return None
    stop = pkg.get("suggestedStop")
    if not isinstance(stop, (int, float)) or float(stop) <= 0:
        return None
    return pkg


def resolve_protect_revision_origin(protect_meta: dict[str, Any]) -> str:
    """V1.43 — trail Confirm → PositionRevision origin=trail; else protect."""
    raw = protect_meta.get("revisionOrigin")
    if isinstance(raw, str) and raw.strip().lower() == "trail":
        return "trail"
    primary = protect_meta.get("primaryReason")
    if isinstance(primary, str) and primary.strip().upper() == "TRAIL":
        return "trail"
    return "protect"


def extract_operativa_exit_meta(raw: dict[str, Any]) -> dict[str, Any] | None:
    """V1.32 — meta reduce/exit_hint con plannedQty + ExitPlan snapshot."""
    pkg = raw.get("decisionPackage")
    if not isinstance(pkg, dict):
        return None
    if pkg.get("operativaIntent") not in {"reduce", "exit_hint"}:
        return None
    planned = pkg.get("plannedQty")
    if not isinstance(planned, (int, float)) or float(planned) <= 0:
        return None
    return pkg


def build_recommendation_from_raw(
    raw: dict[str, Any],
    *,
    account_id: str,
) -> Recommendation:
    metrics = raw.get("metrics") or {}
    return Recommendation(
        recommendation_id=str(raw.get("recommendationId") or raw.get("recommendation_id") or ""),
        decision_id=str(raw.get("decisionId") or ""),
        instrument_id=str(raw.get("instrumentId") or ""),
        action=str(raw.get("action") or "wait"),
        suggested_quantity=float(raw.get("suggestedQuantity") or 0),
        metrics={
            "confidence": float(metrics.get("confidence") or 0),
            "consensus": float(metrics.get("consensus") or 0),
            "evidenceStrength": float(metrics.get("evidenceStrength") or 0),
            "stability": float(metrics.get("stability") or 0),
            "conviction": float(metrics.get("conviction") or 0),
        },
        status="approved",
        created_at=str(raw.get("createdAt") or ""),
        symbol=raw.get("symbol"),
        account_id=account_id,
        suggested_price=raw.get("suggestedPrice"),
        expires_at=raw.get("expiresAt") or raw.get("expires_at"),
        notes=tuple(raw.get("notes") or ()),
    )


class IdentityCoordinator:
    """Contrato DecisionPackage + identidad pre-trade (TTL/orphan/precio/side)."""

    def __init__(
        self,
        *,
        cognitive_store: Any | None = None,
        ohlcv: Any | None = None,
        position_from_exit: Any | None = None,
    ) -> None:
        self._store = cognitive_store
        self._ohlcv = ohlcv
        self._position_from_exit = position_from_exit

    async def resolve_package(
        self,
        *,
        session_id: str | None,
    ) -> tuple[str, dict[str, Any] | None, DecisionSessionRecord | None]:
        contract_status: str = "absent"
        package: dict[str, Any] | None = None
        session_record: DecisionSessionRecord | None = None
        if self._store is not None and session_id:
            session_record = await self._store.get_decision_session(session_id)
            package = resolve_session_decision_package(session_record)
            if package is not None:
                contract_status = "present_verified"
        return contract_status, package, session_record

    async def effective_package_for_side(
        self,
        *,
        rec: Recommendation,
        account_id: str,
        package: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if package is not None:
            return package
        if not is_closing_action(rec.action) or self._position_from_exit is None:
            return None
        row = await self._position_from_exit.get_open(
            account_id, str(rec.instrument_id or "")
        )
        if row is None:
            return None
        from bolsa_application.persist_position_from_exit import row_position_state

        state = row_position_state(row)
        if state is None:
            return None
        return package_action_from_position_direction(
            state.get("direction"),
            instrument_id=str(rec.instrument_id or ""),
        )

    async def resolve_latest_close(self, instrument_id: str) -> float | None:
        if self._ohlcv is None or not instrument_id:
            return None
        getter = getattr(self._ohlcv, "get_latest_close", None)
        if getter is None:
            return None
        try:
            close = await getter(instrument_id)
        except Exception:  # noqa: BLE001
            return None
        if close is None:
            return None
        try:
            value = float(close)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    async def pretrade_reject_reason(
        self,
        *,
        rec: Recommendation,
        intent: Any,
        side_package: dict[str, Any] | None,
        package: dict[str, Any] | None,
        price: float,
    ) -> str | None:
        """Identity + TTL/orphan/precio. None = procede a gates de riesgo/salida."""
        reject_reason = reject_reason_for_execute(
            action=rec.action,
            intent_side=intent.side,
            intent_instrument_id=intent.instrument_id,
            package=side_package,
        )
        if recommendation_is_expired(rec.expires_at):
            return "expired"
        from bolsa_application.confirm.actions import is_opening_action

        if (
            reject_reason is None
            and is_opening_action(rec.action)
            and package is None
            and self._store is not None
        ):
            return "orphan_opening_blocked"
        if reject_reason is not None:
            return reject_reason

        if is_opening_action(rec.action) and self._ohlcv is not None:
            last_close = await self.resolve_latest_close(intent.instrument_id)
            return price_revalidation_reason(price, last_close)
        return None
