/**
 * DTOs de la verificación DÍA-D ENLAZADA a un ciclo AUTO (P2, durable).
 *
 * El POST registra que la verificación D→hoy se lanzó DESDE un ciclo; el GET lista
 * las verificaciones del principal (opcionalmente acotadas a un `cycleId`). Las
 * claves de estrategia son `null` cuando el ciclo no las declara («Sin dato todavía»).
 */

export type DiaDCycleVerificationPersistDto = {
  cycleId: string;
  instrumentId: string;
  symbol: string;
  diaD: string;
  endDate: string;
  mode: string;
  strategyPresetKey?: string | null;
  strategyVersion?: string | null;
  strategyDefinitionId?: string | null;
  band?: string | null;
  result?: Record<string, unknown> | null;
  researchEvidenceId?: string | null;
};

export type DiaDCycleVerificationV1Dto = {
  id: string;
  cycleId: string;
  accountId: string | null;
  instrumentId: string;
  symbol: string;
  diaD: string;
  endDate: string;
  mode: string;
  createdAt: string;
  strategyPresetKey: string | null;
  strategyVersion: string | null;
  strategyDefinitionId: string | null;
  band: string | null;
  result: Record<string, unknown> | null;
  researchEvidenceId: string | null;
};

export type DiaDCycleVerificationListV1Dto = {
  data: DiaDCycleVerificationV1Dto[];
  total: number;
  notes: string[];
};
