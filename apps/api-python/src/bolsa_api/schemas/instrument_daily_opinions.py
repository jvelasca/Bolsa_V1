"""Schemas: InstrumentDailyOpinion (dictamen diario Estudio)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

StanceLiteral = Literal[
    "buy",
    "hold_watch",
    "overbought",
    "reduce",
    "sell_exit",
    "no_trade",
    "review_strategy",
]
GateLiteral = Literal["PASS", "VETO", "WARNING"]
SourceLiteral = Literal["on_demand", "eod_batch", "manual"]


class InstrumentDailyOpinionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    instrument_id: str = Field(alias="instrumentId")
    account_id: str | None = Field(default=None, alias="accountId")
    as_of_bar_date: str = Field(alias="asOfBarDate")
    stance: StanceLiteral
    dictamen_stars: int = Field(alias="dictamenStars", ge=1, le=5)
    strategy_stars: int | None = Field(default=None, alias="strategyStars")
    io_score: float | None = Field(default=None, alias="ioScore")
    fa_score: float | None = Field(default=None, alias="faScore")
    ta_score: float | None = Field(default=None, alias="taScore")
    distress: bool = False
    reasons: list[str] = Field(default_factory=list)
    gate_status: GateLiteral | None = Field(default=None, alias="gateStatus")
    top_id: str | None = Field(default=None, alias="topId")
    top_version: int | None = Field(default=None, alias="topVersion")
    source: SourceLiteral
    engine_version: str = Field(alias="engineVersion")
    idempotency_key: str = Field(alias="idempotencyKey")
    computed_at: str = Field(alias="computedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class InstrumentDailyOpinionHintDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    io_score: float | None = Field(default=None, alias="ioScore")
    fa_score: float | None = Field(default=None, alias="faScore")
    ta_score: float | None = Field(default=None, alias="taScore")
    distress: bool = False
    position_open: bool = Field(default=False, alias="positionOpen")
    allow_trading: bool = Field(default=True, alias="allowTrading")
    has_eod_bar: bool | None = Field(default=None, alias="hasEodBar")


class QueryInstrumentDailyOpinionsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_ids: list[str] = Field(alias="instrumentIds", min_length=1, max_length=200)
    as_of_bar_date: str | None = Field(default=None, alias="asOfBarDate")
    account_id: str | None = Field(default=None, alias="accountId")
    force_refresh: bool = Field(default=False, alias="forceRefresh")
    hints: list[InstrumentDailyOpinionHintDto] = Field(default_factory=list)

    @field_validator("instrument_ids")
    @classmethod
    def _non_empty_ids(cls, value: list[str]) -> list[str]:
        cleaned = [i.strip() for i in value if isinstance(i, str) and i.strip()]
        if not cleaned:
            raise ValueError("instrumentIds must not be empty")
        return cleaned


class InstrumentDailyOpinionsListResponseDto(BaseModel):
    data: list[InstrumentDailyOpinionDto]


class RunEstudioEodOpinionBatchDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_ids: list[str] = Field(alias="instrumentIds", min_length=1, max_length=200)
    as_of_bar_date: str | None = Field(default=None, alias="asOfBarDate")
    account_id: str | None = Field(default=None, alias="accountId")
    force: bool = Field(
        default=False,
        description="Si ESTUDIO_EOD_OPINION_ENABLED=false, force=true permite corrida manual.",
    )
    notify_email: str | None = Field(
        default=None,
        alias="notifyEmail",
        description="Destinatario Alarmas (prefs UI). Si null, usa ESTUDIO_OPINION_EMAIL_TO.",
    )
    notify_email_enabled: bool | None = Field(
        default=None,
        alias="notifyEmailEnabled",
        description="Si se pasa, sustituye ESTUDIO_OPINION_EMAIL_ENABLED para esta corrida.",
    )
    notify_digest_enabled: bool | None = Field(
        default=None,
        alias="notifyDigestEnabled",
        description=(
            "R3 — si true, intenta email HTML resumen operativo (requiere accountId + SMTP). "
            "Sustituye DAILY_OPS_DIGEST_EMAIL_ENABLED para esta corrida."
        ),
    )
    attach_pdf: bool | None = Field(
        default=None,
        alias="attachPdf",
        description="R4 — adjuntar PDF al digest. Sustituye DAILY_OPS_DIGEST_PDF_ENABLED.",
    )

    @field_validator("instrument_ids")
    @classmethod
    def _non_empty_ids(cls, value: list[str]) -> list[str]:
        cleaned = [i.strip() for i in value if isinstance(i, str) and i.strip()]
        if not cleaned:
            raise ValueError("instrumentIds must not be empty")
        return cleaned

    @field_validator("notify_email")
    @classmethod
    def _strip_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class EstudioEodOpinionEmailNotifyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    email_enabled: bool = Field(alias="emailEnabled")
    alarma_count: int = Field(alias="alarmaCount")
    sent: bool
    skipped_reason: str | None = Field(default=None, alias="skippedReason")


class EstudioEodDigestNotifyDto(BaseModel):
    """R3/R4 — resultado envío digest operativo tras eod-batch."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    digest_enabled: bool = Field(alias="digestEnabled")
    sent: bool
    skipped_reason: str | None = Field(default=None, alias="skippedReason")
    as_of: str | None = Field(default=None, alias="asOf")
    pdf_attached: bool = Field(default=False, alias="pdfAttached")


class EstudioEodOpinionBatchResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    enabled: bool
    forced: bool
    count: int
    data: list[InstrumentDailyOpinionDto]
    email_notify: EstudioEodOpinionEmailNotifyDto | None = Field(
        default=None, alias="emailNotify"
    )
    digest_notify: EstudioEodDigestNotifyDto | None = Field(
        default=None, alias="digestNotify"
    )


class OpinionTelemetryDto(BaseModel):
    """A0 — acierto dictamen (proxy 5d)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    schema_version: str = Field(alias="schemaVersion")
    as_of: str = Field(alias="asOf")
    lookback_days: int = Field(alias="lookbackDays")
    days_with_opinions: int = Field(alias="daysWithOpinions")
    opinion_rows: int = Field(alias="opinionRows")
    alarma_count: int = Field(alias="alarmaCount")
    alarma_buy_count: int = Field(alias="alarmaBuyCount")
    mature_buy_sample: int = Field(alias="matureBuySample")
    buy_precision_5d: float | None = Field(default=None, alias="buyPrecision5d")
    buy_hits: int = Field(alias="buyHits")
    buy_misses: int = Field(alias="buyMisses")
    buy_neutrals: int = Field(alias="buyNeutrals")
    buy_recall_5d: float | None = Field(default=None, alias="buyRecall5d")
    recall_move_sample: int = Field(alias="recallMoveSample")
    recall_caught: int = Field(alias="recallCaught")
    criteria_version: str = Field(alias="criteriaVersion")
    forward_bars: int = Field(alias="forwardBars")
    neutral_band_pct: float = Field(alias="neutralBandPct")
    caveats: list[str] = Field(default_factory=list)


class OpinionTelemetryResponseDto(BaseModel):
    data: OpinionTelemetryDto

