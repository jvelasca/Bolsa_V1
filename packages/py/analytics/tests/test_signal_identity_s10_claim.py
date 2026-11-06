"""S10 (auditoría .183) — la identidad de señal es un CLAIM, no un ``Optional`` ignorable.

El hallazgo: ``build_signal_identity`` devuelve ``None`` cuando falta un campo, y un llamador
podía seguir adelante con ese ``None``. Ahí la señal no se deduplicaba (se re-emitía en cada
turno sobre la misma barra), no se podía auditar ni reproducir — y el silencio del ``None``
lo hacía indistinguible de "señal nueva".

Lo que se fija aquí: ``claim_signal_id``/``claim_signal_for_bar`` NUNCA devuelven ``None``.
O hay identidad reclamada, o hay un motivo del vocabulario. Y un ``SignalClaim`` a medias
(sin id y sin motivo, o con ambos) no se puede ni construir.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_analytics.cognitive.signal_identity import (
    SIGNAL_DUPLICATE,
    SIGNAL_IDENTITY_MISSING,
    SIGNAL_STALE,
    SignalClaim,
    claim_signal_for_bar,
    claim_signal_id,
)

SIGNAL_ID = "AAA\x1fver-1\x1f1d\x1f2026-11-05T00:00:00+00:00\x1fabc123"
MOMENT = datetime(2026, 11, 5, 12, 30, tzinfo=UTC)


def test_claim_of_an_identity_returns_the_id_and_no_reason() -> None:
    claim = claim_signal_id(SIGNAL_ID)

    assert claim.is_claimed is True
    assert claim.signal_id == SIGNAL_ID
    assert claim.reason == ""


def test_a_missing_identity_is_refused_not_ignored() -> None:
    for empty in (None, "", "   "):
        claim = claim_signal_id(empty)

        assert claim.is_claimed is False
        assert claim.reason == SIGNAL_IDENTITY_MISSING


def test_an_already_consumed_signal_is_a_duplicate() -> None:
    claim = claim_signal_id(SIGNAL_ID, consumed={SIGNAL_ID})

    assert claim.is_claimed is False
    assert claim.reason == SIGNAL_DUPLICATE


def test_an_expired_signal_is_stale() -> None:
    claim = claim_signal_id(
        SIGNAL_ID,
        valid_until="2026-11-05T00:00:00+00:00",
        as_of="2026-11-06T00:00:00+00:00",
    )

    assert claim.is_claimed is False
    assert claim.reason == SIGNAL_STALE


def test_an_unexpired_signal_is_claimed() -> None:
    claim = claim_signal_id(
        SIGNAL_ID,
        valid_until="2026-11-06T00:00:00+00:00",
        as_of="2026-11-05T10:00:00+00:00",
    )

    assert claim.is_claimed is True


def test_duplicate_wins_over_stale_because_it_is_checked_first_in_the_journal() -> None:
    """El orden del vocabulario es el del journal: sin id, duplicada, caducada."""
    claim = claim_signal_id(
        SIGNAL_ID,
        valid_until="2026-01-01T00:00:00+00:00",
        as_of="2026-11-05T00:00:00+00:00",
        consumed={SIGNAL_ID},
    )

    assert claim.reason == SIGNAL_DUPLICATE


def test_claim_for_bar_builds_the_identity_of_the_bar_that_contains_the_moment() -> None:
    claim = claim_signal_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="ver-1",
        timeframe="1d",
        moment=MOMENT,
    )

    assert claim.is_claimed is True
    assert claim.identity is not None
    assert claim.identity.bar_timestamp == "2026-11-05T00:00:00+00:00"
    assert claim.identity.valid_until == "2026-11-06T00:00:00+00:00"
    assert claim.signal_id == claim.identity.signal_id


def test_claim_for_bar_refuses_a_naive_clock_instead_of_inventing_a_window() -> None:
    claim = claim_signal_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="ver-1",
        timeframe="1d",
        moment=datetime(2026, 11, 5, 12, 30),  # sin tzinfo
    )

    assert claim.is_claimed is False
    assert claim.reason == SIGNAL_IDENTITY_MISSING


def test_claim_for_bar_refuses_an_unreadable_timeframe_or_a_missing_moment() -> None:
    assert (
        claim_signal_for_bar(
            instrument_id="AAA",
            action="BUY",
            strategy_version="ver-1",
            timeframe="1w",  # no soportado: no se adivina la duración
            moment=MOMENT,
        ).reason
        == SIGNAL_IDENTITY_MISSING
    )
    assert (
        claim_signal_for_bar(
            instrument_id="AAA",
            action="BUY",
            strategy_version="ver-1",
            timeframe="1d",
            moment=None,
        ).reason
        == SIGNAL_IDENTITY_MISSING
    )


def test_claim_for_bar_keeps_the_identity_when_the_bar_was_already_consumed() -> None:
    first = claim_signal_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="ver-1",
        timeframe="1d",
        moment=MOMENT,
    )
    assert first.identity is not None

    second = claim_signal_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="ver-1",
        timeframe="1d",
        moment=MOMENT,
        consumed={first.signal_id},
    )

    # El motivo viaja CON la identidad: el journal puede publicar ambos (qué se descartó y
    # por qué) sin tener que reconstruirla.
    assert second.is_claimed is False
    assert second.reason == SIGNAL_DUPLICATE
    assert second.identity is not None
    assert second.identity.signal_id == first.signal_id


def test_a_half_built_claim_cannot_exist() -> None:
    with pytest.raises(ValueError):
        SignalClaim()
    with pytest.raises(ValueError):
        SignalClaim(signal_id="abc", reason=SIGNAL_DUPLICATE)
