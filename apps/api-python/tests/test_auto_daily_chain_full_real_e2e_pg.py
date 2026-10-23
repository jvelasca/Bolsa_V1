"""E2E REAL de la cadena diaria AUTO: señal → plan → ciclo → DÍA-D (PostgreSQL + worker).

Qué certifica este fichero (y qué NO)
-------------------------------------
El test integrado ``test_auto_daily_dia_d_chain_integration.py`` conserva su valor como
prueba RÁPIDA, pero usa dobles en los puertos del servicio diario y en el subproceso del
CLI. Ese test no demuestra que el sistema real produzca la cadena; este sí:

1. **Mundo real sembrado** en PostgreSQL con el harness compartido
   (``tests/support/auto_chain_e2e.py``): 231 barras D1 (210 de contexto + ``D`` + 20 de
   horizonte), cuenta PAPER, instrumento con gates fail-closed, TOP vigente, edge y
   estrategia ACTIVE.
2. **Job real ``estudio_daily``** encolado por la ruta ASGI (``POST /auto/ops-jobs``) y
   ejecutado por el worker real (``process_next_auto_ops_job`` → ``RunEstudioDailyOps``):
   el parte publica ``signalId``/``planId`` y sus propuestas quedan DURABLES (migración
   058) con la MISMA identidad.
3. **Productor real** (``AutoSimRuntime``) que ADOPTA la propuesta: reserva → orden →
   fill → posición → salida → cierre con el **mismo** ``signalId``, ``planId`` y
   ``cycle_id``. No se inyecta ninguna fuente de precio ni un decider de prueba.
4. **Job real ``dia_d_value_replay``** (subproceso CLI, sin monkeypatch del motor): el
   artefacto declara ``meta.account``, ``meta.day``, ``meta.watch == [símbolo]`` y
   ``executedDetail`` con los mismos ids durables.
5. **Lectura por la app ASGI real**: ``/api/auto/estudio-daily``,
   ``/api/auto/estudio-chain`` y ``/api/auto/dia-d-replay/{día}/value/{símbolo}``.
   La atribución de la cadena es ``exact`` por IGUALDAD de ids (jamás por ticker).
6. **Contexto y cola**: otro valor que intenta ocupar el hueco recibe la verdad del
   servidor (``slot.active_other_symbol``), cambiar de cuenta/día no devuelve evidencia
   ajena y la relectura es estable.

Gobierno de honestidad
----------------------
Sin PostgreSQL real el test hace ``pytest.skip``; con
``AUTO_DAILY_CHAIN_E2E_PG_REQUIRED=1`` una precondición ausente es **FALLO DURO**, no un
skip silencioso. La venue es PAPER virtual: no se abre el bridge LIVE, no se toca ``main``
ni ningún sello.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from tests.support import auto_chain_e2e as chain

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED_ENV = "AUTO_DAILY_CHAIN_E2E_PG_REQUIRED"

#: Reloj PINNED del harness: ``D = B`` (barra corriente) y ``B-1`` la frontera de decisión.
_CLOCK_DAY = chain.CLOCK_DAY
#: Barras de CONTEXTO que el replay DÍA-D simula antes de ``D`` (``_DEFAULT_HISTORY_DAYS``).
#: Además deben cubrir SMA200: el rating técnico evalúa SMA20/50/200 y el composite pide
#: 260 barras; con menos de ~206 el tramo de tendencia larga no sería calculable y el
#: ``stance=buy`` quedaría fuera de alcance por falta de DATO, no por umbral.
_CONTEXT_BARS = 210
#: Días de horizonte OOS posteriores a ``D`` que el artefacto puede medir.
_HORIZON_DAYS = 20

_DAY_B_OPEN = chain.DAY_B_OPEN
_DAY_B1_OPEN = chain.DAY_B1_OPEN
_LOT = chain.LOT


@pytest.fixture
def daily_chain_pg() -> None:
    """Gate honesto: sin PostgreSQL real se salta (o falla duro con el env de gobierno)."""
    chain.gate_pg(_REQUIRED_ENV)


# ── Reloj, sonda de fill y entorno de la ruta real ─────────────────────────────────


def _prepare(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, str]:
    """Resuelve ``(instrument_id, day_b, closed_as_of)`` con las primitivas del motor."""
    day_b, closed_as_of = chain.route_clock()
    day_b1 = (date.fromisoformat(day_b) + timedelta(days=1)).isoformat()
    instrument_id = chain.filling_instrument_id(
        buy_tick=chain.bar_tick_for_day(day_b),
        sell_tick=chain.bar_tick_for_day(day_b1),
        buy_mid=_DAY_B_OPEN,
        sell_mid=_DAY_B1_OPEN,
    )
    chain.configure_real_route_env(monkeypatch, instrument_id)
    return instrument_id, day_b, closed_as_of


def _horizon_rows(day_b: str, *, days: int = _HORIZON_DAYS) -> list[Any]:
    """Barras del horizonte OOS: ``B+1`` rompe el stop y el resto queda plano.

    ``B+1`` ya la usa el productor real para cerrar por stop estructural; los días
    siguientes existen para que el replay tenga horizonte que medir (sin inventar precio:
    es la serie sembrada, la misma que lee el motor).
    """
    rows: list[Any] = [
        chain.current_bar_row(
            (date.fromisoformat(day_b) + timedelta(days=1)).isoformat(),
            open_=chain.DAY_B1_OPEN,
            close=chain.DAY_B1_CLOSE,
        )
    ]
    price = chain.DAY_B1_CLOSE
    for offset in range(2, days + 1):
        day = (date.fromisoformat(day_b) + timedelta(days=offset)).isoformat()
        rows.append(chain.current_bar_row(day, open_=price, close=price))
    return rows


def _patch_account_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acota las rutas a la cuenta del header (la auth no es el sujeto de este E2E)."""
    import bolsa_api.api.v1.routes.auto_dia_d as dia_d_route
    import bolsa_api.api.v1.routes.auto_estudio_chain as chain_route
    import bolsa_api.api.v1.routes.auto_estudio_daily as daily_route
    import bolsa_api.api.v1.routes.auto_ops_jobs as jobs_route

    async def _scope(request: Any, _account_id: str | None) -> str | None:
        return request.headers.get("x-account-id")

    for module in (dia_d_route, chain_route, daily_route, jobs_route):
        monkeypatch.setattr(module, "resolve_account_scope_or_default", _scope)


def _client(factory: Any) -> AsyncClient:
    """App ASGI real con la MISMA factoría de sesiones del test (sin lifespan)."""
    from bolsa_api.main import create_app

    app = create_app()
    app.state.session_factory = factory
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── La corrida completa ────────────────────────────────────────────────────────────


async def _run_chain(
    *,
    instrument_id: str,
    day_b: str,
    closed_as_of: str,
    dia_d_dir: Path,
) -> dict[str, Any]:
    """Siembra el mundo, ejecuta los jobs REALES y lee la evidencia por la app ASGI."""
    from bolsa_api.background.auto_ops_job_worker import process_next_auto_ops_job
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
        load_active_strategy_decider,
    )

    engine, factory = await chain.open_session_factory()
    account_id: str | None = None
    version_id: str | None = None
    candidate_id: str | None = None
    membership: list[str] | None = None
    engine_id = f"auto-dailychain-{uuid.uuid4().hex[:10]}"
    day_b1 = (date.fromisoformat(day_b) + timedelta(days=1)).isoformat()
    try:
        async with factory() as session:
            account_id = await chain.seed_account(session)
            # Fundamentales del PERFIL anclados a la frontera de decisión: con un
            # ``fetchedAt`` posterior al día del parte el corte PIT los BLOQUEA (look-ahead)
            # y el score fundamental desaparece — comportamiento correcto, pero dejaría el
            # escenario sin la pata que el dato real sí permite medir.
            await chain.seed_instrument(
                session,
                instrument_id,
                fundamentals=chain.strong_fundamentals(
                    f"{closed_as_of}T00:00:00+00:00"
                ),
            )
        version_id, candidate_id = await chain.seed_active_strategy(
            factory, instrument_id=instrument_id
        )
        async with factory() as session:
            await chain.seed_edge_report(
                session, account_id=account_id, strategy_ref=version_id
            )
        # TOP vigente del valor: sin él el dictamen diario se queda en
        # ``review_strategy``/``no_valid_top`` y nunca propone.
        await chain.seed_strategy_top(factory, instrument_id=instrument_id)

        # Mundo del parte: 210 de contexto (SMA200 calculable) + ``D``. El HORIZONTE OOS
        # (``B+1``..``B+20``) se siembra DESPUÉS del job diario: ``propose`` lee la última
        # barra disponible y, si el futuro ya estuviera en la BD, el plan se construiría
        # sobre un precio que aún no existe en la frontera de decisión.
        bars = chain.closed_bar_rows(closed_as_of, closed_bars=_CONTEXT_BARS)
        bars.append(
            chain.current_bar_row(day_b, open_=_DAY_B_OPEN, close=chain.DAY_B_CLOSE)
        )
        await chain.seed_bars(factory, instrument_id, bars)
        membership = await chain.seed_estudio_list(factory, instrument_id)

        async def _read_symbol() -> str:

            from bolsa_infrastructure.database.models.tables import InstrumentRow

            async with factory() as session:
                row = await session.get(InstrumentRow, instrument_id)
                assert row is not None, "el instrumento sembrado debe existir"
                return str(row.symbol)

        symbol = await _read_symbol()
        headers = {"X-Account-Id": account_id}

        # ── 1. Job real estudio_daily por la ruta ASGI + worker real ────────
        client = _client(factory)
        async with client:
            enqueued = await client.post(
                "/api/auto/ops-jobs",
                headers=headers,
                json={"kind": "estudio_daily", "day": closed_as_of, "payload": {}},
            )
            assert enqueued.status_code == 200, enqueued.text
            daily_job_id = enqueued.json()["id"]
            assert enqueued.json()["status"] == "queued"
            # La cola declara la verdad del servidor también al encolar: el hueco ya está
            # ocupado por ESTE trabajo (activo), que es la petición del usuario.
            assert (enqueued.json().get("slot") or {}).get("matchesRequest") is True

            assert await process_next_auto_ops_job(factory) is True

            daily_job = (
                await client.get(f"/api/auto/ops-jobs/{daily_job_id}", headers=headers)
            ).json()
            assert daily_job["status"] == "completed", daily_job.get("error")
            report = daily_job["result"]
            assert report["status"] in {"ok", "partial"}, report
            value = next(
                row for row in report["values"] if row["instrumentId"] == instrument_id
            )
            assert value["status"] == "ok", json.dumps(value, indent=2, default=str)
            # El dictamen llega a ``buy`` porque el DATO lo justifica (SMA200 calculable +
            # fundamentales en corte + TOP vigente). No se rebajó ningún umbral.
            assert value["opinion"]["stance"] == "buy", json.dumps(
                value, indent=2, default=str
            )
            assert (value["indicators"]["io"] or 0) >= 80, value["indicators"]
            handoff = report.get("handoff") or {}
            assert handoff.get("proposed") == 1, handoff
            plan_id = value["strategy"]["planId"]
            signal_id = value["strategy"]["signalId"]
            assert plan_id and signal_id, value["strategy"]
            assert report["universe"]["reconciled"] is True
            # El universo es el ESTUDIO REAL de la BD (la lista es compartida): lo que se
            # exige es que el valor sembrado esté declarado y que NADA falte sin motivo.
            assert instrument_id in report["universe"]["expectedIds"]
            assert report["universe"]["complete"] is True

        # Horizonte OOS: ``B+1`` rompe el stop y el resto queda plano. Se siembra aquí,
        # ya fijado el parte, para que el productor y el replay DÍA-D lean el futuro real.
        horizon = _horizon_rows(day_b)
        await chain.seed_bars(factory, instrument_id, horizon)
        bars.extend(horizon)

        # ── 2. Productor REAL adopta la propuesta y cierra el ciclo ─────────
        holder = {"now": _CLOCK_DAY}
        worker = AutoSimulationWorker(
            engine_id=engine_id,
            account_id=account_id,
            clock=lambda: holder["now"],
        )
        assert worker._v2_current_bar_day() == day_b  # noqa: SLF001 — coherencia.
        assert worker._v2_closed_bar_as_of() == closed_as_of  # noqa: SLF001
        runtime = AutoSimRuntime(
            factory, worker=worker, engine_id=engine_id, account_id=account_id
        )

        async def _install_decider() -> Any:
            decider = await load_active_strategy_decider(
                factory,
                instrument_id=instrument_id,
                watch=(instrument_id,),
                lot_qty=_LOT,
                signal_enabled=True,
                as_of=worker._v2_closed_bar_as_of(),  # noqa: SLF001
            )
            assert decider is not None, "la ruta real exige la ACTIVE de PostgreSQL"
            runtime.set_decider(decider)
            return decider

        await _install_decider()
        opened = False
        for _ in range(chain.ENTRY_TICKS):
            holder["now"] = _CLOCK_DAY
            await _install_decider()
            await runtime.run_tick()
            if worker._open.get(instrument_id, 0) > 0:  # noqa: SLF001
                opened = True
                break

        closed = False
        if opened:
            for _ in range(chain.EXIT_TICKS):
                holder["now"] = datetime.fromisoformat(f"{day_b1}T10:00:00+00:00")
                await _install_decider()
                await runtime.run_tick()
                if worker._open.get(instrument_id, 0) <= 0:  # noqa: SLF001
                    closed = True
                    break

        # Frontera de durabilidad: se cortan TODAS las conexiones del productor y las
        # lecturas se hacen con una conexión NUEVA.
        await engine.dispose()
        engine, factory = await chain.open_session_factory()
        material = await chain.read_material(factory, account_id)
        proposal_row = await _read_proposal(factory, account_id, closed_as_of)

        client = _client(factory)
        async with client:
            # ── 3. Job real DÍA-D por valor (subproceso CLI, sin dobles) ───────
            # DÍA-D se pide para el DÍA DE ENTRADA del ciclo (``B``), no para la vela del
            # parte (``B-1``): el lado EJECUTADO cuenta hechos durables de ``D`` y la
            # apertura nace en ``B``. La distinción es explícita en la UI (origen del día).
            dia_d_job = await client.post(
                "/api/auto/ops-jobs",
                headers=headers,
                json={
                    "kind": "dia_d_value_replay",
                    "day": day_b,
                    "payload": {"symbol": symbol},
                },
            )
            assert dia_d_job.status_code == 200, dia_d_job.text
            dia_d_job_id = dia_d_job.json()["id"]
            # La cola declara la VERDAD del servidor: otro valor no puede ocupar el hueco.
            conflict = await client.post(
                "/api/auto/ops-jobs",
                headers=headers,
                json={
                    "kind": "dia_d_value_replay",
                    "day": day_b,
                    "payload": {"symbol": "OTRO"},
                },
            )
            assert conflict.status_code == 200, conflict.text
            conflict_body = conflict.json()
            assert conflict_body["id"] == dia_d_job_id
            slot = conflict_body.get("slot") or {}
            assert slot["state"] == "active_other_symbol", slot
            assert slot["matchesRequest"] is False
            assert slot["activeSymbol"] == symbol.upper()
            assert slot["requestedSymbol"] == "OTRO"
            assert "OTRO" in slot["message"] and symbol.upper() in slot["message"]

            assert await process_next_auto_ops_job(factory) is True
            dia_d_state = (
                await client.get(f"/api/auto/ops-jobs/{dia_d_job_id}", headers=headers)
            ).json()
            assert dia_d_state["status"] == "completed", dia_d_state.get("error")

            artifact_path = Path(dia_d_dir) / chain_dir(account_id) / "values" / (
                symbol.upper()
            ) / f"dia-d-auto-{day_b}.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            executed_detail = artifact.get("executedDetail") or {}
            meta = artifact.get("meta") or {}

            # ── 4. Lectura por la app ASGI real ────────────────────────────────
            daily_read = await client.get(
                "/api/auto/estudio-daily",
                headers=headers,
                params={"asOf": closed_as_of},
            )
            assert daily_read.status_code == 200, daily_read.text
            daily_body = daily_read.json()
            chain_read = await client.get(
                "/api/auto/estudio-chain",
                headers=headers,
                params={
                    "cycleId": _cycle_id(material),
                    "instrumentId": instrument_id,
                    # El motor del ciclo es el de ESTA corrida (el default de la ruta es
                    # ``auto-sim``): la evidencia se pide con la verdad del productor real.
                    "engineId": engine_id,
                },
            )
            assert chain_read.status_code == 200, chain_read.text
            chain_body = chain_read.json()
            value_read = await client.get(
                f"/api/auto/dia-d-replay/{day_b}/value/{symbol.upper()}",
                headers=headers,
            )
            assert value_read.status_code == 200, value_read.text
            value_body = value_read.json()

            # Contexto: otra cuenta no ve NADA de esta cuenta.
            stranger = await client.get(
                f"/api/auto/dia-d-replay/{day_b}/value/{symbol.upper()}",
                headers={"X-Account-Id": "acc-otra"},
            )
            stranger_daily = await client.get(
                "/api/auto/estudio-daily",
                headers={"X-Account-Id": "acc-otra"},
                params={"asOf": closed_as_of},
            )
            # Día distinto: no hay artefacto (nunca se sirve el anterior como actual).
            other_day = await client.get(
                f"/api/auto/dia-d-replay/{day_b1}/value/{symbol.upper()}",
                headers=headers,
            )
            # Relectura: el artefacto es estable (no depende de estado en memoria).
            reread = await client.get(
                f"/api/auto/dia-d-replay/{day_b}/value/{symbol.upper()}",
                headers=headers,
            )

        return {
            "account_id": account_id,
            "instrument_id": instrument_id,
            "version_id": version_id,
            "candidate_id": candidate_id,
            "engine_id": engine_id,
            "day_b": day_b,
            "day_b1": day_b1,
            "closed_as_of": closed_as_of,
            "symbol": symbol,
            "bars": len(bars),
            "report": report,
            "value": value,
            "plan_id": plan_id,
            "signal_id": signal_id,
            "handoff": handoff,
            "proposal": proposal_row,
            "opened": opened,
            "closed": closed,
            "material": material,
            "artifact": artifact,
            "artifact_path": str(artifact_path),
            "executed_detail": executed_detail,
            "meta": meta,
            "daily_body": daily_body,
            "chain_body": chain_body,
            "value_body": value_body,
            "stranger": stranger.json(),
            "stranger_daily": stranger_daily.json(),
            "other_day": other_day.json(),
            "reread": reread.json(),
            "membership": membership,
        }
    finally:
        await engine.dispose()
        if account_id is not None:
            await chain.cleanup_world(
                account_id=account_id,
                engine_id=engine_id,
                instrument_id=instrument_id,
                version_id=version_id,
                candidate_id=candidate_id,
                estudio_membership=membership,
            )


def chain_dir(account_id: str) -> str:
    from bolsa_application.dia_d_artifacts import account_segment

    return account_segment(account_id)


def _cycle_id(material: dict[str, Any]) -> str:
    fills = [row for row in material["fills"] if row["cycle_id"]]
    assert fills, "el productor real debe dejar fills con ciclo"
    return str(fills[0]["cycle_id"])


async def _read_proposal(
    factory: Any, account_id: str, day: str
) -> dict[str, Any]:
    from bolsa_infrastructure.database.repositories.estudio_daily_proposal_repository import (
        SqlAlchemyEstudioDailyProposalRepository,
    )

    async with factory() as session:
        rows = await SqlAlchemyEstudioDailyProposalRepository(session).list_for_day(
            account_id=account_id, day=day
        )
        assert rows, "el job diario debe dejar la propuesta durable"
        row = rows[0]
        return {
            "id": row.id,
            "status": row.status,
            "decisionId": row.decision_id,
            "signalId": row.signal_id,
            "consumedCycleId": row.consumed_cycle_id,
            "barDate": row.bar_date,
        }


# ── El test que certifica ──────────────────────────────────────────────────────────


def test_signal_plan_cycle_and_dia_d_share_durable_identity(
    daily_chain_pg: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cadena completa con PostgreSQL, worker y CLI REALES, sin skips silenciosos."""
    instrument_id, day_b, closed_as_of = _prepare(monkeypatch)
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path / "dia-d-auto"))
    _patch_account_scope(monkeypatch)

    result = asyncio.run(
        _run_chain(
            instrument_id=instrument_id,
            day_b=day_b,
            closed_as_of=closed_as_of,
            dia_d_dir=tmp_path / "dia-d-auto",
        )
    )

    # ── Universo y parte: cobertura reconciliable y estado terminal por valor ──
    assert result["bars"] == _CONTEXT_BARS + 1 + _HORIZON_DAYS, result["bars"]
    report = result["report"]
    assert report["universe"]["reconciled"] is True
    assert report["universe"]["complete"] is True
    value = result["value"]
    assert value["status"] == "ok"
    assert value["asOfBarDate"] == closed_as_of

    # ── El parte publica la identidad, y la propuesta durable la conserva ──────
    assert result["handoff"]["proposed"] == 1
    assert result["proposal"]["decisionId"] == result["plan_id"]
    assert result["proposal"]["signalId"] == result["signal_id"]
    assert result["proposal"]["barDate"] == closed_as_of

    # ── El productor adoptó la propuesta y nació UN ciclo con esa identidad ────
    assert result["opened"] is True, "la propuesta adoptada debe poder abrir el ciclo"
    assert result["closed"] is True, "el stop estructural cierra el ciclo sembrado"
    material = result["material"]
    cycle_id = _cycle_id(material)
    assert result["proposal"]["status"] == "consumed", result["proposal"]
    assert result["proposal"]["consumedCycleId"] == cycle_id
    assert all(fill["cycle_id"] == cycle_id for fill in material["fills"]), material["fills"]
    assert any(
        row["cycle_id"] == cycle_id and row["side"] == "sell" for row in material["fills"]
    ), "el cierre hereda el MISMO cycle_id"

    # ── El artefacto DÍA-D declara la MISMA identidad durable ──────────────────
    meta = result["meta"]
    detail = result["executed_detail"]
    assert meta["account"] == result["account_id"]
    assert meta["day"] == result["artifact"]["day"], json.dumps(meta, default=str)
    assert meta["watchInstrumentIds"] == [result["instrument_id"]]
    assert [str(item).upper() for item in meta["watch"]] == [result["symbol"].upper()]
    assert detail.get("planId") == result["plan_id"], json.dumps(
        detail, indent=2, default=str
    )
    assert detail.get("signalId") == result["signal_id"], json.dumps(
        detail, indent=2, default=str
    )
    assert detail.get("cycleId") == cycle_id, json.dumps(detail, indent=2, default=str)
    assert (result["artifact"].get("readOnly")) is True
    # El artefacto es del DÍA DE ENTRADA del ciclo (``D``), no de la vela del parte: el
    # lado ejecutado cuenta hechos durables de ``D`` y la apertura nace ahí.
    assert result["artifact"]["day"] == result["day_b"]

    # ── HTTP real: parte, cadena (atribución EXACTA) y artefacto por valor ─────
    daily_body = result["daily_body"]
    assert daily_body["job"]["id"] and daily_body["job"]["status"] == "completed"
    daily_value = next(
        row
        for row in daily_body["report"]["values"]
        if row["instrumentId"] == result["instrument_id"]
    )
    assert daily_value["strategy"]["planId"] == result["plan_id"]

    chain_body = result["chain_body"]
    assert chain_body["available"] is True, chain_body.get("notes")
    value_row = next(
        row
        for row in chain_body["values"]
        if row["instrumentId"] == result["instrument_id"]
    )
    assert value_row["measured"] is True, value_row
    cycles = [row for row in value_row["cycles"] if row.get("cycleId") == cycle_id]
    assert cycles, value_row
    cycle = cycles[0]
    assert cycle["attribution"]["state"] == "exact", cycle["attribution"]
    assert cycle["attribution"]["proposalPlanId"] == result["plan_id"]
    assert cycle["attribution"]["proposalSignalId"] == result["signal_id"]
    assert cycle["dailyProposal"]["planId"] == result["plan_id"]
    assert cycle["dailyProposal"]["signalId"] == result["signal_id"]
    assert cycle["planId"] == result["plan_id"], cycle
    assert cycle["signalId"] == result["signal_id"], cycle

    value_body = result["value_body"]
    assert value_body["available"] is True, value_body.get("notes")
    assert value_body["symbol"] == result["symbol"].upper()
    assert value_body["executedDetail"]["planId"] == result["plan_id"]
    assert value_body["executedDetail"]["signalId"] == result["signal_id"]
    assert value_body["executedDetail"]["cycleId"] == cycle_id

    # ── Contexto: nada ajeno ni anterior se sirve como propio ─────────────────
    assert result["stranger"]["available"] is False
    assert result["stranger"]["notes"] == ["artifact_not_found"]
    assert result["stranger_daily"]["accountId"] == "acc-otra"
    assert result["stranger_daily"]["report"] is None
    assert result["stranger_daily"]["notes"] == ["no_job_for_day"]
    assert result["other_day"]["available"] is False
    assert result["other_day"]["notes"] == ["artifact_not_found"]
    assert result["reread"] == value_body

