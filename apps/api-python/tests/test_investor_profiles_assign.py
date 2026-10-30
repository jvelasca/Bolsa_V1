"""ART-PROFILE — asignación, bootstrap y guard de borrado contra PG real (ASGI).

Comprueba el contrato de propiedad introducido para CU-D6:

1. asignar un perfil propio → 200 y se lee de vuelta;
2. asignar un perfil de otro usuario → 404 «Perfil no encontrado» (no se filtra su existencia)
   y la cuenta conserva su perfil anterior;
3. desasignar (`profileId: null`) → 200 y el GET responde 404;
4. `ensure-defaults` crea **un** perfil por usuario, se lo asigna a las cuentas sin perfil y es
   idempotente;
5. borrar un perfil en uso → 409 `profile_in_use` con las cuentas afectadas, sin desasignarlas.

Corre contra la BD de ``DATABASE_URL`` (requiere Alembic al día). Si PostgreSQL no responde se
salta, salvo ``INVESTOR_PROFILES_PG_REQUIRED=1``.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_ENV_REQUIRED = "INVESTOR_PROFILES_PG_REQUIRED"
_DEFAULT_PROFILE_NAME = "Perfil por defecto (moderado)"

pytestmark = pytest.mark.asyncio


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_ENV_REQUIRED) == "1":
        raise AssertionError(f"PostgreSQL requerido para perfiles y no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL (perfiles ART-PROFILE) no disponible: {exc}")


@pytest_asyncio.fixture
async def api() -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_api.main import create_app, lifespan
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

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


async def _first_account(client: AsyncClient) -> str:
    response = await client.get("/api/accounts")
    response.raise_for_status()
    rows = response.json()["data"]
    if not rows:
        pytest.skip("Sin cuentas del principal: la suite no crea cuentas de prueba")
    return str(rows[0]["id"])


async def _active_profile_id(client: AsyncClient, account_id: str) -> str | None:
    response = await client.get(f"/api/accounts/{account_id}/active-profile")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return str(response.json()["data"]["profileId"])


async def _restore(client: AsyncClient, account_id: str, previous: str | None) -> None:
    if previous is None:
        await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": None}
        )
        return
    restored = await client.put(
        f"/api/accounts/{account_id}/active-profile", json={"profileId": previous}
    )
    if restored.status_code == 200:
        return
    # Un perfil legacy con ``user_id=NULL`` ya no es asignable (es invisible para su dueño).
    # Se deja la cuenta con el perfil compartido del bootstrap, que es un estado válido.
    await client.post("/api/investor-profiles/ensure-defaults")


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


async def test_assign_own_profile_and_reject_foreign(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, factory = api
    from bolsa_infrastructure.database.models import InvestorProfileRow

    account_id = await _first_account(client)
    previous = await _active_profile_id(client, account_id)
    stamp = int(time.time())
    own_id = await _create_profile(client, f"CU-ASIGN propio {stamp}")
    foreign_id = f"PROF-AJENO-{stamp}"

    try:
        assigned = await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": own_id}
        )
        assert assigned.status_code == 200, assigned.text
        assert await _active_profile_id(client, account_id) == own_id

        async with factory() as session:
            now = datetime.now(UTC)
            session.add(
                InvestorProfileRow(
                    id=foreign_id,
                    name="Perfil de otro usuario",
                    version="1.0.0",
                    user_id=f"tenant-otro-{stamp}",
                    horizon="swing",
                    objectives=["growth"],
                    risk_tolerance="moderate",
                    experience="intermediate",
                    suggested_policy_template_id="moderate",
                    selected_policy_template_id="moderate",
                    updated_by="user",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        cross = await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": foreign_id}
        )
        assert cross.status_code == 404, cross.text
        assert "Perfil no encontrado" in str(cross.json()["detail"])
        # La cuenta no se toca cuando la asignación se rechaza.
        assert await _active_profile_id(client, account_id) == own_id

        unassigned = await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": None}
        )
        assert unassigned.status_code == 200, unassigned.text
        assert await _active_profile_id(client, account_id) is None
    finally:
        async with factory() as session:
            row = await session.get(InvestorProfileRow, foreign_id)
            if row is not None:
                await session.delete(row)
                await session.commit()
        await _restore(client, account_id, previous)
        await client.delete(f"/api/investor-profiles/{own_id}")


async def test_ensure_defaults_creates_one_shared_owned_profile(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, factory = api
    from bolsa_infrastructure.database.models import InvestmentAccountRow

    listing = await client.get("/api/accounts")
    listing.raise_for_status()
    rows = listing.json()["data"]
    if not rows:
        pytest.skip("Sin cuentas del principal")

    # Con una sola cuenta no se puede demostrar el perfil compartido: se crea una demo
    # temporal (justificado) y se cierra+borra al terminar.
    temp_account_id: str | None = None
    if len(rows) < 2:
        stamp = int(time.time())
        created = await client.post(
            "/api/accounts",
            json={
                "name": f"CU-temp perfil compartido {stamp}",
                "currency": "EUR",
                "initialDeposit": 10_000,
            },
        )
        assert created.status_code in (200, 201), created.text
        temp_account_id = str(created.json()["data"]["id"])
        rows = [*rows, created.json()["data"]]

    account_ids = [str(row["id"]) for row in rows[:2]]

    previous: dict[str, str | None] = {}
    for account_id in account_ids:
        previous[account_id] = await _active_profile_id(client, account_id)

    try:
        # Simula cuentas anteriores al catálogo: sin perfil activo.
        async with factory() as session:
            for account_id in account_ids:
                row = await session.get(InvestmentAccountRow, account_id)
                assert row is not None
                row.active_profile_id = None
            await session.commit()

        first = await client.post("/api/investor-profiles/ensure-defaults")
        assert first.status_code == 200, first.text
        defaults = [p for p in first.json()["data"] if p["name"] == _DEFAULT_PROFILE_NAME]
        assert len(defaults) == 1, defaults
        shared = defaults[0]
        # El bootstrap propaga el dueño: un perfil con userId NULL es invisible para su dueño.
        assert shared.get("userId"), "ensure-defaults creó un perfil sin dueño"

        for account_id in account_ids:
            assert await _active_profile_id(client, account_id) == shared["profileId"]

        second = await client.post("/api/investor-profiles/ensure-defaults")
        assert second.status_code == 200, second.text
        defaults_again = [p for p in second.json()["data"] if p["name"] == _DEFAULT_PROFILE_NAME]
        assert len(defaults_again) == 1, "el bootstrap dejó de ser idempotente"
    finally:
        for account_id, profile_id in previous.items():
            await _restore(client, account_id, profile_id)
        if temp_account_id is not None:
            # Se cierra y se borra la demo temporal creada solo para este caso.
            await client.post(f"/api/accounts/{temp_account_id}/close")
            await client.delete(f"/api/accounts/{temp_account_id}")


async def test_delete_profile_in_use_returns_conflict(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _factory = api
    account_id = await _first_account(client)
    previous = await _active_profile_id(client, account_id)
    stamp = int(time.time())
    profile_id = await _create_profile(client, f"CU-BORRADO en uso {stamp}")

    try:
        assigned = await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": profile_id}
        )
        assert assigned.status_code == 200, assigned.text

        blocked = await client.delete(f"/api/investor-profiles/{profile_id}")
        assert blocked.status_code == 409, blocked.text
        detail = blocked.json()["detail"]
        assert detail["code"] == "profile_in_use"
        assert detail["accounts"], "el 409 debe listar las cuentas afectadas"
        # No se desasigna en silencio.
        assert await _active_profile_id(client, account_id) == profile_id
    finally:
        await _restore(client, account_id, previous)
        allowed = await client.delete(f"/api/investor-profiles/{profile_id}")
        assert allowed.status_code == 200, allowed.text


async def test_delete_profile_in_use_by_closed_account_still_returns_conflict(
    api: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """AUD-03: una cuenta cerrada sigue siendo una asignación y bloquea el borrado.

    El 409 no puede depender de que la cuenta esté operativa: el registro histórico
    conserva ``active_profile_id`` y desasignarlo por un borrado de catálogo sería
    exactamente la escritura implícita que la corrección elimina.
    """
    client, _factory = api
    stamp = int(time.time())
    created = await client.post(
        "/api/accounts",
        json={
            "name": f"CU-AUD03 cerrada {stamp}",
            "currency": "EUR",
            "initialDeposit": 10_000,
        },
    )
    assert created.status_code in (200, 201), created.text
    account = created.json()["data"]
    account_id = str(account["id"])
    profile_id = await _create_profile(client, f"CU-AUD03 cerrada perfil {stamp}")

    try:
        assigned = await client.put(
            f"/api/accounts/{account_id}/active-profile", json={"profileId": profile_id}
        )
        assert assigned.status_code == 200, assigned.text
        closed = await client.post(f"/api/accounts/{account_id}/close")
        assert closed.status_code in (200, 204), closed.text

        blocked = await client.delete(f"/api/investor-profiles/{profile_id}")
        assert blocked.status_code == 409, blocked.text
        detail = blocked.json()["detail"]
        assert detail["code"] == "profile_in_use"
        assert any(account["name"] in name for name in detail["accounts"])
        # La FK no ha convertido el rechazo en una desasignación.
        assert await _active_profile_id(client, account_id) == profile_id
    finally:
        # La cuenta temporal se borra (simulada + cerrada) y eso libera el perfil.
        deleted_account = await client.delete(f"/api/accounts/{account_id}")
        assert deleted_account.status_code in (200, 204), deleted_account.text
        allowed = await client.delete(f"/api/investor-profiles/{profile_id}")
        assert allowed.status_code == 200, allowed.text
