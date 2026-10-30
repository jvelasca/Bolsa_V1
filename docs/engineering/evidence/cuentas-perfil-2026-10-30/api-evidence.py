"""Evidencia AUD-03/AUD-01 — respuestas HTTP reales contra la app ASGI (PostgreSQL local).

Reproduce, con la app montada por su propio ``lifespan`` y la BD de ``DATABASE_URL``:

1. ``PUT /api/accounts/{id}/active-profile`` con un perfil propio → ``200``;
2. ``DELETE /api/investor-profiles/{id}`` con el perfil asignado → ``409 profile_in_use``
   (con la lista de cuentas) y la asignación intacta;
3. ``GET``/``PUT`` sobre un perfil de otro tenant → ``404`` (no se filtra su existencia);
4. ``PUT … {"profileId": null}`` (la operación de «Quitar perfil») → ``200`` y el
   ``GET active-profile`` pasa a ``404``: ``active_profile_id`` es realmente ``NULL``,
   sin sustituirlo por el perfil por defecto;
5. ``DELETE`` del perfil ya libre → ``200``.

Restaura el estado: devuelve a la cuenta su perfil anterior, borra el perfil creado y la
fila ajena. Ejecutar desde la raíz del worktree:

    uv run python docs/engineering/evidence/cuentas-perfil-2026-10-30/api-evidence.py

La salida se escribe en UTF-8 sin BOM por ``regen-evidence.ps1``.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

if sys.platform == "win32":
    # psycopg async no soporta ProactorEventLoop en Windows (convención del repo).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[4] / ".env"


def _print(title: str) -> None:
    print(f"\n=== {title} ===")


def _show(label: str, response: object) -> None:
    status = getattr(response, "status_code", "?")
    print(f"{label}: {status}")
    try:
        body = getattr(response, "json")()
    except Exception:  # noqa: BLE001 — respuesta sin cuerpo JSON
        print("<sin cuerpo JSON>")
        return
    print(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True))


async def _run() -> int:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_api.main import create_app, lifespan
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import InvestorProfileRow
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings())
    factory: async_sessionmaker = create_session_factory(engine)
    app = create_app()
    failures = 0
    created_profile_id: str | None = None
    foreign_profile_id: str | None = None
    account_id: str | None = None
    previous_profile_id: str | None = None

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            _print("0. Cuenta semilla")
            listing = await client.get("/api/accounts")
            _show("GET /api/accounts", listing)
            rows = listing.json()["data"]
            if not rows:
                print("Sin cuentas del principal: no hay nada que medir.")
                return 0
            account_id = str(rows[0]["id"])
            previous_profile_id = rows[0].get("activeProfileId")

            stamp = int(time.time())
            _print("1. Perfil propio (catálogo)")
            created = await client.post(
                "/api/investor-profiles",
                json={
                    "name": f"PROF-EVIDENCIA AUD-03 {stamp}",
                    "horizon": "swing",
                    "objectives": ["growth"],
                    "riskTolerance": "moderate",
                    "experience": "intermediate",
                },
            )
            _show("POST /api/investor-profiles", created)
            if created.status_code not in (200, 201):
                return 1
            created_profile_id = str(created.json()["data"]["profileId"])

            _print("2. Asignación a la cuenta semilla")
            assigned = await client.put(
                f"/api/accounts/{account_id}/active-profile",
                json={"profileId": created_profile_id},
            )
            _show(f"PUT /api/accounts/{account_id}/active-profile", assigned)
            failures += int(assigned.status_code != 200)

            _print("3. Borrado del perfil EN USO → 409 profile_in_use")
            blocked = await client.delete(f"/api/investor-profiles/{created_profile_id}")
            _show(f"DELETE /api/investor-profiles/{created_profile_id}", blocked)
            detail = blocked.json().get("detail") or {}
            if blocked.status_code != 409 or detail.get("code") != "profile_in_use":
                print("FALLO: se esperaba 409 profile_in_use")
                failures += 1
            if not detail.get("accounts"):
                print("FALLO: el 409 debe enumerar las cuentas afectadas")
                failures += 1
            still = await client.get(f"/api/accounts/{account_id}/active-profile")
            _show("GET active-profile (no debe haberse desasignado)", still)
            failures += int(still.status_code != 200)

            _print("4. Perfil de otro tenant → 404")
            foreign_profile_id = f"PROF-AJENO-{stamp}"
            async with factory() as session:
                now = datetime.now(UTC)
                session.add(
                    InvestorProfileRow(
                        id=foreign_profile_id,
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
            foreign_get = await client.get(f"/api/investor-profiles/{foreign_profile_id}")
            _show(f"GET /api/investor-profiles/{foreign_profile_id}", foreign_get)
            failures += int(foreign_get.status_code != 404)
            foreign_put = await client.put(
                f"/api/accounts/{account_id}/active-profile",
                json={"profileId": foreign_profile_id},
            )
            _show(f"PUT /api/accounts/{account_id}/active-profile (ajeno)", foreign_put)
            failures += int(foreign_put.status_code != 404)

            _print("5. «Quitar perfil» → active_profile_id = NULL (sin perfil por defecto)")
            unassigned = await client.put(
                f"/api/accounts/{account_id}/active-profile", json={"profileId": None}
            )
            _show(f"PUT /api/accounts/{account_id}/active-profile {{profileId: null}}", unassigned)
            failures += int(unassigned.status_code != 200)
            gone = await client.get(f"/api/accounts/{account_id}/active-profile")
            _show("GET active-profile (debe ser 404: sin perfil)", gone)
            failures += int(gone.status_code != 404)

            _print("6. Borrado del perfil ya libre → 200")
            freed = await client.delete(f"/api/investor-profiles/{created_profile_id}")
            _show(f"DELETE /api/investor-profiles/{created_profile_id}", freed)
            failures += int(freed.status_code != 200)
            if freed.status_code == 200:
                created_profile_id = None

            _print("7. Restauración del estado")
            if previous_profile_id:
                restored = await client.put(
                    f"/api/accounts/{account_id}/active-profile",
                    json={"profileId": previous_profile_id},
                )
                _show("PUT active-profile (restaurar)", restored)
                failures += int(restored.status_code != 200)
            final = await client.get(f"/api/accounts/{account_id}/active-profile")
            _show("GET active-profile (restaurado)", final)

    if created_profile_id or foreign_profile_id:
        async with factory() as session:
            for profile_id in (created_profile_id, foreign_profile_id):
                if not profile_id:
                    continue
                row = await session.get(InvestorProfileRow, profile_id)
                if row is not None:
                    await session.delete(row)
            await session.commit()

    _print("8. Verificación de residuos (solo lectura)")
    async with factory() as session:
        leftover = (
            await session.execute(
                text(
                    "select id from investor_profiles "
                    "where id like 'PROF-EVIDENCIA%' or id like 'PROF-AJENO-%'"
                )
            )
        ).scalars().all()
        seed_profile = await session.scalar(
            text(
                "select active_profile_id from investment_accounts where id = :id"
            ),
            {"id": account_id},
        )
    print(f"perfiles residuales PROF-EVIDENCIA*/PROF-AJENO-*: {list(leftover)}")
    print(f"active_profile_id final de la cuenta semilla: {seed_profile}")
    if leftover:
        failures += 1
    await engine.dispose()

    print(f"\nResultado: {failures} comprobación(es) fallida(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
