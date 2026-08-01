from typing import Any, Protocol

from bolsa_domain.entities.hypothesis import Hypothesis


class HypothesisRepository(Protocol):
    async def insert(
        self,
        *,
        statement: str,
        falsifiers: list[dict[str, Any]],
        kind: str = "hypothesis",
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str = "open",
        hypothesis_id: str | None = None,
    ) -> Hypothesis: ...

    async def get_by_id(self, hypothesis_id: str) -> Hypothesis | None: ...

    async def list(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Hypothesis], int]: ...

    async def update(
        self,
        hypothesis_id: str,
        *,
        statement: str | None = None,
        falsifiers: list[dict[str, Any]] | None = None,
        kind: str | None = None,
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str | None = None,
        clear_domain: bool = False,
        clear_context: bool = False,
    ) -> Hypothesis | None: ...
