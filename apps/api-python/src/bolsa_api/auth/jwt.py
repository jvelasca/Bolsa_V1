"""JWT HS256 — identidad autenticada (R12-AUTH F5 / ADR-027 C.2)."""

from __future__ import annotations

import time
from typing import Any

import jwt
from bolsa_infrastructure.config import Settings

__all__ = [
    "decode_access_token",
    "encode_access_token",
    "extract_bearer_or_cookie_token",
]


def encode_access_token(
    settings: Settings,
    *,
    sub: str,
    role: str | None = None,
) -> str:
    now = int(time.time())
    ttl = settings.app_auth_ttl_seconds
    payload: dict[str, Any] = {
        "sub": sub,
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


def extract_bearer_or_cookie_token(
    request_headers: dict[str, str],
    cookie_value: str | None,
) -> str:
    auth_header = request_headers.get("authorization") or request_headers.get("Authorization") or ""
    bearer = auth_header.removeprefix("Bearer ").strip()
    if bearer:
        return bearer
    return (cookie_value or "").strip()
