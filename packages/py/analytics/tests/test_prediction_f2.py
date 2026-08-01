"""F2 — PredictionV1 heuristic + direction model (numpy fallback / LightGBM)."""

from __future__ import annotations

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.prediction import PredictionService, lightgbm_available
from bolsa_analytics.prediction.lightgbm_direction import build_training_matrix
from bolsa_analytics.prediction.registry import InMemoryPredictionRegistry
from bolsa_analytics.signals.technical_rating_v1 import MODEL_ID as HEURISTIC_ID


def _synth_bars(n: int = 120) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []
    price = 100.0
    for i in range(n):
        # Walk aleatorio suave
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


def test_heuristic_prediction_envelope():
    svc = PredictionService(InMemoryPredictionRegistry())
    pred = svc.predict(instrument_id="inst-1", bars=_synth_bars(), model_id=HEURISTIC_ID)
    assert pred.artifact_type == "ART-PREDICTION"
    assert pred.model_id == HEURISTIC_ID
    assert pred.model_checksum
    assert -1.0 <= pred.value <= 1.0
    assert 0.0 <= pred.confidence <= 1.0
    d = pred.to_dict()
    assert d["schemaVersion"] == "1.0.0"
    assert "predictionId" in d


def test_train_and_predict_direction_fallback():
    bars = _synth_bars(150)
    x, y = build_training_matrix(bars, min_rows=40)
    assert len(x) == len(y)
    svc = PredictionService(InMemoryPredictionRegistry())
    model = svc.train_direction(bars)
    assert model.model_id == "lgbm_direction_v1"
    assert model.framework in {"lightgbm", "numpy_fallback"}
    assert model.binary is not None
    assert model.model_checksum
    pred = svc.predict(instrument_id="inst-1", bars=bars, model_id=model.model_id)
    assert pred.probabilities is not None
    assert "up" in pred.probabilities
    assert -1.0 <= pred.value <= 1.0
    models = svc.list_models()
    assert any(m.model_id == model.model_id for m in models)


def test_lightgbm_flag_is_bool():
    assert isinstance(lightgbm_available(), bool)
