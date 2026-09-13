"""Fixtures y utilidades compartidas de los tests de la API.

Incluye el helper de limpieza de cuentas creadas por tests de integración.

Motivo: varias suites crean cuentas reales vía HTTP/Prisma y no las borraban. El residuo
se acumulaba en la BD (se llegaron a medir 89 cuentas basura), aparecía mezclado con datos
reales en la UI (todas cuelgan del owner ``app``) y además rompía el worker de custodia:
una cuenta sin cartera legacy abortaba el job completo.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_root_env() -> None:
    """Carga el ``.env`` de la RAÍZ del repo en ``os.environ``.

    ``Settings`` usa ``env_file=".env"``, una ruta RELATIVA al cwd. Al ejecutar pytest desde
    ``apps/api-python`` ese ``.env`` no se encuentra y la BD falla con
    ``fe_sendauth: no password supplied``. Cargarlo aquí (una vez, en import del conftest)
    hace que toda la suite funcione independientemente del cwd desde el que se invoque.
    """
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


_load_root_env()

# La ÚNICA cuenta que los tests NUNCA deben borrar (la siembra el bootstrap de la app).
DEMO_ACCOUNT_ID = "default-account-seed"

# Tablas con FK a ``investment_accounts`` que hay que vaciar por cuenta (hijas primero).
_ACCOUNT_CHILD_TABLES = (
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


async def purge_accounts(session_factory, account_ids: list[str]) -> None:
    """Borra el grafo completo de las cuentas indicadas, respetando el orden de FKs.

    Recibe el ``async_sessionmaker`` de la app (``app.state.session_factory``) y abre su
    propia sesión, para poder invocarse desde un ``finally`` sin depender de sesiones
    abiertas por el test.

    Es el teardown que deben invocar las suites que crean cuentas. Borra hijos
    (``ledger_entries``, ``mandate_tenures``, ``position_states``...), luego los
    ``investment_portfolios`` y sus portfolios legacy asociados, y por último la cuenta.

    Salvaguardas:
    - Ignora explícitamente ``default-account-seed``: un test nunca debe borrar la demo.
    - Ignora IDs vacíos/duplicados.
    - Además limpia los portfolios legacy que queden huérfanos (los tests los crean en la
      tabla ``portfolios`` y el vínculo puede quedar NULL, de modo que no se arrastran solos).
    """
    from sqlalchemy import text

    targets = [aid for aid in dict.fromkeys(account_ids) if aid and aid != DEMO_ACCOUNT_ID]
    if not targets:
        return

    async with session_factory() as session:
        for account_id in targets:
            portfolio_rows = await session.execute(
                text(
                    "SELECT id, legacy_portfolio_id FROM investment_portfolios "
                    "WHERE account_id = :aid"
                ),
                {"aid": account_id},
            )
            portfolios = [(str(r[0]), r[1]) for r in portfolio_rows]

            for table in _ACCOUNT_CHILD_TABLES:
                await session.execute(
                    text(f"DELETE FROM {table} WHERE account_id = :aid"),
                    {"aid": account_id},
                )

            for portfolio_id, legacy_id in portfolios:
                await session.execute(
                    text("DELETE FROM ledger_entries WHERE portfolio_id = :pid"),
                    {"pid": portfolio_id},
                )
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

            await session.execute(
                text("DELETE FROM investment_accounts WHERE id = :aid"),
                {"aid": account_id},
            )

        # Portfolios legacy que ya no referencia ningún investment_portfolios (huérfanos).
        orphan_filter = (
            "p.id <> 'default-portfolio-seed' AND NOT EXISTS ("
            "  SELECT 1 FROM investment_portfolios ip WHERE ip.legacy_portfolio_id = p.id"
            ")"
        )
        await session.execute(
            text(
                "DELETE FROM positions WHERE portfolio_id IN "
                f"(SELECT p.id FROM portfolios p WHERE {orphan_filter})"
            )
        )
        await session.execute(
            text(
                "DELETE FROM transactions WHERE portfolio_id IN "
                f"(SELECT p.id FROM portfolios p WHERE {orphan_filter})"
            )
        )
        await session.execute(text(f"DELETE FROM portfolios p WHERE {orphan_filter}"))

        # Perfiles de inversor que quedaron sin cuenta que los referencie.
        await session.execute(
            text(
                "DELETE FROM investor_profiles p WHERE NOT EXISTS ("
                "  SELECT 1 FROM investment_accounts a WHERE a.active_profile_id = p.id"
                ")"
            )
        )
        await session.commit()


async def purge_all_residuals() -> None:
    """Borra TODO residuo de tests: cuentas, portfolios, instrumentos sintéticos y perfiles.

    Es la red de seguridad global (fixture autouse de sesión). No depende de que cada suite
    recuerde limpiar: al terminar la sesión de pytest la BD vuelve al estado sembrado.

    Sobrevive únicamente lo que siembra el bootstrap/seed:
    - ``default-account-seed`` y su ``default-portfolio-seed``.
    - Los instrumentos del catálogo IBEX (los que tienen ``yahoo_symbol`` real, ``*.MC``).

    Los instrumentos sintéticos de tests se reconocen por su id ``inst-*`` (familias
    ``a11``, ``a13``, ``a14``, ``a9proc``, ``g190``...) y por símbolos ``INV*``/``dbg-*``.
    """
    from sqlalchemy import text

    _load_root_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            residual_accounts = (
                (
                    await session.execute(
                        text(
                            "SELECT id FROM investment_accounts WHERE id <> :demo"
                        ),
                        {"demo": DEMO_ACCOUNT_ID},
                    )
                )
                .scalars()
                .all()
            )
            await session.commit()

        if residual_accounts:
            await purge_accounts(factory, [str(a) for a in residual_accounts])

        async with factory() as session:
            # Instrumentos sintéticos + sus barras.
            synthetic = "(id LIKE 'inst-%' OR symbol LIKE 'INV%' OR id LIKE 'dbg-%')"
            await session.execute(
                text(
                    "DELETE FROM ohlcv_bars WHERE instrument_id IN "
                    f"(SELECT id FROM instruments WHERE {synthetic})"
                )
            )
            await session.execute(text(f"DELETE FROM instruments WHERE {synthetic}"))
            await session.commit()
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_residuals_after_session() -> Iterator[None]:
    """Red de seguridad global: limpia los residuos de TODA la sesión de tests.

    Varias suites crean cuentas/instrumentos reales y no los borran (se llegaron a medir 89
    cuentas y 127 instrumentos sintéticos acumulados). En vez de confiar en que cada suite
    recuerde limpiar, al terminar la sesión se purga todo lo que no sea la semilla.

    Se ejecuta también si algún test falla, que es justo cuando más residuo se deja.
    """
    yield
    try:
        asyncio.run(purge_all_residuals())
    except Exception as exc:  # nunca debe tumbar la sesión de tests por el teardown
        print(f"[conftest] aviso: limpieza final de residuos falló: {exc}")
