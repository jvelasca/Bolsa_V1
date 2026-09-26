"""AUTO-MATERIAL-1/2 — PAPER MATERIAL READINESS: diagnóstico del material antes del RUN.

Qué resuelve: ``v2.72`` midió el primer material PAPER real y lo declaró **BLOQUEADO** con el
propio instrumento (**761** fills durables, **0** con ``cycle_id``, **751 ``buy`` / 10 ``sell``**
y **0** filas en ``portfolio_reservations``). El instrumento hizo lo correcto (``exit 2``, sin
publicar un bundle vacío), pero el operador solo descubría el motivo **después** de intentar la
corrida. Este módulo es el **pre-flight**: mide el material y declara, ANTES de ``auto_evidence_run``
(``AUTO-22``), si el material está **correctamente formado** y, solo después, si hay **evidencia
estadística** bastante.

**Dos niveles (V2.74 · AUTO-MATERIAL-2).** ``READY`` no es una sola cosa: son dos, y confundirlas
fue el hueco que esta fase cierra.

* ``PRODUCER_READY`` — el material tiene **estructura**: linaje de ciclo, reservas con denominador
  positivo, ciclos cerrados, salidas con ``cycle_id`` y al menos un R **medible**. Dice "el camino
  V2 produce material correcto", no "hay suficiente muestra".
* ``EVIDENCE_READY`` — además alcanza ``min_cycles_per_strategy`` ciclos medibles por estrategia.
  Dice "ya se puede correr el instrumento estadístico".

Un material estructuralmente completo pero por debajo del mínimo es ``PRODUCER_READY`` y **no**
``EVIDENCE_READY``: nunca se confunde "bien formado" con "suficiente".

Tres reglas duras, declaradas en vez de asumidas:

* **Es un LECTOR, no un productor.** No repara material: no infiere ``cycle_id``, no inventa
  ``reserved_risk``, no sustituye el denominador por capital/equity/nominal y **no** convierte N
  fills en N operaciones. Un material incompleto se **declara**; jamás se rellena para que el gate
  pase.
* **Mide el MISMO material que el instrumento.** Reutiliza ``adaptive_instrument_cycles``
  (``cycles_from_fills`` + ``cycle_risk_from_reservations`` + fricción aplicada) para contar
  ciclos cerrados y R medible: no hay un segundo FIFO ni una segunda aritmética de R que pueda
  divergir del informe.
* **Fail-closed.** El veredicto es ``EVIDENCE_READY`` solo si hay al menos una estrategia con
  ``min_cycles_per_strategy`` ciclos cerrados con denominador positivo; ``PRODUCER_READY`` solo si
  la estructura está completa. Sin material, el veredicto correcto es ``BLOCKED`` con sus motivos
  nombrados, no un ``READY`` optimista.

Read-only y puro: no escribe nada ni consulta nada. El I/O (PostgreSQL) lo aporta quien llama.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from bolsa_application.auto_self_evaluation_feed import adaptive_instrument_cycles

__all__ = [
    "BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES",
    "BLOCKER_NO_CLOSED_CYCLES",
    "BLOCKER_NO_CYCLE_LINEAGE",
    "BLOCKER_NO_EXIT_ORDERS",
    "BLOCKER_NO_MEASURABLE_RISK",
    "BLOCKER_NO_RESERVATIONS",
    "BLOCKER_PRODUCER_PATH_NOT_EXERCISED",
    "DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY",
    "MATERIAL_READINESS_METHOD",
    "READINESS_BLOCKED",
    "READINESS_EVIDENCE_READY",
    "READINESS_PRODUCER_READY",
    "READINESS_READY",
    "PaperMaterialReadiness",
    "build_paper_material_readiness",
]

#: Sello del diagnóstico. Si la lectura cambia (nuevo bloque o nuevo criterio), el sello lo
#: declara: un consumidor no debe leer dos diagnósticos distintos como si fueran el mismo.
#: ``v2`` introduce el veredicto de DOS niveles (``PRODUCER_READY`` / ``EVIDENCE_READY``) y los
#: motivos de productor (``no exit orders`` / ``no measurable risk``).
MATERIAL_READINESS_METHOD = "paper_material_readiness_v2"

#: Verdadero solo si el material no tiene ni la estructura del productor.
READINESS_BLOCKED = "BLOCKED"
#: La estructura está completa (linaje, reservas, cierres, salidas, R medible) — "bien formado".
READINESS_PRODUCER_READY = "PRODUCER_READY"
#: La estructura está completa Y alcanza el mínimo de ciclos medibles por estrategia.
READINESS_EVIDENCE_READY = "EVIDENCE_READY"
#: Alias de compatibilidad: el nivel COMPLETO es el que la versión anterior llamaba ``READY``.
READINESS_READY = READINESS_EVIDENCE_READY

#: No hay ni un fill con ``cycle_id``: sin identidad de ciclo no se puede agrupar entrada/salida.
BLOCKER_NO_CYCLE_LINEAGE = "no cycle lineage"
#: No hay filas de reserva: sin ``reserved_risk`` no hay denominador de R aunque haya cierres.
BLOCKER_NO_RESERVATIONS = "no reservations"
#: Hay fills pero ninguna operación cerrada (ida y vuelta completa) que medir.
BLOCKER_NO_CLOSED_CYCLES = "no closed cycles"
#: Hay cierres, pero ningún denominador de riesgo positivo: el R no es reconstruible.
BLOCKER_NO_MEASURABLE_RISK = "no measurable risk"
#: Se midieron las salidas y ninguna lleva ``cycle_id``: falta la pata de salida con linaje.
BLOCKER_NO_EXIT_ORDERS = "no exit orders"
#: La estructura está completa pero ningún ciclo alcanza el mínimo estadístico declarado.
BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES = "insufficient measurable cycles per strategy"
#: Hecho observable, no una causa: hay fills y a la vez ni linaje de ciclo ni reservas. Es la
#: huella de que el camino que produce ambos (el pipeline AUTO 2.0) no se ejercitó, y se declara
#: para que no se confunda con un defecto del instrumento.
BLOCKER_PRODUCER_PATH_NOT_EXERCISED = "producer path not exercised"

#: Mínimo OPERATIVO de ciclos medidos por estrategia para que el walk-forward produzca lectura
#: (``folds=3``, ``min_is=8``, ``min_oos=4`` ⇒ ``≥32`` ciclos medidos, ver el protocolo del primer
#: RUN PAPER real). Es un umbral **declarado**, parametrizable: no se baja para forzar una corrida.
DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY = 32


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _positive(value: Any) -> bool:
    """¿El valor es un número finito estrictamente positivo? (nunca un cero de relleno)."""
    if value is None or isinstance(value, bool):
        return False
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return False
    return number.is_finite() and number > 0


def _field(row: Any, *names: str) -> Any:
    """Campo ``name`` de un ``Mapping`` o de un objeto (mismo contrato que el manifest)."""
    if isinstance(row, Mapping):
        for name in names:
            if name in row:
                return row[name]
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _cycle_of(row: Any) -> str:
    return _clean(_field(row, "cycleId", "cycle_id"))


def _version_of(row: Any) -> str:
    return _clean(_field(row, "strategyVersion", "strategy_version"))


def _has_measured_risk(row: Any) -> bool:
    """¿La fila del instrumento declara un denominador de R medido (positivo)?"""
    return _positive(_field(row, "riskAmount", "risk_amount"))


def _is_buy(row: Any) -> bool:
    return _clean(_field(row, "side")).lower() == "buy"


def _is_sell(row: Any) -> bool:
    return _clean(_field(row, "side")).lower() == "sell"


def _is_live(row: Any) -> bool:
    live = getattr(row, "is_live", None)
    if live is not None:
        return bool(live)
    status = _clean(_field(row, "status")).upper()
    remaining = _field(row, "remaining_qty", "remainingQty")
    return status == "OPEN" and _positive(remaining)


def _exit_order_cycle(row: Any) -> str:
    return _clean(_field(row, "cycle_id", "cycleId"))


@dataclass(frozen=True, slots=True)
class PaperMaterialReadiness:
    """Veredicto del material PAPER: nivel alcanzado, motivos y linaje declarados.

    ``blockers`` enumera todo lo que impide ``EVIDENCE_READY`` (estructura + hueco de mínimo);
    ``producer_blockers`` solo lo que impide ``PRODUCER_READY`` (estructura). Un material
    bien formado pero corto de muestra tiene ``producer_blockers == ()`` y ``blockers`` con
    ``insufficient measurable cycles per strategy``.
    """

    verdict: str
    blockers: tuple[str, ...]
    facts: Mapping[str, Any]
    lineage: Mapping[str, Any]
    method: str = MATERIAL_READINESS_METHOD
    producer_blockers: tuple[str, ...] = field(default=())

    @property
    def producer_ready(self) -> bool:
        """La estructura del productor está completa (aunque falte muestra)."""
        return self.verdict in (READINESS_PRODUCER_READY, READINESS_EVIDENCE_READY)

    @property
    def evidence_ready(self) -> bool:
        """Hay estructura Y el mínimo de ciclos medibles por estrategia."""
        return self.verdict == READINESS_EVIDENCE_READY

    @property
    def ready(self) -> bool:
        """Nivel completo (``EVIDENCE_READY``): habilita el RUN estadístico."""
        return self.evidence_ready

    def achieved(self, level: str) -> bool:
        """¿Se alcanzó el nivel pedido? (``producer`` o ``evidence``; cualquier otra ⇒ evidence)."""
        if str(level).strip().lower() == "producer":
            return self.producer_ready
        return self.evidence_ready

    def as_dict(self) -> dict[str, Any]:
        """Payload máquina-legible (misma forma para el CLI y una futura pantalla)."""
        return {
            "schema": self.method,
            "verdict": self.verdict,
            "ready": self.ready,
            "producerReady": self.producer_ready,
            "evidenceReady": self.evidence_ready,
            "blockers": list(self.blockers),
            "producerBlockers": list(self.producer_blockers),
            "facts": dict(self.facts),
            "lineage": dict(self.lineage),
        }


def build_paper_material_readiness(
    *,
    account_id: str | None,
    requested_versions: Sequence[str],
    fills: Iterable[Any],
    reservations: Iterable[Any],
    exit_orders: Iterable[Any] | None = None,
    regime_by_cycle: Mapping[str, str] | None = None,
    min_cycles_per_strategy: int = DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY,
    fills_by_version: Mapping[str | None, int] | None = None,
    reservations_read_complete: bool = True,
    database_totals: Mapping[str, Any] | None = None,
) -> PaperMaterialReadiness:
    """(PURA) diagnostica si el material PAPER puede producir evidencia con R medible.

    Mide, sobre el MISMO material que el instrumento (``adaptive_instrument_cycles``):

    * **Ciclos cerrados** — round-trips que ``cycles_from_fills`` declaró terminados (cantidad
      emparejada y sin posición abierta).
    * **R medible** — ciclos cerrados cuyo denominador (``riskAmount``) es positivo, es decir
      reconstruible desde las reservas del ciclo (``reserved_risk``).

    ``exit_orders`` es opcional: cuando se aporta (la lectura de ``auto_exit_orders``), el linaje
    de ciclo se declara también por esa vía y —al ser un bloque de PRODUCTOR— su ausencia total
    bloquea. ``None`` significa **no medido** (no un cero) y **no** bloquea. ``regime_by_cycle`` se
    pasa tal cual a ``cycle_risk_from_reservations``: un ciclo sin régimen queda declarado por esa
    capa, nunca se inventa.

    ``database_totals`` es opcional y solo INFORMATIVO: declara la población total de la tabla
    (todas las cuentas/versiones) para que no se confunda con el universo del instrumento. No entra
    en ningún veredicto ni se inventa si no se aporta.
    """
    fill_rows = list(fills)
    reservation_rows = list(reservations)
    exit_rows = None if exit_orders is None else list(exit_orders)

    cycle_ids: list[str] = []
    seen_cycles: set[str] = set()
    fills_with_cycle = 0
    buys = sells = 0
    fills_by_version_counts: dict[str, int] = {}
    for fill in fill_rows:
        if _is_buy(fill):
            buys += 1
        elif _is_sell(fill):
            sells += 1
        cycle_id = _clean(_field(fill, "cycle_id", "cycleId"))
        if cycle_id:
            fills_with_cycle += 1
            if cycle_id not in seen_cycles:
                seen_cycles.add(cycle_id)
                cycle_ids.append(cycle_id)
        version = _clean(_field(fill, "strategy_version_id", "strategyVersion"))
        if version:
            fills_by_version_counts[version] = fills_by_version_counts.get(version, 0) + 1

    # Mismo material que el instrumento: ciclos + riesgo de reserva + fricción aplicada.
    from bolsa_application.cycle_risk import cycle_risk_from_reservations

    cycle_risk = cycle_risk_from_reservations(
        cycle_ids,
        reservation_rows,
        regime_by_cycle=dict(regime_by_cycle or {}),
        regime_source_durable=True,
    )
    cycles = adaptive_instrument_cycles(fill_rows, cycle_risk)

    closed_cycles = len(cycles)
    measurable = [row for row in cycles if _has_measured_risk(row)]
    measurable_with_identity = sum(1 for row in measurable if _cycle_of(row))

    per_version: dict[str, dict[str, int]] = {}
    versions_without_closed: list[str] = []
    for row in cycles:
        version = _version_of(row)
        if not version:
            continue
        cell = per_version.setdefault(version, {"closedCycles": 0, "measurableCycles": 0})
        cell["closedCycles"] += 1
        if _has_measured_risk(row):
            cell["measurableCycles"] += 1

    requested = [str(v) for v in requested_versions if _clean(v)]
    for version in requested:
        if version not in per_version:
            versions_without_closed.append(version)

    max_measurable = max(
        (cell["measurableCycles"] for cell in per_version.values()), default=0
    )
    max_fills_per_version = max(fills_by_version_counts.values(), default=0)
    versions_meeting = sorted(
        version
        for version, cell in per_version.items()
        if cell["measurableCycles"] >= max(1, int(min_cycles_per_strategy))
    )

    reservations_with_cycle = sum(1 for row in reservation_rows if _cycle_of(row))
    live = sum(1 for row in reservation_rows if _is_live(row))
    exit_orders_with_cycle = (
        None if exit_rows is None else sum(1 for row in exit_rows if _exit_order_cycle(row))
    )

    # ── Estructura del PRODUCTOR (fail-closed) ────────────────────────────────────────────
    # Estos motivos impiden ``PRODUCER_READY``: el material no está "bien formado".
    producer_blockers: list[str] = []
    if fill_rows and fills_with_cycle == 0:
        producer_blockers.append(BLOCKER_NO_CYCLE_LINEAGE)
    if reservations_read_complete and not reservation_rows and fill_rows:
        producer_blockers.append(BLOCKER_NO_RESERVATIONS)
    if closed_cycles == 0:
        producer_blockers.append(BLOCKER_NO_CLOSED_CYCLES)
    if closed_cycles > 0 and not measurable:
        producer_blockers.append(BLOCKER_NO_MEASURABLE_RISK)
    if exit_rows is not None and fill_rows and not exit_orders_with_cycle:
        producer_blockers.append(BLOCKER_NO_EXIT_ORDERS)
    if fill_rows and fills_with_cycle == 0 and not reservations_with_cycle and not reservation_rows:
        producer_blockers.append(BLOCKER_PRODUCER_PATH_NOT_EXERCISED)

    # ── Hueco de EVIDENCIA (mínimo estadístico) ───────────────────────────────────────────
    evidence_gap = max_measurable < max(1, int(min_cycles_per_strategy))
    blockers = list(producer_blockers)
    if evidence_gap:
        blockers.append(BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES)

    if producer_blockers:
        verdict = READINESS_BLOCKED
        level = "blocked"
    elif evidence_gap:
        verdict = READINESS_PRODUCER_READY
        level = "producer"
    else:
        verdict = READINESS_EVIDENCE_READY
        level = "evidence"

    facts: dict[str, Any] = {
        "account": _clean(account_id) or None,
        "requestedStrategyVersions": requested,
        "minCyclesPerStrategy": max(1, int(min_cycles_per_strategy)),
        "executionReality": "VIRTUAL — NO REAL MONEY",
        "readinessLevel": level,
        "evidenceGap": bool(evidence_gap),
        "producerBlockers": list(producer_blockers),
        "durableFills": len(fill_rows),
        "fillsWithCycle": fills_with_cycle,
        "fillsWithoutCycle": len(fill_rows) - fills_with_cycle,
        "buys": buys,
        "sells": sells,
        "reservations": len(reservation_rows),
        "reservationsWithCycle": reservations_with_cycle,
        "reservationsLive": live,
        "closedCycles": closed_cycles,
        "measurableCycles": len(measurable),
        "measurableCyclesWithIdentity": measurable_with_identity,
        "maxFillsPerVersion": max_fills_per_version,
        "maxMeasurableCyclesPerVersion": max_measurable,
        "versionsMeetingMinimum": versions_meeting,
        "versionsWithoutClosedCycles": versions_without_closed,
        "perVersion": {version: per_version[version] for version in sorted(per_version)},
        "reservationsReadComplete": bool(reservations_read_complete),
        "materialNote": (
            "material PAPER REAL sobre cuenta PAPER VIRTUAL (dinero VIRTUAL): el gate solo mide "
            "linaje, cierres y denominador de R; no repara ni infiere material"
        ),
    }
    if fills_by_version is not None:
        facts["fillsTotalForAccount"] = sum(int(v) for v in fills_by_version.values())
    # Población TOTAL (informativa, nunca un veredicto): evita confundir la tabla entera con el
    # universo del instrumento (761 vs 4 en la medición de v2.72/v2.73).
    if database_totals is not None:
        facts["databaseTotals"] = dict(database_totals)

    lineage: dict[str, Any] = {
        "cycle": {
            "fillsWithCycle": fills_with_cycle,
            "fillsWithoutCycle": len(fill_rows) - fills_with_cycle,
            "exitOrdersWithCycle": exit_orders_with_cycle,
            "exitOrders": None if exit_rows is None else len(exit_rows),
        },
        "reservation": {
            "rows": len(reservation_rows),
            "withCycle": reservations_with_cycle,
            "live": live,
            "released": len(reservation_rows) - live,
        },
        "closure": {
            "closedCycles": closed_cycles,
            "closedCyclesWithIdentity": sum(1 for row in cycles if _cycle_of(row)),
            "closedCyclesWithRisk": len(measurable),
            "cyclesWithoutIdentity": sum(1 for row in cycles if not _cycle_of(row)),
        },
        "readiness": {
            "level": level,
            "producerReady": verdict in (READINESS_PRODUCER_READY, READINESS_EVIDENCE_READY),
            "evidenceReady": verdict == READINESS_EVIDENCE_READY,
        },
    }

    return PaperMaterialReadiness(
        verdict=verdict,
        blockers=tuple(blockers),
        facts=facts,
        lineage=lineage,
        producer_blockers=tuple(producer_blockers),
    )
