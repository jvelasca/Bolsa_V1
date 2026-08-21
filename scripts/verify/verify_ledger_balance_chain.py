#!/usr/bin/env python3
"""Fase R-9.7 (F7) + R-10 F3 — verificación de los invariantes A + B del ledger real.

Recorre ``ledger_entries`` por ``account_id`` en orden ``(executed_at, id)`` y
comprueba, por cuenta, las invariantes **A** (cash↔ledger, M-2) y **B**
(secuencial por fila):

**Invariante B** (cadena ``balance_after``)::

    balance_after[n] == balance_after[n-1] + amount[n]

La fila ``trade`` y la fila ``fee`` de una operación ya NO comparten balance_after;
desde R-10 F3, ``ExecuteTrade`` escribe ``balance_after`` secuenciales:

- ``trade``: cash tras aplicar SOLO el notional (aún sin fee).
- ``fee``:   cash tras aplicar notional + fee (= cash final post-operación).

Para una fila aislada (deposit/withdrawal/fee/custody) la misma regla encadena con
la anterior. No existe caso de grupo que comparta balance_after.

**Invariante A** (M-2, conciliación cash↔ledger)::

    Σ ledger_entries.amount del account == Σ portfolios.cash del account

``Σ ledger`` no filtra por ``type`` (toda fila muta cash) e incluye la fila
``deposit`` +``initial_deposit`` del seed. El cash del account es la **suma** del
``cash`` de TODAS sus legacy portfolios (vía ``InvestmentPortfolioRow.
legacy_portfolio_id -> PortfolioRow.cash``), no de una sola cartera. Cuentas sin
portfolios exigen ``Σ ledger == 0``. Comparación con tolerancia ``1e-6``
(NUMERIC(18,6)). No se hacen backfill: si una cuenta legacy no cumple A, se refleja
el FAIL en la salida (política D6).

Uso (repo root):
  uv run python scripts/verify/verify_ledger_balance_chain.py

Exit 0 si todas las cuentas cumplen A y B; exit 1 con mensaje claro si alguna
falla o si no hay conexión.
"""

from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (
    ROOT / "packages" / "py" / "infrastructure" / "src",
    ROOT / "packages" / "py" / "domain" / "src",
    ROOT / "packages" / "py" / "market" / "src",
    ROOT / "packages" / "py" / "application" / "src",
):
    if str(_p) not in sys.path:
        sys.path[:0] = [str(_p)]

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra).
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:  # noqa: BLE001 - ya seguro en plataformas sin esta política
        pass


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _validate_sequential(rows: list[tuple[str, str, str, Decimal, Decimal]], account_id: str) -> str:
    """Valida el invariante **secuencial por fila** sobre filas ordenadas.

    Cada fila del query es ``(id, reference_id, reference_type, amount,
    balance_after)``. Regla: ``balance_after[n] == balance_after[n-1] + amount[n]``
    arrancando desde ``prev_balance = 0`` (semántica R-10 F3, sin grupos que
    compartan balance_after). Devuelve 'OK (...) ' o 'FAIL (...) ' con el detalle.
    """
    if not rows:
        return "OK (sin entradas)"
    prev_balance = Decimal("0")
    for r in rows:
        expected = prev_balance + r[3]
        if r[4] != expected:
            return (
                f"FAIL(cuenta {account_id}) fila {r[0]}: balance_after {r[4]} "
                f"!= prev {prev_balance} + amount {r[3]} = {expected}"
            )
        prev_balance = r[4]
    return f"OK (final balance_after {prev_balance})"


def _validate_account_cash_ledger(
    ledger_total: Decimal, cash_total: Decimal, account_id: str
) -> str:
    """Valida el invariante **A** (M-2) para una cuenta: cash del account == Σ ledger.

    ``ledger_total`` = Σ ``amount`` de TODAS las filas ledger del account (sin
    filtrar por ``type``; incluye el ``deposit`` +``initial_deposit`` del seed).
    ``cash_total`` = Σ ``PortfolioRow.cash`` de TODAS sus legacy portfolios.

    Compara con tolerancia ``Decimal("1e-6")`` (NUMERIC(18,6)). Cuentas sin
    portfolios (``cash_total == 0``) exigen ``ledger_total == 0`` dentro de la
    tolerancia. Devuelve ``'OK ...'`` o ``'FAIL(...) ...'`` con el detalle.
    """
    tolerance = Decimal("1e-6")
    if abs(ledger_total - cash_total) > tolerance:
        return (
            f"FAIL(cuenta {account_id}) sum_ledger {ledger_total} != "
            f"sum_cash_portfolios {cash_total} (diff {ledger_total - cash_total})"
        )
    return f"OK (sum_ledger {ledger_total} == sum_cash {cash_total})"


async def _run() -> int:
    _load_env()
    from sqlalchemy import select, text

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import (
        InvestmentPortfolioRow,
        LedgerEntryRow,
        PortfolioRow,
    )
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    print("=== verify_ledger_balance_chain ===")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        print(f"FAIL: no se pudo conectar a PostgreSQL ({exc})")
        return 1

    async with engine.connect() as conn:
        acct_ids = (
            await conn.execute(
                select(LedgerEntryRow.account_id)
                .distinct()
                .order_by(LedgerEntryRow.account_id)
            )
        ).scalars().all()

    failures = 0
    async with engine.connect() as conn:
        for account_id in acct_ids:
            res = await conn.execute(
                select(
                    LedgerEntryRow.id,
                    LedgerEntryRow.reference_id,
                    LedgerEntryRow.reference_type,
                    LedgerEntryRow.amount,
                    LedgerEntryRow.balance_after,
                )
                .where(LedgerEntryRow.account_id == account_id)
                .order_by(LedgerEntryRow.executed_at, LedgerEntryRow.id)
            )
            rows = [
                (
                    str(r[0]),
                    (str(r[1]) if r[1] is not None else ""),
                    (str(r[2]) if r[2] is not None else ""),
                    r[3],
                    r[4],
                )
                for r in res.all()
            ]
            result = _validate_sequential(rows, str(account_id))
            print(f"  {account_id} [B balance_after]: {result}")
            if result.startswith("FAIL"):
                failures += 1

            # Invariante A (M-2): Σ ledger.amount == Σ portfolios.cash del account.
            ledger_total = (
                await conn.execute(
                    select(LedgerEntryRow.amount).where(
                        LedgerEntryRow.account_id == account_id
                    )
                )
            ).scalars().all()
            ledger_sum = sum(ledger_total, Decimal("0"))

            cash_values = (
                await conn.execute(
                    select(PortfolioRow.cash)
                    .join(
                        InvestmentPortfolioRow,
                        InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
                    )
                    .where(InvestmentPortfolioRow.account_id == account_id)
                )
            ).scalars().all()
            cash_sum = sum((c for c in cash_values if c is not None), Decimal("0"))

            result_a = _validate_account_cash_ledger(ledger_sum, cash_sum, str(account_id))
            print(f"  {account_id} [A cash-ledger]: {result_a}")
            if result_a.startswith("FAIL"):
                failures += 1
    await engine.dispose()

    if failures:
        print(f"FAIL: {failures} cuenta(s) NO cumplen invariantes A/B del ledger")
        return 1
    print("OK: todas las cuentas cumplen A (cash-ledger) y B (cadena balance_after)")
    return 0


def main() -> int:
    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
