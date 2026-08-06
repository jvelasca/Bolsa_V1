"""Caso de uso F3 — Composite Investment Score (lectura; sin IA)."""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_analytics.indicators.compute import OhlcvBar as IndicatorBar
from bolsa_analytics.knowledge.as_of_cut import (
    LOOKAHEAD_BLOCKED_WARNING,
    RECONSTRUCTED_WARNING,
    normalize_as_of_date,
    resolve_fundamentals_pit,
    strip_lookahead_fundamentals,
    today_iso_utc,
)
from bolsa_analytics.knowledge.composite_score import (
    build_composite_card,
    composite_to_chip,
)
from bolsa_analytics.signals.technical_rating_v1 import compute_technical_rating_v1
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_market.fundamentals_as_of import (
    build_fundamentals_as_of_from_pack,
    parse_statement_pack,
)


class _OhlcvPort(Protocol):
    async def execute(
        self,
        instrument_id: str,
        *,
        limit: int = 200,
        timeframe: TimeFrame | str = TimeFrame.D1,
        date_to: str | None = None,
    ) -> list[Any] | None: ...


def _bars_to_indicator(bars: list[Any]) -> list[IndicatorBar]:
    out: list[IndicatorBar] = []
    for bar in bars:
        try:
            out.append(
                IndicatorBar(
                    timestamp=str(getattr(bar, "timestamp", "") or ""),
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(getattr(bar, "volume", 0) or 0),
                )
            )
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def _technical_score_from_bars(bars: list[Any]) -> tuple[float | None, str | None]:
    indicator_bars = _bars_to_indicator(bars)
    if len(indicator_bars) < 50:
        return None, None
    rating = compute_technical_rating_v1(indicator_bars)
    if rating is None:
        return None, None
    # 0–100 → [-1, +1]
    value = round((float(rating.total) - 50.0) / 50.0, 4)
    return value, f"technical_rating_v1:{rating.model_version}"


class GetInstrumentComposite:
    """FUND snapshot + TA rating desde OHLCV (si hay barras) → CompositeCard."""

    def __init__(
        self,
        instruments: InstrumentRepository,
        ohlcv: _OhlcvPort | None = None,
    ) -> None:
        self._instruments = instruments
        self._ohlcv = ohlcv

    async def execute(
        self,
        instrument_id: str,
        *,
        horizon: str = "swing",
        regime: str = "neutral",
        risk_tolerance: str | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any] | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None
        fundamentals = await self._instruments.get_fundamentals(instrument_id)
        ticker = getattr(instrument, "symbol", None) or instrument_id

        as_of_norm = normalize_as_of_date(as_of)
        fetched_at = None
        if isinstance(fundamentals, dict) and fundamentals.get("fetchedAt"):
            fetched_at = str(fundamentals.get("fetchedAt"))
        pit = resolve_fundamentals_pit(as_of=as_of_norm, fetched_at=fetched_at)

        tech_score: float | None = None
        tech_method: str | None = None
        date_to = as_of_norm if as_of_norm and as_of_norm < today_iso_utc() else None
        bars: list[Any] | None = None
        if self._ohlcv is not None:
            try:
                bars = await self._ohlcv.execute(
                    instrument_id,
                    limit=180,
                    timeframe=TimeFrame.D1,
                    date_to=date_to,
                )
            except TypeError:
                bars = await self._ohlcv.execute(
                    instrument_id, limit=180, timeframe=TimeFrame.D1
                )
            except Exception:  # noqa: BLE001
                bars = None
            tech_score, tech_method = _technical_score_from_bars(bars or [])

        close_as_of = None
        if bars:
            try:
                close_as_of = float(bars[-1].close)
            except (TypeError, ValueError, AttributeError, IndexError):
                close_as_of = None

        fund_for_score = fundamentals
        extra_warnings: list[str] = []
        if pit == "blocked":
            getter = getattr(self._instruments, "get_profile_snapshot", None)
            pack = None
            if getter is not None:
                snap = await getter(instrument_id)
                pack = parse_statement_pack(snap if isinstance(snap, dict) else None)
            rebuilt = build_fundamentals_as_of_from_pack(
                pack,
                as_of_norm or today_iso_utc(),
                close_price=close_as_of if close_as_of and close_as_of > 0 else None,
            )
            if rebuilt is not None:
                fund_for_score = rebuilt
                pit = "reconstructed"
                extra_warnings.append(RECONSTRUCTED_WARNING)
            else:
                fund_for_score = strip_lookahead_fundamentals(fundamentals)
                extra_warnings.append(LOOKAHEAD_BLOCKED_WARNING)

        hz = horizon if horizon in {"intraday", "swing", "position", "long_term"} else "swing"
        rg = (
            regime
            if regime in {"risk_on", "neutral", "risk_off", "crisis", "uncertain"}
            else "neutral"
        )

        card = build_composite_card(
            instrument_id=instrument_id,
            ticker=str(ticker),
            fundamentals=fund_for_score,
            technical_score=tech_score,
            technical_method=tech_method,
            horizon=hz,  # type: ignore[arg-type]
            regime=rg,  # type: ignore[arg-type]
            risk_tolerance=risk_tolerance,
        )
        meta = card.setdefault("metadata", {})
        if isinstance(meta, dict):
            meta["asOfDate"] = as_of_norm
            meta["pointInTime"] = pit
            meta["fundPointInTime"] = pit
            meta["taCutToAsOf"] = bool(date_to)
        if extra_warnings:
            warns = list(card.get("warnings") or [])
            for w in extra_warnings:
                if w not in warns:
                    warns.append(w)
            card["warnings"] = warns
        return card

    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 40,
        horizon: str = "swing",
        regime: str = "neutral",
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        ids: list[str] = []
        for raw in instrument_ids:
            iid = (raw or "").strip()
            if not iid or iid in seen:
                continue
            seen.add(iid)
            ids.append(iid)
            if len(ids) >= max_ids:
                break
        chips: list[dict[str, Any]] = []
        for instrument_id in ids:
            # Un fallo puntual no debe tumbar el batch (500 → cuelga la UI).
            try:
                card = await self.execute(
                    instrument_id,
                    horizon=horizon,
                    regime=regime,
                    as_of=as_of,
                )
            except Exception:
                continue
            if card is None:
                continue
            chips.append(composite_to_chip(card))
        return chips
