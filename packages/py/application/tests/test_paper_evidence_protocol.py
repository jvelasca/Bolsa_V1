"""Frente B — protocolo longitudinal PAPER: snapshot durable + serie pura.

Certifica (y una mutación debe poder romper):

* La identidad del snapshot es ``(cuenta, día)``: determinista e idempotente por día.
* El ``verdict`` del snapshot es SIEMPRE el literal reservado ``NO_CONFIRMED`` (nunca promueve).
* Sin cuenta atribuible no se finge un snapshot (``None``).
* La serie se ordena (más antigua → más nueva) e ignora filas que no son snapshots.

Módulo puro: sin I/O, sin reloj real, sin PostgreSQL.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from bolsa_application.paper_evidence_protocol import (
    PAPER_EVIDENCE_SNAPSHOT_EVENT,
    PAPER_VERDICT_NO_CONFIRMED,
    build_paper_evidence_snapshot_entry,
    paper_evidence_series,
)


def _evidence(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "paper-evidence/1",
        "asOf": "2026-10-09T12:00:00Z",
        "metCriterionIds": ["c1", "c2"],
        "unmetCriterionIds": ["c3"],
        "unknownCriterionIds": ["c4"],
        "contradictions": [],
        "blockers": ["blocker-1"],
        "fillsWindowFull": False,
        "fillsTotalForAccount": 42,
    }
    payload.update(overrides)
    return payload


def test_snapshot_identity_is_deterministic_per_account_and_day() -> None:
    """Misma cuenta y mismo día ⇒ misma ``dedupe_key`` (idempotente); otro día, otra."""
    entry = build_paper_evidence_snapshot_entry(account_id="acc-1", evidence=_evidence())
    assert entry is not None
    assert entry.event_type == PAPER_EVIDENCE_SNAPSHOT_EVENT
    assert entry.dedupe_key == "auto_paper_evidence_snapshot:acc-1:2026-10-09"
    other_day = build_paper_evidence_snapshot_entry(
        account_id="acc-1", evidence=_evidence(asOf="2026-10-10T00:00:00Z")
    )
    assert other_day is not None
    assert other_day.dedupe_key != entry.dedupe_key


def test_snapshot_never_emits_confirmed() -> None:
    """El protocolo NUNCA promueve: el veredicto es el literal reservado ``NO_CONFIRMED``."""
    entry = build_paper_evidence_snapshot_entry(account_id="acc-1", evidence=_evidence())
    assert entry is not None
    assert entry.payload["verdict"] == PAPER_VERDICT_NO_CONFIRMED == "NO_CONFIRMED"


def test_snapshot_without_account_is_none() -> None:
    """Sin cuenta atribuible no se finge un snapshot (fail-closed)."""
    assert build_paper_evidence_snapshot_entry(account_id="  ", evidence=_evidence()) is None
    assert build_paper_evidence_snapshot_entry(account_id=None, evidence=_evidence()) is None


def test_series_is_sorted_and_declares_windows() -> None:
    """La serie va de más antigua a más nueva, cuenta criterios e ignora filas ajenas."""
    newer = build_paper_evidence_snapshot_entry(
        account_id="acc-1", evidence=_evidence(asOf="2026-10-10T00:00:00Z")
    )
    older = build_paper_evidence_snapshot_entry(
        account_id="acc-1", evidence=_evidence(asOf="2026-10-09T00:00:00Z")
    )
    noise = SimpleNamespace(
        id="other", event_type="auto_entry_decision", payload={"cycleId": "cyc-1"}
    )
    assert newer is not None and older is not None
    series = paper_evidence_series([newer, older, noise])
    assert [row["asOf"] for row in series] == [
        "2026-10-09T00:00:00Z",
        "2026-10-10T00:00:00Z",
    ]
    assert series[0]["metCount"] == 2
    assert series[0]["unmetCount"] == 1
    assert series[0]["unknownCount"] == 1
    assert series[0]["verdict"] == "NO_CONFIRMED"
    # La truncación se declara, no se esconde.
    assert series[0]["fillsWindowFull"] is False
    assert series[0]["fillsTotalForAccount"] == 42
