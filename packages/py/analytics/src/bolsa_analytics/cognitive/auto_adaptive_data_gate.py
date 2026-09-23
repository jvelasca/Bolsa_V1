"""AUTO-13 — Adaptive Data Gate: la salud de la EVIDENCIA, separada de la salud de la estrategia.

Qué cierra: el audit de ``v2.52-beta`` (§21 y §22) señala que el sistema **no** distinguía
"datos Adaptive incompletos" de "estrategia mala". Un hueco de medición (una lectura rota, un
sink caído, una completitud parcial) se declaraba en un log o no se declaraba, pero **no
limitaba** la adaptación: Adaptive seguía repartiendo riesgo con lo que hubiera. Y §21 añade el
caso del journal: «1 fallo → ``DEGRADED``; N fallos consecutivos → ``STALE``; sin journal durante
X ciclos → ``BLOCKED``. Pero: **Risk Engine continúa funcionando**».

Este módulo es un **gate de EVIDENCIA**, no un gate de riesgo: gradúa la salud de lo que
Adaptive sabe de sí mismo. Nunca sustituye al gobernador, al kill switch ni a los gates duros —
solo decide **cuánto puede adaptar** Adaptive con la evidencia que tiene.

Su invariante (el del audit): **ninguna estrategia puede ser castigada por una deuda de los
datos.** Los cuatro estados con sus cuatro efectos declarados:

* ``OK`` → ``ADAPTS``: rotación y reparto completos.
* ``DEGRADED`` → ``LIMITS``: se conserva la protección (las pausas vivas y las pausas NUEVAS por
  salud siguen permitidas) pero **no se estrecha por evidencia fina** (se deja de usar la parte de
  la evidencia que no es de fiar; el reparto cae a su eje histórico).
* ``STALE`` → ``FREEZES``: además, **no se admiten reactivaciones nuevas** (levantar una pausa
  exigiría evidencia que no se pudo leer) y el reparto se congela en el histórico.
* ``BLOCKED`` → ``NO_ADAPT``: no se adapta ese tick (el plan Adaptive se declara **ausente** y el
  motor determinista decide sin él). Es el caso "la evidencia durable lleva demasiados ciclos sin
  publicarse".

El efecto se **deriva** del estado (una tabla, no dos campos que puedan divergir) y el diagrama
del audit (``adapta / limita / no adapta``) es la lectura gruesa de ``FREEZES`` dentro de
"limita": ``DEGRADED`` y ``STALE`` comparten rama y se distinguen en el matiz.

Disciplina de medición, la de la casa: **sin dato no se degrada ni se premia.** Que el llamante
no aporte la completitud o la ventana reciente (``None``) es "no se pidió medir", no "está mal":
se declara (``evidence_not_provided``) y no cambia el estado, que es lo que mantiene
**byte-idéntico** el comportamiento histórico cuando el gate no se aporta. Lo que sí degrada es
un hecho **explícito** (un fallo, una lectura rota, un régimen ausente declarado).

Módulo puro: sin I/O, sin estado y orden-invariante. No lee el journal ni cuenta fallos; recibe
esos hechos ya medidos por quien los tiene (el worker) y los gradúa.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_analytics.cognitive.measurement import is_complete

#: Estado de la salud de la EVIDENCIA Adaptive (eje propio: no es el estado operativo de la
#: estrategia, ni su calidad estadística — los tres ejes NO se mezclan, ver §29 del audit).
DataGateStatus = Literal["OK", "DEGRADED", "STALE", "BLOCKED"]
#: Efecto declarado del estado sobre la adaptación. ``FREEZES`` es la lectura fina de "limita
#: más": conserva lo vigente y no admite reactivaciones nuevas.
DataGateEffect = Literal["ADAPTS", "LIMITS", "FREEZES", "NO_ADAPT"]

DATA_GATE_OK: DataGateStatus = "OK"
DATA_GATE_DEGRADED: DataGateStatus = "DEGRADED"
DATA_GATE_STALE: DataGateStatus = "STALE"
DATA_GATE_BLOCKED: DataGateStatus = "BLOCKED"

DATA_GATE_ADAPTS: DataGateEffect = "ADAPTS"
DATA_GATE_LIMITS: DataGateEffect = "LIMITS"
DATA_GATE_FREEZES: DataGateEffect = "FREEZES"
DATA_GATE_NO_ADAPT: DataGateEffect = "NO_ADAPT"

#: Versión de la POLÍTICA del gate. Cambiar los umbrales (o la tabla estado→efecto) EXIGE subir
#: esta versión: sin ella, dos lecturas iguales podrían venir de reglas distintas sin que se note.
DATA_GATE_POLICY_VERSION = "auto13-v1"

#: Fallos CONSECUTIVOS del sink del journal a partir de los cuales el estado es ``STALE`` (§21:
#: «N fallos consecutivos»). Un único fallo ya deja el estado en ``DEGRADED``.
DATA_GATE_SINK_FAILURES_STALE_DEFAULT = 3
#: Ciclos sin evidencia durable publicada a partir de los cuales el estado es ``BLOCKED`` (§21:
#: «sin journal durante X ciclos»). ``None`` como antigüedad significa "no se pudo medir".
DATA_GATE_JOURNAL_GAP_BLOCKED_DEFAULT = 10
#: Cadencia DECLARADA de un ciclo de evaluación Adaptive, en segundos: el tick del worker
#: (``AUTO_ENGINE_SIM`` corre a ``60s`` por defecto). Es lo que convierte una antigüedad medida
#: (segundos) en ``journal_age_cycles`` sin inventar un contador de proceso — y por eso el ancla
#: **sobrevive a un reinicio**: solo depende del journal durable y de esta regla declarada.
DATA_GATE_EVALUATION_CYCLE_SECONDS_DEFAULT = 60.0

#: Tabla estado → efecto. Es la ÚNICA fuente del efecto: así no puede publicarse un estado con un
#: efecto incoherente (el bug clásico de dos campos que se actualizan por caminos distintos).
_EFFECT_BY_STATUS: Mapping[DataGateStatus, DataGateEffect] = {
    DATA_GATE_OK: DATA_GATE_ADAPTS,
    DATA_GATE_DEGRADED: DATA_GATE_LIMITS,
    DATA_GATE_STALE: DATA_GATE_FREEZES,
    DATA_GATE_BLOCKED: DATA_GATE_NO_ADAPT,
}

#: Motivos declarados (vocabulario propio del gate; viajan en ``notes`` para que la lectura sea
#: auditable sin releer el log del proceso).
DATA_GATE_NOTE_JOURNAL_GAP = "journal_gap"
DATA_GATE_NOTE_SINK_FAILURES = "sink_failures"
DATA_GATE_NOTE_DURABLE_UNREAD = "durable_state_unread"
DATA_GATE_NOTE_UNREADABLE_ROWS = "unreadable_rows"
DATA_GATE_NOTE_POLICY_MISMATCH = "policy_version_mismatch"
DATA_GATE_NOTE_INSUFFICIENT_HISTORY = "insufficient_history"
DATA_GATE_NOTE_MEASUREMENT_INCOMPLETE = "measurement_incomplete"
DATA_GATE_NOTE_RECENT_UNAVAILABLE = "recent_unavailable"
DATA_GATE_NOTE_REGIME_ABSENT = "regime_absent"
DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN = "journal_age_unknown"
DATA_GATE_NOTE_EVIDENCE_NOT_PROVIDED = "evidence_not_provided"


@dataclass(frozen=True, slots=True)
class DataGatePolicy:
    """Umbrales declarados del gate (``§21``), para que la versión selle la regla completa."""

    policy_version: str = DATA_GATE_POLICY_VERSION
    #: Fallos consecutivos del sink a partir de los cuales el estado pasa a ``STALE``.
    sink_failures_stale: int = DATA_GATE_SINK_FAILURES_STALE_DEFAULT
    #: Ciclos sin publicar evidencia durable a partir de los cuales el estado pasa a ``BLOCKED``.
    journal_gap_blocked: int = DATA_GATE_JOURNAL_GAP_BLOCKED_DEFAULT
    #: Segundos que dura un ciclo de evaluación Adaptive (cadencia declarada del tick).
    evaluation_cycle_seconds: float = DATA_GATE_EVALUATION_CYCLE_SECONDS_DEFAULT

    def __post_init__(self) -> None:
        for field_name in ("sink_failures_stale", "journal_gap_blocked"):
            value = int(getattr(self, field_name))
            if value < 1:
                raise ValueError(f"{field_name} must be >= 1")
        # El float se valida aparte: ``int()`` truncaría una cadencia fraccionaria válida.
        if float(self.evaluation_cycle_seconds) <= 0:
            raise ValueError("evaluation_cycle_seconds must be > 0")


@dataclass(frozen=True, slots=True)
class DataGateReading:
    """Lectura del gate: el estado, los HECHOS que lo motivaron y los límites declarados.

    ``effect`` no se guarda: se **deriva** del estado con la tabla declarada, de modo que una
    lectura no pueda afirmar un efecto distinto del que corresponde a su estado.
    """

    status: DataGateStatus = DATA_GATE_OK
    notes: tuple[str, ...] = ()
    # --- hechos medidos (los que el llamante pudo aportar) --------------------------------
    sink_failures: int = 0
    journal_age_cycles: int | None = None
    read_ok: bool = True
    measurement_completeness: str | None = None
    recent_available: bool | None = None
    regime_available: bool | None = None
    unreadable_rows: int = 0
    policy_version_mismatch: bool = False
    insufficient_history: bool = False
    policy_version: str = DATA_GATE_POLICY_VERSION

    @property
    def effect(self) -> DataGateEffect:
        return _EFFECT_BY_STATUS[self.status]

    @property
    def adapts(self) -> bool:
        """True solo si el gate permite adaptar con la evidencia completa."""
        return self.effect == DATA_GATE_ADAPTS

    @property
    def limits_adaptation(self) -> bool:
        """True si la adaptación debe limitarse o congelarse (``DEGRADED``/``STALE``)."""
        return self.effect in (DATA_GATE_LIMITS, DATA_GATE_FREEZES)

    @property
    def blocks_adaptation(self) -> bool:
        """True si este tick no debe adaptar (el plan Adaptive se declara ausente)."""
        return self.effect == DATA_GATE_NO_ADAPT

    def as_dict(self) -> dict[str, Any]:
        """Resumen para el log/evidencia del llamante: estado, efecto, motivos y hechos."""
        return {
            "status": self.status,
            "effect": self.effect,
            "notes": list(self.notes),
            "sinkFailures": self.sink_failures,
            "journalAgeCycles": self.journal_age_cycles,
            "readOk": self.read_ok,
            "measurementCompleteness": self.measurement_completeness,
            "recentAvailable": self.recent_available,
            "regimeAvailable": self.regime_available,
            "unreadableRows": self.unreadable_rows,
            "policyVersionMismatch": self.policy_version_mismatch,
            "insufficientHistory": self.insufficient_history,
            "policyVersion": self.policy_version,
        }


def _reading(status: DataGateStatus, *, notes: list[str], **facts: Any) -> DataGateReading:
    return DataGateReading(status=status, notes=tuple(sorted(notes)), **facts)


def _instant(value: str | None) -> datetime | None:
    """Instante ISO-8601 (``Z`` o ``+hh:mm``) a ``datetime`` con zona; ``None`` si no se lee."""
    text = str(value).strip() if isinstance(value, str) else ""
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def journal_age_cycles(
    *,
    last_published_at: str | None,
    now: str,
    policy: DataGatePolicy | None = None,
) -> int | None:
    """(PURA) ciclos de evaluación transcurridos desde la última evidencia durable publicada.

    Un **ciclo** es un tick de evaluación Adaptive, y su duración es un dato **declarado** de la
    política (``evaluation_cycle_seconds``), no una medida del reloj: así la antigüedad se puede
    juzgar contra el umbral de ``journal_gap_blocked`` (§21, «sin journal durante X ciclos») sin
    mantener ningún contador de proceso. Esa es la mitad que **sobrevive a un reinicio**: solo
    depende de la evidencia durable (``last_published_at``, el ``asOf`` de la fila más nueva) y de
    una regla versionada.

    Devuelve ``None`` —"no se pudo medir", que **no** bloquea, igual que en ``assess_data_gate``—
    cuando falta el instante, cuando no es legible o cuando es **posterior** a ``now`` (un reloj
    que va hacia atrás no puede fabricar una antigüedad). No se supone juventud ni se inventa
    antigüedad: las dos serían una medición que no se hizo.
    """
    resolved = policy or DataGatePolicy()
    published = _instant(last_published_at)
    current = _instant(now)
    if published is None or current is None:
        return None
    elapsed = (current - published).total_seconds()
    if elapsed < 0:
        return None
    cycle = float(resolved.evaluation_cycle_seconds)
    return int(elapsed // cycle)


def assess_data_gate(
    *,
    sink_failures: int = 0,
    journal_age_cycles: int | None = None,
    read_ok: bool = True,
    measurement_completeness: str | None = None,
    recent_available: bool | None = None,
    regime_available: bool | None = None,
    unreadable_rows: int = 0,
    policy_version_mismatch: bool = False,
    insufficient_history: bool = False,
    policy: DataGatePolicy | None = None,
) -> DataGateReading:
    """(PURA) gradúa la salud de la evidencia Adaptive y declara por qué.

    Precedencia (el primer criterio que aplica manda): ``BLOCKED`` > ``STALE`` > ``DEGRADED`` >
    ``OK``. Un estado más grave **absorbe** a los demás, de modo que un ``BLOCKED`` nunca se
    publica con los motivos de un ``DEGRADED`` y el lector no tiene que combinarlos.

    * ``BLOCKED`` — la evidencia durable lleva ``journal_gap_blocked`` ciclos (o más) sin
      publicarse. Es el journal muerto del §21, y el único caso en que no se adapta.
    * ``STALE`` — el sink acumula ``sink_failures_stale`` fallos consecutivos, o la fuente
      durable **no se pudo leer** (``read_ok = False``), o hay filas ilegibles, o la política
      cambió, o la ventana de historia no alcanza. Nada de esto permite afirmar una reactivación.
    * ``DEGRADED`` — al menos un fallo del sink, o una completitud de medición **aportada** que no
      está completa, o una ventana reciente **aportada** como no disponible, o un régimen
      **aportado** como ausente (§20: el hueco de régimen es evidencia incompleta, nunca un
      régimen adverso ni favorable).
    * ``OK`` — nada de lo anterior.

    ``measurement_completeness``/``recent_available``/``regime_available`` en ``None`` significan
    "no se pidió medir" y **no** degradan: solo se declaran. ``journal_age_cycles`` en ``None``
    tampoco bloquea (no se puede juzgar la antigüedad), pero se declara.
    """
    resolved = policy or DataGatePolicy()
    failures = max(0, int(sink_failures or 0))
    unreadable = max(0, int(unreadable_rows or 0))
    age = None if journal_age_cycles is None else max(0, int(journal_age_cycles))
    facts: dict[str, Any] = {
        "sink_failures": failures,
        "journal_age_cycles": age,
        "read_ok": bool(read_ok),
        "measurement_completeness": measurement_completeness,
        "recent_available": recent_available,
        "regime_available": regime_available,
        "unreadable_rows": unreadable,
        "policy_version_mismatch": bool(policy_version_mismatch),
        "insufficient_history": bool(insufficient_history),
        "policy_version": resolved.policy_version,
    }

    if age is not None and age >= int(resolved.journal_gap_blocked):
        return _reading(DATA_GATE_BLOCKED, notes=[DATA_GATE_NOTE_JOURNAL_GAP], **facts)

    stale_notes: list[str] = []
    if failures >= int(resolved.sink_failures_stale):
        stale_notes.append(DATA_GATE_NOTE_SINK_FAILURES)
    if not read_ok:
        stale_notes.append(DATA_GATE_NOTE_DURABLE_UNREAD)
    if unreadable > 0:
        stale_notes.append(DATA_GATE_NOTE_UNREADABLE_ROWS)
    if policy_version_mismatch:
        stale_notes.append(DATA_GATE_NOTE_POLICY_MISMATCH)
    if insufficient_history:
        stale_notes.append(DATA_GATE_NOTE_INSUFFICIENT_HISTORY)
    if stale_notes:
        if age is None:
            stale_notes.append(DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN)
        return _reading(DATA_GATE_STALE, notes=stale_notes, **facts)

    degraded_notes: list[str] = []
    if failures > 0:
        degraded_notes.append(DATA_GATE_NOTE_SINK_FAILURES)
    if measurement_completeness is not None and not is_complete(measurement_completeness):
        degraded_notes.append(DATA_GATE_NOTE_MEASUREMENT_INCOMPLETE)
    if recent_available is False:
        degraded_notes.append(DATA_GATE_NOTE_RECENT_UNAVAILABLE)
    if regime_available is False:
        degraded_notes.append(DATA_GATE_NOTE_REGIME_ABSENT)
    if degraded_notes:
        return _reading(DATA_GATE_DEGRADED, notes=degraded_notes, **facts)

    notes: list[str] = []
    if measurement_completeness is None and recent_available is None and regime_available is None:
        notes.append(DATA_GATE_NOTE_EVIDENCE_NOT_PROVIDED)
    if age is None:
        notes.append(DATA_GATE_NOTE_JOURNAL_AGE_UNKNOWN)
    return _reading(DATA_GATE_OK, notes=notes, **facts)


__all__ = [
    "DATA_GATE_ADAPTS",
    "DATA_GATE_BLOCKED",
    "DATA_GATE_DEGRADED",
    "DATA_GATE_EVALUATION_CYCLE_SECONDS_DEFAULT",
    "DATA_GATE_FREEZES",
    "DATA_GATE_JOURNAL_GAP_BLOCKED_DEFAULT",
    "DATA_GATE_LIMITS",
    "DATA_GATE_NO_ADAPT",
    "DATA_GATE_OK",
    "DATA_GATE_POLICY_VERSION",
    "DATA_GATE_SINK_FAILURES_STALE_DEFAULT",
    "DATA_GATE_STALE",
    "DataGateEffect",
    "DataGatePolicy",
    "DataGateReading",
    "DataGateStatus",
    "assess_data_gate",
    "journal_age_cycles",
]
