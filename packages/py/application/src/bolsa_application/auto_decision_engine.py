"""V2.23 / A9 (Bloque 4) — Decision Spine determinista e inyectable (sin IA real).

El worker AUTO decide por símbolo a través de un ``DecisionProvider``
(= ``Callable[[str], DecisionPackage]``). Vivir con ``None`` (⇒ HOLD permanente) era el
hueco P1-02 del audit: existe el contrato y el proxy de gobernanza IA, pero ningún
motor que proponga BUY/SELL en el hot path.

Este módulo aporta un **Decision Spine determinista** (sin LLM, sin credenciales, sin
red) como proveedor operativo por defecto del scheduler SIM. Sus reglas son cerradas y
SÓLO proponen decisiones; la ejecución/autoridad sigue en las barreras de
``decision_contract`` (RiskGate / kill switch / Simulation-Gate / position-limits).

El futuro socket IA es explícito: un ``DecisionSpineAI`` puede sustituir a esta clase
implementando el MISMO contrato (``__call__(symbol) -> DecisionPackage``). Un LLM o
proxy de gobernanza NO entra en el hot path (decisión de arquitectura): IA propone,
el gate de riesgo decide y, si no responde, la política determinista degrada a HOLD.

Comportamiento (día autónomo determinista acotado, HOLD-dominante y fail-closed):

* Con ``enabled=False`` (default) o símbolo fuera del ``watch`` ⇒ HOLD. Sin ``enabled``
  el motor NUNCA propone ninguna compra (seguro por defecto).
* Al primer tick de un símbolo nuevo del watch ⇒ propone ``BUY lot_qty``.
* Durante ``exit_after_ticks`` vueltas con la posición abierta ⇒ propone HOLD
  (retención); pasado ese retén ⇒ propone ``SELL`` de toda la horquilla (cierre).
* Tras el cierre el símbolo entra en ``COOLDOWN`` y NO re-abre en este proceso
  (no-doble BUY tras cierre; no apilar). A crash/restart la posición durable y su
  readopción son del Bloque 5.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from bolsa_application.decision_contract import DecisionPackage

# El socket IA del AUTO = ``Callable[[str], DecisionPackage]`` (el mismo alias que
# ``paper_auto_engine_worker.DecisionProvider`` en la capa API; se declara local para
# no acoplar la capa de aplicación al proceso HTTP/worker).
DecisionProvider = Callable[[str], DecisionPackage]

__all__ = [
    "AutoDecisionEngine",
    "deterministic_auto_decider",
]


@dataclass(slots=True)
class AutoDecisionEngine:
    """Spine Decision determinista: horquillas BUY→(HOLD)→SELL por símbolo.

    No es un modelo de mercado: es la forma mínima y repetible de materializar el
    camino AUTO SIM end-to-end (A9) y dejar el socket a un ``DecisionSpineAI`` futuro.
    """

    watch: tuple[str, ...] = ()
    lot_qty: float = 100.0
    exit_after_ticks: int = 3
    max_qty: float = 100.0
    enabled: bool = False

    # estado en proceso (la posición durable/readopción es Bloque 5).
    _state: dict[str, str] = field(default_factory=dict)  # BUY | COOLDOWN
    _enter_ticks: dict[str, int] = field(default_factory=dict)
    _age: int = 0

    def __call__(self, symbol: str) -> DecisionPackage:
        try:
            return self._decide(symbol)
        except Exception:  # noqa: BLE001 — una propuesta nunca debe romper el motor.
            return DecisionPackage(
                action="HOLD", instrument_id=symbol, quantity=0,
                source="auto-spine:deterministic",
            )

    def _decide(self, symbol: str) -> DecisionPackage:
        if not self.enabled or symbol not in self.watch:
            return DecisionPackage(
                action="HOLD", instrument_id=symbol, quantity=0,
                source="auto-spine:deterministic",
            )
        self._age += 1
        if self._state.get(symbol) == "COOLDOWN":
            return DecisionPackage(
                action="HOLD", instrument_id=symbol, quantity=0,
                source="auto-spine:deterministic",
            )
        if symbol not in self._state:
            # Primera exposición: apertura acotada (el RiskGate+position-limits vetan
            # si procede; un segundo BUY sobre posición ya abierta la bloquea el worker).
            self._state[symbol] = "BUY"
            self._enter_ticks[symbol] = self._age
            return DecisionPackage(
                action="BUY", instrument_id=symbol,
                quantity=min(self.lot_qty, self.max_qty),
                source="auto-spine:deterministic",
            )
        # Retención determinista y cierre.
        if self._age - self._enter_ticks.get(symbol, self._age) >= self.exit_after_ticks:
            self._state[symbol] = "COOLDOWN"
            return DecisionPackage(
                action="SELL", instrument_id=symbol,
                quantity=min(self.lot_qty, self.max_qty),
                source="auto-spine:deterministic",
            )
        return DecisionPackage(
            action="HOLD", instrument_id=symbol, quantity=0,
            source="auto-spine:deterministic",
        )


def deterministic_auto_decider(
    watch: tuple[str, ...],
    *,
    lot_qty: float = 100.0,
    exit_after_ticks: int = 3,
    max_qty: float = 100.0,
    enabled: bool = False,
) -> DecisionProvider:
    """Factory de un ``DecisionProvider`` determinista listo para el worker Auto."""
    return AutoDecisionEngine(
        watch=tuple(watch),
        lot_qty=lot_qty,
        exit_after_ticks=exit_after_ticks,
        max_qty=max_qty,
        enabled=enabled,
    )
