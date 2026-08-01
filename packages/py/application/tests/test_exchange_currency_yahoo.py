"""Smoke: exchange/currency heurística de import."""

from bolsa_application.market_indices import _exchange_currency_for_yahoo


def test_exchange_currency_heuristics() -> None:
    assert _exchange_currency_for_yahoo("SAN.MC") == ("BME", "EUR")
    assert _exchange_currency_for_yahoo("SAP.DE") == ("XETRA", "EUR")
    assert _exchange_currency_for_yahoo("AIR.PA") == ("UNKNOWN", "EUR")
    assert _exchange_currency_for_yahoo("AAPL") == ("UNKNOWN", "USD")
    assert _exchange_currency_for_yahoo("VOD.L") == ("LSE", "GBP")

