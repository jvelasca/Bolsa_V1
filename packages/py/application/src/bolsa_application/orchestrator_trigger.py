"""R2 — disparador gobernado del embudo AUTO (``POST /api/auto/orchestrator/run``).

La auditoría LAB 2026-11-16 encontró que el embudo completo (ESTUDIO → LAB → TOP3 →
COACH → FINALISTA) solo era alcanzable de noche y con ``AUTO_ORCHESTRATOR_ENABLED=1``.
Este servicio lo hace alcanzable **sin** abrir una puerta trasera:

* **``dryRun`` por defecto ``True``**, y el default lo aplica el servidor: un ``POST`` sin
  cuerpo no escribe nada del lifecycle (el store se envuelve en ``DryRunLifecycleStore``,
  que suprime las escrituras y las declara en el recibo).
* **Nunca escribe ACTIVE**: ``max_phase`` se fuerza a ``FINALISTA`` y un
  ``toPhase='active'`` es rechazado (400). El salto a ACTIVE sigue pasando por
  ``decide_promotion`` en el worker, jamás por esta ruta.
* **Idempotencia durable** por ``(instrumentId, accountId, snapshot, cycle, dryRun)``: el
  ``run_id`` es determinista y el recibo se busca en el ledger de auditoría, así que
  repetir devuelve el MISMO recibo con ``replayed=True`` en lugar de re-ejecutar.
* **Ámbito ESTUDIO**: un instrumento fuera del universo canónico (o un universo no
  resuelto) es un conflicto de ámbito, no un ciclo silencioso.
* **Fail-closed**: si el ciclo no llega a FINALISTA, el recibo es ``INCOMPLETE`` con sus
  motivos y los gates evaluados; nunca un éxito inventado. Si el ciclo revienta, también.
* **Auditoría**: cada ejecución (dry o real) deja un evento ``auto.orchestrator.run`` con
  actor, ``dryRun``, fase alcanzada, gates y resultado. Ese evento ES el recibo durable.

Lo que esta ruta NO hace (por contrato): aceptar evidencia del cliente, saltar gates,
sustituir el universo ESTUDIO, escribir el TOP ni promocionar.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from bolsa_application.auto_orchestrator import PHASE_FINALISTA
from bolsa_application.orchestrator_cycle import build_cycle_run_id, run_cycle_once

logger = logging.getLogger(__name__)

__all__ = [
    "TRIGGER_AUDIT_EVENT_TYPE",
    "TRIGGER_MAX_PHASE",
    "DryRunLifecycleStore",
    "InMemoryTriggerLedger",
    "OrchestratorTrigger",
    "TriggerConflictError",
    "TriggerLedger",
    "TriggerReceipt",
    "TriggerRequest",
    "TriggerScopeError",
    "TriggerRequestError",
    "trigger_idempotency_key",
    "trigger_run_id",
]

#: Tipo del evento de plataforma que sirve de recibo durable (sin migración).
TRIGGER_AUDIT_EVENT_TYPE = "auto.orchestrator.run"
#: Techo de fase: el disparador JAMÁS escribe ACTIVE por esta vía.
TRIGGER_MAX_PHASE = PHASE_FINALISTA
#: Estados del recibo. ``COMPLETED`` solo si se alcanzó la fase declarada.
STATUS_COMPLETED = "COMPLETED"
STATUS_INCOMPLETE = "INCOMPLETE"

#: Escrituras del lifecycle que un ``dryRun`` suprime (declaradas, no silenciadas).
_WRITE_METHODS = frozenset(
    {
        "save_candidate",
        "save_evaluation",
        "save_finalist",
        "save_promotion",
        "save_active",
        "save_health",
        "save_coach_assessment",
        "save_shadow_result",
    }
)


class TriggerRequestError(Exception):
    """Petición inválida (400): fase pedida fuera del contrato o cuerpo incompleto."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class TriggerScopeError(Exception):
    """Conflicto de ámbito (409): fuera de ESTUDIO o universo no resuelto."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class TriggerConflictError(TriggerScopeError):
    """Conflicto (409): cuenta cerrada, ejecución en vuelo o slot ocupado."""


# ── Ledger (recibo durable + auditoría) ─────────────────────────────────────────


class TriggerLedger(Protocol):
    """Puerto del recibo durable. La implementación real usa ``platform_events``."""

    async def find(self, *, run_id: str) -> dict[str, Any] | None: ...

    async def append(self, *, run_id: str, payload: dict[str, Any]) -> str: ...


class InMemoryTriggerLedger:
    """Ledger en proceso (tests y composición mínima)."""

    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}

    async def find(self, *, run_id: str) -> dict[str, Any] | None:
        stored = self.entries.get(run_id)
        return dict(stored) if stored is not None else None

    async def append(self, *, run_id: str, payload: dict[str, Any]) -> str:
        self.entries[run_id] = dict(payload)
        return f"mem-{run_id}"


# ── Store de solo lectura del dry run ───────────────────────────────────────────


class DryRunLifecycleStore:
    """Envoltorio de SOLO LECTURA del store del lifecycle (``dryRun``).

    Delega todo al store real y suprime las escrituras conocidas, registrándolas en
    ``writes`` para que el recibo declare qué se habría escrito. No inventa lecturas:
    ``get_active``/``list_health``/``list_candidates`` siguen golpeando la BD real.
    """

    def __init__(self, inner: Any) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "writes", [])

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name not in _WRITE_METHODS:
            return attribute

        async def _suppressed(*args: Any, **kwargs: Any) -> None:
            # No puede fallar: un dry run que «finge» una escritura y revienta sería
            # indistinguible de uno real.
            self.writes.append(name)
            return None

        return _suppressed


# ── Clave/identidad determinista ───────────────────────────────────────────────


def _clean(value: str | None) -> str:
    return (value or "").strip()


def trigger_idempotency_key(
    *,
    instrument_id: str,
    account_id: str | None,
    snapshot: str | None,
    cycle: str,
    dry_run: bool,
) -> str:
    """Clave canónica de idempotencia.

    Incluye ``dryRun`` a propósito: un recibo *dry* no puede bloquear la ejecución real
    del mismo ciclo (son resultados distintos), pero repetir el MISMO cuerpo sí devuelve
    el mismo recibo. La desviación se documenta en ADR-053.
    """
    return "|".join(
        (
            _clean(instrument_id).upper(),
            _clean(account_id) or "-",
            _clean(snapshot) or "-",
            _clean(cycle),
            "dry" if dry_run else "wet",
        )
    )


def trigger_run_id(key: str) -> str:
    """``run_id`` determinista y estable para una clave de idempotencia."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"trigger:{digest}"


# ── Petición / recibo ──────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class TriggerRequest:
    """Petición ya validada por la ruta (sin evidencia del cliente)."""

    instrument_id: str
    account_id: str | None = None
    dry_run: bool = True
    to_phase: str = TRIGGER_MAX_PHASE
    data_snapshot_id: str | None = None
    #: Día UTC del ciclo; el servidor lo fija si llega vacío (no lo inventa el cliente).
    cycle: str = ""
    actor: str = "unknown"
    correlation_id: str | None = None


@dataclass(slots=True)
class TriggerReceipt:
    """Recibo verificable de una ejecución del embudo."""

    run_id: str
    instrument_id: str
    account_id: str | None
    dry_run: bool
    status: str
    phase_reached: str | None
    cycle: str
    idempotency_key: str
    gates: tuple[dict[str, Any], ...] = ()
    candidates: int = 0
    evaluated: int = 0
    promoted: bool = False
    active_version_id: str | None = None
    reasons: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    replayed: bool = False
    audit_event_id: str | None = None
    computed_at: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        """Payload JSON-safe (lo que se persiste como auditoría y se devuelve)."""
        return {
            "runId": self.run_id,
            "instrumentId": self.instrument_id,
            "accountId": self.account_id,
            "dryRun": self.dry_run,
            "status": self.status,
            "phaseReached": self.phase_reached,
            "cycle": self.cycle,
            "idempotencyKey": self.idempotency_key,
            "gates": [dict(gate) for gate in self.gates],
            "candidates": self.candidates,
            "evaluated": self.evaluated,
            "promoted": self.promoted,
            "activeVersionId": self.active_version_id,
            "reasons": list(self.reasons),
            "writes": list(self.writes),
            "auditEventId": self.audit_event_id,
            "computedAt": self.computed_at,
            "notes": list(self.notes),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, replayed: bool = True) -> TriggerReceipt:
        return cls(
            run_id=str(payload.get("runId") or ""),
            instrument_id=str(payload.get("instrumentId") or ""),
            account_id=payload.get("accountId"),
            dry_run=bool(payload.get("dryRun", True)),
            status=str(payload.get("status") or STATUS_INCOMPLETE),
            phase_reached=payload.get("phaseReached"),
            cycle=str(payload.get("cycle") or ""),
            idempotency_key=str(payload.get("idempotencyKey") or ""),
            gates=tuple(dict(gate) for gate in (payload.get("gates") or ())),
            candidates=int(payload.get("candidates") or 0),
            evaluated=int(payload.get("evaluated") or 0),
            promoted=bool(payload.get("promoted", False)),
            active_version_id=payload.get("activeVersionId"),
            reasons=tuple(str(reason) for reason in (payload.get("reasons") or ())),
            writes=tuple(str(name) for name in (payload.get("writes") or ())),
            replayed=replayed,
            audit_event_id=payload.get("auditEventId"),
            computed_at=str(payload.get("computedAt") or ""),
            notes=tuple(str(note) for note in (payload.get("notes") or ())),
        )


def _gate_payload(gate: Any) -> dict[str, Any]:
    status = getattr(gate, "status", None)
    return {
        "gate": str(getattr(gate, "gate", "") or ""),
        "status": getattr(status, "value", status) if status is not None else None,
        "detail": getattr(gate, "detail", None),
    }


# ── Servicio ───────────────────────────────────────────────────────────────────


class OrchestratorTrigger:
    """Ejecuta el embudo con techo FINALISTA, idempotencia y auditoría."""

    def __init__(
        self,
        *,
        orchestrator: Any,
        ledger: TriggerLedger,
        clock: Any = None,
        run_cycle: Any = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._ledger = ledger
        self._clock = clock or (lambda: datetime.now(UTC))
        # Inyectable para tests: el default es la ÚNICA implementación del embudo.
        self._run_cycle = run_cycle or run_cycle_once

    async def universe_ids(self) -> tuple[str, ...] | None:
        """Universo ESTUDIO resuelto (``None`` si no hay universo disponible)."""
        resolver = getattr(self._orchestrator, "resolve_universe", None)
        if resolver is None:
            return None
        resolution = await resolver()
        if resolution is None:
            # El orquestador no tiene resolver cableado: no hay universo canónico.
            return None
        status = str(getattr(resolution, "status", "") or "")
        if status != "ok":
            return ()
        return tuple(
            str(i) for i in (getattr(resolution, "instrument_ids", None) or ()) if i
        )

    async def execute(self, request: TriggerRequest) -> TriggerReceipt:
        """Ejecuta (o reproduce) una pasada del embudo y devuelve su recibo."""
        if request.to_phase != TRIGGER_MAX_PHASE:
            raise TriggerRequestError(
                "phase_not_allowed",
                "toPhase fuera del contrato: el disparador gobernado llega como máximo a "
                f"{TRIGGER_MAX_PHASE!r} (ACTIVE solo por decide_promotion).",
            )
        instrument_id = _clean(request.instrument_id)
        if not instrument_id:
            raise TriggerRequestError("instrument_required", "instrumentId es obligatorio.")

        now = self._clock()
        cycle = _clean(request.cycle) or now.date().isoformat()
        key = trigger_idempotency_key(
            instrument_id=instrument_id,
            account_id=request.account_id,
            snapshot=request.data_snapshot_id,
            cycle=cycle,
            dry_run=request.dry_run,
        )
        run_id = trigger_run_id(key)

        # Idempotencia durable ANTES de cualquier efecto: repetir no duplica.
        stored = await self._ledger.find(run_id=run_id)
        if stored is not None:
            logger.info(
                "orchestrator trigger replay instrument=%s run_id=%s dry_run=%s",
                instrument_id,
                run_id,
                request.dry_run,
            )
            return TriggerReceipt.from_payload(stored, replayed=True)

        scope_ids = await self.universe_ids()
        if scope_ids is None:
            raise TriggerScopeError(
                "estudio_universe_unavailable",
                "El orquestador no tiene universo ESTUDIO cableado: no se ejecuta el "
                "embudo fuera del universo canónico.",
            )
        if instrument_id not in scope_ids:
            raise TriggerScopeError(
                "instrument_out_of_estudio_scope",
                f"{instrument_id} no pertenece al universo ESTUDIO vigente "
                f"({len(scope_ids)} instrumentos): el disparador no sustituye el universo.",
            )

        reason: str | None = None
        outcome: Any = None
        dry_store: DryRunLifecycleStore | None = None
        deps = getattr(self._orchestrator, "deps", None)
        if request.dry_run and deps is not None:
            dry_store = DryRunLifecycleStore(deps.store)
            deps.store = dry_store

        try:
            outcome = await self._run_cycle(
                self._orchestrator,
                instrument_id=instrument_id,
                cycle_id=cycle,
                run_id=build_cycle_run_id(instrument_id, cycle),
                max_phase=TRIGGER_MAX_PHASE,
                # La vigilancia escribe salud sobre la ACTIVA: fuera del techo FINALISTA.
                watch=False,
            )
        except Exception as exc:  # noqa: BLE001 — fail-closed: recibo INCOMPLETE.
            logger.exception("orchestrator trigger cycle failed instrument=%s", instrument_id)
            reason = f"ciclo_fallo:{type(exc).__name__}"
        finally:
            if dry_store is not None and deps is not None:
                # El store real se restaura siempre, incluso si el ciclo revienta.
                deps.store = dry_store._inner  # noqa: SLF001 — restauración explícita.

        result = getattr(outcome, "result", None)
        gates = tuple(_gate_payload(gate) for gate in (getattr(result, "gates", ()) or ()))
        phase = getattr(result, "phase", None)
        promoted = bool(getattr(result, "promoted", False))
        active_version_id = getattr(result, "active_version_id", None)
        notes: list[str] = []
        if promoted or active_version_id:
            # Defensa en profundidad: con el techo FINALISTA esto es imposible.
            notes.append("contrato_violado: el ciclo escribió ACTIVE pese al techo FINALISTA")
            reason = reason or "promocion_no_permitida"
        if result is not None and phase != TRIGGER_MAX_PHASE:
            reason = reason or f"fase_no_alcanzada:{phase or 'desconocida'}"
        status = STATUS_COMPLETED if (result is not None and reason is None) else STATUS_INCOMPLETE

        receipt = TriggerReceipt(
            run_id=run_id,
            instrument_id=instrument_id,
            account_id=request.account_id,
            dry_run=request.dry_run,
            status=status,
            phase_reached=phase,
            cycle=cycle,
            idempotency_key=key,
            gates=gates,
            candidates=int(getattr(result, "candidates", 0) or 0),
            evaluated=int(getattr(result, "evaluated", 0) or 0),
            promoted=promoted,
            active_version_id=active_version_id,
            reasons=tuple(str(r) for r in (getattr(result, "reasons", ()) or ())),
            writes=tuple(dry_store.writes) if dry_store is not None else (),
            computed_at=now.isoformat(),
            notes=tuple(notes),
        )
        if reason is not None:
            receipt.notes = (*receipt.notes, reason)

        # Auditoría: el evento ES el recibo durable (también en dry run, para que la
        # puerta quede trazada aunque no escriba nada del lifecycle).
        payload = receipt.to_payload()
        payload["actor"] = request.actor
        payload["eventType"] = TRIGGER_AUDIT_EVENT_TYPE
        receipt.audit_event_id = await self._ledger.append(run_id=run_id, payload=payload)
        logger.info(
            "orchestrator trigger instrument=%s status=%s phase=%s dry_run=%s "
            "run_id=%s actor=%s",
            instrument_id,
            status,
            phase,
            request.dry_run,
            run_id,
            request.actor,
        )
        return receipt
