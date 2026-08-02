"""Direction model — LightGBM si está instalado; si no, numpy_fallback (tests/CI)."""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from bolsa_analytics.features.models import FeatureSnapshot
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.prediction.models import ModelArtifact, Prediction, new_prediction_id

MODEL_ID = "lgbm_direction_v1"
MODEL_VERSION = "1.0.0"
FEATURE_KEYS = ("ret_1", "ret_5", "ret_10", "vol_10", "range_pct", "close_z")


def lightgbm_available() -> bool:
    try:
        import lightgbm  # noqa: F401

        return True
    except ImportError:
        return False


def _feature_row(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, i: int) -> np.ndarray:
    c = closes[i]
    ret_1 = (closes[i] / closes[i - 1] - 1.0) if i >= 1 and closes[i - 1] else 0.0
    ret_5 = (closes[i] / closes[i - 5] - 1.0) if i >= 5 and closes[i - 5] else 0.0
    ret_10 = (closes[i] / closes[i - 10] - 1.0) if i >= 10 and closes[i - 10] else 0.0
    window = closes[max(0, i - 9) : i + 1]
    vol_10 = float(np.std(np.diff(window) / window[:-1])) if len(window) > 2 else 0.0
    hi = highs[i]
    lo = lows[i]
    range_pct = float((hi - lo) / c) if c else 0.0
    mean = float(np.mean(window))
    std = float(np.std(window)) or 1.0
    close_z = float((c - mean) / std)
    return np.array([ret_1, ret_5, ret_10, vol_10, range_pct, close_z], dtype=np.float64)


def build_training_matrix(bars: list[OhlcvBar], *, min_rows: int = 40) -> tuple[np.ndarray, np.ndarray]:
    closes = np.array([float(b.close) for b in bars], dtype=np.float64)
    highs = np.array([float(b.high) for b in bars], dtype=np.float64)
    lows = np.array([float(b.low) for b in bars], dtype=np.float64)
    xs: list[np.ndarray] = []
    ys: list[int] = []
    for i in range(15, len(bars) - 1):
        xs.append(_feature_row(closes, highs, lows, i))
        ys.append(1 if closes[i + 1] > closes[i] else 0)
    if len(xs) < min_rows:
        raise ValueError(f"Insuficientes filas para entrenar ({len(xs)} < {min_rows})")
    return np.vstack(xs), np.array(ys, dtype=np.int32)


@dataclass
class _NumpyFallbackModel:
    """Logistic-like pesos por correlación de features con y (sin sklearn/lgbm)."""

    weights: np.ndarray
    bias: float

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        logits = x @ self.weights + self.bias
        p = 1.0 / (1.0 + np.exp(-np.clip(logits, -20, 20)))
        return np.column_stack([1.0 - p, p])


def _train_numpy_fallback(x: np.ndarray, y: np.ndarray) -> _NumpyFallbackModel:
    # Estandarizar
    mu = x.mean(axis=0)
    sigma = x.std(axis=0)
    sigma = np.where(sigma < 1e-9, 1.0, sigma)
    xz = (x - mu) / sigma
    # Pesos = correlación feature↔y
    yz = (y - y.mean()) / (y.std() or 1.0)
    weights = np.array([(xz[:, j] * yz).mean() for j in range(xz.shape[1])], dtype=np.float64)
    bias = float(np.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6)))
    # Empaquetar mu/sigma en weights extendidos vía objeto
    model = _NumpyFallbackModel(weights=weights / (np.linalg.norm(weights) + 1e-9), bias=bias)
    model.mu = mu  # type: ignore[attr-defined]
    model.sigma = sigma  # type: ignore[attr-defined]
    return model


def _predict_numpy(model: _NumpyFallbackModel, row: np.ndarray) -> float:
    mu = getattr(model, "mu", np.zeros_like(row))
    sigma = getattr(model, "sigma", np.ones_like(row))
    xz = (row - mu) / sigma
    proba = model.predict_proba(xz.reshape(1, -1))[0, 1]
    return float(proba)


def train_direction_model(
    bars: list[OhlcvBar],
    *,
    feature_set_id: str = "fset_core_v1",
    composition_hash: str = "ohlcv_derived_v1",
) -> ModelArtifact:
    x, y = build_training_matrix(bars)
    framework: str
    metrics: dict[str, float | None]
    hyper: dict[str, Any]
    binary: bytes

    if lightgbm_available():
        import lightgbm as lgb

        split = int(len(x) * 0.8)
        train = lgb.Dataset(x[:split], label=y[:split])
        valid = lgb.Dataset(x[split:], label=y[split:], reference=train)
        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "verbosity": -1,
            "num_leaves": 15,
            "learning_rate": 0.05,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.8,
            "bagging_freq": 1,
            "seed": 42,
        }
        booster = lgb.train(
            params,
            train,
            num_boost_round=80,
            valid_sets=[valid],
            callbacks=[lgb.early_stopping(10, verbose=False)],
        )
        preds = booster.predict(x[split:])
        acc = float(((preds >= 0.5).astype(int) == y[split:]).mean()) if len(y[split:]) else None
        binary = pickle.dumps({"kind": "lightgbm", "booster_str": booster.model_to_string()})
        framework = "lightgbm"
        metrics = {"accuracyHoldout": None if acc is None else round(acc, 4), "nRows": float(len(y))}
        hyper = params
    else:
        model = _train_numpy_fallback(x, y)
        split = int(len(x) * 0.8)
        preds = np.array([_predict_numpy(model, x[i]) for i in range(split, len(x))])
        acc = float(((preds >= 0.5).astype(int) == y[split:]).mean()) if len(preds) else None
        binary = pickle.dumps(
            {
                "kind": "numpy_fallback",
                "weights": model.weights.tolist(),
                "bias": model.bias,
                "mu": model.mu.tolist(),
                "sigma": model.sigma.tolist(),
            }
        )
        framework = "numpy_fallback"
        metrics = {"accuracyHoldout": None if acc is None else round(acc, 4), "nRows": float(len(y))}
        hyper = {"featureKeys": list(FEATURE_KEYS)}

    checksum = hashlib.sha256(binary).hexdigest()
    return ModelArtifact(
        model_id=MODEL_ID,
        model_version=MODEL_VERSION,
        framework=framework,  # type: ignore[arg-type]
        feature_set_id=feature_set_id,
        composition_hash=composition_hash,
        target_name="next_bar_up",
        target_type="class",
        model_checksum=checksum,
        metrics=metrics,
        hyperparameters=hyper,
        trained_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        binary=binary,
    )


def _load_binary(model: ModelArtifact) -> Any:
    if model.binary is None:
        raise ValueError("Modelo sin binary")
    return pickle.loads(model.binary)


def predict_direction(
    model: ModelArtifact,
    bars: list[OhlcvBar],
    *,
    instrument_id: str,
    snapshot: FeatureSnapshot | None = None,
    horizon: str = "1d",
) -> Prediction:
    if len(bars) < 20:
        raise ValueError("Se necesitan ≥20 barras para predecir")
    closes = np.array([float(b.close) for b in bars], dtype=np.float64)
    highs = np.array([float(b.high) for b in bars], dtype=np.float64)
    lows = np.array([float(b.low) for b in bars], dtype=np.float64)
    row = _feature_row(closes, highs, lows, len(bars) - 1)
    payload = _load_binary(model)

    if payload["kind"] == "lightgbm":
        import lightgbm as lgb

        booster = lgb.Booster(model_str=payload["booster_str"])
        p_up = float(booster.predict(row.reshape(1, -1))[0])
    else:
        nm = _NumpyFallbackModel(
            weights=np.array(payload["weights"], dtype=np.float64),
            bias=float(payload["bias"]),
        )
        nm.mu = np.array(payload["mu"], dtype=np.float64)  # type: ignore[attr-defined]
        nm.sigma = np.array(payload["sigma"], dtype=np.float64)  # type: ignore[attr-defined]
        p_up = _predict_numpy(nm, row)

    # value ∈ [-1,+1] desde P(up)
    value = round(2.0 * p_up - 1.0, 4)
    conf = round(min(1.0, abs(value) * 0.5 + 0.35), 3)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return Prediction(
        prediction_id=new_prediction_id(),
        instrument_id=instrument_id,
        model_id=model.model_id,
        model_version=model.model_version,
        model_checksum=model.model_checksum,
        feature_set_id=model.feature_set_id,
        composition_hash=model.composition_hash,
        timestamp=now,
        as_of=now,
        horizon=horizon,
        value=value,
        confidence=conf,
        feature_snapshot_id=None if snapshot is None else getattr(snapshot, "timestamp", None) and None,
        probabilities={"down": round(1.0 - p_up, 4), "up": round(p_up, 4)},
        data_version=None,
        trace_id=None,
    )


def feature_vector_debug(bars: list[OhlcvBar]) -> dict[str, float]:
    closes = np.array([float(b.close) for b in bars], dtype=np.float64)
    highs = np.array([float(b.high) for b in bars], dtype=np.float64)
    lows = np.array([float(b.low) for b in bars], dtype=np.float64)
    row = _feature_row(closes, highs, lows, len(bars) - 1)
    return {k: float(v) for k, v in zip(FEATURE_KEYS, row, strict=True)}
