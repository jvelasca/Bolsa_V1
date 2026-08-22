"""Sesión stateless por cookie HttpOnly firmada (R-8B.2).

Diseño:
  - Sin store server-side: la cookie {@link SESSION_COOKIE_NAME} lleva
    ``"{exp:.0f}.{token}.{sig}"`` donde ``token`` es el SHA-256 existente de
    tokens.create_access_token, ``exp`` el deadline y ``sig`` el HMAC del valor firmado con app_auth_secret (comparación en tiempo
    constante).
  - El middleware valida la cookie alternativamente al header ``Authorization``
    Bearer; el FE migra a cookie y deja el Bearer como fallback para otros clientes.

`exp` es un deadline expresado en **Unix epoch UTC** (segundos desde
1970-01-01T00:00:00Z), calculado y comparado con ``time.time()``. Al ser un
timestamp absoluto y portable entre hosts, la misma cookie puede emitirse y
validarse en procesos o servidores distintos sin depender de un reloj
monotónico compartido. La longevidad se controla mediante el TTL aplicado en la
creación.

DEV (crítico): Secure=True impide que el navegador envíe la cookie sobre
http://localhost:8000 en desarrollo. Por eso la cookie solo se marca ``Secure``
cuando environment es producción (prod/production); en dev ``Secure=False`` para
que la sesión funcione en localhost (HTTP).
"""

import hashlib
import hmac
import secrets
import time

from bolsa_infrastructure.config import Settings

from bolsa_api.auth.tokens import create_access_token

SESSION_COOKIE_NAME = "bolsa_session"
SESSION_COOKIE_PATH = "/api"


def session_deadline(settings: Settings) -> int:
    """Deadline epoch UTC (segundos) de la sesión actual."""
    return int(time.time()) + settings.app_auth_ttl_seconds


def create_session_cookie_value(settings: Settings) -> str:
    """Construye el valor firmado de la cookie ``exp.token.sig``."""
    exp = session_deadline(settings)
    token = create_access_token(settings)
    sig = hmac.new(
        settings.app_auth_secret.encode(), f"{exp}.{token}".encode(), hashlib.sha256
    ).hexdigest()
    return f"{exp}.{token}.{sig}"


def verify_session_cookie(settings: Settings, value: str) -> bool:
    """Valida formato, firma, expiración y token de una cookie de sesión."""
    if not settings.app_password or not value:
        return False
    parts = value.split(".")
    if len(parts) != 3 or not all(parts):
        return False
    exp_raw, token, sig = parts
    try:
        exp = int(exp_raw)
    except ValueError:
        return False
    expected_sig = hmac.new(
        settings.app_auth_secret.encode(), f"{exp}.{token}".encode(), hashlib.sha256
    ).hexdigest()
    if not secrets.compare_digest(sig, expected_sig):
        return False
    if time.time() >= exp:
        return False
    return secrets.compare_digest(token, create_access_token(settings))


def cookie_secure(settings: Settings) -> bool:
    """Secure solo en producción; en dev a HTTP localhost no le llega la cookie."""
    return settings.environment.strip().lower() in {"prod", "production"}
