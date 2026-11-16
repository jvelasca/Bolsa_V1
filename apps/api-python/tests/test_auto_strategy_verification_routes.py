"""ADR-050 — contrato HTTP de la verificación periódica de estrategia.

Hermético (sin PostgreSQL): se sustituyen el alcance de cuenta, el universo declarado, el
repositorio durable y la sesión. Los artefactos as-run se escriben en ``tmp_path``.

Lo que se blinda aquí:

* El perfil se emite **pre-registrado y hasheado** y ``activationAllowed`` es siempre ``False``.
* Sin universo declarado no hay perfil ni veredicto: se declara el hueco (``409``), no se inventa.
* Sin épocas medidas no se sella nada (``409``); una época ya sellada con otra medición ``409``.
* El ledger filtra por desenlace y por **calidad de decisión** (ejes distintos).
* La huella de medición no depende de ``meta.generatedAt``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_strategy_verification as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.main import create_app
from bolsa_application.dia_d_artifacts import as_run_artifact_path_in
from bolsa_infrastructure.database.repositories.strategy_verification_repository import (
    SealedVerificationRunConflictError,
)


@dataclass
class _Run:
    account_id: str
    profile_id: str
    profile_hash: str
    kind: str
    day: str
    to_day: str
    measurement_hash: str
    verdict: str
    strategy_version: str | None
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": f"run-{self.day}",
            "accountId": self.account_id,
            "profileId": self.profile_id,
            "profileHash": self.profile_hash,
            "kind": self.kind,
            "day": self.day,
            "toDay": self.to_day,
            "measurementHash": self.measurement_hash,
            "verdict": self.verdict,
            "strategyVersion": self.strategy_version,
            "payload": self.payload,
            "createdAt": "2026-11-14T00:00:00+00:00",
        }


class _FakeRepo:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict
        self.runs: list[_Run] = []
        self.upserts: list[dict[str, Any]] = []

    async def upsert_run(self, **kwargs: Any) -> _Run:
        self.upserts.append(kwargs)
        if self.conflict:
            raise SealedVerificationRunConflictError("época sellada con otra medición")
        run = _Run(
            account_id=kwargs["account_id"],
            profile_id=kwargs["profile_id"],
            profile_hash=kwargs["profile_hash"],
            kind=kwargs["kind"],
            day=kwargs["day"],
            to_day=kwargs["to_day"],
            measurement_hash=kwargs["measurement_hash"],
            verdict=kwargs["verdict"],
            strategy_version=kwargs.get("strategy_version"),
            payload=dict(kwargs.get("payload") or {}),
        )
        self.runs.append(run)
        return run

    async def latest(self, *, account_id: str, profile_id: str | None = None):
        rows = [r for r in self.runs if r.account_id == account_id]
        return rows[-1] if rows else None

    async def list_runs(
        self,
        *,
        account_id: str,
        profile_id: str | None = None,
        kind: str | None = None,
        limit: int = 200,
    ):
        rows = [
            r
            for r in self.runs
            if r.account_id == account_id
            and (profile_id is None or r.profile_id == profile_id)
            and (kind is None or r.kind == kind)
        ]
        return tuple(rows[-max(1, int(limit)) :])


class _Session:
    async def commit(self) -> None:
        return None


def _artifact(
    day: str,
    *,
    to_day: str,
    account: str = "acc",
    generated_at: str = "2026-11-14T00:00:00+00:00",
    ledger: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = ledger if ledger is not None else []
    return {
        "engine": "dia-d-as-run-v1",
        "day": day,
        "toDay": to_day,
        "account": account,
        "status": "measured",
        "measured": True,
        "costBps": 32.0,
        "startingState": {"legs": 1, "instruments": ["AAA"], "cashOnly": False},
        "arms": [
            {
                "arm": "as_run",
                "measured": True,
                "reason": None,
                "realizedR": 1.25,
                "returnPct": 1.1,
                "unrealizedR": 0.4,
                "cycles": 1,
                "ledger": rows,
                "pnlCurrency": 100.0,
                "maeR": -0.4,
                "mfeR": 2.0,
                "capture": 0.62,
            },
            {
                "arm": "hold_structural",
                "measured": True,
                "reason": None,
                "realizedR": 0.9,
                "returnPct": 0.8,
                "unrealizedR": 0.0,
                "cycles": 1,
                "ledger": [],
            },
        ],
        "gaps": [],
        "hash": f"artifact-hash-{day}-{generated_at}",
        "meta": {
            "account": account,
            "bump": "v2.11.209",
            "generatedAt": generated_at,
            "stateSource": "sim_auto_positions",
        },
    }


def _write(tmp_path, artifact: dict[str, Any], *, account: str = "acc") -> None:
    path = as_run_artifact_path_in(tmp_path, str(artifact["day"]), account)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact), encoding="utf-8")


def _app(repo: _FakeRepo, *, scope: str | None, universe: tuple[str, ...]):  # noqa: ANN202
    app = create_app()

    async def _session():  # noqa: ANN202
        yield _Session()

    async def _scope(_request: Any, _account_id: Any) -> str | None:  # noqa: ANN202
        return scope

    async def _universe(_session: Any, *, account_id: str) -> tuple[str, ...]:  # noqa: ANN202
        return universe

    app.dependency_overrides[get_db_session] = _session
    route.resolve_account_scope_or_default = _scope  # type: ignore[assignment]
    route._declared_universe = _universe  # type: ignore[assignment]
    route.SqlAlchemyStrategyVerificationRepository = lambda _session: repo  # type: ignore[assignment]
    return app


async def _request(app, method: str, path: str, **kwargs: Any):  # noqa: ANN001, ANN202
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


@pytest.fixture
def artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("DIA_D_AS_RUN_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_profile_without_declared_universe_is_declared_not_invented(
    artifacts, monkeypatch
) -> None:
    app = _app(_FakeRepo(), scope="acc", universe=())
    body = (await _request(app, "GET", "/api/auto/strategy-verification/profile")).json()
    assert body["available"] is False
    assert body["activationAllowed"] is False
    assert body["notes"] == ["no_declared_universe"]


@pytest.mark.asyncio
async def test_profile_is_preregistered_and_never_activates(artifacts) -> None:
    app = _app(_FakeRepo(), scope="acc", universe=("AAA", "BBB"))
    body = (await _request(app, "GET", "/api/auto/strategy-verification/profile")).json()
    assert body["available"] is True
    assert body["activationAllowed"] is False
    assert len(body["profileHash"]) == 64
    assert body["profile"]["universeInstruments"] == ["AAA", "BBB"]
    assert body["profile"]["samples"]["minCohortSamples"] == 12
    assert body["profile"]["decision"]["allowAutoActivation"] is False


@pytest.mark.asyncio
async def test_profile_without_scope_is_fail_closed(artifacts) -> None:
    app = _app(_FakeRepo(), scope=None, universe=("AAA",))
    body = (await _request(app, "GET", "/api/auto/strategy-verification/profile")).json()
    assert body["available"] is False
    assert body["notes"] == ["no_account_scope"]


@pytest.mark.asyncio
async def test_recompute_without_universe_conflicts(artifacts) -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc", universe=())
    response = await _request(app, "POST", "/api/auto/strategy-verification", json={})
    assert response.status_code == 409
    assert "no_declared_universe" in response.json()["detail"]
    assert repo.upserts == []


@pytest.mark.asyncio
async def test_recompute_without_measured_epochs_conflicts(artifacts) -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc", universe=("AAA",))
    response = await _request(app, "POST", "/api/auto/strategy-verification", json={})
    assert response.status_code == 409
    assert "no_measured_epochs" in response.json()["detail"]
    assert repo.upserts == []


@pytest.mark.asyncio
async def test_recompute_seals_an_advisory_verdict(artifacts) -> None:
    _write(artifacts, _artifact("2026-01-05", to_day="2026-01-30"))
    _write(artifacts, _artifact("2026-01-30", to_day="2026-02-27"))
    repo = _FakeRepo()
    app = _app(repo, scope="acc", universe=("AAA",))

    response = await _request(app, "POST", "/api/auto/strategy-verification", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["activationAllowed"] is False
    assert body["verdict"]["activationAllowed"] is False
    assert body["verdict"]["verdict"] in {
        "continue",
        "watch",
        "relab",
        "promote_requires_human",
        "insufficient_sample",
        "inconclusive_version_change",
    }
    assert body["run"]["kind"] == "epoch"
    assert body["run"]["day"] == "2026-01-05"
    assert body["run"]["toDay"] == "2026-02-27"
    assert body["run"]["measurementHash"] == body["verdict"]["measurementHash"]
    assert len(repo.upserts) == 1


@pytest.mark.asyncio
async def test_recompute_never_counts_overlapping_epochs(artifacts) -> None:
    # La segunda época empieza ANTES del cierre de la primera: es solape y se descarta.
    _write(artifacts, _artifact("2026-01-05", to_day="2026-02-27"))
    _write(artifacts, _artifact("2026-02-10", to_day="2026-03-10"))
    repo = _FakeRepo()
    app = _app(repo, scope="acc", universe=("AAA",))

    body = (await _request(app, "POST", "/api/auto/strategy-verification", json={})).json()
    assert body["run"]["day"] == "2026-01-05"
    assert body["run"]["toDay"] == "2026-02-27"
    assert len(body["verdict"]["epochs"]) == 1


@pytest.mark.asyncio
async def test_recompute_declares_conflict_on_a_sealed_epoch(artifacts) -> None:
    _write(artifacts, _artifact("2026-01-05", to_day="2026-01-30"))
    repo = _FakeRepo(conflict=True)
    app = _app(repo, scope="acc", universe=("AAA",))
    response = await _request(app, "POST", "/api/auto/strategy-verification", json={})
    assert response.status_code == 409
    assert "otra medición" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_requires_scope_and_declares_no_history(artifacts) -> None:
    app = _app(_FakeRepo(), scope="acc", universe=("AAA",))
    body = (await _request(app, "GET", "/api/auto/strategy-verification")).json()
    assert body["available"] is False
    assert body["activationAllowed"] is False
    assert body["notes"] == ["no_verification_runs"]
    assert body["runs"] == []


@pytest.mark.asyncio
async def test_history_rejects_unknown_kind(artifacts) -> None:
    app = _app(_FakeRepo(), scope="acc", universe=("AAA",))
    response = await _request(
        app, "GET", "/api/auto/strategy-verification/history?kind=intraday"
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_ledger_filters_by_outcome_and_quality(artifacts) -> None:
    ledger = [
        {
            "cycleId": "c1",
            "arm": "as_run",
            "instrumentId": "AAA",
            "outcome": "win",
            "decisionQuality": "consistent",
            "netR": 1.1,
        },
        {
            "cycleId": "c2",
            "arm": "as_run",
            "instrumentId": "BBB",
            "outcome": "loss",
            "decisionQuality": "consistent",
            "netR": -1.0,
        },
        {
            "cycleId": "c3",
            "arm": "as_run",
            "instrumentId": "CCC",
            "outcome": "open",
            "decisionQuality": "unmeasured",
            "netR": None,
        },
    ]
    _write(artifacts, _artifact("2026-01-05", to_day="2026-01-30", ledger=ledger))
    app = _app(_FakeRepo(), scope="acc", universe=("AAA",))

    all_rows = (
        await _request(
            app, "GET", "/api/auto/strategy-verification/ledger?day=2026-01-05"
        )
    ).json()
    assert all_rows["available"] is True
    assert len(all_rows["rows"]) == 3

    losses = (
        await _request(
            app, "GET", "/api/auto/strategy-verification/ledger?day=2026-01-05&outcome=loss"
        )
    ).json()
    assert [row["cycleId"] for row in losses["rows"]] == ["c2"]

    consistent = (
        await _request(
            app,
            "GET",
            "/api/auto/strategy-verification/ledger?day=2026-01-05&quality=consistent",
        )
    ).json()
    assert [row["cycleId"] for row in consistent["rows"]] == ["c1", "c2"]

    by_instrument = (
        await _request(
            app,
            "GET",
            "/api/auto/strategy-verification/ledger?day=2026-01-05&instrument=CCC",
        )
    ).json()
    assert [row["cycleId"] for row in by_instrument["rows"]] == ["c3"]


@pytest.mark.asyncio
async def test_ledger_rejects_unknown_outcome(artifacts) -> None:
    app = _app(_FakeRepo(), scope="acc", universe=("AAA",))
    response = await _request(
        app, "GET", "/api/auto/strategy-verification/ledger?day=2026-01-05&outcome=draw"
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_ledger_without_artifact_is_fail_closed(artifacts) -> None:
    app = _app(_FakeRepo(), scope="acc", universe=("AAA",))
    body = (
        await _request(
            app, "GET", "/api/auto/strategy-verification/ledger?day=2026-01-05"
        )
    ).json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]


@pytest.mark.asyncio
async def test_ledger_never_serves_another_accounts_artifact(artifacts) -> None:
    _write(artifacts, _artifact("2026-01-05", to_day="2026-01-30", account="otra"), account="otra")
    app = _app(_FakeRepo(), scope="acc", universe=("AAA",))
    body = (
        await _request(
            app, "GET", "/api/auto/strategy-verification/ledger?day=2026-01-05"
        )
    ).json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]


@pytest.mark.asyncio
async def test_measurement_hash_ignores_generated_at(artifacts) -> None:
    app = _app(_FakeRepo(), scope="acc", universe=("AAA",))
    _write(
        artifacts,
        _artifact("2026-01-05", to_day="2026-01-30", generated_at="2026-01-30T18:00:00+00:00"),
    )
    first = (
        await _request(
            app, "GET", "/api/auto/strategy-verification/measurement-hash?day=2026-01-05"
        )
    ).json()
    _write(
        artifacts,
        _artifact("2026-01-05", to_day="2026-01-30", generated_at="2026-02-01T07:30:00+00:00"),
    )
    second = (
        await _request(
            app, "GET", "/api/auto/strategy-verification/measurement-hash?day=2026-01-05"
        )
    ).json()
    assert first["measurementHash"] == second["measurementHash"]
    # El hash del ARTEFACTO sí cambia: por eso no sirve como identidad de medición.
    assert first["artifactHash"] != second["artifactHash"]


@pytest.mark.asyncio
async def test_recompute_measurement_hash_is_reproducible_across_replays(artifacts) -> None:
    repo = _FakeRepo()
    app = _app(repo, scope="acc", universe=("AAA",))
    _write(
        artifacts,
        _artifact("2026-01-05", to_day="2026-01-30", generated_at="2026-01-30T18:00:00+00:00"),
    )
    first = (await _request(app, "POST", "/api/auto/strategy-verification", json={})).json()

    _write(
        artifacts,
        _artifact("2026-01-05", to_day="2026-01-30", generated_at="2026-03-02T09:00:00+00:00"),
    )
    second = (await _request(app, "POST", "/api/auto/strategy-verification", json={})).json()

    assert first["run"]["measurementHash"] == second["run"]["measurementHash"]
