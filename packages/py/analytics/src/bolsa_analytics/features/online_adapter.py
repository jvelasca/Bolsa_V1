"""OnlineFeatureAdapter — envuelve FeatureCache / memoria (RFC-005 migración paso 2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_analytics.features.catalog import FeatureCatalog, bootstrap_catalog
from bolsa_analytics.features.models import FeatureSnapshot
from bolsa_analytics.signals.feature_cache import (
    FeatureCache,
    InMemoryFeatureCache,
    hash_indicator_specs,
)


class OnlineFeatureAdapter:
    """
    Adapter online que implementa IFeaturePort.

    - `put_snapshot` / `get_latest`: store en proceso (y opcionalmente cache).
    - `get_as_of`: PIT mínima — solo snapshots con timestamp <= as_of.
    - `feature_cache` se expone para materializar series vía hash P8 (sin reescribir indicadores).
    """

    def __init__(
        self,
        *,
        catalog: FeatureCatalog | None = None,
        cache: FeatureCache | None = None,
    ) -> None:
        self._catalog = catalog or bootstrap_catalog()
        self._cache = cache or InMemoryFeatureCache()
        self._latest: dict[tuple[str, str], FeatureSnapshot] = {}
        self._history: list[FeatureSnapshot] = []

    @property
    def catalog(self) -> FeatureCatalog:
        return self._catalog

    @property
    def feature_cache(self) -> FeatureCache:
        return self._cache

    def specs_hash_for_set(self, feature_set_id: str) -> str:
        specs = self._catalog.indicator_specs_for_set(feature_set_id)
        return hash_indicator_specs(specs)

    def put_snapshot(self, snap: FeatureSnapshot) -> None:
        key = (snap.instrument_id, snap.feature_set_id)
        self._latest[key] = snap
        self._history.append(snap)

    def get_latest(
        self,
        instrument_id: str,
        feature_set_id: str,
    ) -> FeatureSnapshot | None:
        return self._latest.get((instrument_id, feature_set_id))

    def get_as_of(
        self,
        instrument_id: str,
        feature_set_id: str,
        as_of: datetime,
        *,
        tolerance_seconds: int = 0,
    ) -> FeatureSnapshot | None:
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)
        candidates = [
            snap
            for snap in self._history
            if snap.instrument_id == instrument_id
            and snap.feature_set_id == feature_set_id
            and snap.timestamp <= as_of
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda s: s.timestamp)
        if tolerance_seconds > 0:
            delta = (as_of - best.timestamp).total_seconds()
            if delta > tolerance_seconds:
                return None
        return best

    def get_as_of_many(
        self,
        instrument_ids: list[str],
        feature_set_id: str,
        timestamps: list[datetime],
        *,
        tolerance_seconds: int = 0,
    ) -> list[FeatureSnapshot]:
        out: list[FeatureSnapshot] = []
        for instrument_id, ts in zip(instrument_ids, timestamps, strict=False):
            snap = self.get_as_of(
                instrument_id,
                feature_set_id,
                ts,
                tolerance_seconds=tolerance_seconds,
            )
            if snap is not None:
                out.append(snap)
        return out

    def materialize_latest_from_values(
        self,
        *,
        instrument_id: str,
        feature_set_id: str,
        values: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> FeatureSnapshot:
        feature_set = self._catalog.get_set(feature_set_id)
        snap = FeatureSnapshot(
            instrument_id=instrument_id,
            timestamp=timestamp or datetime.now(UTC),
            feature_set_id=feature_set_id,
            composition_hash=feature_set.composition_hash,
            values=values,
        )
        self.put_snapshot(snap)
        return snap
