"""Acredita un dividendo bruto y retiene en el mismo savepoint.

No lo llama el turno AUTO. No lee precios ni hechos societarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bolsa_domain.account_settings import settings_from_dict
from bolsa_domain.errors import IdempotencyKeyExists
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)

from .idempotency import _assert_cash_payload_matches, _idempotent_savepoint

_QUANT = Decimal("0.000001")
_REFERENCE_TYPE = "dividend"


def split_dividend(gross: Decimal, withholding_pct: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Devuelve ``(bruto, retención, neto)`` a 6 decimales."""
    if gross <= 0:
        raise ValueError("El dividendo bruto debe ser mayor que cero")
    if withholding_pct < 0 or withholding_pct > 100:
        raise ValueError("La retención del dividendo debe estar entre 0 y 100")
    gross_q = gross.quantize(_QUANT)
    withheld = (gross_q * withholding_pct / Decimal("100")).quantize(_QUANT)
    net = (gross_q - withheld).quantize(_QUANT)
    return gross_q, withheld, net


@dataclass(frozen=True)
class DividendCredit:
    """Resultado de acreditar un dividendo (bruto, retención y neto)."""

    account_id: str
    portfolio_id: str
    idempotency_key: str
    gross: float
    withholding: float
    net: float
    balance_after: float
    currency: str


class CreditDividend:
    """Acredita el bruto y escribe la retención en el mismo savepoint."""

    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        portfolio_repo: SqlAlchemyPortfolioRepository,
        ledger_repo: SqlAlchemyLedgerRepository,
    ) -> None:
        self._account_repo = account_repo
        self._portfolio_repo = portfolio_repo
        self._ledger_repo = ledger_repo

    async def execute(
        self,
        account_id: str,
        *,
        gross: float,
        idempotency_key: str,
        note: str | None = None,
    ) -> DividendCredit:
        if not idempotency_key.strip():
            raise ValueError("El dividendo exige idempotency_key")
        scope = await self._account_repo.resolve_scope(account_id)
        settings = scope.account.settings or settings_from_dict(None)
        gross_q, withheld, net = split_dividend(
            Decimal(str(gross)),
            Decimal(str(settings.tax.dividend_withholding_pct)),
        )
        await self._account_repo.lock_account(scope.account.id)
        existing = await self._ledger_repo.find_cash_movement_by_reference(
            _REFERENCE_TYPE,
            idempotency_key,
            account_id=scope.account.id,
            type="dividend",
        )
        if existing is not None:
            _assert_cash_payload_matches(
                existing,
                amount=float(gross_q),
                note=note,
                storage_sign=1,
                idempotency_key=idempotency_key,
            )
            withheld_entry = await self._ledger_repo.find_cash_movement_by_reference(
                _REFERENCE_TYPE,
                idempotency_key,
                account_id=scope.account.id,
                type="dividend_withholding",
            )
            withheld_amount = (
                abs(float(withheld_entry.amount)) if withheld_entry is not None else float(withheld)
            )
            return DividendCredit(
                account_id=account_id,
                portfolio_id=scope.portfolio.id,
                idempotency_key=idempotency_key,
                gross=float(existing.amount),
                withholding=withheld_amount,
                net=float(existing.amount) - withheld_amount,
                balance_after=float(
                    withheld_entry.balance_after if withheld_entry is not None else existing.balance_after
                ),
                currency=existing.currency,
            )
        session = getattr(self._ledger_repo, "session", None)
        description = note or "Dividendo"
        try:
            async with _idempotent_savepoint(session):
                after_gross = await self._portfolio_repo._credit_cash_row(
                    scope.legacy_portfolio_id,
                    float(gross_q),
                )
                await self._ledger_repo.append_cash_movement(
                    account_id=account_id,
                    portfolio_id=scope.portfolio.id,
                    entry_type="dividend",
                    amount=float(gross_q),
                    currency=scope.account.currency,
                    balance_after=after_gross,
                    reference_id=idempotency_key,
                    reference_type=_REFERENCE_TYPE,
                    description=description,
                )
                if withheld > 0:
                    balance_after = await self._portfolio_repo._debit_cash_row(
                        scope.legacy_portfolio_id,
                        float(withheld),
                    )
                else:
                    balance_after = after_gross
                await self._ledger_repo.append_cash_movement(
                    account_id=account_id,
                    portfolio_id=scope.portfolio.id,
                    entry_type="dividend_withholding",
                    amount=-float(withheld),
                    currency=scope.account.currency,
                    balance_after=balance_after,
                    reference_id=idempotency_key,
                    reference_type=_REFERENCE_TYPE,
                    description="Retención del dividendo",
                )
                await self._account_repo.touch_activity(account_id)
        except IdempotencyKeyExists:
            existing = await self._ledger_repo.find_cash_movement_by_reference(
                _REFERENCE_TYPE,
                idempotency_key,
                account_id=scope.account.id,
                type="dividend",
            )
            if existing is None:
                raise
            _assert_cash_payload_matches(
                existing,
                amount=float(gross_q),
                note=note,
                storage_sign=1,
                idempotency_key=idempotency_key,
            )
            return DividendCredit(
                account_id=account_id,
                portfolio_id=scope.portfolio.id,
                idempotency_key=idempotency_key,
                gross=float(existing.amount),
                withholding=float(withheld),
                net=float(net),
                balance_after=float(existing.balance_after),
                currency=existing.currency,
            )
        return DividendCredit(
            account_id=account_id,
            portfolio_id=scope.portfolio.id,
            idempotency_key=idempotency_key,
            gross=float(gross_q),
            withholding=float(withheld),
            net=float(net),
            balance_after=float(balance_after),
            currency=scope.account.currency,
        )


__all__ = ["CreditDividend", "DividendCredit", "split_dividend"]
