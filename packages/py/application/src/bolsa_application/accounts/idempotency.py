"""Helpers de idempotencia (SAVEPOINT, matchers cash/trade)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from bolsa_domain.entities.account import CashMovementResult, LedgerEntry
from bolsa_domain.entities.portfolio import Transaction
from bolsa_domain.errors import IdempotencyKeyReused
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def _idempotent_savepoint(
    session: AsyncSession | None,
) -> AsyncIterator[None]:
    """Abre un SAVEPOINT si hay una sesión real; no-op en tests con fakes.

    R-8A/P0-B: permite revertir SOLO el intento de escritura del perdedor de una
    carrera de idempotencia (``add_cash``/``deduct_cash`` + ``append_cash_movement``)
    sin descartar el estado de la transacción de la request. En los tests con repos
    fake (que no exponen ``session``) se ejecuta como no-op y el patrón sigue
    comportándose igual que antes (sin colisiones reales).
    """
    if session is None:
        yield
        return
    async with session.begin_nested():
        yield


def _cash_movement_result_from_entry(entry: LedgerEntry, kind: str) -> CashMovementResult:
    """Reconstruye un CashMovementResult desde la entrada de ledger original.

    Se usa para rejugar un movimento ya persistido (idempotencia) manteniendo la
    misma shape (id = reference_id de la entrada, que es la idempotency_key).
    """
    return CashMovementResult(
        id=entry.reference_id or entry.id,
        account_id=entry.account_id,
        portfolio_id=entry.portfolio_id or "",
        kind=kind,
        amount=entry.amount,
        currency=entry.currency,
        balance_after=entry.balance_after,
        executed_at=entry.executed_at,
        description=entry.description,
    )


def _cash_payload_matches(
    entry: LedgerEntry,
    *,
    amount: float,
    note: str | None,
    storage_sign: int,
) -> bool:
    """Compara el payload entrante de un deposit/withdraw contra lo persistido.

    El valor financiero crítico es el ``amount``. La entrada de ledger guarda el
    deposit con el importe positivo y el withdraw con su signo (negativo); la
    comparación aplica ``storage_sign`` (1 para deposit, -1 para withdraw) para
    alinear el entrante con el signo de almacenamiento. Se normaliza a ``Decimal``
    (con ``Decimal(str(x))``) y se compara por igualdad exacta a escala financiera
    de 6 decimales (Numeric(18,6)); no se usa ninguna tolerancia. ``note``/description
    se comparan exactamente sólo si el entrante aporta nota. Si algún campo
    difiere, la key se está reutilizando con un payload distinto → conflicto.
    """
    from decimal import Decimal

    amount_matches = Decimal(str(entry.amount)).quantize(Decimal("0.000001")) == Decimal(str(amount * storage_sign)).quantize(Decimal("0.000001"))
    if not amount_matches:
        return False
    if note is not None:
        return note == entry.description
    return True


def _assert_cash_payload_matches(
    entry: LedgerEntry,
    *,
    amount: float,
    note: str | None,
    storage_sign: int,
    idempotency_key: str,
) -> None:
    if not _cash_payload_matches(
        entry,
        amount=amount,
        note=note,
        storage_sign=storage_sign,
    ):
        raise IdempotencyKeyReused(idempotency_key)


def _trade_payload_matches(existing: Transaction, *, instrument_id: str, trade_type: str, quantity: float, price: float) -> bool:
    """Compara el payload entrante de un trade contra la transacción persistida.

    Coincide si `instrument_id`, `trade_type`, `quantity` y `price` son iguales.
    Se normaliza a ``Decimal`` (con ``Decimal(str(x))``) y se compara quantity/price
    por igualdad exacta a escala financiera de 6 decimales (Numeric(18,6)); no se
    usa ninguna tolerancia. ``total`` es derivable (quantity*price + fees) y no se
    compara directamente.
    """
    from decimal import Decimal

    if existing.instrument_id != instrument_id:
        return False
    if existing.type != trade_type:
        return False
    if Decimal(str(existing.quantity)).quantize(Decimal("0.000001")) != Decimal(str(quantity)).quantize(Decimal("0.000001")):
        return False
    if Decimal(str(existing.price)).quantize(Decimal("0.000001")) != Decimal(str(price)).quantize(Decimal("0.000001")):
        return False
    return True


def _assert_trade_payload_matches(existing: Transaction, *, instrument_id: str, trade_type: str, quantity: float, price: float, idempotency_key: str) -> None:
    if not _trade_payload_matches(
        existing,
        instrument_id=instrument_id,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
    ):
        raise IdempotencyKeyReused(idempotency_key)
