"""Entidad de dominio — job operativo AUTO (cola durable de trabajos).

Un job representa una unidad de trabajo **de servidor** con progreso y desenlace
observables: la generación diaria del universo ESTUDIO (``estudio_daily``), la
ejecución manual del sandbox DÍA-D AUTO (``dia_d_replay``) y la verificación DÍA-D
de **un valor** de ESTUDIO (``dia_d_value_replay``).

Doctrina «Sin dato todavía» (``UNKNOWN != 0``): ``progress``/``result`` viajan como
diccionarios posibles vacíos; un hueco NUNCA se rellena con ceros inventados. El
``error`` es ``None`` mientras no haya fallo declarado.

Sin dependencias externas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Tipos de job soportados.
JOB_KIND_ESTUDIO_DAILY = "estudio_daily"
JOB_KIND_DIA_D_REPLAY = "dia_d_replay"
#: Verificación DÍA-D del sandbox **acotada a un valor** (``payload.symbol`` obligatorio).
#: Escribe en un artefacto propio (``…/values/<SYMBOL>/…``) y nunca pisa el del día.
JOB_KIND_DIA_D_VALUE_REPLAY = "dia_d_value_replay"
JOB_KINDS: tuple[str, ...] = (
    JOB_KIND_ESTUDIO_DAILY,
    JOB_KIND_DIA_D_REPLAY,
    JOB_KIND_DIA_D_VALUE_REPLAY,
)

#: Estados del ciclo de vida.
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
#: Estados que ocupan el hueco de idempotencia ``(kind, cuenta, día)``.
JOB_ACTIVE_STATUSES: tuple[str, ...] = (JOB_STATUS_QUEUED, JOB_STATUS_RUNNING)


@dataclass(frozen=True, slots=True)
class AutoOpsJob:
    """Foto inmutable de un job operativo."""

    id: str
    kind: str
    status: str
    day: str
    account_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    progress: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempt: int = 0
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    heartbeat_at: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status in JOB_ACTIVE_STATUSES
