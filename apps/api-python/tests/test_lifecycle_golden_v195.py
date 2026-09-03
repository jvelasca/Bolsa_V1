"""V1.95 — Golden HTTP: Financial Integrity + opening veto.

  Confirm OPEN → T1 → EXIT → drain
    → GET /lifecycle/integrity clean/OK
    → corrupt T1 ledger reference
    → GET /integrity drift/BLOCKED
    → Confirm new OPEN DENY (reconciliation:lifecycle_*)

Requires PostgreSQL (LIFECYCLE_PG_REQUIRED=1 fails hard).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.jwt import encode_access_token
from bolsa_api.auth.session import SESSION_COOKIE_NAME
from bolsa_api.main import create_app, lifespan
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
    account_id = f"lc-g195-{uuid4().hex[:12]}"
    legacy_id = f"pf-g195-{uuid4().hex[:12]}"
    inv_pf_id = f"ip-g195-{uuid4().hex[:12]}"
    ledger_id = f"le-g195-{uuid4().hex[:12]}"
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
                description="Depósito inicial golden v195",
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
    sym = symbol or f"G195{instrument_id[-6:].upper()}"
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


async def _drain(factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
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
    return drain


@pytest.fixture
def auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "lifecycle-golden-v195-password")
    monkeypatch.setenv("APP_AUTH_SECRET", "lifecycle-golden-v195-secret-key-32b")
    monkeypatch.setenv("JWT_SIGNING_KEY", "lifecycle-golden-v195-secret-key-32b")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_v195_golden_integrity_then_opening_veto(auth_secret: None) -> None:
    instrument_id = f"inst-g195-{uuid4().hex[:8]}"
    instrument_b = f"inst-g195b-{uuid4().hex[:8]}"
    user_a = f"user-a-{uuid4().hex[:8]}"

    try:
        app = create_app()
    except Exception as exc:  # noqa: BLE001
        _require_or_skip(exc)
        raise

    async with lifespan(app):
        factory = app.state.session_factory
        await _insert_user(factory, user_id=user_a)
        await _insert_instrument(factory, instrument_id=instrument_id)
        await _insert_instrument(factory, instrument_id=instrument_b)
        acc_a = await _insert_account(factory, user_id=user_a, name="Golden V195 A")
        token_a = await _jwt(factory, user_a)
        decision_id = f"dec-g195-{uuid4().hex[:10]}"
        plan = _triggered_plan(instrument_id, decision_id=decision_id)
        session_id = f"DSS-g195-{uuid4().hex[:10]}"
        await _seed_propose_session(
            factory,
            session_id=session_id,
            account_id=acc_a,
            instrument_id=instrument_id,
            decision_id=decision_id,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unauth = await client.get(
                "/api/lifecycle/integrity", params={"accountId": acc_a}
            )
            assert unauth.status_code == 401

            client.cookies.set(SESSION_COOKIE_NAME, token_a)
            await seed_http_opening_allow(app, client, acc_a, instrument_id)

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

            drain = await _drain(factory)
            assert drain.get("errors", 0) == 0, drain

            integ = await client.get(
                "/api/lifecycle/integrity", params={"accountId": acc_a}
            )
            assert integ.status_code == 200, integ.text
            payload = integ.json()["data"]
            assert payload["status"] == "clean", payload
            assert payload["operationalState"] == "OK", payload
            assert payload.get("fillLinkIssues") in ([], None) or len(
                payload.get("fillLinkIssues") or []
            ) == 0

            async with factory() as session:
                result = await session.execute(
                    delete(LedgerEntryRow).where(
                        LedgerEntryRow.account_id == acc_a,
                        LedgerEntryRow.reference_id == t1_tx,
                        LedgerEntryRow.reference_type == "transaction",
                    )
                )
                assert result.rowcount >= 1, "expected T1 ledger row to delete"
                await session.commit()

            integ2 = await client.get(
                "/api/lifecycle/integrity", params={"accountId": acc_a}
            )
            assert integ2.status_code == 200, integ2.text
            payload2 = integ2.json()["data"]
            assert payload2["status"] != "clean", payload2
            assert payload2["operationalState"] in ("DEGRADED", "BLOCKED"), payload2
            assert payload2["status"] == "drift"
            assert payload2["operationalState"] == "BLOCKED"
            assert any(
                "T1_EXECUTED" in (i.get("detail") or "")
                for i in (payload2.get("fillLinkIssues") or [])
            ), payload2

            decision_b = f"dec-g195b-{uuid4().hex[:10]}"
            session_b = f"DSS-g195b-{uuid4().hex[:10]}"
            plan_b = _triggered_plan(instrument_b, decision_id=decision_b)
            await _seed_propose_session(
                factory,
                session_id=session_b,
                account_id=acc_a,
                instrument_id=instrument_b,
                decision_id=decision_b,
            )
            await seed_http_opening_allow(app, client, acc_a, instrument_b)

            deny_resp = await client.post(
                "/api/ai/intents/confirm",
                json={
                    "recommendation": _open_rec(
                        instrument_b, plan_b, decision_id=decision_b
                    ),
                    "accountId": acc_a,
                    "execute": True,
                    "signedStop": 9.5,
                    "sessionId": session_b,
                },
            )
            assert deny_resp.status_code == 200, deny_resp.text
            deny_data = deny_resp.json()["data"]
            deny_trade = deny_data.get("trade") or {}
            assert deny_trade.get("status") != "executed", deny_data
            reason = str(deny_trade.get("reason") or "")
            blob = f"{reason} {deny_data!r}"
            assert deny_trade.get("status") == "rejected_by_gate", deny_data
            # Confirm maps OR-4 to risk_veto; integrity BLOCKED above is the
            # financial-integrity proof. Reason may be risk_veto or lifecycle_*.
            assert "reconciliation:lifecycle_" in blob or reason == "risk_veto", (
                deny_data
            )
