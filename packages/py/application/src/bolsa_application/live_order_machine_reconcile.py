"""Reconcile de la máquina ``live_orders`` vs broker-truth (H7).

Detect/report **drift**, nunca auto-heal (fail-closed, coherente con LR-1 y con la
cadena honesta: no se fabrica CANCELLED/FILLED del venue por aquí). Consulta las
órdenes **abiertas** (SUBMITTED/WORKING/PARTIAL/CANCEL_REQUESTED que ya tienen
``venue_order_id``; las UNKNOWN ya se intentan resolver en el poll del recovery
worker) y las contrasta con el estado reportado por ``GET /orders/{id}``.

No escribe en el store. Produce un report por fila con diferencias observadas y
un estado sugerido (sin aplicarlo). El operador/otra capa decide la acción.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from bolsa_application.live_order_query import BrokerOrderQueryResult

# Estados de la máquina "abiertos" candidatos a reconciliar (tienen
# venue_order_id y un life-cycle susceptible de divergir del broker).
_OPEN_CANDIDATE = {"SUBMITTED", "WORKING", "PARTIAL", "CANCEL_REQUESTED"}


@dataclass(frozen=True, slots=True)
class LiveOrderDrift:
    """Una divergencia observada entre la máquina y el estado del venue."""

    order_id: str
    account_id: str
    venue_order_id: str
    machine_state: str
    broker_state: str | None
    kind: str  # 'cancel_broker_side' | 'fill_unseen' | 'state_mismatch' | 'query_unavailable'
    suggested: str | None  # estado objetivo sugerido (sin auto-aplicar)
    broker_filled: Decimal | None = None
    broker_remaining: Decimal | None = None
    reason: str | None = None


@dataclass
class LiveOrderMachineReconcileReport:
    """Resumen mutable (fácil de acumular) del reconcile de la máquina."""

    checked: int = 0
    drifts: list[LiveOrderDrift] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for d in self.drifts:
            kinds[d.kind] = kinds.get(d.kind, 0) + 1
        return {
            "checked": self.checked,
            "drifts": len(self.drifts),
            "kinds": kinds,
        }


def _row_id(order: Any) -> str:
    return getattr(order, "order_id", "") or ""


def _row_account(order: Any) -> str:
    return getattr(order, "account_id", "") or ""


async def reconcile_live_order_machine(
    store: Any,
    *,
    query_provider: Any,
    limit: int = 50,
) -> LiveOrderMachineReconcileReport:
    """Compara open live_orders con broker-truth y devuelve drift (no muta).

    ``store`` ha de exponer ``list_open_orders``. ``query_provider`` es el mismo
    shape del recovery de UNKNOWN: ``(venue, account_id, venue_order_id)`` →
    de vuelve un query port o None (fila sin query → drift ``query_unavailable``).
    """
    report = LiveOrderMachineReconcileReport()

    list_open = getattr(store, "list_open_orders", None)
    if list_open is None:
        return report  # sin list_open → nada que reconciliar

    open_orders = await list_open(limit=limit)
    for order in open_orders:
        status = (getattr(order, "status", "") or "").upper()
        if status not in _OPEN_CANDIDATE:
            continue
        venue = (getattr(order, "venue", "") or "").upper()
        venue_order_id = (getattr(order, "venue_order_id", "") or "").strip()
        account_id = _row_account(order)
        if not venue_order_id:
            continue  # sin id de venue no es reconciliable contra el broker
        order_id = _row_id(order)

        query = None
        if query_provider is not None:
            try:
                query = await query_provider(venue, account_id, venue_order_id)
            except Exception:
                query = None
        if query is None:
            report.checked += 1
            report.drifts.append(
                LiveOrderDrift(
                    order_id=order_id,
                    account_id=account_id,
                    venue_order_id=venue_order_id,
                    machine_state=status,
                    broker_state=None,
                    kind="query_unavailable",
                    suggested=None,
                    reason="no_query_provider_or_error",
                )
            )
            continue

        result: BrokerOrderQueryResult | None = None
        try:
            result = await query.query_broker_order(venue_order_id=venue_order_id)
        except Exception:
            result = None
        report.checked += 1
        if result is None or result.outcome == "unavailable":
            report.drifts.append(
                LiveOrderDrift(
                    order_id=order_id,
                    account_id=account_id,
                    venue_order_id=venue_order_id,
                    machine_state=status,
                    broker_state=None,
                    kind="query_unavailable",
                    suggested=None,
                    reason=result.reason if result else "query_error",
                )
            )
            continue

        broker_state = result.outcome  # working|partial|filled|rejected|cancelled
        live_status = result.to_live_status()  # máquina canonical or None

        # 1) El venue confirmó cancel; la máquina local aún no lo ve (intención
        #    local por resolver → encaja en H5: solo confirm broker hace CANCELLED).
        if live_status == "CANCELLED" and status != "CANCELLED":
            report.drifts.append(
                LiveOrderDrift(
                    order_id=order_id,
                    account_id=account_id,
                    venue_order_id=venue_order_id,
                    machine_state=status,
                    broker_state=broker_state,
                    suggested="CANCEL_REQUESTED",
                    kind="cancel_broker_side",
                    reason="venue_confirmed_cancelled",
                )
            )
            continue
        # 2) El venue llenó (parcial/completo) y la máquina sigue sin reflejarlo.
        if live_status in {"PARTIAL", "FILLED"} and status not in {"PARTIAL", "FILLED"}:
            report.drifts.append(
                LiveOrderDrift(
                    order_id=order_id,
                    account_id=account_id,
                    venue_order_id=venue_order_id,
                    machine_state=status,
                    broker_state=broker_state,
                    suggested=live_status,
                    kind="fill_unseen",
                    broker_filled=result.filled_quantity,
                    broker_remaining=result.remaining_quantity,
                    reason="venue_reports_fill_not_seen_locally",
                )
            )
            continue
        # 3) Cualquier otro desajuste de grado/estado entre venue y máquina.
        if live_status is not None and live_status != status:
            report.drifts.append(
                LiveOrderDrift(
                    order_id=order_id,
                    account_id=account_id,
                    venue_order_id=venue_order_id,
                    machine_state=status,
                    broker_state=broker_state,
                    suggested=live_status,
                    kind="state_mismatch",
                    reason="venue_state_differs_from_local_machine",
                )
            )

    return report
