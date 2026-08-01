import type { InvestmentAccountDto, PaperLabEvidenceSnapshot } from './accounts.js';

export interface DeployPaperAccountRequestDto {
  /** Capital inicial; si se omite, 10 000 o el del backtest fuente. */
  initialDeposit?: number;
  accountName?: string;
  /** Provenance opcional desde un run concreto. */
  sourceBacktestRunId?: string;
  /**
   * Optional lab snapshot from Optimizar stash/checklist (P7).
   * Server prefers research_trials.blocks when present; this fills the gap after adopt.
   */
  labEvidence?: PaperLabEvidenceSnapshot | null;
}

export interface DeployPaperAccountResponseDto {
  data: InvestmentAccountDto;
}
