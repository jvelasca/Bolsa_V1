"""Siembra mandato + barra fresca para POST /portfolio/trade (I1).

El puerto HTTP usa el mismo ``check_opening`` de producción (DS-03 + DS-05).
Los tests que esperan 200 en un buy deben sembrar permiso; no se relaja el gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_infrastructure.database.repositories.ohlcv_repository import (
    SqlAlchemyOhlcvRepository,
)
from fastapi import FastAPI
from httpx import AsyncClient


async def seed_http_opening_allow(
    app: FastAPI,
    client: AsyncClient,
    account_id: str,
    instrument_id: str,
) -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    tenure_id = f"mt-i1-{uuid4().hex[:16]}"
    resp = await client.put(
        f"/api/accounts/{account_id}/mandates",
        json={
            "tenures": [
                {
                    "id": tenure_id,
                    "accountId": account_id,
                    "instrumentId": instrument_id,
                    "effectiveFrom": now,
                    "actor": "user",
                    "reason": "adopt",
                }
            ],
            "links": [],
        },
    )
    assert resp.status_code == 200, resp.text

    factory = app.state.session_factory
    async with factory() as session:
        repo = SqlAlchemyOhlcvRepository(session)
        today = datetime.now(UTC).date().isoformat()
        await repo.upsert_daily_bars(
            instrument_id,
            [
                OhlcvBar(
                    timestamp=today,
                    open=10.0,
                    high=10.0,
                    low=10.0,
                    close=10.0,
                    volume=1,
                )
            ],
        )
        await session.commit()
