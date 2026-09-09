"""Probe de crash-injection C3 (V2.18/A7 Iter-1) — proceso real, sin tocar el núcleo.

Este módulo NO prueba nada por sí mismo: es el **harness de proceso** que el test
`test_c3_crash_injection_scheduler_worker.py` lanza como subproceso Python real
(``sys.executable <este fichero>``) y después mata deliberadamente (SIGKILL /
TerminateProcess en Windows).

Reusa el worker real de recovery en el punto de máximo riesgo sin modificar su
implementación: `resolve_one_unknown` de
`apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py` sobre un
`PostgresLiveOrderStore` de verdad en la BD aislada. Solo se inyecta la resolución del
query (un doble que devuelve un resultado de broker) y el *momento* del crash.

Dos modos (seleccionados por env ``LIVE_A7_PROBE_MODE``):

* ``crasher`` — reclama una o varias filas UNKNOWN (``claim_unknown_batch`` deja el
  row-lock en vivo), escribe el sentinel y se queda **parking SIN commit**. Es el punto
  en el que un worker puede morir con el claim/open-tx → el driver lo SIGKILLea al ver
  el sentinel: la tx cae en ROLLBACK y la fila vuelve a estar reclamable sin doble
  efecto.
* ``reader`` — reprocesa las filas UNKNOWN con un query que reporta ``filled`` por la
  cantidad total de la orden: es el *segundo worker* que tras el crash recupera la
  orden y la materializa **exactamente una vez** en la máquina FSM (nunca re-POST;
  ``financial_apply_count`` intacto = 0, sin dinero inventado).

Señalización al driver: archivo sentinel (ruta en ``LIVE_A7_SENTINEL``). El candado de
sincronización real lo da el row-lock de PostgreSQL (FOR UPDATE), NO un sleep elegido
arbitrariamente. Ante un error el probe escribe ``error: …`` en el sentinel para que el
driver falle con mensaje claro en vez de agotar un timeout mudo.
"""

from __future__ import annotations

import asyncio
import os
import sys


def _apply_loop_policy() -> None:
    # psycopg async no soporta ProactorEventLoop en Windows (convención del repo).
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_env() -> None:
    from pathlib import Path

    # Local: <raíz>/.env. Subimos desde el fichero hasta la raíz del repo (guard por
    # `.github` + `package.json`); CI ya inyecta DATABASE_URL por env del job.
    if os.environ.get("DATABASE_URL"):
        return
    d = Path(__file__).resolve().parent
    root: Path | None = None
    for _ in range(0, 10):
        if (d / ".github").is_dir() and (d / "package.json").is_file():
            root = d
            break
        parent = d.parent
        if parent == d:
            break
        d = parent
    if root is None:
        return
    env_path = root / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover — dep opcional
        return
    load_dotenv(env_path, override=False)


def _write_sentinel(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _new_engine(settings: object):
    from bolsa_infrastructure.database.session import create_engine

    return create_engine(settings)  # type: ignore[arg-type]


async def _probe_crash_hold() -> None:
    """Reclama UNKNOWN y hace parking con el row-lock (FOR UPDATE) abierto, SIN commit.

    Es el estado "peor instante": la fila está reclamada (lease fresco en la tx del
    proceso) pero aún no hay resolución persistida. Al matar este proceso, la BD hace
    ROLLBACK de todo (lease y claim desaparecen); el segundo worker puede reclamar la
    orden y resolverla exactamente una vez.
    """
    from bolsa_application.live_order_store import PostgresLiveOrderStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_session_factory

    get_settings.cache_clear()
    engine = _new_engine(get_settings())
    session_factory = create_session_factory(engine)
    sentinel = _require_sentinel()
    worker_id = os.environ.get("LIVE_A7_WORKER_ID") or "live-recovery-crasher"

    try:
        async with session_factory() as session:
            try:
                store = PostgresLiveOrderStore(session)
                rows = await store.claim_unknown_batch(
                    limit=50,
                    worker_id=worker_id,
                    stale_after_seconds=120,
                )
                if not rows:
                    # Nada que reclamar en el mismo instante: no hay crash point que
                    # matar. El driver verá `claimed=0` y no matará el proceso.
                    _write_sentinel(sentinel, "claimed=0")
                    return
                # Row-lock (FOR UPDATE) en vivo, SIN commit. Señaliza al driver que
                # puede matarnos aquí y queda parking SIN commit: al matar el proceso
                # este claim+lease caen en ROLLBACK (la fila queda reclamable).
                _write_sentinel(
                    sentinel,
                    f"claimed={','.join(r.order_id for r in rows)}",
                )
                await asyncio.sleep(600)  # solo parking; el candado lo pone PG
            except Exception as exc:  # noqa: BLE001 — informar al driver, no morir mudo
                _write_sentinel(sentinel, f"error: {exc!r}")
    finally:
        await engine.dispose()


async def _probe_reader() -> None:
    """Segundo worker: reelabora UNKNOWN como ``filled`` y persiste una sola vez."""
    from bolsa_api.background.live_order_recovery_worker import (  # type: ignore[import-untyped]
        resolve_one_unknown,
    )
    from bolsa_application.live_order_query import (
        BrokerOrderQueryResult,
        MockLiveOrderQuery,
    )
    from bolsa_application.live_order_store import PostgresLiveOrderStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_session_factory

    get_settings.cache_clear()
    engine = _new_engine(get_settings())
    session_factory = create_session_factory(engine)
    sentinel = _require_sentinel()
    worker_id = os.environ.get("LIVE_A7_WORKER_ID") or "live-recovery-reader"

    try:
        async with session_factory() as session:
            store = PostgresLiveOrderStore(session)
            rows = await store.claim_unknown_batch(
                limit=50,
                worker_id=worker_id,
                stale_after_seconds=120,
            )
            resolved = 0
            for order in rows:
                query = MockLiveOrderQuery(
                    BrokerOrderQueryResult(
                        outcome="filled",
                        venue_order_id=order.venue_order_id,
                        filled_quantity=order.quantity,
                        remaining_quantity=0,
                    )
                )
                status = await resolve_one_unknown(
                    order,
                    query,
                    store=store,
                    account_id=order.account_id or "live",
                )
                if status == "resolved":
                    resolved += 1
            _write_sentinel(
                sentinel,
                f"drained={len(rows)} resolved={resolved}",
            )
    except Exception as exc:  # noqa: BLE001 — informar al driver, no morir mudo
        _write_sentinel(sentinel, f"error: {exc!r}")
    finally:
        await engine.dispose()


def _require_sentinel() -> str:
    sentinel = os.environ.get("LIVE_A7_SENTINEL")
    if not sentinel:
        raise RuntimeError("LIVE_A7_SENTINEL no está definido para el probe")
    return sentinel


async def _main() -> int:
    mode = os.environ.get("LIVE_A7_PROBE_MODE") or "crasher"
    if mode == "reader":
        await _probe_reader()
    else:
        await _probe_crash_hold()
    return 0


def run() -> None:
    _apply_loop_policy()
    _load_env()
    loop: asyncio.AbstractEventLoop
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        with asyncio.Runner(loop_factory=lambda: loop) as runner:
            runner.run(_main())
    except Exception as exc:  # noqa: BLE001 — sentinel error si algo explota al arrancar
        sentinel = os.environ.get("LIVE_A7_SENTINEL")
        if sentinel:
            _write_sentinel(sentinel, f"error: {exc!r}")
        raise


if __name__ == "__main__":
    run()
