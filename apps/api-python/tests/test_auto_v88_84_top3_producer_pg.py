"""V2.88.84 — productor PRODUCTIVO del TOP3 cross-asset (``top3_opportunities``) sobre PG.

Certifica que el TOP3 cross-asset que ``v2.88.82`` dejó SIN escritor ahora se produce en la
ruta real, y que la degradación a scoring histórico deja de ser silenciosa:

* **Bloque A** — ``_v2_persist_top3`` escribe la tabla 052 UNA vez por barra (idempotente
  dentro de la barra) y DECLARA por slot si el score usó evidencia LAB o scoring histórico.
* **Bloque B** — ``AutoSimRuntime.run_tick`` (ruta de producción, sin inyectar el sink)
  compone el sink por sesión/tick y el TOP3 queda LEÍDO por el repositorio: un activo con
  campeón ACTIVE sale sin motivo; uno sin campeón sale con ``scoring_historico_sin_campeon``
  (degradación explícita end-to-end). Si se quita ``top3_opportunity_sink=`` de ``run_tick``,
  el Bloque B se cae.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real/credenciales hace
``pytest.skip``; con ``AUTO_SCHEDULER_PG_REQUIRED=1`` un skip es FALLO DURO. NUNCA abre el
bridge LIVE (venue simulated/paper).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_SCHEDULER_PG_REQUIRED"

# Métricas LAB deterministas del campeón sembrado (ver ``evidence_components``):
#   robustness = media(wfe, dsr, 1 - pbo) = media(0.8, 0.9, 0.9) = 0.866..
#   edge       = robust_score / EDGE_SCALE   = 5.0 / 10.0      = 0.5
_WFE = 0.8
_DSR = 0.9
_PBO = 0.1
_ROBUST_SCORE = 5.0
_REGIME = "trend_up"
_EXPECTED_ROBUSTNESS = round((_WFE + _DSR + (1.0 - _PBO)) / 3.0, 4)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el productor del TOP3 (v2.88.84) no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (productor del TOP3) no disponible: {exc}")


@pytest_asyncio.fixture
async def top3_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (052).
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_instrument(session: AsyncSession, instrument_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    if await session.get(InstrumentRow, instrument_id) is not None:
        return
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"T3{suffix.upper()}",
            yahoo_symbol=f"t3{suffix}",
            name="TOP3 productor",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


async def _seed_champion(session: AsyncSession, *, instrument_id: str) -> dict[str, str]:
    """Siembra un campeón ACTIVE con evidencia LAB (candidata→eval→finalista→activa)."""
    from bolsa_application.strategy_lifecycle_store import (
        ActiveStrategyRecord,
        PostgresStrategyLifecycleStore,
    )
    from bolsa_domain.entities.strategy_lifecycle import (
        PROMOTION_GATES,
        ActiveStrategy,
        GateResult,
        StrategyCandidate,
        StrategyEvaluation,
        StrategyFinalist,
    )

    suffix = uuid.uuid4().hex[:10]
    candidate_id = f"cand-t3-{suffix}"
    version_id = f"ver-t3-{suffix}"

    store = PostgresStrategyLifecycleStore(session)
    await store.save_candidate(
        StrategyCandidate(
            id=candidate_id,
            instrument_id=instrument_id,
            strategy_family="sma",
            params={"fast": 20, "slow": 50},
            data_snapshot_id=f"snap-t3-{suffix}",
        )
    )
    await store.save_evaluation(
        StrategyEvaluation(
            candidate_id=candidate_id,
            score=1.42,
            gates=tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES),
            metrics={
                "instrument_id": instrument_id,
                "robust_score": _ROBUST_SCORE,
                "oos_score": 0.9,
                "wfe": _WFE,
                "dsr": _DSR,
                "pbo": _PBO,
                "regime": _REGIME,
            },
        )
    )
    await store.save_finalist(
        StrategyFinalist(
            candidate_id=candidate_id,
            version_id=version_id,
            name="SMA-20/50",
            definition_hash=f"hash-t3-{suffix}",
            definition={"family": "sma", "instrument_id": instrument_id},
        )
    )
    await store.save_active(
        ActiveStrategyRecord(
            active=ActiveStrategy(
                version_id=version_id,
                candidate_id=candidate_id,
                instrument_id=instrument_id,
                name="SMA-20/50",
                definition={"family": "sma", "instrument_id": instrument_id},
            ),
            promoted_at=datetime.now(UTC).isoformat(),
        )
    )
    return {"candidate_id": candidate_id, "version_id": version_id}


async def _cleanup_champion(factory: async_sessionmaker[AsyncSession], ids: dict[str, str]) -> None:
    from bolsa_infrastructure.database.models.tables import (
        StrategyCandidateRow,
        StrategyEvaluationRow,
        StrategyHealthRow,
        StrategyPromotionRow,
        StrategyVersionRow,
    )

    candidate_id = ids["candidate_id"]
    version_id = ids["version_id"]
    async with factory() as session:
        await session.execute(
            delete(StrategyHealthRow).where(StrategyHealthRow.version_id == version_id)
        )
        await session.execute(
            delete(StrategyPromotionRow).where(StrategyPromotionRow.candidate_id == candidate_id)
        )
        await session.execute(
            delete(StrategyVersionRow).where(StrategyVersionRow.candidate_id == candidate_id)
        )
        await session.execute(
            delete(StrategyEvaluationRow).where(StrategyEvaluationRow.candidate_id == candidate_id)
        )
        await session.execute(
            delete(StrategyCandidateRow).where(StrategyCandidateRow.id == candidate_id)
        )
        await session.commit()


async def _cleanup_instrument(
    factory: async_sessionmaker[AsyncSession], instrument_id: str
) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow

    async with factory() as session:
        await session.execute(delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id))
        await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
        await session.commit()


async def _cleanup_top3(factory: async_sessionmaker[AsyncSession], run_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import Top3OpportunityRow

    async with factory() as session:
        await session.execute(delete(Top3OpportunityRow).where(Top3OpportunityRow.run_id == run_id))
        await session.commit()


# ── Bloque A — el productor escribe UNA foto por barra y DECLARA la procedencia ──


@pytest.mark.asyncio
async def test_persist_top3_writes_once_per_bar_and_declares_provenance(
    top3_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_v2_persist_top3``: escribe la barra una vez e inyecta el motivo por slot."""
    from bolsa_analytics.cognitive.opportunity_ranker import OpportunityScore
    from bolsa_api.background import auto_simulation_worker as w
    from bolsa_application.top3_opportunities import HISTORICAL_SCORING_NO_CHAMPION
    from bolsa_infrastructure.database.repositories.top3_opportunity_repository import (
        SqlAlchemyTop3OpportunityRepository,
    )

    bar = "2026-10-07T00:00:00Z"
    run_id = f"top3-sim-{bar}"
    plan = SimpleNamespace(
        ranked=(
            OpportunityScore(instrument_id="AAA", components={"edge": 0.9}, combined=0.9, rank=1),
            OpportunityScore(instrument_id="BBB", components={"edge": 0.5}, combined=0.5, rank=2),
        )
    )
    worker = w.AutoSimulationWorker(engine_id=f"eng-t3-{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(worker, "_v2_current_bar_start", lambda: bar)

    try:
        async with top3_pg_factory() as session:
            worker._top3_opportunity_sink = w.build_top3_opportunity_sink(session)
            repo = SqlAlchemyTop3OpportunityRepository(session)

            # Sólo AAA tiene campeón ⇒ BBB debe declarar la degradación a scoring histórico.
            await worker._v2_persist_top3(
                plan, regime="trend_up", evidenced_symbols=frozenset({"AAA"})
            )

            rows = await repo.list_for_run(run_id)
            assert [r.rank for r in rows] == [1, 2]
            by_asset = {r.asset_id: r for r in rows}
            assert by_asset["AAA"].reasons == []
            assert by_asset["BBB"].reasons == [HISTORICAL_SCORING_NO_CHAMPION]
            assert all(r.regime == "trend_up" for r in rows)

            # Segunda llamada dentro de la MISMA barra: no-op (una foto por barra).
            await worker._v2_persist_top3(
                plan, regime="trend_up", evidenced_symbols=frozenset({"AAA"})
            )
            assert len(await repo.list_for_run(run_id)) == 2
    finally:
        await _cleanup_top3(top3_pg_factory, run_id)


# ── Bloque B — el runtime PRODUCTIVO cablea el productor (regresión del wiring) ──


@pytest.mark.asyncio
async def test_runtime_writes_top3_with_declared_degradation(
    top3_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``AutoSimRuntime.run_tick`` escribe el TOP3 real: evidencia vs scoring histórico.

    Conduce la ruta REAL sin inyectar el sink (``run_tick`` lo compone). Un activo con campeón
    ACTIVE sale sin motivo y con sus componentes LAB; uno sin campeón sale declarado. Si se
    elimina ``top3_opportunity_sink=`` de ``run_tick``, no hay filas y esto se cae.
    """
    from bolsa_api.background import auto_simulation_worker as w
    from bolsa_application.decision_contract import DecisionPackage
    from bolsa_application.top3_opportunities import HISTORICAL_SCORING_NO_CHAMPION
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.top3_opportunity_repository import (
        SqlAlchemyTop3OpportunityRepository,
    )

    ev_id = f"inst-ev-{uuid.uuid4().hex[:10]}"
    nov_id = f"inst-nov-{uuid.uuid4().hex[:10]}"
    engine_id = f"eng-t3-{uuid.uuid4().hex[:10]}"
    ids: dict[str, str] = {}
    account_id: str | None = None
    run_id = ""

    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", f"{ev_id},{nov_id}")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")

    def _buy_decider(symbol: str) -> Any:
        # Sólo las señales de ENTRADA (``BUY``) compiten por el ranking (``plan_v2_tick``
        # filtra ``action == "BUY"``); un ``HOLD`` no llega al TOP3. El paquete entra en
        # ``packages``/ranking aunque el motor luego lo vete (la foto del TOP3 existe igual).
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=100)

    try:
        async with top3_pg_factory() as session:
            await _seed_instrument(session, ev_id)
            await _seed_instrument(session, nov_id)
            ids = await _seed_champion(session, instrument_id=ev_id)
            scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"T3-{uuid.uuid4().hex[:8]}", initial_deposit=100_000.0
            )
            await session.commit()
            account_id = scope.account.id

        worker = w.AutoSimulationWorker(
            engine_id=engine_id, account_id=account_id, decider=_buy_decider
        )
        runtime = w.AutoSimRuntime(
            top3_pg_factory,
            worker=worker,
            engine_id=engine_id,
            account_id=account_id,
        )
        await runtime.run_tick()

        async with top3_pg_factory() as session:
            repo = SqlAlchemyTop3OpportunityRepository(session)
            run_id, rows = await repo.latest()

        assert run_id.startswith(f"top3-{account_id}-"), (
            "el runtime debe escribir el TOP3 anclado a la cuenta y la barra"
        )
        by_asset = {r.asset_id: r for r in rows}
        assert ev_id in by_asset, "el activo con campeón ACTIVE debe estar en el TOP3"
        assert nov_id in by_asset, "el activo sin campeón también compite (scoring histórico)"
        assert by_asset[ev_id].reasons == [], "con evidencia LAB no se declara degradación"
        assert by_asset[ev_id].components["robustness"] == pytest.approx(
            _EXPECTED_ROBUSTNESS, abs=1e-4
        ), "los componentes LAB deben llegar a la fila persistida"
        assert by_asset[nov_id].reasons == [HISTORICAL_SCORING_NO_CHAMPION], (
            "sin campeón ACTIVE la degradación a scoring histórico es EXPLÍCITA"
        )
    finally:
        from bolsa_infrastructure.database.models.tables import (
            SimAutoPositionRow,
            SimConsumedSignalRow,
        )

        if account_id is not None:
            async with top3_pg_factory() as session:
                await session.execute(
                    delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
                )
                await session.execute(
                    delete(SimConsumedSignalRow).where(
                        SimConsumedSignalRow.account_id == account_id
                    )
                )
                await session.commit()
        if run_id:
            await _cleanup_top3(top3_pg_factory, run_id)
        if ids:
            await _cleanup_champion(top3_pg_factory, ids)
        await _cleanup_instrument(top3_pg_factory, ev_id)
        await _cleanup_instrument(top3_pg_factory, nov_id)
