"""V2.19 (A7 Iter-2 · P2-01/C3) — apply financiero del recovery, por fases GATED.

Puente real del UNKNOWN-financiero decidido para la iteración de escritura
(dec. bridge por fases idempotentes + go fail-closed OFF por defecto).

La resolución UNKNOWN (``resolve_one_unknown``) hoy persiste la máquina a
``FILLED`` sin materializar dinero (fsm_only, veto XL-3). Este módulo expone la
**decisión** (pura, sin I/O) de qué fill recuperado es materializable con un
cobro financiero *real* sin fabricar datos del broker:

* Si el broker (``BrokerOrderQueryResult``) NO acredita ``fill_seq`` + ``fill_price``
  → devuelve ``None``: la fila del recovery sigue fsm_only intacta (cero dinero
  inventado; firewall H4/H6). Un fill sin precio NO se abre en Position/Ledger.
* Si SÍ los aporta → se construye un ``ExecutionEvent`` candidato con identidad
  financiera ``execution_id = f"{venue_order_id}#{fill_seq}"``.

La **materialización** durable (captura → APPLYING → APPLIED/FAILED/RETRY,
idempotente por ``execution_id``) y la idempotencia financiera real de
Position/Ledger por ``idempotency_key`` (``ExecuteTrade`` M4) viven en capas
existentes; aquí solo se decide y se construye el ``apply_finance`` que
las une bajo go. Este Apply no se llama por defecto: el worker/path lo invoca
solo cuando ``LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED`` está activo
(default OFF), de modo que sin go el runtime sigue exacto a V2.18.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from bolsa_application.execution_event import ExecutionEvent
from bolsa_application.live_order_query import BrokerOrderQueryResult

RecoveryFinancialDecision = Literal[
    "not_fill",  # target no era un fill materializable (no filled/partial).
    "price_unknown",  # fill confirmado pero SIN precio acreditado → fsm_only.
    "not_recoverable_here",  # sin venue/order id constatable → seguro fsm_only.
    "apply_candidate",  # llenado real con secuencia+precio → candidato materializable.
]


def venue_order_id_of(order: object) -> str | None:
    vid = getattr(order, "venue_order_id", None)
    return str(vid).strip() if isinstance(vid, str) and vid.strip() else None


def recovery_financial_decision(
    order: object,
    result: BrokerOrderQueryResult,
) -> RecoveryFinancialDecision:
    """(PURA) qué vertiente aplica para el resultado de query del recovery.

    Reglas (fail-closed, sin fabricar fill/precio):
    * Solo outcomes FILLED/partial (que iluminaron una transición legal a fill)
      pueden materializar; el resto jamás.
    * Requiere ``venue_order_id`` constatable (identidad del venue).
    * Requiere ``fill_seq`` + ``fill_price`` acreditados por el broker. Si falta
      cualquiera → ``price_unknown`` (NO se materializa; fsm_only intacto).
    """
    outcome = str(getattr(result, "outcome", "") or "").strip().upper()
    locked_targets = {"FILLED", "PARTIAL"}
    if outcome not in locked_targets:
        return "not_fill"

    vid = venue_order_id_of(order)
    if vid is None:
        vid_from_result = getattr(result, "venue_order_id", None)
        if not (isinstance(vid_from_result, str) and vid_from_result.strip()):
            return "not_recoverable_here"

    seq = getattr(result, "fill_seq", None)
    price_obj = getattr(result, "fill_price", None)
    if seq is None or price_obj is None:
        return "price_unknown"
    return "apply_candidate"


def build_recovery_execution_candidate(
    order: object,
    result: BrokerOrderQueryResult,
) -> ExecutionEvent | None:
    """Construye el ExecutionEvent candidato SOLO si es apply_candidate (o None).

    La cantidad a aplicar es la del *delta* que el recovery detecta como fill:
    ``filled_quantity`` del resultado (el recovery la persiste en el order SÍ ya
    reconcilia en la máquina). Se usa la propia qty del resultado (real del
    bridge), no una invención del recovery. account_id = el del order LIVE.
    """
    if recovery_financial_decision(order, result) != "apply_candidate":
        return None
    vid = venue_order_id_of(order)
    if vid is None:
        vid_from_result = getattr(result, "venue_order_id", None)
        if isinstance(vid_from_result, str) and vid_from_result.strip():
            vid = vid_from_result.strip()
        else:
            return None

    def _s(x: object) -> str:
        return str(x).strip() if x is not None else ""

    fill_qty = _to_event_qty(result.filled_quantity)
    if fill_qty <= 0:
        return None
    oid = _s(getattr(order, "order_id", None)) or "recovery"
    venue = _s(getattr(order, "venue", None)).upper() or "LIVE"
    account_id = _s(getattr(order, "account_id", None)) or None
    seq = result.fill_seq
    if seq is None:  # mypy no ve la garantía de "apply_candidate"; guard explícito.
        return None
    return ExecutionEvent(
        execution_id=f"{vid}#{result.fill_seq}",
        order_id=oid,
        venue=venue,
        qty=fill_qty,
        account_id=account_id,
        venue_order_id=vid,
        fill_seq=int(seq),
    )


def _to_event_qty(qty: object) -> Decimal:
    """Decimal(6dp) >=0; parsea los DTO wire sin arrastrar float bestial."""
    from decimal import ROUND_HALF_UP

    if qty is None:
        return Decimal("0")
    try:
        d = Decimal(str(qty))
    except Exception:  # noqa: BLE001
        return Decimal("0")
    if d.is_nan() or d <= 0:
        return Decimal("0")
    return d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def recovery_idempotency_key(execution_id: str) -> str:
    """Key estable para la transacción financiera (no-doble M4 por ExecuteTrade).

    Viene de la identidad financiera del fill; 16-128 chars, sin whitespace.
    """
    import re

    slug = re.sub(r"[^A-Za-z0-9_]", "-", (execution_id or "").strip())
    slug = slug.strip("-")
    if not slug:
        slug = "unknown"
    return f"recovery-fin-{slug[:100]}"[-128:]
