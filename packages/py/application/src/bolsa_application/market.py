"""Use-cases de estado de mercado y live quote."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from bolsa_domain.entities.market_provider import MarketProviderConfig
from bolsa_domain.repositories.instrument_repository import InstrumentRepository, InstrumentWithMeta
from bolsa_domain.value_objects.market import (
    InstrumentLiveQuote,
    LiveQuoteReference,
    MarketProviderStatus,
    XtbQuote,
)
from bolsa_market.providers import (
    XtbBridgeClient,
    XtbBridgeHealth,
    XtbBridgeQuote,
    format_xtb_bridge_connect_error,
)
from bolsa_market.xtb_symbols import to_xtb_symbol

_XTB_QUOTE_CONCURRENCY = 8


class GetMarketStatus:
    """Estado de los proveedores del registro, con la configuración efectiva.

    Doctrina de honestidad: **no** se declara un proveedor disponible por existir. Yahoo
    solo es ``healthy`` si su última verificación persistida fue correcta; sin verificación
    el estado es «sin verificar». XTB, cuando está usable, se mide en vivo contra el bridge
    (una petición de salud); si no hay URL, se declara «sin configurar».

    ``live=False`` (060) devuelve **solo lo persistido**: es la lectura que usa el icono de
    la barra, para que un GET no genere tráfico a proveedores y para que la barra y la
    tarjeta de Configuración no discrepen. Medir es competencia del comprobador.
    """

    def __init__(
        self,
        configs: Sequence[MarketProviderConfig],
        *,
        xtb_health: Callable[[str], Awaitable[XtbBridgeHealth]] | None = None,
        live: bool = True,
    ) -> None:
        self._configs = tuple(configs)
        self._xtb_health = xtb_health or _default_xtb_health
        self._live = live

    async def execute(self) -> list[MarketProviderStatus]:
        statuses: list[MarketProviderStatus] = []
        for config in self._configs:
            healthy = config.healthy
            verified = config.verified
            message = config.status_message
            if self._live and config.id == "xtb" and config.usable and config.base_url:
                try:
                    health = await self._xtb_health(config.base_url)
                except Exception as exc:  # noqa: BLE001 — el estado es el resultado
                    healthy = False
                    verified = True
                    message = format_xtb_bridge_connect_error(config.base_url, exc)
                else:
                    healthy = getattr(health, "status", "") == "ok"
                    verified = True
                    message = getattr(health, "message", "") or (
                        f"Bridge {getattr(health, 'mode', '')}".strip() or config.status_message
                    )
            statuses.append(
                MarketProviderStatus(
                    id=config.id,
                    label=config.label,
                    enabled=config.enabled,
                    healthy=healthy,
                    message=message,
                    priority=config.priority,
                    min_interval_seconds=config.min_interval_seconds,
                    base_url=config.base_url,
                    capabilities=config.capabilities,
                    description=config.description,
                    verified=verified,
                    base_url_source=config.base_url_source,
                    last_check_at=config.last_check_at,
                    last_check_ok=config.last_check_ok,
                    last_check_message=config.last_check_message,
                )
            )
        return statuses


async def _default_xtb_health(base_url: str) -> XtbBridgeHealth:
    return await XtbBridgeClient(base_url).check_health()


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
    """Batch live quotes: one meta hydrate + one XTB health + bounded quote fan-out.

    059 — la URL del bridge se resuelve en el momento de la petición (configuración
    persistida con fallback a entorno), no se congela al construir el caso de uso: un
    cambio en Configuración surte efecto sin reiniciar el proceso.
    """

    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        xtb_bridge_url: str | None,
        *,
        xtb_bridge_url_resolver: Callable[[], Awaitable[str | None]] | None = None,
    ) -> None:
        self._instruments = instrument_repository
        self._xtb_bridge_url = xtb_bridge_url
        self._xtb_bridge_url_resolver = xtb_bridge_url_resolver

    async def _bridge_url(self) -> str | None:
        if self._xtb_bridge_url_resolver is not None:
            resolved = await self._xtb_bridge_url_resolver()
            return (resolved or "").strip() or None
        return (self._xtb_bridge_url or "").strip() or None

    async def execute(self, instrument_ids: list[str]) -> list[InstrumentLiveQuote]:
        metas = await self._instruments.get_quotes_by_ids(instrument_ids)
        if not metas:
            return []

        xtb_by_symbol: dict[str, XtbBridgeQuote] = {}
        xtb_available = False
        bridge_url = await self._bridge_url()
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
    """Obtiene Instrument Live Quote."""

    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        xtb_bridge_url: str | None,
        *,
        _batch: GetInstrumentLiveQuotes | None = None,
        xtb_bridge_url_resolver: Callable[[], Awaitable[str | None]] | None = None,
    ) -> None:
        self._batch = _batch or GetInstrumentLiveQuotes(
            instrument_repository,
            xtb_bridge_url,
            xtb_bridge_url_resolver=xtb_bridge_url_resolver,
        )

    async def execute(self, instrument_id: str) -> InstrumentLiveQuote | None:
        quotes = await self._batch.execute([instrument_id])
        return quotes[0] if quotes else None
