from pydantic import BaseModel, ConfigDict, Field


class DeployPaperAccountRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    initial_deposit: float | None = Field(default=None, alias="initialDeposit")
    account_name: str | None = Field(default=None, alias="accountName")
    source_backtest_run_id: str | None = Field(default=None, alias="sourceBacktestRunId")
    lab_evidence: dict | None = Field(default=None, alias="labEvidence")
