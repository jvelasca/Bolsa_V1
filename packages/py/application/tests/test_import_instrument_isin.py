from unittest.mock import AsyncMock

import pytest
from bolsa_domain.entities.instrument import Instrument

from bolsa_application.import_instrument import ImportInstrument


@pytest.mark.asyncio
async def test_import_existing_instrument_backfills_isin_when_empty() -> None:
    repo = AsyncMock()
    sync = AsyncMock()
    existing = Instrument(
        id="inst-1",
        symbol="DHL",
        yahoo_symbol="DHL.DE",
        name="Deutsche Post AG",
        exchange="XETRA",
        country="DE",
        currency="EUR",
        isin=None,
    )
    repo.get_by_yahoo_symbol.return_value = existing
    repo.get_with_meta_by_id.return_value = AsyncMock(
        id="inst-1",
        symbol="DHL",
        yahoo_symbol="DHL.DE",
        isin="DE0005552004",
    )

    use_case = ImportInstrument(repo, sync)
    await use_case.execute(
        yahoo_symbol="DHL.DE",
        symbol="DHL",
        name="Deutsche Post AG",
        exchange="XETRA",
        currency="EUR",
        sync=False,
        isin="DE0005552004",
    )

    repo.update_isin.assert_awaited_once_with("inst-1", "DE0005552004")
    repo.create.assert_not_called()
