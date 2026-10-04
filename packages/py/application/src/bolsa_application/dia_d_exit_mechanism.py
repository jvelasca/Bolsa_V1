"""V2.88.44 · DÍA-D AUTO — vocabulario y clasificador del MECANISMO DE SALIDA (puro).

Qué es
------
El diagnóstico de dónde nace la pérdida necesita saber **por qué decisión** se cerró cada ciclo:
un ``structural_stop``, un ``target_1``/``target_2``, un ``trail``, un ``time_exit``, un
``thesis_exit``, un cierre de gobernador (``risk_exit``/``regime_exit``/``kill_switch``) o una
salida genérica del decider. El journal del motor ya publica ese motivo por fila
(``position_close.reason``, el ``day_exit_reason`` del plan de salida); este módulo es la ÚNICA
casa que lo **clasifica** en un mecanismo estable, para que el ledger y el plegado no improvisen
cada uno su propia taxonomía.

Tres reglas duras
-----------------
* **Un motivo ausente NO se disfraza.** Sin ``reason`` el mecanismo es ``SIN_MECANISMO``
  (hueco declarado, nunca ``0`` ni una etiqueta inventada).
* **La precedencia es determinista.** El motivo puede traer varios tokens (p. ej. la política
  legacy junta razones con comas); se resuelve con un orden fijo
  (``STOP > TRAILING > TARGET_2 > TARGET_1 > TIME > THESIS > ...``) para que dos tokens nunca
  empaten ni dependan del orden de lectura.
* **Un token no catalogado se declara genérico** (``EXIT_REQUESTED``): el decider pidió salir sin
  un mecanismo de esta tabla. El texto CRUDO viaja aparte (``exitEvidence``) para no perder el
  rastro: clasificar no es borrar.

Puro y determinista: sin I/O, sin reloj, sin estado.
"""

from __future__ import annotations

from typing import Any

#: El motor EJECUTÓ el stop estructural (o el stop de protección legacy).
EXIT_MECHANISM_STOP = "STOP_EJECUTADO"
#: Primer objetivo alcanzado (parcial o total).
EXIT_MECHANISM_TARGET_1 = "TARGET_1"
#: Segundo objetivo alcanzado.
EXIT_MECHANISM_TARGET_2 = "TARGET_2"
#: Salida por trailing (el stop acompañó al precio).
EXIT_MECHANISM_TRAILING = "TRAILING"
#: Salida por tiempo (``time_exit``).
EXIT_MECHANISM_TIME = "TIME_EXIT"
#: Salida por invalidación de tesis (``thesis_exit``).
EXIT_MECHANISM_THESIS = "THESIS_EXIT"
#: Salida por régimen (gobernador).
EXIT_MECHANISM_REGIME = "REGIME_EXIT"
#: Liquidación de riesgo del gobernador.
EXIT_MECHANISM_RISK = "RISK_EXIT"
#: Parada dura (``kill_switch``).
EXIT_MECHANISM_KILL_SWITCH = "KILL_SWITCH"
#: Riesgo de cartera (``portfolio_risk``).
EXIT_MECHANISM_PORTFOLIO_RISK = "PORTFOLIO_RISK"
#: Salida manual declarada.
EXIT_MECHANISM_MANUAL = "MANUAL"
#: El decider pidió salir sin un mecanismo catalogado (o el motivo legacy de sesión).
EXIT_MECHANISM_EXIT_REQUESTED = "EXIT_REQUESTED"
#: HUELLO DECLARADO: no hay motivo de cierre medido (nunca ``0`` ni una etiqueta inventada).
EXIT_MECHANISM_SIN_MECANISMO = "SIN_MECANISMO"

#: Orden determinista de precedencia (gana el primero presente). Un caso con dos tokens
#: (``stop`` + ``t1``) se atribuye al de mayor precedencia: el hecho más severo.
PRECEDENCE: tuple[str, ...] = (
    EXIT_MECHANISM_STOP,
    EXIT_MECHANISM_TRAILING,
    EXIT_MECHANISM_TARGET_2,
    EXIT_MECHANISM_TARGET_1,
    EXIT_MECHANISM_TIME,
    EXIT_MECHANISM_THESIS,
    EXIT_MECHANISM_REGIME,
    EXIT_MECHANISM_RISK,
    EXIT_MECHANISM_KILL_SWITCH,
    EXIT_MECHANISM_PORTFOLIO_RISK,
    EXIT_MECHANISM_MANUAL,
    EXIT_MECHANISM_EXIT_REQUESTED,
)

#: Vocabulario PÚBLICO completo (los mecanismos citables, sin el hueco).
EXIT_MECHANISMS: tuple[str, ...] = PRECEDENCE

#: Tokens crudos → mecanismo. Incluye el vocabulario del día (``DAY_EXIT_REASONS``) y el legacy
#: de la política de protección (``protective_stop``/``t1_exit``/``trailing_stop``/``session_close``).
_TOKEN_TO_MECHANISM: dict[str, str] = {
    "structural_stop": EXIT_MECHANISM_STOP,
    "protective_stop": EXIT_MECHANISM_STOP,
    "stop": EXIT_MECHANISM_STOP,
    "trail": EXIT_MECHANISM_TRAILING,
    "trailing": EXIT_MECHANISM_TRAILING,
    "trailing_stop": EXIT_MECHANISM_TRAILING,
    "target_2": EXIT_MECHANISM_TARGET_2,
    "t2_exit": EXIT_MECHANISM_TARGET_2,
    "t2_hit": EXIT_MECHANISM_TARGET_2,
    "target_1": EXIT_MECHANISM_TARGET_1,
    "t1_exit": EXIT_MECHANISM_TARGET_1,
    "t1_hit": EXIT_MECHANISM_TARGET_1,
    "time_exit": EXIT_MECHANISM_TIME,
    "time_stop": EXIT_MECHANISM_TIME,
    "thesis_exit": EXIT_MECHANISM_THESIS,
    "thesis_invalidation": EXIT_MECHANISM_THESIS,
    "regime_exit": EXIT_MECHANISM_REGIME,
    "risk_exit": EXIT_MECHANISM_RISK,
    "kill_switch": EXIT_MECHANISM_KILL_SWITCH,
    "portfolio_risk": EXIT_MECHANISM_PORTFOLIO_RISK,
    "manual": EXIT_MECHANISM_MANUAL,
    "session_close": EXIT_MECHANISM_EXIT_REQUESTED,
    "exit_requested": EXIT_MECHANISM_EXIT_REQUESTED,
}


def classify_exit_mechanism(reason: Any) -> tuple[str, str]:
    """``(mecanismo, evidencia)`` de un motivo de cierre crudo (PURO y total).

    ``evidencia`` es el texto CRUDO normalizado (puede ser ``""``): se conserva para que
    clasificar no borre el rastro. Sin motivo ⇒ ``(SIN_MECANISMO, "")``. Un token no catalogado
    ⇒ ``(EXIT_REQUESTED, raw)``: el decider salió sin mecanismo de la tabla, y se declara así en
    vez de inventar uno.
    """
    raw = str(reason or "").strip()
    if not raw:
        return EXIT_MECHANISM_SIN_MECANISMO, ""
    tokens = {token.strip().lower() for token in raw.split(",") if token.strip()}
    mapped = {_TOKEN_TO_MECHANISM[token] for token in tokens if token in _TOKEN_TO_MECHANISM}
    if not mapped:
        return EXIT_MECHANISM_EXIT_REQUESTED, raw
    for mechanism in PRECEDENCE:
        if mechanism in mapped:
            return mechanism, raw
    return EXIT_MECHANISM_EXIT_REQUESTED, raw


__all__ = [
    "EXIT_MECHANISMS",
    "EXIT_MECHANISM_EXIT_REQUESTED",
    "EXIT_MECHANISM_KILL_SWITCH",
    "EXIT_MECHANISM_MANUAL",
    "EXIT_MECHANISM_PORTFOLIO_RISK",
    "EXIT_MECHANISM_REGIME",
    "EXIT_MECHANISM_RISK",
    "EXIT_MECHANISM_SIN_MECANISMO",
    "EXIT_MECHANISM_STOP",
    "EXIT_MECHANISM_TARGET_1",
    "EXIT_MECHANISM_TARGET_2",
    "EXIT_MECHANISM_THESIS",
    "EXIT_MECHANISM_TIME",
    "EXIT_MECHANISM_TRAILING",
    "PRECEDENCE",
    "classify_exit_mechanism",
]
