"""Topes de lote backend ↔ frontend (contrato compartido).

El frontend trocea con `packages/shared/src/batch-limits.ts`. Si un tope cambia
aquí, hay que cambiarlo allí (y viceversa): estos tests fijan el contrato.

Verificado en esta sesión: 201 ids → 422 en quotes y en dictámenes diarios.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bolsa_api.schemas.composite_card import QueryInstrumentCompositeDto
from bolsa_api.schemas.instrument_daily_opinions import (
    QueryInstrumentDailyOpinionsDto,
    RunEstudioEodOpinionBatchDto,
)
from bolsa_api.schemas.instruments import InstrumentQuotesRequestDto

QUOTES_LIMIT = 200
DAILY_OPINIONS_LIMIT = 200
COMPOSITE_LIMIT = 40


def _ids(count: int) -> list[str]:
    return [f"id-{index}" for index in range(count)]


def test_quotes_accepts_limit_and_rejects_limit_plus_one() -> None:
    InstrumentQuotesRequestDto(ids=_ids(QUOTES_LIMIT))

    with pytest.raises(ValidationError):
        InstrumentQuotesRequestDto(ids=_ids(QUOTES_LIMIT + 1))


def test_quotes_requires_at_least_one_id() -> None:
    with pytest.raises(ValidationError):
        InstrumentQuotesRequestDto(ids=[])


def test_daily_opinions_accepts_limit_and_rejects_limit_plus_one() -> None:
    QueryInstrumentDailyOpinionsDto(instrumentIds=_ids(DAILY_OPINIONS_LIMIT))

    with pytest.raises(ValidationError):
        QueryInstrumentDailyOpinionsDto(
            instrumentIds=_ids(DAILY_OPINIONS_LIMIT + 1)
        )


def test_estudio_eod_batch_shares_daily_opinions_cap() -> None:
    RunEstudioEodOpinionBatchDto(instrumentIds=_ids(DAILY_OPINIONS_LIMIT))

    with pytest.raises(ValidationError):
        RunEstudioEodOpinionBatchDto(instrumentIds=_ids(DAILY_OPINIONS_LIMIT + 1))


def test_composite_keeps_its_own_smaller_cap() -> None:
    QueryInstrumentCompositeDto(instrumentIds=_ids(COMPOSITE_LIMIT))

    with pytest.raises(ValidationError):
        QueryInstrumentCompositeDto(instrumentIds=_ids(COMPOSITE_LIMIT + 1))
