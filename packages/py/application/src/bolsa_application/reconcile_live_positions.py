"""P1-02 (E2 full V2.14) — reconcile de POSICIÓN continuo (LR-1) en el tick del
recovery worker, bajo el MISMO go que el writer de drift de órdenes.

El detector LR-1 ``ReconcileLiveLedger`` compara posiciones/cash **broker** (live
venue) contra las **locales** (``GetPortfolioSummary``). Hoy LR-1 solo se ejecuta
en el path HTTP de apertura (al intentar operar). Este módulo lo reconcilia **de
fondo, cada tick**, para que un drift de posición (p.ej. AAPL 120 broker vs 100
local) sea visible **sin** que haya una nueva orden intentada y deje el venue
``live`` incident-blocked (OR-4 DENY) aunque nadie opere.

Honestidad mantenida (mismo espíritu que P2-01/order-drift):

* **No auto-heal** / sin cerrar incidentes aquí: solo abre si detecta
  drift/unavailable; review→resolve→clear lo hace el operador.
* Reusa piezas probadas — ``ReconcileLiveLedger`` + ``sync_opening_incidents``
  (que mapea ``live_recon_status`` → ``live_drift``/``live_unavailable`` con dedup
  1-por-(account,kind)) — para NO duplicar detector ni dedup.
* **Gate bajo go** idéntico a P2-01: sin env el worker no corre esto (fail-closed).
* **Scope venue live**: solo se reconcilia (y abre incidente) en el venue efectivo
  ``live``; cuentas/venue paper nunca comparan contra el bridge live (evita ruido).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from bolsa_application.reconciliation_opening_gate import (
    LiveReconLookup,
    ReconcileLiveLedgerLookup,
)


class LivePositionIncidentOpener(Protocol):
    """Abre incidentes durables desde el status LR-1 de una cuenta."""

    async def open_from_live_status(
        self, *, account_id: str, live_recon_status: str | None
    ) -> None: ...


@dataclass
class LivePositionReconcileResult:
    """Resumen de una pasada (testable sin DB)."""

    accounts_considered: int = 0
    drifted: int = 0
    unavailable: int = 0
    clean: int = 0
    errors: int = 0
    account_errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "accounts_considered": self.accounts_considered,
            "drifted": self.drifted,
            "unavailable": self.unavailable,
            "clean": self.clean,
            "errors": self.errors,
        }


async def reconcile_and_open_position_incidents(
    accounts: list[str],
    *,
    live_recon: ReconcileLiveLedgerLookup | LiveReconLookup,
    opener: LivePositionIncidentOpener,
) -> LivePositionReconcileResult:
    """Por cuenta activa en venue live: lee LR-1 status y (si drift) abre incidentes."""
    result = LivePositionReconcileResult()
    for raw in accounts or ():
        account_id = (raw or "").strip()
        if not account_id:
            continue
        result.accounts_considered += 1
        try:
            status = await live_recon.live_recon_status(account_id)
        except Exception:  # noqa: BLE001 — una cuenta no tumba la pasada
            result.errors += 1
            result.account_errors.append(account_id)
            continue
        await opener.open_from_live_status(account_id=account_id, live_recon_status=status)
        if status == "drift":
            result.drifted += 1
        elif status == "unavailable":
            result.unavailable += 1
        else:
            result.clean += 1
    return result


class SyncOpeningIncidentsOpener:
    """Abre desde un status LR-1 reusando ``sync_opening_incidents`` (venue live)."""

    def __init__(self, incident_store: Any) -> None:
        from bolsa_application.operational_incident_store import (
            sync_opening_incidents,
        )

        self._store = incident_store
        self._sync = sync_opening_incidents

    async def open_from_live_status(
        self, *, account_id: str, live_recon_status: str | None
    ) -> None:
        await self._sync(
            self._store,
            account_id=account_id,
            live_recon_status=live_recon_status,
            broker_venue="live",
        )
