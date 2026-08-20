"""API: autenticación / estado de sesión."""

import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.auth.session import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    cookie_secure,
    create_session_cookie_value,
    verify_session_cookie,
)
from bolsa_infrastructure.config import get_settings

router = APIRouter()


class LoginRequestDto(BaseModel):
    password: str = Field(min_length=1)


class LoginResponseDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    auth_enabled: bool = Field(alias="authEnabled")


class LoginResponseDto(BaseModel):
    data: LoginResponseDataDto


class AuthStatusDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    auth_enabled: bool = Field(alias="authEnabled")
    authenticated: bool = Field(default=False)


class AuthStatusResponseDto(BaseModel):
    data: AuthStatusDataDto


@router.post("/auth/login", response_model=LoginResponseDto)
async def login(body: LoginRequestDto) -> JSONResponse:
    settings = get_settings()
    auth_enabled = bool(settings.app_password)

    if auth_enabled and not secrets.compare_digest(body.password, settings.app_password or ""):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    # R-8B.2: sesión stateless vía cookie HttpOnly firmada. `set_cookie` de
    # Starlette emite el `Set-Cookie` con HttpOnly/Secure/SameSite/Path. El
    # token ya no viaja en el body; solo `authEnabled`.
    response = JSONResponse(
        content=LoginResponseDto(
            data=LoginResponseDataDto(auth_enabled=auth_enabled)
        ).model_dump(by_alias=True),
        status_code=200,
    )
    if settings.app_auth_ttl_seconds > 0:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            create_session_cookie_value(settings),
            max_age=settings.app_auth_ttl_seconds,
            path=SESSION_COOKIE_PATH,
            secure=cookie_secure(settings),
            httponly=True,
            samesite="lax",
        )
    return response


@router.post("/auth/logout")
async def logout() -> JSONResponse:
    """Borra la cookie de sesión. Funciona aunque la auth esté desactivada."""
    response = JSONResponse(content={"data": {}}, status_code=200)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        secure=cookie_secure(get_settings()),
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/auth/status", response_model=AuthStatusResponseDto)
async def auth_status(request: Request) -> AuthStatusResponseDto:
    settings = get_settings()
    # R-8B.2: además de authEnabled, reporta si hay una sesión HttpOnly válida
    # (cookie firmada) para que el FE decida login vs shell en el arranque.
    authenticated = bool(
        settings.app_password
        and verify_session_cookie(
            settings, request.cookies.get(SESSION_COOKIE_NAME) or ""
        )
    )
    return AuthStatusResponseDto(
        data=AuthStatusDataDto(
            auth_enabled=bool(settings.app_password),
            authenticated=authenticated,
        ),
    )
