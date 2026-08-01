"""News / earnings → MarketEvents desde Yahoo (determinista; sin LLM)."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from bolsa_analytics.cognitive.market_events import MarketEvent, MarketEventCalendar, build_market_event
from bolsa_market.yahoo_client import YahooFinanceClient, get_yahoo_finance_client

_CACHE: dict[str, tuple[float, list[MarketEvent]]] = {}
_CACHE_TTL_SEC = 900.0  # 15 min

_BULLISH = frozenset(
    {
        "beat",
        "beats",
        "surge",
        "surges",
        "rally",
        "rallies",
        "soar",
        "soars",
        "jump",
        "jumps",
        "upgrade",
        "upgrades",
        "raised",
        "raises",
        "record",
        "growth",
        "profit",
        "profits",
        "bullish",
        "outperform",
        "buy",
        "strong",
        "wins",
        "win",
        "approval",
        "approved",
        "breakthrough",
    }
)
_BEARISH = frozenset(
    {
        "miss",
        "misses",
        "plunge",
        "plunges",
        "fall",
        "falls",
        "drop",
        "drops",
        "cut",
        "cuts",
        "downgrade",
        "downgrades",
        "lawsuit",
        "probe",
        "fraud",
        "loss",
        "losses",
        "bearish",
        "underperform",
        "sell",
        "weak",
        "recall",
        "layoff",
        "layoffs",
        "bankrupt",
        "default",
        "warning",
        "slump",
        "slumps",
    }
)


def heuristic_title_sentiment(title: str) -> float:
    """Score [-1, +1] por keywords en título (sin LLM)."""
    tokens = re.findall(r"[a-z0-9]+", (title or "").lower())
    if not tokens:
        return 0.0
    bull = sum(1 for t in tokens if t in _BULLISH)
    bear = sum(1 for t in tokens if t in _BEARISH)
    if bull == 0 and bear == 0:
        return 0.0
    raw = (bull - bear) / max(1, bull + bear)
    return round(max(-1.0, min(1.0, raw * 0.85)), 3)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _event_id(prefix: str, key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def news_items_to_events(
    items: list[dict[str, Any]],
    *,
    symbol: str,
    now: datetime | None = None,
    horizon_days: float = 3.0,
) -> list[MarketEvent]:
    now_dt = now or datetime.now(timezone.utc)
    sym = symbol.upper().strip()
    out: list[MarketEvent] = []
    for item in items:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        uuid = str(item.get("uuid") or item.get("id") or title)
        pub_raw = item.get("providerPublishTime")
        try:
            pub_ts = int(pub_raw) if pub_raw is not None else int(now_dt.timestamp())
        except (TypeError, ValueError):
            pub_ts = int(now_dt.timestamp())
        published = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
        # Noticias > 7d ignoradas
        if (now_dt - published).total_seconds() > 7 * 86400:
            continue
        sentiment = heuristic_title_sentiment(title)
        impact = "medium" if abs(sentiment) >= 0.4 else "low"
        valid_from = published
        valid_to = published + timedelta(days=horizon_days)
        if valid_to < now_dt:
            continue
        related = item.get("relatedTickers") or []
        affects = [sym]
        if isinstance(related, list):
            affects.extend(str(t).upper() for t in related if t)
        publisher = str(item.get("publisher") or "yahoo")
        out.append(
            build_market_event(
                entity=sym,
                event_type="news",
                sentiment=sentiment,
                impact=impact,  # type: ignore[arg-type]
                horizon_days=horizon_days,
                source=f"yahoo:{publisher}",
                credibility=0.55,
                valid_from=_iso(valid_from),
                valid_to=_iso(valid_to),
                affects=tuple(dict.fromkeys(affects)),
                event_id=_event_id("YNEWS", f"{sym}:{uuid}"),
            )
        )
    return out


def earnings_from_quote_summary(
    modules: dict[str, Any] | None,
    *,
    symbol: str,
    now: datetime | None = None,
) -> list[MarketEvent]:
    """Extrae próximo earnings de calendarEvents si existe."""
    if not modules:
        return []
    now_dt = now or datetime.now(timezone.utc)
    cal = modules.get("calendarEvents") or {}
    earn = cal.get("earnings") or {}
    dates = earn.get("earningsDate") or []
    if not dates:
        return []
    first = dates[0] if isinstance(dates, list) else dates
    raw = first.get("raw") if isinstance(first, dict) else first
    try:
        ts = int(raw)
    except (TypeError, ValueError):
        return []
    when = datetime.fromtimestamp(ts, tz=timezone.utc)
    # ±7 días ventana de blackout/earnings
    if abs((when - now_dt).total_seconds()) > 14 * 86400:
        return []
    sym = symbol.upper().strip()
    return [
        build_market_event(
            entity=sym,
            event_type="earnings",
            sentiment=0.0,
            impact="high",
            horizon_days=7.0,
            source="yahoo:calendarEvents",
            credibility=0.85,
            valid_from=_iso(when),
            valid_to=_iso(when + timedelta(days=1)),
            affects=(sym,),
            event_id=_event_id("YEARN", f"{sym}:{ts}"),
        )
    ]


async def fetch_yahoo_market_events(
    yahoo_symbol: str,
    *,
    client: YahooFinanceClient | None = None,
    use_cache: bool = True,
    news_count: int = 8,
    include_earnings: bool = True,
) -> list[MarketEvent]:
    """Fetch + parse noticias (+ earnings opcional) con cache 15m."""
    sym = yahoo_symbol.strip().upper()
    if not sym:
        return []
    global _CACHE
    now_m = time.monotonic()
    if use_cache and sym in _CACHE:
        at, events = _CACHE[sym]
        if now_m - at < _CACHE_TTL_SEC:
            return list(events)

    cli = client or get_yahoo_finance_client()
    events: list[MarketEvent] = []
    try:
        items = await cli.fetch_news(sym, news_count=news_count)
        events.extend(news_items_to_events(items, symbol=sym))
    except Exception:
        pass

    if include_earnings:
        try:
            modules = await cli.fetch_quote_summary(sym, modules="calendarEvents")
            events.extend(earnings_from_quote_summary(modules, symbol=sym))
        except Exception:
            pass

    if use_cache:
        _CACHE[sym] = (now_m, list(events))
    return events


def upsert_events_into_calendar(
    calendar: MarketEventCalendar,
    events: list[MarketEvent],
) -> int:
    """Inserta/reemplaza por event_id. Devuelve nº upserts."""
    if not events:
        return 0
    by_id = {ev.event_id: i for i, ev in enumerate(calendar.events)}
    n = 0
    for ev in events:
        if ev.event_id in by_id:
            calendar.events[by_id[ev.event_id]] = ev
        else:
            calendar.add(ev)
            by_id[ev.event_id] = len(calendar.events) - 1
        n += 1
    return n


class YahooNewsEventPort:
    """Adaptador para ProposeRecommendationFromTa — refresca calendario compartido."""

    def __init__(self, calendar: MarketEventCalendar, *, client: YahooFinanceClient | None = None) -> None:
        self._calendar = calendar
        self._client = client

    async def refresh_for_symbol(self, yahoo_symbol: str) -> int:
        events = await fetch_yahoo_market_events(yahoo_symbol, client=self._client)
        return upsert_events_into_calendar(self._calendar, events)
