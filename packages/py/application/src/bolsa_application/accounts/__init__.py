"""Use-cases de cuentas DEMO/trading, ledger y trades."""

from bolsa_application.accounts.cash import DepositCashToAccount, WithdrawCashFromAccount
from bolsa_application.accounts.crud import (
    CloseAccount,
    CreateSimulatedAccount,
    DeleteAccount,
    GetAccount,
    ListAccounts,
    SetDefaultAccount,
    UpdateAccount,
    UpdateAccountSettings,
)
from bolsa_application.accounts.custody import ApplyCustodyFees
from bolsa_application.accounts.ledger import ListLedgerEntries
from bolsa_application.accounts.portfolio import GetPortfolioSummary, ListTransactions
from bolsa_application.accounts.summary import (
    GetAccountSummary,
    ListAccountSummaries,
    _account_summary_from_portfolio,
)
from bolsa_application.accounts.tax import GetTaxReport
from bolsa_application.accounts.trade import ExecuteTrade

__all__ = [
    "ListAccounts",
    "CreateSimulatedAccount",
    "UpdateAccountSettings",
    "GetAccount",
    "GetAccountSummary",
    "ListAccountSummaries",
    "UpdateAccount",
    "SetDefaultAccount",
    "CloseAccount",
    "DeleteAccount",
    "DepositCashToAccount",
    "WithdrawCashFromAccount",
    "ApplyCustodyFees",
    "ListLedgerEntries",
    "GetPortfolioSummary",
    "ListTransactions",
    "ExecuteTrade",
    "GetTaxReport",
    "_account_summary_from_portfolio",
]
