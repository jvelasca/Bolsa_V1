"""Rutas canónicas del artefacto DÍA-D AUTO — **aisladas por cuenta y día**.

Un artefacto por ``(cuenta, día)`` es la única forma de que dos cuentas que replayen el mismo
día no compitan por el mismo fichero. Antes de este módulo la ruta dependía solo del día
(``operability_runs/dia-d-auto/dia-d-auto-<D>.json``), de modo que dos jobs concurrentes de
cuentas distintas escribían el mismo fichero y uno de ellos podía fallar al leer el artefacto
sobrescrito por el otro.

Esquema vigente::

    operability_runs/dia-d-auto/<segmento-cuenta>/dia-d-auto-<D>.json
    operability_runs/dia-d-auto/<segmento-cuenta>/progress/<job>.jsonl

Reglas:

* El **segmento de cuenta** se deriva de forma determinista y segura: una cuenta con el
  alfabeto esperado (``[A-Za-z0-9_-]``) se usa tal cual; cualquier otra se sustituye por un
  hash estable (``acct-<sha256>``). Nunca se interpola la cuenta sin sanear: una cuenta como
  ``../otra`` no puede escapar del árbol.
* El **artefacto legacy** (ruta plana, sin cuenta) se conserva solo para **lectura**: el
  fallback acepta ese fichero únicamente si su ``meta.account`` coincide con la cuenta activa.
  Nunca se escribe en la ruta plana.
* Este módulo es puro (solo ``pathlib``/``re``/``hashlib``): no lee disco ni configuración, de
  modo que worker, ruta HTTP y CLI comparten exactamente el mismo esquema.
"""

from __future__ import annotations

import hashlib
import pathlib
import re

__all__ = [
    "DIA_D_ARTIFACT_DIR",
    "DIA_D_PROGRESS_SUBDIR",
    "account_segment",
    "artifact_relpath",
    "artifact_path",
    "legacy_artifact_path",
    "progress_relpath",
]

#: Carpeta raíz de artefactos, relativa a la raíz del repo.
DIA_D_ARTIFACT_DIR = pathlib.Path("operability_runs") / "dia-d-auto"

#: Subcarpeta del JSONL de progreso dentro del segmento de cuenta.
DIA_D_PROGRESS_SUBDIR = "progress"

#: Alfabeto admitido para usar la cuenta tal cual (evita ``.``/``/``/``\\`` y rutas relativas).
_SAFE_ACCOUNT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

#: Prefijo del segmento derivado cuando la cuenta no es segura.
_HASH_PREFIX = "acct-"


def account_segment(account_id: str) -> str:
    """Segmento de ruta **seguro y estable** para ``account_id``.

    Una cuenta con el alfabeto esperado se devuelve intacta (legible en disco); cualquier otra
    se mapea a ``acct-<sha256[:40]>``. La función es determinista: la misma cuenta produce
    siempre el mismo directorio, así que escritura y lectura coinciden sin coordinación.
    """
    value = (account_id or "").strip()
    if _SAFE_ACCOUNT.fullmatch(value):
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:40]
    return f"{_HASH_PREFIX}{digest}"


def artifact_relpath(day: str, account_id: str) -> pathlib.Path:
    """Ruta **relativa** del artefacto de ``(cuenta, día)`` dentro de la raíz del repo."""
    return DIA_D_ARTIFACT_DIR / account_segment(account_id) / f"dia-d-auto-{day}.json"


def artifact_path(root: pathlib.Path, day: str, account_id: str) -> pathlib.Path:
    """Ruta **absoluta** del artefacto de ``(cuenta, día)`` bajo ``root``."""
    return pathlib.Path(root) / artifact_relpath(day, account_id)


def legacy_artifact_path(root: pathlib.Path, day: str) -> pathlib.Path:
    """Ruta plana histórica (sin cuenta). Solo para **lectura** con ``meta.account`` verificado."""
    return pathlib.Path(root) / DIA_D_ARTIFACT_DIR / f"dia-d-auto-{day}.json"


def progress_relpath(job_id: str, account_id: str) -> pathlib.Path:
    """Ruta **relativa** del JSONL de progreso de un job (bajo el segmento de su cuenta)."""
    safe_job = re.sub(r"[^A-Za-z0-9_-]", "_", job_id or "") or "job"
    return (
        DIA_D_ARTIFACT_DIR
        / account_segment(account_id)
        / DIA_D_PROGRESS_SUBDIR
        / f"{safe_job}.jsonl"
    )
