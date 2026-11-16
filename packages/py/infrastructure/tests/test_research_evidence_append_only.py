"""R7 — Evidence es append-only también en la API del repositorio.

La convención («Evidence append-only; Belief mutable») no puede depender de que
nadie llame a un ``update``: si el repositorio no expone mutación, el único
camino es insertar una fila nueva. Este test **fija** ese contrato:

* la entidad de dominio es inmutable (``frozen``): rebindear un campo falla;
* el repositorio público solo ofrece insertar y leer —sin ``update``,
  ``delete``, ``upsert`` ni ``merge``—;
* el módulo no importa las sentencias mutables de SQLAlchemy;
* ``insert_evidence`` no acepta un modo de conflicto que pudiera sobrescribir.

Si mañana se necesita corregir una evidencia, se inserta otra con su
procedencia; nunca se reescribe la anterior.

@see docs/engineering/research-lifecycle.md (tabla `research_evidence`)
@see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §8 (R7)
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

from bolsa_domain.entities.research_evidence import ResearchEvidence
from bolsa_infrastructure.database.repositories.research_evidence_repository import (
    SqlAlchemyResearchEvidenceRepository,
)

_FORBIDDEN_METHODS = (
    "update",
    "update_evidence",
    "delete",
    "delete_evidence",
    "upsert",
    "merge",
    "replace",
    "save",
)


def _evidence() -> ResearchEvidence:
    return ResearchEvidence(
        id="ev-1",
        instrument_id="inst-1",
        level="B",
        source="holdout",
        evidence_weight=0.8,
        summary={"oosScore": 3.2},
        created_at="2026-11-16T10:00:00+00:00",
        trial_id="trial-1",
    )


def test_entity_is_immutable() -> None:
    evidence = _evidence()
    with pytest.raises(FrozenInstanceError):
        evidence.evidence_weight = 0.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evidence.summary = {}  # type: ignore[misc]


def test_repository_public_surface_is_append_and_read_only() -> None:
    public = {
        name
        for name, member in inspect.getmembers(
            SqlAlchemyResearchEvidenceRepository,
            predicate=callable,
        )
        if not name.startswith("_")
    }

    assert public == {"insert_evidence", "get_by_id", "list_evidence"}, (
        "El repositorio de Evidence debe limitarse a insertar y leer; "
        f"métodos públicos encontrados: {sorted(public)}"
    )
    for forbidden in _FORBIDDEN_METHODS:
        assert forbidden not in public


def test_repository_module_does_not_import_mutating_statements() -> None:
    module = inspect.getmodule(SqlAlchemyResearchEvidenceRepository)
    assert module is not None
    source = inspect.getsource(module)

    assert "sqlalchemy import update" not in source
    assert "sqlalchemy import delete" not in source
    assert "from sqlalchemy import update, delete" not in source


def test_insert_evidence_has_no_conflict_mode() -> None:
    parameters = inspect.signature(SqlAlchemyResearchEvidenceRepository.insert_evidence).parameters

    assert "on_conflict" not in parameters
    assert "on_conflict_do_update" not in parameters
    assert "merge" not in parameters
    # El identificador es opcional solo para poder reproducir un recibo; nunca
    # para reescribir una fila existente (la PK duplicada debe fallar).
    assert "evidence_id" in parameters
