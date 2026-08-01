from dataclasses import dataclass

from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.repositories.instrument_repository import InstrumentRepository, SyncLogDetail
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.services.price_summary import build_price_summary
from bolsa_domain.value_objects.price_summary import PriceSummary


@dataclass(frozen=True, slots=True)
class InstrumentDetail:
    instrument: Instrument
    last_sync: SyncLogDetail | None
    price_summary: PriceSummary | None


class GetInstrumentDetail:
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        ohlcv_repository: OhlcvRepository,
    ) -> None:
        self._instruments = instrument_repository
        self._ohlcv = ohlcv_repository

    async def execute(self, instrument_id: str) -> InstrumentDetail | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None

        last_sync = await self._instruments.get_last_sync_detail(instrument_id)
        bars = await self._ohlcv.get_bars(instrument_id, limit=500)
        price_summary = build_price_summary(bars, summary_limit=500)

        return InstrumentDetail(
            instrument=instrument,
            last_sync=last_sync,
            price_summary=price_summary,
        )
