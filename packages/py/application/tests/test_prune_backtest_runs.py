"""PruneBacktestRuns keeps newest N runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from bolsa_application.backtests import PruneBacktestRuns


@dataclass
class _FakeRepo:
    keep_args: list[int] = field(default_factory=list)

    async def prune_runs(self, keep: int) -> int:
        self.keep_args.append(keep)
        return max(0, 25 - keep)


def test_prune_clamps_keep() -> None:
    repo = _FakeRepo()
    use_case = PruneBacktestRuns(repo)  # type: ignore[arg-type]
    deleted = asyncio.run(use_case.execute(keep=20))
    assert deleted == 5
    assert repo.keep_args == [20]


def test_prune_rejects_huge_keep() -> None:
    repo = _FakeRepo()
    use_case = PruneBacktestRuns(repo)  # type: ignore[arg-type]
    asyncio.run(use_case.execute(keep=10_000))
    assert repo.keep_args == [500]
