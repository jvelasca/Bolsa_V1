"""Catálogo bootstrap ART-FEATURE-DEF (RFC-005) — ≥10 features base.

Relación Feature → Indicator: `indicator_id` = IND-* (dueño Feature Registry).
`parity_ref` puede ser IND-* o id legacy; compute_bridge resuelve a chart id.
"""

from __future__ import annotations

from bolsa_analytics.features.models import FeatureDef, FeatureSet, composition_hash_from_defs


def bootstrap_feature_defs() -> tuple[FeatureDef, ...]:
    """Core Production set — instancias parametrizadas de IndicatorUniverse."""
    return (
        FeatureDef(
            feature_id="feat_sma_20_close",
            version="1.0.0",
            feature_key="sma_20_close",
            compute_key="sma",
            params={"period": 20, "source": "close"},
            indicator_id="IND-SMA",
            parity_ref="IND-SMA",
        ),
        FeatureDef(
            feature_id="feat_sma_50_close",
            version="1.0.0",
            feature_key="sma_50_close",
            compute_key="sma",
            params={"period": 50, "source": "close"},
            indicator_id="IND-SMA",
            parity_ref="IND-SMA",
        ),
        FeatureDef(
            feature_id="feat_ema_12_close",
            version="1.0.0",
            feature_key="ema_12_close",
            compute_key="ema",
            params={"period": 12, "source": "close"},
            indicator_id="IND-EMA",
            parity_ref="IND-EMA",
        ),
        FeatureDef(
            feature_id="feat_ema_26_close",
            version="1.0.0",
            feature_key="ema_26_close",
            compute_key="ema",
            params={"period": 26, "source": "close"},
            indicator_id="IND-EMA",
            parity_ref="IND-EMA",
        ),
        FeatureDef(
            feature_id="feat_wma_20_close",
            version="1.0.0",
            feature_key="wma_20_close",
            compute_key="wma",
            params={"period": 20, "source": "close"},
            indicator_id="IND-LWMA",
            parity_ref="IND-LWMA",
        ),
        FeatureDef(
            feature_id="feat_rsi_14_close",
            version="1.0.0",
            feature_key="rsi_14_close",
            compute_key="rsi",
            params={"period": 14, "source": "close"},
            indicator_id="IND-RSI",
            parity_ref="IND-RSI",
        ),
        FeatureDef(
            feature_id="feat_atr_14",
            version="1.0.0",
            feature_key="atr_14",
            compute_key="atr",
            params={"period": 14},
            indicator_id="IND-ATR",
            parity_ref="IND-ATR",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_cci_20",
            version="1.0.0",
            feature_key="cci_20",
            compute_key="cci",
            params={"period": 20},
            indicator_id="IND-CCI",
            parity_ref="IND-CCI",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_stoch_14",
            version="1.0.0",
            feature_key="stoch_14",
            compute_key="stoch",
            params={"kPeriod": 14},
            indicator_id="IND-SO",
            parity_ref="IND-SO",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_macd_12_26",
            version="1.0.0",
            feature_key="macd_12_26",
            compute_key="macd",
            params={"fastPeriod": 12, "slowPeriod": 26},
            indicator_id="IND-MACD",
            parity_ref="IND-MACD",
        ),
        FeatureDef(
            feature_id="feat_bb_20_2_mid",
            version="1.0.0",
            feature_key="bb_20_2_mid",
            compute_key="bb",
            params={"period": 20, "stdDev": 2, "line": "mid"},
            indicator_id="IND-BB",
            parity_ref="IND-BB",
        ),
        FeatureDef(
            feature_id="feat_volume",
            version="1.0.0",
            feature_key="volume",
            compute_key="volume",
            params={},
            indicator_id="IND-VOL",
            parity_ref="IND-VOL",
            inputs=("ohlcv.volume",),
        ),
        # Oleada 1 — XTB alto valor / baja complejidad
        FeatureDef(
            feature_id="feat_williams_r_14",
            version="1.0.0",
            feature_key="williams_r_14",
            compute_key="willr",
            params={"period": 14},
            indicator_id="IND-WILLR",
            parity_ref="IND-WILLR",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_momentum_10_close",
            version="1.0.0",
            feature_key="momentum_10_close",
            compute_key="mom",
            params={"period": 10, "source": "close"},
            indicator_id="IND-MOM",
            parity_ref="IND-MOM",
        ),
        FeatureDef(
            feature_id="feat_std_dev_20_close",
            version="1.0.0",
            feature_key="std_dev_20_close",
            compute_key="sd",
            params={"period": 20, "source": "close"},
            indicator_id="IND-SD",
            parity_ref="IND-SD",
        ),
        FeatureDef(
            feature_id="feat_donchian_20_mid",
            version="1.0.0",
            feature_key="donchian_20_mid",
            compute_key="dc",
            params={"period": 20, "line": "mid"},
            indicator_id="IND-DC",
            parity_ref="IND-DC",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        # Oleada 2
        FeatureDef(
            feature_id="feat_adx_14",
            version="1.0.0",
            feature_key="adx_14",
            compute_key="adx",
            params={"period": 14},
            indicator_id="IND-ADX",
            parity_ref="IND-ADX",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_stoch_rsi_14",
            version="1.0.0",
            feature_key="stoch_rsi_14",
            compute_key="srsi",
            params={"rsiPeriod": 14, "stochPeriod": 14, "kPeriod": 3, "dPeriod": 3},
            indicator_id="IND-SRSI",
            parity_ref="IND-SRSI",
        ),
        FeatureDef(
            feature_id="feat_supertrend_10_3",
            version="1.0.0",
            feature_key="supertrend_10_3",
            compute_key="st",
            params={"atrPeriod": 10, "multiplier": 3},
            indicator_id="IND-ST",
            parity_ref="IND-ST",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_vwap",
            version="1.0.0",
            feature_key="vwap",
            compute_key="vwap",
            params={},
            indicator_id="IND-VWAP",
            parity_ref="IND-VWAP",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close", "ohlcv.volume"),
        ),
        # Oleada 3
        FeatureDef(
            feature_id="feat_obv",
            version="1.0.0",
            feature_key="obv",
            compute_key="obv",
            params={},
            indicator_id="IND-OBV",
            parity_ref="IND-OBV",
            inputs=("ohlcv.close", "ohlcv.volume"),
        ),
        FeatureDef(
            feature_id="feat_roc_12_close",
            version="1.0.0",
            feature_key="roc_12_close",
            compute_key="roc",
            params={"period": 12, "source": "close"},
            indicator_id="IND-ROC",
            parity_ref="IND-ROC",
        ),
        FeatureDef(
            feature_id="feat_mfi_14",
            version="1.0.0",
            feature_key="mfi_14",
            compute_key="mfi",
            params={"period": 14},
            indicator_id="IND-MFI",
            parity_ref="IND-MFI",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close", "ohlcv.volume"),
        ),
        FeatureDef(
            feature_id="feat_aroon_25_up",
            version="1.0.0",
            feature_key="aroon_25_up",
            compute_key="aroon",
            params={"period": 25, "line": "up"},
            indicator_id="IND-AROON",
            parity_ref="IND-AROON",
            inputs=("ohlcv.high", "ohlcv.low"),
        ),
        FeatureDef(
            feature_id="feat_psar",
            version="1.0.0",
            feature_key="psar",
            compute_key="sar",
            params={"step": 0.02, "maxAf": 0.2},
            indicator_id="IND-SAR",
            parity_ref="IND-SAR",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_bears_13",
            version="1.0.0",
            feature_key="bears_13",
            compute_key="bears",
            params={"period": 13},
            indicator_id="IND-BEARS",
            parity_ref="IND-BEARS",
            inputs=("ohlcv.low", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_bulls_13",
            version="1.0.0",
            feature_key="bulls_13",
            compute_key="bulls",
            params={"period": 13},
            indicator_id="IND-BULLS",
            parity_ref="IND-BULLS",
            inputs=("ohlcv.high", "ohlcv.close"),
        ),
        FeatureDef(
            feature_id="feat_alligator_lips",
            version="1.0.0",
            feature_key="alligator_lips",
            compute_key="ali",
            params={"line": "lips"},
            indicator_id="IND-ALI",
            parity_ref="IND-ALI",
            inputs=("ohlcv.high", "ohlcv.low"),
        ),
        FeatureDef(
            feature_id="feat_ichimoku_tenkan",
            version="1.0.0",
            feature_key="ichimoku_tenkan",
            compute_key="ich",
            params={"tenkanPeriod": 9, "kijunPeriod": 26, "senkouBPeriod": 52, "displacement": 26, "line": "tenkan"},
            indicator_id="IND-ICH",
            parity_ref="IND-ICH",
            inputs=("ohlcv.high", "ohlcv.low", "ohlcv.close"),
        ),
    )


class FeatureCatalog:
    def __init__(self, defs: tuple[FeatureDef, ...] | None = None) -> None:
        self._defs = {d.feature_id: d for d in (defs or bootstrap_feature_defs())}
        self._by_key = {d.feature_key: d for d in self._defs.values()}
        self._sets: dict[str, FeatureSet] = {}
        self._register_default_set()

    def _register_default_set(self) -> None:
        defs = list(self._defs.values())
        feature_set = FeatureSet(
            feature_set_id="fset_core_v1",
            version="1.0.0",
            name="Core production OHLCV features",
            members=tuple((d.feature_id, d.version) for d in defs),
            composition_hash=composition_hash_from_defs(defs),
        )
        self._sets[feature_set.feature_set_id] = feature_set

    def get_def(self, feature_id: str) -> FeatureDef:
        return self._defs[feature_id]

    def get_by_key(self, feature_key: str) -> FeatureDef:
        return self._by_key[feature_key]

    def list_defs(self) -> list[FeatureDef]:
        return list(self._defs.values())

    def list_by_indicator_id(self, indicator_id: str) -> list[FeatureDef]:
        """Features cuya relación apunta a IND-* (dirección Feature → Indicator)."""
        return [
            d
            for d in self._defs.values()
            if (d.indicator_id or d.parity_ref) == indicator_id
        ]

    def get_set(self, feature_set_id: str) -> FeatureSet:
        return self._sets[feature_set_id]

    def list_sets(self) -> list[FeatureSet]:
        return list(self._sets.values())

    def specs_for_set(self, feature_set_id: str) -> list[dict]:
        feature_set = self.get_set(feature_set_id)
        return [self.get_def(fid).to_indicator_spec() for fid, _ver in feature_set.members]

    def indicator_specs_for_set(self, feature_set_id: str) -> list[dict]:
        """Alias usado por OnlineFeatureAdapter / tests P8."""
        return self.specs_for_set(feature_set_id)


def bootstrap_catalog() -> FeatureCatalog:
    return FeatureCatalog()
