"""R12-AUTH F8b: trackers and execution policies scoped by JWT principal."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bolsa_infrastructure.database.models import (
    ExecutionPolicyRow,
    InstrumentListRow,
    StrategyDefinitionRow,
    TrackerDefinitionRow,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.principal import DEFAULT_APP_PRINCIPAL
from bolsa_api.main import create_app, lifespan


def _now() -> datetime:
    return datetime.now(UTC)


def _patch_request_principal(monkeypatch: pytest.MonkeyPatch, principal: str) -> None:
    def fake(_request: object) -> str:
        return principal

    for target in (
        "bolsa_api.auth.request_principal.get_request_principal",
        "bolsa_api.api.dependencies.get_request_principal",
        "bolsa_api.api.v1.routes.trackers.get_request_principal",
        "bolsa_api.api.v1.routes.execution_policies.get_request_principal",
        "bolsa_api.api.v1.routes.lists.get_request_principal",
    ):
        monkeypatch.setattr(target, fake)


async def _insert_raw_strategy(
    factory: async_sessionmaker[AsyncSession],
) -> str:
    strategy_id = f"strat-{uuid4().hex[:12]}"
    async with factory() as session:
        session.add(
            StrategyDefinitionRow(
                id=strategy_id,
                name="Isolation test strategy",
                definition={"kind": "test"},
                origin="manual",
                timeframe="1d",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.commit()
    return strategy_id


async def _delete_raw_strategy(
    factory: async_sessionmaker[AsyncSession],
    strategy_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(StrategyDefinitionRow, strategy_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


async def _insert_raw_tracker(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str | None,
    name: str,
    strategy_id: str,
    list_id: str | None = None,
    schedule: dict[str, object] | None = None,
) -> str:
    tracker_id = f"trk-{uuid4().hex[:12]}"
    now = _now()
    universe: dict[str, object] = (
        {"listId": list_id} if list_id is not None else {"instrumentIds": ["inst-iso-1"]}
    )
    definition: dict[str, object] = {
        "id": tracker_id,
        "name": name,
        "strategyDefinitionId": strategy_id,
        "universe": universe,
        "timeframe": "1d",
        "barLimit": 500,
        "maxResults": 100,
        "evaluationMode": "bar_close",
        "origin": "manual",
        "enabled": True,
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
    }
    if schedule is not None:
        definition["schedule"] = schedule
    async with factory() as session:
        session.add(
            TrackerDefinitionRow(
                id=tracker_id,
                name=name,
                definition=definition,
                strategy_definition_id=strategy_id,
                strategy_version=None,
                timeframe="1d",
                evaluation_mode="bar_close",
                origin="manual",
                enabled=True,
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return tracker_id


async def _insert_raw_list(
    factory: async_sessionmaker[AsyncSession],
    *,
    list_id: str,
    name: str = "Isolation test list",
) -> str:
    now = _now()
    async with factory() as session:
        session.add(
            InstrumentListRow(
                id=list_id,
                name=name,
                source="custom",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return list_id


async def _delete_raw_list(
    factory: async_sessionmaker[AsyncSession],
    list_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(InstrumentListRow, list_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


async def _delete_raw_tracker(
    factory: async_sessionmaker[AsyncSession],
    tracker_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(TrackerDefinitionRow, tracker_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


async def _insert_raw_policy(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str | None,
    name: str,
) -> str:
    policy_id = f"pol-{uuid4().hex[:12]}"
    now = _now()
    async with factory() as session:
        session.add(
            ExecutionPolicyRow(
                id=policy_id,
                name=name,
                definition={
                    "id": policy_id,
                    "name": name,
                    "mode": "alert",
                    "signalKinds": ["entry_long"],
                    "requireValidatedBacktest": False,
                    "origin": "manual",
                    "enabled": True,
                    "createdAt": now.isoformat(),
                    "updatedAt": now.isoformat(),
                },
                mode="alert",
                account_id=None,
                strategy_definition_id=None,
                origin="manual",
                enabled=True,
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return policy_id


async def _delete_raw_policy(
    factory: async_sessionmaker[AsyncSession],
    policy_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(ExecutionPolicyRow, policy_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_trackers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8b G6: trackers scoped al principal JWT."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        strategy_id = await _insert_raw_strategy(factory)
        tracker_a = await _insert_raw_tracker(
            factory,
            user_id="user-a",
            name="Tracker A isolation",
            strategy_id=strategy_id,
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/trackers/{tracker_a}")
                assert response.status_code == 404

                listed = await client.get("/api/trackers")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert tracker_a not in ids
        finally:
            await _delete_raw_tracker(factory, tracker_a)
            await _delete_raw_strategy(factory, strategy_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_tracker_hidden_from_non_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8b F7a: legacy tracker ``user_id is None`` invisible salvo bootstrap."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        strategy_id = await _insert_raw_strategy(factory)
        legacy_id = await _insert_raw_tracker(
            factory,
            user_id=None,
            name="Legacy tracker isolation",
            strategy_id=strategy_id,
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/trackers/{legacy_id}")
                assert response.status_code == 404

                listed = await client.get("/api/trackers")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
        finally:
            await _delete_raw_tracker(factory, legacy_id)
            await _delete_raw_strategy(factory, strategy_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_tracker_visible_to_bootstrap() -> None:
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        strategy_id = await _insert_raw_strategy(factory)
        legacy_id = await _insert_raw_tracker(
            factory,
            user_id=None,
            name="Legacy tracker bootstrap",
            strategy_id=strategy_id,
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/trackers/{legacy_id}")
                assert response.status_code == 200
                assert response.json()["data"]["id"] == legacy_id

                listed = await client.get("/api/trackers")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id in ids
        finally:
            await _delete_raw_tracker(factory, legacy_id)
            await _delete_raw_strategy(factory, strategy_id)


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_execution_policies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8b G6: execution policies scoped al principal JWT."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        policy_a = await _insert_raw_policy(
            factory, user_id="user-a", name="Policy A isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/execution-policies/{policy_a}")
                assert response.status_code == 404

                listed = await client.get("/api/execution-policies")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert policy_a not in ids
        finally:
            await _delete_raw_policy(factory, policy_a)


@pytest.mark.asyncio
async def test_legacy_null_user_id_policy_hidden_from_non_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_policy(
            factory, user_id=None, name="Legacy policy isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/execution-policies/{legacy_id}")
                assert response.status_code == 404

                listed = await client.get("/api/execution-policies")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
        finally:
            await _delete_raw_policy(factory, legacy_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_policy_visible_to_bootstrap() -> None:
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_policy(
            factory, user_id=None, name="Legacy policy bootstrap"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/execution-policies/{legacy_id}")
                assert response.status_code == 200
                assert response.json()["data"]["id"] == legacy_id

                listed = await client.get("/api/execution-policies")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id in ids
        finally:
            await _delete_raw_policy(factory, legacy_id)


@pytest.mark.asyncio
async def test_bootstrap_principal_constant_matches_default() -> None:
    assert DEFAULT_APP_PRINCIPAL == "app"


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_trackers_on_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8e: GET /lists/{id}/trackers filtra por principal."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    list_id = f"lst-{uuid4().hex[:12]}"
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        strategy_id = await _insert_raw_strategy(factory)
        await _insert_raw_list(factory, list_id=list_id)
        tracker_a = await _insert_raw_tracker(
            factory,
            user_id="user-a",
            name="Tracker A on list",
            strategy_id=strategy_id,
            list_id=list_id,
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/lists/{list_id}/trackers")
                assert response.status_code == 200
                ids = {row["id"] for row in response.json()["data"]}
                assert tracker_a not in ids
        finally:
            await _delete_raw_tracker(factory, tracker_a)
            await _delete_raw_list(factory, list_id)
            await _delete_raw_strategy(factory, strategy_id)


@pytest.mark.asyncio
async def test_bulk_evaluate_schedules_scoped_to_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8e: POST /trackers/schedules/evaluate sin trackerId solo ve trackers del principal."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    schedule = {"kind": "on_bar_close"}
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        strategy_id = await _insert_raw_strategy(factory)
        tracker_a = await _insert_raw_tracker(
            factory,
            user_id="user-a",
            name="Tracker A scheduled",
            strategy_id=strategy_id,
            schedule=schedule,
        )
        tracker_b = await _insert_raw_tracker(
            factory,
            user_id="user-b",
            name="Tracker B scheduled",
            strategy_id=strategy_id,
            schedule=schedule,
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/trackers/schedules/evaluate")
                assert response.status_code == 200
                run_ids = {run["trackerId"] for run in response.json()["data"]["runs"]}
                assert tracker_a not in run_ids
                assert tracker_b in run_ids or len(run_ids) == 0
        finally:
            await _delete_raw_tracker(factory, tracker_a)
            await _delete_raw_tracker(factory, tracker_b)
            await _delete_raw_strategy(factory, strategy_id)
