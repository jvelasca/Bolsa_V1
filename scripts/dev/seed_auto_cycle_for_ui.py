#!/usr/bin/env python3
"""Seed dev: siembra UN ciclo AUTO durable REAL para abrirlo en el navegador.

Por qué existe
--------------
En local el worker del motor AUTO puede estar caído: ``GET /api/auto/operational-monitor``
devuelve 0 ciclos y ``/auto/operar`` declara «Sin operaciones en la ventana». Este script
siembra UN ciclo durable escribiendo en los MISMOS stores/modulos del backend (importándolos,
sin copiar su lógica):

* reserva durable — ``bolsa_application.reservation_store.PostgresReservationStore.save_claim``
  con un ``bolsa_analytics.cognitive.portfolio_reservation.PortfolioReservation``.
* dos fills — ``bolsa_application.sim_durable_store.PostgresSimFillFinanceContextStore.save``
  (compra 100.0 / venta 110.0 con ``execution_id`` determinista ``-buy``/``-sell``).
* el spine — ``decision_journal_entries`` vía ``SqlAlchemyJournalRepository``:
  ``auto_entry_decision`` + ``build_reservation_claim_entry`` +
  ``build_reservation_reconciliation_entry`` (``bolsa_application.auto_operational_audit``).
* el TOP de Finalistas — por HTTP ``PUT /api/instruments/{uuid}/strategy-top`` (NUNCA por
  tabla directa), con un ``strategyDefinitionId`` REAL sacado de ``GET /api/strategies``.

El patrón está calcado de ``apps/api-python/tests/test_auto_operational_monitor_pg.py``
(helpers ``_reservation``/``_seed_fill``/``_seed_journal`` y fixture que carga ``.env`` +
``ensure_migrated``).

Uso (raíz del repo)::

    uv run --no-sync python scripts/dev/seed_auto_cycle_for_ui.py --symbol ACS
    uv run --no-sync python scripts/dev/seed_auto_cycle_for_ui.py --symbol ACS --cleanup

Requisitos: ``.env`` con ``DATABASE_URL``, PostgreSQL migrado y la API FastAPI levantada en
``--api-base`` (default ``http://127.0.0.1:8000``). Si algo falta el script FALLA RUIDOSAMENTE
(nunca finge): declara ``.env``/PG/API ausentes y sale con código ≠ 0.

Al terminar imprime el ``cycle_id`` y la ruta ``/auto/operar/operacion/<cycleId>``. El script
es idempotente: el ``cycle_id`` es determinista por ``(account_id, symbol)`` y, antes de
sembrar, barre cualquier residuo previo de ESE ciclo.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for _p in (
    ROOT / "packages" / "py" / "domain" / "src",
    ROOT / "packages" / "py" / "market" / "src",
    ROOT / "packages" / "py" / "infrastructure" / "src",
    ROOT / "packages" / "py" / "application" / "src",
    ROOT / "packages" / "py" / "analytics" / "src",
    ROOT / "packages" / "py" / "ai" / "src",
):
    if str(_p) not in sys.path:
        sys.path[:0] = [str(_p)]

# psycopg async no soporta ProactorEventLoop (patrón del repo).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ENV_PATH = ROOT / ".env"
DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_ACCOUNT_ID = "default-account-seed"
DEFAULT_PRESET_KEY = "sma_crossover"
#: El motor por defecto de ``read_operational_monitor`` (el header ``lastDecisionAt`` va scoped).
ENGINE_ID = "auto-sim"
#: Namespace de los ciclos sembrados por este script (ancla de la limpieza).
CYCLE_PREFIX = "cyc-ui-"
_HTTP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


# ── HTTP mínimo (sin dependencias) ────────────────────────────────────────────────


def _http_json(
    method: str,
    path: str,
    *,
    api_base: str,
    body: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> Any:
    url = f"{api_base.rstrip('/')}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers=_HTTP_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API no alcanzable en {api_base}: {exc}") from exc
    return json.loads(raw) if raw else None


def _require_env() -> None:
    if not ENV_PATH.exists():
        raise RuntimeError(
            f"falta {ENV_PATH} (DATABASE_URL). Copia .env.example y configúralo."
        )
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - entorno sin deps del backend.
        raise RuntimeError("python-dotenv no instalado: usa el entorno del backend (uv).") from exc
    load_dotenv(ENV_PATH, override=False)


def _require_api(api_base: str) -> None:
    _http_json("GET", "/api/health", api_base=api_base, timeout=10.0)


def _resolve_instrument(
    api_base: str, *, symbol: str | None, instrument_id: str | None
) -> tuple[str, str]:
    """Devuelve ``(uuid, symbol)`` del instrumento real del catálogo."""
    payload = _http_json("GET", "/api/instruments", api_base=api_base)
    rows = payload.get("data") or []
    if instrument_id:
        row = next((r for r in rows if str(r.get("id")) == instrument_id), None)
        if row is None:
            raise RuntimeError(
                f"instrument-id {instrument_id!r} no está en el catálogo /api/instruments"
            )
        return str(row["id"]), str(row["symbol"])
    if symbol:
        upper = symbol.strip().upper()
        row = next(
            (r for r in rows if str(r.get("symbol", "")).upper() == upper), None
        )
        if row is None:
            raise RuntimeError(
                f"símbolo {symbol!r} no está en el catálogo /api/instruments"
            )
        return str(row["id"]), str(row["symbol"])
    if not rows:
        raise RuntimeError("el catálogo /api/instruments está vacío")
    row = rows[0]
    print(
        f"· (sin --symbol/--instrument-id) uso el primer instrumento: "
        f"{row['symbol']} · {row['id']}"
    )
    return str(row["id"]), str(row["symbol"])


def _resolve_strategy(api_base: str) -> tuple[str, str, str]:
    """Devuelve ``(strategyDefinitionId, token, label)`` de una estrategia REAL.

    ``token`` es el ``presetKey`` (o el id): es el sello que casa con el ``strategyType`` del
    slot del TOP (emparejamiento textual que exige la UI de la operación).
    """
    payload = _http_json("GET", "/api/strategies", api_base=api_base)
    rows = payload.get("data") or []
    chosen = next((r for r in rows if str(r.get("presetKey") or "").strip()), None)
    if chosen is None and rows:
        chosen = rows[0]
    if chosen is None:
        print("· no hay estrategias guardadas: creo una desde preset sma_crossover")
        created = _http_json(
            "POST",
            "/api/strategies/from-preset",
            api_base=api_base,
            body={
                "name": "Seed UI · Cruce SMA 20/50",
                "presetKey": DEFAULT_PRESET_KEY,
                "timeframe": "1d",
            },
        )
        chosen = created["data"]
    definition_id = str(chosen["id"])
    token = str(chosen.get("presetKey") or "").strip() or definition_id
    label = str(chosen.get("name") or "Estrategia #1")
    return definition_id, token, label


def _put_strategy_top(
    api_base: str,
    *,
    instrument_uuid: str,
    symbol: str,
    definition_id: str,
    strategy_type: str,
    label: str,
) -> None:
    body = {
        "instrumentId": instrument_uuid,
        "symbol": symbol,
        "timeframe": "1d",
        "status": "semifinal",
        "evidenceLevel": "in_sample_only",
        "slots": [
            {
                "rank": 1,
                "label": label,
                "strategyType": strategy_type,
                "strategyDefinitionId": definition_id,
                "stars": 3,
                "score": 70,
                "source": "coach",
            }
        ],
        "coachFacts": {
            "recommendations": [
                {
                    "rank": 1,
                    "reasons": [
                        "Cruce SMA 20/50 alcista con la tendencia de fondo confirmada",
                        "Estructura de riesgo definida (stop bajo el último soporte)",
                    ],
                }
            ]
        },
    }
    _http_json(
        "PUT",
        f"/api/instruments/{urllib.parse.quote(instrument_uuid)}/strategy-top",
        api_base=api_base,
        body=body,
    )


# ── PostgreSQL: engine/sesión (patrón del test PG del monitor) ─────────────────────


async def _open_factory() -> tuple[Any, Any]:
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import (
        create_engine,
        create_session_factory,
    )

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    return engine, factory


# ── Helpers de sembrado (calcados del test PG del monitor) ─────────────────────────


def _reservation(
    *,
    reservation_id: str,
    cycle_id: str,
    account_id: str,
    instrument: str,
    strategy_version_id: str,
) -> Any:
    from bolsa_analytics.cognitive.portfolio_reservation import PortfolioReservation

    return PortfolioReservation(
        reservation_id=reservation_id,
        account_id=account_id,
        instrument_id=instrument,
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0,
        reserved_risk=250.0,
        strategy_version_id=strategy_version_id,
        created_at=datetime.now(UTC).isoformat(),
        cycle_id=cycle_id,
        status="OPEN",
    )


async def _seed_fill(
    session: Any,
    *,
    account_id: str,
    cycle_id: str,
    instrument: str,
    strategy_version_id: str,
    side: str,
    price: float,
    reference_mid: float,
) -> None:
    from bolsa_application.sim_durable_store import (
        PostgresSimFillFinanceContextStore,
        SimFillFinanceContext,
    )

    store = PostgresSimFillFinanceContextStore(session, autocommit=False)
    await store.save(
        SimFillFinanceContext(
            # ``execution_id`` determinista: el store sella su propio ``created_at``, así que el
            # orden FIFO del ciclo queda fijado por ``(created_at, execution_id)``.
            execution_id=f"EX-{cycle_id}-{side}",
            instrument_id=instrument,
            side=side,
            quantity=Decimal("10"),
            price=Decimal(str(price)),
            reference_mid=Decimal(str(reference_mid)),
            account_id=account_id,
            strategy_version_id=strategy_version_id,
            cycle_id=cycle_id,
        )
    )


async def _seed_journal(
    session: Any,
    *,
    account_id: str,
    cycle_id: str,
    instrument: str,
    strategy_version_id: str,
    reservation_id: str,
) -> None:
    from bolsa_application.auto_cycle_journal import cycle_decision_id
    from bolsa_application.auto_operational_audit import (
        REASON_GRACE_WINDOW_KEEP,
        RECONCILIATION_KEEP,
        build_reservation_claim_entry,
        build_reservation_reconciliation_entry,
    )
    from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)
    decision_id = cycle_decision_id(cycle_id) or f"dec-{uuid.uuid4().hex[:12]}"
    as_of = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    await repository.append(
        DecisionJournalEntryRecord(
            id=f"JNL-seed-{uuid.uuid4().hex[:12]}",
            decision_id=decision_id,
            event_type="auto_entry_decision",
            actor="auto-sim-seed",
            created_at=as_of,
            session_id=None,
            account_id=account_id,
            instrument_id=instrument,
            payload={
                "event": "auto_entry_decision",
                "cycleId": cycle_id,
                "instrumentId": instrument,
                "strategyVersion": strategy_version_id,
                "rank": 1,
                "opportunityScore": 0.9,
                "engineId": ENGINE_ID,
            },
        )
    )
    claim = build_reservation_claim_entry(
        reservation_id=reservation_id,
        cycle_id=cycle_id,
        claimed=True,
        actor="auto-sim-seed",
        session_id="sess-seed",
        as_of=as_of,
        account_id=account_id,
        instrument_id=instrument,
    )
    assert claim is not None
    await repository.append(claim)
    reconciliation = build_reservation_reconciliation_entry(
        reservation_id=reservation_id,
        cycle_id=cycle_id,
        decision=RECONCILIATION_KEEP,
        reason=REASON_GRACE_WINDOW_KEEP,
        mine=False,
        aged=False,
        grace_window_seconds=61.0,
        actor="auto-sim-seed",
        session_id="sess-seed",
        as_of=as_of,
        account_id=account_id,
        instrument_id=instrument,
    )
    assert reconciliation is not None
    await repository.append(reconciliation)
    await session.commit()


async def _wipe_cycle(session: Any, *, account_id: str, cycle_id: str) -> None:
    """Borra el rastro durable de UN ciclo sembrado (idempotencia / limpieza)."""
    from sqlalchemy import text

    from bolsa_application.auto_cycle_journal import cycle_decision_id

    params = {"account_id": account_id, "cycle_id": cycle_id}
    await session.execute(
        text(
            "DELETE FROM sim_fill_finance_context "
            "WHERE account_id = :account_id AND cycle_id = :cycle_id"
        ),
        params,
    )
    await session.execute(
        text(
            "DELETE FROM portfolio_reservations "
            "WHERE account_id = :account_id AND cycle_id = :cycle_id"
        ),
        params,
    )
    decision_id = cycle_decision_id(cycle_id)
    if decision_id:
        await session.execute(
            text(
                "DELETE FROM decision_journal_entries "
                "WHERE account_id = :account_id AND decision_id = :decision_id"
            ),
            {"account_id": account_id, "decision_id": decision_id},
        )


def _cycle_id_for(account_id: str, symbol: str) -> str:
    """``cycle_id`` determinista por ``(cuenta, símbolo)`` ⇒ reejecutar es idempotente."""
    digest = hashlib.sha256(f"{account_id}:{symbol}".encode()).hexdigest()[:12]
    return f"{CYCLE_PREFIX}{digest}"


async def _seed_db(
    *,
    account_id: str,
    symbol: str,
    strategy_version_id: str,
    cycle_id: str,
) -> str:
    from bolsa_application.reservation_store import PostgresReservationStore

    reservation_id = f"RES-{cycle_id}"
    engine, factory = await _open_factory()
    try:
        # Barrido previo del MISMO ciclo: reejecutar no duplica (journal append-only incluido).
        async with factory() as session:
            await _wipe_cycle(session, account_id=account_id, cycle_id=cycle_id)
            await session.commit()

        async with factory() as session:
            reservations = PostgresReservationStore(session, autocommit=True)
            claimed = await reservations.save_claim(
                _reservation(
                    reservation_id=reservation_id,
                    cycle_id=cycle_id,
                    account_id=account_id,
                    instrument=symbol,
                    strategy_version_id=strategy_version_id,
                )
            )
            if not claimed:
                raise RuntimeError(
                    "save_claim devolvió False: había un compromiso vivo con la misma "
                    "identidad (residuo no barrido)."
                )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=symbol,
                strategy_version_id=strategy_version_id,
                side="buy",
                price=100.0,
                reference_mid=99.9,
            )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=symbol,
                strategy_version_id=strategy_version_id,
                side="sell",
                price=110.0,
                reference_mid=110.1,
            )
            await session.commit()
            await _seed_journal(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=symbol,
                strategy_version_id=strategy_version_id,
                reservation_id=reservation_id,
            )
    finally:
        await engine.dispose()
    return reservation_id


async def _cleanup_db(*, account_id: str) -> tuple[list[str], list[str]]:
    """Borra los ciclos sembrados (``cyc-ui-*``) de la cuenta. Devuelve (ciclos, símbolos)."""
    from sqlalchemy import text

    engine, factory = await _open_factory()
    cycles: list[str] = []
    symbols: list[str] = []
    try:
        async with factory() as session:
            cycles = list(
                (
                    await session.execute(
                        text(
                            "SELECT DISTINCT cycle_id FROM portfolio_reservations "
                            "WHERE account_id = :account_id AND cycle_id LIKE :prefix"
                        ),
                        {"account_id": account_id, "prefix": f"{CYCLE_PREFIX}%"},
                    )
                )
                .scalars()
                .all()
            )
            symbols = [
                str(s)
                for s in (
                    await session.execute(
                        text(
                            "SELECT DISTINCT instrument_id FROM portfolio_reservations "
                            "WHERE account_id = :account_id AND cycle_id LIKE :prefix"
                        ),
                        {"account_id": account_id, "prefix": f"{CYCLE_PREFIX}%"},
                    )
                )
                .scalars()
                .all()
                if s
            ]
            for cycle_id in cycles:
                await _wipe_cycle(session, account_id=account_id, cycle_id=cycle_id)
            await session.commit()
    finally:
        await engine.dispose()
    return cycles, symbols


# ── Orquestación ───────────────────────────────────────────────────────────────────


async def _run_seed(args: argparse.Namespace) -> int:
    instrument_uuid, symbol = _resolve_instrument(
        args.api_base, symbol=args.symbol, instrument_id=args.instrument_id
    )
    definition_id, token, label = _resolve_strategy(args.api_base)
    cycle_id = _cycle_id_for(args.account_id, symbol)

    print(f"· instrumento: {symbol} · {instrument_uuid}")
    print(f"· estrategia #1: {label} · {definition_id} (sello={token})")
    print(f"· ciclo: {cycle_id}")

    await _seed_db(
        account_id=args.account_id,
        symbol=symbol,
        strategy_version_id=token,
        cycle_id=cycle_id,
    )
    _put_strategy_top(
        args.api_base,
        instrument_uuid=instrument_uuid,
        symbol=symbol,
        definition_id=definition_id,
        strategy_type=token,
        label=label,
    )

    route = f"/auto/operar/operacion/{cycle_id}"
    print("")
    print("OK — ciclo AUTO sembrado (durable).")
    print(f"  account_id : {args.account_id}")
    print(f"  cycle_id   : {cycle_id}")
    print(f"  ruta       : {route}")
    print(f"  monitor    : GET {args.api_base}/api/auto/operational-monitor?cycleId={cycle_id}")
    return 0


async def _run_cleanup(args: argparse.Namespace) -> int:
    cycles, symbols = await _cleanup_db(account_id=args.account_id)
    if cycles:
        print(f"· ciclos borrados: {', '.join(cycles)}")
    else:
        print("· no había ciclos sembrados (cyc-ui-*) que borrar")

    targets: set[str] = set()
    for symbol in symbols:
        try:
            uuid_, _ = _resolve_instrument(
                args.api_base, symbol=symbol, instrument_id=None
            )
            targets.add(uuid_)
        except RuntimeError as exc:
            print(f"  (aviso) no pude resolver {symbol!r} para borrar su TOP: {exc}")
    if args.instrument_id:
        targets.add(args.instrument_id)
    elif args.symbol:
        try:
            uuid_, _ = _resolve_instrument(
                args.api_base, symbol=args.symbol, instrument_id=None
            )
            targets.add(uuid_)
        except RuntimeError as exc:
            print(f"  (aviso) no pude resolver {args.symbol!r}: {exc}")

    for instrument_uuid in sorted(targets):
        try:
            _http_json(
                "DELETE",
                f"/api/instruments/{urllib.parse.quote(instrument_uuid)}"
                "/strategy-top?timeframe=1d",
                api_base=args.api_base,
            )
            print(f"· TOP de Finalistas borrado: {instrument_uuid}")
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                print(f"· (sin TOP que borrar) {instrument_uuid}")
            else:
                print(f"  (aviso) DELETE strategy-top {instrument_uuid}: {exc}")
    print("OK — limpieza completada.")
    return 0


async def _run(args: argparse.Namespace) -> int:
    print("Bolsa V1 — seed de un ciclo AUTO para la UI")
    _require_env()
    _require_api(args.api_base)
    if args.cleanup:
        return await _run_cleanup(args)
    return await _run_seed(args)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Siembra (o limpia) UN ciclo AUTO durable para abrirlo en el navegador."
    )
    parser.add_argument(
        "--symbol", default=None, help="Símbolo/ticker real (p. ej. ACS). Sin él usa el primero."
    )
    parser.add_argument(
        "--instrument-id", default=None, help="UUID del instrumento (opcional; anula --symbol)."
    )
    parser.add_argument(
        "--api-base", default=DEFAULT_API_BASE, help=f"Base URL de la API (default {DEFAULT_API_BASE})."
    )
    parser.add_argument(
        "--account-id", default=DEFAULT_ACCOUNT_ID, help=f"Cuenta (default {DEFAULT_ACCOUNT_ID})."
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Borra lo sembrado (filas por cuenta/ciclo + DELETE .../strategy-top) y sale.",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
