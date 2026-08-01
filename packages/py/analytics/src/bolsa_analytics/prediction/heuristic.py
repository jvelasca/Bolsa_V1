"""Prediction heurística — envuelve technical_rating_v1 como ART-PREDICTION."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from bolsa_analytics.features.models import FeatureSnapshot
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.prediction.models import ModelArtifact, Prediction, new_prediction_id
from bolsa_analytics.signals.technical_rating_v1 import (
    MODEL_ID,
    TECHNICAL_RATING_V1_VERSION,
    compute_technical_rating_v1,
)

_HEURISTIC_CHECKSUM = hashlib.sha256(
    f"{MODEL_ID}:{TECHNICAL_RATING_V1_VERSION}".encode()
).hexdigest()


def heuristic_model_artifact(*, feature_set_id: str = "fset_core_v1", composition_hash: str = "heuristic") -> ModelArtifact:
    return ModelArtifact(
        model_id=MODEL_ID,
        model_version=TECHNICAL_RATING_V1_VERSION,
        framework="heuristic",
        feature_set_id=feature_set_id,
        composition_hash=composition_hash,
        target_name="technical_score",
        target_type="continuous",
        model_checksum=_HEURISTIC_CHECKSUM,
        metrics={},
        hyperparameters={"source": "technical_rating_v1"},
        trained_at=None,
        binary=None,
    )


def prediction_from_technical_rating(
    bars: list[OhlcvBar],
    *,
    instrument_id: str,
    snapshot: FeatureSnapshot | None = None,
    horizon: str = "1d",
) -> Prediction | None:
    rating = compute_technical_rating_v1(bars)
    if rating is None:
        return None
    # total 0–100 → value [-1,+1]
    value = round((float(rating.total) - 50.0) / 50.0, 4)
    conf = min(1.0, abs(value) * 0.6 + 0.25)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    fs_id = snapshot.feature_set_id if snapshot else "fset_core_v1"
    comp = snapshot.composition_hash if snapshot else "ohlcv_direct"
    return Prediction(
        prediction_id=new_prediction_id(),
        instrument_id=instrument_id,
        model_id=MODEL_ID,
        model_version=TECHNICAL_RATING_V1_VERSION,
        model_checksum=_HEURISTIC_CHECKSUM,
        feature_set_id=fs_id,
        composition_hash=comp,
        timestamp=now,
        as_of=now,
        horizon=horizon,
        value=value,
        confidence=round(conf, 3),
        feature_snapshot_id=None,
        probabilities=None,
    )
