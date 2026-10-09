"""PAPER — protocolo longitudinal (snapshots durables append-only).

El contrato PAPER (``contrato-evidencia-paper-confirmacion-2026-10-09.md``) evalúa **siete
criterios** sobre el material durable, pero esa evidencia se recalculaba **on-demand** con topes
declarados (500 ciclos / 5000 fills) y **no se acumulaba**: no había forma de observar la
*evolución* de la evidencia a lo largo del tiempo (¿los criterios se van cumpliendo?). Este módulo
cierra ese hueco con una **serie longitudinal durable**:

* ``build_paper_evidence_snapshot_entry`` — (PURA) convierte una lectura de evidencia en una fila
  append-only del spine (``decision_journal_entries``, ADR-029), con la identidad determinista del
  día (``dedupe_key``) para que reintentos no dupliquen la foto del día.
* ``paper_evidence_series`` — (PURA) reconstruye la serie ordenada (más antigua → más nueva) desde
  las filas durables.

Regla dura (no negociable por este protocolo): el ``verdict`` del snapshot es **siempre** el literal
``NO_CONFIRMED``. La promoción a ``CONFIRMED`` es una **decisión humana** (ver ADR); ningún camino
de este módulo la emite. Un snapshot sin cuenta atribuible no se finge: ``None``.

@see docs/adr/046-protocolo-longitudinal-paper.md
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

__all__ = [
    "PAPER_EVIDENCE_SNAPSHOT_EVENT",
    "PAPER_VERDICT_NO_CONFIRMED",
    "build_paper_evidence_snapshot_entry",
    "paper_evidence_series",
]

#: Evento durable del spine que representa UNA foto longitudinal de la evidencia PAPER.
PAPER_EVIDENCE_SNAPSHOT_EVENT = "auto_paper_evidence_snapshot"

#: Veredicto LITERAL reservado: el protocolo NUNCA promueve. La confirmación es humana.
PAPER_VERDICT_NO_CONFIRMED = "NO_CONFIRMED"

_DEDUPE_KEY_MAX_LENGTH = 160


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _payload_of(entry: Any) -> Mapping[str, Any]:
    payload = getattr(entry, "payload", None)
    if payload is None and isinstance(entry, Mapping):
        payload = entry.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _ids(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(value) for value in raw if str(value).strip()]


def build_paper_evidence_snapshot_entry(
    *,
    account_id: str | None,
    evidence: Mapping[str, Any],
    as_of: str | None = None,
) -> DecisionJournalEntryRecord | None:
    """(PURA) foto durable de una lectura de evidencia PAPER, o ``None`` sin cuenta.

    Copia los hechos de la lectura (identidades de criterios, contradicciones y bloqueos) **tal
    cual**, sin recalcular ni reinterpretar: el snapshot es una traza, no una segunda autoridad.
    La identidad natural es ``(cuenta, día)`` (``dedupe_key``) ⇒ una foto por cuenta y día; un
    reintento del mismo día no duplica y **no pisa** la primera foto del día (``ON CONFLICT DO
    NOTHING``).
    """
    account = str(account_id or "").strip()
    if not account:
        return None
    stamp = str(as_of or evidence.get("asOf") or _now())
    day = stamp[:10]
    payload: dict[str, Any] = {
        "event": PAPER_EVIDENCE_SNAPSHOT_EVENT,
        "accountId": account,
        "asOf": stamp,
        "schemaVersion": evidence.get("schemaVersion"),
        # Literal por contrato: este protocolo NO promueve.
        "verdict": PAPER_VERDICT_NO_CONFIRMED,
        "metCriterionIds": _ids(evidence.get("metCriterionIds")),
        "unmetCriterionIds": _ids(evidence.get("unmetCriterionIds")),
        "unknownCriterionIds": _ids(evidence.get("unknownCriterionIds")),
        "contradictions": _ids(evidence.get("contradictions")),
        "blockers": _ids(evidence.get("blockers")),
        "fillsWindowFull": bool(evidence.get("fillsWindowFull")),
        "fillsTotalForAccount": evidence.get("fillsTotalForAccount"),
    }
    dedupe = f"{PAPER_EVIDENCE_SNAPSHOT_EVENT}:{account}:{day}"[:_DEDUPE_KEY_MAX_LENGTH]
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=f"snap-{day}-{account}",
        event_type=PAPER_EVIDENCE_SNAPSHOT_EVENT,
        actor="paper-evidence-protocol",
        created_at=stamp,
        session_id=None,
        account_id=account,
        instrument_id=None,
        payload=payload,
        dedupe_key=dedupe,
    )


def paper_evidence_series(entries: Iterable[Any]) -> list[dict[str, Any]]:
    """(PURA) serie longitudinal ordenada (más antigua → más nueva) desde snapshots durables.

    Ignora cualquier fila cuyo ``event_type`` no sea el del snapshot (la lectura puede traer
    vecinos) y ordena por ``asOf`` con desempate determinista por ``decision_id``. No agrega ni
    interpreta: cada fila es la foto tal como se selló.
    """
    rows: list[dict[str, Any]] = []
    for entry in entries:
        if getattr(entry, "event_type", None) != PAPER_EVIDENCE_SNAPSHOT_EVENT:
            continue
        payload = _payload_of(entry)
        met = _ids(payload.get("metCriterionIds"))
        unmet = _ids(payload.get("unmetCriterionIds"))
        unknown = _ids(payload.get("unknownCriterionIds"))
        rows.append(
            {
                "snapshotId": getattr(entry, "id", None),
                "asOf": payload.get("asOf"),
                "verdict": payload.get("verdict") or PAPER_VERDICT_NO_CONFIRMED,
                "metCount": len(met),
                "unmetCount": len(unmet),
                "unknownCount": len(unknown),
                "metCriterionIds": met,
                "unmetCriterionIds": unmet,
                "unknownCriterionIds": unknown,
                "contradictions": _ids(payload.get("contradictions")),
                "blockers": _ids(payload.get("blockers")),
                "fillsWindowFull": bool(payload.get("fillsWindowFull")),
                "fillsTotalForAccount": payload.get("fillsTotalForAccount"),
            }
        )
    rows.sort(key=lambda row: (str(row.get("asOf") or ""), str(row.get("snapshotId") or "")))
    return rows
