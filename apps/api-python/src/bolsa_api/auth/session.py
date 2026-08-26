"""Cookie HttpOnly de sesión JWT (R12-AUTH / ADR-027 C.2).

La cookie ``SESSION_COOKIE_NAME`` transporta el JWT HS256 emitido en login
y refresh. El middleware autentica únicamente con JWT válido (cookie o
Bearer). ``Secure`` solo se marca en producción para que localhost HTTP
reciba la cookie en desarrollo.
"""

from bolsa_infrastructure.config import Settings, is_production_environment

SESSION_COOKIE_NAME = "bolsa_session"
SESSION_COOKIE_PATH = "/api"


def cookie_secure(settings: Settings) -> bool:
    """Secure en producción; dev/staging/local permiten HTTP localhost."""
    return is_production_environment(settings.environment)
