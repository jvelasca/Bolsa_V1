"""Provenance de la instancia (recomendación P-alta del auditor externo V2.14).

Objetivo: que ``/api/health`` (y en el futuro ``/about`` + logs de arranque)
responda de forma unívoca y sin depender de que la BD esté arriba:

    PRODUCT_VERSION      → producto/release (ej. ``V2.14``)
    PACKAGE_VERSION      → versión del paquete/monorepo (ej. ``1.43.0-beta``)
    GIT_SHA              → commit exacto en HEAD
    DB_SCHEMA_VERSION    → revisión Alembic deseada (autoridad de esquema)
    API_CONTRACT_VERSION → versión del contrato OpenAPI que expone el proceso

Single source of truth:

- ``PACKAGE_VERSION`` se lee del ``package.json`` raíz (la versión que ya
  publican los bumps de release). No se duplica a mano.
- ``GIT_SHA`` se toma de la env ``GIT_SHA`` (inyectable por CI/build) y, si no
  está, de ``git rev-parse HEAD`` sobre el árbol de trabajo (best-effort).
- ``DB_SCHEMA_VERSION`` se deriva de la revisión Alembic ``head`` de los scripts
  de migración del workspace. Cero constantes a mano que puedan divergir del DDL.
- ``PRODUCT_VERSION`` y ``API_CONTRACT_VERSION`` son etiquetas semánticas de
  release; se leen de env con ``None`` por defecto (mejor ausente que inventado).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from bolsa_infrastructure.config import is_production_environment

# Ruta del monorepo raíz derivada de este fichero.
#   <root>/apps/api-python/src/bolsa_api/provenance.py
# parents[0]=bolsa_api · [1]=src · [2]=api-python · [3]=apps · [4]=<root>
_ROOT = Path(__file__).resolve().parents[4]

# Etiquetas semánticas de release que deben estar presentes en un build de
# producción (V2.15 hardening): sin ellas la instancia en marcha no puede
# identificarse inequívocamente ante una auditoría ni distinguir un binary real
# de uno local/desarrollador. Ver ``require_release_identity_env``.
RELEASE_IDENTITY_ENV = ("PRODUCT_VERSION", "API_CONTRACT_VERSION")


@dataclass(frozen=True)
class Provenance:
    """Bloque de provenance estable; ninguna lectura debe romper /health."""

    product: str | None
    package: str | None
    git_sha: str | None
    schema_revision: str | None
    api_contract: str | None
    sources: dict[str, str] = field(default_factory=dict)


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def missing_release_identity_env() -> list[str]:
    """Env de identidad de release ausentes (`PRODUCT_VERSION`/`API_CONTRACT_VERSION`)."""
    return [key for key in RELEASE_IDENTITY_ENV if not _env(key)]


def require_release_identity_env(environment: str) -> None:
    """Fail-fast gate de release: identidad de build obligatoria en producción.

    V2.15 (hardening): en un entorno **productivo** un binary que arranca sin
    ``PRODUCT_VERSION`` o ``API_CONTRACT_VERSION`` es indistinguible de una build
    local → bloqueamos el arranque en ``create_app``. En dev/test/staging (allowlist
    de ``is_production_environment``) estas env siguen siendo opcionales para no
    romper el arranque local ni el CI (que no las define); el bloque degrada al
    reporte ``null`` de siempre.
    """
    if not is_production_environment(environment):
        return
    missing = missing_release_identity_env()
    if missing:
        lista = ", ".join(missing)
        raise RuntimeError(
            "ENVIRONMENT=production exige identidad de release en build: "
            f"{lista} ausente(s). Defínela(s) al construir/imagen (no en runtime)."
        )


def _read_root_package_version() -> str | None:
    """Versión del package.json raíz (monorepo) → PACKAGE_VERSION."""
    try:
        data = json.loads((_ROOT / "package.json").read_text(encoding="utf-8"))
        version = data.get("version")
        return version if isinstance(version, str) and version else None
    except Exception:  # noqa: BLE001 — provenance nunca debe tumbar la API
        return None


def _read_db_schema_revision() -> str | None:
    """Revisión Alembic ``head`` esperada (DB_SCHEMA_VERSION).

    Resuelve la config Alembic igual que lo hace el bootstrap de migraciones,
    pero en modo lectura (no abre BD, no aplica nada). Si alembic no está
    disponible en este proceso se degrada a ``None``.
    """
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        infra_root = _ROOT / "packages" / "py" / "infrastructure"
        cfg = Config(str(infra_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(infra_root / "alembic"))
        heads = ScriptDirectory.from_config(cfg).get_heads()
        if not heads:
            return None
        # Línea lineal en este repo; si hubiera varias cabezas se reporta la de
        # mayor sufijo numérico (coincide con el guard "022") sin sintetizar merge.
        return sorted(heads, key=lambda h: (len(h), h), reverse=True)[0]
    except Exception:  # noqa: BLE001
        return None


def _read_git_sha() -> str | None:
    """GIT_SHA env si existe; si no, best-effort ``git rev-parse HEAD``."""
    env = _env("GIT_SHA")
    if env:
        return env
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        head = (proc.stdout or "").strip()
        return head or None
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def build_provenance() -> Provenance:
    """Ensambla y cachea el bloque de provenance de esta instancia."""
    product = _env("PRODUCT_VERSION")
    api_contract = _env("API_CONTRACT_VERSION")
    package = _read_root_package_version()
    schema_revision = _read_db_schema_revision()
    git_sha = _read_git_sha()

    sources: dict[str, str] = {
        "package": "root package.json version",
        "schema_revision": "alembic script head (desired schema)",
    }
    if git_sha:
        sources["git_sha"] = "GIT_SHA env" if _env("GIT_SHA") else "git rev-parse HEAD"
    if product:
        sources["product"] = "PRODUCT_VERSION env"
    if api_contract:
        sources["api_contract"] = "API_CONTRACT_VERSION env"

    return Provenance(
        product=product,
        package=package,
        git_sha=git_sha,
        schema_revision=schema_revision,
        api_contract=api_contract,
        sources=sources,
    )
