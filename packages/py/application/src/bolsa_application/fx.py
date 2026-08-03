"""Use-cases de tipos de cambio (FX)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from bolsa_market.yahoo_client import get_yahoo_finance_client, normalize_yahoo_error


@dataclass(frozen=True, slots=True)
class FxRate:
    """Use-case / tipo: Fx Rate."""
    from_currency: str
    to_currency: str
    rate: float
    yahoo_symbol: str
    timestamp: str
    source: str = "yahoo"


class GetFxRate:
    """Obtiene Fx Rate."""
    async def execute(self, from_currency: str, to_currency: str) -> FxRate:
        base = from_currency.strip().upper()
        quote = to_currency.strip().upper()
        if not base or not quote:
            raise ValueError("Divisas from y to son obligatorias")
        if base == quote:
            return FxRate(
                from_currency=base,
                to_currency=quote,
                rate=1.0,
                yahoo_symbol=f"{base}{quote}",
                timestamp=datetime.now(UTC).isoformat(),
            )

        client = get_yahoo_finance_client()
        direct = f"{base}{quote}=X"
        try:
            price, timestamp = await client.fetch_spot_price(direct)
            return FxRate(
                from_currency=base,
                to_currency=quote,
                rate=price,
                yahoo_symbol=direct,
                timestamp=timestamp,
            )
        except Exception as direct_error:
            inverse = f"{quote}{base}=X"
            try:
                price, timestamp = await client.fetch_spot_price(inverse)
                if price == 0:
                    raise ValueError("Tipo de cambio inválido")
                return FxRate(
                    from_currency=base,
                    to_currency=quote,
                    rate=1.0 / price,
                    yahoo_symbol=inverse,
                    timestamp=timestamp,
                )
            except Exception as inverse_error:
                raise RuntimeError(
                    normalize_yahoo_error(inverse_error)
                    or normalize_yahoo_error(direct_error)
                    or f"No se pudo obtener FX {base}/{quote}",
                ) from inverse_error
