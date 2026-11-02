"""Casos de uso — espacios de trabajo (documento + dockLayout).

El cliente web decide el arranque: último activo local → default → primero.
«Nuevo en blanco» y «Duplicar» usan ambos `CreateWorkspace` con distinto `document`.

Ver docs/WORKSPACE_PERSISTENCE.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from bolsa_infrastructure.database.repositories.workspace_repository import (
    SqlAlchemyWorkspaceRepository,
    WorkspaceRecord,
    WorkspaceSummary,
    WorkspaceVersionConflict,
    parse_timestamp,
)

__all__ = [
    "CloseWorkspaceCharts",
    "CreateWorkspace",
    "DeleteWorkspace",
    "GetDefaultWorkspace",
    "GetWorkspace",
    "ListWorkspaces",
    "UpdateWorkspace",
    "WorkspaceVersionConflict",
    "close_workspace_charts",
]


def _iso_now() -> str:
    """Mismo formato que `new Date().toISOString()` (ms + `Z`)."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _instrument_id_from_snapshot_key(key: str) -> str | None:
    separator = key.find("::")
    return key[separator + 2 :] if separator >= 0 else None


def close_workspace_charts(
    document: dict[str, Any],
    instrument_ids: Iterable[str],
    active_chart_id: str | None = None,
) -> dict[str, Any]:
    """Devuelve el documento sin las pestañas de ``instrument_ids``.

    Poda, en una sola escritura, las tres vistas que deben ir siempre juntas:
    `charts`, `chartStateByListInstrument` y `list.visualizationEntries`
    (Visualizados). Es idempotente: ids ausentes no cambian nada.
    """
    closing = {instrument_id for instrument_id in instrument_ids if instrument_id}
    if not closing:
        return document

    charts_in = document.get("charts")
    if not isinstance(charts_in, list):
        charts_in = []
    charts = [
        tab
        for tab in charts_in
        if not (isinstance(tab, dict) and tab.get("instrumentId") in closing)
    ]
    removed = len(charts_in) - len(charts)
    if removed == 0:
        return document

    open_instrument_ids = {
        tab.get("instrumentId") for tab in charts if isinstance(tab, dict)
    }

    next_document: dict[str, Any] = {**document, "charts": charts}

    active_still_open = any(
        isinstance(tab, dict)
        and tab.get("id") == active_chart_id
        and tab.get("instrumentId") in open_instrument_ids
        for tab in charts
    )
    if active_chart_id is not None:
        next_document["activeChartId"] = (
            active_chart_id if active_still_open else (charts[-1].get("id") if charts else None)
        )

    snapshots = document.get("chartStateByListInstrument")
    if isinstance(snapshots, dict):
        next_document["chartStateByListInstrument"] = {
            key: snapshot
            for key, snapshot in snapshots.items()
            if _instrument_id_from_snapshot_key(key) in open_instrument_ids
        }

    list_config = document.get("list")
    if isinstance(list_config, dict):
        entries = list_config.get("visualizationEntries")
        if isinstance(entries, list):
            next_document["list"] = {
                **list_config,
                "visualizationEntries": [
                    entry
                    for entry in entries
                    if not (
                        isinstance(entry, dict)
                        and entry.get("instrumentId") in closing
                    )
                ],
            }

    # El contexto de lista apunta a la pestaña desde la que se abrió el gráfico.
    # Si esa pestaña desaparece, el contexto queda huérfano y la próxima fusión lo
    # resucita (mergeWorkspaceChartState lo prefería sobre el del documento nuevo).
    context = document.get("chartListContext")
    if isinstance(context, dict) and context.get("instrumentId") not in open_instrument_ids:
        next_document["chartListContext"] = None

    next_document["updatedAt"] = _iso_now()
    return next_document


def _revision_matches(current_iso: str, expected_iso: str | None) -> bool:
    """¿La revisión que envió el cliente es la vigente?

    ``parse_timestamp`` lanza ``WorkspaceInvalidRevision`` si el valor no es ISO-8601:
    una revisión corrupta no puede degradarse a "sin comprobación".
    """
    expected = parse_timestamp(expected_iso)
    if expected is None:
        return True
    return parse_timestamp(current_iso) == expected


class ListWorkspaces:
    """Lista Workspaces."""

    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(self, *, owner_user_id: str) -> list[WorkspaceSummary]:
        return await self._repo.list_all(owner_user_id=owner_user_id)


class GetWorkspace:
    """Obtiene Workspace."""

    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(self, workspace_id: str) -> WorkspaceRecord | None:
        return await self._repo.get_by_id(workspace_id)


class GetDefaultWorkspace:
    """Obtiene Default Workspace."""

    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(self, *, owner_user_id: str) -> WorkspaceRecord | None:
        return await self._repo.get_default(owner_user_id=owner_user_id)


class CreateWorkspace:
    """Crea un espacio. El web envía documento vacío (nuevo) o clon del activo (duplicar)."""

    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        name: str,
        document: dict[str, Any],
        dock_layout: dict[str, Any] | None = None,
        is_default: bool = False,
        user_id: str,
    ) -> WorkspaceRecord:
        if not name.strip():
            raise ValueError("Workspace name is required")
        count = await self._repo.count(owner_user_id=user_id)
        if count == 0:
            is_default = True
        return await self._repo.create(
            name=name,
            document=document,
            dock_layout=dock_layout,
            is_default=is_default,
            user_id=user_id,
        )


class UpdateWorkspace:
    """Actualiza Workspace."""

    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        workspace_id: str,
        *,
        owner_user_id: str,
        name: str | None = None,
        document: dict[str, Any] | None = None,
        dock_layout: dict[str, Any] | None = None,
        is_default: bool | None = None,
        expected_updated_at: str | None = None,
    ) -> WorkspaceRecord:
        if name is not None and not name.strip():
            raise ValueError("Workspace name is required")
        updated = await self._repo.update(
            workspace_id,
            owner_user_id=owner_user_id,
            name=name,
            document=document,
            dock_layout=dock_layout,
            is_default=is_default,
            expected_updated_at=expected_updated_at,
        )
        if updated is None:
            raise ValueError("Workspace not found")
        return updated


class CloseWorkspaceCharts:
    """Cierra pestañas de gráfico en el documento persistido (body mínimo).

    El cliente web lo usa al quitar valores de Visualizados y al cerrar el
    navegador: el documento completo con 200+ pestañas no cabe en un `keepalive`.
    """

    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        workspace_id: str,
        *,
        owner_user_id: str,
        instrument_ids: Iterable[str],
        active_chart_id: str | None = None,
        expected_updated_at: str | None = None,
    ) -> WorkspaceRecord:
        existing = await self._repo.get_by_id(workspace_id)
        if existing is None:
            raise ValueError("Workspace not found")
        # La revisión se comprueba ANTES de decidir si hay algo que podar: un cierre
        # idempotente (ids ya cerrados) tampoco puede aceptar una revisión obsoleta.
        if not _revision_matches(existing.updated_at, expected_updated_at):
            raise WorkspaceVersionConflict(existing.updated_at)
        document = close_workspace_charts(
            existing.document or {},
            instrument_ids,
            active_chart_id,
        )
        if document is existing.document:
            # Nada que podar: no se toca `updated_at` (idempotente de verdad).
            return existing
        updated = await self._repo.update(
            workspace_id,
            owner_user_id=owner_user_id,
            document=document,
            expected_updated_at=expected_updated_at,
        )
        if updated is None:
            raise ValueError("Workspace not found")
        return updated


class DeleteWorkspace:
    """Elimina Workspace."""

    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(self, workspace_id: str, *, owner_user_id: str) -> None:
        count = await self._repo.count(owner_user_id=owner_user_id)
        if count <= 1:
            raise ValueError("Cannot delete the last workspace")
        ok = await self._repo.delete(workspace_id, owner_user_id=owner_user_id)
        if not ok:
            raise ValueError("Workspace not found")
