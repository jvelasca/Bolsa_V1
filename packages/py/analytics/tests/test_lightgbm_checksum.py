"""F5 — LightGBM/numpy direction model: SHA256 checksum before pickle load."""

from __future__ import annotations

import pytest

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.prediction.lightgbm_direction import (
    predict_direction,
    train_direction_model,
)


def _synth_bars(n: int = 120) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []
    price = 100.0
    for i in range(n):
        price = price * (1.0 + (0.002 if i % 3 else -0.0015))
        bars.append(
            OhlcvBar(
                timestamp=f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
                open=price * 0.99,
                high=price * 1.01,
                low=price * 0.98,
                close=price,
                volume=1_000_000,
            )
        )
    return bars


def test_load_binary_rejects_checksum_mismatch() -> None:
    bars = _synth_bars(150)
    model = train_direction_model(bars)
    assert model.binary is not None
    tampered = model.model_checksum[:-1] + ("0" if model.model_checksum[-1] != "0" else "1")
    bad = type(model)(
        model_id=model.model_id,
        model_version=model.model_version,
        framework=model.framework,
        feature_set_id=model.feature_set_id,
        composition_hash=model.composition_hash,
        target_name=model.target_name,
        target_type=model.target_type,
        model_checksum=tampered,
        metrics=model.metrics,
        hyperparameters=model.hyperparameters,
        trained_at=model.trained_at,
        binary=model.binary,
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        predict_direction(bad, bars, instrument_id="inst-1")


def test_load_binary_rejects_tampered_pickle_bytes() -> None:
    bars = _synth_bars(150)
    model = train_direction_model(bars)
    assert model.binary is not None
    corrupted = bytearray(model.binary)
    corrupted[0] ^= 0xFF
    bad = type(model)(
        model_id=model.model_id,
        model_version=model.model_version,
        framework=model.framework,
        feature_set_id=model.feature_set_id,
        composition_hash=model.composition_hash,
        target_name=model.target_name,
        target_type=model.target_type,
        model_checksum=model.model_checksum,
        metrics=model.metrics,
        hyperparameters=model.hyperparameters,
        trained_at=model.trained_at,
        binary=bytes(corrupted),
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        predict_direction(bad, bars, instrument_id="inst-1")
