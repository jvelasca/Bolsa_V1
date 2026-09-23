"""AUTO-11 — el estado Adaptive, RECONSTRUIDO desde el journal durable (puro sobre las filas).

Qué cierra: la deuda que ``V2.51`` declaró en su propio audit-pack («el cooldown sigue en
memoria»). ``_v2_adaptive_paused_cycles`` vivía en el proceso y se reconstruía del plan anterior,
así que un reinicio lo devolvía a ``0``: una estrategia pausada podía **levantar su pausa antes de
cumplir su ventana mínima**, que es justo lo que la hysteresis de ``AUTO-8.1`` existe para evitar.

La pieza que lo hace durable ya estaba escrita: ``AUTO-11`` publica cada evaluación Adaptive como
una fila append-only (``auto_adaptive_journal``). Aquí se lee esa historia y se **rehace** el
contador con la MISMA regla que lo hacía el proceso, sin tabla nueva y sin migración.

**Cómo se rehace, y por qué así.** ``_v2_next_paused_cycles`` (el estado vivo) hacía, por turno:

    nuevo_contador = {v: anterior[v] + 1  para cada v en plan.rotation.paused}

o sea: una versión que **no** está pausada en un turno desaparece del mapa (cuenta a 0), y una que
sí lo está suma uno. Recorrer las evaluaciones de **nueva a vieja** y contar la **racha inicial**
de pausas por versión reproduce eso exactamente: el primer turno en que la versión no aparece
pausada cierra la racha, y el número de filas consecutivas cuenta lo mismo que contaba el proceso.

**Saturación declarada.** El valor publicado se limita a ``min_pause_cycles + 1``. No es una
pérdida: el único consumo del contador es ``count < min_pause_cycles`` y ``count <= 0`` (las ramas
de cooldown e hysteresis de ``recommend_rotation``), así que cualquier valor por encima del umbral
significa lo mismo. Saturar además evita que el número crezca sin límite en la historia.

**Una evaluación por TURNO.** La identidad de la recomendación es determinista por turno
(``dec-adap-<hash>``), así que dos filas con el mismo ``decision_id`` son la MISMA evaluación
escrita dos veces (reintento del sink), no dos turnos. Se colapsan antes de contar —``collapsed``
lo declara— porque contarlas dos veces inflaría la racha y alargaría el cooldown: se afirmaría un
turno que no ocurrió. Es el mismo dedupe que el lector de régimen hace con las trazas de un ciclo.

**Tres huecos, declarados y distintos** (la disciplina de ``cycle_risk``/``AUTO-10``):

* ``read_ok = False`` — la fuente durable **no se pudo leer**: no hay contador y no se finge que no
  hubiera pausas (``adaptive_state_unread``). Es el caso que separa "leí y no había" de "no leí".
* ``insufficient_history`` — se leyeron menos filas que la ventana pedida: la racha es un **suelo**
  porque la historia puede no alcanzar. Se declara, no se convierte en ``0``.
* ``unreadable`` — filas sin el contrato de rotación usable (``rotation.paused``). Cuentan como
  corte de racha (fail-closed: no se afirma una pausa que no se puede leer) y se cuentan aparte.

**Continuidad de política.** El contador **se conserva** a través de un cambio de ``policyVersion``
—resetearlo sería exactamente el bug que esta fase cierra— y desde el turno siguiente mandan los
umbrales de la política en curso. La mezcla se declara (``policy_version_mismatch`` y
``policy_versions``) para que nadie interprete retrospectivamente el pasado con reglas nuevas: la
historia no se reescribe, solo se declara.

Read-only: no escribe nada. El puerto de lectura es el mismo del spine (``list_entries`` filtrado
por ``event_type``), así que la lectura va por columnas con índice y no por el ``payload``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bolsa_application.auto_adaptive_journal import (
    AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
)

__all__ = [
    "ADAPTIVE_STATE_WINDOW_DEFAULT",
    "AdaptiveStateReading",
    "adaptive_state_unread",
    "read_adaptive_state",
    "rebuild_paused_cycles",
]

#: Ventana por defecto de evaluaciones leídas. Tiene que superar holgadamente
#: ``min_pause_cycles`` (default 3) para que la racha se pueda probar entera.
ADAPTIVE_STATE_WINDOW_DEFAULT = 50

#: ``event_type`` que se lee (el que escribe ``auto_adaptive_journal``).
ADAPTIVE_RECOMMENDATION_EVENT = AUTO_ADAPTIVE_RECOMMENDATION_EVENT


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _payload_of(entry: Any) -> Mapping[str, Any]:
    """``payload`` de la fila, acepte el registro del spine o un mapping (tests/evidence)."""
    payload = getattr(entry, "payload", None)
    if isinstance(payload, Mapping):
        return payload
    if isinstance(entry, Mapping):
        nested = entry.get("payload")
        if isinstance(nested, Mapping):
            return nested
        return entry
    return {}


def _instant_of(entry: Any) -> datetime | None:
    raw = getattr(entry, "created_at", None)
    if not isinstance(raw, str) or not raw.strip():
        if isinstance(entry, Mapping):
            raw = entry.get("created_at")
        if not isinstance(raw, str) or not raw.strip():
            return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _identity_of(entry: Any) -> str:
    for name in ("id", "decision_id"):
        value = getattr(entry, name, None)
        if not isinstance(value, str) and isinstance(entry, Mapping):
            value = entry.get(name)
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return ""


def _turn_key_of(entry: Any) -> str:
    """Clave del TURNO de la fila (``decision_id``), o ``""`` si la fila no la declara.

    La identidad de la recomendación es determinista por turno (``dec-adap-<hash>``), así que dos
    filas con el mismo ``decision_id`` son **la misma evaluación escrita dos veces**, no dos
    evaluaciones. Es el mismo dedupe que hace el lector de régimen con las trazas de un ciclo.
    """
    value = getattr(entry, "decision_id", None)
    if not isinstance(value, str) and isinstance(entry, Mapping):
        value = entry.get("decision_id")
    return _clean(value)


def _ordered(rows: Sequence[Any]) -> list[Any]:
    """Filas de la evaluación **más nueva a más vieja**, ordenadas por instante de forma defensiva.

    El puerto real (``list_entries``) ya sirve ``created_at DESC``, pero el orden aquí no es un
    detalle de estilo: una fila fuera de sitio corrompería la racha y reactivaría una pausa antes
    de tiempo. Un instante ilegible se ordena al final (nunca se le supone "lo más nuevo") y el
    desempate por identidad mantiene el resultado determinista.
    """
    return sorted(
        rows,
        key=lambda entry: (
            _instant_of(entry) or datetime.min.replace(tzinfo=UTC),
            _identity_of(entry),
        ),
        reverse=True,
    )


def _dedupe(ordered: Sequence[Any]) -> tuple[list[Any], int]:
    """Una fila por TURNO (gana la más nueva); devuelve las que quedan y cuántas se colapsaron.

    Sin esto, un reintento del sink inflaría la racha y alargaría el cooldown: contar dos veces la
    misma evaluación es afirmar un turno que no ocurrió.
    """
    seen: set[str] = set()
    kept: list[Any] = []
    collapsed = 0
    for entry in ordered:
        key = _turn_key_of(entry) or _identity_of(entry)
        if not key:
            kept.append(entry)
            continue
        if key in seen:
            collapsed += 1
            continue
        seen.add(key)
        kept.append(entry)
    return kept, collapsed


def _paused_set(payload: Mapping[str, Any]) -> frozenset[str] | None:
    """Versiones pausadas de una evaluación; ``None`` si la fila no trae el contrato usable.

    ``None`` no es "no había pausas" (eso es un conjunto vacío): es "esta fila no se puede leer
    como evaluación", y tratarla como vacía afirmaría una reactivación que no ocurrió.
    """
    rotation = payload.get("rotation")
    if not isinstance(rotation, Mapping):
        return None
    raw = rotation.get("paused")
    if raw is None or isinstance(raw, (str, bytes)) or not isinstance(raw, Iterable):
        return None
    paused: set[str] = set()
    for item in raw:
        version = _clean(item)
        if version:
            paused.add(version)
    return frozenset(paused)


def _policy_version_of(payload: Mapping[str, Any]) -> str:
    return _clean(payload.get("policyVersion"))


def rebuild_paused_cycles(
    rows: Sequence[Any],
    *,
    min_pause_cycles: int,
) -> tuple[dict[str, int], dict[str, str], int]:
    """(PURA) racha de pausa por versión, reconstruida de las evaluaciones (nueva→vieja primero).

    Devuelve ``(contador, motivos, colapsadas)``. ``contador`` solo trae versiones con racha
    ``> 0`` —una versión que no está pausada no debe aparecer, igual que en el mapa vivo— y su
    valor está **saturado** en ``min_pause_cycles + 1``. ``motivos`` declara, por versión, por qué
    el valor es un suelo (``bounded``) en vez de una cuenta probada. ``colapsadas`` son las filas
    de más del mismo turno (reintento del sink) que no se cuentan dos veces.
    """
    cap = max(0, int(min_pause_cycles)) + 1
    ordered, collapsed = _dedupe(_ordered(rows))
    counts, reasons = _streaks([_payload_of(entry) for entry in ordered], cap=cap)
    return counts, reasons, collapsed


def _streaks(
    payloads: Sequence[Mapping[str, Any]], *, cap: int
) -> tuple[dict[str, int], dict[str, str]]:
    """(PURA) racha inicial de pausas por versión sobre evaluaciones ordenadas nueva→vieja.

    Una versión que no está pausada en un turno corta su racha —da igual si porque el plan la
    reactivó o porque desapareció del mapa: el estado vivo hacía exactamente lo mismo— y una fila
    ilegible también (fail-closed: no se afirma una pausa que no se puede leer).
    """
    versions: set[str] = set()
    for payload in payloads:
        versions.update(_paused_set(payload) or ())
        rotation = payload.get("rotation")
        if isinstance(rotation, Mapping):
            for row in rotation.get("byStrategy") or ():
                if isinstance(row, Mapping):
                    version = _clean(row.get("strategyVersion"))
                    if version:
                        versions.add(version)

    counts: dict[str, int] = {}
    reasons: dict[str, str] = {}
    for version in sorted(versions):
        streak = 0
        proven = False
        for payload in payloads:
            paused = _paused_set(payload)
            if paused is None or version not in paused:
                # Racha cortada (o fila ilegible): el proceso vivo habría quitado la versión
                # del mapa en ese turno, así que la cuenta termina aquí y queda PROBADA.
                proven = True
                break
            streak += 1
        if streak <= 0:
            continue
        counts[version] = min(streak, cap)
        if not proven:
            # Se agotó la ventana sin encontrar el corte: la racha verdadera es ``>= streak``.
            reasons[version] = "bounded"
    return counts, reasons


@dataclass(frozen=True, slots=True)
class AdaptiveStateReading:
    """El estado Adaptive reconstruido + el motivo declarado de cada límite de la lectura.

    ``read_ok`` es el que separa los dos "no hay nada": ``False`` significa que la fuente durable
    **no se pudo leer** (el contador viene vacío porque no se miró, no porque no hubiera pausas).
    """

    paused_cycles: Mapping[str, int] = field(default_factory=dict)
    read_ok: bool = True
    evaluated: int = 0
    requested: int = 0
    policy_versions: tuple[str, ...] = ()
    policy_version_mismatch: bool = False
    bounded: tuple[str, ...] = ()
    insufficient_history: bool = False
    unreadable: int = 0
    #: Filas de más del MISMO turno (reintento del sink) colapsadas antes de contar.
    collapsed: int = 0

    @property
    def saturated(self) -> bool:
        """True si alguna racha quedó recortada por el techo (el valor publicado es un suelo)."""
        return bool(self.bounded)

    @property
    def paused(self) -> tuple[str, ...]:
        return tuple(sorted(self.paused_cycles))

    def as_dict(self) -> dict[str, Any]:
        """Resumen para el log del llamante: lo reconstruido y TODOS los límites declarados."""
        return {
            "readOk": self.read_ok,
            "evaluated": self.evaluated,
            "requested": self.requested,
            "paused": list(self.paused),
            "pausedCycles": dict(sorted(self.paused_cycles.items())),
            "policyVersions": list(self.policy_versions),
            "policyVersionMismatch": self.policy_version_mismatch,
            "bounded": list(self.bounded),
            "insufficientHistory": self.insufficient_history,
            "unreadableRows": self.unreadable,
            "collapsedRows": self.collapsed,
        }


def read_adaptive_state(
    rows: Sequence[Any],
    *,
    min_pause_cycles: int,
    running_policy_version: str = "",
    window: int = ADAPTIVE_STATE_WINDOW_DEFAULT,
    read_ok: bool = True,
) -> AdaptiveStateReading:
    """(PURA sobre las filas) la lectura completa: contador reconstruido + todo lo declarado.

    ``rows`` son las evaluaciones durables (``adaptive_recommendation``). ``window`` es cuántas se
    pidieron: con menos EVALUACIONES que la ventana, la antigüedad de la racha no está probada y se
    declara ``insufficient_history``. Un reintento del sink (misma evaluación dos veces) se colapsa
    antes de contar y se declara en ``collapsed``.
    """
    ordered, collapsed = _dedupe(_ordered(rows))
    payloads = [_payload_of(entry) for entry in ordered]
    counts, reasons = _streaks(payloads, cap=max(0, int(min_pause_cycles)) + 1)
    versions: list[str] = []
    for entry in ordered:
        version = _policy_version_of(_payload_of(entry))
        if version and version not in versions:
            versions.append(version)
    running = _clean(running_policy_version)
    if running:
        mismatch = any(version != running for version in versions)
    else:
        # Sin política en curso declarada, lo único afirmable es que la historia es mixta.
        mismatch = len(versions) > 1
    unreadable = sum(1 for payload in payloads if _paused_set(payload) is None)
    size = max(0, int(window))
    return AdaptiveStateReading(
        paused_cycles=counts,
        read_ok=read_ok,
        evaluated=len(ordered),
        requested=size,
        policy_versions=tuple(versions),
        policy_version_mismatch=mismatch,
        bounded=tuple(sorted(reasons)),
        insufficient_history=len(ordered) < size,
        unreadable=unreadable,
        collapsed=collapsed,
    )


def adaptive_state_unread(
    reason: str = "", *, window: int = ADAPTIVE_STATE_WINDOW_DEFAULT
) -> AdaptiveStateReading:
    """La lectura de una fuente durable que **no se pudo leer** (``read_ok = False``).

    Existe para que el fallo de lectura sea un valor de primera clase y no un mapa vacío: sin
    ella, "revienta el lector" y "no hay ninguna pausa" llegarían al worker con la misma forma, y
    el contador se reiniciaría —el bug de ``V2.51``— por la puerta de atrás.
    """
    del reason  # el motivo lo registra el llamante; aquí lo que importa es el hecho.
    return AdaptiveStateReading(read_ok=False, requested=max(0, int(window)))
