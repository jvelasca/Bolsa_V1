"""Entidad de dominio — verificación DÍA-D ENLAZADA a un ciclo AUTO (P2).

Sin dependencias externas. Registra, de forma durable, que la verificación manual
D→hoy del sandbox LAB se lanzó DESDE un ciclo concreto y con qué identidad EXACTA
de estrategia (``preset_key``/``version``/``definition_id``), además del resultado
declarado (banda + métricas).

**Resuelta por servidor (v111).** La identidad del ciclo (instrumento y estrategia)
NO la declara el navegador: se DERIVA de los hechos durables AUTO antes de persistir.
``facts_hash`` sella QUÉ snapshot de hechos respaldó la verificación, de modo que un
ciclo sin identidad declarada viaja como hueco (``None``) y nunca se fabrica.

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
    #: v111 — hash determinista de los hechos durables del ciclo que respaldan la
    #: verificación (identidad derivada + ventana declarada). ``None`` = hueco declarado
    #: (fila anterior a la resolución por servidor), nunca un valor inventado.
    facts_hash: str | None = None
    #: v111 — actor humano que lanzó/confirmó la verificación, si lo declara.
    verified_by: str | None = None
