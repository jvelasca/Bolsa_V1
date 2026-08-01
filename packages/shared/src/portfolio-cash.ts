/**
 * Modelo canónico de efectivo y movimientos de cuenta (ADR 008, modelo XTB).
 *
 * Reglas:
 * - Cada cuenta de inversión tiene una cartera legacy interna donde vive el efectivo operativo.
 * - Depósitos/retiradas externas modifican el efectivo total (simulación: inyección/retirada de capital).
 * - El ledger es append-only; `balanceAfter` es el saldo tras el movimiento.
 */

import type { LedgerEntryType } from './accounts.js';

/** Origen semántico del movimiento (campo `referenceType`). */
export type LedgerReferenceType =
  | 'transaction'
  | 'transfer'
  | 'external'
  | 'custody'
  | 'migration'
  | 'manual';

/** Clasificación de movimiento de efectivo para UI e informes. */
export type CashMovementKind =
  | 'transfer'
  | 'external_deposit'
  | 'external_withdrawal'
  | 'trade'
  | 'fee'
  | 'custody'
  | 'initial_deposit'
  | 'other';

export interface DepositCashRequestDto {
  amount: number;
  note?: string | null;
}

export interface WithdrawCashRequestDto {
  amount: number;
  note?: string | null;
}

export interface CashMovementResultDto {
  id: string;
  accountId: string;
  portfolioId: string;
  kind: CashMovementKind;
  amount: number;
  currency: string;
  balanceAfter: number;
  executedAt: string;
  description: string | null;
}

/** Resuelve el tipo de movimiento para mostrar en UI a partir de un asiento ledger. */
export function classifyCashMovement(entry: {
  type: LedgerEntryType;
  referenceType: string | null;
  amount: number;
}): CashMovementKind {
  if (entry.referenceType === 'transfer') return 'transfer';
  if (entry.referenceType === 'external') {
    return entry.amount >= 0 ? 'external_deposit' : 'external_withdrawal';
  }
  if (entry.referenceType === 'custody') return 'custody';
  if (entry.referenceType === 'migration' || entry.referenceType === 'manual') {
    return entry.type === 'deposit' ? 'initial_deposit' : 'other';
  }
  if (entry.type === 'buy' || entry.type === 'sell') return 'trade';
  if (entry.type === 'fee') return 'fee';
  return 'other';
}

export const CASH_MOVEMENT_LABELS: Record<CashMovementKind, string> = {
  transfer: 'Transferencia (histórico)',
  external_deposit: 'Depósito externo',
  external_withdrawal: 'Retirada externa',
  trade: 'Operación bursátil',
  fee: 'Comisión y cargos',
  custody: 'Custodia anual',
  initial_deposit: 'Depósito inicial',
  other: 'Movimiento',
};

/** Etiqueta legible en español para un asiento del libro mayor. */
export function formatLedgerEntryLabel(entry: {
  type: LedgerEntryType;
  referenceType: string | null;
  amount: number;
}): string {
  if (entry.type === 'buy') return 'Compra';
  if (entry.type === 'sell') return 'Venta';
  if (entry.type === 'withdrawal' && entry.referenceType !== 'external') return 'Retirada';
  if (entry.type === 'deposit' && entry.referenceType !== 'external' && entry.referenceType !== 'manual') {
    return 'Ingreso de efectivo';
  }
  if (entry.type === 'dividend') return 'Dividendo';
  if (entry.type === 'adjustment') return 'Ajuste';
  return CASH_MOVEMENT_LABELS[classifyCashMovement(entry)] ?? entry.type;
}

/** Breve explicación del movimiento para la UI de ayuda contextual. */
export function ledgerEntryHint(entry: {
  type: LedgerEntryType;
  referenceType: string | null;
  amount: number;
}): string | null {
  const kind = classifyCashMovement(entry);
  if (kind === 'initial_deposit') {
    return 'Capital con el que se creó la cuenta simulada. Suma efectivo disponible.';
  }
  if (kind === 'external_deposit') {
    return 'Aportación simulada de capital (menú Depósito en Movimientos).';
  }
  if (kind === 'external_withdrawal') {
    return 'Retirada simulada de capital hacia fuera de la cuenta.';
  }
  if (entry.type === 'buy') {
    return 'Importe de la compra (títulos × precio). Las comisiones van en líneas aparte.';
  }
  if (entry.type === 'sell') {
    return 'Importe de la venta (títulos × precio). Las comisiones van en líneas aparte.';
  }
  if (kind === 'fee' || entry.type === 'fee') {
    return 'Cargo descontado del efectivo: comisión del broker, IVA, impuesto de transmisiones (compras) o conversión FX según el perfil de la cuenta.';
  }
  if (kind === 'custody') {
    return 'Cargo anual de custodia: % configurado sobre el patrimonio total (se aplica al consultar resumen o fiscal).';
  }
  return null;
}
