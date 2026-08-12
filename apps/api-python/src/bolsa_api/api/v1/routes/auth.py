"""API: autenticación / estado de sesión."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.auth.tokens import create_access_token
from bolsa_infrastructure.config import get_settings

router = APIRouter()


class LoginRequestDto(BaseModel):
    password: str = Field(min_length=1)


class LoginResponseDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    token: str
    auth_enabled: bool = Field(alias="authEnabled")


class LoginResponseDto(BaseModel):
    data: LoginResponseDataDto


class AuthStatusDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    auth_enabled: bool = Field(alias="authEnabled")


class AuthStatusResponseDto(BaseModel):
    data: AuthStatusDataDto


@router.post("/auth/login", response_model=LoginResponseDto)
async def login(body: LoginRequestDto) -> LoginResponseDto:
    settings = get_settings()
    auth_enabled = bool(settings.app_password)

    if auth_enabled and body.password != settings.app_password:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    token = create_access_token(settings)
    return LoginResponseDto(
        data=LoginResponseDataDto(token=token, auth_enabled=auth_enabled),
    )


@router.get("/auth/status", response_model=AuthStatusResponseDto)
async def auth_status() -> AuthStatusResponseDto:
    settings = get_settings()
    return AuthStatusResponseDto(
        data=AuthStatusDataDto(auth_enabled=bool(settings.app_password)),
    )
