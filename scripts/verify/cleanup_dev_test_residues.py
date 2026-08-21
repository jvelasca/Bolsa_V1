#!/usr/bin/env python3
"""R-12 A6 — listar / borrar residuos de tests en la DB de desarrollo.

Residuos históricos que NO rompen ``verify_ledger_balance_chain`` (EXIT 0) pero
ensucian la BD compartida: cuentas ``simulated`` cuyo nombre contiene
``m7-win-`` y instrumentos cuyo nombre empieza por ``M2 ``.

Por defecto solo LISTA. El borrado usa el path canónico
``close_account`` → ``delete_simulated_account`` (D6: no backfill) y exige
``--apply``.

Uso (repo root)::

    uv run python scripts/verify/cleanup_dev_test_residues.py
    uv run python scripts/verify/cleanup_dev_test_residues.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
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

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:  # noqa: BLE001
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


async def _run(*, apply: bool) -> int:
    _load_env()
    from sqlalchemy import or_, select

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import InstrumentRow, InvestmentAccountRow
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    print("=== cleanup_dev_test_residues ===")
    try:
        async with factory() as session:
            accounts = (
                await session.execute(
                    select(InvestmentAccountRow).where(
                        InvestmentAccountRow.type == "simulated",
                        or_(
                            InvestmentAccountRow.name.ilike("%m7-win-%"),
                            InvestmentAccountRow.name.ilike("%M7-win-%"),
                            InvestmentAccountRow.name.ilike("CHAOS m7%"),
                        ),
                    )
                )
            ).scalars().all()
            instruments = (
                await session.execute(
                    select(InstrumentRow).where(InstrumentRow.name.like("M2 %"))
                )
            ).scalars().all()
            print(f"cuentas candidatas: {len(accounts)}")
            for account_row in accounts:
                print(f"  account {account_row.id}  {account_row.name!r}  status={account_row.status}")
            print(f"instrumentos candidatos: {len(instruments)}")
            for instrument_row in instruments:
                print(f"  instrument {instrument_row.id}  {instrument_row.name!r}  {instrument_row.symbol}")
            if not apply:
                print("OK: dry-run (pasa --apply para borrar por path canónico)")
                return 0
            repo = SqlAlchemyAccountRepository(session)
            for account_row in accounts:
                try:
                    if account_row.status == "active":
                        await repo.close_account(account_row.id)
                    await repo.delete_simulated_account(account_row.id)
                    print(f"  deleted account {account_row.id}")
                except Exception as exc:  # noqa: BLE001
                    print(f"  FAIL account {account_row.id}: {exc}")
                    await session.rollback()
                    return 1
            for instrument_row in instruments:
                await session.delete(instrument_row)
                print(f"  deleted instrument {instrument_row.id}")
            await session.commit()
            print("OK: residuos aplicados")
            return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Borrar de verdad (close+delete canónico). Sin este flag solo lista.",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_run(apply=args.apply))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
