"""PAPER-2 — lector read-only de la evidencia durable PAPER (I/O del adaptador).

Este módulo es el único punto con I/O del adaptador PAPER. Lee, **solo con ``SELECT``**, las
fuentes durables autorizadas —``sim_fill_finance_context`` (fills), el spine
``decision_journal_entries`` (cierres ``auto_cycle_settlement``) y el agregado por versión del
store— y las entrega al adaptador puro (``paper_evidence_adapter``). No escribe nada, no toca el
motor de decisión, no habilita ninguna promoción.

Regla dura: una lectura que falla se **declara** (``fills_loaded``/``settlements_loaded`` +
``notes``); jamás se convierte en un material limpio. Una ventana truncada por el ``limit`` se
declara; no se presenta como el universo completo. Y lo que no se puede leer (fills sin
``cycle_id``, fuera del alcance de las fuentes por ciclo) se cuenta y se declara, no se esconde.

Aislamiento por cuenta (PAPER-2.1): un cierre durable **sin cuenta atribuible** (``account_id``
nulo o vacío) NO se incorpora al ámbito de la cuenta consultada. Se cuenta y se declara como
``unattributed_settlements_excluded``; jamás se lee como evidencia de esta cuenta. Un cierre de
OTRA cuenta tampoco entra.

@see packages/py/application/src/bolsa_application/paper_evidence_adapter.py
@see apps/api-python/src/bolsa_api/api/v1/routes/auto_paper_evidence.py
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_application.auto_cycle_journal import cycle_decision_id
from bolsa_application.auto_operational_monitor import AUTO_CYCLE_SETTLEMENT_EVENT
from bolsa_application.paper_evidence_adapter import (
    PaperEvidenceInput,
    build_paper_evidence,
)
from bolsa_application.paper_evidence_reconciliation import reconcile_paper_evidence

__all__ = [
    "DEFAULT_PAPER_EVIDENCE_CYCLE_LIMIT",
    "DEFAULT_PAPER_EVIDENCE_FILL_LIMIT",
    "empty_paper_evidence",
    "read_paper_evidence",
]

logger = logging.getLogger(__name__)

#: Tope declarado de ciclos recientes a enumerar. Truncar la ventana se declara, nunca se finge.
DEFAULT_PAPER_EVIDENCE_CYCLE_LIMIT = 500
#: Tope declarado de fills a leer (``list_by_cycle_ids``).
DEFAULT_PAPER_EVIDENCE_FILL_LIMIT = 5000

#: Notas de procedencia que el lector añade al DTO (todas declaran un hueco o una cota).
NOTE_FILLS_NOT_LOADED = "fills_not_loaded"
NOTE_SETTLEMENTS_NOT_LOADED = "settlements_not_loaded"
NOTE_FILLS_WINDOW_TRUNCATED = "fills_window_truncated"
NOTE_UNATTRIBUTED_FILLS = "unattributed_fills_present"
#: Cierres durables EXCLUIDOS por no declarar una cuenta atribuible al ámbito consultado.
NOTE_UNATTRIBUTED_SETTLEMENTS = "unattributed_settlements_excluded"


def _payload_of(entry: Any) -> Mapping[str, Any]:
    payload = getattr(entry, "payload", None)
    if payload is None and isinstance(entry, Mapping):
        payload = entry.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _cycle_of(fill: Any) -> str:
    value = getattr(fill, "cycle_id", None)
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


async def read_paper_evidence(
    session: Any,
    account_id: str,
    *,
    versions: Sequence[str] | None = None,
    cycle_limit: int = DEFAULT_PAPER_EVIDENCE_CYCLE_LIMIT,
    fill_limit: int = DEFAULT_PAPER_EVIDENCE_FILL_LIMIT,
    as_of: str | None = None,
) -> dict[str, Any]:
    """(I/O, READ-ONLY) lee el material PAPER durable y compone el DTO de evidencia.

    El alcance es la cuenta: los fills salen de ``list_by_cycle_ids``/``count_by_strategy_version``
    acotados por ``account_id`` y los cierres se buscan por el ``decision_id`` **derivado del
    ciclo** de esos mismos fills (nunca por ``payload->>'cycleId'``). Sin cuenta legible el
    llamante debe resolver el scope antes (fail-closed ``no_account_scope``).
    """
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    context_store = PostgresSimFillFinanceContextStore(session, autocommit=False)
    repository = SqlAlchemyJournalRepository(session)

    notes: list[str] = []
    fills: list[Any] = []
    fills_loaded = True
    fills_window_full = True
    total_for_account: int | None = None
    known_versions: list[str] = []

    try:
        cycle_ids = await context_store.list_recent_cycle_ids(
            account_id, limit=max(1, int(cycle_limit))
        )
        fills = await context_store.list_by_cycle_ids(
            account_id, cycle_ids, limit=max(1, int(fill_limit))
        )
        counts = await context_store.count_by_strategy_version(account_id=account_id)
        total_for_account = sum(int(value) for value in counts.values())
        known_versions = sorted(
            str(key) for key in counts if key is not None and str(key).strip()
        )
        if counts.get(None, 0) > 0:
            # Fills sin atribución de estrategia: no se leen por ciclo, se DECLARAN.
            notes.append(NOTE_UNATTRIBUTED_FILLS)
        # La ventana queda truncada si cualquiera de los dos topes se alcanzó.
        fills_window_full = (
            len(fills) < max(1, int(fill_limit)) and len(cycle_ids) < max(1, int(cycle_limit))
        )
    except Exception:  # noqa: BLE001 — sin lectura el hueco se DECLARA, no se finge material.
        logger.warning("paper evidence: durable fills unavailable", exc_info=True)
        fills_loaded = False
        fills = []
        notes.append(NOTE_FILLS_NOT_LOADED)

    settlements: list[dict[str, Any]] = []
    settlements_loaded = True
    unattributed_settlements = 0
    try:
        settlement_cycle_ids = sorted({_cycle_of(fill) for fill in fills} - {""})
        decision_ids = [
            decision for decision in (cycle_decision_id(cid) for cid in settlement_cycle_ids) if decision
        ]
        entries = (
            await repository.list_by_decision_ids(decision_ids) if decision_ids else []
        )
        for entry in entries:
            if getattr(entry, "event_type", None) != AUTO_CYCLE_SETTLEMENT_EVENT:
                continue
            entry_account = getattr(entry, "account_id", None)
            if entry_account is None or not str(entry_account).strip():
                # Cierre sin cuenta atribuible: NO se incorpora al ámbito consultado (fail-closed).
                # Se cuenta y se declara; jamás se lee como evidencia de esta cuenta.
                unattributed_settlements += 1
                continue
            if str(entry_account) != account_id:
                # Cierre de OTRA cuenta: no entra (una fila de otra cuenta no casa nunca).
                continue
            payload = dict(_payload_of(entry))
            if payload:
                settlements.append(payload)
    except Exception:  # noqa: BLE001 — un fallo de lectura de cierres se declara.
        logger.warning("paper evidence: durable settlements unavailable", exc_info=True)
        settlements_loaded = False
        settlements = []
        notes.append(NOTE_SETTLEMENTS_NOT_LOADED)
    if unattributed_settlements and settlements_loaded:
        notes.append(NOTE_UNATTRIBUTED_SETTLEMENTS)

    if not fills_window_full:
        notes.append(NOTE_FILLS_WINDOW_TRUNCATED)

    reconciliation = reconcile_paper_evidence(
        fills=fills,
        settlements=settlements,
        fills_loaded=fills_loaded,
        settlements_loaded=settlements_loaded,
        unattributed_settlements=(unattributed_settlements if settlements_loaded else 0),
    )

    requested = [str(v) for v in (versions or []) if str(v).strip()] or known_versions
    dto = build_paper_evidence(
        PaperEvidenceInput(
            account_id=account_id,
            requested_versions=requested,
            reconciliation=reconciliation,
            as_of=as_of,
        )
    )
    dto["fillsWindowFull"] = fills_window_full
    dto["fillsTotalForAccount"] = total_for_account
    dto["notes"] = [*dto.get("blockers", []), *notes]
    return dto


def empty_paper_evidence(
    account_id: str,
    versions: Sequence[str] | None = None,
    *,
    note: str = "no_account_scope",
) -> dict[str, Any]:
    """(PURA) DTO de evidencia SIN material, con la cuenta declarada y el motivo del hueco.

    Es el fail-closed del endpoint: sin cuenta operativa visible no se lee **nada** y todos los
    criterios quedan ``unknown`` (``UNKNOWN ≠ 0``), con el veredicto reservado ``NO_CONFIRMED``.
    """
    reconciliation = reconcile_paper_evidence(
        fills=[],
        settlements=[],
        fills_loaded=False,
        settlements_loaded=False,
    )
    dto = build_paper_evidence(
        PaperEvidenceInput(
            account_id=account_id,
            requested_versions=[str(v) for v in (versions or []) if str(v).strip()],
            reconciliation=reconciliation,
            as_of=None,
        )
    )
    dto["fillsWindowFull"] = False
    dto["fillsTotalForAccount"] = None
    dto["notes"] = [note, *dto.get("blockers", [])]
    return dto
