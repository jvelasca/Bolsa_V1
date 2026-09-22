"""AUTO-10 — el régimen del ciclo, DURABLE (contrato puro; la escritura la hace el llamante).

Qué cierra: el hueco que ``AUTO-9`` declaró en vez de inventar (``regime_not_durable``). El
worker ya conocía las dos piezas —el régimen del turno (``_v2_regime()``) y la identidad del
ciclo (``_v2_cycle_for()``)— pero las dejaba en una lista **en memoria**, así que el eje
``strategy × regime`` se quedaba sin insumo durable. Aquí vive el contrato de la entrada
append-only que las ata: ``cycleId`` + ``marketRegime``, con el estado de medición de cada
dimensión.

Tres reglas duras, declaradas en vez de asumidas:

* **Identidad derivada, nunca inventada.** Un ``cycle_id`` con forma ``cyc-<x>`` tiene por
  decisión ``dec-<x>``: es el mismo acuñado determinista de ``auto_v2_entry`` (la MISMA clave
  produce el mismo digest; solo cambia el prefijo), y es lo que permite leer por el índice de
  ``decision_id`` sin migración. Si el ``cycle_id`` no tiene esa forma, la entrada **no
  finge** una derivación: se marca con ``decision_id`` propio y se declara
  (``cycleIdDerived = False``) para que el lector sepa que el índice no la alcanza.
* **Sin ``cycle_id`` no hay entrada.** ``build_auto_cycle_regime_entry`` devuelve ``None``:
  es un no-op que el llamante **declara**, no una entrada con un ciclo vacío.
* **Régimen ausente = declarado, no disfrazado.** Sin régimen, ``marketRegime`` viaja ``None``
  **y** ``regimeMeasurement = UNKNOWN``: un consumidor distingue "preguntado y no medido" de
  "medido". Nunca se escribe un ``UNKNOWN`` de relleno como si fuera un valor de régimen.

Read-only respecto al dinero: este módulo **no** escribe en la base de datos; construye el
registro que el worker entrega a su sink durable.
"""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

__all__ = [
    "AUTO_CYCLE_REGIME_EVENT",
    "build_auto_cycle_regime_entry",
    "cycle_decision_id",
]

#: ``event_type`` de la entrada de régimen por ciclo (append-only en el journal del spine).
AUTO_CYCLE_REGIME_EVENT = "auto_cycle_regime"
#: Prefijos del acuñado determinista de ``auto_v2_entry`` (ciclo y decisión de la misma clave).
CYCLE_ID_PREFIX = "cyc-"
DECISION_ID_PREFIX = "dec-"


def cycle_decision_id(cycle_id: str | None) -> str | None:
    """``decision_id`` que corresponde a ``cycle_id`` por intercambio de prefijo, o ``None``.

    ``cyc-<x>`` ⇒ ``dec-<x>`` con la MISMA ``<x>``: no se recalcula ningún digest porque la
    clave que acuñó el ciclo es la que acuña la decisión. ``None`` cuando no hay ciclo o su
    forma no permite derivar: derivar a ciegas sería afirmar una identidad que no se puede
    probar.
    """
    text = str(cycle_id or "").strip()
    if not text.startswith(CYCLE_ID_PREFIX):
        return None
    suffix = text[len(CYCLE_ID_PREFIX) :].strip()
    return f"{DECISION_ID_PREFIX}{suffix}" if suffix else None


def _stamp(as_of: str) -> str:
    if as_of:
        return as_of
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_auto_cycle_regime_entry(
    *,
    cycle_id: str | None,
    market_regime: str | None,
    actor: str,
    as_of: str,
    account_id: str | None = None,
    instrument_id: str | None = None,
    strategy_version: str | None = None,
) -> DecisionJournalEntryRecord | None:
    """(PURA) entrada append-only con el régimen del ciclo abierto, o ``None`` sin ciclo.

    El ``payload`` es deliberadamente estable (hay golden en los tests): ``event``,
    ``cycleId``, ``marketRegime`` (``None`` = no medido), ``regimeMeasurement``
    (``COMPLETE``/``UNKNOWN``), ``cycleIdDerived`` y, **solo** si viaja, ``strategyVersion``
    (la ausencia no se disfraza).
    """
    from uuid import uuid4

    text = str(cycle_id or "").strip()
    if not text:
        return None
    regime = market_regime.strip() if isinstance(market_regime, str) else None
    derived = cycle_decision_id(text)
    measurement: MeasurementStatus = MEASUREMENT_COMPLETE if regime else MEASUREMENT_UNKNOWN
    payload: dict[str, Any] = {
        "event": AUTO_CYCLE_REGIME_EVENT,
        "cycleId": text,
        "marketRegime": regime or None,
        "regimeMeasurement": measurement,
        "cycleIdDerived": derived is not None,
    }
    if str(strategy_version or "").strip():
        payload["strategyVersion"] = str(strategy_version)
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=derived or f"{DECISION_ID_PREFIX}{uuid4().hex[:12]}",
        event_type=AUTO_CYCLE_REGIME_EVENT,
        actor=actor,
        created_at=_stamp(as_of),
        account_id=str(account_id or "").strip() or None,
        instrument_id=str(instrument_id or "").strip() or None,
        payload=payload,
    )
