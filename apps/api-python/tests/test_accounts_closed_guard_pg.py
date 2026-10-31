"""CTA-D5 / CTA-D3 / CTA-09 — guardas de cuenta cerrada y round-trip de settings en PG real.

Casos que fija esta suite (ASGI contra ``DATABASE_URL``):

1. **CTA-D5**: una cuenta cerrada no admite escrituras de configuración
   (``PATCH /settings``), de datos (``PATCH /accounts/{id}``) ni de perfil
   (``PUT /active-profile``) → 409 ``account_closed``. La cuenta conserva su
   nombre, sus settings y su ``active_profile_id``.
2. **CTA-D5 (bootstrap)**: ``POST /investor-profiles/ensure-defaults`` no asigna
   perfil a cuentas cerradas (son registro histórico, no operativa).
3. **CTA-D3**: las notas internas hacen round-trip con sus espacios interiores;
   el recorte de extremos es del cliente al guardar, no del transporte.
4. **CTA-09**: guardar comisiones/fiscal PRESERVA ``settings_json.brokerVenue``
   (la preferencia Paper/Live de la cuenta no se borra al guardar el otro bloque).
5. **CTA-D10**: ``GET /accounts/summaries`` omite las cuentas cerradas en vez de
   fallar con 500 al resolver su scope (que solo admite activas).
6. **make-default**: ``POST /accounts/{id}/make-default`` sobre una cuenta cerrada
   responde 409 ``account_closed`` y **no** mueve el default vigente del owner.

Si PostgreSQL no responde se salta, salvo ``CTA_PG_REQUIRED=1``.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_ENV_REQUIRED = "CTA_PG_REQUIRED"

pytestmark = pytest.mark.asyncio

_SETTINGS: dict[str, object] = {
    "commission": {
        "presetId": "standard_es",
        "label": "Estándar ES",
        "stockCommissionPct": 0.1,
        "stockCommissionMin": 1.0,
        "stockCommissionMax": 29.0,
        "vatOnCommissionPct": 21.0,
        "fxConversionPct": 0.1,
        "custodyAnnualPct": 0.0,
    },
    "tax": {
        "jurisdiction": "ES",
        "costBasisMethod": "fifo",
        "stampDutyBuyPct": 0.2,
        "dividendWithholdingPct": 19.0,
        "capitalGainsTaxPct": 19.0,
        "fiscalYearStartMonth": 1,
    },
    "notes": None,
}


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_ENV_REQUIRED) == "1":
        raise AssertionError(f"PostgreSQL requerido para CTA-D5 y no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL (CTA-D5 cuentas cerradas) no disponible: {exc}")


def _settings_with_notes(notes: str | None) -> dict[str, object]:
    return {**_SETTINGS, "notes": notes}


@pytest_asyncio.fixture
async def api() -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    from bolsa_api.main import create_app, lifespan

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail honesto según entorno
        _require_or_skip(exc)
        raise

    factory = create_session_factory(engine)
    app = create_app()
    try:
        async with lifespan(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client, factory
    finally:
        await engine.dispose()


async def _create_account(client: AsyncClient, name: str) -> str:
    response = await client.post(
        "/api/accounts",
        json={"name": name, "currency": "EUR", "initialDeposit": 10_000},
    )
    assert response.status_code in (200, 201), response.text
    return str(response.json()["data"]["id"])


async def _create_profile(client: AsyncClient, name: str) -> str:
    response = await client.post(
        "/api/investor-profiles",
        json={
            "name": name,
            "horizon": "swing",
            "objectives": ["growth"],
            "riskTolerance": "moderate",
            "experience": "intermediate",
        },
    )
    assert response.status_code in (200, 201), response.text
    return str(response.json()["data"]["profileId"])


async def _profile_ids(client: AsyncClient) -> set[str]:
    response = await client.get("/api/investor-profiles")
    response.raise_for_status()
    return {str(row["profileId"]) for row in response.json()["data"]}


async def _active_profile_id(client: AsyncClient, account_id: str) -> str | None:
    response = await client.get(f"/api/accounts/{account_id}/active-profile")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return str(response.json()["data"]["profileId"])


async def _default_account_ids(client: AsyncClient) -> set[str]:
    """Ids de las cuentas del principal marcadas ``isDefault`` (incluye cerradas)."""
    response = await client.get("/api/accounts")
    response.raise_for_status()
    return {str(row["id"]) for row in response.json()["data"] if row.get("isDefault")}


async def _dispose_account(client: AsyncClient, account_id: str) -> None:
    """Cierra (si hace falta) y borra la cuenta demo desechable."""
    await client.post(f"/api/accounts/{account_id}/close")
    response = await client.delete(f"/api/accounts/{account_id}")
    assert response.status_code in (200, 204), response.text


def _assert_account_closed(response: Response) -> None:
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "account_closed", detail
    assert detail["message"]


async def test_closed_account_rejects_settings_name_and_profile_writes(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """CTA-D5 — la cuenta cerrada es de solo lectura, también por API."""
    client, _factory = api
    stamp = int(time.time())
    account_id = await _create_account(client, f"CU-CTA-D5 {stamp}")
    profile_id = await _create_profile(client, f"CU-CTA-D5 perfil {stamp}")

    try:
        saved = await client.patch(
            f"/api/accounts/{account_id}/settings",
            json={"settings": _settings_with_notes("nota previa")},
        )
        assert saved.status_code == 200, saved.text
        assigned = await client.put(
            f"/api/accounts/{account_id}/active-profile",
            json={"profileId": profile_id},
        )
        assert assigned.status_code == 200, assigned.text

        closed = await client.post(f"/api/accounts/{account_id}/close")
        assert closed.status_code in (200, 204), closed.text

        blocked_settings = await client.patch(
            f"/api/accounts/{account_id}/settings",
            json={"settings": _settings_with_notes("no debería guardarse")},
        )
        _assert_account_closed(blocked_settings)

        blocked_name = await client.patch(
            f"/api/accounts/{account_id}", json={"name": "Nombre prohibido"}
        )
        _assert_account_closed(blocked_name)

        blocked_profile = await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": None}
        )
        _assert_account_closed(blocked_profile)

        # Ninguna escritura rechazada se aplicó a medias.
        after = await client.get(f"/api/accounts/{account_id}")
        assert after.status_code == 200, after.text
        row = after.json()["data"]
        assert row["name"].startswith("CU-CTA-D5 ")
        assert row["settings"]["notes"] == "nota previa"
        assert await _active_profile_id(client, account_id) == profile_id
    finally:
        await _dispose_account(client, account_id)
        allowed = await client.delete(f"/api/investor-profiles/{profile_id}")
        assert allowed.status_code == 200, allowed.text


async def test_closed_account_cannot_be_made_default(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """Una cuenta cerrada no puede promocionarse a principal (409 ``account_closed``).

    La guarda vive en el repositorio y corre **antes** del ``UPDATE`` que desmarca al
    resto de cuentas del owner: el rechazo no puede mover el default vigente.
    """
    client, _factory = api
    stamp = int(time.time())
    account_id = await _create_account(client, f"CU-CTA-D5 default {stamp}")

    try:
        defaults_before = await _default_account_ids(client)

        closed = await client.post(f"/api/accounts/{account_id}/close")
        assert closed.status_code in (200, 204), closed.text

        blocked = await client.post(f"/api/accounts/{account_id}/make-default")
        _assert_account_closed(blocked)

        # El default vigente del owner no se movió.
        assert await _default_account_ids(client) == defaults_before

        # Y la cerrada sigue sin ser principal.
        after = await client.get(f"/api/accounts/{account_id}")
        assert after.status_code == 200, after.text
        assert after.json()["data"]["isDefault"] is False
    finally:
        await _dispose_account(client, account_id)


async def test_ensure_defaults_does_not_touch_closed_accounts(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """CTA-D5 — el bootstrap de perfiles ignora el registro histórico cerrado."""
    client, _factory = api
    stamp = int(time.time())
    profile_ids_before = await _profile_ids(client)
    account_id = await _create_account(client, f"CU-CTA-D5 bootstrap {stamp}")

    try:
        cleared = await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": None}
        )
        assert cleared.status_code == 200, cleared.text
        closed = await client.post(f"/api/accounts/{account_id}/close")
        assert closed.status_code in (200, 204), closed.text

        ensured = await client.post("/api/investor-profiles/ensure-defaults")
        assert ensured.status_code == 200, ensured.text

        # La cuenta cerrada sigue sin perfil: ni se le asigna ni se crea uno por ella.
        assert await _active_profile_id(client, account_id) is None
    finally:
        await _dispose_account(client, account_id)
        # Residuo del bootstrap en la versión sin la guarda: se retira el perfil creado.
        for profile_id in (await _profile_ids(client)) - profile_ids_before:
            await client.delete(f"/api/investor-profiles/{profile_id}")


async def test_notes_round_trip_keeps_inner_spaces(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """CTA-D3 — el transporte no recorta: «nota con espacios» vuelve idéntica."""
    client, _factory = api
    stamp = int(time.time())
    account_id = await _create_account(client, f"CU-CTA-D3 {stamp}")
    notes = "nota con espacios  y   dobles"

    try:
        saved = await client.patch(
            f"/api/accounts/{account_id}/settings",
            json={"settings": _settings_with_notes(notes)},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["settings"]["notes"] == notes

        fetched = await client.get(f"/api/accounts/{account_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["data"]["settings"]["notes"] == notes

        cleared = await client.patch(
            f"/api/accounts/{account_id}/settings",
            json={"settings": _settings_with_notes(None)},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["data"]["settings"]["notes"] is None
    finally:
        await _dispose_account(client, account_id)


async def test_closed_account_does_not_break_account_summaries(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """CTA-D10 — ``GET /accounts/summaries`` no revienta con una cuenta cerrada.

    ``resolve_scope`` solo resuelve cuentas activas; la lista debe saltar la cerrada
    (registro histórico) en vez de propagar el ``ValueError`` como 500.
    """
    client, _factory = api
    stamp = int(time.time())
    closed_id = await _create_account(client, f"CU-CTA-D10 {stamp}")

    try:
        active_before = await client.get("/api/accounts/summaries")
        assert active_before.status_code == 200, active_before.text
        active_ids = {row["account"]["id"] for row in active_before.json()["data"]}
        assert closed_id in active_ids

        closed = await client.post(f"/api/accounts/{closed_id}/close")
        assert closed.status_code in (200, 204), closed.text

        after = await client.get("/api/accounts/summaries")
        assert after.status_code == 200, after.text
        ids = {row["account"]["id"] for row in after.json()["data"]}
        assert closed_id not in ids
        # La cuenta activa sigue resumida: no se vacía la lista entera.
        assert ids, after.text
    finally:
        await _dispose_account(client, closed_id)


async def test_saving_settings_preserves_account_broker_venue(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """CTA-09 — guardar comisiones/fiscal no borra la preferencia Paper|Live."""
    client, _factory = api
    stamp = int(time.time())
    account_id = await _create_account(client, f"CU-CTA-09 {stamp}")

    try:
        chosen = await client.patch(
            f"/api/accounts/{account_id}/broker-venue", json={"venue": "paper"}
        )
        assert chosen.status_code == 200, chosen.text
        assert chosen.json()["preference"] == "paper"

        saved = await client.patch(
            f"/api/accounts/{account_id}/settings",
            json={"settings": _settings_with_notes("configuración guardada")},
        )
        assert saved.status_code == 200, saved.text

        venue = await client.get(f"/api/accounts/{account_id}/broker-venue")
        assert venue.status_code == 200, venue.text
        assert venue.json()["preference"] == "paper"
    finally:
        await _dispose_account(client, account_id)
