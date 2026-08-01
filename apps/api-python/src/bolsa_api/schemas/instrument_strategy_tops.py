"""Schemas: InstrumentStrategyTop (TOP-3 AT por valor)."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InstrumentStrategyTopSlotDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    rank: Literal[1, 2, 3]
    label: str
    strategy_type: str | None = Field(default=None, alias="strategyType")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    stars: float
    score: float
    stars_capped: bool | None = Field(default=None, alias="starsCapped")
    run_id: str | None = Field(default=None, alias="runId")
    source: Literal["coach", "user", "optimized"] = "coach"
    total_return_pct: float | None = Field(default=None, alias="totalReturnPct")
    excess_return_pct: float | None = Field(default=None, alias="excessReturnPct")
    max_drawdown_pct: float | None = Field(default=None, alias="maxDrawdownPct")
    late_return_pct: float | None = Field(default=None, alias="lateReturnPct")


class InstrumentStrategyTopDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    artifact_type: str = Field(default="ART-INSTRUMENT-TOP", alias="artifactType")
    schema_version: str = Field(default="1.0.0", alias="schemaVersion")
    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str | None = None
    timeframe: str
    period_label: str | None = Field(default=None, alias="periodLabel")
    status: Literal["draft", "semifinal", "active"]
    version: int
    evidence_level: Literal["in_sample_only", "lab_validated"] = Field(alias="evidenceLevel")
    slots: list[InstrumentStrategyTopSlotDto]
    coach_headline: str | None = Field(default=None, alias="coachHeadline")
    coach_facts: dict[str, Any] | None = Field(default=None, alias="coachFacts")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class InstrumentStrategyTopResponseDto(BaseModel):
    data: InstrumentStrategyTopDto | None


class InstrumentStrategyTopsListResponseDto(BaseModel):
    data: list[InstrumentStrategyTopDto]


class QueryInstrumentStrategyTopsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_ids: list[str] = Field(alias="instrumentIds", min_length=1, max_length=200)
    timeframe: str = "1d"


class UpsertInstrumentStrategyTopDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    symbol: str | None = None
    timeframe: str = "1d"
    period_label: str | None = Field(default=None, alias="periodLabel")
    status: Literal["draft", "semifinal", "active"] = "semifinal"
    evidence_level: Literal["in_sample_only", "lab_validated"] = Field(
        default="in_sample_only", alias="evidenceLevel"
    )
    slots: list[InstrumentStrategyTopSlotDto] = Field(min_length=1, max_length=3)
    coach_headline: str | None = Field(default=None, alias="coachHeadline")
    coach_facts: dict[str, Any] | None = Field(default=None, alias="coachFacts")

    @model_validator(mode="after")
    def require_run_ids_for_lab_or_active(self) -> Self:
        """Checklist Camino A: lab_validated / active exige runId en todos los slots."""
        if self.evidence_level != "lab_validated" and self.status != "active":
            return self
        missing = [
            s.rank
            for s in self.slots
            if not (isinstance(s.run_id, str) and s.run_id.strip())
        ]
        if missing:
            raise ValueError(
                "lab_validated/active TOP requires runId on every slot; "
                f"missing ranks {missing}"
            )
        return self
