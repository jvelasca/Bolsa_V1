"""Persistencia del workspace: concurrencia optimista y cierre compacto de pestañas.

Regresión de Visualizados: el documento guardado no debe poder "resucitar" pestañas
que el usuario cerró, ni por un PUT con revisión obsoleta ni porque el cierre de
pestañas tenga que reenviar el documento completo.
"""

import asyncio
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan
from bolsa_application.workspaces import close_workspace_charts
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.workspace_repository import (
    SqlAlchemyWorkspaceRepository,
    WorkspaceVersionConflict,
)
from bolsa_infrastructure.database.session import create_engine, create_session_factory


def _document(charts: list[dict], viz: list[dict]) -> dict:
    return {
        "version": 1,
        "id": "doc",
        "name": "Persistencia",
        "updatedAt": "2026-01-01T00:00:00.000Z",
        "charts": charts,
        "activeChartId": charts[-1]["id"] if charts else None,
        "chartStateByListInstrument": {
            f"estudio::{tab['instrumentId']}": {
                "timeframe": "1D",
                "drawings": [],
            }
            for tab in charts
        },
        "list": {"visualizationEntries": viz, "apiListId": "estudio"},
        "layout": {"chartInspectorOpen": False},
    }


def _tab(tab_id: str, instrument_id: str) -> dict:
    return {"id": tab_id, "instrumentId": instrument_id, "label": instrument_id}


def _viz(instrument_id: str) -> dict:
    return {
        "instrumentId": instrument_id,
        "symbol": instrument_id,
        "name": instrument_id,
        "firstViewedAt": "2026-01-01T00:00:00.000Z",
        "lastViewedAt": "2026-01-01T00:00:00.000Z",
        "viewCount": 1,
    }


def test_close_workspace_charts_prunes_all_three_views() -> None:
    charts = [_tab("t1", "SAN"), _tab("t2", "BBVA"), _tab("t3", "ITX")]
    document = _document(charts, [_viz("SAN"), _viz("BBVA"), _viz("ITX")])

    pruned = close_workspace_charts(document, ["SAN", "ITX"], "t1")

    assert [tab["id"] for tab in pruned["charts"]] == ["t2"]
    assert list(pruned["chartStateByListInstrument"]) == ["estudio::BBVA"]
    assert [entry["instrumentId"] for entry in pruned["list"]["visualizationEntries"]] == [
        "BBVA"
    ]
    # Active tab cerrada → pasa a la última que queda.
    assert pruned["activeChartId"] == "t2"
    # El resto del documento sobrevive intacto.
    assert pruned["list"]["apiListId"] == "estudio"
    assert pruned["layout"] == {"chartInspectorOpen": False}
    # El documento original no se muta.
    assert len(document["charts"]) == 3


def test_close_workspace_charts_is_idempotent_and_noop_returns_same_document() -> None:
    charts = [_tab("t1", "SAN")]
    document = _document(charts, [_viz("SAN")])

    assert close_workspace_charts(document, ["BBVA"]) is document
    assert close_workspace_charts(document, []) is document


def test_close_workspace_charts_keeps_active_tab_and_handles_empty_result() -> None:
    charts = [_tab("t1", "SAN"), _tab("t2", "BBVA")]
    document = _document(charts, [_viz("SAN"), _viz("BBVA")])

    kept = close_workspace_charts(document, ["BBVA"], "t1")
    assert kept["activeChartId"] == "t1"

    empty = close_workspace_charts(document, ["SAN", "BBVA"], "t1")
    assert empty["charts"] == []
    assert empty["activeChartId"] is None
    assert empty["chartStateByListInstrument"] == {}
    assert empty["list"]["visualizationEntries"] == []


@pytest.mark.asyncio
async def test_workspace_expected_updated_at_conflict_and_close_charts() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            charts = [_tab("t1", "SAN"), _tab("t2", "BBVA"), _tab("t3", "ITX")]
            created = await client.post(
                "/api/workspaces",
                json={
                    "name": "Visualizados",
                    "document": _document(
                        charts, [_viz("SAN"), _viz("BBVA"), _viz("ITX")]
                    ),
                },
            )
            assert created.status_code == 201
            workspace_id = created.json()["data"]["id"]
            revision = created.json()["data"]["updatedAt"]

            # Revisión vigente → escribe.
            ok = await client.put(
                f"/api/workspaces/{workspace_id}",
                json={
                    "document": _document(charts, [_viz("SAN")]),
                    "expectedUpdatedAt": revision,
                },
            )
            assert ok.status_code == 200
            fresh_revision = ok.json()["data"]["updatedAt"]
            assert fresh_revision != revision

            # Revisión obsoleta → 409 y el documento NO cambia.
            stale = await client.put(
                f"/api/workspaces/{workspace_id}",
                json={
                    "document": _document(charts, [_viz("SAN")]),
                    "expectedUpdatedAt": revision,
                },
            )
            assert stale.status_code == 409
            assert stale.json()["detail"]["code"] == "workspace_conflict"
            assert stale.json()["detail"]["currentUpdatedAt"] == fresh_revision

            # Cierre compacto: solo ids, sin reenviar el documento.
            closed = await client.post(
                f"/api/workspaces/{workspace_id}/charts/close",
                json={
                    "instrumentIds": ["BBVA", "ITX"],
                    "activeChartId": "t3",
                    "expectedUpdatedAt": fresh_revision,
                },
            )
            assert closed.status_code == 200
            document = closed.json()["data"]["document"]
            assert [tab["instrumentId"] for tab in document["charts"]] == ["SAN"]
            assert document["activeChartId"] == "t1"
            assert list(document["chartStateByListInstrument"]) == ["estudio::SAN"]
            assert [
                entry["instrumentId"]
                for entry in document["list"]["visualizationEntries"]
            ] == ["SAN"]
            closed_revision = closed.json()["data"]["updatedAt"]

            # Idempotente: repetirlo no mueve la revisión.
            again = await client.post(
                f"/api/workspaces/{workspace_id}/charts/close",
                json={
                    "instrumentIds": ["BBVA", "ITX"],
                    "expectedUpdatedAt": closed_revision,
                },
            )
            assert again.status_code == 200
            assert again.json()["data"]["updatedAt"] == closed_revision

            # Y una revisión vieja en el cierre también da 409.
            conflicting_close = await client.post(
                f"/api/workspaces/{workspace_id}/charts/close",
                json={
                    "instrumentIds": ["SAN"],
                    "expectedUpdatedAt": fresh_revision,
                },
            )
            assert conflicting_close.status_code == 409

            await client.delete(f"/api/workspaces/{workspace_id}")


@pytest.mark.asyncio
async def test_pruned_charts_survive_an_api_restart() -> None:
    """El cierre de pestañas es estado en BD: reiniciar la API no lo deshace."""
    document = _document(
        [_tab("t1", "SAN"), _tab("t2", "BBVA")],
        [_viz("SAN"), _viz("BBVA")],
    )

    async def create_and_prune() -> tuple[str, str]:
        app = create_app()
        async with lifespan(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                created = await client.post(
                    "/api/workspaces",
                    json={"name": "Reinicio", "document": document},
                )
                workspace_id = created.json()["data"]["id"]
                closed = await client.post(
                    f"/api/workspaces/{workspace_id}/charts/close",
                    json={"instrumentIds": ["BBVA"]},
                )
                assert closed.status_code == 200
                return workspace_id, closed.json()["data"]["updatedAt"]

    workspace_id, closed_revision = await create_and_prune()

    # Proceso "nuevo": app y lifespan nuevos, misma BD.
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            detail = await client.get(f"/api/workspaces/{workspace_id}")
            assert detail.status_code == 200
            assert detail.json()["data"]["updatedAt"] == closed_revision
            restored = detail.json()["data"]["document"]
            assert [tab["instrumentId"] for tab in restored["charts"]] == ["SAN"]
            assert [
                entry["instrumentId"]
                for entry in restored["list"]["visualizationEntries"]
            ] == ["SAN"]
            await client.delete(f"/api/workspaces/{workspace_id}")


class _PausableSession:
    """Delegación a la sesión real que pausa tras el primer SELECT.

    Reproduce el TOCTOU de la revisión optimista: la comprobación (SELECT) ocurre
    antes de que otro cliente confirme su escritura. Sin una escritura condicional,
    ambos PUT pasan la comprobación y el último gana en silencio.
    """

    def __init__(
        self, inner: Any, reached: asyncio.Event, resume: asyncio.Event
    ) -> None:
        self._inner = inner
        self._reached = reached
        self._resume = resume
        self._paused = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        result = await self._inner.execute(statement, *args, **kwargs)
        if not self._paused and str(statement).lstrip().lower().startswith("select"):
            self._paused = True
            self._reached.set()
            await self._resume.wait()
        return result


@pytest.mark.asyncio
async def test_two_updates_from_the_same_revision_do_not_both_win() -> None:
    """Dos clientes que leyeron la misma revisión: exactamente uno debe recibir 409."""
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            record = await SqlAlchemyWorkspaceRepository(session).create(
                name="Concurrencia",
                document=_document([], []),
                user_id="audit-user",
            )
            await session.commit()
            workspace_id = record.id
            revision = record.updated_at

        reached = asyncio.Event()
        resume = asyncio.Event()

        async with factory() as session_b:
            repo_b = SqlAlchemyWorkspaceRepository(
                _PausableSession(session_b, reached, resume)
            )

            async def second_writer() -> None:
                try:
                    await repo_b.update(
                        workspace_id,
                        owner_user_id="audit-user",
                        name="B",
                        expected_updated_at=revision,
                    )
                    await session_b.commit()
                except WorkspaceVersionConflict:
                    await session_b.rollback()
                    raise

            task = asyncio.create_task(second_writer())
            await asyncio.wait_for(reached.wait(), timeout=10)

            # El primero confirma mientras el segundo ya leyó la revisión antigua.
            async with factory() as session_a:
                await SqlAlchemyWorkspaceRepository(session_a).update(
                    workspace_id,
                    owner_user_id="audit-user",
                    name="A",
                    expected_updated_at=revision,
                )
                await session_a.commit()

            resume.set()
            with pytest.raises(WorkspaceVersionConflict):
                await asyncio.wait_for(task, timeout=10)

        async with factory() as session:
            repo = SqlAlchemyWorkspaceRepository(session)
            final = await repo.get_by_id(workspace_id)
            assert final is not None
            assert final.name == "A"
            await repo.delete(workspace_id, owner_user_id="audit-user")
            await session.commit()
    finally:
        await engine.dispose()


def test_close_workspace_charts_prunes_chart_list_context() -> None:
    charts = [_tab("t1", "SAN"), _tab("t2", "BBVA")]
    document = _document(charts, [_viz("SAN"), _viz("BBVA")])
    document["chartListContext"] = {"listId": "estudio", "instrumentId": "BBVA"}

    pruned = close_workspace_charts(document, ["BBVA"], None)

    assert pruned["chartListContext"] is None


@pytest.mark.asyncio
async def test_invalid_revision_is_rejected_instead_of_fail_open() -> None:
    """Una revisión malformada no debe desactivar la comprobación en silencio."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/workspaces",
                json={"name": "Revisión inválida", "document": _document([], [])},
            )
            workspace_id = created.json()["data"]["id"]

            response = await client.put(
                f"/api/workspaces/{workspace_id}",
                json={
                    "document": _document([], []),
                    "expectedUpdatedAt": "no-es-una-fecha",
                },
            )
            assert response.status_code == 400
            assert response.json()["detail"]["code"] == "workspace_invalid_revision"

            await client.delete(f"/api/workspaces/{workspace_id}")


@pytest.mark.asyncio
async def test_noop_close_with_stale_revision_still_conflicts() -> None:
    """Cerrar ids que ya no están abiertos no puede saltarse la revisión."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/workspaces",
                json={
                    "name": "Cierre idempotente",
                    "document": _document([_tab("t1", "SAN")], [_viz("SAN")]),
                },
            )
            workspace_id = created.json()["data"]["id"]
            stale = created.json()["data"]["updatedAt"]

            moved = await client.put(
                f"/api/workspaces/{workspace_id}",
                json={
                    "document": _document([_tab("t1", "SAN")], [_viz("SAN")]),
                    "expectedUpdatedAt": stale,
                },
            )
            assert moved.status_code == 200
            fresh = moved.json()["data"]["updatedAt"]
            assert fresh != stale

            noop = await client.post(
                f"/api/workspaces/{workspace_id}/charts/close",
                json={"instrumentIds": ["NO-EXISTE"], "expectedUpdatedAt": stale},
            )
            assert noop.status_code == 409
            assert noop.json()["detail"]["code"] == "workspace_conflict"

            ok = await client.post(
                f"/api/workspaces/{workspace_id}/charts/close",
                json={"instrumentIds": ["NO-EXISTE"], "expectedUpdatedAt": fresh},
            )
            assert ok.status_code == 200
            assert ok.json()["data"]["updatedAt"] == fresh

            await client.delete(f"/api/workspaces/{workspace_id}")
