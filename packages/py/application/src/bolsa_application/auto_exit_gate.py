"""S-6 — el worker AUTO consulta F5 (``ExitPermission``) antes de emitir una salida.

**Hallazgo (auditoría 2026-10-26 §5.8).** ``check_exit_permission`` se invocaba en
``evaluate_exit_plan``, en el desk paper y en las pruebas, pero **no** en el worker AUTO:
las condiciones que F5 veta (``data_stale``/``market_closed``/``portfolio_drift``/
``paper_auto_env_blocked``) no tenían ningún efecto sobre una salida AUTO y **el efecto
no estaba declarado** en el journal ni en la UI. No era un bypass accidental; era una
decisión de arquitectura sin contrato escrito.

**Decisión declarada (este módulo la hace explícita).**

1. El AUTO **consulta** F5 en cada salida que va a emitir, sobre el **mismo ``ExitPlan``**
   que produjo la decisión (``PositionManagerResult.exit_plan``). Consultar un plan
   reconstruido aguas abajo reabriría el drift que S-1/S-2 cerraron: dos capas juzgando
   objetos distintos con la misma condición.
2. El veredicto **no bloquea** la salida en AUTO SIM, y eso se declara con
   ``exemption = "auto_sim_exit_precedence"`` cuando F5 niega. Por qué:
   * la salida protectora (stop, trail, riesgo de cartera, gobernador, invalidación de
     tesis) reduce riesgo: vetarla empeora el riesgo, que es el invariante de la casa;
   * el venue es el simulador paper, así que un ``market_closed``/``portfolio_drift`` de
     F5 no describe una orden real contra un bróker;
   * bloquear un objetivo (``TARGET_1``/``TARGET_2``/``TIME_STOP``) por dato rancio
     cambiaría la serie de fills del simulador sin reducir exposición.
3. Nada queda mudo: el veredicto, sus motivos, el contexto JIT y la exención viajan al
   journal (``exit_permission``), de modo que la asimetría se ve en vez de descubrirse.

El contrato es deliberadamente estrecho: **este módulo no ejecuta** ni conoce el
settlement; sólo traduce un ``ExitPlan`` a un veredicto revisable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.exit_permission import ExitPermission
from bolsa_analytics.cognitive.exit_plan import PROTECTIVE_EXIT_REASONS, ExitPlan
from bolsa_application.auto_reason_codes import EXIT_PERMISSION
from bolsa_application.evaluate_exit_plan import auto_exit_permission

#: Motivo declarado por el que una salida AUTO se emite aunque F5 la niegue.
AUTO_EXIT_EXEMPTION = "auto_sim_exit_precedence"

#: ``reasonCode`` con el que el worker journaliza la consulta (una por salida emitida). La
#: casa única del literal es ``auto_reason_codes``: así el journal y el lector del día no
#: pueden discrepar sobre qué código es una atribución de gestión.
AUTO_EXIT_PERMISSION_EVENT = EXIT_PERMISSION


@dataclass(frozen=True, slots=True)
class AutoExitReview:
    """Consulta F5 de una salida AUTO, con la exención declarada."""

    permission: ExitPermission
    protective: bool
    exemption: str | None

    @property
    def denied(self) -> bool:
        """F5 negaría la salida (``DENY``). No implica que el AUTO no vaya a salir."""
        return self.permission.verdict == "DENY"

    @property
    def blocks_exit(self) -> bool:
        """Contrato S-6: en AUTO SIM F5 **nunca** bloquea una salida. Siempre ``False``.

        Si algún día se decide bloquear, el cambio es de arquitectura y DEBE pasar por
        este punto único (y por su prueba), no por una rama suelta en el worker.
        """
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "permission": self.permission.to_dict(),
            "protective": self.protective,
            "exemption": self.exemption,
            # El contrato se publica con el hecho: quien lea el journal no tiene que
            # inferir si la salida se emitió a pesar del DENY.
            "blocksExit": False,
        }


def review_auto_exit(
    exit_plan: ExitPlan | None,
    *,
    data_stale: bool = False,
    portfolio_drift: bool = False,
    market_closed: bool | None = None,
    paper_d_execute: bool = True,
    kill_switch: bool = False,
    at: str | None = None,
) -> AutoExitReview:
    """Consulta F5 para una salida AUTO (sin ejecutar nada).

    ``market_closed=None`` = el worker no mide la sesión: se declara desconocido y, con
    ``require_jit_context=False``, no fabrica un veto que no puede sostener. ``data_stale``
    y ``portfolio_drift`` los aporta el tick (el mismo dato con el que se vetan aperturas).

    ``paper_d_execute=True`` porque el venue del AUTO es el simulador paper: sin esta
    bandera F5 negaría por ``paper_auto_env_blocked`` en TODAS las salidas y el veredicto
    dejaría de informar sobre el dato.
    """
    permission = auto_exit_permission(
        exit_plan,
        paper_d_execute=paper_d_execute,
        data_stale=data_stale,
        market_closed=market_closed,
        portfolio_drift=portfolio_drift,
        kill_switch=kill_switch,
        require_jit_context=False,
        at=at,
    )
    protective = bool(
        exit_plan is not None
        and exit_plan.primary_reason in PROTECTIVE_EXIT_REASONS
    )
    exemption = AUTO_EXIT_EXEMPTION if permission.verdict == "DENY" else None
    return AutoExitReview(
        permission=permission,
        protective=protective,
        exemption=exemption,
    )


__all__ = [
    "AUTO_EXIT_EXEMPTION",
    "AUTO_EXIT_PERMISSION_EVENT",
    "AutoExitReview",
    "review_auto_exit",
]
