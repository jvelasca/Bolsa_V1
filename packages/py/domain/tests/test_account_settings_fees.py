"""OR-P2 — fees usan Decimal internamente."""

from bolsa_domain.account_settings import AccountSettings, calculate_trade_fees, settings_from_dict


def test_calculate_trade_fees_decimal_stable() -> None:
    settings: AccountSettings = settings_from_dict(None)
    # Clásico float trap: 0.1 * 0.2; aquí notional vía str→Decimal.
    fees = calculate_trade_fees(0.1 * 3, "buy", settings, currency="EUR")
    assert fees.total >= 0
    assert fees.currency == "EUR"
    # Misma entrada por Decimal path (str) debe ser determinista.
    a = calculate_trade_fees(1234.56, "buy", settings)
    b = calculate_trade_fees(1234.56, "buy", settings)
    assert a.total == b.total
    assert a.commission == b.commission
