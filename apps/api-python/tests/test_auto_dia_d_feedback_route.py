"""DÍA-D AUTO · FEEDBACK — contratos HTTP de la ruta read-only (fail-closed, sin PG).

La ruta solo LEE artefactos JSON; el motor AUTO se ejercita por CLI, nunca por HTTP. Por eso
estos tests no necesitan PostgreSQL: monkeypatchean la resolución de cuenta (aislamiento) y
apuntan el directorio de artefactos a un ``tmp_path``.
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_dia_d_feedback as route
from bolsa_api.main import create_app


def _artifact(window: str, account: str = "acc") -> dict:
    day_from, day_to = window.split("_")
    return {
        "schemaVersion": "dia-d-feedback-v1",
        "kind": "DIA_D_AUTO_FEEDBACK",
        "readOnly": True,
        "window": {"from": day_from, "to": day_to, "days": [day_from, day_to]},
        "matrixBasis": "entryDay",
        "summary": {
            "values": 1,
            "oosSupported": 0,
            "mixed": 0,
            "refuted": 1,
            "notMeasured": 0,
            "measuredValues": 1,
            "byEvidenceQuality": {
                "NOT_MEASURED": 0,
                "PRELIMINARY": 1,
                "SUPPORTED": 0,
                "STRONG": 0,
            },
            "errors": {"SOFTWARE": 1, "OPERATIONAL": 0, "DATA": 0, "total": 1},
        },
        "values": [
            {
                "symbol": "AAA",
                "verdict": "REFUTED",
                "verdictReason": "software_divergence",
                "evidenceQuality": "PRELIMINARY",
                "expectancyR": 0.5,
                "hitRate": 0.6,
                "measuredCycles": 5,
                "daysCovered": 1,
                "windowDays": 2,
                "realizedRTotal": 2.5,
                "errors": {"SOFTWARE": 1, "OPERATIONAL": 0, "DATA": 0, "total": 1},
                "errorTotal": 1,
                "byDay": {day_from: {"realizedR": 2.5, "cycles": 5, "errors": 1}},
                "limits": {"minCycles": 5, "minHitRate": 0.5},
            }
        ],
        "matrix": [
            {
                "symbol": "AAA",
                "cells": [
                    {
                        "day": day_from,
                        "realizedR": 2.5,
                        "cycles": 5,
                        "errors": 1,
                        "outcome": "ERROR",
                    },
                    {
                        "day": day_to,
                        "realizedR": None,
                        "cycles": 0,
                        "errors": 0,
                        "outcome": "NOT_MEASURED",
                    },
                ],
            }
        ],
        "errors": [
            {"day": day_from, "symbol": "AAA", "kind": "SOFTWARE", "code": "FILL"}
        ],
        "gate": {"ready": False, "verdict": "INCONCLUSIVE"},
        "meta": {"account": account, "bump": "2.11.34-beta"},
        "limits": ["Advisory read-only: no cambia el motor."],
    }


@pytest.fixture
def app():
    return create_app()


def _write(tmp_path, window: str, account: str = "acc") -> None:
    (tmp_path / f"feedback-{window}.json").write_text(
        json.dumps(_artifact(window, account)), encoding="utf-8"
    )


async def _get(app, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_list_returns_windows_descending_and_latest_artifact(
    app, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-25_2026-09-29")
    _write(tmp_path, "2026-09-25_2026-09-30")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-feedback")

    assert response.status_code == 200
    body = response.json()
    assert body["readOnly"] is True
    assert body["windows"] == ["2026-09-25_2026-09-30", "2026-09-25_2026-09-29"]
    assert body["latest"] == "2026-09-25_2026-09-30"
    # El artefacto más reciente viaja embebido (misma proyección que el detalle).
    assert body["artifact"]["available"] is True
    assert body["artifact"]["window"]["from"] == "2026-09-25"
    assert body["artifact"]["window"]["to"] == "2026-09-30"


@pytest.mark.asyncio
async def test_get_returns_the_artifact_projection(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-25_2026-09-30")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-feedback/2026-09-25_2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["kind"] == "DIA_D_AUTO_FEEDBACK"
    assert body["matrixBasis"] == "entryDay"
    assert body["summary"]["refuted"] == 1
    assert body["summary"]["oosSupported"] == 0
    assert body["values"][0]["symbol"] == "AAA"
    assert body["values"][0]["evidenceQuality"] == "PRELIMINARY"
    assert body["values"][0]["expectancyR"] == 0.5
    assert body["matrix"][0]["cells"][1]["outcome"] == "NOT_MEASURED"
    assert body["errors"][0]["kind"] == "SOFTWARE"
    assert body["notes"] == []


@pytest.mark.asyncio
async def test_get_missing_artifact_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-feedback/2026-09-25_2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]


@pytest.mark.asyncio
async def test_no_account_scope_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-25_2026-09-30")

    async def _no_scope(_request, _account_id):
        return None

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _no_scope)
    detail = await _get(app, "/api/auto/dia-d-feedback/2026-09-25_2026-09-30")
    listing = await _get(app, "/api/auto/dia-d-feedback")

    assert detail.json()["available"] is False
    assert detail.json()["notes"] == ["no_account_scope"]
    assert listing.json()["windows"] == []
    assert listing.json()["notes"] == ["no_account_scope"]


@pytest.mark.asyncio
async def test_invalid_window_is_declared(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-feedback/not-a-window")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["invalid_window"]


@pytest.mark.asyncio
async def test_account_mismatch_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    # D34-06: una cuenta ajena es INDISTINGUIBLE de inexistente; no se entrega el artefacto.
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-25_2026-09-30", account="otra-cuenta")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    detail = await _get(app, "/api/auto/dia-d-feedback/2026-09-25_2026-09-30")
    listing = await _get(app, "/api/auto/dia-d-feedback")

    assert detail.status_code == 200
    body = detail.json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]
    assert body["values"] == []
    assert body["matrix"] == []
    # El listado tampoco revela la ventana de otra cuenta.
    assert listing.json()["windows"] == []
    assert listing.json()["latest"] is None
    assert listing.json()["notes"] == ["no_artifacts"]


@pytest.mark.asyncio
async def test_listing_only_returns_windows_of_the_current_account(
    app, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-25_2026-09-29", account="acc")
    _write(tmp_path, "2026-09-25_2026-09-30", account="otra-cuenta")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    body = (await _get(app, "/api/auto/dia-d-feedback")).json()
    assert body["windows"] == ["2026-09-25_2026-09-29"]
    assert body["latest"] == "2026-09-25_2026-09-29"


@pytest.mark.asyncio
async def test_list_without_artifacts_is_declared(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-feedback")

    assert response.status_code == 200
    body = response.json()
    assert body["windows"] == []
    assert body["latest"] is None
    assert body["artifact"] is None
    assert body["notes"] == ["no_artifacts"]
