"""Hermeticidad de los chaos tests live_a7 (fugas cruzadas a la BD compartida).

``seed_unknown_row`` persiste filas ``live_orders`` en estado ``UNKNOWN`` con
``account_id='acc-c3-test'``. Hasta ahora la única limpieza era ``cleanup_row`` dentro
del cuerpo de cada test: si un assert intermedio fallaba (o el ``try/finally`` no
cubría el tramo de asserts final), la fila quedaba viva en la BD compartida.

Eso NO se queda dentro de ``live_a7``: ``claim_unknown_batch`` es una barrida GLOBAL de
``status='UNKNOWN'`` (no acepta ``account_id`` — correcto en producción, un worker de
recuperación atiende cualquier cuenta). Así que un residuo ``c3a-*`` hacía que
``test_two_workers_claim_disjoint_unknown_batch`` (otra suite, mismo job) reclamara
filas ajenas y fallara con ``lote no cubierto: missing {'lo-conc-...'}``. La suite se
envenenaba a sí misma entre pasadas y entre suites.

Este fixture purga, al terminar cada test del paquete, las filas UNKNOWN de prueba, para
que ninguna pasada —verde o roja— deje munición para la siguiente. Construye su propia
conexión a propósito: el fixture ``factory`` vive en el módulo de test y no es visible
desde un ``conftest``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

# Cuenta de pruebas de live_a7 (ver ``seed_unknown_row`` en el módulo C3).
_TEST_ACCOUNT_ID = "acc-c3-test"
_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


def _load_root_env() -> None:
    if not _ROOT_ENV.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT_ENV, override=False)
    except ImportError:  # pragma: no cover — optional dep
        return


async def _purge_unknown_rows_now() -> None:
    """Borra las UNKNOWN de prueba (``acc-c3-test``) del paquete live_a7.

    Best-effort deliberado: una purga que falla no debe convertir un test en error.
    Solo toca el espacio de pruebas de live_a7; el resto de la tabla es de producción
    local y no se toca (no es un TRUNCATE).
    """
    _load_root_env()
    engine = None
    try:
        from bolsa_infrastructure.config import get_settings
        from bolsa_infrastructure.database.models.tables import LiveOrderRow
        from bolsa_infrastructure.database.session import create_engine, create_session_factory
        from sqlalchemy import delete

        get_settings.cache_clear()
        engine = create_engine(get_settings())
        factory = create_session_factory(engine)
        async with factory() as session:
            await session.execute(
                delete(LiveOrderRow).where(LiveOrderRow.account_id == _TEST_ACCOUNT_ID)
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — la purga nunca debe tumbar un test
        pass
    finally:
        if engine is not None:
            try:
                await engine.dispose()
            except Exception:  # noqa: BLE001
                pass


@pytest_asyncio.fixture(autouse=True)
async def _purge_unknown_rows_around_test() -> AsyncIterator[None]:
    """Borra las UNKNOWN de prueba ANTES y DESPUÉS de cada test del paquete.

    ANTES: una pasada anterior interrumpida (crash real de un subproceso, kill del runner)
    puede dejar filas ``acc-c3-test`` vivas; sin esta purga previa, ``test_c3a`` arranca
    con ``count_unknown() > 0`` y su invariante final falla. DESPUÉS: ninguna pasada
    —verde o roja— deja munición para la siguiente (self-poisoning entre suites).
    """
    await _purge_unknown_rows_now()
    yield
    await _purge_unknown_rows_now()
