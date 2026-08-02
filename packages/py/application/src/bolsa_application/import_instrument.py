"""Importar un instrumento externo (Yahoo) al catálogo local.

Flujo:
    1. Buscar por yahoo_symbol; si no existe, crear Instrument en BD.
    2. Opcionalmente ejecutar SyncInstrumentDailyBars (years_back).
    3. Devolver instrumento con meta (lastSync) y flags created/sync.

Usado por POST /api/instruments/import (búsqueda Yahoo en listas).
"""
from dataclasses import dataclass

from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta
from bolsa_domain.value_objects.market import SyncResult
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.ids import new_id
from bolsa_infrastructure.instrument_search import normalize_isin

from bolsa_application.sync_instrument import SyncInstrumentDailyBars


def infer_market_meta(yahoo_symbol: str, exchange: str, currency: str) -> tuple[str, str]:
    normalized = yahoo_symbol.upper()
    if normalized.endswith(".MC") or normalized.endswith(".MA"):
        return "BME", "ES"
    if normalized.endswith(".DE"):
        return exchange or "XETRA", "DE"
    if normalized.endswith(".L"):
        return exchange or "LSE", "GB"
    if normalized.endswith(".PA"):
        return exchange or "EPA", "FR"
    if exchange.upper() in {"BME", "MCE", "MAD"}:
        return "BME", "ES"
    if currency.upper() == "USD":
        return exchange or "NASDAQ", "US"
    if currency.upper() == "GBP":
        return exchange or "LSE", "GB"
    if "." not in normalized and exchange.upper() in {"NMS", "NYQ", "NASDAQ", "NYSE", "NGM"}:
        return exchange, "US"
    return exchange or "UNKNOWN", "ES"


@dataclass(frozen=True, slots=True)
class ImportInstrumentResult:
    instrument: InstrumentWithMeta
    created: bool
    sync: SyncResult | None


class ImportInstrument:
    def __init__(
        self,
        repo: SqlAlchemyInstrumentRepository,
        sync_use_case: SyncInstrumentDailyBars,
    ) -> None:
        self._repo = repo
        self._sync = sync_use_case

    async def execute(
        self,
        *,
        yahoo_symbol: str,
        symbol: str,
        name: str,
        exchange: str,
        currency: str = "EUR",
        sync: bool = True,
        years_back: int = 5,
        isin: str | None = None,
    ) -> ImportInstrumentResult | None:
        yahoo = yahoo_symbol.strip()
        if not yahoo:
            raise ValueError("yahooSymbol es obligatorio")

        normalized_isin = normalize_isin(isin) if isin and isin.strip() else None
        if normalized_isin and len(normalized_isin) != 12:
            normalized_isin = None

        existing = await self._repo.get_by_yahoo_symbol(yahoo)
        created = False

        if existing is None:
            market_exchange, country = infer_market_meta(yahoo, exchange, currency)
            instrument = Instrument(
                id=new_id(),
                symbol=symbol.strip().upper() or yahoo.replace(".MC", "").replace(".MA", ""),
                yahoo_symbol=yahoo,
                name=name.strip() or symbol,
                exchange=market_exchange,
                country=country,
                currency=currency.strip().upper() or "EUR",
                sector=None,
                isin=normalized_isin,
                is_active=True,
            )
            await self._repo.create(instrument)
            created = True
            instrument_id = instrument.id
        else:
            instrument_id = existing.id
            if normalized_isin and not existing.isin:
                await self._repo.update_isin(instrument_id, normalized_isin)

        with_meta = await self._repo.get_with_meta_by_id(instrument_id)
        if with_meta is None:
            return None

        sync_result: SyncResult | None = None
        if sync:
            sync_result = await self._sync.execute(instrument_id, years_back=years_back)
            with_meta = await self._repo.get_with_meta_by_id(instrument_id) or with_meta

        return ImportInstrumentResult(
            instrument=with_meta,
            created=created,
            sync=sync_result,
        )
