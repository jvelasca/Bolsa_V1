"""AUTO v2.88.26 — vocabulario canónico del HECHO durable de PROTECCIÓN.

Qué cierra: hasta hoy la protección de una posición vivía **sólo** en el estado proyectado
(``sim_auto_positions.position_state``): el monitor encendía el paso ``PROTECTION`` con esa
proyección y no había traza append-only de las transiciones (ratchet de stop, T1/T2, armado de
trailing, salida pedida) que permitiesen reconstruir *cuándo* y *por qué* cambió la protección.

Este módulo fija el vocabulario del ``kind`` con el que esas transiciones se **persisten** como
entradas append-only en el spine (``decision_journal_entries``, ``auto_protection_event``). Es un
vocabulario **cerrado** y **compuesto de las casas únicas**:

* los eventos del FSM de ``position_lifecycle`` (``PROTECT_APPLIED``, ``T1_HIT``, ``TRAIL_ARMED``,
  ``TRAIL_ADVANCED``, ``TIME_EXIT``, ``THESIS_EXIT``, ``EXIT_REQUESTED``);
* los ``reason codes`` de gestión de ``auto_reason_codes`` (``STOP_RATCHET_APPLIED``,
  ``PROTECT_REQUESTED``);
* una **extensión declarada**: ``T2_HIT`` (espejo de ``T1_HIT``; el FSM no tiene evento T2).

Regla dura (misma que ``price_source_kind``): la ausencia se DECLARA. Un ``kind`` ajeno al
vocabulario no se convierte en un literal inventado ni en una cadena libre — se normaliza a
``None`` (no medido), nunca a un ``"UNKNOWN"`` que parecería una medición.
"""

from __future__ import annotations

from bolsa_analytics.cognitive.position_lifecycle import T2_HIT
from bolsa_application.auto_reason_codes import PROTECT_REQUESTED, STOP_RATCHET_APPLIED

__all__ = [
    "PROTECTION_EVENT_KINDS",
    "usable_protection_kind",
]

#: Motivos de gestión (``auto_reason_codes``) llevados a la forma canónica del hecho durable.
#: La casa de los literales sigue siendo ``auto_reason_codes`` (los escribe en minúscula porque
#: son ``reason codes`` del journal); aquí sólo se normalizan a MAYÚSCULAS para que el ``kind``
#: del hecho durable no viaje escrito de dos formas.
STOP_RATCHET_KIND = STOP_RATCHET_APPLIED.upper()
PROTECT_REQUESTED_KIND = PROTECT_REQUESTED.upper()

#: Vocabulario cerrado del ``kind`` del hecho durable de protección. Reutiliza el FSM (una sola
#: casa de los literales de ciclo de vida) + los motivos de gestión + ``T2_HIT`` (extensión
#: declarada: el FSM no tiene evento T2, sólo ``T1_HIT``).
PROTECTION_EVENT_KINDS: frozenset[str] = frozenset(
    {
        # Eventos del FSM (``position_lifecycle``).
        "PROTECT_APPLIED",
        "T1_HIT",
        T2_HIT,
        "TRAIL_ARMED",
        "TRAIL_ADVANCED",
        "TIME_EXIT",
        "THESIS_EXIT",
        "EXIT_REQUESTED",
        # Motivos de gestión de posición (``auto_reason_codes``), en forma canónica.
        STOP_RATCHET_KIND,
        PROTECT_REQUESTED_KIND,
    }
)


def usable_protection_kind(raw: object) -> str | None:
    """(PURA) el ``kind`` UTILIZABLE, o ``None`` si no pertenece al vocabulario.

    Un valor ausente o ajeno al vocabulario NO se rellena con un literal: se declara como
    "no medido" (``None``). Normaliza el texto (mayúsculas/espacios) para que el mismo hecho
    no viaje escrito de dos formas.
    """
    text = str(raw or "").strip().upper()
    return text if text in PROTECTION_EVENT_KINDS else None
