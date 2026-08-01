from __future__ import annotations

from bolsa_domain.repositories.instrument_repository import InstrumentRepository, InstrumentWithMeta
from bolsa_domain.value_objects.market import (
    InstrumentLiveQuote,
    LiveQuoteReference,
    MarketProviderStatus,
    XtbQuote,
)
from bolsa_market.providers import XtbBridgeClient, XtbBridgeQuote, format_xtb_bridge_connect_error
from bolsa_market.xtb_symbols import to_xtb_symbol

_XTB_QUOTE_CONCURRENCY = 8


class GetMarketStatus:
    def __init__(self, xtb_bridge_url: str | None) -> None:
        self._xtb_bridge_url = xtb_bridge_url

    async def execute(self) -> list[MarketProviderStatus]:
        xtb_enabled = bool(self._xtb_bridge_url and self._xtb_bridge_url.strip())
        xtb_healthy = False
        xtb_message = "XTB_BRIDGE_URL no configurada"

        if xtb_enabled:
            client = XtbBridgeClient(self._xtb_bridge_url.strip())  # type: ignore[union-attr]
            try:
                health = await client.check_health()
                xtb_healthy = health.status == "ok"
                xtb_message = health.message or (
                    f"Bridge {health.mode}" if health.mode else "Bridge activo"
                )
            except Exception as exc:
                xtb_healthy = False
                xtb_message = format_xtb_bridge_connect_error(self._xtb_bridge_url.strip(), exc)

        return [
            MarketProviderStatus(
                id="yahoo",
                label="Yahoo Finance",
                enabled=True,
                healthy=True,
                message="Histórico diario (catálogo local + chart API)",
            ),
            MarketProviderStatus(
                id="xtb",
                label="XTB Bridge",
                enabled=xtb_enabled,
                healthy=xtb_healthy,
                message=xtb_message,
            ),
        ]


def _reference_from_meta(meta: InstrumentWithMeta) -> LiveQuoteReference | None:
    if meta.last_close is None:
        return None
    timestamp = meta.last_bar_date or ""
    if not timestamp:
        return None
    return LiveQuoteReference(price=meta.last_close, timestamp=timestamp, source="db")


def _to_xtb_quote(quote: XtbBridgeQuote) -> XtbQuote:
    return XtbQuote(
        symbol=quote.symbol,
        bid=quote.bid,
        ask=quote.ask,
        last=quote.last,
        timestamp=quote.timestamp,
    )


class GetInstrumentLiveQuotes:
    """Batch live quotes: one meta hydrate + one XTB health + bounded quote fan-out."""

    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        xtb_bridge_url: str | None,
    ) -> None:
        self._instruments = instrument_repository
        self._xtb_bridge_url = xtb_bridge_url

    async def execute(self, instrument_ids: list[str]) -> list[InstrumentLiveQuote]:
        metas = await self._instruments.get_quotes_by_ids(instrument_ids)
        if not metas:
            return []

        xtb_by_symbol: dict[str, XtbBridgeQuote] = {}
        xtb_available = False
        bridge_url = (self._xtb_bridge_url or "").strip()
        if bridge_url:
            client = XtbBridgeClient(bridge_url)
            try:
                health = await client.check_health()
                if health.status == "ok":
                    xtb_available = True
                    symbol_refs: dict[str, float | None] = {}
                    for meta in metas:
                        xtb_symbol = to_xtb_symbol(meta.symbol, yahoo_symbol=meta.yahoo_symbol)
                        symbol_refs[xtb_symbol] = meta.last_close
                    xtb_by_symbol = await client.fetch_quotes(
                        list(symbol_refs.keys()),
                        references=symbol_refs,
                        concurrency=_XTB_QUOTE_CONCURRENCY,
                    )
            except Exception:
                xtb_available = False
                xtb_by_symbol = {}

        items: list[InstrumentLiveQuote] = []
        for meta in metas:
            reference = _reference_from_meta(meta)
            xtb_symbol = to_xtb_symbol(meta.symbol, yahoo_symbol=meta.yahoo_symbol)
            bridge_quote = xtb_by_symbol.get(xtb_symbol)
            xtb_quote = _to_xtb_quote(bridge_quote) if bridge_quote is not None else None

            spread_pct: float | None = None
            if reference and xtb_quote and reference.price != 0:
                spread_pct = ((xtb_quote.last - reference.price) / reference.price) * 100

            items.append(
                InstrumentLiveQuote(
                    instrument_id=meta.id,
                    symbol=meta.symbol,
                    reference=reference,
                    xtb=xtb_quote,
                    spread_pct=spread_pct,
                    xtb_available=xtb_available,
                )
            )
        return items


class GetInstrumentLiveQuote:
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        xtb_bridge_url: str | None,
        *,
        _batch: GetInstrumentLiveQuotes | None = None,
    ) -> None:
        self._batch = _batch or GetInstrumentLiveQuotes(instrument_repository, xtb_bridge_url)

    async def execute(self, instrument_id: str) -> InstrumentLiveQuote | None:
        quotes = await self._batch.execute([instrument_id])
        return quotes[0] if quotes else None
