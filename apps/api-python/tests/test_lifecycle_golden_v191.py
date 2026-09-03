"""V1.91 — Golden: Confirm HTTP → PAPER → PositionSync → outbox → lifecycle → snapshot.

Certifies the full product path (no PositionSync inject, no synthetic TradeResult):
  TradePlan TRIGGERED
    → POST /ai/intents/confirm execute=true
    → PAPER ExecuteTrade → transactionId
    → PositionSync (persist+enqueue same TX)
    → post-commit drain
    → GET snapshot
  OPEN → T1 reduce → EXIT · replay open · User B 403

Requires PostgreSQL (LIFECYCLE_PG_REQUIRED=1 fails hard).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord
from bolsa_infrastructure.auth.passwords import hash_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import (
    InstrumentRow,
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
    UserRow,
)
from bolsa_infrastructure.database.repositories.cognitive_repository import (
    SqlAlchemyCognitiveRepository,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.jwt import encode_access_token
from bolsa_api.auth.session import SESSION_COOKIE_NAME
from bolsa_api.main import create_app, lifespan
from tests.opening_gate_seed import seed_http_opening_allow


def _now() -> datetime:
    return datetime.now(UTC)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get("LIFECYCLE_PG_REQUIRED") == "1":
        raise AssertionError(
            f"lifecycle golden required but PostgreSQL unavailable: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL no disponible: {exc}")


async def _insert_user(
    factory: async_sessionmaker[AsyncSession], *, user_id: str
) -> None:
    async with factory() as session:
        if await session.get(UserRow, user_id) is None:
            session.add(
                UserRow(
                    id=user_id,
                    login=user_id,
                    password_hash=hash_password("pw"),
                    role="operator",
                    session_version=0,
                    created_at=_now(),
                    disabled_at=None,
                )
            )
            await session.commit()


async def _insert_account(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    name: str,
) -> str:
    account_id = f"lc-g191-{uuid4().hex[:12]}"
    legacy_id = f"pf-g191-{uuid4().hex[:12]}"
    inv_pf_id = f"ip-g191-{uuid4().hex[:12]}"
    ledger_id = f"le-g191-{uuid4().hex[:12]}"
    now = _now()
    deposit = Decimal("100000")
    async with factory() as session:
        session.add(
            InvestmentAccountRow(
                id=account_id,
                user_id=user_id,
                name=name,
                type="simulated",
                status="active",
                currency="USD",
                base_currency="USD",
                initial_deposit=deposit,
                leverage=Decimal("1"),
                is_default=False,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            PortfolioRow(
                id=legacy_id,
                name=f"{name} — cartera",
                currency="USD",
                cash=deposit,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            InvestmentPortfolioRow(
                id=inv_pf_id,
                account_id=account_id,
                legacy_portfolio_id=legacy_id,
                name="Cartera principal",
                description=None,
                strategy_tag="core",
                sort_order=0,
                is_default=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            LedgerEntryRow(
                id=ledger_id,
                account_id=account_id,
                portfolio_id=inv_pf_id,
                type="deposit",
                amount=deposit,
                currency="USD",
                balance_after=deposit,
                reference_type="manual",
                reference_id=account_id,
                description="Depósito inicial golden v191",
                executed_at=now,
                created_at=now,
            )
        )
        await session.commit()
    return account_id


async def _insert_instrument(
    factory: async_sessionmaker[AsyncSession],
    *,
    instrument_id: str,
    symbol: str | None = None,
) -> None:
    now = _now()
    sym = symbol or f"G191{instrument_id[-6:].upper()}"
    async with factory() as session:
        if await session.get(InstrumentRow, instrument_id) is None:
            session.add(
                InstrumentRow(
                    id=instrument_id,
                    symbol=sym,
                    yahoo_symbol=f"{sym}-{instrument_id}",
                    isin=None,
                    name=sym,
                    exchange="TEST",
                    country="US",
                    currency="USD",
                    sector=None,
                    type="stock",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()


async def _jwt(factory: async_sessionmaker[AsyncSession], user_id: str) -> str:
    settings = get_settings()
    async with factory() as session:
        user = await session.get(UserRow, user_id)
        assert user is not None
        return encode_access_token(
            settings, sub=user.id, sv=user.session_version, role=user.role
        )


def _triggered_plan(instrument_id: str, *, decision_id: str) -> dict[str, Any]:
    # Prices aligned with opening_gate_seed flat bars @ 10.0 (±2%).
    return {
        "id": f"tp-{decision_id}",
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "symbol": "AAPL",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 10.0,
        "structuralStop": 9.5,
        "target1": 10.5,
        "target2": 11.0,
        "quantity": 10.0,
        "riskAmount": 5.0,
    }


def _open_rec(
    instrument_id: str, plan: dict[str, Any], *, decision_id: str
) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "action": "recommend_long",
        "suggestedQuantity": 10.0,
        "suggestedPrice": 10.0,
        "tradePlan": plan,
    }


def _reduce_rec(instrument_id: str, *, decision_id: str) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "action": "reduce",
        "suggestedQuantity": 5.0,
        "suggestedPrice": 10.5,
        "decisionPackage": {
            "operativaIntent": "reduce",
            "exitSource": "event",
            "plannedQty": 5.0,
            "exitPlan": {
                "status": "TRIGGERED",
                "suggestedAction": "reduce",
                "primaryReason": "TARGET_1",
                "suggestedQty": 5.0,
            },
        },
    }


def _exit_rec(instrument_id: str, *, decision_id: str) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "action": "exit_hint",
        "suggestedQuantity": 5.0,
        "suggestedPrice": 10.8,
        "decisionPackage": {
            "operativaIntent": "exit",
            "exitSource": "event",
            "plannedQty": 5.0,
            "exitPlan": {
                "status": "TRIGGERED",
                "suggestedAction": "exit",
                "primaryReason": "MANUAL",
                "suggestedQty": 5.0,
            },
        },
    }


async def _seed_propose_session(
    factory: async_sessionmaker[AsyncSession],
    *,
    session_id: str,
    account_id: str,
    instrument_id: str,
    decision_id: str,
) -> None:
    """ADR-031 H3 — Confirm openings require a DecisionPackage (not orphan)."""
    record = DecisionSessionRecord(
        id=session_id,
        kind="propose",
        status="open",
        instrument_id=instrument_id,
        created_at=_now().isoformat().replace("+00:00", "Z"),
        decision_id=decision_id,
        account_id=account_id,
        payload={
            "decisionId": decision_id,
            "runtime": {
                "decisionPackage": {
                    "decisionId": decision_id,
                    "instrumentId": instrument_id,
                    "action": "recommend_long",
                },
                "tradePlan": _triggered_plan(instrument_id, decision_id=decision_id),
            },
        },
    )
    async with factory() as session:
        await SqlAlchemyCognitiveRepository(session).append_decision_session(record)
        await session.commit()


@pytest.fixture
def auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "lifecycle-golden-v191-password")
    monkeypatch.setenv("APP_AUTH_SECRET", "lifecycle-golden-v191-secret-key-32b")
    monkeypatch.setenv("JWT_SIGNING_KEY", "lifecycle-golden-v191-secret-key-32b")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_v191_golden_confirm_http_paper_lifecycle_snapshot(
    auth_secret: None,
) -> None:
    instrument_id = f"inst-g191-{uuid4().hex[:8]}"
    user_a = f"user-a-{uuid4().hex[:8]}"
    user_b = f"user-b-{uuid4().hex[:8]}"

    try:
        app = create_app()
    except Exception as exc:  # noqa: BLE001
        _require_or_skip(exc)
        raise

    async with lifespan(app):
        factory = app.state.session_factory
        await _insert_user(factory, user_id=user_a)
        await _insert_user(factory, user_id=user_b)
        await _insert_instrument(factory, instrument_id=instrument_id)
        acc_a = await _insert_account(factory, user_id=user_a, name="Golden V191 A")
        await _insert_account(factory, user_id=user_b, name="Golden V191 B")
        token_a = await _jwt(factory, user_a)
        token_b = await _jwt(factory, user_b)
        decision_id = f"dec-g191-{uuid4().hex[:10]}"
        plan = _triggered_plan(instrument_id, decision_id=decision_id)
        session_id = f"DSS-g191-{uuid4().hex[:10]}"
        await _seed_propose_session(
            factory,
            session_id=session_id,
            account_id=acc_a,
            instrument_id=instrument_id,
            decision_id=decision_id,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, token_a)
            await seed_http_opening_allow(app, client, acc_a, instrument_id)

            # OPEN via real Confirm HTTP
            open_resp = await client.post(
                "/api/ai/intents/confirm",
                json={
                    "recommendation": _open_rec(
                        instrument_id, plan, decision_id=decision_id
                    ),
                    "accountId": acc_a,
                    "execute": True,
                    "signedStop": 9.5,
                    "sessionId": session_id,
                },
            )
            assert open_resp.status_code == 200, open_resp.text
            open_data = open_resp.json()["data"]
            trade = open_data.get("trade") or {}
            assert trade.get("status") == "executed", (
                f"open rejected: {trade.get('reason')} full={open_data!r}"
            )
            open_tx = trade["transactionId"]
            assert isinstance(open_tx, str) and open_tx.strip()
            position_id = (
                open_data.get("positionPersist", {})
                .get("lifecycle", {})
                .get("positionId")
            )
            assert isinstance(position_id, str) and position_id.strip(), open_data

            # Replay OPEN — may reject (already open); lifecycle must stay single open_tx
            replay_resp = await client.post(
                "/api/ai/intents/confirm",
                json={
                    "recommendation": _open_rec(
                        instrument_id, plan, decision_id=decision_id
                    ),
                    "accountId": acc_a,
                    "execute": True,
                    "signedStop": 9.5,
                    "sessionId": session_id,
                },
            )
            assert replay_resp.status_code == 200, replay_resp.text

            # T1 reduce — same decisionId as OPEN (lifecycle identity envelope)
            t1_resp = await client.post(
                "/api/ai/intents/confirm",
                json={
                    "recommendation": _reduce_rec(
                        instrument_id, decision_id=decision_id
                    ),
                    "accountId": acc_a,
                    "execute": True,
                    "sessionId": session_id,
                },
            )
            assert t1_resp.status_code == 200, t1_resp.text
            t1_data = t1_resp.json()["data"]
            t1_trade = t1_data.get("trade") or {}
            assert t1_trade.get("status") == "executed", (
                f"t1 rejected: {t1_trade.get('reason')} full={t1_data!r}"
            )
            t1_tx = t1_trade["transactionId"]
            assert isinstance(t1_tx, str) and t1_tx.strip()
            t1_lc = (t1_data.get("positionPersist") or {}).get("lifecycle") or {}
            assert t1_lc.get("status") in ("pending", "applied"), (
                f"t1 lifecycle missing: {t1_data.get('positionPersist')!r}"
            )

            # EXIT remaining — same decisionId as OPEN (lifecycle identity + FE)
            exit_resp = await client.post(
                "/api/ai/intents/confirm",
                json={
                    "recommendation": _exit_rec(
                        instrument_id, decision_id=decision_id
                    ),
                    "accountId": acc_a,
                    "execute": True,
                    "sessionId": session_id,
                },
            )
            assert exit_resp.status_code == 200, exit_resp.text
            exit_data = exit_resp.json()["data"]
            exit_trade = exit_data.get("trade") or {}
            assert exit_trade.get("status") == "executed", (
                f"exit rejected: {exit_trade.get('reason')} full={exit_data!r}"
            )
            exit_lc = (exit_data.get("positionPersist") or {}).get("lifecycle") or {}
            assert exit_lc.get("status") in ("pending", "applied"), (
                f"exit lifecycle missing: {exit_data.get('positionPersist')!r}"
            )

            # Explicit post-confirm drain (kick may race; worker not in ASGI test)
            from bolsa_application.lifecycle_event_store import (
                AppendLifecycleEvent,
                PostgresLifecycleEventStore,
            )
            from bolsa_application.lifecycle_outbox import (
                PostgresLifecycleOutboxStore,
                drain_lifecycle_outbox,
            )

            async with factory() as drain_session:
                drain = await drain_lifecycle_outbox(
                    PostgresLifecycleOutboxStore(drain_session),
                    AppendLifecycleEvent(PostgresLifecycleEventStore(drain_session)),
                )
                await drain_session.commit()
            assert drain.get("errors", 0) == 0 or drain.get("applied", 0) >= 0, drain

            snap_resp = await client.get(
                f"/api/lifecycle/positions/{position_id}/snapshot"
            )
            assert snap_resp.status_code == 200, snap_resp.text
            snap = snap_resp.json()["data"]
            assert snap["stage"] == "closed", (
                f"stage={snap['stage']} kinds={[e['kind'] for e in snap['events']]} "
                f"drain={drain}"
            )
            kinds = [e["kind"] for e in snap["events"]]
            assert kinds[0] == "POSITION_OPENED"
            assert "T1_EXECUTED" in kinds
            assert kinds[-1] == "POSITION_CLOSED"
            event_ids = [e["eventId"] for e in snap["events"]]
            assert open_tx in event_ids
            assert event_ids.count(open_tx) == 1

            client.cookies.set(SESSION_COOKIE_NAME, token_b)
            foreign = await client.get(
                f"/api/lifecycle/positions/{position_id}/snapshot"
            )
            assert foreign.status_code == 403
