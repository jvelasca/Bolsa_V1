"""API: autenticación / estado de sesión.

Con auth ON (``APP_PASSWORD``) el login exige un usuario en ``users`` y
``verify_password``; la cookie de sesión es el JWT HS256. Sin fila de
usuario → 401. El status trata autenticado solo si el JWT decodifica.
"""

import logging

from bolsa_infrastructure.auth.passwords import verify_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import UserRow
from bolsa_infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.auth.jwt import (
    decode_access_token,
    encode_access_token,
    extract_bearer_or_cookie_token,
    session_version_matches,
)
from bolsa_api.auth.session import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    cookie_secure,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    return decode_access_token(settings, token) is not None


async def _resolve_jwt_user(
    request: Request, token: str
) -> tuple[UserRow | None, dict[str, object] | None]:
    settings = get_settings()
    claims = decode_access_token(settings, token)
    if claims is None:
        return None, None
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        return None, None

    factory = request.app.state.session_factory
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        user = await repo.get_by_id(sub.strip())
        if user is None or user.disabled_at is not None:
            return None, None
        if not session_version_matches(claims, user.session_version):
            return None, None
        return user, claims


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

        if user is None or user.disabled_at is not None:
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        if not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        jwt_value = encode_access_token(
            settings,
            sub=user.id,
            sv=user.session_version,
            role=user.role,
        )
        logger.info(
            "auth.login.success user_id=%s login=%s",
            user.id,
            user.login,
        )
        response = JSONResponse(
            content=LoginResponseDto(
                data=LoginResponseDataDto(auth_enabled=True)
            ).model_dump(by_alias=True),
            status_code=200,
        )
        _set_session_cookie(response, jwt_value)
        return response


@router.post("/auth/refresh")
async def refresh(request: Request) -> JSONResponse:
    """Re-emite JWT con nuevo ``exp`` si el access token (cookie o Bearer) sigue válido."""
    settings = get_settings()
    if not settings.app_password:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = extract_bearer_or_cookie_token(
        dict(request.headers),
        request.cookies.get(SESSION_COOKIE_NAME),
    )
    user, _claims = await _resolve_jwt_user(request, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    jwt_value = encode_access_token(
        settings,
        sub=user.id,
        sv=user.session_version,
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


@router.post("/auth/logout")
async def logout(request: Request) -> JSONResponse:
    """Borra la cookie de sesión. JWT users: invalida tokens previos (logout-all)."""
    settings = get_settings()
    token = extract_bearer_or_cookie_token(
        dict(request.headers),
        request.cookies.get(SESSION_COOKIE_NAME),
    )
    user, _claims = await _resolve_jwt_user(request, token)
    if user is not None:
        factory = request.app.state.session_factory
        async with factory() as session:
            repo = SqlAlchemyUserRepository(session)
            await repo.increment_session_version(user.id)

    response = JSONResponse(content={"data": {}}, status_code=200)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        secure=cookie_secure(settings),
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
