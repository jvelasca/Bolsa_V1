"""Entidad de dominio de evento de plataforma (auditoría) — sin dependencias externas."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PlatformEventRecord:
    id: str
    type: str
    payload: dict[str, Any]
    correlation_id: str | None
    user_id: str | None
    created_at: str
