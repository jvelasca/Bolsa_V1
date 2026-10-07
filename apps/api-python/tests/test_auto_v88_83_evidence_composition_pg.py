"""V2.88.83 — costura PRODUCTIVA de la evidencia de estrategia (TOP3) sobre PG real.

Certifica que la evidencia LAB del campeón ACTIVE por instrumento **llega al AUTO real**,
no solo a los tests:

* ``_compose_evidence_source(session)`` construye una ``StrategyEvidenceSource`` real sobre
  ``PostgresStrategyLifecycleStore`` (campeón ACTIVE + evaluación + salud) y el adaptador
  ``opportunity_evidence_adapter`` la traduce a los 7 componentes del ``OpportunityScore``.
* ``AutoSimRuntime.run_tick`` compone esa fuente por sesión/tick (ruta de producción,
  ``evidence_source=None``) y el ``evidence`` que recibe ``plan_v2_tick`` NO es ``None`` y
  contiene el instrumento. Si se elimina la línea ``evidence_source=...`` del runtime, el
  Bloque B se pone rojo: es la prueba de regresión del wiring.

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
_EXPECTED_EDGE = 0.5


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la costura de evidencia (v2.88.83) no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (costura de evidencia) no disponible: {exc}")


@pytest_asyncio.fixture
async def evidence_pg_factory() -> async_sessionmaker[AsyncSession]:
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
            symbol=f"EV{suffix.upper()}",
            yahoo_symbol=f"EV{suffix}",
            name="Evidencia TOP3",
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
    """Siembra un campeón ACTIVE con evidencia LAB (candidata→eval→finalista→activa).

    Reproduce la secuencia certificada de ``test_strategy_lifecycle_pg``: ``get_active``
    localiza la activa por la fila de promoción que escribe ``save_active``, y la versión
    inmutable la aporta ``save_finalist``.
    """
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
    candidate_id = f"cand-ev-{suffix}"
    version_id = f"ver-ev-{suffix}"

    store = PostgresStrategyLifecycleStore(session)
    await store.save_candidate(
        StrategyCandidate(
            id=candidate_id,
            instrument_id=instrument_id,
            strategy_family="sma",
            params={"fast": 20, "slow": 50},
            data_snapshot_id=f"snap-ev-{suffix}",
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
            definition_hash=f"hash-ev-{suffix}",
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
    return {"candidate_id": candidate_id, "version_id": version_id, "instrument_id": instrument_id}


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


# ── Bloque A — el adaptador productivo mapea el campeón ACTIVE a componentes ─────


@pytest.mark.asyncio
async def test_compose_evidence_source_maps_active_champion(
    evidence_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``_compose_evidence_source`` sobre PG real: 7 componentes + fail-closed sin ACTIVE."""
    from bolsa_api.background.auto_simulation_worker import _compose_evidence_source

    instrument_id = f"inst-ev-{uuid.uuid4().hex[:10]}"
    ids: dict[str, str] = {}
    try:
        async with evidence_pg_factory() as session:
            await _seed_instrument(session, instrument_id)
            ids = await _seed_champion(session, instrument_id=instrument_id)

            source = _compose_evidence_source(session)
            await source.refresh([instrument_id], regime=_REGIME)

            components = source.components_for(instrument_id)
            assert components is not None, "el campeón ACTIVE debe producir evidencia"
            assert components["robustness"] == pytest.approx(_EXPECTED_ROBUSTNESS, abs=1e-4)
            assert components["edge"] == pytest.approx(_EXPECTED_EDGE, abs=1e-4)
            assert components["regime_fit"] == pytest.approx(1.0), "régimen coincidente ⇒ 1.0"
            # Fail-closed: un instrumento sin ACTIVE NO produce evidencia (nunca se inventa).
            assert source.components_for(f"sin-active-{uuid.uuid4().hex[:6]}") is None
    finally:
        if ids:
            await _cleanup_champion(evidence_pg_factory, ids)
        await _cleanup_instrument(evidence_pg_factory, instrument_id)


# ── Bloque B — el runtime PRODUCTIVO compone la fuente y la inyecta en plan_v2_tick ──


@pytest.mark.asyncio
async def test_runtime_composes_evidence_and_feeds_plan_v2_tick(
    evidence_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regresión del wiring: si se quita ``evidence_source=`` de ``run_tick``, esto se cae.

    Conduce la ruta REAL (``AutoSimRuntime.run_tick`` → ``real_turn``) con
    ``evidence_source=None``. Espía la composición productiva y el ``plan_v2_tick`` del hot
    path: el ``evidence`` recibido debe existir y contener el instrumento con sus componentes.
    """
    from bolsa_api.background import auto_simulation_worker as w
    from bolsa_application.decision_contract import DecisionPackage
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    instrument_id = f"inst-ev-{uuid.uuid4().hex[:10]}"
    engine_id = f"eng-ev-{uuid.uuid4().hex[:10]}"
    ids: dict[str, str] = {}
    account_id: str | None = None
    calls: dict[str, Any] = {"compose": 0, "evidence": None}

    real_compose = w._compose_evidence_source
    real_plan = w.plan_v2_tick

    def _spy_compose(session: Any) -> Any:
        calls["compose"] += 1
        return real_compose(session)

    def _spy_plan(*args: Any, **kwargs: Any) -> Any:
        captured = kwargs.get("evidence")
        if captured is not None:
            calls["evidence"] = captured
        return real_plan(*args, **kwargs)

    monkeypatch.setattr(w, "_compose_evidence_source", _spy_compose)
    monkeypatch.setattr(w, "plan_v2_tick", _spy_plan)

    # Watch acotado al instrumento sembrado + motor V2 SIM-ONLY (nunca LIVE).
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")

    def _hold_decider(symbol: str) -> Any:
        # Paquete NO-None: entra en ``packages`` (aunque no opere) y basta para que el
        # look-up de evidencia del instrumento sea observable en ``plan_v2_tick``.
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    try:
        async with evidence_pg_factory() as session:
            await _seed_instrument(session, instrument_id)
            ids = await _seed_champion(session, instrument_id=instrument_id)
            scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"EV-{uuid.uuid4().hex[:8]}", initial_deposit=100_000.0
            )
            await session.commit()
            account_id = scope.account.id

        worker = w.AutoSimulationWorker(
            engine_id=engine_id,
            account_id=account_id,
            decider=_hold_decider,
        )
        runtime = w.AutoSimRuntime(
            evidence_pg_factory,
            worker=worker,
            engine_id=engine_id,
            account_id=account_id,
        )
        await runtime.run_tick()

        assert calls["compose"] >= 1, "el runtime debe componer la evidencia por sesión/tick"
        evidence = calls["evidence"]
        assert evidence is not None, "plan_v2_tick debe recibir evidencia (wiring productivo)"
        assert instrument_id in evidence, "el instrumento del campeón debe estar en el lookup"
        assert evidence[instrument_id]["robustness"] == pytest.approx(
            _EXPECTED_ROBUSTNESS, abs=1e-4
        )
        assert evidence[instrument_id]["edge"] == pytest.approx(_EXPECTED_EDGE, abs=1e-4)
    finally:
        from bolsa_infrastructure.database.models.tables import (
            SimAutoPositionRow,
            SimConsumedSignalRow,
        )

        if account_id is not None:
            async with evidence_pg_factory() as session:
                await session.execute(
                    delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
                )
                await session.execute(
                    delete(SimConsumedSignalRow).where(
                        SimConsumedSignalRow.account_id == account_id
                    )
                )
                await session.commit()
        if ids:
            await _cleanup_champion(evidence_pg_factory, ids)
        await _cleanup_instrument(evidence_pg_factory, instrument_id)
