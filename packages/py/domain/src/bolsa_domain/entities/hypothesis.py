from dataclasses import dataclass
from typing import Any, Literal

HypothesisKind = Literal["hypothesis", "anti"]
HypothesisStatus = Literal["open", "paused", "abandoned", "consolidated"]


@dataclass(frozen=True, slots=True)
class Hypothesis:
    id: str
    kind: HypothesisKind
    statement: str
    falsifiers: list[dict[str, Any]]
    status: HypothesisStatus
    created_at: str
    updated_at: str
    domain: str | None = None
    context: dict[str, Any] | None = None
