"""MarketEvent estructurado + decay + contexto de blackout (RFC-008 D4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

ImpactLevel = Literal["low", "medium", "high", "very_high"]

EARNINGS_TYPES = frozenset({"earnings", "earnings_release", "results"})
FED_TYPES = frozenset({"FOMC", "fed", "FED", "fomc"})
ECB_TYPES = frozenset({"ECB", "ecb"})
HIGH_IMPACT_MACRO = frozenset({"CPI", "PCE", "NFP", "PMI", "FOMC", "ECB", "GDP"})


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """Noticia/fundamental/macro normalizado — no párrafo libre."""

    event_id: str
    entity: str
    event_type: str
    sentiment: float
    impact: ImpactLevel
    horizon_days: float
    affects: tuple[str, ...]
    source: str
    credibility: float
    valid_from: str
    valid_to: str
    artifact_type: str = "ART-MARKET-EVENT"
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "eventId": self.event_id,
            "entity": self.entity,
            "eventType": self.event_type,
            "sentiment": self.sentiment,
            "impact": self.impact,
            "horizonDays": self.horizon_days,
            "affects": list(self.affects),
            "source": self.source,
            "credibility": self.credibility,
            "validFrom": self.valid_from,
            "validTo": self.valid_to,
        }


def build_market_event(
    *,
    entity: str,
    event_type: str,
    sentiment: float,
    impact: ImpactLevel,
    horizon_days: float,
    source: str,
    credibility: float,
    valid_from: str,
    valid_to: str,
    affects: tuple[str, ...] | list[str] = (),
    event_id: str | None = None,
) -> MarketEvent:
    return MarketEvent(
        event_id=event_id or f"EVT-{uuid4().hex[:12]}",
        entity=entity.upper(),
        event_type=event_type,
        sentiment=max(-1.0, min(1.0, sentiment)),
        impact=impact,
        horizon_days=horizon_days,
        affects=tuple(a.upper() for a in affects),
        source=source,
        credibility=max(0.0, min(1.0, credibility)),
        valid_from=valid_from,
        valid_to=valid_to,
    )


def event_decay_weight(event: MarketEvent, *, now: datetime | None = None) -> float:
    """
    Peso efectivo 0–1 con decay lineal en [valid_from, valid_to].
    Fuera de ventana → 0. Credibility acota el máximo.
    """
    now_dt = now or datetime.now(timezone.utc)
    start = _parse_ts(event.valid_from)
    end = _parse_ts(event.valid_to)
    if now_dt < start or now_dt > end:
        return 0.0
    span = (end - start).total_seconds()
    if span <= 0:
        return event.credibility
    remaining = (end - now_dt).total_seconds() / span
    return float(event.credibility * max(0.0, min(1.0, remaining)))


@dataclass(frozen=True, slots=True)
class EventBlackoutContext:
    hours_to_earnings: float | None = None
    hours_since_earnings: float | None = None
    high_impact_macro_active: bool = False
    fed_fomc_active: bool = False
    ecb_active: bool = False
    active_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "hoursToEarnings": self.hours_to_earnings,
            "hoursSinceEarnings": self.hours_since_earnings,
            "highImpactMacroActive": self.high_impact_macro_active,
            "fedFomcActive": self.fed_fomc_active,
            "ecbActive": self.ecb_active,
            "activeEventIds": list(self.active_event_ids),
        }


@dataclass
class MarketEventCalendar:
    """Calendario en memoria (D4). Persistencia PG = fase posterior."""

    events: list[MarketEvent] = field(default_factory=list)

    def add(self, event: MarketEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()

    def active_events(
        self,
        *,
        symbol: str | None = None,
        now: datetime | None = None,
        min_weight: float = 0.05,
    ) -> list[tuple[MarketEvent, float]]:
        now_dt = now or datetime.now(timezone.utc)
        sym = (symbol or "").upper()
        out: list[tuple[MarketEvent, float]] = []
        for ev in self.events:
            w = event_decay_weight(ev, now=now_dt)
            if w < min_weight:
                continue
            if ev.entity in {"MACRO", "*"} or ev.entity == sym or sym in ev.affects:
                out.append((ev, w))
            elif not sym and ev.entity == "MACRO":
                out.append((ev, w))
        return out

    def blackout_context(
        self,
        symbol: str,
        *,
        now: datetime | None = None,
    ) -> EventBlackoutContext:
        """
        Contexto de vetos Policy.

        Convención earnings: `valid_from` = instante del evento (resultados).
        Se considera en ±7 días aunque el decay de evidencia sea 0 (pre-ventana).
        Macro (FOMC/ECB/CPI…): usa ventana valid_from–valid_to con decay > 0.
        """
        now_dt = now or datetime.now(timezone.utc)
        sym = symbol.upper()
        hours_to: float | None = None
        hours_since: float | None = None
        fed = False
        ecb = False
        macro = False
        ids: list[str] = []

        for ev in self.events:
            et = ev.event_type
            entity_hit = (
                ev.entity == sym
                or sym in ev.affects
                or ev.entity in {"MACRO", "*"}
            )
            if not entity_hit:
                continue

            if et in EARNINGS_TYPES or et.lower() == "earnings":
                start = _parse_ts(ev.valid_from)
                delta_h = (start - now_dt).total_seconds() / 3600.0
                if -168 <= delta_h <= 168:
                    ids.append(ev.event_id)
                    if delta_h >= 0:
                        hours_to = delta_h if hours_to is None else min(hours_to, delta_h)
                    else:
                        since = -delta_h
                        hours_since = since if hours_since is None else min(hours_since, since)
                continue

            w = event_decay_weight(ev, now=now_dt)
            if w < 0.05:
                continue
            ids.append(ev.event_id)
            if et in FED_TYPES:
                fed = True
                macro = True
            if et in ECB_TYPES:
                ecb = True
                macro = True
            if et.upper() in HIGH_IMPACT_MACRO or ev.impact in {"high", "very_high"}:
                if ev.entity == "MACRO" or et.upper() in HIGH_IMPACT_MACRO:
                    macro = True

        return EventBlackoutContext(
            hours_to_earnings=hours_to,
            hours_since_earnings=hours_since,
            high_impact_macro_active=macro,
            fed_fomc_active=fed,
            ecb_active=ecb,
            active_event_ids=tuple(ids),
        )
