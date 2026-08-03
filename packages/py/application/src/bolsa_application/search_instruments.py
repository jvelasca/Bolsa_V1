"""Búsqueda de instrumentos: catálogo local + Yahoo Finance.

GET /api/instruments/search?q= devuelve coincidencias en BD y hits externos
(no importados) para mostrar en el dropdown de listas.

Los hits externos se importan vía ImportInstrument al seleccionarlos en UI.
"""
from dataclasses import dataclass

from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.instrument_search import looks_like_isin_query, normalize_isin
from bolsa_market.yahoo_client import get_yahoo_finance_client, normalize_yahoo_error


@dataclass(frozen=True, slots=True)
class ExternalSearchHit:
    """DTO fila: External Search Hit."""
    symbol: str
    yahoo_symbol: str
    name: str
    exchange: str
    currency: str
    isin: str | None = None


@dataclass(frozen=True, slots=True)
class SearchInstrumentsResult:
    """Busca Instruments Result."""
    catalog: list[InstrumentWithMeta]
    external: list[ExternalSearchHit]


class SearchInstruments:
    """Busca Instruments."""
    def __init__(self, repo: SqlAlchemyInstrumentRepository) -> None:
        self._repo = repo

    async def execute(self, query: str, *, limit: int = 12) -> SearchInstrumentsResult:
        q = query.strip()
        if not q:
            return SearchInstrumentsResult(catalog=[], external=[])

        catalog = list(await self._repo.search_catalog(q, limit=limit))
        isin_hint = normalize_isin(q) if looks_like_isin_query(q) else None
        catalog = await self._merge_catalog_for_isin_query(q, catalog, limit=limit, isin_hint=isin_hint)
        known_yahoo = {item.yahoo_symbol.upper() for item in catalog}
        external: list[ExternalSearchHit] = []

        if len(catalog) < limit:
            try:
                client = get_yahoo_finance_client()
                quotes = await client.search_quotes(q, quotes_count=limit)
                for quote in quotes:
                    if quote.get("quoteType") != "EQUITY" or not quote.get("symbol"):
                        continue
                    yahoo_symbol = str(quote["symbol"])
                    if yahoo_symbol.upper() in known_yahoo:
                        continue
                    symbol = yahoo_symbol.replace(".MC", "").replace(".MA", "")
                    external.append(
                        ExternalSearchHit(
                            symbol=symbol,
                            yahoo_symbol=yahoo_symbol,
                            name=str(
                                quote.get("longname")
                                or quote.get("shortname")
                                or symbol,
                            ),
                            exchange=str(quote.get("exchange") or "UNKNOWN"),
                            currency=str(quote.get("currency") or "EUR"),
                            isin=isin_hint,
                        ),
                    )
                    if len(catalog) + len(external) >= limit:
                        break
            except Exception as exc:
                # Búsqueda externa es best-effort; el catálogo local sigue disponible.
                _ = normalize_yahoo_error(exc)

        return SearchInstrumentsResult(catalog=catalog, external=external)

    async def _merge_catalog_for_isin_query(
        self,
        query: str,
        catalog: list[InstrumentWithMeta],
        *,
        limit: int,
        isin_hint: str | None,
    ) -> list[InstrumentWithMeta]:
        if not isin_hint:
            return catalog

        catalog_ids = {item.id for item in catalog}
        try:
            client = get_yahoo_finance_client()
            quotes = await client.search_quotes(query, quotes_count=limit)
        except Exception as exc:
            _ = normalize_yahoo_error(exc)
            return catalog

        for quote in quotes:
            if quote.get("quoteType") != "EQUITY" or not quote.get("symbol"):
                continue
            yahoo_symbol = str(quote["symbol"]).upper()
            existing = await self._repo.get_by_yahoo_symbol(yahoo_symbol)
            if existing is None:
                continue
            if not existing.isin:
                await self._repo.update_isin(existing.id, isin_hint)
            if existing.id in catalog_ids:
                continue
            meta = await self._repo.get_with_meta_by_id(existing.id)
            if meta is None:
                continue
            catalog.append(meta)
            catalog_ids.add(meta.id)
            if len(catalog) >= limit:
                break

        refreshed: list[InstrumentWithMeta] = []
        for item in catalog:
            if isin_hint and not item.isin:
                updated = await self._repo.get_with_meta_by_id(item.id)
                refreshed.append(updated or item)
            else:
                refreshed.append(item)
        return refreshed
