from unittest.mock import AsyncMock

import pytest

from bolsa_application.import_instrument import (
    ImportInstrument,
    normalize_symbol,
    normalize_yahoo_symbol,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BP", "BP"),
        ("BP.L", "BP.L"),
        ("BP/", "BP"),
        ("BP/.L", "BP.L"),
        ("BT/A", "BTA"),
        ("BT/A.L", "BTA.L"),
        ("  TEF.MC ", "TEF.MC"),
        ("", ""),
    ],
)
def test_normalize_yahoo_symbol_strips_slashes_and_whitespace(raw: str, expected: str) -> None:
    assert normalize_yahoo_symbol(raw) == expected


def test_normalize_symbol_falls_back_to_yahoo_symbol_when_empty() -> None:
    assert normalize_symbol("  ", "BP.L") == "BP.L"
    assert normalize_symbol("BTA", "BTA.L") == "BTA"
    assert normalize_symbol("", "TEF.MC") == "TEF"
    assert normalize_symbol("", "BP/.L") == "BP.L"


@pytest.mark.asyncio
async def test_import_new_instrument_stores_normalized_symbols() -> None:
    repo = AsyncMock()
    sync = AsyncMock()
    repo.get_by_yahoo_symbol.return_value = None
    repo.get_with_meta_by_id.return_value = AsyncMock(
        id="inst-1",
        symbol="BTA",
        yahoo_symbol="BTA.L",
        name="BT Group PLC",
        exchange="LSE",
        country="GB",
        currency="GBP",
    )

    use_case = ImportInstrument(repo, sync)
    await use_case.execute(
        yahoo_symbol="BT/A.L",
        symbol="BT/A",
        name="BT Group PLC",
        exchange="LSE",
        currency="GBP",
        sync=False,
    )

    created = repo.create.await_args.args[0]
    assert created.symbol == "BTA"
    assert created.yahoo_symbol == "BTA.L"
    assert created.exchange == "LSE"


@pytest.mark.asyncio
async def test_import_looks_up_normalized_yahoo_symbol() -> None:
    repo = AsyncMock()
    sync = AsyncMock()
    repo.get_by_yahoo_symbol.return_value = None
    repo.get_with_meta_by_id.return_value = AsyncMock(
        id="inst-2",
        symbol="BP",
        yahoo_symbol="BP.L",
        name="BP PLC",
        exchange="LSE",
        country="GB",
        currency="GBP",
    )

    use_case = ImportInstrument(repo, sync)
    await use_case.execute(
        yahoo_symbol="BP/.L",
        symbol="BP/",
        name="BP PLC",
        exchange="LSE",
        currency="GBP",
        sync=False,
    )

    repo.get_by_yahoo_symbol.assert_awaited_once_with("BP.L")
    created = repo.create.await_args.args[0]
    assert created.symbol == "BP"
    assert created.yahoo_symbol == "BP.L"


@pytest.mark.asyncio
async def test_import_clean_ticker_is_unchanged() -> None:
    repo = AsyncMock()
    sync = AsyncMock()
    repo.get_by_yahoo_symbol.return_value = None
    repo.get_with_meta_by_id.return_value = AsyncMock(
        id="inst-3",
        symbol="DHL",
        yahoo_symbol="DHL.DE",
        name="Deutsche Post AG",
        exchange="XETRA",
        country="DE",
        currency="EUR",
    )

    use_case = ImportInstrument(repo, sync)
    await use_case.execute(
        yahoo_symbol="DHL.DE",
        symbol="DHL",
        name="Deutsche Post AG",
        exchange="XETRA",
        currency="EUR",
        sync=False,
    )

    created = repo.create.await_args.args[0]
    assert created.symbol == "DHL"
    assert created.yahoo_symbol == "DHL.DE"
