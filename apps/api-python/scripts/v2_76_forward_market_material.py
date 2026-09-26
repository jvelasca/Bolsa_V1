#!/usr/bin/env python3
"""V2.76 · AUTO-MATERIAL-4 — PAPER FORWARD con precio de MERCADO (material diverso).

Qué resuelve: ``v2.75`` cruzó la CANTIDAD (``EVIDENCE_READY``, 42 ciclos medibles) pero no la
DIVERSIDAD: todos los ciclos cayeron en UN bucket de calendario y UN episodio de régimen, porque el
harness conducía el productor con **precio guionizado** y **régimen forzado** (``BULL_TREND``).
``P3-2`` (correlación por cubos) y ``P3-3`` (``P(R>0)`` vs N) exigen **material de MERCADO repartido
en ≥4 cubos y ≥2 episodios**.

Qué hace este runner:

1. Cablea un ``price_script`` de **MERCADO** (``MarketPriceSnapshot``: cotización XTB live con
   respaldo del último cierre durable) en el ``AutoSimulationWorker`` — el ÚNICO seam de precio del
   motor. ATR y régimen ya los compone ``AutoSimRuntime.run_tick`` desde ``ohlcv_bars`` REALES.
2. **NO** fija ``AUTO_ENGINE_SIM_V2_REGIME``: el régimen operativo sale de ``DiscoveryRegimeSource``
   (barras), así que los episodios de régimen pueden ser diversos.
3. Corre DOS versiones de estrategia sobre la MISMA cuenta: la **A** determinista
   (``auto-2.0:<vA>``, re-entra cuando el símbolo está plano) y la **B** = estrategia ACTIVE
   promovida (``active-strategy:<vB>``), enrutadas por símbolo (``SplitWatchDecider``).
4. Avanza con **reloj REAL** (``default_clock``): los cubos de calendario salen del instante durable
   del fill (``created_at``), así que la diversidad de cubos exige TIEMPO REAL transcurrido. Este
   runner se deja corriendo días; no simula fechas.
5. Lee el material con la MISMA pieza que el gate (``build_paper_material_readiness``) y declara el
   veredicto. Publica JSON de progreso para el operador.
6. Antes de correr, diagnostica (read-only) el **régimen de MERCADO** del watch con las MISMAS
   piezas del tick y declara si el universo admite entradas LONG (``--preflight-only`` no escribe
   nada). Motivo MEDIDO de esta fase: el agregado es el veredicto más conservador presente, así que
   un solo ``trend_down`` en un watch amplio deja el eje en ``BEAR_TREND`` y veta por
   ``regime_invalid`` todas las entradas del tick.

Qué NO hace (reglas duras del repo):

* **No** baja ``min cycles`` / ``min R`` / ``folds`` / ``min_episodes`` para forzar un READY.
* **No** repara material: no infiere ``cycle_id`` ni ``reserved_risk``, no backdatea ``created_at``,
  no rellena el histórico legacy.
* **No** reparte: ``ALLOCATION`` sigue congelado (``auto18-v1`` / ``auto15-v1``). Sin migración.
* **No** toca el freeze (``auto_simulation_worker.py`` no se modifica): sólo lo CABLEA.

Uso (desde la raíz del repo)::

    # Cuenta nueva + watch derivado del catálogo real (recomendado).
    uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \\
        --interval-seconds 60 --json --out evidencia-forward.json

    # Cuenta existente y watch explícito.
    uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \\
        --account-id <uuid> --watch AAA,BBB,CCC

    # Antes de dejar el runner días corriendo: ¿puede ENTRAR este universo hoy?
    uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \\
        --preflight-only --watch-size 20

Códigos de salida: ``0`` si el material alcanza el nivel pedido (default ``evidence``); ``2`` si no
lo alcanza o no se pudo ejercitar (se declara por stderr); ``1`` uso incorrecto. En
``--preflight-only``: ``0`` si el universo admite entradas LONG hoy y ``2`` si el eje operativo las
veta (``BEAR_TREND``/``UNKNOWN`` ⇒ ``regime_invalid``), sin escribir nada.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

_SYMBOLS_ENV = "AUTO_ENGINE_SIMULATED_WATCH"

logger = logging.getLogger("v2_76_forward_market_material")

#: Mínimo declarado del protocolo (no se baja para forzar una corrida).
_DEFAULT_MIN_CYCLES = 32


def _configure_env(*, venue: str) -> None:
    """Fija las env del productor V2. NO fija régimen: ése lo aporta el MERCADO (barras)."""
    os.environ.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "0",
            "AUTO_ENGINE_SIM_V2": "1",
            # NO se fija AUTO_ENGINE_SIM_V2_REGIME a propósito: con el override puesto, TODOS los
            # ciclos comparten un único episodio de régimen (fue el hallazgo de v2.75). Sin él,
            # ``DiscoveryRegimeSource`` lee el régimen de las barras reales.
            "AUTO_ENGINE_SIM_V2_EQUITY": "100000",
            "AUTO_ENGINE_SIM_V2_TOP_N": "5",
            # El ATR sintético no sostiene una geometría de riesgo de mercado: el símbolo sin
            # barras suficientes queda vetado (se declara) en vez de dimensionarse con un 2 %.
            "AUTO_ENGINE_SIM_V2_ATR_REQUIRED": "1",
            "AUTO_ENGINE_SIMULATED_VENUE": venue,
            "AUTO_ENGINE_SIM_INTERVAL_SECONDS": "1.0",
            "AUTO_ENGINE_SIM_LOT_QTY": "100",
            # El par real de versiones: A determinista + B = estrategia ACTIVE con su señal real.
            "AUTO_ENGINE_SIM_ACTIVE_STRATEGY": "1",
            "AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL": "1",
            # El gate PAPER se corre con esta venue: su guarda exige ``paper``.
            "BROKER_VENUE": "paper",
        }
    )
    if venue != "paper":  # pragma: no cover — guarda de coherencia del operador.
        logger.warning("venue %s != paper: el gate PAPER rechazará este material", venue)


def _watch_from_cli(raw: str | None) -> list[str]:
    """Watch explícito del operador (o vacío: se derivará del catálogo)."""
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


async def _watch_from_catalog(factory: Any, size: int, *, min_bars: int) -> list[str]:
    """Deriva el watch del CATÁLOGO REAL: activos, con sector y con HISTORIA suficiente.

    No se inventan instrumentos ni fundamentales: sin sector la candidata se veta
    (``sector_unknown``) y sin barras no hay ATR ni régimen reales (``atr_source`` lo declara y el
    régimen del tick cae a ``regime_invalid``, que bloquea TODAS las entradas — defecto observado y
    corregido dentro de esta misma fase). Por eso se exige un MÍNIMO de barras diarias. El watch es
    determinista (orden por ``id``) para que dos corridas midan el mismo universo.
    """
    from sqlalchemy import func, select

    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow

    async with factory() as session:
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


def _quote_price(quote: Any) -> float | None:
    """Precio utilizable de una cotización del bridge (``last`` > ``bid`` > ``ask``)."""
    for attribute in ("last", "bid", "ask"):
        try:
            value = float(getattr(quote, attribute))
        except (AttributeError, TypeError, ValueError):
            continue
        if value == value and value not in (float("inf"), float("-inf")) and value > 0:
            return value
    return None


def _compose_price_providers(factory: Any, *, xtb_url: str | None) -> tuple[Any, Any]:
    """Compone los dos proveedores del ``MarketPriceSnapshot`` (live + cierre durable).

    El cierre sale del catálogo (``last_close`` de las barras durables, UNA consulta por lote): es
    el respaldo declarado cuando el bridge no sirve el símbolo. La cotización viva exige el bridge;
    sin ``XTB_BRIDGE_URL`` el snapshot queda sólo con cierres (se declara, no se finge).
    """
    bridge_url = (xtb_url or "").strip()

    async def _metas(symbols: list[str]) -> list[Any]:
        from bolsa_infrastructure.database.repositories.instrument_repository import (
            SqlAlchemyInstrumentRepository,
        )

        async with factory() as session:
            return await SqlAlchemyInstrumentRepository(session).get_quotes_by_ids(
                [str(s) for s in symbols]
            )

    async def quotes(symbols: list[str]) -> dict[str, float]:
        if not bridge_url:
            return {}
        from bolsa_market.providers import XtbBridgeClient
        from bolsa_market.xtb_symbols import to_xtb_symbol

        metas = await _metas(list(symbols))
        refs: dict[str, float | None] = {}
        ids_by_xtb: dict[str, str] = {}
        for meta in metas:
            xtb_symbol = to_xtb_symbol(meta.symbol, yahoo_symbol=meta.yahoo_symbol)
            refs[xtb_symbol] = meta.last_close
            ids_by_xtb[xtb_symbol] = str(meta.id)
        if not refs:
            return {}
        # ``fetch_quotes`` absorbe el fallo POR SÍMBOLO y devuelve el mapa parcial: un bridge
        # caído deja el mapa vacío y el cierre durable cubre (nunca se aborta el tick).
        raw = await XtbBridgeClient(bridge_url).fetch_quotes(list(refs), references=refs)
        out: dict[str, float] = {}
        for xtb_symbol, quote in raw.items():
            instrument_id = ids_by_xtb.get(str(xtb_symbol))
            price = _quote_price(quote)
            if instrument_id and price is not None:
                out[instrument_id] = price
        return out

    async def closes(symbols: list[str]) -> dict[str, float]:
        metas = await _metas(list(symbols))
        return {
            str(meta.id): float(meta.last_close)
            for meta in metas
            if meta.last_close is not None and float(meta.last_close) > 0
        }

    return quotes, closes


async def _market_regime_preflight(factory: Any, watch: Sequence[str]) -> dict[str, Any]:
    """Diagnóstico READ-ONLY del régimen de MERCADO del watch (no escribe ni decide).

    Compone las MISMAS piezas que el tick (``make_bar_snapshot_loader`` → clasificador de
    barras → agregado → eje operativo) y declara si el universo puede ENTRAR hoy. Existe por
    un hallazgo MEDIDO de esta fase: el agregado es el veredicto **más conservador**
    presente (``_REGIME_CONSERVATIVE_PRIORITY``), así que **un solo** ``trend_down`` en el
    watch deja el eje operativo en ``BEAR_TREND`` y veta por ``regime_invalid`` TODAS las
    entradas LONG del tick (el motor V2 es long-only). Sin este diagnóstico, el operador
    descubre a los cuatro días que el universo no podía operar.

    No se inventa régimen: el símbolo sin barras cuenta como ``sin_regimen`` y el agregado
    sigue siendo fail-closed (⇒ ``UNKNOWN`` ⇒ exit-only).
    """
    from bolsa_analytics.cognitive.market_regime_gate import (  # noqa: PLC0415
        map_trial_regime,
        regime_allows_entry_for,
    )
    from bolsa_application.active_strategy_signal_evaluator import (  # noqa: PLC0415
        make_bar_snapshot_loader,
    )
    from bolsa_application.auto_v2_entry import aggregate_trial_regime  # noqa: PLC0415
    from bolsa_application.discovery_market_regime import (  # noqa: PLC0415
        classify_market_regime,
    )
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (  # noqa: PLC0415
        SqlAlchemyOhlcvRepository,
    )

    async with factory() as session:
        loader = make_bar_snapshot_loader(SqlAlchemyOhlcvRepository(session), list(watch))
        snapshot = await loader()

    by_symbol = {
        str(symbol): classify_market_regime(list(bars or [])) for symbol, bars in snapshot.items()
    }
    for symbol in watch:  # símbolo sin barras: se declara, no se inventa.
        by_symbol.setdefault(str(symbol), "")
    counts: dict[str, int] = {}
    for label in by_symbol.values():
        key = str(label or "sin_regimen")
        counts[key] = counts.get(key, 0) + 1
    aggregate = aggregate_trial_regime(by_symbol.values())
    operational = map_trial_regime(aggregate)
    return {
        "barsLoaded": len(snapshot),
        "bySymbol": by_symbol,
        "counts": counts,
        "aggregateTrialRegime": aggregate,
        "operationalRegime": operational,
        "entriesAllowedLong": bool(regime_allows_entry_for(operational, "long")),
    }


async def _seed_account(session: Any) -> str:
    """Cuenta PAPER nueva (igual que el harness de v2.75): material aislado y auditable."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"AUTO-V76-{os.urandom(4).hex()}",
        initial_deposit=100_000.0,
    )
    await session.commit()
    return scope.account.id


async def _seed_edge_report(session: Any, *, account_id: str, strategy_ref: str) -> None:
    """Informe de edge de la versión A: sin él el motor veta por ``edge_below_threshold``.

    Es el MISMO requisito que en producción: la ausencia de edge NO se rellena con un 0.9 por
    defecto. Se siembra sólo para la versión que este runner ATRIBUYE (la determinista).
    """
    from decimal import Decimal

    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    session.add(
        EdgeReportRow(
            id=f"edge-v76-{os.urandom(5).hex()}",
            version="v2.76-forward-market",
            strategy_or_signal_ref=strategy_ref,
            instrument_universe_ref=None,
            account_id=account_id,
            credibility=Decimal("0.80"),
            edge_score=Decimal("0.90"),
            band="positive",
            suite={},
            notes=[],
            payload=None,
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _active_strategy_version(factory: Any, account_id: str) -> str:
    """Versión de la estrategia ACTIVE promovida (la que estampa ``active-strategy:<v>``)."""
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

    try:
        async with factory() as session:
            record = await PostgresStrategyLifecycleStore(session).get_active(
                instrument_id=account_id
            )
    except Exception:  # noqa: BLE001 — sin lectura fiable no hay versión B que declarar.
        logger.exception("no se pudo leer la estrategia ACTIVE")
        return ""
    if record is None:
        return ""
    return str(getattr(record.active, "version_id", "") or "").strip()


async def _load_secondary_decider(
    factory: Any, *, account_id: str, watch: list[str]
) -> tuple[Any, str]:
    """Versión B = estrategia ACTIVE promovida (señal real). Devuelve ``(decider, versión)``."""
    from bolsa_api.background.auto_simulation_worker import load_active_strategy_decider

    version = await _active_strategy_version(factory, account_id)
    if not version:
        return None, ""
    try:
        decider = await load_active_strategy_decider(
            factory,
            instrument_id=account_id,
            watch=tuple(watch),
            signal_enabled=True,
        )
    except Exception:  # noqa: BLE001 — sin ACTIVE fiable se corre sólo la versión A (se declara).
        logger.exception("no se pudo cargar la estrategia ACTIVE (versión B): se corre sólo A")
        return None, version
    return decider, version


def _hold_decider(source: str) -> Any:
    """Decider que sólo hace ``HOLD`` (versión B ausente): no se inventa una estrategia."""
    from bolsa_application.decision_contract import DecisionPackage

    def _decide(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0, source=source)

    return _decide


def _compose_pair_decider(
    *,
    watch: list[str],
    watch_a: list[str],
    version_a: str,
    worker: Any,
    secondary: Any,
) -> Any:
    """Compone el par real; sin versión B, TODO va a la versión A y se declara el hueco."""
    from bolsa_application.auto_forward_deciders import build_forward_pair_decider

    if secondary is None:
        # Sin B no hay correlación que medir (P3-2), pero la versión A sigue produciendo material
        # para P3-3. El hueco se declara en el payload, no se disfraza.
        watch_a = list(watch)
        secondary = _hold_decider("forward:no-secondary")

    return build_forward_pair_decider(
        watch_a=watch_a,
        version_a=version_a,
        decider_b=secondary,
        held_quantity=lambda symbol: worker._open.get(symbol, 0),  # noqa: SLF001 — cableado.
        lot_qty=float(os.environ.get("AUTO_ENGINE_SIM_LOT_QTY") or "100"),
    )


async def _read_readiness(
    factory: Any, account_id: str, *, versions: list[str], min_cycles: int
) -> Any:
    """Lee el material durable de la cuenta y compone el veredicto con la pieza del GATE."""
    from sqlalchemy import select

    from bolsa_application.paper_material_readiness import build_paper_material_readiness
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.database.models.tables import AutoExitOrderRow

    async with factory() as session:
        context_store = PostgresSimFillFinanceContextStore(session)
        reservation_store = PostgresReservationStore(session)
        fills_by_version = await context_store.count_by_strategy_version(account_id=account_id)
        seen = sorted({str(v) for v in fills_by_version if v})
        fills: list[Any] = []
        for version in sorted(set(seen) | {str(v) for v in versions if str(v)}):
            fills.extend(
                await context_store.list_for_strategy_version(version, account_id=account_id)
            )
        reservations = await reservation_store.list_all(account_id, limit=5000)
        exit_cycles = (
            (
                await session.execute(
                    select(AutoExitOrderRow.cycle_id).where(
                        AutoExitOrderRow.account_id == account_id
                    )
                )
            )
            .scalars()
            .all()
        )
        exit_orders = [{"cycle_id": value} for value in exit_cycles]

    return build_paper_material_readiness(
        account_id=account_id,
        requested_versions=list(versions),
        fills=fills,
        reservations=reservations,
        exit_orders=exit_orders,
        regime_by_cycle={},
        min_cycles_per_strategy=max(1, int(min_cycles)),
        fills_by_version=fills_by_version,
    )


def _journal_reasons(worker: Any) -> list[str]:
    """Agrega los motivos del journal V2 EN MEMORIA (por qué el tick no abre/falta material).

    Es el diagnóstico que el operador necesita para saber si el bloqueo es de DATO (sector,
    liquidez, ATR, régimen, edge) o de MERCADO (sin movimiento). No escribe nada.
    """
    counts: dict[str, int] = {}
    for entry in list(getattr(worker, "_v2_journal", ()) or ()):
        payload = getattr(entry, "payload", None)
        if not isinstance(payload, dict):
            continue
        for reason in payload.get("reasonCodes") or ():
            key = str(reason)
            counts[key] = counts.get(key, 0) + 1
    return [f"{key}:{value}" for key, value in sorted(counts.items(), key=lambda kv: -kv[1])]


def _progress_row(readiness: Any, *, prices: int, watch: int, ticks: int) -> dict[str, Any]:
    facts = readiness.facts
    return {
        "ticks": ticks,
        "pricesServed": prices,
        "watchSize": watch,
        "durableFills": facts["durableFills"],
        "closedCycles": facts["closedCycles"],
        "measurableCycles": facts["measurableCycles"],
        "maxMeasurableCyclesPerVersion": facts["maxMeasurableCyclesPerVersion"],
        "versionsMeetingMinimum": list(facts["versionsMeetingMinimum"]),
        "perVersion": dict(facts["perVersion"]),
        "verdict": readiness.verdict,
        "blockers": list(readiness.blockers),
    }


def _print_progress(row: dict[str, Any]) -> None:
    print(
        f"[{datetime.now(UTC).strftime('%H:%M:%S')}] ticks={row['ticks']} "
        f"prices={row['pricesServed']}/{row['watchSize']} "
        f"cycles={row['measurableCycles']}/{row['maxMeasurableCyclesPerVersion']} "
        f"verdict={row['verdict']}",
        flush=True,
    )


def _print_preflight(evidence: dict[str, Any]) -> None:
    """Resumen humano del preflight de MERCADO (read-only)."""
    regime = evidence["marketRegime"]
    print("PREFLIGHT · RÉGIMEN DE MERCADO DEL WATCH (read-only, no escribe)")
    print("-" * 62)
    print(f"watch                          {evidence['watchSize']} símbolos")
    print(f"barras servidas por el loader  {regime['barsLoaded']}")
    print(f"régimen por símbolo            {regime['counts']}")
    print(f"agregado (más conservador)     {regime['aggregateTrialRegime']}")
    print(f"eje operativo                  {regime['operationalRegime']}")
    print(
        f"entradas LONG                  "
        f"{'PERMITIDAS' if regime['entriesAllowedLong'] else 'VETADAS (regime_invalid)'}"
    )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
        default_clock,
    )
    from bolsa_application.market_price_snapshot import MarketPriceSnapshot
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    _configure_env(venue=args.venue)

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    engine_base = f"auto-v76-{os.urandom(4).hex()}"
    account_id = str(args.account_id or "")
    watch = _watch_from_cli(args.watch)
    version_a = str(args.version_a or f"v76-forward-{engine_base[-4:]}")
    version_b = ""
    ticks = 0
    prices = 0
    secondary_loaded = False
    stop_reason = "completed"
    requested_versions = [version_a]
    totals = {
        "decided": 0,
        "proposals": 0,
        "vetoes": 0,
        "orders": 0,
        "fills": 0,
        "opened": 0,
        "closed": 0,
    }
    last_gate_reason: list[str] = []
    try:
        if not watch:
            watch = await _watch_from_catalog(
                factory, int(args.watch_size), min_bars=int(args.min_bars)
            )
        if not watch:
            raise RuntimeError("el catálogo no aportó ningún instrumento con sector y barras")
        os.environ[_SYMBOLS_ENV] = ",".join(watch)

        # Reparto determinista del universo en las dos versiones (A determinista, B = ACTIVE).
        from bolsa_application.auto_forward_deciders import split_watch

        watch_a, watch_b = split_watch(watch, a_share=float(args.a_share))

        # Diagnóstico de MERCADO antes de tocar nada: declara si el universo puede entrar
        # hoy. En modo ``--preflight-only`` el runner NO escribe (no siembra cuenta ni
        # material) y devuelve solo este diagnóstico.
        market_regime = await _market_regime_preflight(factory, watch)
        if args.preflight_only:
            return {
                "bump": "2.01.0-beta",
                "phase": "V2.76 AUTO-MATERIAL-4 MARKET MATERIAL FORWARD",
                "mode": "preflight",
                "account": account_id or "(no sembrada: el preflight no escribe)",
                "level": str(args.level),
                "minBars": int(args.min_bars),
                "minCyclesPerStrategy": int(args.min_cycles),
                "venue": str(args.venue),
                "watchA": list(watch_a),
                "watchB": list(watch_b),
                "watchSize": len(watch),
                "marketRegime": market_regime,
            }

        if not account_id:
            async with factory() as session:
                account_id = await _seed_account(session)
                await _seed_edge_report(session, account_id=account_id, strategy_ref=version_a)

        quotes_provider, closes_provider = _compose_price_providers(
            factory, xtb_url=settings.xtb_bridge_url
        )
        snapshot = MarketPriceSnapshot(
            quotes_provider=quotes_provider, closes_provider=closes_provider
        )

        worker = AutoSimulationWorker(
            engine_id=engine_base,
            account_id=account_id,
            require_account_id=True,
            price_script=snapshot,
            clock=default_clock,
        )
        secondary, version_b = await _load_secondary_decider(
            factory, account_id=account_id, watch=watch
        )
        secondary_loaded = secondary is not None
        requested_versions = [version_a, *([version_b] if version_b else [])]
        runtime = AutoSimRuntime(
            factory,
            worker=worker,
            engine_id=engine_base,
            account_id=account_id,
        )
        runtime.set_decider(
            _compose_pair_decider(
                watch=watch,
                watch_a=watch_a,
                version_a=version_a,
                worker=worker,
                secondary=secondary,
            )
        )

        next_secondary_refresh = 0.0
        loop = asyncio.get_running_loop()
        while True:
            if loop.time() >= next_secondary_refresh:
                secondary, version_b = await _load_secondary_decider(
                    factory, account_id=account_id, watch=watch
                )
                secondary_loaded = secondary_loaded or secondary is not None
                requested_versions = [version_a, *([version_b] if version_b else [])]
                runtime.set_decider(
                    _compose_pair_decider(
                        watch=watch,
                        watch_a=watch_a,
                        version_a=version_a,
                        worker=worker,
                        secondary=secondary,
                    )
                )
                next_secondary_refresh = loop.time() + max(1.0, float(args.decider_refresh_seconds))

            prices = await snapshot.refresh(watch)
            report = await runtime.run_tick()
            ticks += 1
            if report is not None:
                for field_name in totals:
                    totals[field_name] += int(getattr(report, field_name, 0) or 0)
            # Motivos del último tick (seam de diagnóstico del motor, read-only): sin ellos el
            # operador no puede saber POR QUÉ el material no avanza (sector, liquidez, ATR, ...).
            reasons = list(getattr(runtime.worker, "_last_gate_reason", ()) or ())
            if reasons:
                last_gate_reason = reasons

            if int(args.report_every) > 0 and ticks % int(args.report_every) == 0:
                readiness = await _read_readiness(
                    factory,
                    account_id,
                    versions=requested_versions,
                    min_cycles=int(args.min_cycles),
                )
                _print_progress(
                    _progress_row(readiness, prices=prices, watch=len(watch), ticks=ticks)
                )
                if args.stop_when_ready and readiness.achieved(args.level):
                    stop_reason = "ready"
                    break

            if int(args.max_ticks) > 0 and ticks >= int(args.max_ticks):
                break
            await asyncio.sleep(max(0.0, float(args.interval_seconds)))

        readiness = await _read_readiness(
            factory,
            account_id,
            versions=requested_versions,
            min_cycles=int(args.min_cycles),
        )
    finally:
        await engine.dispose()

    return {
        "bump": "2.01.0-beta",
        "phase": "V2.76 AUTO-MATERIAL-4 MARKET MATERIAL FORWARD",
        "account": account_id,
        "engineBase": engine_base,
        "versionA": version_a,
        "versionB": version_b,
        "requestedVersions": list(requested_versions),
        "watchA": list(watch_a),
        "watchB": list(watch_b),
        "secondaryActive": bool(secondary_loaded),
        "pairAvailable": bool(secondary_loaded and version_b and watch_b),
        "watchSize": len(watch),
        "ticks": ticks,
        "turnTotals": totals,
        "lastGateReason": last_gate_reason,
        "journalReasons": _journal_reasons(runtime.worker),
        "marketRegime": market_regime,
        "stopReason": stop_reason,
        "priceSources": snapshot.sources(),
        "minCyclesPerStrategy": int(args.min_cycles),
        "level": str(args.level),
        "sample": _progress_row(readiness, prices=prices, watch=len(watch), ticks=ticks),
        "readiness": readiness.as_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account-id", default=None, help="cuenta PAPER existente (si falta, se crea)"
    )
    parser.add_argument(
        "--watch", default=None, help="instrumentos separados por coma (si falta, catálogo)"
    )
    parser.add_argument(
        "--watch-size", type=int, default=20, help="tamaño del watch derivado del catálogo"
    )
    parser.add_argument(
        "--min-bars",
        type=int,
        default=60,
        help="barras D1 mínimas por símbolo en el watch derivado (ATR/régimen reales)",
    )
    parser.add_argument(
        "--a-share",
        type=float,
        default=0.5,
        help="fracción del watch asignada a la versión A (el resto a la ACTIVE)",
    )
    parser.add_argument(
        "--version-a", default=None, help="versión de la estrategia determinista (A)"
    )
    parser.add_argument("--interval-seconds", type=float, default=60.0, help="espera entre ticks")
    parser.add_argument(
        "--max-ticks", type=int, default=0, help="tope de ticks (0 = hasta interrupción)"
    )
    parser.add_argument(
        "--decider-refresh-seconds",
        type=float,
        default=300.0,
        help="cada cuánto se recarga la versión B (barras frescas)",
    )
    parser.add_argument(
        "--report-every", type=int, default=10, help="ticks entre informes de progreso"
    )
    parser.add_argument(
        "--stop-when-ready",
        action="store_true",
        help="termina en cuanto se alcanza el nivel pedido",
    )
    parser.add_argument("--level", choices=("producer", "evidence"), default="evidence")
    parser.add_argument("--min-cycles", type=int, default=_DEFAULT_MIN_CYCLES)
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument("--json", action="store_true", help="emite el payload como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="solo diagnostica el régimen de MERCADO del watch y NO escribe nada",
    )
    args = parser.parse_args(argv)

    if int(args.min_cycles) <= 0:
        print("# uso incorrecto: --min-cycles debe ser > 0", file=sys.stderr)
        return 1
    if int(args.watch_size) <= 0:
        print("# uso incorrecto: --watch-size debe ser > 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        evidence = asyncio.run(_run(args))
    except KeyboardInterrupt:  # pragma: no cover — parada del operador.
        print("\n# interrumpido por el operador: se declara sin veredicto final", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 — sin PostgreSQL/mercado no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo ejercitar el forward ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    if args.json:
        print(payload)
    elif evidence.get("mode") == "preflight":
        _print_preflight(evidence)
    else:
        print("PAPER FORWARD · MARKET MATERIAL (V2.76 · AUTO-MATERIAL-4)")
        print("-" * 52)
        print(f"account                        {evidence['account']}")
        print(f"watch                          {evidence['watchSize']}")
        print(f"version A (determinista)       {evidence['versionA']}  ({len(evidence['watchA'])})")
        print(
            f"version B (ACTIVE)             "
            f"{evidence['versionB'] or 'AUSENTE'}  ({len(evidence['watchB'])})"
        )
        print(f"ticks                          {evidence['ticks']}")
        print(f"turn totals                    {evidence['turnTotals']}")
        print(f"par de versiones               {'SI' if evidence['pairAvailable'] else 'NO'}")
        print(f"verdict                        {evidence['sample']['verdict']}")
        print(f"measurable cycles              {evidence['sample']['measurableCycles']}")
        print(
            f"max measurable/version         {evidence['sample']['maxMeasurableCyclesPerVersion']}"
        )
        print("Allocation                     FROZEN")
        for blocker in evidence["sample"]["blockers"]:
            print(f"  - {blocker}")
        print(
            "\n# NOTA: la diversidad de cubos exige TIEMPO REAL; un solo tick no puede cerrar P3-2.",
            file=sys.stderr,
        )

    if evidence.get("mode") == "preflight":
        allowed = bool(evidence["marketRegime"]["entriesAllowedLong"])
        print(
            f"# preflight: entradas LONG {'PERMITIDAS' if allowed else 'VETADAS'} "
            f"(eje {evidence['marketRegime']['operationalRegime']}); no se escribió nada",
            file=sys.stderr,
        )
        return 0 if allowed else 2

    if evidence["readiness"]["verdict"] == "EVIDENCE_READY":
        verdict_level = "evidence"
    elif evidence["readiness"]["producerReady"]:
        verdict_level = "producer"
    else:
        verdict_level = "blocked"
    order = {"blocked": 0, "producer": 1, "evidence": 2}
    if order[verdict_level] >= order[str(args.level)]:
        print(
            f"# nivel '{args.level}' alcanzado (nivel medido: {verdict_level})",
            file=sys.stderr,
        )
        return 0
    print(
        f"# BLOQUEADO: nivel '{args.level}' NO alcanzado (nivel medido: {verdict_level}); motivos: "
        + "; ".join(evidence["sample"]["blockers"]),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
