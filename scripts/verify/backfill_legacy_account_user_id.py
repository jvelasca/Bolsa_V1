#!/usr/bin/env python3
"""R12-AUTH F7b — backfill one-shot de ``investment_accounts.user_id`` legacy NULL.

Migración **offline** (ventana de mantenimiento). Estampa
``Settings.owner_principal()`` (default ``"app"``) en filas con ``user_id IS NULL``:

    UPDATE investment_accounts SET user_id = :bootstrap WHERE user_id IS NULL

Prohibido en hot path: este módulo NO debe importarse ni invocarse desde
``database_bootstrap``, API, workers ni ``account_migration``. No corre al arranque.

Otras tablas con ``user_id`` NULL (workspaces, trackers, policies, platform_events)
quedan fuera de alcance: ADR-027 nombra solo ``investment_accounts``. F7a (soft
visibility) sigue vigente; F7c (hard close) no forma parte de este script.

Uso (repo root)::

    uv run python scripts/verify/backfill_legacy_account_user_id.py
    uv run python scripts/verify/backfill_legacy_account_user_id.py \\
        --apply --i-know-this-is-maintenance

Sin flags: dry-run (cuenta + lista ids; 0 UPDATEs). ``--apply`` exige también
``--i-know-this-is-maintenance``. Exit 0 en dry-run y apply OK; exit 1 si falla.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

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


async def list_legacy_null_account_ids(session: AsyncSession) -> list[str]:
    """Ids de ``investment_accounts`` con ``user_id IS NULL`` (solo lectura)."""
    from sqlalchemy import select

    from bolsa_infrastructure.database.models import InvestmentAccountRow

    rows = (
        await session.execute(
            select(InvestmentAccountRow.id)
            .where(InvestmentAccountRow.user_id.is_(None))
            .order_by(InvestmentAccountRow.id)
        )
    ).scalars().all()
    return [str(account_id) for account_id in rows]


async def apply_legacy_account_user_id_backfill(
    session: AsyncSession,
    *,
    bootstrap: str,
    restrict_to_ids: Sequence[str] | None = None,
) -> int:
    """``UPDATE investment_accounts SET user_id = :bootstrap WHERE user_id IS NULL``.

    No hace commit (lo decide el caller). ``restrict_to_ids`` es solo para tests
    sobre una BD compartida; el CLI nunca lo pasa (SQL = ADR-027 F7b).
    """
    from typing import Any, cast

    from sqlalchemy import update
    from sqlalchemy.engine import CursorResult

    from bolsa_infrastructure.database.models import InvestmentAccountRow

    if restrict_to_ids is not None and len(restrict_to_ids) == 0:
        return 0

    stmt = (
        update(InvestmentAccountRow)
        .where(InvestmentAccountRow.user_id.is_(None))
        .values(user_id=bootstrap)
    )
    if restrict_to_ids is not None:
        stmt = stmt.where(InvestmentAccountRow.id.in_(list(restrict_to_ids)))
    result = await session.execute(stmt)
    return int(cast(CursorResult[Any], result).rowcount)


async def _run(*, apply: bool) -> int:
    _load_env()
    from sqlalchemy import text

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    bootstrap = settings.owner_principal()
    engine = create_engine(settings)
    print("=== backfill_legacy_account_user_id ===")
    print(f"bootstrap: {bootstrap!r}")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        print(f"FAIL: no se pudo conectar a PostgreSQL ({exc})")
        return 1

    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            ids = await list_legacy_null_account_ids(session)
            print(f"legacy null user_id: {len(ids)}")
            for account_id in ids:
                print(f"  {account_id}")
            if not apply:
                print(
                    "OK: dry-run (0 UPDATEs). "
                    "Pasa --apply --i-know-this-is-maintenance para escribir."
                )
                return 0
            updated = await apply_legacy_account_user_id_backfill(
                session, bootstrap=bootstrap
            )
            await session.commit()
            print(f"OK: apply user_id={bootstrap!r} en {updated} filas")
            return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribe el UPDATE. Exige también --i-know-this-is-maintenance.",
    )
    parser.add_argument(
        "--i-know-this-is-maintenance",
        action="store_true",
        help="Acuse de ventana de mantenimiento (obligatorio junto a --apply).",
    )
    args = parser.parse_args(argv)
    if args.apply and not args.i_know_this_is_maintenance:
        print(
            "FAIL: --apply exige --i-know-this-is-maintenance "
            "(ventana de mantenimiento); 0 UPDATEs"
        )
        return 1
    apply = bool(args.apply and args.i_know_this_is_maintenance)
    try:
        return asyncio.run(_run(apply=apply))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
