"""Feature Registry skeleton (RFC-005) — IFeaturePort + catalog bootstrap."""

from bolsa_analytics.features.catalog import FeatureCatalog, bootstrap_catalog
from bolsa_analytics.features.compute_bridge import (
    compute_feature_set_values,
    compute_feature_value,
    materialize_feature_snapshot,
)
from bolsa_analytics.features.models import FeatureDef, FeatureSet, FeatureSnapshot, composition_hash
from bolsa_analytics.features.online_adapter import OnlineFeatureAdapter
from bolsa_analytics.features.ports import IFeaturePort

__all__ = [
    "FeatureCatalog",
    "FeatureDef",
    "FeatureSet",
    "FeatureSnapshot",
    "IFeaturePort",
    "OnlineFeatureAdapter",
    "bootstrap_catalog",
    "composition_hash",
    "compute_feature_set_values",
    "compute_feature_value",
    "materialize_feature_snapshot",
]
