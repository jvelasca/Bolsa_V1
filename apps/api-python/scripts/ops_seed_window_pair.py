#!/usr/bin/env python3
"""OPS · Semilla del par A/B para la ventana PAPER forward (operación, no fase de motor).

Qué resuelve: el runner de la ventana (``v2_76_forward_market_material.py``) localiza la
versión B con ``get_active(instrument_id=<cuenta>)``; las promociones reales del repo están
keyed por **instrumento** (``inst-v229-…``), no por cuenta, así que sin una estrategia B
ACTIVE **atribuida a la cuenta de la ventana** el par A/B queda ``CAPAZ`` sin ``ACTIVO``
(``versionB=""`` ⇒ ``pairActive=false``).

Este script deja el entorno listo **una sola vez, antes de D1**:

1. Crea (o reusa) la **cuenta simulada dedicada y fija** de la ventana (``$ACCOUNT``).
2. Siembra la **versión B** en ``strategy_versions`` con una definición **ejecutable real**
   construida por el propio catálogo del repo (``strategy_definition_from_preset``), para
   que la señal de B se evalúe de verdad (``evaluate_strategy_last_bar``) y no quede en
   HOLD por falta de ``executable``.
3. Inserta la **fila localizadora** en ``strategy_promotions`` con
   ``instrument_id=$ACCOUNT`` y ``promoted=true``.
4. Siembra el ``EdgeReport`` de **A y de B** sobre la misma cuenta (sin edge, el motor veta
   por ``edge_below_threshold``).
5. Escribe ``operability_runs/window-setup.json`` con ``{account, versionA, versionB}`` para
   reusar D1..D4.

REGLA DURA (honestidad del material): la B sembrada NO está **gate-certificada**. La fila de
``strategy_promotions`` es un **localizador de ámbito** (lo dice el propio store: «la fila de
localización NO certifica shadow»), con ``shadow_validated=false`` y una ``notes``/``reasons``
que lo declaran. Por eso ``pairActive=true`` significa «par operativo sembrado», **no**
«promoción certificada por gates», y ``P3-3`` (A/B) no se cierra con esto: solo queda
**medible**. Mismo criterio que el ``EdgeReport`` sintético que el propio runner siembra para A.

Qué NO hace: no toca el motor (``auto_simulation_worker.py``), ni el gobernador, ni ``TOP_N``,
ni umbrales, ni allocation; no añade migración; no modifica ``.env`` (imprime las líneas que el
operador debe fijar).

Uso (desde la raíz del repo)::

    uv run --no-sync python apps/api-python/scripts/ops_seed_window_pair.py

    # Reusar una cuenta ya creada (idempotente) y fijar etiquetas:
    uv run --no-sync python apps/api-python/scripts/ops_seed_window_pair.py \\
        --account-id <uuid> --version-a v283-window-a --version-b v283-window-b

Códigos de salida: ``0`` semilla lista; ``2`` bloqueado (sin PostgreSQL o cuenta inexistente);
``1`` uso incorrecto.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"
_DEFAULT_OUT = _REPO_ROOT / "operability_runs" / "window-setup.json"

_DEFAULT_ACCOUNT_NAME = "PAPER-VENTANA"
_DEFAULT_VERSION_A = "v283-window-a"
_DEFAULT_VERSION_B = "v283-window-b"
_DEFAULT_PRESET = "sma_crossover"
_DEFAULT_LOT_QTY = 100.0
_DEFAULT_WATCH_SIZE = 20
_DEFAULT_MIN_BARS = 60

#: Declaración explícita: la B es una semilla operativa, NO una promoción certificada por gates.
SEED_PROMOTION_REASON = "semilla_operativa_ventana_no_gate_certificada"
SEED_EDGE_NOTE = "edge_operativo_ventana_no_gate_certificado"
SEED_VERSION_LABEL = "v2.83-window-operator-seed"

logger = logging.getLogger("ops_seed_window_pair")


async def _resolve_account(session: Any, *, account_id: str | None, name: str) -> tuple[str, bool]:
    """Devuelve ``(account_id, created)``. Sin ``--account-id`` crea una cuenta simulada nueva."""
    from bolsa_infrastructure.database.models.tables import InvestmentAccountRow
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    if account_id:
        existing = await session.get(InvestmentAccountRow, account_id)
        if existing is None:
            raise LookupError(f"la cuenta indicada no existe: {account_id}")
        return str(existing.id), False

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"{name}-{uuid4().hex[:6]}",
        initial_deposit=100_000.0,
    )
    await session.commit()
    return str(scope.account.id), True


async def _derive_watch(session: Any, *, size: int, min_bars: int) -> list[str]:
    """Watch determinista del catálogo real (mismo criterio que el runner de la ventana)."""
    from sqlalchemy import func, select

    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow

    with_history = (
        select(OhlcvBarRow.instrument_id)
        .where(OhlcvBarRow.timeframe == "1d")
        .group_by(OhlcvBarRow.instrument_id)
        .having(func.count() >= max(2, int(min_bars)))
        .subquery()
    )
    stmt = (
        select(InstrumentRow.id)
        .join(with_history, with_history.c.instrument_id == InstrumentRow.id)
        .where(
            InstrumentRow.is_active.is_(True),
            InstrumentRow.sector.isnot(None),
        )
        .order_by(InstrumentRow.id)
        .limit(max(1, int(size)))
    )
    return [str(row[0]) for row in (await session.execute(stmt)).all()]


async def _seed_version_b(
    session: Any,
    *,
    account_id: str,
    version_b: str,
    preset: str,
    watch: list[str],
    lot_qty: float,
) -> tuple[str, bool]:
    """Crea la versión B (definición ejecutable) y su localizador de promoción por cuenta."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from bolsa_analytics.signals.preset_catalog import (
        is_valid_preset_key,
        strategy_definition_from_preset,
    )
    from bolsa_application.strategy_promotion_phase import definition_hash
    from bolsa_infrastructure.database.models.tables import (
        StrategyPromotionRow,
        StrategyVersionRow,
    )
    from bolsa_infrastructure.ids import new_id

    if not is_valid_preset_key(preset):
        raise ValueError(f"preset desconocido: {preset}")

    existing = await session.get(StrategyVersionRow, version_b)
    if existing is not None:
        logger.info("versión B ya existente: %s (se reutiliza)", version_b)
        return str(existing.candidate_id), False

    executable = strategy_definition_from_preset(preset, list(watch))
    definition: dict[str, Any] = {
        "family": preset,
        "params": {"seed": "ventana-paper", "preset": preset},
        "lot_qty": float(lot_qty),
        "executable": executable,
    }
    candidate_id = f"cand-{version_b}"
    now = datetime.now(UTC)

    session.add(
        StrategyVersionRow(
            id=version_b,
            candidate_id=candidate_id,
            # El ámbito de la versión sembrada es la CUENTA de la ventana (no un instrumento):
            # ``get_active`` localiza por la promoción, pero la fila debe ser no-nula y coherente.
            instrument_id=account_id,
            name=f"PAPER-WINDOW {preset}",
            definition_hash=definition_hash(definition),
            definition=definition,
            is_finalist=True,
            created_at=now,
        )
    )
    await session.execute(
        pg_insert(StrategyPromotionRow)
        .values(
            id=new_id(),
            finalist_id=version_b,
            candidate_id=candidate_id,
            instrument_id=account_id,
            promoted=True,
            reasons=[SEED_PROMOTION_REASON],
            # Declarado: la fila es un localizador de ámbito, NO certifica shadow.
            shadow_validated=False,
            shadow_validation_id=None,
            promoted_at=now,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.commit()
    return candidate_id, True


async def _seed_edge_report(session: Any, *, account_id: str, strategy_ref: str) -> bool:
    """Siembra el EdgeReport de una versión sobre la cuenta (idempotente)."""
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    existing = (
        (
            await session.execute(
                select(EdgeReportRow.id).where(
                    EdgeReportRow.account_id == account_id,
                    EdgeReportRow.strategy_or_signal_ref == strategy_ref,
                )
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return False

    session.add(
        EdgeReportRow(
            id=f"edge-window-{uuid4().hex[:8]}",
            version=SEED_VERSION_LABEL,
            strategy_or_signal_ref=strategy_ref,
            instrument_universe_ref=None,
            account_id=account_id,
            credibility=Decimal("0.80"),
            edge_score=Decimal("0.90"),
            band="positive",
            suite={},
            notes=[SEED_EDGE_NOTE],
            payload=None,
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return True


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        account_id, account_created = await _resolve_account(
            session, account_id=args.account_id, name=args.account_name
        )
        watch = [s.strip() for s in (args.watch or "").split(",") if s.strip()]
        if not watch:
            watch = await _derive_watch(
                session, size=int(args.watch_size), min_bars=int(args.min_bars)
            )
        if not watch:
            raise RuntimeError("el catálogo no aportó ningún instrumento con sector y barras")

        _, version_b_created = await _seed_version_b(
            session,
            account_id=account_id,
            version_b=args.version_b,
            preset=args.preset,
            watch=watch,
            lot_qty=float(args.lot_qty),
        )
        edge_a_created = await _seed_edge_report(
            session, account_id=account_id, strategy_ref=args.version_a
        )
        edge_b_created = await _seed_edge_report(
            session, account_id=account_id, strategy_ref=args.version_b
        )

    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "account": account_id,
        "accountCreated": account_created,
        "versionA": args.version_a,
        "versionB": args.version_b,
        "preset": args.preset,
        "lotQty": float(args.lot_qty),
        "watch": watch,
        "watchSize": len(watch),
        "versionBCreated": version_b_created,
        "edgeACreated": edge_a_created,
        "edgeBCreated": edge_b_created,
        "declaration": {
            "promotionReason": SEED_PROMOTION_REASON,
            "edgeNote": SEED_EDGE_NOTE,
            "gateCertified": False,
            "note": (
                "Semilla operativa: habilita pairActive y la atribución A/B; NO certifica los "
                "gates de promoción ni cierra P3-3."
            ),
        },
    }


def _print_summary(payload: dict[str, Any]) -> None:
    print("OPS · SEMILLA DEL PAR A/B PARA LA VENTANA PAPER")
    print("-" * 54)
    print(f"cuenta (PAPER_D_ACCOUNT_ID)   {payload['account']}")
    print(f"  cuenta creada               {'sí' if payload['accountCreated'] else 'reusada'}")
    print(f"version A (determinista)      {payload['versionA']}")
    print(f"version B (ACTIVE)            {payload['versionB']}  ({payload['preset']})")
    print(f"  versión B creada            {'sí' if payload['versionBCreated'] else 'reusada'}")
    print(
        f"  edge A / edge B             {'sí' if payload['edgeACreated'] else 'existía'} / "
        f"{'sí' if payload['edgeBCreated'] else 'existía'}"
    )
    print(f"watch                         {payload['watchSize']} símbolos")
    print("")
    print("# Declara estas dos líneas en .env y reinicia la API (node scripts/dev-api-python.mjs):")
    print(f"PAPER_D_ACCOUNT_ID={payload['account']}")
    print("BROKER_VENUE=paper")
    print("")
    print(
        "# NOTA: la B es una SEMILLA OPERATIVA (no gate-certificada): pairActive=true significa",
        file=sys.stderr,
    )
    print(
        "#       'par sembrado', no 'promoción certificada'; P3-3 no se cierra con esto.",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account-id", default=None, help="cuenta existente a reusar (si falta, se crea)"
    )
    parser.add_argument(
        "--account-name",
        default=_DEFAULT_ACCOUNT_NAME,
        help="prefijo del nombre de la cuenta nueva",
    )
    parser.add_argument(
        "--version-a", default=_DEFAULT_VERSION_A, help="etiqueta fija de la versión A"
    )
    parser.add_argument(
        "--version-b", default=_DEFAULT_VERSION_B, help="id de la versión B sembrada"
    )
    parser.add_argument(
        "--preset", default=_DEFAULT_PRESET, help="preset ejecutable de la versión B"
    )
    parser.add_argument(
        "--lot-qty", type=float, default=_DEFAULT_LOT_QTY, help="lote de la versión B"
    )
    parser.add_argument(
        "--watch", default=None, help="watch explícito (coma) para el universo de B"
    )
    parser.add_argument(
        "--watch-size", type=int, default=_DEFAULT_WATCH_SIZE, help="tamaño del watch derivado"
    )
    parser.add_argument(
        "--min-bars", type=int, default=_DEFAULT_MIN_BARS, help="barras D1 mínimas por símbolo"
    )
    parser.add_argument("--out", default=str(_DEFAULT_OUT), help="ruta del JSON de setup")
    args = parser.parse_args(argv)

    if int(args.watch_size) <= 0:
        print("# uso incorrecto: --watch-size debe ser > 0", file=sys.stderr)
        return 1
    if float(args.lot_qty) <= 0:
        print("# uso incorrecto: --lot-qty debe ser > 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        payload = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PostgreSQL no hay semilla: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo sembrar el par A/B ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
