"""R6 — contrato HTTP del experimento TOP DÍA D (``/api/research/dia-d-experiment-top``).

Hermético: sin PostgreSQL, sin ``backtest_runs`` reales. Se doblan la sesión, el
repositorio de evidencia y el de backtests. Cubre el contrato que hace durable el
F-D y las dos formas de rechazo que lo mantienen honesto:

* **201** con la fila insertada (``source='dia_d_experiment_top'``) y un commit;
* **400** si ``asOfDiaD`` es futura o los ranks no son 1..N;
* **422** si el cuerpo trae evidencia del cliente o un ``runId`` que el servidor
  no puede verificar;
* **``data=null``** cuando no hay experimento guardado (hueco declarado).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.research as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.main import create_app
from bolsa_domain.entities.research_evidence import ResearchEvidence

_TODAY = datetime.now(UTC).date()
_PAST = (_TODAY - timedelta(days=30)).isoformat()
_FUTURE = (_TODAY + timedelta(days=3)).isoformat()

_PASS_METRICS = {
    "returnBasis": "net",
    "netReturnPct": 4.2,
    "roundTripCostBps": 32.0,
    "netTradeCount": 40,
    "excessReturnPct": 1.1,
    "expectancyCurrency": 12.5,
}


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:  # pragma: no cover
        return None


class _EvidenceRepo:
    def __init__(self) -> None:
        self.rows: list[ResearchEvidence] = []
        self.inserted: list[dict[str, Any]] = []

    async def insert_evidence(self, **kwargs: Any) -> ResearchEvidence:
        self.inserted.append(kwargs)
        row = ResearchEvidence(
            id=f"ev-{len(self.inserted)}",
            instrument_id=kwargs["instrument_id"],
            level=kwargs["level"],
            source=kwargs["source"],
            evidence_weight=kwargs["evidence_weight"],
            summary=kwargs["summary"],
            created_at="2026-11-16T10:00:00+00:00",
            math_version=kwargs.get("math_version"),
        )
        self.rows.insert(0, row)
        return row

    async def list_evidence(
        self,
        *,
        instrument_id: str | None = None,
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        level: str | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchEvidence], int]:
        rows = [
            row
            for row in self.rows
            if (instrument_id is None or row.instrument_id == instrument_id)
            and (source is None or row.source == source)
            and (level is None or row.level == level)
        ]
        return rows, len(rows)


class _Run:
    def __init__(self, instrument_id: str, metrics: dict[str, Any] | None) -> None:
        self.instrument_id = instrument_id
        self.manifest = {"outputs": {"isMetrics": metrics}}


class _Backtests:
    def __init__(self, runs: dict[str, _Run]) -> None:
        self._runs = runs

    async def get_run(self, run_id: str) -> _Run | None:
        return self._runs.get(run_id)


def _app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repo: _EvidenceRepo | None = None,
    runs: dict[str, _Run] | None = None,
):  # noqa: ANN202
    app = create_app()
    session = _Session()
    evidence = repo or _EvidenceRepo()
    backtests = _Backtests(
        runs
        if runs is not None
        else {
            "run-1": _Run("inst-1", dict(_PASS_METRICS)),
            "run-2": _Run("inst-1", dict(_PASS_METRICS)),
        }
    )

    async def _session():  # noqa: ANN202
        yield session

    app.dependency_overrides[get_db_session] = _session
    monkeypatch.setattr(route, "get_research_evidence_repository", lambda _session: evidence)
    monkeypatch.setattr(route, "SqlAlchemyBacktestRepository", lambda _session: backtests)
    app.state.evidence = evidence
    app.state.session = session
    return app


def _slot(rank: int = 1, **overrides: Any) -> dict[str, Any]:
    slot: dict[str, Any] = {
        "rank": rank,
        "label": f"Estrategia {rank}",
        "stars": 4.0,
        "score": 1.2,
        "source": "optimized",
        "runId": f"run-{rank}",
    }
    slot.update(overrides)
    return slot


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "instrumentId": "inst-1",
        "timeframe": "1d",
        "asOfDiaD": _PAST,
        "slots": [_slot(1), _slot(2)],
        "coachHeadline": "Dos candidatas medidas",
    }
    body.update(overrides)
    return body


async def _post(app, body: dict[str, Any]):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/research/dia-d-experiment-top", json=body)


async def _get(app, params: dict[str, Any]):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/research/dia-d-experiment-top", params=params)


@pytest.mark.asyncio
async def test_post_saves_and_returns_the_experiment(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    response = await _post(app, _body())

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["instrumentId"] == "inst-1"
    assert data["asOfDiaD"] == _PAST
    assert data["level"] == "C"
    assert [slot["rank"] for slot in data["slots"]] == [1, 2]
    assert data["provenance"]["evidenceLevel"] == "lab_validated"
    assert app.state.session.commits == 1
    inserted = app.state.evidence.inserted[0]
    assert inserted["source"] == "dia_d_experiment_top"
    assert inserted["summary"]["sandbox"] is True


@pytest.mark.asyncio
async def test_post_rejects_future_day(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    response = await _post(app, _body(asOfDiaD=_FUTURE))

    assert response.status_code == 400
    assert "asOfDiaD" in response.json()["detail"]
    assert app.state.session.commits == 0


@pytest.mark.asyncio
async def test_post_rejects_non_consecutive_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    response = await _post(app, _body(slots=[_slot(1), _slot(3)]))

    assert response.status_code == 400
    assert "ranks" in response.json()["detail"]


@pytest.mark.asyncio
async def test_post_rejects_client_evidence_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    response = await _post(app, _body(savedAt="2026-01-01T00:00:00+00:00", level="A"))

    # ``extra='forbid'``: el cliente no aporta sello temporal ni nivel.
    assert response.status_code == 422
    assert app.state.evidence.inserted == []


@pytest.mark.asyncio
async def test_post_rejects_unverifiable_run(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    response = await _post(app, _body(slots=[_slot(1, runId="run-fantasma")]))

    assert response.status_code == 422
    assert "run-fantasma" in response.json()["detail"]
    assert app.state.evidence.inserted == []


@pytest.mark.asyncio
async def test_get_declares_the_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    response = await _get(app, {"instrumentId": "inst-1", "timeframe": "1d", "asOfDiaD": _PAST})

    assert response.status_code == 200
    assert response.json() == {"data": None}


@pytest.mark.asyncio
async def test_get_returns_what_was_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert (await _post(app, _body())).status_code == 201

    response = await _get(app, {"instrumentId": "inst-1", "timeframe": "1d", "asOfDiaD": _PAST})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["coachHeadline"] == "Dos candidatas medidas"
    assert data["savedAt"] == "2026-11-16T10:00:00+00:00"

    other_day = await _get(
        app, {"instrumentId": "inst-1", "timeframe": "1d", "asOfDiaD": _TODAY.isoformat()}
    )
    assert other_day.json() == {"data": None}


@pytest.mark.asyncio
async def test_get_requires_instrument(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    response = await _get(app, {"timeframe": "1d", "asOfDiaD": _PAST})

    assert response.status_code == 422
