"""V2.44 — frescura POR DIMENSIÓN: stale ⇒ no entry, salida protectora permitida.

El contrato que muerden estos tests:

* ``market_data`` no fresca (``stale`` **o** ``unknown``) ⇒ ``blocks_new_entry``.
* Las demás dimensiones NO bloquean la apertura por sí solas (degradan el
  dimensionamiento, que ya es fail-closed río abajo).
* Un instante no interpretable es ``unknown``, nunca ``0`` (que fabricaría un stale).
* El veredicto se publica como veto de APERTURAS, jamás como un halt: la casa reconcilia
  vetando aperturas, nunca una salida que reduce riesgo.
"""

from __future__ import annotations

from bolsa_analytics.cognitive.data_freshness import (
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    FreshnessPolicy,
    assess_data_freshness,
    dimension_freshness,
)


def test_fresh_market_data_allows_entry() -> None:
    assessment = assess_data_freshness(now=1000.0, market_data_at=1000.0)
    assert assessment.dimension("market_data").status == FRESHNESS_FRESH
    assert assessment.market_data_stale is False
    assert assessment.blocks_new_entry is False
    assert assessment.data_freshness == FRESHNESS_FRESH


def test_stale_market_data_blocks_new_entry() -> None:
    assessment = assess_data_freshness(
        now=1000.0,
        market_data_at=1000.0 - 301.0,
        policy=FreshnessPolicy(max_market_data_age_s=300.0),
    )
    assert assessment.dimension("market_data").status == FRESHNESS_STALE
    assert assessment.market_data_stale is True
    assert assessment.blocks_new_entry is True
    # La etiqueta del snapshot NO puede publicar "fresh" cuando el veto está activo.
    assert assessment.data_freshness == FRESHNESS_STALE


def test_unknown_market_data_is_not_fresh() -> None:
    """Sin dato de mercado el eje es ``unknown``: no se abre contra lo que no se fecha."""
    assessment = assess_data_freshness(now=1000.0, market_data_at=None)
    assert assessment.dimension("market_data").status == FRESHNESS_UNKNOWN
    assert assessment.market_data_stale is False  # ``unknown`` no es ``stale``...
    assert assessment.blocks_new_entry is True  # ...pero veta igual.
    assert assessment.data_freshness == FRESHNESS_STALE


def test_stale_atr_does_not_block_entry_by_itself() -> None:
    """Una dimensión NO-mercado vieja degrada el tamaño, no congela la apertura."""
    assessment = assess_data_freshness(
        now=10_000.0,
        market_data_at=10_000.0,
        atr_at=0.0,
        policy=FreshnessPolicy(max_atr_age_s=3600.0),
    )
    assert assessment.dimension("atr").status == FRESHNESS_STALE
    assert assessment.blocks_new_entry is False


def test_unparseable_timestamp_is_unknown_not_epoch_zero() -> None:
    """``0`` sería "muy viejo" y fabricaría un stale; no interpretable ⇒ ``unknown``."""
    reading = dimension_freshness("market_data", "not-a-date", now=1000.0, max_age_seconds=300.0)
    assert reading.last_at is None
    assert reading.age_seconds is None
    assert reading.status == FRESHNESS_UNKNOWN


def test_iso_timestamp_is_normalized() -> None:
    reading = dimension_freshness(
        "quote", "2026-09-19T09:00:00Z", now=1_789_000_000.0, max_age_seconds=None
    )
    assert reading.status == FRESHNESS_FRESH
    assert reading.last_at is not None


def test_none_threshold_does_not_declare_stale() -> None:
    """``None`` = "no se mide aquí", no "libre": sigue ``fresh`` si hay dato."""
    reading = dimension_freshness("volume", 10.0, now=1_000_000.0, max_age_seconds=None)
    assert reading.status == FRESHNESS_FRESH


def test_policy_rejects_negative_thresholds() -> None:
    import pytest

    with pytest.raises(ValueError):
        FreshnessPolicy(max_market_data_age_s=-1.0)
