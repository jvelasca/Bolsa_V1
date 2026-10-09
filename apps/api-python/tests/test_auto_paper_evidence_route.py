"""PAPER-2 — DTO del endpoint ``/auto/paper-evidence`` (hermético, sin PG).

Certifica que el DTO de respuesta **valida** el payload del lector y que el fail-closed sin cuenta
no emite la confirmación: todos los criterios quedan ``unknown`` (``UNKNOWN ≠ 0``) y el token
reservado no aparece suelto.
"""

from __future__ import annotations

import json
import re

from bolsa_api.api.v1.routes.auto_paper_evidence import AutoPaperEvidenceDto
from bolsa_application.paper_evidence_reader import empty_paper_evidence


def test_no_account_scope_is_a_valid_dto_with_all_criteria_unknown() -> None:
    payload = empty_paper_evidence("", ["orb-1"], note="no_account_scope")
    dto = AutoPaperEvidenceDto(**payload)

    assert dto.verdict == "NO_CONFIRMED"
    assert dto.readOnly is True
    assert dto.notes[0] == "no_account_scope"
    assert {item.status for item in dto.criteria} == {"unknown"}
    assert dto.metCriterionIds == []
    assert dto.fillsWindowFull is False
    assert dto.fillsTotalForAccount is None
    # El token reservado no aparece suelto (frontera de palabra): ``NO_CONFIRMED`` no lo es.
    assert re.search(r"\bCONFIRMED\b", json.dumps(payload)) is None


def test_dto_keeps_nullable_counts_as_none_and_never_zero() -> None:
    payload = empty_paper_evidence("acc-1")
    dto = AutoPaperEvidenceDto(**payload)

    window = next(item for item in dto.criteria if item.id == "window")
    assert window.status == "unknown"
    assert window.counts["days"] is None
    assert window.counts["episodes"] is None
