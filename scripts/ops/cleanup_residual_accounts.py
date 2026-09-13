"""Limpieza puntual: borra las cuentas residuales de tests de integración.

Contexto: la BD acumuló 89 cuentas basura creadas por suites que no hacen teardown.
Todas tienen ``user_id='app'`` (el owner de la app), por lo que aparecen mezcladas con
datos reales en la UI y, además, rompen el worker de custodia (no tienen cartera legacy
válida, y una sola cuenta mala abortaba el job entero).

Criterio de borrado (lista BLANCA, no lista negra): sobrevive únicamente la cuenta demo
sembrada. Se comprobó que las 89 restantes tienen cartera legacy, así que discriminar
por "no tiene cartera" NO sirve; el único criterio seguro es la identidad de la demo.

Uso:
    python scripts/ops/cleanup_residual_accounts.py            # dry-run
    python scripts/ops/cleanup_residual_accounts.py --apply    # ejecuta

El borrado va en UNA transacción con recuento antes/después; si el recuento no cuadra,
hace rollback y no deja la BD a medias.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    # Psycopg async no funciona con ProactorEventLoop (default en Windows).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "py" / "infrastructure" / "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

# La ÚNICA cuenta que debe sobrevivir. La siembra el bootstrap de la app.
DEMO_ACCOUNT_ID = "default-account-seed"

# Tablas con FK a investment_accounts que hay que vaciar por cuenta (hijas primero).
ACCOUNT_CHILD_TABLES = (
    "core_r_account_state",
    "supervised_f3_account_state",
    "custody_obligation",
    "custody_obligations",
    "execution_policies",
    "position_policies",
    "position_states",
    "pending_orders",
    "mandate_trade_links",
    "mandate_tenures",
    "ledger_entries",
)


def _load_env() -> None:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


async def _residual_account_ids(session: AsyncSession) -> list[tuple[str, str]]:
    """(id, name) de todas las cuentas salvo la demo."""
    rows = await session.execute(
        text(
            "SELECT id, name FROM investment_accounts "
            "WHERE id <> :demo ORDER BY created_at"
        ),
        {"demo": DEMO_ACCOUNT_ID},
    )
    return [(str(r[0]), str(r[1])) for r in rows]


async def _delete_account_graph(session: AsyncSession, account_id: str) -> None:
    """Borra el grafo completo de una cuenta respetando el orden de FKs."""
    # Portfolios de la cuenta (y sus legacy_portfolio_id) antes que la cuenta.
    portfolio_rows = await session.execute(
        text(
            "SELECT id, legacy_portfolio_id FROM investment_portfolios "
            "WHERE account_id = :aid"
        ),
        {"aid": account_id},
    )
    portfolios = [(str(r[0]), r[1]) for r in portfolio_rows]

    for table in ACCOUNT_CHILD_TABLES:
        await session.execute(
            text(f"DELETE FROM {table} WHERE account_id = :aid"), {"aid": account_id}
        )

    for portfolio_id, legacy_id in portfolios:
        # Hijos de investment_portfolios (FK a portfolio_id).
        await session.execute(
            text("DELETE FROM ledger_entries WHERE portfolio_id = :pid"),
            {"pid": portfolio_id},
        )
        # Hijos del portfolio legacy (positions/transactions apuntan a portfolios.id).
        if legacy_id:
            await session.execute(
                text("DELETE FROM positions WHERE portfolio_id = :pid"),
                {"pid": legacy_id},
            )
            await session.execute(
                text("DELETE FROM transactions WHERE portfolio_id = :pid"),
                {"pid": legacy_id},
            )
        await session.execute(
            text("DELETE FROM investment_portfolios WHERE id = :pid"),
            {"pid": portfolio_id},
        )

    # Cuenta (libera active_profile_id con el propio DELETE).
    await session.execute(
        text("DELETE FROM investment_accounts WHERE id = :aid"), {"aid": account_id}
    )


async def _delete_orphan_legacy_portfolios(session: AsyncSession) -> int:
    """Borra portfolios legacy que ya no referencia ninguna ``investment_portfolios``.

    Caso real detectado: los tests crean el portfolio legacy (tabla ``portfolios``) y su
    vínculo ``investment_portfolios.legacy_portfolio_id`` puede quedar NULL, de modo que al
    borrar la cuenta el legacy NO se arrastraba y quedaba huérfano. El criterio seguro es
    "ningún investment_portfolios lo referencia", excluyendo SIEMPRE el sembrado.
    """
    orphan_filter = (
        "p.id <> 'default-portfolio-seed' AND NOT EXISTS ("
        "  SELECT 1 FROM investment_portfolios ip WHERE ip.legacy_portfolio_id = p.id"
        ")"
    )
    await session.execute(
        text(f"DELETE FROM positions WHERE portfolio_id IN (SELECT p.id FROM portfolios p WHERE {orphan_filter})")
    )
    await session.execute(
        text(f"DELETE FROM transactions WHERE portfolio_id IN (SELECT p.id FROM portfolios p WHERE {orphan_filter})")
    )
    result = await session.execute(
        text(f"DELETE FROM portfolios p WHERE {orphan_filter}")
    )
    return int(result.rowcount or 0)


async def _orphan_investor_profiles(session: AsyncSession) -> int:
    """Borra perfiles de inversor que ya no referencia ninguna cuenta."""
    result = await session.execute(
        text(
            "DELETE FROM investor_profiles p WHERE NOT EXISTS ("
            "  SELECT 1 FROM investment_accounts a WHERE a.active_profile_id = p.id"
            ")"
        )
    )
    return int(result.rowcount or 0)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ejecuta el borrado (sin esta bandera es solo dry-run).",
    )
    args = parser.parse_args()

    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)

    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            before = (
                await session.execute(text("SELECT count(*) FROM investment_accounts"))
            ).scalar_one()
            rows = await _residual_account_ids(session)

            print(f"Cuentas totales: {before}")
            print(f"Residuales a borrar: {len(rows)}")
            print(f"Sobrevive: {DEMO_ACCOUNT_ID}")
            print("-" * 60)
            for account_id, name in rows:
                print(f"  {account_id}  {name}")

            if not args.apply:
                print("\n[DRY-RUN] Nada borrado. Repite con --apply para ejecutar.")
                return 0

            for account_id, _ in rows:
                await _delete_account_graph(session, account_id)
            orphan_legacies = await _delete_orphan_legacy_portfolios(session)
            profiles_deleted = await _orphan_investor_profiles(session)

            after = (
                await session.execute(text("SELECT count(*) FROM investment_accounts"))
            ).scalar_one()
            expected = before - len(rows)
            if after != expected:
                await session.rollback()
                print(
                    f"\nABORTADO: recuento inesperado (antes={before}, "
                    f"esperado={expected}, despues={after}). Rollback."
                )
                return 1

            await session.commit()
            print(
                f"\n[APLICADO] Cuentas: {before} -> {after}. "
                f"Portfolios legacy huerfanos borrados: {orphan_legacies}. "
                f"Perfiles huerfanos borrados: {profiles_deleted}."
            )
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
