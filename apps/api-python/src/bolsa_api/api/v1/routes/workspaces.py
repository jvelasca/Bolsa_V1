"""Rutas HTTP de espacios de trabajo (`/api/workspaces`).

El cliente elige al arrancar el último activo local; `isDefault` es reserva.
UI: chip barra superior → gestor (nuevo en blanco / duplicar vía POST con documento).

Ver docs/WORKSPACE_PERSISTENCE.md y docs/API_REFERENCE.md § Workspaces.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session, get_workspace_repository
from bolsa_api.auth.principal import account_visible_to_principal
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.schemas.workspaces import (
    CreateWorkspaceRequestDto,
    UpdateWorkspaceRequestDto,
    WorkspaceDetailDto,
    WorkspaceResponseDto,
    WorkspacesListResponseDto,
    WorkspaceSummaryDto,
)
from bolsa_application.workspaces import (
    CreateWorkspace,
    DeleteWorkspace,
    GetDefaultWorkspace,
    GetWorkspace,
    ListWorkspaces,
    UpdateWorkspace,
)
from bolsa_infrastructure.database.repositories.workspace_repository import (
    WorkspaceRecord,
    WorkspaceSummary,
)

router = APIRouter()

DEFAULT_DOCUMENT = {
    "version": 1,
    "id": "default",
    "name": "Espacio de trabajo",
    "updatedAt": "1970-01-01T00:00:00.000Z",
    "layout": {
        "listPanelOpen": True,
        "listPanelSizePct": 28,
        "rightPanelOpen": True,
        "rightPanelSizePct": 24,
        "activeRoute": "/trading",
    },
    "preferences": {"autoSave": True, "openOnStartup": True},
    "charts": [],
    "activeChartId": None,
    "list": {
        "id": "ibex35",
        "name": "IBEX 35",
        "source": "api",
        "columns": ["symbol", "lastClose", "changePct"],
    },
}


def _require_workspace_access(
    record: WorkspaceRecord | None,
    principal: str,
) -> WorkspaceRecord:
    if record is None or not account_visible_to_principal(record.user_id, principal):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return record


def _to_summary_dto(item: WorkspaceSummary) -> WorkspaceSummaryDto:
    return WorkspaceSummaryDto(
        id=item.id,
        name=item.name,
        is_default=item.is_default,
        updated_at=item.updated_at,
    )


def _to_detail_dto(item: WorkspaceRecord) -> WorkspaceDetailDto:
    return WorkspaceDetailDto(
        id=item.id,
        name=item.name,
        is_default=item.is_default,
        document=item.document,
        dock_layout=item.dock_layout,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/workspaces", response_model=WorkspacesListResponseDto)
async def list_workspaces(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspacesListResponseDto:
    principal = get_request_principal(request)
    repo = get_workspace_repository(session)
    items = await ListWorkspaces(repo).execute(owner_user_id=principal)
    return WorkspacesListResponseDto(data=[_to_summary_dto(item) for item in items])


@router.get("/workspaces/default", response_model=WorkspaceResponseDto)
async def get_default_workspace(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponseDto:
    principal = get_request_principal(request)
    repo = get_workspace_repository(session)
    record = await GetDefaultWorkspace(repo).execute(owner_user_id=principal)
    if record is None:
        created = await CreateWorkspace(repo).execute(
            name="Espacio de trabajo",
            document=DEFAULT_DOCUMENT,
            is_default=True,
            user_id=principal,
        )
        return WorkspaceResponseDto(data=_to_detail_dto(created))
    return WorkspaceResponseDto(data=_to_detail_dto(record))


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponseDto)
async def get_workspace(
    workspace_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponseDto:
    principal = get_request_principal(request)
    repo = get_workspace_repository(session)
    record = await GetWorkspace(repo).execute(workspace_id)
    record = _require_workspace_access(record, principal)
    return WorkspaceResponseDto(data=_to_detail_dto(record))


@router.post("/workspaces", response_model=WorkspaceResponseDto, status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequestDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponseDto:
    principal = get_request_principal(request)
    repo = get_workspace_repository(session)
    try:
        created = await CreateWorkspace(repo).execute(
            name=body.name,
            document=body.document or DEFAULT_DOCUMENT,
            dock_layout=body.dock_layout,
            is_default=body.is_default,
            user_id=principal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceResponseDto(data=_to_detail_dto(created))


@router.put("/workspaces/{workspace_id}", response_model=WorkspaceResponseDto)
async def update_workspace(
    workspace_id: str,
    body: UpdateWorkspaceRequestDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponseDto:
    principal = get_request_principal(request)
    repo = get_workspace_repository(session)
    existing = await GetWorkspace(repo).execute(workspace_id)
    _require_workspace_access(existing, principal)
    try:
        updated = await UpdateWorkspace(repo).execute(
            workspace_id,
            owner_user_id=principal,
            name=body.name,
            document=body.document,
            dock_layout=body.dock_layout,
            is_default=body.is_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WorkspaceResponseDto(data=_to_detail_dto(updated))


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    principal = get_request_principal(request)
    repo = get_workspace_repository(session)
    existing = await GetWorkspace(repo).execute(workspace_id)
    _require_workspace_access(existing, principal)
    try:
        await DeleteWorkspace(repo).execute(workspace_id, owner_user_id=principal)
    except ValueError as exc:
        status = 404 if str(exc) == "Workspace not found" else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
