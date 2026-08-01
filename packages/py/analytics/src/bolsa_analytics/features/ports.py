"""IFeaturePort — consumidores STRATEGY/RUNTIME (RFC-005 §5.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from bolsa_analytics.features.models import FeatureSnapshot


class IFeaturePort(Protocol):
    def get_latest(
        self,
        instrument_id: str,
        feature_set_id: str,
    ) -> FeatureSnapshot | None: ...

    def get_as_of(
        self,
        instrument_id: str,
        feature_set_id: str,
        as_of: datetime,
        *,
        tolerance_seconds: int = 0,
    ) -> FeatureSnapshot | None: ...

    def get_as_of_many(
        self,
        instrument_ids: list[str],
        feature_set_id: str,
        timestamps: list[datetime],
        *,
        tolerance_seconds: int = 0,
    ) -> list[FeatureSnapshot]: ...
