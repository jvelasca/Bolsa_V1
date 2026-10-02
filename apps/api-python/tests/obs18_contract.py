"""Contrato ÚNICO OBS-18 del cierre de una reserva con fill PARCIAL.

Antes este contrato vivía duplicado (y DIVERGENTE) en dos gemelos:

* ``test_auto_v46_concurrent.py`` (hermético) medía el estado **intermedio** que deja
  ``AutoSimulationWorker.auto_turn`` por sí solo: la regla 1 (``RELEASE_REASON_FILL``) libera
  SOLO lo materializado y deja la COLA viva ⇒ ``released_qty == materializado``,
  ``remaining_qty == pedido − materializado``.
* ``test_concurrent_auto_pg.py`` (PG) medía el estado **terminal** que deja el CIERRE de
  turno (``AutoSimRuntime.run_tick`` → ``real_turn`` → ``_v2_reconcile_reservations`` con
  ``startup=False, attribute_fills=False, only_ids=...``): la regla 2 (OBS-18) retira la cola
  muerta ⇒ ``released_qty == pedido``, ``remaining_qty == 0``, motivo ``tail_dead``.

Las dos observaciones eran ciertas de su punto de entrada, pero solo la segunda es el estado
**terminal** de producción. Este módulo fija ESE oráculo en un único sitio y ambos gemelos lo
comparten: el hermético conduce ``real_turn`` (el mismo cierre que el proceso real) para que
midan lo mismo.

Contrato terminal (lo que TODO consumidor debe observar al acabar el turno):

* ``released_qty == quantity`` — la fila se libera ENTERA (fill materializado + cola muerta);
* ``remaining_qty == 0`` — no queda cola viva retenida (el bug que OBS-18 cierra);
* ``release_reason == 'tail_dead'`` — la fila SÍ registró fill parcial (evidencia de fill);
* ``status != 'OPEN'`` — una reserva retirada no puede seguir comprometiendo capital;
* capital retenido ``reserved_cash == 0`` — no hay sobre-riesgo × nº de workers.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

#: Motivo canónico de la retirada de la COLA de un fill parcial (``replay_oos``).
DEAD_TAIL_REASON = "tail_dead"
#: Estado final de la fila retirada por cancelación de su cola.
RELEASED_BY_CANCEL = "RELEASED_BY_CANCEL"


def assert_obs18_terminal_reservation(reservation: Any, *, diagnostic: str = "") -> None:
    """Exige el contrato terminal OBS-18 sobre una fila de reserva ya cerrada.

    ``diagnostic`` se añade al mensaje de fallo (p. ej. ``Σ APPLIED``/hechos del ledger) para
    separar «fila sin fill» de «procedencia perdida».
    """
    requested = Decimal(str(reservation.quantity))
    released = Decimal(str(reservation.released_qty or 0))
    remaining = Decimal(str(reservation.remaining_qty or 0))
    suffix = f" [{diagnostic}]" if diagnostic else ""
    assert released == requested, (
        "OBS-18: la fila debe quedar liberada ENTERA (fill materializado + cola muerta); "
        f"released={released} pedido={requested}{suffix}"
    )
    assert remaining == 0, (
        f"OBS-18: no puede quedar cola viva retenida (remaining={remaining}){suffix}"
    )
    assert str(reservation.release_reason) == DEAD_TAIL_REASON, (
        "OBS-18: la retirada debe DECLARAR que había cola de fill parcial "
        f"(motivo={reservation.release_reason!r} status={reservation.status!r}){suffix}"
    )
    assert str(reservation.status).upper() != "OPEN", (
        f"OBS-18: una reserva retirada no puede quedar OPEN (status={reservation.status!r}){suffix}"
    )
    assert float(reservation.reserved_cash or 0) == 0.0, (
        "OBS-18: no puede quedar capital retenido tras retirar la cola "
        f"(reserved_cash={reservation.reserved_cash}){suffix}"
    )
