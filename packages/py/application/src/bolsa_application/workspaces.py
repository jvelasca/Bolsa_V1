"""Casos de uso — espacios de trabajo (documento + dockLayout).

El cliente web decide el arranque: último activo local → default → primero.
«Nuevo en blanco» y «Duplicar» usan ambos `CreateWorkspace` con distinto `document`.

Ver docs/WORKSPACE_PERSISTENCE.md.
"""

from __future__ import annotations

from typing import Any

from bolsa_infrastructure.database.repositories.workspace_repository import (
    SqlAlchemyWorkspaceRepository,
    WorkspaceRecord,
    WorkspaceSummary,
)


class ListWorkspaces:
    """Lista Workspaces."""
    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[WorkspaceSummary]:
        return await self._repo.list_all()


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

    async def execute(self) -> WorkspaceRecord | None:
        return await self._repo.get_default()


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
    ) -> WorkspaceRecord:
        if not name.strip():
            raise ValueError("Workspace name is required")
        count = await self._repo.count()
        if count == 0:
            is_default = True
        return await self._repo.create(
            name=name,
            document=document,
            dock_layout=dock_layout,
            is_default=is_default,
        )


class UpdateWorkspace:
    """Actualiza Workspace."""
    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        workspace_id: str,
        *,
        name: str | None = None,
        document: dict[str, Any] | None = None,
        dock_layout: dict[str, Any] | None = None,
        is_default: bool | None = None,
    ) -> WorkspaceRecord:
        if name is not None and not name.strip():
            raise ValueError("Workspace name is required")
        updated = await self._repo.update(
            workspace_id,
            name=name,
            document=document,
            dock_layout=dock_layout,
            is_default=is_default,
        )
        if updated is None:
            raise ValueError("Workspace not found")
        return updated


class DeleteWorkspace:
    """Elimina Workspace."""
    def __init__(self, repo: SqlAlchemyWorkspaceRepository) -> None:
        self._repo = repo

    async def execute(self, workspace_id: str) -> None:
        count = await self._repo.count()
        if count <= 1:
            raise ValueError("Cannot delete the last workspace")
        ok = await self._repo.delete(workspace_id)
        if not ok:
            raise ValueError("Workspace not found")
