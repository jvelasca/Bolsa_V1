import hashlib
import secrets

from bolsa_infrastructure.config import Settings


def create_access_token(settings: Settings) -> str:
    secret = settings.app_auth_secret
    password = settings.app_password or ""
    return hashlib.sha256(f"bolsa:{password}:{secret}".encode()).hexdigest()


def verify_access_token(settings: Settings, token: str) -> bool:
    if not settings.app_password:
        return True
    if not token:
        return False
    # F-SEG-1: comparación de token en tiempo constante para evitar timing attacks.
    return secrets.compare_digest(token, create_access_token(settings))
