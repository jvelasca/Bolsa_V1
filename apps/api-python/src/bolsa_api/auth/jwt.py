"""JWT HS256 — identidad autenticada (R12-AUTH F5 / ADR-027 C.2)."""

from __future__ import annotations

import time
from typing import Any

import jwt
from bolsa_infrastructure.config import Settings
from starlette.requests import Request

from bolsa_api.auth.session import SESSION_COOKIE_NAME

__all__ = [
    "decode_access_token",
    "encode_access_token",
    "extract_bearer_or_cookie_token",
    "extract_jwt_sub_from_request",
    "session_version_matches",
]


def encode_access_token(
    settings: Settings,
    *,
    sub: str,
    sv: int,
    role: str | None = None,
) -> str:
    now = int(time.time())
    ttl = settings.app_auth_ttl_seconds
    payload: dict[str, Any] = {
        "sub": sub,
        "sv": sv,
        "iat": now,
        "exp": now + ttl if ttl > 0 else now + 86400,
    }
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.jwt_signing_key_resolved(), algorithm="HS256")


def decode_access_token(settings: Settings, token: str) -> dict[str, Any] | None:
    if not token or not token.strip():
        return None
    try:
        claims = jwt.decode(
            token.strip(),
            settings.jwt_signing_key_resolved(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        return None
    return claims


def session_version_matches(claims: dict[str, Any], db_session_version: int) -> bool:
    sv = claims.get("sv")
    if sv is None:
        return False
    try:
        return int(sv) == db_session_version
    except (TypeError, ValueError):
        return False


def extract_bearer_or_cookie_token(
    request_headers: dict[str, str],
    cookie_value: str | None,
) -> str:
    auth_header = request_headers.get("authorization") or request_headers.get("Authorization") or ""
    bearer = auth_header.removeprefix("Bearer ").strip()
    if bearer:
        return bearer
    return (cookie_value or "").strip()


def extract_jwt_sub_from_request(request: Request) -> str | None:
    """``sub`` del JWT sin validar ``sv`` (p. ej. rate-limit antes del auth middleware)."""
    from bolsa_infrastructure.config import get_settings

    settings = get_settings()
    token = extract_bearer_or_cookie_token(
        dict(request.headers),
        request.cookies.get(SESSION_COOKIE_NAME),
    )
    claims = decode_access_token(settings, token)
    if claims is None:
        return None
    sub = claims.get("sub")
    return sub.strip() if isinstance(sub, str) and sub.strip() else None
