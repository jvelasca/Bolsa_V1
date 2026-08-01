export type InvestmentAccountType = 'simulated' | 'paper' | 'live';

/**
 * Premisa producto (2026-07-31):
 * - `simulated` = **Demo** — único tipo operativo hoy (cuenta activa).
 * - `paper` = reservado a **broker real futuro** (API operador); NO es paper-trading simulado.
 * - `live` = reservado producción estricta (detalle al cablear brokers).
 * @see docs/engineering/account-premises-demo-vs-paper-2026-07-31.md
 */
export type InvestmentAccountStatus = 'active' | 'suspended' | 'closed';

/** Compact lab validation stamped at deploy (P7). Hoy: cuenta activa DEMO. */
export type PaperLabEvidenceSnapshot = {
  kind: 'none' | 'holdout' | 'walkforward' | 'cpcv';
  oosScore?: number | null;
  meanOosScore?: number | null;
  oosReturnPct?: number | null;
  nFolds?: number | null;
  pathCount?: number | null;
  walkForwardEfficiency?: number | null;
  oosCv?: number | null;
  positiveOosFoldShare?: number | null;
  wfeSource?: string | null;
  credibility?: number | null;
  edgeBand?: string | null;
  monteCarloPValue?: number | null;
  dsr?: number | null;
  pbo?: number | null;
  persistedEdgeReportId?: string | null;
  trialId?: string | null;
  sourceBacktestRunId?: string | null;
  note?: string | null;
};

export type LedgerEntryType =
  | 'deposit'
  | 'withdrawal'
  | 'buy'
  | 'sell'
  | 'fee'
  | 'dividend'
  | 'adjustment';

export interface InvestmentAccountDto {
  id: string;
  userId: string | null;
  name: string;
  description: string | null;
  type: InvestmentAccountType;
  status: InvestmentAccountStatus;
  currency: string;
  baseCurrency: string;
  initialDeposit: number;
  leverage: number;
  marginCallLevelPct: number | null;
  isDefault: boolean;
  settings: import('./account-settings.js').AccountSettings | null;
  /** Perfil inversor activo (catálogo ART-PROFILE). */
  activeProfileId?: string | null;
  /** BT-7 — estrategia vinculada (cuentas paper). */
  strategyDefinitionId?: string | null;
  sourceBacktestRunId?: string | null;
  /** P7 — snapshot lab al desplegar (settings_json.labEvidence). Provenance, not prod gate. */
  labEvidence?: PaperLabEvidenceSnapshot | null;
  createdAt: string;
  updatedAt: string;
  lastActivityAt: string | null;
}

export interface InvestmentPortfolioDto {
  id: string;
  accountId: string;
  legacyPortfolioId: string | null;
  name: string;
  description: string | null;
  strategyTag: string | null;
  sortOrder: number;
  isDefault: boolean;
}

export interface AccountSummaryDto {
  account: InvestmentAccountDto;
  defaultPortfolio: InvestmentPortfolioDto;
  cash: number;
  totalMarketValue: number;
  totalCost: number;
  totalUnrealizedPnl: number;
  totalEquity: number;
  marginUsed: number;
  freeMargin: number;
  marginLevelPct: number | null;
  positionsCount: number;
}

export interface LedgerEntryDto {
  id: string;
  accountId: string;
  portfolioId: string | null;
  type: LedgerEntryType;
  amount: number;
  currency: string;
  balanceAfter: number;
  instrumentId: string | null;
  symbol: string | null;
  quantity: number | null;
  price: number | null;
  referenceType: string | null;
  referenceId: string | null;
  description: string | null;
  executedAt: string;
}

export interface UpdateInvestmentAccountRequestDto {
  name?: string;
  description?: string | null;
}

/** Perfil a crear y asignar en el mismo POST /accounts (asistente Nueva demo). */
export interface CreateAccountInvestorProfileDto {
  name?: string | null;
  horizon: import('./cognitive/investor-profile.js').ProfileHorizon;
  objectives?: string[];
  riskTolerance: import('./cognitive/investor-profile.js').RiskTolerance;
  experience: import('./cognitive/investor-profile.js').ExperienceLevel;
  maxAcceptableLossPct?: number | null;
  notes?: string | null;
  suggestedPolicyTemplateId?: string | null;
  selectedPolicyTemplateId?: string | null;
}

export interface CreateInvestmentAccountRequestDto {
  name: string;
  description?: string | null;
  currency?: string;
  baseCurrency?: string;
  initialDeposit?: number;
  leverage?: number;
  marginCallLevelPct?: number | null;
  portfolioName?: string;
  portfolioDescription?: string | null;
  strategyTag?: string | null;
  settings?: import('./account-settings.js').AccountSettings;
  commissionPresetId?: import('./account-settings.js').CommissionPresetId;
  /**
   * Asignar un perfil del catálogo. Si se omite y tampoco hay `investorProfile`,
   * el API crea un perfil moderate por defecto.
   */
  activeProfileId?: string | null;
  /** Crear un perfil nuevo y asignarlo (prioridad sobre activeProfileId). */
  investorProfile?: CreateAccountInvestorProfileDto | null;
}
