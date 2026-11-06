"""Entidad de dominio — propuesta diaria ESTUDIO con identidad durable (handoff).

El parte diario ESTUDIO publica, por valor, una señal (``signalId``) y un plan
(``TradePlan.decisionId``). Hasta ahora esa identidad vivía **solo** dentro del
``result`` del job: el productor AUTO no la consumía y, por tanto, el ciclo durable
que abría el motor no podía enlazarse con la propuesta que el usuario había visto
en pantalla. La coincidencia de símbolo no es una atribución y este repositorio no
la usa como tal.

Esta entidad es el puente **durable** entre ambos mundos: una fila por
``(cuenta, día, instrumento)`` que conserva la identidad propuesta y su desenlace
(``proposed`` → ``consumed`` | ``rejected`` | ``expired``).

Doctrina «Sin dato todavía» (``UNKNOWN != 0``): un campo que la propuesta no declara
viaja ``None``; jamás un valor inventado. Una propuesta que no se consumió **no** se
marca consumida: queda declarada con su motivo.

Sin dependencias externas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Estado inicial: la propuesta se publicó y espera al productor.
PROPOSAL_STATUS_PROPOSED = "proposed"
#: El productor adoptó la identidad y abrió un ciclo durable con ella.
PROPOSAL_STATUS_CONSUMED = "consumed"
#: Los gates del motor vetaron la entrada: la propuesta NO se sustituye por otra.
PROPOSAL_STATUS_REJECTED = "rejected"
#: La propuesta envejeció antes de que el productor la evaluara (frescura declarada).
PROPOSAL_STATUS_EXPIRED = "expired"

PROPOSAL_STATUSES: tuple[str, ...] = (
    PROPOSAL_STATUS_PROPOSED,
    PROPOSAL_STATUS_CONSUMED,
    PROPOSAL_STATUS_REJECTED,
    PROPOSAL_STATUS_EXPIRED,
)

#: Estados que siguen esperando al productor.
PROPOSAL_PENDING_STATUSES: tuple[str, ...] = (PROPOSAL_STATUS_PROPOSED,)


@dataclass(frozen=True, slots=True)
class EstudioDailyProposal:
    """Foto inmutable de una propuesta diaria con identidad durable."""

    id: str
    account_id: str
    day: str
    instrument_id: str
    status: str = PROPOSAL_STATUS_PROPOSED
    symbol: str | None = None
    #: Identidad DURABLE del plan (``TradePlan.decisionId``). ``None`` si no la declara.
    decision_id: str | None = None
    #: Identidad estable de la señal que originó el plan (``signal.id``).
    signal_id: str | None = None
    strategy_definition_id: str | None = None
    strategy_version: int | None = None
    preset_key: str | None = None
    #: Día de la VELA que alimentó la propuesta (``asOfBarDate``). Es la frescura real.
    bar_date: str | None = None
    #: ``TradePlan`` tal cual lo publicó el parte (geometría incluida).
    plan: dict[str, Any] = field(default_factory=dict)
    #: Ciclo durable que la adoptó (``None`` mientras no se consuma).
    consumed_cycle_id: str | None = None
    consumed_at: str | None = None
    #: Motivo declarado del rechazo/caducidad (``None`` si no aplica).
    reason: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def is_pending(self) -> bool:
        return self.status in PROPOSAL_PENDING_STATUSES

    @property
    def degraded_reasons(self) -> tuple[str, ...]:
        """D-2 — motivos por los que el PARTE quedó ``partial`` (dentro del plan).

        La marca vive en el JSON del plan (``plan.degradedReasons``) porque la tabla no
        tiene columna propia: no se rellena un hueco con una migración solo para declarar
        una degradación. Un plan antiguo (sin la clave) devuelve ``()``, que es "no
        declarado", nunca "sano".
        """
        raw = (self.plan or {}).get("degradedReasons")
        if not isinstance(raw, (list, tuple)):
            return ()
        seen: dict[str, None] = {}
        for item in raw:
            text = str(item or "").strip()
            if text:
                seen.setdefault(text, None)
        return tuple(seen)
