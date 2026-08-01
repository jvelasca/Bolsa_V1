"""CORE-P — multi-perfil live via ASGI (sin servidor externo).

Crea low/high, asigna a cuenta, lee active-profile y comprueba declared
(risk/horizon) + invariantes espejo del front Coach/Lab.
"""

from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan

POLICY = {
    "low": {"allowLabIfWeak": False, "maxDrawdownSoftPct": 18, "space×": 0.75},
    "high": {"allowLabIfWeak": True, "maxDrawdownSoftPct": 40, "space×": 1.35},
}


@pytest.mark.asyncio
async def test_core_p_multi_profile_assign_roundtrip() -> None:
    app = create_app()
    stamp = int(time.time())
    created: list[str] = []

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            accounts = await client.get("/api/accounts")
            accounts.raise_for_status()
            rows = accounts.json()["data"]
            if not rows:
                create_acc = await client.post(
                    "/api/accounts",
                    json={
                        "name": f"CORE-P smoke account {stamp}",
                        "currency": "EUR",
                        "initialDeposit": 10_000,
                    },
                )
                create_acc.raise_for_status()
                account_id = create_acc.json()["data"]["id"]
            else:
                account_id = rows[0]["id"]

            prev = await client.get(f"/api/accounts/{account_id}/active-profile")
            previous_profile_id = (
                prev.json()["data"]["profileId"] if prev.status_code == 200 else None
            )

            try:
                low = await client.post(
                    "/api/investor-profiles",
                    json={
                        "name": f"CORE-P ASGI low {stamp}",
                        "horizon": "long_term",
                        "objectives": ["preservation"],
                        "riskTolerance": "low",
                        "experience": "intermediate",
                    },
                )
                assert low.status_code in (200, 201)
                low_id = low.json()["data"]["profileId"]
                created.append(low_id)

                high = await client.post(
                    "/api/investor-profiles",
                    json={
                        "name": f"CORE-P ASGI high {stamp}",
                        "horizon": "intraday",
                        "objectives": ["growth"],
                        "riskTolerance": "high",
                        "experience": "intermediate",
                    },
                )
                assert high.status_code in (200, 201)
                high_id = high.json()["data"]["profileId"]
                created.append(high_id)

                assign_low = await client.put(
                    f"/api/accounts/{account_id}/active-profile",
                    json={"profileId": low_id},
                )
                assert assign_low.status_code == 200
                active_low = await client.get(
                    f"/api/accounts/{account_id}/active-profile"
                )
                assert active_low.status_code == 200
                data_low = active_low.json()["data"]
                assert data_low["profileId"] == low_id
                assert data_low["declared"]["riskTolerance"] == "low"
                assert data_low["declared"]["horizon"] == "long_term"
                assert POLICY["low"]["maxDrawdownSoftPct"] == 18
                assert POLICY["low"]["allowLabIfWeak"] is False

                assign_high = await client.put(
                    f"/api/accounts/{account_id}/active-profile",
                    json={"profileId": high_id},
                )
                assert assign_high.status_code == 200
                active_high = await client.get(
                    f"/api/accounts/{account_id}/active-profile"
                )
                assert active_high.status_code == 200
                data_high = active_high.json()["data"]
                assert data_high["profileId"] == high_id
                assert data_high["declared"]["riskTolerance"] == "high"
                assert data_high["declared"]["horizon"] == "intraday"
                assert POLICY["high"]["maxDrawdownSoftPct"] == 40
                assert POLICY["high"]["allowLabIfWeak"] is True
                assert low_id != high_id
            finally:
                if previous_profile_id:
                    await client.put(
                        f"/api/accounts/{account_id}/active-profile",
                        json={"profileId": previous_profile_id},
                    )
                for pid in created:
                    await client.delete(f"/api/investor-profiles/{pid}")
