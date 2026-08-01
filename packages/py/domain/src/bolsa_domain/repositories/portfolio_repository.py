from typing import Literal, Protocol

from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, TradeResult, Transaction


class PortfolioRepository(Protocol):
    async def get_or_create_default_portfolio(self) -> Portfolio: ...

    async def get_summary(self) -> PortfolioSummary: ...

    async def list_transactions(self, limit: int = 50) -> list[Transaction]: ...

    async def execute_trade(
        self,
        *,
        instrument_id: str,
        trade_type: Literal["buy", "sell"],
        quantity: float,
        price: float,
    ) -> TradeResult: ...
