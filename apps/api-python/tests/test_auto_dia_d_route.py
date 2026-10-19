"""DÍA-D AUTO — contratos HTTP de la ruta read-only (fail-closed, sin PG).

La ruta solo LEE artefactos JSON; el motor AUTO se ejercita por CLI, nunca por HTTP. Por eso
estos tests no necesitan PostgreSQL: monkeypatchean la resolución de cuenta (aislamiento) y
apuntan el directorio de artefactos a un ``tmp_path``.
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_dia_d as route
from bolsa_api.main import create_app
from bolsa_application.dia_d_artifacts import artifact_path_in


def _artifact(day: str, account: str = "acc") -> dict:
    return {
        "schemaVersion": "dia-d-auto-v1",
        "kind": "DIA_D_AUTO",
        "readOnly": True,
        "day": day,
        "meta": {"account": account, "versionA": "v1"},
        "comparison": [
            {
                "step": "SIGNAL",
                "declared": 1,
                "executed": 1,
                "verdict": "MATCH",
                "measurement": "COMPLETE",
            },
            {
                "step": "FILL",
                "declared": 2,
                "executed": None,
                "verdict": "NOT_MEASURED",
                "measurement": "UNKNOWN",
            },
        ],
        "summary": {"verdict": "PARTIAL", "match": 1, "divergent": 0, "notMeasured": 1, "steps": 2},
        "oos": {
            "closedCount": 1,
            "openCount": 0,
            "realizedRTotal": 1.5,
            "unmeasuredCount": 0,
            "realized": [],
            "open": [],
        },
        "limits": ["sandbox read-only"],
        "executedDetail": {"day": day, "fills": 1},
    }


@pytest.fixture
def app():
    return create_app()


def _write(tmp_path, day: str, account: str = "acc", *, legacy: bool = False) -> None:
    """Escribe el artefacto en el esquema vigente (por cuenta) o en la ruta plana legacy."""
    if legacy:
        path = tmp_path / f"dia-d-auto-{day}.json"
    else:
        path = tmp_path / account / f"dia-d-auto-{day}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_artifact(day, account)), encoding="utf-8")


async def _get(app, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_list_returns_available_days_descending(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-29")
    _write(tmp_path, "2026-09-30")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay")

    assert response.status_code == 200
    body = response.json()
    assert body["readOnly"] is True
    assert body["days"] == ["2026-09-30", "2026-09-29"]


@pytest.mark.asyncio
async def test_get_returns_the_artifact_projection(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay/2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["day"] == "2026-09-30"
    assert body["summary"]["verdict"] == "PARTIAL"
    assert [row["step"] for row in body["steps"]] == ["SIGNAL", "FILL"]
    assert body["oos"]["realizedRTotal"] == 1.5
    assert body["notes"] == []


@pytest.mark.asyncio
async def test_get_missing_artifact_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay/2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]


@pytest.mark.asyncio
async def test_no_account_scope_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30")

    async def _no_scope(_request, _account_id):
        return None

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _no_scope)
    detail = await _get(app, "/api/auto/dia-d-replay/2026-09-30")
    listing = await _get(app, "/api/auto/dia-d-replay")

    assert detail.status_code == 200
    assert detail.json()["available"] is False
    assert detail.json()["notes"] == ["no_account_scope"]
    assert listing.json()["days"] == []
    assert listing.json()["notes"] == ["no_account_scope"]


@pytest.mark.asyncio
async def test_invalid_day_is_declared(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay/not-a-day")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["invalid_day"]


@pytest.mark.asyncio
async def test_account_mismatch_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    # D34-06: una cuenta ajena es INDISTINGUIBLE de inexistente; no se entrega el artefacto.
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30", account="otra-cuenta")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    detail = await _get(app, "/api/auto/dia-d-replay/2026-09-30")
    listing = await _get(app, "/api/auto/dia-d-replay")

    assert detail.status_code == 200
    assert detail.json()["available"] is False
    assert detail.json()["notes"] == ["artifact_not_found"]
    assert detail.json()["steps"] == []
    # El listado tampoco revela el día de otra cuenta.
    assert listing.json()["days"] == []
    assert listing.json()["notes"] == ["no_artifacts"]


@pytest.mark.asyncio
async def test_listing_only_returns_days_of_the_current_account(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-29", account="acc")
    _write(tmp_path, "2026-09-30", account="otra-cuenta")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    body = (await _get(app, "/api/auto/dia-d-replay")).json()
    assert body["days"] == ["2026-09-29"]


@pytest.mark.asyncio
async def test_two_accounts_same_day_have_independent_artifacts(
    app, tmp_path, monkeypatch
) -> None:
    """D1: dos cuentas el mismo día no compiten por el mismo fichero ni se ven entre sí."""
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30", account="acc-1")
    _write(tmp_path, "2026-09-30", account="acc-2")

    async def _scope_acc1(_request, _account_id):
        return "acc-1"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope_acc1)
    body = (
        await _get(app, "/api/auto/dia-d-replay/2026-09-30")
    ).json()
    assert body["available"] is True
    assert body["meta"]["account"] == "acc-1"

    async def _scope_acc2(_request, _account_id):
        return "acc-2"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope_acc2)
    body = (
        await _get(app, "/api/auto/dia-d-replay/2026-09-30")
    ).json()
    assert body["available"] is True
    assert body["meta"]["account"] == "acc-2"


@pytest.mark.asyncio
async def test_legacy_flat_artifact_is_declared_and_owner_only(
    app, tmp_path, monkeypatch
) -> None:
    """La ruta plana histórica solo se sirve a su dueño y se declara como legacy."""
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30", account="acc", legacy=True)

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    body = (await _get(app, "/api/auto/dia-d-replay/2026-09-30")).json()
    assert body["available"] is True
    assert body["notes"] == ["legacy_artifact"]
    assert body["artifactModifiedAt"] is not None
    assert (await _get(app, "/api/auto/dia-d-replay")).json()["days"] == [
        "2026-09-30"
    ]

    async def _other(_request, _account_id):
        return "otra-cuenta"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _other)
    other = (await _get(app, "/api/auto/dia-d-replay/2026-09-30")).json()
    assert other["available"] is False
    assert other["notes"] == ["artifact_not_found"]


@pytest.mark.asyncio
async def test_canonical_artifact_wins_over_legacy(app, tmp_path, monkeypatch) -> None:
    """Si existen ambos, se lee el de la cuenta y NO se etiqueta como legacy."""
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30", account="acc", legacy=True)
    canonical = tmp_path / "acc" / "dia-d-auto-2026-09-30.json"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    payload = _artifact("2026-09-30", "acc")
    payload["summary"]["verdict"] = "MATCH"
    canonical.write_text(json.dumps(payload), encoding="utf-8")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    body = (await _get(app, "/api/auto/dia-d-replay/2026-09-30")).json()
    assert body["available"] is True
    assert body["notes"] == []
    assert body["summary"]["verdict"] == "MATCH"


def test_escritor_y_lector_resuelven_la_misma_raiz(tmp_path, monkeypatch) -> None:
    """El worker que ESCRIBE y la ruta que LEE deben resolver el mismo directorio.

    Falsable: si el worker vuelve a ``_repo_root()`` sin honrar ``DIA_D_AUTO_DIR``, escribe en
    el árbol del repo mientras la API lee del directorio redirigido; el artefacto existe en
    disco y la UI declara ``artifact_not_found`` sin ningún error visible.
    """
    import bolsa_api.background.auto_ops_dia_d as worker

    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    worker_dir = worker.artifacts_dir_for_jobs()
    assert worker_dir == route._artifacts_dir()
    assert (
        artifact_path_in(worker_dir, "2026-09-30", "acc")
        == route._artifact_path("2026-09-30", "acc")
    )

    # Sin override (y con override en blanco) ambos caen en la misma carpeta por defecto.
    monkeypatch.delenv("DIA_D_AUTO_DIR", raising=False)
    assert worker.artifacts_dir_for_jobs() == route._artifacts_dir()
    monkeypatch.setenv("DIA_D_AUTO_DIR", "   ")
    assert worker.artifacts_dir_for_jobs() == route._artifacts_dir()
