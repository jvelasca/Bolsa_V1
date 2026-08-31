"""V1.47 — OperationalContext / MarketSnapshot (Runtime Truth).

HTTP no transporta hechos de mercado. Tests inyectan FakeMarketDataPort
o ``build_test_operational_context``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal, Protocol

from bolsa_analytics.cognitive.position_state import PositionState
from bolsa_market.market_calendar import (
    SessionState,
    expected_last_daily_bar,
    resolve_session_state,
    session_is_open,
)

MarketDataPermission = Literal["FRESH", "STALE", "MISSING", "INVALID"]
PaperDeskNextAction = Literal[
    "MANTENER",
    "SUBIR_STOP",
    "REDUCIR",
    "SALIR",
    "ESPERAR_APERTURA",
    "REVISAR_DATOS_NO_FRESCOS",
    "BLOQUEADO",
]


def is_stop_touched(
    *,
    direction: str,
    mark: float | None,
    stop: float | None,
) -> bool:
    if mark is None or stop is None or mark <= 0 or stop <= 0:
        return False
    if direction == "long":
        return mark <= stop + 1e-9
    if direction == "short":
        return mark >= stop - 1e-9
    return False


def classify_market_data(
    *,
    last_price: float | None,
    bar_date: str | None,
    expected: date,
) -> MarketDataPermission:
    if last_price is None or last_price <= 0:
        return "MISSING" if not bar_date else "INVALID"
    if not bar_date or not str(bar_date).strip():
        return "MISSING"
    raw = str(bar_date).strip()[:10]
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return "INVALID"
    if d < expected:
        return "STALE"
    return "FRESH"


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    instrument_id: str
    last_price: float | None
    permission: MarketDataPermission
    timestamp: str | None = None
    source: str = "ohlcv"
    as_of: str | None = None
    bid: float | None = None
    ask: float | None = None
    market: str | None = None
    session: SessionState = "OPEN"

    def operable_mark(self) -> float | None:
        """Precio usable para ExitPlan. MISSING/INVALID → None (nunca actual_entry)."""
        if self.permission in ("MISSING", "INVALID"):
            return None
        if self.last_price is None or self.last_price <= 0:
            return None
        return float(self.last_price)

    def is_stale(self) -> bool:
        return self.permission == "STALE"


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    instrument_id: str
    position: PositionState
    remaining_quantity: float
    current_stop: float | None


@dataclass(frozen=True, slots=True)
class RiskSnapshot:
    instrument_id: str
    stop_touched: bool
    mark_price: float | None


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    account_id: str
    drift: bool


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    existing_intent_keys: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class OperationalContext:
    account_id: str
    as_of: str | None
    session: SessionState
    portfolio: PortfolioSnapshot
    markets: dict[str, MarketSnapshot]
    execution: ExecutionSnapshot = field(default_factory=ExecutionSnapshot)
    trail_hint: bool = False
    trail_stop: float | None = None

    def market_for(self, instrument_id: str) -> MarketSnapshot | None:
        return self.markets.get(instrument_id)

    def market_closed(self) -> bool:
        return not session_is_open(self.session)

    def data_stale(self, instrument_id: str) -> bool:
        snap = self.market_for(instrument_id)
        return snap is None or snap.is_stale() or snap.permission in ("MISSING", "INVALID")

    def mark_price(self, instrument_id: str) -> float | None:
        snap = self.market_for(instrument_id)
        if snap is None:
            return None
        return snap.operable_mark()

    def stop_touched(self, instrument_id: str, position: PositionState) -> bool:
        mark = self.mark_price(instrument_id)
        return is_stop_touched(
            direction=position.direction,
            mark=mark,
            stop=position.current_stop,
        )

    def risk_for(self, instrument_id: str, position: PositionState) -> RiskSnapshot:
        mark = self.mark_price(instrument_id)
        return RiskSnapshot(
            instrument_id=instrument_id,
            stop_touched=self.stop_touched(instrument_id, position),
            mark_price=mark,
        )


class MarketDataPort(Protocol):
    async def snapshot(self, instrument_id: str) -> MarketSnapshot: ...


class FakeMarketDataPort:
    """Fixture de test — no usar en HTTP."""

    def __init__(self, snapshots: dict[str, MarketSnapshot]) -> None:
        self._snapshots = snapshots

    async def snapshot(self, instrument_id: str) -> MarketSnapshot:
        found = self._snapshots.get(instrument_id)
        if found is not None:
            return found
        return MarketSnapshot(
            instrument_id=instrument_id,
            last_price=None,
            permission="MISSING",
            source="test",
        )


class OhlcvMarketDataPort:
    """Runtime: last close + bar date → MarketSnapshot."""

    def __init__(
        self,
        ohlcv: object,
        *,
        exchange: str = "BME",
        country: str = "ES",
        now: datetime | None = None,
        source: str = "ohlcv",
    ) -> None:
        self._ohlcv = ohlcv
        self._exchange = exchange
        self._country = country
        self._now = now
        self._source = source

    async def snapshot(self, instrument_id: str) -> MarketSnapshot:
        close: float | None = None
        bar_date: str | None = None
        getter = getattr(self._ohlcv, "get_latest_close", None)
        date_getter = getattr(self._ohlcv, "get_latest_bar_date", None)
        try:
            if getter is not None:
                raw = await getter(instrument_id)
                if raw is not None:
                    close = float(raw)
                    if close <= 0:
                        close = None
        except (TypeError, ValueError):
            close = None
        except Exception:  # noqa: BLE001
            close = None
        try:
            if date_getter is not None:
                bar_date = await date_getter(instrument_id)
                if bar_date is not None:
                    bar_date = str(bar_date)
        except Exception:  # noqa: BLE001
            bar_date = None

        expected = expected_last_daily_bar(
            exchange=self._exchange,
            country=self._country,
            as_of=self._now,
        )
        permission = classify_market_data(
            last_price=close, bar_date=bar_date, expected=expected
        )
        session = resolve_session_state(
            exchange=self._exchange, country=self._country, as_of=self._now
        )
        as_of = None
        if self._now is not None:
            as_of = self._now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return MarketSnapshot(
            instrument_id=instrument_id,
            last_price=close,
            permission=permission,
            timestamp=bar_date,
            source=self._source,
            as_of=as_of,
            market=self._exchange,
            session=session,
        )


class OperationalContextBuilder:
    def __init__(
        self,
        market: MarketDataPort,
        portfolio_recon: object | None = None,
        *,
        exchange: str = "BME",
        country: str = "ES",
        now: datetime | None = None,
    ) -> None:
        self._market = market
        self._portfolio_recon = portfolio_recon
        self._exchange = exchange
        self._country = country
        self._now = now

    async def build(
        self,
        account_id: str,
        instrument_ids: list[str],
        *,
        as_of: str | None = None,
        trail_hint: bool = False,
        trail_stop: float | None = None,
    ) -> OperationalContext:
        session = resolve_session_state(
            exchange=self._exchange, country=self._country, as_of=self._now
        )
        drift = False
        lookup = self._portfolio_recon
        if lookup is not None:
            getter = getattr(lookup, "portfolio_recon_status", None)
            if getter is not None:
                try:
                    status = await getter(account_id)
                    drift = str(status) == "drift"
                except Exception:  # noqa: BLE001
                    drift = True

        markets: dict[str, MarketSnapshot] = {}
        for iid in instrument_ids:
            key = str(iid).strip()
            if not key:
                continue
            markets[key] = await self._market.snapshot(key)

        return OperationalContext(
            account_id=account_id,
            as_of=as_of,
            session=session,
            portfolio=PortfolioSnapshot(account_id=account_id, drift=drift),
            markets=markets,
            trail_hint=trail_hint,
            trail_stop=trail_stop,
        )


def build_test_operational_context(
    *,
    account_id: str = "acc-1",
    as_of: str | None = "2026-08-31",
    marks: dict[str, float] | None = None,
    permission: MarketDataPermission = "FRESH",
    session: SessionState = "OPEN",
    drift: bool = False,
    trail_hint: bool = False,
    trail_stop: float | None = None,
    missing: tuple[str, ...] = (),
) -> OperationalContext:
    """Solo tests — no es fuente de runtime HTTP."""
    markets: dict[str, MarketSnapshot] = {}
    for iid, price in (marks or {}).items():
        markets[iid] = MarketSnapshot(
            instrument_id=iid,
            last_price=price,
            permission=permission,
            timestamp=as_of,
            source="test",
            as_of=as_of,
            session=session,
        )
    for iid in missing:
        markets[iid] = MarketSnapshot(
            instrument_id=iid,
            last_price=None,
            permission="MISSING",
            source="test",
            session=session,
        )
    return OperationalContext(
        account_id=account_id,
        as_of=as_of,
        session=session,
        portfolio=PortfolioSnapshot(account_id=account_id, drift=drift),
        markets=markets,
        trail_hint=trail_hint,
        trail_stop=trail_stop,
    )


def resolve_paper_desk_next_action(
    *,
    status: str,
    decision_verdict: str | None,
    permission_reasons: tuple[str, ...] = (),
    reason: str | None = None,
    session: SessionState = "OPEN",
) -> PaperDeskNextAction:
    _ = decision_verdict
    reasons = set(permission_reasons)
    if (
        reason in ("data_unavailable", "missing_mark_price")
        or "data_unavailable" in reasons
        or reason == "data_stale"
        or "data_stale" in reasons
    ):
        return "REVISAR_DATOS_NO_FRESCOS"
    if status == "denied":
        return "BLOQUEADO"
    if status == "held" and (
        not session_is_open(session) or reason == "queue_next_session"
    ):
        return "ESPERAR_APERTURA"
    if status == "protected":
        return "SUBIR_STOP"
    if status == "reduced":
        return "REDUCIR"
    if status == "exited":
        return "SALIR"
    if status == "held":
        return "MANTENER"
    if status in ("error", "no_plan", "skipped", "sell_skipped"):
        return "BLOQUEADO"
    return "MANTENER"
