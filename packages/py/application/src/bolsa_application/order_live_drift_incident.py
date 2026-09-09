"""P2-01 (E2 full V2.14) — drift durable de la máquina ``live_orders`` → incidente.

El poll del recovery worker (H7) ``reconcile_live_order_machine`` ya *detecta* y
reporta divergencias entre la máquina local y broker-truth (``LiveOrderDrift``),
pero hoy (V2.13) solo las **loguea**: no persiste nada. Este módulo convierte un
report de drift **accionable** en un incidente durable ``live_drift`` por cuenta
(ADR-035 / DEX-3), de modo que el venue quede incident-blocked para nuevas
aperturas (OR-4 ``allow_opening_fill``) mientras haya uno activo.

Honestidad mantenida:

* **No auto-heal.** Nunca cierra / muta libros / cambia la máquina. Requiere la
  cadena humana review → resolve → clear (mismo protocolo DEX-3 que
  ``sync_opening_incidents``).
* **Strict kinds** (decisión operativa): solo drifts *confirmados por broker* —
  ``cancel_broker_side`` (el venue confirmó cancel), ``fill_unseen`` (el venue
  reporta un fill que la máquina aún no ve) y ``state_mismatch`` — abren
  incidente. ``query_unavailable`` (el bridge simplemente no contestó) **no** abre
  incidente: si abriéramos por timeouts crearíamos vetos falsos de apertura.
* **Un OPEN por cuenta** y tipo: se reusa la misma semántica ``get_active`` que
  ``PostgresOperationalIncidentStore.put`` mantiene (una sola fila activa por
  ``(account_id, kind)``), así que dos workers en paralelo no duplican (P2-2).
* **El incidente vigente crece con el drift (Auditoría 2):** un OPEN por cuenta
  no significa que un subtipo posterior quede invisible. Si la cuenta ya tiene
  un ``live_drift`` y un tick entrega un drift de firma nueva (p. ej.
  ``fill_unseen`` después de un ``cancel_broker_side``), el snapshot del
  incidente activo se **amplía** (merge idempotente por firma); solo un drift
  ya registrado es replay no-op. Nunca se crea un 2º OPEN ni se auto-heal.
* **Gate ``bajo go``** vía env (default OFF, fail-closed): el wiring del worker
  no cambia el runtime de V2.13 por defecto (sigue log-only) hasta que el
  operador habilite ``LIVE_LIVE_DRIFT_DURABLE_WRITER_ENABLED``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any, Protocol, cast

from bolsa_analytics.cognitive.operational_incident import (
    OperationalIncident,
    OperationalIncidentStatus,
    open_incident,
)
from bolsa_infrastructure.ids import new_id

LIVE_DRIFT_DURABLE_WRITER_ENV = "LIVE_LIVE_DRIFT_DURABLE_WRITER_ENABLED"

# Drifts que representan la divergencia real. `query_unavailable` == el bridge no
# respondió (transitorio); no es señal de drift y no debe abrir veto.
ACTIONABLE_DRIFT_KINDS: frozenset[str] = frozenset(
    {"cancel_broker_side", "fill_unseen", "state_mismatch"}
)
_LIVE_DRIFT_KIND = "live_drift"

# Estados considerados activos (pasivo hasta clear) — igual semántica del store.
_ACTIVE: frozenset[OperationalIncidentStatus] = frozenset({"open", "in_review", "resolved"})


def live_drift_durable_writer_enabled() -> bool:
    """Gate ``bajo go`` del writer durable. Default fail-closed = False."""
    raw = (os.getenv(LIVE_DRIFT_DURABLE_WRITER_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def drift_is_actionable(drift: Any) -> bool:
    """True solo para drifts confirmados por broker (strict kinds).

    Sin import circular: recibe un ``LiveOrderDrift`` (o un shape con ``kind``).
    """
    kind = (getattr(drift, "kind", "") or "").strip()
    return kind in ACTIONABLE_DRIFT_KINDS


@dataclass
class AccountLiveDrift:
    """Aglutrado por cuenta: snapshot legible de los drifts accionables."""

    account_id: str
    drifts: tuple[Any, ...]

    def snapshot(self) -> str:
        return _snapshot_from_drifts(self.drifts)


def _drift_fields(d: Any) -> list[str]:
    """Celdas canónicas de un drift para la fila de snapshot.

    Las 3 primeras (order_id, venue_order_id, kind) son la firma canónica que
    identifica un drift (mismo order+venue+subtipo = misma divergencia). El
    resto son contexto legible para el operador.
    """
    return [
        _non_empty(getattr(d, "order_id", "")),
        _non_empty(getattr(d, "venue_order_id", "")),
        _non_empty(getattr(d, "kind", "")),
        _non_empty(getattr(d, "machine_state", "")),
        _non_empty(getattr(d, "broker_state", "")),
        _non_empty(getattr(d, "suggested", "")),
    ]


def _drift_signature(d: Any) -> str:
    """Firma canónica de un drift = (order_id, venue_order_id, kind)."""
    return "|".join(_drift_fields(d)[:3])


def _snapshot_from_drifts(drifts: tuple[Any, ...]) -> str:
    """Construye el snapshot unión de filas (sin duplicar por firma canónica)."""
    seen: set[str] = set()
    rows: list[str] = []
    for d in drifts:
        signature = _drift_signature(d)
        if signature in seen:
            continue
        seen.add(signature)
        rows.append("|".join(_drift_fields(d)))
    return f"order_live_drift:{len(rows)}:" + ";".join(rows)


def snapshot_signatures(snapshot: str | None) -> frozenset[str]:
    """Firmas (order_id,venue_order_id,kind) ya registradas en un snapshot.

    Compatible con el formato vigente: cada segmento tras el prefijo de cabecera
    es una fila cuyas 3 primeras celdas son la firma. Un snapshot vacío/ilegible
    devuelve conjunto vacío (fail-open: se re-registrará).
    """
    signatures: set[str] = set()
    for segment in _snapshot_body(snapshot).split(";"):
        segment = segment.strip()
        if not segment:
            continue
        cells = segment.split("|")
        if len(cells) >= 3:
            signatures.add("|".join(cells[:3]))
    return frozenset(signatures)


def _snapshot_body(snapshot: str | None) -> str:
    """Devuelve la parte de filas de un snapshot (tras el prefijo cabecera)."""
    if not snapshot:
        return ""
    raw = snapshot.strip()
    second_colon = raw.find(":", raw.find(":") + 1)
    return raw[second_colon + 1 :] if second_colon >= 0 else raw


def merge_account_drift_snapshot(
    *,
    current: str | None,
    drifts: tuple[Any, ...],
) -> tuple[str, bool]:
    """Fusiona drifts de una cuenta en el snapshot vigente de su incidente activo.

    Devuelve ``(nuevo_snapshot, hubo_danuevo)``. La fusión es idempotente: un
    drift cuya firma (order_id, venue_order_id, kind) **ya figura** no reescribe
    nada. Solo cuando llega un drift nuevo (p. ej. un ``fill_unseen`` que aparece
    un tick después de que la cuenta abrió un ``live_drift`` por
    ``cancel_broker_side``) se anexa la fila, de modo que el operador que revisa
    el incidente abierto SI ve la divergencia más grave recién aparecida.
    """
    registered = snapshot_signatures(current)
    rows = [s for s in _snapshot_body(current).split(";") if s.strip()]
    seen: set[str] = set(registered)
    merged_new = False
    for d in drifts:
        signature = _drift_signature(d)
        if signature in seen:
            continue
        seen.add(signature)
        rows.append("|".join(_drift_fields(d)))
        merged_new = True
    return f"order_live_drift:{len(rows)}:" + ";".join(rows), merged_new


@dataclass
class PublishOrderDriftsResult:
    """Resumen del publish (testable sin DB)."""

    accounts_with_actionable: int = 0
    opened: int = 0
    already_active: int = 0
    merged: int = 0
    skipped_unavailable: int = 0

    def summary(self) -> dict[str, int]:
        return {
            "accounts_with_actionable": self.accounts_with_actionable,
            "opened": self.opened,
            "already_active": self.already_active,
            "merged": self.merged,
            "skipped_unavailable": self.skipped_unavailable,
        }


class IncidentHolder(Protocol):
    """Puerto mínimo de persistencia usado por el publish (DEX-3 store)."""

    async def get_active(self, account_id: str, kind: str) -> OperationalIncident | None: ...

    async def put(self, incident: OperationalIncident) -> None: ...


def _non_empty(value: object) -> str:
    s = getattr(value, "strip", None)
    if callable(s):
        return cast(str, s())
    return "" if value is None else str(value)


def actionable_accounts(report: Any) -> list[AccountLiveDrift]:
    """Agrupa los drifts accionables del report por cuenta (orden estable)."""
    grouped: dict[str, list[Any]] = {}
    for d in getattr(report, "drifts", ()) or ():
        if not drift_is_actionable(d):
            continue
        aid = _non_empty(d.account_id)
        if not aid:
            continue
        grouped.setdefault(aid, []).append(d)
    return [
        AccountLiveDrift(account_id=aid, drifts=tuple(drifts)) for aid, drifts in grouped.items()
    ]


async def publish_order_live_drifts(
    report: Any,
    *,
    holder: IncidentHolder,
) -> PublishOrderDriftsResult:
    """Abre incidentes durables ``live_drift`` por cuenta y los amplía al crecer el drift.

    ``skipped_unavailable`` cuenta los drifts ``query_unavailable`` que se
    descartan (no accionables). No auto-heal y respeta un-OPEN-por-cuenta: si
    ``(account_id, live_drift)`` ya está activo no se duplica ni se sobrescribe la
    traza ya registrada del snapshot.

    Corrección Auditoría 2 (estado cerrado): cuando una cuenta ya tiene un
    ``live_drift`` activo y en un tick posterior aparece un drift **nuevo** (una
    firma order/venue/subtipo no registrada aún — p. ej. un ``fill_unseen`` que
    llega después de haberse abierto por ``cancel_broker_side``), en vez de
    descartarlo con un ``already_active`` silencioso se **anexa al snapshot** del
    incidente vigente. Así la divergencia más grave jamás queda invisible bajo
    otra; un drift idéntico repetido sigue siendo no-op (``already_active``).
    """
    result = PublishOrderDriftsResult()
    for d in getattr(report, "drifts", ()) or ():
        if _non_empty(d.kind) == "query_unavailable":
            result.skipped_unavailable += 1

    for account in actionable_accounts(report):
        result.accounts_with_actionable += 1
        existing = await holder.get_active(account.account_id, _LIVE_DRIFT_KIND)
        if existing is not None and existing.status in _ACTIVE:
            # Ya hay un live_drift abierto en la cuenta: ¿este report aporta
            # algún drift no registrado todavía? Si sí → ampliar el snapshot del
            # incidente vigente (no abrir un segundo open). Si no → replay no-op.
            merged_snapshot, has_new = merge_account_drift_snapshot(
                current=existing.snapshot,
                drifts=account.drifts,
            )
            if has_new:
                await holder.put(replace(existing, snapshot=merged_snapshot))
                result.merged += 1
            else:
                result.already_active += 1
            continue
        await holder.put(
            open_incident(
                incident_id=new_id(),
                account_id=account.account_id,
                kind=_LIVE_DRIFT_KIND,  # type: ignore[arg-type]
                snapshot=account.snapshot(),
            )
        )
        result.opened += 1
    return result
