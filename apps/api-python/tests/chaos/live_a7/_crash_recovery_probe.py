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
    from bolsa_application.live_order_query import (
        BrokerOrderQueryResult,
        MockLiveOrderQuery,
    )
    from bolsa_application.live_order_store import PostgresLiveOrderStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_session_factory

    from bolsa_api.background.live_order_recovery_worker import (  # type: ignore[import-untyped]
        resolve_one_unknown,
    )

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


def _build_financial_result(order: object) -> object:
    """Resultado broker real (FILLED con precio+secuencia) para el apply financiero.

    Reconstruye el llenado acreditado que materializa el puente V2.19/P2-01: el
    recovery NO inventa precio/secuencia (fail-closed H4/H6); aquí los recibe el
    driver (env), porque en el veneno C3-C/C3-D son justamente los campos que
    ``apply_candidate`` exige para dejar ``fsm_only`` y materializar dinero.
    """
    from decimal import Decimal

    from bolsa_application.live_order_query import BrokerOrderQueryResult

    seq = os.environ.get("LIVE_A7_FIN_FILL_SEQ")
    price = os.environ.get("LIVE_A7_FIN_FILL_PRICE")
    if not seq:
        raise RuntimeError("LIVE_A7_FIN_FILL_SEQ no está definido para el apply financiero")
    if not price:
        raise RuntimeError("LIVE_A7_FIN_FILL_PRICE no está definido para el apply financiero")
    qty = getattr(order, "quantity", None) or 1
    return BrokerOrderQueryResult(
        outcome="filled",
        venue_order_id=getattr(order, "venue_order_id", None),
        filled_quantity=qty,
        remaining_quantity=0,
        fill_seq=int(seq),
        fill_price=Decimal(str(price)),
    )


async def _probe_financial(*, crasher: bool) -> None:
    """Aplica un UNKNOWN-fill FINANCIERAMENTE (C3-C/C3-D) sobre PG real.

    Reusa el MISMO cable V2.19/P2-01 que el worker cablea en producción
    (``_apply_recovery_fills_financially``): ``PostgresExecutionEventStore`` +
    ``apply_execution_financial_once`` + ``ExecuteTrade`` idempotente por
    ``recovery_idempotency_key`` sobre la cuenta/cartera/cash reales.

    * ``crasher=True`` (subproceso A): tras dejar la traza durable en ``APPLYING``
      y ejecutar el ``ExecuteTrade`` (con el dinero en vuelo, sin commit), hace
      parking para que el driver haga SIGKILL — el punto "peor instante" del apply.
    * ``crasher=False`` (subproceso B): re-encuentra la misma traza (durable) y la
      re-materializa por el camino durable exacto (``apply_execution_financial_once``
      idempotente): si un proceso previo la dejó ``APPLYING``/``CAPTURED`` la completa;
      si ya está ``APPLIED`` devuelve ``already_applied`` sin tocar el dinero.
    """
    from bolsa_application.accounts import ExecuteTrade
    from bolsa_application.execution_event import (
        PostgresExecutionEventStore,
        apply_execution_financial_once,
    )
    from bolsa_application.live_order_store import PostgresLiveOrderStore
    from bolsa_application.recovery_apply import (
        build_recovery_execution_candidate,
        recovery_idempotency_key,
    )
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )
    from bolsa_infrastructure.database.session import create_session_factory

    get_settings.cache_clear()
    engine = _new_engine(get_settings())
    session_factory = create_session_factory(engine)
    sentinel = _require_sentinel()
    order_id = os.environ.get("LIVE_A7_FIN_ORDER_ID")
    if not order_id:
        raise RuntimeError("LIVE_A7_FIN_ORDER_ID no está definido para el apply financiero")

    try:
        async with session_factory() as session:
            store = PostgresLiveOrderStore(session)
            order = await store.get(order_id)
            if order is None:
                raise RuntimeError(f"live_order {order_id} no existe para el apply financiero")
            result = _build_financial_result(order)
            candidate = build_recovery_execution_candidate(order, result)
            if candidate is None:
                raise RuntimeError(f"order {order_id} no es apply_candidate (¿sin fill_seq/price?)")

            account_repo = SqlAlchemyAccountRepository(session)
            portfolio_repo = SqlAlchemyPortfolioRepository(session)
            ledger_repo = SqlAlchemyLedgerRepository(session)
            exec_store = PostgresExecutionEventStore(session)
            trade = ExecuteTrade(account_repo, portfolio_repo, ledger_repo)
            instrument = order.instrument_id
            side = order.side
            price = float(result.fill_price)  # type: ignore[union-attr]

            async def _apply(_execution: object) -> bool:
                try:
                    await trade.execute(
                        instrument_id=instrument,
                        trade_type=side,
                        quantity=float(_execution.qty),
                        price=price,
                        account_id=_execution.account_id,
                        idempotency_key=recovery_idempotency_key(
                            _execution.execution_id
                        ),
                    )
                    return True
                except Exception:  # noqa: BLE001 — no applied; no marcar APPLIED.
                    return False

            # Identidad de lease de este subproceso (single-owner): se usa como
            # `owner` de los CAS. `lease_window_seconds` desde env (default 0 → el
            # reclaim de un APPLYING huérfano procede de inmediato; el driver decide
            # según el escenario). En prod el recovery usará el lease real.
            lease_owner = os.environ.get("LIVE_A7_WORKER_ID") or "probe-worker"
            lease_secs = int(
                (os.environ.get("LIVE_A7_FIN_LEASE_SECONDS") or "0").strip() or "0"
            )

            if crasher:
                crash_after_commit = (
                    os.environ.get("LIVE_A7_FIN_CRASH_COMMITTED") == "1"
                )
                if crash_after_commit:
                    # C3-E (V2.20): crash DESPUÉS del commit FINANCIERO, ANTES del
                    # APPLIED. Pasos manuales para dejar el dinero DURABLE (commit)
                    # pero la traza aún en APPLYING en el instante del SIGKILL:
                    #   capture → grant APPLYING (commit interno) → ExecuteTrade →
                    #   session.commit() (dinero durable) → park → driver SIGKILL.
                    await exec_store.capture(candidate)
                    if not await exec_store.start_apply(
                        candidate.execution_id, owner=lease_owner
                    ):
                        raise RuntimeError("C3-E: no pude adquirir APPLYING para crash")
                    effective = await _apply(candidate)
                    if not effective:
                        raise RuntimeError("C3-E: ExecuteTrade no fue efectivo")
                    await session.commit()  # dinero durable, traza todavía APPLYING
                    _write_sentinel(sentinel, "financial-committed=1")
                    await asyncio.sleep(600)  # parking hasta el SIGKILL del driver
                else:
                    # Crash en MEDIO del apply (C3-C): ExecuteTrade en vuelo SIN commit.
                    async def _park_apply(_execution: object) -> bool:
                        effective = await _apply(_execution)
                        if not effective:
                            return False
                        _write_sentinel(sentinel, "financial-applying=1")
                        await asyncio.sleep(600)  # parking hasta el SIGKILL del driver
                        return True  # unreachable a escala de test (es matado antes)

                    await apply_execution_financial_once(
                        exec_store,
                        execution=candidate,
                        apply_finance=_park_apply,
                        owner=lease_owner,
                        lease_window_seconds=lease_secs,
                        retryable_on_ineffective=True,
                    )
                    _write_sentinel(sentinel, "financial-applying=1")
            else:
                outcome = await apply_execution_financial_once(
                    exec_store,
                    execution=candidate,
                    apply_finance=_apply,
                    owner=lease_owner,
                    lease_window_seconds=lease_secs,
                    retryable_on_ineffective=True,
                )
                row = await exec_store.get(candidate.execution_id)
                has = f"status={(row.status if row else 'missing')}"  # type: ignore[union-attr]
                attempt = (
                    (" attempt=" + str(row.attempt_count))  # type: ignore[union-attr]
                    if row
                    else ""
                )
                _write_sentinel(sentinel, f"finished={outcome} {has}{attempt}")
    except Exception as exc:  # noqa: BLE001 — informar al driver, no morir mudo
        _write_sentinel(sentinel, f"error: {exc!r}")
    finally:
        await engine.dispose()


async def _probe_cas_contest() -> None:
    """Probe de CONCURSO CAS (P1-01/#2 V2.20): single-owner APPLYING real-PG.

    Abre su propia sesión PG y ejecuta ``PostgresExecutionEventStore.start_apply``
    sobre UN ``execution_id`` CAPTURED compartido con otro worker, tras esperar por
    una señal "go" (barrer de arranque común). Escribe ``won=1`` si GANÓ la
    adquisición exclusiva (ÚNICO dueño de APPLYING) o ``won=0`` si la perdió.
    Dos procesos con esto demuestran winner=1/loser=0 real (tu test #2):
    ``start_apply`` es CAS atómico CAPTURED/RETRY/FAILED→APPLYING (sin auto-reclaim),
    así que el que no gane ve el estado ya en APPLYING → 0 filas → False.
    """
    import time as _time

    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_session_factory

    get_settings.cache_clear()
    engine = _new_engine(get_settings())
    session_factory = create_session_factory(engine)
    sentinel = _require_sentinel()
    worker_id = os.environ.get("LIVE_A7_WORKER_ID") or "cas-contest"
    execution_id = os.environ.get("LIVE_A7_CAS_EXECUTION_ID") or ""
    if not execution_id:
        raise RuntimeError("LIVE_A7_CAS_EXECUTION_ID no está definido para el concurso CAS")

    try:
        # Barrer: espera a la señal "go" del driver (fichero en su tmp_path).
        # Así ambos workers arrancan el CAS en la misma ventana de tiempo.
        go_file = os.environ.get("LIVE_A7_CAS_GO_FILE") or ""
        deadline = _time.monotonic() + 40.0
        while go_file and _time.monotonic() < deadline:
            try:
                if os.path.exists(go_file):
                    break
            except OSError:
                pass
            await asyncio.sleep(0.01)
        async with session_factory() as session:
            store = PostgresExecutionEventStore(session)
            won = await store.start_apply(execution_id, owner=worker_id)
            _write_sentinel(sentinel, f"won={1 if won else 0}")
    except Exception as exc:  # noqa: BLE001 — informar al driver, no morir mudo
        _write_sentinel(sentinel, f"error: {exc!r}")
    finally:
        await engine.dispose()


async def _main() -> int:
    mode = os.environ.get("LIVE_A7_PROBE_MODE") or "crasher"
    if mode == "reader":
        await _probe_reader()
    elif mode == "crasher-financial":
        await _probe_financial(crasher=True)
    elif mode == "reader-financial":
        await _probe_financial(crasher=False)
    elif mode == "cas-contest":
        await _probe_cas_contest()
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
