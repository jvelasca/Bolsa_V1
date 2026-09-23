"""AUTO-11 — la recomendación Adaptive, DURABLE (contrato puro; la escritura la hace el llamante).

Qué cierra: la mitad de ``AUTO-8`` que no tenía memoria. Hasta ``V2.51`` el ``AdaptivePlan``
vivía **solo** en el proceso —se consumía en ``plan_v2_tick`` y moría al volver del turno—, así
que la única evidencia de "por qué Adaptive recomendó esto" era el payload de la decisión
APROBADA y solo cuando había estrechamiento. Aquí vive el contrato de la entrada append-only que
la guarda **entera**: rotación, asignación, eje de evidencia, salud por estrategia y el contador
de pausa que ENTRÓ a decidir.

Cuatro reglas duras, declaradas en vez de asumidas:

* **Sin plan no hay entrada.** ``build_adaptive_recommendation_entry`` devuelve ``None`` cuando no
  hay recomendación que registrar (flag OFF, sin store, lectura fallida): es un no-op que el
  llamante **declara**, nunca una fila con un plan vacío. Una fila vacía afirmaría "Adaptive
  evaluó y no recomendó nada", que es un hecho distinto de "Adaptive no evaluó".
* **La identidad es del TURNO, no del plan.** ``dec-adap-<hash(cuenta, asOf)>`` es determinista:
  un reintento del mismo turno **no duplica** evidencia (y si llegara a duplicarla, el lector la
  colapsa). No se deriva del ciclo ni de la decisión —la recomendación es de cartera, no de una
  operación—, y su forma NO es derivable a partir de un ``cyc-``: no se puede confundir con la
  traza de ``AUTO-10``.
* **Lo que no se midió se declara.** ``regime`` viaja ``None`` cuando no hay régimen (nunca un
  ``UNKNOWN`` de relleno) y ``healthByStrategy`` va vacío cuando ninguna estrategia trae fila: el
  lector distingue "evaluada sin evidencia" de "no evaluada".
* **Read-only, y se dice en la fila.** ``readOnly`` viaja en el payload como la declaración de que
  esto es una **recomendación**: la autoridad de ejecución sigue siendo el motor determinista.
  Dejar constancia durable de eso es justo lo que permite auditar el reparto de autoridad.

Read-only respecto al dinero: este módulo **no** escribe en la base de datos; construye el
registro que el worker entrega a su sink durable.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

__all__ = [
    "ADAPTIVE_RECOMMENDATION_DECISION_PREFIX",
    "AUTO_ADAPTIVE_RECOMMENDATION_EVENT",
    "adaptive_recommendation_decision_id",
    "build_adaptive_recommendation_entry",
]

#: ``event_type`` de la recomendación Adaptive durable (append-only en el journal del spine).
AUTO_ADAPTIVE_RECOMMENDATION_EVENT = "adaptive_recommendation"
#: Prefijo propio de la identidad del turno. Deliberadamente distinto de ``dec-<hex>`` (la
#: decisión por señal) y de ``cyc-<hex>`` (el ciclo): ninguna de las dos derivaciones de
#: ``AUTO-10`` puede alcanzar esta forma, así que no hay lectura cruzada posible.
ADAPTIVE_RECOMMENDATION_DECISION_PREFIX = "dec-adap-"

#: Claves del reparto que se publican tal cual (contrato de ``AllocationPlan.as_dict``). Se
#: listan para que el payload no dependa de lo que un día devuelva el plan: lo que no esté aquí
#: no viaja, y lo que falte se declara ausente.
_ROTATION_KEYS = ("paused", "byStrategy")
_ALLOCATION_KEYS = ("riskMultipliers", "evidenceAxis")


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _stamp(as_of: str) -> str:
    if as_of:
        return as_of
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int_map(raw: Any) -> dict[str, int]:
    """Contador de pausa normalizado (``> 0``) y ordenado: un ``0`` no es una pausa."""
    if not isinstance(raw, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, value in raw.items():
        version = _clean(key)
        if not version or isinstance(value, bool):
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            counts[version] = count
    return dict(sorted(counts.items()))


def _project(plan: Any, part: str, keys: tuple[str, ...]) -> dict[str, Any]:
    """(PURA) sub-dict declarado de un plan: solo las claves del contrato, sin inventar.

    Se proyecta en vez de volcar ``as_dict()`` entero para que la evidencia durable tenga una
    forma ESTABLE: una clave nueva del plan no puede colarse en la historia sin decidirlo aquí.
    """
    holder = getattr(plan, part, None)
    as_dict = getattr(holder, "as_dict", None)
    if not callable(as_dict):
        return {}
    raw = as_dict()
    if not isinstance(raw, Mapping):
        return {}
    return {key: raw[key] for key in keys if key in raw}


def _health_by_strategy(plan: Any) -> dict[str, Any]:
    """Salud por estrategia que sustentó la recomendación, ordenada por versión.

    Se pregunta al PROPIO plan (``evidence_for``) en vez de reconstruir los campos: la evidencia
    del journal es entonces, byte a byte, la misma que la decisión aprobada publica cuando hay
    estrechamiento. Una versión sin fila de salud simplemente no aparece: la ausencia se declara.
    """
    evidence_for = getattr(plan, "evidence_for", None)
    if not callable(evidence_for):
        return {}
    health: dict[str, Any] = {}
    for row in getattr(plan, "health", ()) or ():
        version = _clean(getattr(row, "strategy_version", None))
        if not version or version in health:
            continue
        evidence = evidence_for(version)
        if isinstance(evidence, Mapping):
            health[version] = dict(evidence)
    return dict(sorted(health.items()))


def adaptive_recommendation_decision_id(*, account_id: str | None, as_of: str) -> str:
    """Identidad determinista del TURNO de evaluación Adaptive (o una única si no hay instante).

    ``as_of`` es la clave del turno: dos evaluaciones de la misma cuenta en el mismo instante son
    la MISMA evaluación (un reintento del tick no es una recomendación nueva). Sin instante no hay
    clave estable que reclamar, así que se conserva el fallback aleatorio —igual que
    ``entry_decision_id`` con una señal sin barra—: una identidad única, nunca una compartida por
    accidente.
    """
    stamp = _clean(as_of)
    if not stamp:
        from uuid import uuid4

        return f"{ADAPTIVE_RECOMMENDATION_DECISION_PREFIX}{uuid4().hex[:12]}"
    key = f"{_clean(account_id)}\x1f{stamp}"
    digest = sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"{ADAPTIVE_RECOMMENDATION_DECISION_PREFIX}{digest}"


def build_adaptive_recommendation_entry(
    *,
    plan: Any,
    actor: str,
    as_of: str,
    account_id: str | None = None,
    paused_cycles: Mapping[str, int] | None = None,
) -> DecisionJournalEntryRecord | None:
    """(PURA) entrada append-only con la recomendación Adaptive del turno, o ``None`` sin plan.

    ``plan`` es el ``AdaptivePlan`` de ``AUTO-8`` (se lee por su contrato público: ``rotation``,
    ``allocation``, ``policy_version``, ``regime``, ``read_only``, ``health``/``evidence_for``).
    ``paused_cycles`` es el contador que **entró** a decidir —no el que sale—: es el dato con el
    que se reconstruye el cooldown tras un reinicio, y publicarlo aquí es lo que hace que un
    turno sea auditable sin releer los anteriores.
    """
    if plan is None:
        return None
    from uuid import uuid4

    stamp = _stamp(as_of)
    regime = _clean(getattr(plan, "regime", None))
    payload: dict[str, Any] = {
        "event": AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
        "asOf": stamp,
        "readOnly": bool(getattr(plan, "read_only", True)),
        "policyVersion": _clean(getattr(plan, "policy_version", None)) or None,
        "regime": regime or None,
        "rotation": _project(plan, "rotation", _ROTATION_KEYS),
        "allocation": _project(plan, "allocation", _ALLOCATION_KEYS),
        "pausedCycles": _int_map(paused_cycles),
        "healthByStrategy": _health_by_strategy(plan),
    }
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=adaptive_recommendation_decision_id(account_id=account_id, as_of=stamp),
        event_type=AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
        actor=actor,
        created_at=stamp,
        account_id=_clean(account_id) or None,
        payload=payload,
    )
