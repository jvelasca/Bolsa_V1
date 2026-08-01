from bolsa_market.xtb_symbols import to_xtb_symbol


def test_to_xtb_symbol_uses_yahoo_suffix_for_foreign_listings() -> None:
    assert to_xtb_symbol("DHL", yahoo_symbol="DHL.DE") == "DHL.DE"


def test_to_xtb_symbol_defaults_to_es_for_local_symbol() -> None:
    assert to_xtb_symbol("AENA") == "AENA.ES"
