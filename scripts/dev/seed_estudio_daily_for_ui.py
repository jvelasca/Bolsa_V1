"""Siembra (o limpia) el mundo ESTUDIO de la operativa diaria para el journey LIVE del navegador.

Para qué sirve
--------------
El spec ``apps/web/e2e/gp-e2e-auto-daily-chain-live.spec.ts`` ejercita la UI contra la API y
el WORKER reales: pulsa «Calcular operativa diaria» y espera el parte durable; después pide el
DÍA-D del valor y comprueba la cola y el artefacto. Para que el parte proponga de verdad hace
falta un mundo sembrado: instrumento con barras (>= 210 para que SMA200 sea calculable y el
``stance`` pueda ser ``buy`` por DATO, no por umbral), fundamentales en corte PIT, estrategia
ACTIVE, informe de edge, foto TOP vigente y pertenencia a la lista canónica ``estudio``.

Qué NO hace
-----------
No reimplementa el motor ni el embudo: reutiliza el harness REAL de siembra
(``apps/api-python/tests/support/auto_chain_e2e.py``) — la misma fuente que usa el E2E de
Python. No toca cuentas protegidas (demo/PAPER), no modifica ``main``, no abre el bridge LIVE
y no rebaja ningún gate: si el dato no justifica el plan, el parte lo declarará.

Idempotencia y limpieza
-----------------------
Todos los ids son DETERMINISTAS por símbolo (``inst-ui-daily-…``, ``cand-ui-daily-…``), de modo
que reejecutar barre lo anterior y ``--cleanup`` borra exactamente lo sembrado sin adivinar.

Uso
---
    uv run --no-sync python scripts/dev/seed_estudio_daily_for_ui.py \
        --account-id <cuenta efímera> --symbol E2EDAILY --api-base http://localhost:8000

Salida: una línea ``MANIFEST {…}`` (JSON) con la identidad sembrada — el spec la parsea para
saber símbolo/instrumento/día y para restaurar la lista ``estudio`` al terminar.

    uv run --no-sync python scripts/dev/seed_estudio_daily_for_ui.py --cleanup \
        --account-id <cuenta efímera> --symbol E2EDAILY \
        --previous-membership <ids separados por comas>
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP_PY = _REPO_ROOT / "apps" / "api-python"
for _path in (_APP_PY, _APP_PY / "tests"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_SYMBOL = "E2EDAILY"
#: Barras de contexto: 210 para que SMA200 sea calculable (el rating pide 200 y el
#: composite 260; con menos, la pata de tendencia larga no existe y el stance no puede ser buy).
DEFAULT_BARS = 210
#: Prefijo de TODAS las filas que este seed crea (la limpieza se apoya en él).
PREFIX = "ui-daily"


def _digest(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:10]


def instrument_id_for(symbol: str) -> str:
    """``instrument_id`` determinista por símbolo (reejecutar no duplica el mundo)."""
    return f"inst-{PREFIX}-{_digest(symbol.upper())}"


def _default_as_of() -> str:
    """Vela CERRADA por defecto: ayer (UTC), que es la frontera de decisión del parte."""
    return (datetime.now(UTC).date() - timedelta(days=1)).isoformat()


async def _ensure_instrument(factory: Any, *, instrument_id: str, symbol: str, as_of: str) -> None:
    """Instrumento con gates medibles: sector + fundamentales con corte PIT (nunca futuros)."""
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    from tests.support import auto_chain_e2e as chain

    async with factory() as session:
        await chain.seed_instrument(
            session,
            instrument_id,
            symbol_prefix=symbol[:3] or "UID",
            fundamentals=chain.strong_fundamentals(f"{as_of}T00:00:00+00:00"),
        )
        row = await session.get(InstrumentRow, instrument_id)
        assert row is not None, "el instrumento sembrado debe existir"
        # El harness genera un símbolo aleatorio; aquí el símbolo ES el contrato del journey
        # (la URL del valor y el `payload.symbol` del replay), así que se fija.
        if row.symbol != symbol or row.yahoo_symbol != symbol:
            row.symbol = symbol
            row.yahoo_symbol = symbol
            await session.commit()


async def _seed_bars(factory: Any, *, instrument_id: str, as_of: str, bars: int) -> int:
    """Serie D1 con la ÚLTIMA barra CERRADA en ``as_of`` (idempotente: barre las propias)."""
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import OhlcvBarRow

    from tests.support import auto_chain_e2e as chain

    async with factory() as session:
        await session.execute(
            delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id)
        )
        await session.commit()
    rows = chain.closed_bar_rows(as_of, closed_bars=bars)
    await chain.seed_bars(factory, instrument_id, rows)
    return len(rows)


async def _seed(account_id: str, *, symbol: str, as_of: str, bars: int) -> dict[str, Any]:
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    from tests.support import auto_chain_e2e as chain

    instrument_id = instrument_id_for(symbol)
    token = _digest(symbol, "strategy")
    engine, factory = await chain.open_session_factory()
    try:
        await _ensure_instrument(
            factory, instrument_id=instrument_id, symbol=symbol, as_of=as_of
        )
        bar_count = await _seed_bars(
            factory, instrument_id=instrument_id, as_of=as_of, bars=bars
        )
        version_id, candidate_id = await chain.seed_active_strategy(
            factory, instrument_id=instrument_id, prefix=PREFIX, suffix=token
        )
        async with factory() as session:
            await session.execute(
                delete(EdgeReportRow).where(
                    EdgeReportRow.account_id == account_id,
                    EdgeReportRow.id.like(f"edge-{PREFIX}-%"),
                )
            )
            await session.commit()
            await chain.seed_edge_report(
                session,
                account_id=account_id,
                strategy_ref=version_id,
                prefix=f"edge-{PREFIX}",
            )
        await chain.seed_strategy_top(factory, instrument_id=instrument_id)
        membership = await chain.seed_estudio_list(factory, instrument_id)
        return {
            "accountId": account_id,
            "symbol": symbol.upper(),
            "instrumentId": instrument_id,
            "asOf": as_of,
            "bars": bar_count,
            "strategyVersionId": version_id,
            "candidateId": candidate_id,
            "previousMembership": membership,
        }
    finally:
        await engine.dispose()


async def _cleanup(
    account_id: str,
    *,
    symbol: str,
    previous_membership: list[str] | None,
) -> dict[str, Any]:
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    from tests.support import auto_chain_e2e as chain

    instrument_id = instrument_id_for(symbol)
    token = _digest(symbol, "strategy")
    version_id = f"v-{PREFIX}-{token}"
    candidate_id = f"cand-{PREFIX}-{token}"
    engine, factory = await chain.open_session_factory()
    try:
        async with factory() as session:
            await session.execute(
                delete(EdgeReportRow).where(
                    EdgeReportRow.account_id == account_id,
                    EdgeReportRow.id.like(f"edge-{PREFIX}-%"),
                )
            )
            await session.commit()
        # ``cleanup_world`` borra: filas durables de la cuenta (fills, journal, reservas,
        # posiciones, salidas, propuestas, jobs), la estrategia sembrada, el TOP, las barras
        # y el instrumento. Los ids son deterministas ⇒ borra EXACTAMENTE lo nuestro.
        await chain.cleanup_world(
            account_id=account_id,
            engine_id="auto-sim",
            instrument_id=instrument_id,
            version_id=version_id,
            candidate_id=candidate_id,
            estudio_membership=None,
        )
        if previous_membership is not None:
            await chain.restore_estudio_list(factory, previous_membership)
        else:
            # Sin la membresía previa, el estado final correcto sigue siendo «este valor no
            # está en la lista»: se retira (idempotente) sin tocar al resto del universo.
            await chain.restore_estudio_list(
                factory,
                [
                    item
                    for item in (await _estudio_members(factory))
                    if item != instrument_id
                ],
            )
        return {"accountId": account_id, "instrumentId": instrument_id, "cleaned": True}
    finally:
        await engine.dispose()


async def _estudio_members(factory: Any) -> list[str]:
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        current = await repo.ensure_estudio_list()
        return list(current.instrument_ids)


def _parse_membership(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


async def _run(args: argparse.Namespace) -> int:
    symbol = (args.symbol or DEFAULT_SYMBOL).strip().upper()
    if not args.account_id:
        raise RuntimeError("falta --account-id (la cuenta efímera del journey)")
    if args.cleanup:
        result = await _cleanup(
            args.account_id,
            symbol=symbol,
            previous_membership=_parse_membership(args.previous_membership),
        )
        print(f"MANIFEST {json.dumps(result, ensure_ascii=False)}")
        print("OK — limpieza completada.")
        return 0
    as_of = (args.as_of or _default_as_of()).strip()
    date.fromisoformat(as_of)  # valida el formato ISO (falla antes de sembrar nada)
    if args.bars < 210:
        raise RuntimeError(
            f"--bars={args.bars}: SMA200 necesita >= 210 barras de contexto para ser "
            "calculable (no se rebajan umbrales: sin dato, el stance no puede ser buy)."
        )
    result = await _seed(
        args.account_id, symbol=symbol, as_of=as_of, bars=int(args.bars)
    )
    print(f"MANIFEST {json.dumps(result, ensure_ascii=False, default=str)}")
    print("")
    print("OK — mundo ESTUDIO sembrado.")
    print(f"  cuenta     : {result['accountId']}")
    print(f"  símbolo    : {result['symbol']} ({result['instrumentId']})")
    print(f"  vela cerrada: {result['asOf']} · barras {result['bars']}")
    print(f"  estrategia : {result['strategyVersionId']}")
    print("  UI         : /auto-monitor?mode=daily")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Siembra (o limpia) el mundo ESTUDIO de la operativa diaria para el journey "
            "LIVE del navegador (API + worker reales)."
        )
    )
    parser.add_argument(
        "--account-id",
        default=None,
        help="Cuenta efímera del journey (obligatoria).",
    )
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help=f"Símbolo del valor sembrado (default {DEFAULT_SYMBOL}).",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Vela CERRADA del parte en ISO (default: ayer UTC).",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=DEFAULT_BARS,
        help=f"Barras D1 de contexto (default {DEFAULT_BARS}; mínimo 210).",
    )
    parser.add_argument(
        "--previous-membership",
        default=None,
        help="Ids previos de la lista ``estudio`` (coma) para restaurarla EXACTA al limpiar.",
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help=f"Base URL de la API (default {DEFAULT_API_BASE}).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Borra lo sembrado (ids deterministas + filas de la cuenta) y sale.",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
