#!/usr/bin/env python3
"""OPS · Acuña la cuenta de la ventana PAPER con el **id FIJO** de la fuente única.

Qué resuelve: ADR-046 exige que la cuenta de la ventana sea **fija** (``WINDOW_CONFIG.account``
en ``scripts/lib/window-forward.mjs``, replicado en ``.env`` como ``PAPER_D_ACCOUNT_ID``). Pero
``SqlAlchemyAccountRepository.create_simulated_account`` acuña su id con ``new_id()`` y no acepta
un id explícito, así que no existe forma de (re)sembrar ese id desde la API del repositorio.

Este script lo hace sin duplicar la lógica de alta: crea la cuenta por el camino canónico (con
su cartera legacy, su ``investment_portfolios``, su asiento de depósito y su ``settings_json``
ya serializado) y **re-etiqueta** el id dentro de la MISMA transacción, reparentando de forma
genérica TODAS las FK que apunten a ``investment_accounts`` (leídas de ``information_schema``,
no de una lista que pueda quedar corta).

Uso (desde la raíz del repo)::

    uv run --no-sync python scripts/ops/seed_window_account_fixed_id.py            # dry-run
    uv run --no-sync python scripts/ops/seed_window_account_fixed_id.py --apply

Salidas: ``0`` ya existe (idempotente) o creada con ``--apply`` · ``2`` sin PostgreSQL
(se DECLARA, no se fuerza) · ``1`` uso incorrecto.

NO toca el motor, el gobernador, umbrales ni migraciones; NO siembra el par A/B (eso es
``apps/api-python/scripts/ops_seed_window_pair.py``). Vive en ``scripts/``, que NO participa del
freeze de la ventana.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOTENV = _REPO_ROOT / ".env"
_WINDOW_FORWARD_MJS = _REPO_ROOT / "scripts" / "lib" / "window-forward.mjs"
_ACCOUNT_NAME = "PAPER-VENTANA-a9c515"


def _window_account_id() -> str:
    """Id fijo declarado en ``WINDOW_CONFIG`` del runner JS (misma fuente que el operador)."""
    import re

    source = _WINDOW_FORWARD_MJS.read_text(encoding="utf-8")
    start = source.find("export const WINDOW_CONFIG")
    if start < 0:
        raise RuntimeError("window-forward.mjs no declara WINDOW_CONFIG")
    match = re.search(r"\baccount:\s*'([^']+)'", source[start:])
    if match is None:
        raise RuntimeError("WINDOW_CONFIG no declara `account`")
    return match.group(1).strip()


async def _fk_columns_to_accounts(session) -> list[tuple[str, str]]:
    """``(tabla, columna)`` de TODAS las FK que apuntan a ``investment_accounts``."""
    from sqlalchemy import text

    rows = (
        await session.execute(
            text(
                """
                SELECT kcu.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                 AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND ccu.table_name = 'investment_accounts'
                """
            )
        )
    ).all()
    return [(str(r[0]), str(r[1])) for r in rows]


async def _account_columns(session) -> list[str]:
    from sqlalchemy import text

    rows = (
        await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'investment_accounts' ORDER BY ordinal_position"
            )
        )
    ).scalars()
    return [str(c) for c in rows]


async def _relabel_account_id(session, *, temp_id: str, fixed_id: str) -> list[str]:
    """Re-etiqueta el id de la cuenta recién creada y reparenta sus hijas. Devuelve el detalle."""
    from sqlalchemy import text

    columns = await _account_columns(session)
    quoted = ", ".join(f'"{c}"' for c in columns)
    selected = ", ".join(":fixed" if c == "id" else f'"{c}"' for c in columns)
    await session.execute(
        text(
            f"INSERT INTO investment_accounts ({quoted}) "  # noqa: S608 — columnas de information_schema
            f"SELECT {selected} FROM investment_accounts WHERE id = :temp"
        ),
        {"fixed": fixed_id, "temp": temp_id},
    )

    reparented: list[str] = []
    for table, column in await _fk_columns_to_accounts(session):
        if table == "investment_accounts":
            continue
        result = await session.execute(
            text(
                f'UPDATE "{table}" SET "{column}" = :fixed '  # noqa: S608 — nombres de information_schema
                f'WHERE "{column}" = :temp'
            ),
            {"fixed": fixed_id, "temp": temp_id},
        )
        if result.rowcount:
            reparented.append(f"{table}.{column}={result.rowcount}")

    await session.execute(
        text("DELETE FROM investment_accounts WHERE id = :temp"), {"temp": temp_id}
    )
    return reparented


async def _run(apply: bool) -> int:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from sqlalchemy import text

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    fixed_id = _window_account_id()
    print(f"# cuenta de la ventana (fuente única): {fixed_id}")

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            existing = (
                await session.execute(
                    text("SELECT name FROM investment_accounts WHERE id = :id"), {"id": fixed_id}
                )
            ).first()
            if existing is not None:
                print(
                    f"# ya existe: id={fixed_id} name={existing[0]!r} (idempotente, nada que hacer)"
                )
                return 0

            if not apply:
                print("# dry-run: la cuenta NO existe y se acuñaría con el id fijo")
                print("# añade --apply para crearla")
                return 0

            scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=_ACCOUNT_NAME, initial_deposit=100_000.0
            )
            temp_id = str(scope.account.id)
            reparented = await _relabel_account_id(session, temp_id=temp_id, fixed_id=fixed_id)
            await session.commit()

            row = (
                await session.execute(
                    text("SELECT id, name, type, status FROM investment_accounts WHERE id = :id"),
                    {"id": fixed_id},
                )
            ).first()
            print(f"# creada: {tuple(str(v) for v in row)}")
            print(f"# id temporal re-etiquetado: {temp_id} -> {fixed_id}")
            print(f"# hijas reparentadas: {', '.join(reparented) if reparented else '(ninguna)'}")
            print("")
            print("# siguiente paso (par A/B de la ventana):")
            print(
                "#   uv run --no-sync python apps/api-python/scripts/ops_seed_window_pair.py "
                f"--account-id {fixed_id} --version-a v283-window-a --version-b v283-window-b"
            )
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="crea la cuenta (por defecto: dry-run, no escribe)"
    )
    args = parser.parse_args(argv)

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        return asyncio.run(_run(bool(args.apply)))
    except Exception as error:  # noqa: BLE001 — sin PostgreSQL no hay siembra: se DECLARA.
        print(f"# BLOQUEADO: no se pudo acuñar la cuenta ({type(error).__name__}: {error})")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
