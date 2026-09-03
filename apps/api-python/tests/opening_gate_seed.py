"""Siembra mandato + barra fresca para POST /portfolio/trade (I1).

El puerto HTTP usa el mismo ``check_opening`` de producción (DS-03 + DS-05).
Los tests que esperan 200 en un buy deben sembrar permiso; no se relaja el gate.

Nota V1.91: Alembic baseline no crea el UNIQUE Prisma de ``ohlcv_bars``
(``instrument_id, timeframe, timestamp``), así que el seed inserta filas
directas en vez de ``ON CONFLICT`` via ``upsert_daily_bars``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient

from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.ohlcv_time import parse_bar_timestamp
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.models import OhlcvBarRow
from bolsa_infrastructure.ids import new_id

_FLAT_BAR_COUNT = 120
_FLAT_BAR_PRICE = 10.0


def _flat_daily_bars(*, end: date | None = None) -> list[OhlcvBar]:
    """Serie plana sin saltos >50% — pasa sanity_opening_veto_reason (DS-05)."""
    last = end or datetime.now(UTC).date()
    start = last - timedelta(days=_FLAT_BAR_COUNT - 1)
    out: list[OhlcvBar] = []
    day = start
    while day <= last:
        out.append(
            OhlcvBar(
                timestamp=day.isoformat(),
                open=_FLAT_BAR_PRICE,
                high=_FLAT_BAR_PRICE,
                low=_FLAT_BAR_PRICE,
                close=_FLAT_BAR_PRICE,
                volume=1000,
            )
        )
        day += timedelta(days=1)
    return out


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
    created_at = datetime.now(UTC)
    async with factory() as session:
        for bar in _flat_daily_bars():
            session.add(
                OhlcvBarRow(
                    id=new_id(),
                    instrument_id=instrument_id,
                    timeframe=TimeFrame.D1,
                    timestamp=parse_bar_timestamp(bar.timestamp),
                    open=Decimal(str(bar.open)),
                    high=Decimal(str(bar.high)),
                    low=Decimal(str(bar.low)),
                    close=Decimal(str(bar.close)),
                    volume=bar.volume,
                    adj_close=(
                        Decimal(str(bar.adj_close)) if bar.adj_close is not None else None
                    ),
                    source=bar.source,
                    created_at=created_at,
                )
            )
        await session.commit()
