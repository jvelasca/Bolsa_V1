"""DTOs HTTP de espacios de trabajo."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    name: str
    is_default: bool = Field(alias="isDefault")
    updated_at: str = Field(alias="updatedAt")


class WorkspacePayloadDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    document: dict[str, Any]
    dock_layout: dict[str, Any] | None = Field(alias="dockLayout", default=None)


class WorkspaceDetailDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    name: str
    is_default: bool = Field(alias="isDefault")
    document: dict[str, Any]
    dock_layout: dict[str, Any] | None = Field(alias="dockLayout", default=None)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class WorkspacesListResponseDto(BaseModel):
    data: list[WorkspaceSummaryDto]


class WorkspaceResponseDto(BaseModel):
    data: WorkspaceDetailDto


class CreateWorkspaceRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    name: str = Field(min_length=1, max_length=128)
    document: dict[str, Any] | None = None
    dock_layout: dict[str, Any] | None = Field(alias="dockLayout", default=None)
    is_default: bool = Field(alias="isDefault", default=False)


class UpdateWorkspaceRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    name: str | None = Field(default=None, min_length=1, max_length=128)
    document: dict[str, Any] | None = None
    dock_layout: dict[str, Any] | None = Field(alias="dockLayout", default=None)
    is_default: bool | None = Field(alias="isDefault", default=None)
