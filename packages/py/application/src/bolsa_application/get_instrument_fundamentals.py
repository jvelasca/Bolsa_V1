"""Caso de uso F1 — lectura FundamentalCard (sin IA, sin refresh)."""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_analytics.knowledge.as_of_cut import (
    normalize_as_of_date,
    resolve_fundamentals_pit,
    today_iso_utc,
)
from bolsa_analytics.knowledge.fundamental_card import build_fundamental_card, card_to_chip
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


def _close_as_of(bars: list[Any] | None) -> float | None:
    if not bars:
        return None
    last = bars[-1]
    try:
        close = float(getattr(last, "close", None) or 0)
    except (TypeError, ValueError):
        return None
    return close if close > 0 else None


class GetInstrumentFundamentals:
    """Obtiene Instrument Fundamentals."""
    def __init__(
        self,
        repository: InstrumentRepository,
        ohlcv: _OhlcvPort | None = None,
    ) -> None:
        self._repository = repository
        self._ohlcv = ohlcv

    async def _profile_snapshot(self, instrument_id: str) -> dict[str, Any] | None:
        getter = getattr(self._repository, "get_profile_snapshot", None)
        if getter is None:
            return None
        snap = await getter(instrument_id)
        return snap if isinstance(snap, dict) else None

    async def _resolve_fundamentals(
        self,
        instrument_id: str,
        *,
        as_of: str | None,
    ) -> dict[str, Any] | None:
        fundamentals = await self._repository.get_fundamentals(instrument_id)
        as_of_norm = normalize_as_of_date(as_of)
        if as_of_norm is None or as_of_norm >= today_iso_utc():
            return fundamentals

        fetched_at = None
        if isinstance(fundamentals, dict) and fundamentals.get("fetchedAt"):
            fetched_at = str(fundamentals.get("fetchedAt"))
        pit = resolve_fundamentals_pit(as_of=as_of_norm, fetched_at=fetched_at)
        if pit != "blocked":
            return fundamentals

        snapshot = await self._profile_snapshot(instrument_id)
        pack = parse_statement_pack(snapshot)
        close: float | None = None
        if self._ohlcv is not None:
            try:
                bars = await self._ohlcv.execute(
                    instrument_id,
                    limit=5,
                    timeframe=TimeFrame.D1,
                    date_to=as_of_norm,
                )
            except TypeError:
                bars = None
            except Exception:  # noqa: BLE001
                bars = None
            close = _close_as_of(bars)

        rebuilt = build_fundamentals_as_of_from_pack(
            pack,
            as_of_norm,
            close_price=close,
        )
        return rebuilt if rebuilt is not None else fundamentals

    async def execute(
        self,
        instrument_id: str,
        *,
        as_of: str | None = None,
    ) -> dict[str, Any] | None:
        instrument = await self._repository.get_by_id(instrument_id)
        if instrument is None:
            return None
        fundamentals = await self._resolve_fundamentals(instrument_id, as_of=as_of)
        ticker = getattr(instrument, "symbol", None) or instrument_id
        return build_fundamental_card(
            instrument_id=instrument_id,
            ticker=str(ticker),
            fundamentals=fundamentals,
            as_of=as_of,
        )

    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 80,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Batch chips FA para filas de lista (PR3). Omite ids desconocidos."""
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
            try:
                card = await self.execute(instrument_id, as_of=as_of)
            except Exception:
                continue
            if card is None:
                continue
            chips.append(card_to_chip(card))
        return chips
