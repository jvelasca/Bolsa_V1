"""Catálogo conocido de índices populares (descubrimiento + constitutivos)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnownIndex:
    code: str
    display_name: str
    yahoo_symbol: str
    region: str
    currency: str
    """Provider de constitutivos: curated | remote_us | remote_intl | pending."""
    constituent_provider: str
    expected_count_min: int
    expected_count_max: int


KNOWN_INDICES: dict[str, KnownIndex] = {
    # —— Europa (prioridad producto ES/EU) ——
    "IBEX35": KnownIndex(
        code="IBEX35",
        display_name="IBEX 35",
        yahoo_symbol="^IBEX",
        region="ES",
        currency="EUR",
        constituent_provider="curated",
        expected_count_min=33,
        expected_count_max=37,
    ),
    "DAX": KnownIndex(
        code="DAX",
        display_name="DAX",
        yahoo_symbol="^GDAXI",
        region="DE",
        currency="EUR",
        constituent_provider="remote_intl",
        expected_count_min=38,
        expected_count_max=42,
    ),
    "STOXX50E": KnownIndex(
        code="STOXX50E",
        display_name="Euro Stoxx 50",
        yahoo_symbol="^STOXX50E",
        region="EU",
        currency="EUR",
        constituent_provider="remote_intl",
        expected_count_min=48,
        expected_count_max=52,
    ),
    "FTSE100": KnownIndex(
        code="FTSE100",
        display_name="FTSE 100",
        yahoo_symbol="^FTSE",
        region="GB",
        currency="GBP",
        constituent_provider="remote_intl",
        expected_count_min=90,
        expected_count_max=110,
    ),
    "FTSEMIB": KnownIndex(
        code="FTSEMIB",
        display_name="FTSE MIB",
        yahoo_symbol="FTSEMIB.MI",
        region="IT",
        currency="EUR",
        constituent_provider="remote_intl",
        expected_count_min=35,
        expected_count_max=45,
    ),
    # —— EE.UU. ——
    "SPX": KnownIndex(
        code="SPX",
        display_name="S&P 500",
        yahoo_symbol="^GSPC",
        region="US",
        currency="USD",
        constituent_provider="remote_us",
        expected_count_min=480,
        expected_count_max=520,
    ),
    "OEX": KnownIndex(
        code="OEX",
        display_name="S&P 100",
        yahoo_symbol="^OEX",
        region="US",
        currency="USD",
        constituent_provider="remote_us",
        expected_count_min=90,
        expected_count_max=110,
    ),
    "NDX": KnownIndex(
        code="NDX",
        display_name="NASDAQ-100",
        yahoo_symbol="^NDX",
        region="US",
        currency="USD",
        constituent_provider="remote_intl",
        expected_count_min=95,
        expected_count_max=105,
    ),
    "DJI": KnownIndex(
        code="DJI",
        display_name="Dow Jones",
        yahoo_symbol="^DJI",
        region="US",
        currency="USD",
        constituent_provider="remote_intl",
        expected_count_min=28,
        expected_count_max=32,
    ),
    # —— Asia ——
    "HSI": KnownIndex(
        code="HSI",
        display_name="Hang Seng",
        yahoo_symbol="^HSI",
        region="HK",
        currency="HKD",
        constituent_provider="remote_intl",
        expected_count_min=70,
        expected_count_max=95,
    ),
    # Pendientes (sin CSV Yahoo-aligned estable aún): CAC40, AEX, SMI, N225…
}


def get_known_index(code_or_yahoo: str) -> KnownIndex | None:
    key = code_or_yahoo.strip().upper()
    if key in KNOWN_INDICES:
        return KNOWN_INDICES[key]
    for item in KNOWN_INDICES.values():
        if item.yahoo_symbol.upper() == key or item.yahoo_symbol.upper() == f"^{key.lstrip('^')}":
            return item
    return None


def catalog_list_id_for_index(code: str) -> str:
    """ID estable de InstrumentList para un índice (source=catalog)."""
    normalized = code.strip().upper()
    if normalized == "IBEX35":
        return "ibex35"
    return f"idx-{normalized.lower()}"


def index_code_from_catalog_list_id(list_id: str) -> str | None:
    """Inverse: id de lista catalog → código índice, o None."""
    lid = (list_id or "").strip()
    if lid == "ibex35":
        return "IBEX35"
    if lid.startswith("idx-"):
        code = lid[4:].upper()
        return code if code in KNOWN_INDICES else None
    return None
