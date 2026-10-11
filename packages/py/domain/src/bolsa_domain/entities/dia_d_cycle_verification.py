"""Entidad de dominio — verificación DÍA-D ENLAZADA a un ciclo AUTO (P2).

Sin dependencias externas. Registra, de forma durable, que la verificación manual
D→hoy del sandbox LAB se lanzó DESDE un ciclo concreto y con qué identidad EXACTA
de estrategia (``preset_key``/``version``/``definition_id``), además del resultado
declarado (banda + métricas).

Doctrina «Sin dato todavía» (``UNKNOWN != 0``): las claves de estrategia son
``None`` cuando el ciclo no las declara; un hueco NUNCA se rellena con ``""``/``0``.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DiaDCycleVerification:
    id: str
    cycle_id: str
    account_id: str | None
    instrument_id: str
    symbol: str
    dia_d: str
    end_date: str
    mode: str
    created_at: str
    strategy_preset_key: str | None = None
    strategy_version: str | None = None
    strategy_definition_id: str | None = None
    band: str | None = None
    result: dict[str, Any] | None = None
    research_evidence_id: str | None = None
