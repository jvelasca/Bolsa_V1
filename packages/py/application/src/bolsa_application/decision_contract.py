"""V2.21 / A8 (M5) — Contrato IA vs gates deterministas (solo propone; SIN IA).

Separación de poderes exigida por el audit §9/§14 (AUTO → SIMULATED ONLY):

    DecisionPackage (IA propone) → RiskGate (determinista) → ExecutionPlan → broker.

La IA/documento únicamente produce un ``DecisionPackage``: un intent de trade
``BUY/SELL/HOLD`` con símbolo/cantidad/precio. **Nunca** puede pedir ejecutar un
bypass: el ``RiskGateDecision`` derivado por el callejón determinista es quien
otorga o veta el paso a un ``ExecutionPlan`` (que a su vez jamás abre la vía
LIVE — M0 la mantiene doblemente bloqueada). Este módulo es SOLO contrato/forma:
no hay código de IA nuevo (per tu opción contract_doc), y el test de barricada
prueba que cualquier canal IA que intente ejecutar bypass es abortado por el gate.

Garantía P0: un DecisionPackage NO puede saltar Risk Engine (kill switch),
Reconciliation ni el Simulation Gate. Incluso un BUY agresivo de IA se reduce a
proponer: la puerta determinista puede emitir ``hold``/``veto`` y jamás arrancar
dinero sin venue PAPER/Simulated + ausencia de kill switch (y aun así el SIM only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

Action = Literal["BUY", "SELL", "HOLD"]

VenueAllowed = Literal["paper", "simulated"]

# El SOLO venue que un DecisionPackage puede terminar ejecutando (si se llegara):
# nunca LIVE real. M0 bloquea además el camino XTB con doble barrera.
ALLOWED_AUTO_VENUES: frozenset[VenueAllowed] = frozenset({"paper", "simulated"})

# H1: prefijo canónico de la fuente de una propuesta de la estrategia ACTIVE.
_ACTIVE_STRATEGY_SOURCE_PREFIX = "active-strategy:"


def format_active_strategy_source(version_id: str, preset_key: str | None) -> str:
    """H1 — Fuente canónica de una propuesta de la estrategia ACTIVE.

    Formato fijado (lo parsea el worker AUTO; NO cambiar sin coordinar):

    * sin ``preset_key`` (``None``, cadena vacía o solo espacios) ⇒
      ``active-strategy:<version_id>`` (identidad histórica, sin cambios).
    * con ``preset_key`` no vacío ⇒ ``active-strategy:<version_id>::<preset_key>``
      (separador literal de dos caracteres ``::``).

    El ``preset_key`` es la identidad exacta que el motor AUTO realmente conoce. Un
    ``version_id`` vacío se conserva tal cual (``active-strategy:``), igual que hoy:
    la ausencia de preset nunca cambia la forma previa.

    Única fuente de verdad: ambos decisores (``auto_orchestrator`` y
    ``active_strategy_signal_evaluator``) la importan para no poder divergir.
    """
    key = (preset_key or "").strip()
    if key:
        return f"{_ACTIVE_STRATEGY_SOURCE_PREFIX}{version_id}::{key}"
    return f"{_ACTIVE_STRATEGY_SOURCE_PREFIX}{version_id}"



class RiskGateReason(StrEnum):
    AUTO_OK_SIMULATED = "auto_simulated_only"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    VIOLATES_SIMULATION_GATE = "violates_simulation_gate"
    VENUE_NOT_AUTO_ALLOWED = "venue_not_auto_allowed"
    IA_ATTEMPTED_BYPASS = "ia_attempted_bypass"


@dataclass(frozen=True, slots=True)
class DecisionPackage:
    """Intención PROPUESTA por la IA/sesión. Solo sirve para proponer.

    NO es una orden ni lleva idempotency financiera; es el payload que SOMETE al
    RiskGate determinista. Un BUY/SELL con cantidad>0 aquí es una PROPUESTA.
    """

    action: Action
    instrument_id: str
    quantity: float = 0.0
    suggested_price: float = 0.0
    source: str = "id_used_to_propose"
    proposed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    memo: str = ""
    # O-6 — PROCEDENCIA de la feature que sostiene la propuesta. Aditivas: ``None`` en los
    # productores que no la declaran, y ``None`` se OMITE al aterrizar en el journal (la
    # ausencia es información, jamás un relleno). ``feature_source`` es ``"real"`` (OHLCV
    # completo) o ``"synthetic"`` (ventana close-only: ``volume = 0`` y rango = cierre) —los
    # presets de rango o volumen no valen lo mismo en cada caso—; ``signal_window_bars`` es
    # el número de barras realmente evaluadas, el dato que distingue «no había señal» de
    # «la ventana no alcanza el warmup».
    feature_source: str | None = None
    signal_window_bars: int | None = None
    # B-5 — MOTIVO TIPIFICADO de un ``HOLD`` que no es «la señal dijo no». Una estrategia
    # promovida puede quedarse fuera del mercado por configuración (``active_signal_disabled``),
    # por falta de definición ejecutable (``no_executable``) o por no tener barras
    # (``no_snapshot``); los tres casos producían la MISMA fila —ninguna— y el operador solo veía
    # «no operó». El literal vive en ``auto_reason_codes.ACTIVE_HOLD_REASONS`` y el worker lo
    # journaliza; ``None`` (sin motivo) es el HOLD legítimo de una señal que se evaluó y no entró.
    hold_reason: str | None = None
    # B-1 (ventana derivada) — ADITIVAS. ``warmup_bars`` es el warmup que el preset exige,
    # **medido sobre la serie** (``preset_evaluability.measured_warmup_bars``); ``None``
    # significa que no se pudo medir, y entonces la decisión es un HOLD declarado
    # (``warmup_unmeasurable``), nunca una ventana inventada. ``signal_window_source`` dice
    # de dónde salió la ventana efectiva: ``"env"`` (el suelo configurado) o
    # ``"preset_warmup"`` (se subió para cubrir el warmup del preset). Se omite si no hay dato.
    warmup_bars: int | None = None
    signal_window_source: str | None = None

    @property
    def is_execution_intent(self) -> bool:
        """Un DecisionPackage nunca se considera por sí solo una intención ejecutable."""
        return False


@dataclass(frozen=True, slots=True)
class RiskGateDecision:
    """Veredicto determinista sobre un DecisionPackage."""

    allow_proposal: bool
    reasons: tuple[RiskGateReason, ...] = ()
    memo: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Registro determinista de planificación emitido por la puerta (SIM-ONLY).

    NO es una orden y NUNCA lleva venue LIVE: es la separación intermedia del
    contrato ``DecisionPackage → RiskGate → ExecutionPlan → broker``. Solo una
    capa posterior de M4 podría materializar el llenado — siempre PAPER/Simulated
    y aun así gobernada por gates. Este módulo (M5) solo describe/emite la forma.
    """

    instrument_id: str
    action: Action
    quantity: float
    venue: VenueAllowed = "simulated"
    plan_id: str = "plan_sim_dry"
    planned_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def targets_live(self) -> bool:
        """Un ExecutionPlan derivado por el callejón determinista jamás apunta LIVE."""
        return False


def derive_execution_plan(
    pkg: DecisionPackage,
    *,
    venue: str,
    kill_switch_active: bool = False,
) -> ExecutionPlan | None:
    """Da (o no) un ``ExecutionPlan`` SIM-ONLY a partir de una propuesta.

    Acta de SAFE/dry: solo cuando la puerta ``risk_gate_auto_paper_dry`` admite la
    propuesta y el venue es paper/simulated se materializa el **registro** de
    plan. Cualquier venue LIVE se rechaza devolviendo ``None`` (la vía M0 queda
    doblemente bloqueada; no hay ExecutionPlan LIVE posible).
    """
    verdict = risk_gate_auto_paper_dry(
        pkg,
        kill_switch_active=kill_switch_active,
        venue=venue,
    )
    if not verdict.allow_proposal or pkg.action == "HOLD":
        return None
    # venue garantizado en {paper, simulated} por la puerta (nunca LIVE real).
    assigned = str(venue).strip().lower()
    allowed: VenueAllowed = "simulated" if assigned == "simulated" else "paper"
    return ExecutionPlan(
        instrument_id=pkg.instrument_id,
        action=pkg.action,
        quantity=pkg.quantity,
        venue=allowed,  # literal "paper"/"simulated", nunca real.
    )


def simulation_gate_allows(venue: str) -> bool:
    """V2.22/A9 (M6) — 3ª barrera antes de resolver un broker: si alguien (o un env
    mal configurado: ``AUTO_ENGINE_SIMULATED_VENUE=live``) solicita LIVE desde el
    camino AUTO, este gate lo BLOQUEA de forma temprana, sin depender de las
    barreras posteriores (M0/LIVE-adapter).

    Solo deja pasar un venue AUTO-permitido ({paper, simulated}), que es el único
    destino que jamás abre la vía real. Una sola fuente con el funnel de
    liquidación (``AUTO_SETTLE_VENUES``) para que un gate y un settle nunca
    discrepen.
    """
    from bolsa_application.simulated_settlement import normalized_auto_venue

    return normalized_auto_venue(venue) is not None


def risk_gate_auto_paper_dry(
    pkg: DecisionPackage,
    *,
    kill_switch_active: bool,
    venue: str,
    require_simulated_or_paper: bool = True,
) -> RiskGateDecision:
    """Puerta determinista AUTO (SAFE/**dry**): nunca produce ExecutionPlan LIVE.

    * kill switch ON o venue fuera de {paper, simulated} → NO propuesta (veto).
    * Requiere que la IA **no** haya intentado marcar ejecución directa (bypass).
    """
    if pkg.is_execution_intent:
        return RiskGateDecision(
            allow_proposal=False,
            reasons=(RiskGateReason.IA_ATTEMPTED_BYPASS,),
            memo="IA no puede saltar los gates: solo propone.",
        )
    if kill_switch_active:
        return RiskGateDecision(
            allow_proposal=False,
            reasons=(RiskGateReason.KILL_SWITCH_ACTIVE,),
            memo="kill switch activo: nada AUTO procede.",
        )
    if require_simulated_or_paper or pkg.action == "HOLD":
        if str(venue).strip().lower() not in ALLOWED_AUTO_VENUES:
            return RiskGateDecision(
                allow_proposal=False,
                reasons=(
                    RiskGateReason.VENUE_NOT_AUTO_ALLOWED,
                    RiskGateReason.VIOLATES_SIMULATION_GATE,
                ),
                memo=f"venue={venue} no es AUTO-allowed ({sorted(ALLOWED_AUTO_VENUES)}).",
            )
        # Auto-Paper dry: la propuesta es admisible de cara a sim (aún no llena).
        return RiskGateDecision(
            allow_proposal=True,
            reasons=(RiskGateReason.AUTO_OK_SIMULATED,),
            memo="proposal AUTO admisible en SAFE/dry (no llena dinero por sí).",
        )
    return RiskGateDecision(
        allow_proposal=False,
        reasons=(RiskGateReason.VIOLATES_SIMULATION_GATE,),
        memo="no permitido fuera de SAFE/simulated.",
    )
