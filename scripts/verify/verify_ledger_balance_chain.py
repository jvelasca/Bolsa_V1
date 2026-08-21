#!/usr/bin/env python3
"""Fase R-9.7 (F7) + R-10 F3 — verificación del invariante ``balance_after`` en el ledger real.

Recorre ``ledger_entries`` por ``account_id`` en orden ``(executed_at, id)`` y
comprueba el invariante **secuencial por fila** para TODO el ledger::

    balance_after[n] == balance_after[n-1] + amount[n]

La fila ``trade`` y la fila ``fee`` de una operación ya NO comparten balance_after;
desde R-10 F3, ``ExecuteTrade`` escribe ``balance_after`` secuenciales:

- ``trade``: cash tras aplicar SOLO el notional (aún sin fee).
- ``fee``:   cash tras aplicar notional + fee (= cash final post-operación).

Para una fila aislada (deposit/withdrawal/fee/custody) la misma regla encadena con
la anterior. No existe caso de grupo que comparta balance_after.

Uso (repo root):
  uv run python scripts/verify/verify_ledger_balance_chain.py

Exit 0 si todas las cuentas cumplen el invariante; exit 1 con mensaje claro si no.
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


async def _run() -> int:
    _load_env()
    from sqlalchemy import select, text

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import LedgerEntryRow
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
            print(f"  {account_id}: {result}")
            if result.startswith("FAIL"):
                failures += 1
    await engine.dispose()

    if failures:
        print(f"FAIL: {failures} cuenta(s) NO cumplen el invariante balance_after")
        return 1
    print("OK: todas las cuentas cumplen la cadena balance_after")
    return 0


def main() -> int:
    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
