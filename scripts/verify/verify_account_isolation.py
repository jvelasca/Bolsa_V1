#!/usr/bin/env python3
"""Fase R-9.7 (F7) — verificación de AISLAMIENTO por cuenta (A/B) fuera de pytest.

Crea dos cuentas simuladas y usa la MISMA ``idempotency_key``/``reference_id`` en
ambas vía el repo real de ledger (``append_cash_movement``, deposit). Comprueba que
produce exactamente 1 fila por cuenta — la semántica F1 (lookup por cuenta+type) y el
UNIQUE por-cuenta+type hacen que la misma key en otra cuenta sea legítima y NO se
"absorba". Al final limpia las cuentas e instrumentos creados (best-effort).

Uso (repo root):
  uv run python scripts/verify/verify_account_isolation.py

Exit 0 si hay exactamente 1 fila por cuenta y el lookup aislado funciona;
exit 1 con mensaje claro si no.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

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


def _now() -> datetime:
    return datetime.now(UTC)


async def _make_account(
    session: AsyncSession, tag: str
) -> tuple[str, str, str]:
    """Crea una cuenta simulada + instrumento; devuelve (account_id, pf_id, instrument_id)."""
    from bolsa_infrastructure.database.models import InstrumentRow
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"VerifyA {tag}",
        initial_deposit=100_000.0,
    )
    pf_id = scope.portfolio.id
    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"VA{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"VA{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"VerifyA {tag}",
        exchange="BMAD",
        country="ES",
        currency="EUR",
        type="stock",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(instrument)
    await session.flush()
    return scope.account.id, pf_id, instrument.id


async def _cleanup(session: AsyncSession, account_id: str, instrument_id: str) -> None:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    repo = SqlAlchemyAccountRepository(session)
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models import InstrumentRow

    try:
        await repo.close_account(account_id)
        await repo.delete_simulated_account(account_id)
        await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
        await session.commit()
    except Exception:  # noqa: BLE001 - cleanup best-effort
        await session.rollback()


async def _run() -> int:
    _load_env()
    from sqlalchemy import func, select, text

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import LedgerEntryRow
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    print("=== verify_account_isolation ===")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        print(f"FAIL: no se pudo conectar a PostgreSQL ({exc})")
        return 1

    factory = create_session_factory(engine)
    shared_key = f"verify-iso-{uuid4().hex[:10]}"
    created: list[tuple[str, str]] = []  # (account_id, instrument_id)
    result_code = 1
    try:
        async with factory() as setup:
            acc_a, pf_a, inst_a = await _make_account(setup, "a")
            acc_b, pf_b, inst_b = await _make_account(setup, "b")
            created = [(acc_a, inst_a), (acc_b, inst_b)]
            repo = SqlAlchemyLedgerRepository(setup)
            await repo.append_cash_movement(
                account_id=acc_a,
                portfolio_id=pf_a,
                entry_type="deposit",
                amount=500.0,
                currency="EUR",
                balance_after=100_500.0,
                reference_id=shared_key,
                reference_type="external",
                description="verify iso A",
            )
            await repo.append_cash_movement(
                account_id=acc_b,
                portfolio_id=pf_b,
                entry_type="deposit",
                amount=750.0,
                currency="EUR",
                balance_after=100_750.0,
                reference_id=shared_key,
                reference_type="external",
                description="verify iso B",
            )
            await setup.commit()

            # Exactamente 1 fila por cuenta + lookup aislado. ``amount`` es el DELTA
            # del movimiento (500 para A, 750 para B), no el balance_after.
            for acc, amount in ((acc_a, 500.0), (acc_b, 750.0)):
                via_lookup = await repo.find_cash_movement_by_reference(
                    "external", shared_key, account_id=acc, type="deposit"
                )
                if via_lookup is None or via_lookup.account_id != acc:
                    print(f"FAIL: cuenta {acc} no encontró SU movimiento (se absorbió)")
                    return 1
                if via_lookup.amount != amount:
                    print(f"FAIL: cuenta {acc} importe inesperado {via_lookup.amount} != {amount}")
                    return 1
            total = (
                await setup.execute(
                    select(func.count(LedgerEntryRow.id)).where(
                        LedgerEntryRow.reference_type == "external",
                        LedgerEntryRow.reference_id == shared_key,
                        LedgerEntryRow.type == "deposit",
                    )
                )
            ).scalar_one()
            if int(total) != 2:
                print(f"FAIL: se esperaban exactamente 2 filas (1 por cuenta), hay {total}")
                return 1
            result_code = 0
        if result_code == 0:
            print(
                "OK: la misma idempotency_key en dos cuentas produce 1 fila por cuenta (aislada)"
            )
        return result_code
    finally:
        if created:
            async with factory() as cleanup_session:
                for acc_id, inst_id in created:
                    await _cleanup(cleanup_session, acc_id, inst_id)
        await engine.dispose()


def main() -> int:
    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
