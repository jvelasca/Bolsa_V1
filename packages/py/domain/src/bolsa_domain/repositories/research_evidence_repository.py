from typing import Any, Protocol

from bolsa_domain.entities.research_evidence import ResearchEvidence


class ResearchEvidenceRepository(Protocol):
    async def insert_evidence(
        self,
        *,
        instrument_id: str,
        level: str,
        source: str,
        evidence_weight: float,
        summary: dict[str, Any],
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        edge_report_id: str | None = None,
        math_version: str | None = None,
        evidence_id: str | None = None,
    ) -> ResearchEvidence: ...

    async def get_by_id(self, evidence_id: str) -> ResearchEvidence | None: ...

    async def list_evidence(
        self,
        *,
        instrument_id: str | None = None,
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchEvidence], int]: ...
