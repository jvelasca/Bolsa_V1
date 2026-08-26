"""Decision Journal 2.0 — vista Tesis (ADR-036). Solo lectura; no duplica TradePlan."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

from bolsa_application.decision_board import (
    extract_session_thesis_health,
    extract_session_trade_plan,
)

NO_OPERATIONAL_PLAN_COPY = "No existe todavía un plan operativo."
ARTIFACT_TYPE = "ART-DECISION-JOURNAL-STUDY"
SCHEMA_VERSION = "1.0.0"
STUDY_SESSION_LIMIT = 500

_EMPTY_GEOMETRY: dict[str, Any] = {
    "entry": None,
    "stop": None,
    "target1": None,
    "target2": None,
    "expectedRR": None,
    "riskAmount": None,
    "hasOperationalPlan": False,
}

_TREND_PRIMARY_LABELS = {
    "strong_bullish": "Fuertemente alcista",
    "bullish": "Alcista",
    "weak": "Neutra / rango",
    "bearish": "Bajista",
    "strong_bearish": "Fuertemente bajista",
}

_STRUCTURE_SMA_LABELS = {
    "bullish_stack": "Alcista",
    "bearish_stack": "Bajista",
    "mixed": "Mixta",
}

_INVALIDATOR_LABELS = {
    "exhaustion": "Agotamiento del movimiento",
    "distress": "Distress fundamental",
    "crisis": "Régimen de crisis",
    "luck": "Señal poco robusta (suerte)",
}

_THESIS_HEALTH_WHY_LABELS = {
    "confidence_degraded": "Confianza degradada",
    "stop_intact": "Stop estructural aún intacto",
    "hard_exit": "Salida dura señalada",
    "expired": "Plan caducado",
}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number:  # NaN
        return None
    return number


def _camel(plan: dict[str, Any], camel: str, snake: str) -> Any:
    if camel in plan:
        return plan.get(camel)
    return plan.get(snake)


def journal_study_has_valid_stop(plan: dict[str, Any] | None) -> bool:
    if not isinstance(plan, dict):
        return False
    why = plan.get("whyNot") or plan.get("why_not") or []
    if isinstance(why, list) and "no_stop" in why:
        return False
    entry = _finite(_camel(plan, "entry", "entry"))
    stop = _finite(_camel(plan, "structuralStop", "structural_stop"))
    direction = str(plan.get("direction") or "")
    if entry is None or entry <= 0 or stop is None:
        return False
    if direction == "long":
        return stop < entry
    if direction == "short":
        return stop > entry
    return False


def journal_study_geometry(plan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return dict(_EMPTY_GEOMETRY)
    status = str(plan.get("status") or "")
    if status not in {"ARMED", "TRIGGERED"}:
        return dict(_EMPTY_GEOMETRY)
    if not journal_study_has_valid_stop(plan):
        return dict(_EMPTY_GEOMETRY)
    return {
        "entry": _finite(plan.get("entry")),
        "stop": _finite(_camel(plan, "structuralStop", "structural_stop")),
        "target1": _finite(_camel(plan, "target1", "target_1")),
        "target2": _finite(_camel(plan, "target2", "target_2")),
        "expectedRR": _finite(_camel(plan, "expectedRR", "expected_rr")),
        "riskAmount": _finite(_camel(plan, "riskAmount", "risk_amount")),
        "hasOperationalPlan": True,
    }


def map_journal_study_opinion(*, bias: str | None, action: str | None) -> str | None:
    if bias in {"bullish", "bearish", "neutral"}:
        return bias
    if action == "recommend_long":
        return "bullish"
    if action == "recommend_short":
        return "bearish"
    if action in {"wait", "reduce", "exit_hint"}:
        return "neutral"
    return None


def map_journal_study_period(timeframe: str | None) -> str | None:
    if not timeframe:
        return None
    tf = timeframe.strip()
    lower = tf.lower()
    if lower in {"1d", "d", "daily", "1day"}:
        return "daily"
    if lower in {"1w", "1wk", "w", "weekly", "1week"}:
        return "weekly"
    if tf == "1M" or lower in {"1mo", "monthly", "1month", "1mon"}:
        return "monthly"
    return None


def map_journal_study_strength(overall_confidence: Any) -> float | None:
    value = _finite(overall_confidence)
    if value is None:
        return None
    clamped = min(1.0, max(0.0, value))
    return round(clamped * 100) / 10.0


def map_journal_study_strength_band(strength: float | None) -> str | None:
    if strength is None:
        return None
    if strength >= 8:
        return "very_strong"
    if strength >= 6:
        return "strong"
    if strength >= 4:
        return "moderate"
    if strength >= 2:
        return "weak"
    if strength >= 0:
        return "very_weak"
    return None


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def map_journal_study_vigencia(*, now: datetime, expires_at: str | None) -> str | None:
    expires = _parse_iso(expires_at)
    if expires is None:
        return None
    if now > expires:
        return "expired"
    if expires - now <= timedelta(hours=24):
        return "expiring_soon"
    return "current"


def map_journal_study_age_ms(studied_at: str, now: datetime) -> int | None:
    at = _parse_iso(studied_at)
    if at is None:
        return None
    age = int((now - at).total_seconds() * 1000)
    return max(0, age)


def map_journal_study_status(
    *,
    position_status: str | None = None,
    proposal_status: str | None = None,
    recommendation_status: str | None = None,
    exit_primary_reason: str | None = None,
    trade_plan_status: str | None = None,
    trade_plan_why_not: list[str] | None = None,
    action: str | None = None,
    bias: str | None = None,
    has_open_position: bool = False,
    has_live_plan: bool = False,
    has_operational_plan: bool = False,
) -> str:
    proposal = (proposal_status or recommendation_status or "").strip().lower()
    why = trade_plan_why_not or []

    if position_status == "CLOSED":
        return "closed"
    if proposal in {"rejected", "superseded"}:
        return "cancelled"
    if exit_primary_reason == "THESIS_INVALIDATION":
        return "invalidated"
    if exit_primary_reason in {"TARGET_1", "TARGET_2"}:
        return "target_reached"
    if trade_plan_status == "TRIGGERED" and (has_open_position or has_live_plan):
        return "target_active"

    wait_or_neutral = action == "wait" or bias == "neutral"
    if wait_or_neutral and not has_operational_plan:
        return "neutral"

    no_plan = trade_plan_status is None
    no_stop = "no_stop" in why
    if no_plan or no_stop:
        return "no_target"

    directional = bias in {"bullish", "bearish"} or action in {
        "recommend_long",
        "recommend_short",
    }
    if trade_plan_status in {"ARMED", "WATCH"} and directional:
        return "in_progress"
    return "closed"


def _read_bias(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    direct = value.get("bias")
    if direct in {"bullish", "bearish", "neutral"}:
        return str(direct)
    meta = value.get("metadata")
    if isinstance(meta, dict):
        nested = meta.get("bias")
        if nested in {"bullish", "bearish", "neutral"}:
            return str(nested)
    return None


def map_journal_study_consensus(assessments: list[Any] | None) -> dict[str, int]:
    bullish = bearish = neutral = 0
    for item in assessments or []:
        bias = _read_bias(item)
        if bias == "bullish":
            bullish += 1
        elif bias == "bearish":
            bearish += 1
        elif bias == "neutral":
            neutral += 1
    return {
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "total": bullish + bearish + neutral,
    }


def map_journal_study_trends(
    facts: list[dict[str, Any]] | None,
    fallback_opinion: str | None,
) -> list[dict[str, Any]]:
    trends: list[dict[str, Any]] = []
    primary = next((f for f in facts or [] if f.get("key") == "trend.primary"), None)
    structure = next((f for f in facts or [] if f.get("key") == "structure.sma"), None)
    short_display = None
    short_value = None
    if isinstance(primary, dict):
        value = str(primary.get("value") or "")
        short_value = value
        short_display = (
            _TREND_PRIMARY_LABELS.get(value)
            or primary.get("claim")
            or value
            or None
        )
    elif fallback_opinion == "bullish":
        short_display = "Alcista"
        short_value = fallback_opinion
    elif fallback_opinion == "bearish":
        short_display = "Bajista"
        short_value = fallback_opinion
    elif fallback_opinion == "neutral":
        short_display = "Neutra"
        short_value = fallback_opinion
    if short_display:
        trends.append(
            {
                "key": "short_term",
                "label": "Corto plazo",
                "value": short_value,
                "display": short_display,
            }
        )
    if isinstance(structure, dict):
        value = str(structure.get("value") or "")
        trends.append(
            {
                "key": "background",
                "label": "De fondo",
                "value": value,
                "display": _STRUCTURE_SMA_LABELS.get(value)
                or structure.get("claim")
                or value,
            }
        )
    return trends


def map_journal_study_indicators(facts: list[dict[str, Any]] | None) -> dict[str, str | None]:
    refs: set[str] = set()
    for fact in facts or []:
        raw_refs = fact.get("refs")
        if isinstance(raw_refs, dict):
            refs.update(str(k).lower() for k in raw_refs)
    primary: list[str] = []
    if {"adx", "plus_di", "minus_di"} & refs:
        primary.append("ADX + DI")
    if {"atr", "atr_percentile"} & refs:
        primary.append("ATR")
    confirm: list[str] = []
    if "rsi" in refs:
        confirm.append("RSI")
    if {"sma_20", "sma_50", "sma20", "sma50"} & refs:
        confirm.append("SMA")
    return {
        "primary": " + ".join(primary) if primary else None,
        "confirmation": " + ".join(confirm) if confirm else None,
    }


def map_journal_study_invalidation(
    *,
    direction: str | None,
    structural_stop: float | None,
    has_operational_plan: bool,
    invalidators: list[str] | None = None,
    reevaluate_when: list[str] | None = None,
    thesis_health_why: list[str] | None = None,
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def _push(text: str) -> None:
        trimmed = text.strip()
        if not trimmed or trimmed in seen:
            return
        seen.add(trimmed)
        items.append(trimmed)

    if has_operational_plan and structural_stop is not None:
        price = f"{structural_stop:.2f}"
        if direction == "short":
            _push(f"Cierre > {price}")
        elif direction == "long":
            _push(f"Cierre < {price}")
    for raw in invalidators or []:
        _push(_INVALIDATOR_LABELS.get(raw, raw))
    for raw in reevaluate_when or []:
        _push(str(raw))
    for raw in thesis_health_why or []:
        _push(_THESIS_HEALTH_WHY_LABELS.get(raw, raw))
    return items


def extract_session_decision_package(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    runtime = payload.get("runtime")
    if isinstance(runtime, dict):
        raw = runtime.get("decisionPackage") or runtime.get("decision_package")
        if isinstance(raw, dict) and raw:
            return dict(raw)
    top = payload.get("decisionPackage") or payload.get("decision_package")
    return dict(top) if isinstance(top, dict) and top else None


def extract_session_facts(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    candidates: list[Any] = []
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    for blob in (
        payload.get("factSet"),
        payload.get("fact_set"),
        runtime.get("factSet") if isinstance(runtime, dict) else None,
        payload.get("evidence"),
    ):
        if isinstance(blob, dict):
            facts = blob.get("facts")
            if isinstance(facts, list):
                candidates.extend(facts)
    out: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not key:
            continue
        out.append(
            {
                "key": str(key),
                "value": str(item.get("value") or ""),
                "claim": item.get("claim"),
                "refs": item.get("refs") if isinstance(item.get("refs"), dict) else None,
            }
        )
    return out


def extract_ta_bias(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    assessments = payload.get("assessments")
    if isinstance(assessments, list):
        for item in assessments:
            bias = _read_bias(item)
            if bias:
                return bias
            if isinstance(item, dict) and item.get("type") == "technical":
                bias = _read_bias(item)
                if bias:
                    return bias
    pkg = extract_session_decision_package(payload)
    if isinstance(pkg, dict):
        action = pkg.get("action")
        mapped = map_journal_study_opinion(bias=None, action=str(action) if action else None)
        return mapped
    return None


def extract_invalidators(package: dict[str, Any] | None) -> list[str]:
    if not isinstance(package, dict):
        return []
    out: list[str] = []
    breakdown = package.get("evidenceBreakdown") or package.get("evidence_breakdown") or []
    if not isinstance(breakdown, list):
        return []
    for item in breakdown:
        if not isinstance(item, dict):
            continue
        raw = item.get("invalidators")
        if isinstance(raw, list):
            out.extend(str(x) for x in raw if x)
    return out


def extract_narrative(payload: dict[str, Any] | None, package: dict[str, Any] | None) -> list[str]:
    notes: list[str] = []
    if isinstance(package, dict):
        raw_notes = package.get("notes")
        if isinstance(raw_notes, list):
            notes.extend(str(n) for n in raw_notes if n)
    if isinstance(payload, dict):
        assessments = payload.get("assessments")
        if isinstance(assessments, list):
            for item in assessments:
                if not isinstance(item, dict):
                    continue
                facts = item.get("facts") or item.get("narrativeFacts")
                if isinstance(facts, list):
                    notes.extend(str(n) for n in facts if n)
    return notes


@dataclass(frozen=True, slots=True)
class DecisionJournalStudyView:
    session_id: str
    instrument_id: str
    studied_at: str
    status: str
    has_operational_plan: bool
    decision_id: str | None = None
    symbol: str | None = None
    name: str | None = None
    age_ms: int | None = None
    period: str | None = None
    timeframe: str | None = None
    opinion: str | None = None
    strength: float | None = None
    strength_band: str | None = None
    vigencia: str | None = None
    entry: float | None = None
    stop: float | None = None
    target1: float | None = None
    target2: float | None = None
    expected_rr: float | None = None
    risk_amount: float | None = None
    user_thesis: None = None
    decision_summary: str | None = None
    analysis_notes: list[str] = field(default_factory=list)
    trends: list[dict[str, Any]] = field(default_factory=list)
    consensus: dict[str, int] = field(default_factory=dict)
    indicators: dict[str, str | None] = field(default_factory=dict)
    invalidation: list[str] = field(default_factory=list)
    next_review_at: str | None = None
    trade_plan_status: str | None = None
    action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": ARTIFACT_TYPE,
            "schemaVersion": SCHEMA_VERSION,
            "sessionId": self.session_id,
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "name": self.name,
            "studiedAt": self.studied_at,
            "ageMs": self.age_ms,
            "period": self.period,
            "timeframe": self.timeframe,
            "opinion": self.opinion,
            "status": self.status,
            "strength": self.strength,
            "strengthBand": self.strength_band,
            "vigencia": self.vigencia,
            "entry": self.entry,
            "stop": self.stop,
            "target1": self.target1,
            "target2": self.target2,
            "expectedRR": self.expected_rr,
            "riskAmount": self.risk_amount,
            "hasOperationalPlan": self.has_operational_plan,
            "userThesis": None,
            "decisionSummary": self.decision_summary,
            "analysisNotes": list(self.analysis_notes),
            "trends": list(self.trends),
            "consensus": dict(self.consensus),
            "indicators": dict(self.indicators),
            "invalidation": list(self.invalidation),
            "nextReviewAt": self.next_review_at,
            "tradePlanStatus": self.trade_plan_status,
            "action": self.action,
        }


@dataclass(frozen=True, slots=True)
class DecisionJournalStudyListResult:
    account_id: str
    studies: list[DecisionJournalStudyView]
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "studies": [s.to_dict() for s in self.studies],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


class SessionReader(Protocol):
    async def list_decision_sessions(
        self,
        *,
        limit: int = 50,
        account_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[DecisionSessionRecord]: ...


class InstrumentQuoteReader(Protocol):
    async def get_quotes_by_ids(self, instrument_ids: list[str]) -> list[Any]: ...


class ListMembershipReader(Protocol):
    async def get_by_id(self, list_id: str) -> Any: ...

    async def list_memberships(self) -> dict[str, list[str]]: ...


class PositionReader(Protocol):
    async def list_open_for_account(self, account_id: str) -> list[Any]: ...


def _payload_timeframe(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("timeframe")
    return str(raw) if raw else None


def _recommendation_status(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    rec = payload.get("recommendation")
    if isinstance(rec, dict):
        status = rec.get("status")
        if isinstance(status, str) and status.strip():
            return status
    return None


def _exit_reason_from_position(record: Any) -> str | None:
    blob = getattr(record, "position_state", None)
    if not isinstance(blob, dict):
        return None
    exit_plan = blob.get("exitPlan") or blob.get("exit_plan")
    if not isinstance(exit_plan, dict):
        return None
    reason = exit_plan.get("primaryReason") or exit_plan.get("primary_reason")
    return str(reason) if reason else None


def build_study_view(
    *,
    session: DecisionSessionRecord,
    name: str | None,
    position_status: str | None,
    has_open_position: bool,
    exit_primary_reason: str | None,
    now: datetime,
) -> DecisionJournalStudyView:
    payload = session.payload if isinstance(session.payload, dict) else {}
    package = extract_session_decision_package(payload)
    plan = extract_session_trade_plan(payload)
    geometry = journal_study_geometry(plan)
    action = str(package.get("action")) if isinstance(package, dict) and package.get("action") else None
    bias = extract_ta_bias(payload)
    confidence = None
    if isinstance(package, dict):
        confidence = package.get("overallConfidence")
        if confidence is None:
            metrics = package.get("metrics")
            if isinstance(metrics, dict):
                confidence = metrics.get("confidence")
    studied_at = ""
    if isinstance(package, dict) and package.get("timestamp"):
        studied_at = str(package.get("timestamp"))
    if not studied_at:
        studied_at = session.created_at
    timeframe = _payload_timeframe(payload)
    why: list[str] = []
    plan_status = None
    direction = None
    expires_at = None
    if isinstance(plan, dict):
        plan_status = str(plan.get("status") or "") or None
        direction = str(plan.get("direction") or "") or None
        raw_why = plan.get("whyNot") or plan.get("why_not") or []
        if isinstance(raw_why, list):
            why = [str(x) for x in raw_why]
        expires_at = _camel(plan, "expiresAt", "expires_at")
        if expires_at is not None:
            expires_at = str(expires_at)
    thesis_health = extract_session_thesis_health(payload)
    thesis_why: list[str] = []
    if isinstance(thesis_health, dict):
        raw_why = thesis_health.get("why")
        if isinstance(raw_why, list):
            thesis_why = [str(x) for x in raw_why]
    facts = extract_session_facts(payload)
    assessments = payload.get("assessments") if isinstance(payload.get("assessments"), list) else []
    notes = extract_narrative(payload, package)
    opinion = map_journal_study_opinion(bias=bias, action=action)
    strength = map_journal_study_strength(confidence)
    rec_status = _recommendation_status(payload)
    status = map_journal_study_status(
        position_status=position_status,
        recommendation_status=rec_status,
        exit_primary_reason=exit_primary_reason,
        trade_plan_status=plan_status,
        trade_plan_why_not=why,
        action=action,
        bias=bias,
        has_open_position=has_open_position,
        has_live_plan=plan_status is not None and plan_status != "EXPIRED",
        has_operational_plan=bool(geometry["hasOperationalPlan"]),
    )
    return DecisionJournalStudyView(
        session_id=session.id,
        instrument_id=session.instrument_id,
        studied_at=studied_at,
        status=status,
        has_operational_plan=bool(geometry["hasOperationalPlan"]),
        decision_id=session.decision_id,
        symbol=session.symbol,
        name=name,
        age_ms=map_journal_study_age_ms(studied_at, now),
        period=map_journal_study_period(timeframe),
        timeframe=timeframe,
        opinion=opinion,
        strength=strength,
        strength_band=map_journal_study_strength_band(strength),
        vigencia=map_journal_study_vigencia(now=now, expires_at=expires_at),
        entry=geometry["entry"],
        stop=geometry["stop"],
        target1=geometry["target1"],
        target2=geometry["target2"],
        expected_rr=geometry["expectedRR"],
        risk_amount=geometry["riskAmount"],
        decision_summary=notes[0] if notes else None,
        analysis_notes=notes,
        trends=map_journal_study_trends(facts, opinion),
        consensus=map_journal_study_consensus(assessments if isinstance(assessments, list) else []),
        indicators=map_journal_study_indicators(facts),
        invalidation=map_journal_study_invalidation(
            direction=direction,
            structural_stop=geometry["stop"],
            has_operational_plan=bool(geometry["hasOperationalPlan"]),
            invalidators=extract_invalidators(package),
            thesis_health_why=thesis_why,
        ),
        next_review_at=expires_at,
        trade_plan_status=plan_status,
        action=action,
    )


def _latest_propose_per_instrument(
    rows: list[DecisionSessionRecord],
) -> list[DecisionSessionRecord]:
    seen: set[str] = set()
    out: list[DecisionSessionRecord] = []
    for row in rows:
        if row.kind != "propose":
            continue
        if row.instrument_id in seen:
            continue
        seen.add(row.instrument_id)
        out.append(row)
    return out


def _matches_filters(
    view: DecisionJournalStudyView,
    *,
    q: str | None,
    period: str | None,
    opinion: str | None,
    status: str | None,
    strength_band: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    allowed_ids: set[str] | None,
) -> bool:
    if allowed_ids is not None and view.instrument_id not in allowed_ids:
        return False
    if q:
        needle = q.strip().lower()
        hay = " ".join(
            part.lower()
            for part in (view.symbol, view.name, view.instrument_id)
            if part
        )
        if needle not in hay:
            return False
    if period and period != "all" and view.period != period:
        return False
    if opinion and opinion != "all" and view.opinion != opinion:
        return False
    if status and status != "all" and view.status != status:
        return False
    if strength_band and strength_band != "all" and view.strength_band != strength_band:
        return False
    studied = _parse_iso(view.studied_at)
    if date_from is not None and (studied is None or studied < date_from):
        return False
    if date_to is not None and (studied is None or studied > date_to):
        return False
    return True


class GetDecisionJournalStudies:
    """Lista la última tesis propose por instrumento (solo lectura)."""

    def __init__(
        self,
        session_reader: SessionReader,
        *,
        instruments: InstrumentQuoteReader | None = None,
        lists: ListMembershipReader | None = None,
        positions: PositionReader | None = None,
        default_limit: int = 50,
        max_limit: int = 200,
    ) -> None:
        self._sessions = session_reader
        self._instruments = instruments
        self._lists = lists
        self._positions = positions
        self._default_limit = default_limit
        self._max_limit = max_limit

    async def execute(
        self,
        account_id: str,
        *,
        list_id: str | None = None,
        q: str | None = None,
        period: str | None = None,
        opinion: str | None = None,
        status: str | None = None,
        strength_band: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        now: datetime | None = None,
    ) -> DecisionJournalStudyListResult:
        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(1, effective_limit), self._max_limit)
        effective_offset = max(0, offset)
        clock = now or datetime.now(UTC)

        rows = await self._sessions.list_decision_sessions(
            account_id=account_id,
            limit=STUDY_SESSION_LIMIT,
        )
        latest = _latest_propose_per_instrument(rows)

        names: dict[str, str] = {}
        if self._instruments is not None and latest:
            quotes = await self._instruments.get_quotes_by_ids(
                [r.instrument_id for r in latest]
            )
            for quote in quotes:
                iid = getattr(quote, "id", None)
                name = getattr(quote, "name", None)
                if iid and name:
                    names[str(iid)] = str(name)

        open_by_instrument: dict[str, Any] = {}
        if self._positions is not None:
            for rec in await self._positions.list_open_for_account(account_id):
                iid = getattr(rec, "instrument_id", None)
                if iid:
                    open_by_instrument[str(iid)] = rec

        allowed_ids: set[str] | None = None
        if list_id and list_id not in {"todas", "all", ""}:
            allowed_ids = await self._resolve_list_ids(account_id, list_id, open_by_instrument)

        views: list[DecisionJournalStudyView] = []
        for row in latest:
            pos = open_by_instrument.get(row.instrument_id)
            pos_status = getattr(pos, "status", None) if pos is not None else None
            view = build_study_view(
                session=row,
                name=names.get(row.instrument_id),
                position_status=str(pos_status) if pos_status else None,
                has_open_position=pos is not None,
                exit_primary_reason=_exit_reason_from_position(pos) if pos is not None else None,
                now=clock,
            )
            if _matches_filters(
                view,
                q=q,
                period=period,
                opinion=opinion,
                status=status,
                strength_band=strength_band,
                date_from=_parse_iso(date_from),
                date_to=_parse_iso(date_to),
                allowed_ids=allowed_ids,
            ):
                views.append(view)

        total = len(views)
        page = views[effective_offset : effective_offset + effective_limit]
        return DecisionJournalStudyListResult(
            account_id=account_id,
            studies=page,
            total=total,
            limit=effective_limit,
            offset=effective_offset,
        )

    async def _resolve_list_ids(
        self,
        account_id: str,
        list_id: str,
        open_by_instrument: dict[str, Any],
    ) -> set[str] | None:
        if list_id in {"__builtin:portfolio__", "portfolio"}:
            return set(open_by_instrument.keys())
        if self._lists is None:
            return None
        detail = await self._lists.get_by_id(list_id)
        if detail is None:
            return set()
        ids = getattr(detail, "instrument_ids", None)
        if isinstance(ids, list):
            return {str(i) for i in ids}
        return set()


@dataclass(frozen=True, slots=True)
class DecisionJournalStudyHistoryResult:
    account_id: str
    instrument_id: str
    symbol: str | None
    name: str | None
    studies: list[DecisionJournalStudyView]
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "name": self.name,
            "studies": [s.to_dict() for s in self.studies],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


class GetDecisionJournalStudyHistory:
    """Historial propose por instrumento (solo lectura, ADR-036 Evolución)."""

    def __init__(
        self,
        session_reader: SessionReader,
        *,
        instruments: InstrumentQuoteReader | None = None,
        positions: PositionReader | None = None,
        default_limit: int = 20,
        max_limit: int = 100,
    ) -> None:
        self._sessions = session_reader
        self._instruments = instruments
        self._positions = positions
        self._default_limit = default_limit
        self._max_limit = max_limit

    async def execute(
        self,
        account_id: str,
        instrument_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
        now: datetime | None = None,
    ) -> DecisionJournalStudyHistoryResult:
        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(1, effective_limit), self._max_limit)
        effective_offset = max(0, offset)
        clock = now or datetime.now(UTC)

        rows = await self._sessions.list_decision_sessions(
            account_id=account_id,
            instrument_id=instrument_id,
            limit=STUDY_SESSION_LIMIT,
        )
        propose = [r for r in rows if r.kind == "propose"]
        propose.sort(key=lambda r: r.created_at, reverse=True)

        name: str | None = None
        symbol: str | None = propose[0].symbol if propose else None
        if self._instruments is not None and instrument_id:
            quotes = await self._instruments.get_quotes_by_ids([instrument_id])
            if quotes:
                name = getattr(quotes[0], "name", None)
                if name is not None:
                    name = str(name)

        pos = None
        if self._positions is not None:
            for rec in await self._positions.list_open_for_account(account_id):
                if str(getattr(rec, "instrument_id", "")) == instrument_id:
                    pos = rec
                    break
        pos_status = getattr(pos, "status", None) if pos is not None else None
        exit_reason = _exit_reason_from_position(pos) if pos is not None else None
        has_open = pos is not None

        views: list[DecisionJournalStudyView] = []
        for row in propose:
            views.append(
                build_study_view(
                    session=row,
                    name=name,
                    position_status=str(pos_status) if pos_status else None,
                    has_open_position=has_open,
                    exit_primary_reason=exit_reason,
                    now=clock,
                )
            )

        total = len(views)
        page = views[effective_offset : effective_offset + effective_limit]
        return DecisionJournalStudyHistoryResult(
            account_id=account_id,
            instrument_id=instrument_id,
            symbol=symbol,
            name=name,
            studies=page,
            total=total,
            limit=effective_limit,
            offset=effective_offset,
        )


__all__ = [
    "DecisionJournalStudyHistoryResult",
    "DecisionJournalStudyListResult",
    "DecisionJournalStudyView",
    "GetDecisionJournalStudies",
    "GetDecisionJournalStudyHistory",
    "NO_OPERATIONAL_PLAN_COPY",
    "build_study_view",
    "journal_study_geometry",
    "map_journal_study_status",
]
