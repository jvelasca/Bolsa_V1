"""API: autenticación / estado de sesión."""

import secrets

from bolsa_infrastructure.auth.passwords import verify_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.auth.jwt import (
    decode_access_token,
    encode_access_token,
    extract_bearer_or_cookie_token,
)
from bolsa_api.auth.session import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    cookie_secure,
    create_session_cookie_value,
    verify_session_cookie,
)

router = APIRouter()


class LoginRequestDto(BaseModel):
    password: str = Field(min_length=1)
    login: str | None = Field(default=None, min_length=1)


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


def _set_session_cookie(response: JSONResponse, cookie_value: str) -> None:
    settings = get_settings()
    if settings.app_auth_ttl_seconds <= 0:
        return
    response.set_cookie(
        SESSION_COOKIE_NAME,
        cookie_value,
        max_age=settings.app_auth_ttl_seconds,
        path=SESSION_COOKIE_PATH,
        secure=cookie_secure(settings),
        httponly=True,
        samesite="lax",
    )


def _session_is_authenticated(request: Request) -> bool:
    settings = get_settings()
    if not settings.app_password:
        return False
    token = extract_bearer_or_cookie_token(
        dict(request.headers),
        request.cookies.get(SESSION_COOKIE_NAME),
    )
    if decode_access_token(settings, token) is not None:
        return True
    return verify_session_cookie(settings, token)


@router.post("/auth/login", response_model=LoginResponseDto)
async def login(body: LoginRequestDto, request: Request) -> JSONResponse:
    settings = get_settings()
    auth_enabled = bool(settings.app_password)

    if not auth_enabled:
        response = JSONResponse(
            content=LoginResponseDto(
                data=LoginResponseDataDto(auth_enabled=False)
            ).model_dump(by_alias=True),
            status_code=200,
        )
        return response

    factory = request.app.state.session_factory
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        login_name = (body.login or settings.bootstrap_login()).strip()
        user = await repo.get_by_login(login_name)

        if user is not None:
            if user.disabled_at is not None:
                raise HTTPException(status_code=401, detail="Contraseña incorrecta")
            if not verify_password(body.password, user.password_hash):
                raise HTTPException(status_code=401, detail="Contraseña incorrecta")
            jwt_value = encode_access_token(
                settings,
                sub=user.id,
                role=user.role,
            )
            response = JSONResponse(
                content=LoginResponseDto(
                    data=LoginResponseDataDto(auth_enabled=True)
                ).model_dump(by_alias=True),
                status_code=200,
            )
            _set_session_cookie(response, jwt_value)
            return response

    if not secrets.compare_digest(body.password, settings.app_password or ""):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    response = JSONResponse(
        content=LoginResponseDto(
            data=LoginResponseDataDto(auth_enabled=auth_enabled)
        ).model_dump(by_alias=True),
        status_code=200,
    )
    _set_session_cookie(response, create_session_cookie_value(settings))
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
    return AuthStatusResponseDto(
        data=AuthStatusDataDto(
            auth_enabled=bool(settings.app_password),
            authenticated=_session_is_authenticated(request),
        ),
    )
