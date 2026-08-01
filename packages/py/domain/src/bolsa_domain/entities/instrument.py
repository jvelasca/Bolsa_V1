from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Instrument:
    """Activo listado — entidad de dominio sin dependencias externas."""

    id: str
    symbol: str
    yahoo_symbol: str
    name: str
    exchange: str
    currency: str
    country: str = "ES"
    sector: str | None = None
    isin: str | None = None
    is_active: bool = True
