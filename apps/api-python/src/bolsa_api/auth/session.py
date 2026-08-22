"""Cookie HttpOnly de sesión JWT (R12-AUTH / ADR-027 C.2).

La cookie ``SESSION_COOKIE_NAME`` transporta el JWT HS256 emitido en login
y refresh. El middleware autentica únicamente con JWT válido (cookie o
Bearer). ``Secure`` solo se marca en producción para que localhost HTTP
reciba la cookie en desarrollo.
"""

from bolsa_infrastructure.config import Settings

SESSION_COOKIE_NAME = "bolsa_session"
SESSION_COOKIE_PATH = "/api"


def cookie_secure(settings: Settings) -> bool:
    """Secure solo en producción; en dev a HTTP localhost no le llega la cookie."""
    return settings.environment.strip().lower() in {"prod", "production"}
