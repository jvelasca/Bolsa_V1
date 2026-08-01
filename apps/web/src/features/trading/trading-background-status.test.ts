import { describe, expect, it } from 'vitest';
import type { SyncQueueItemDto, SyncSettingsDto } from '@bolsa/shared';
import { summarizeBackgroundSync } from '@/features/trading/trading-background-status';

import { summarizeBackgroundSync } from '@/features/trading/trading-background-sync-summary';
const baseSettings: SyncSettingsDto = {
  autoSyncEnabled: true,
  scanIntervalMinutes: 30,
  minDelaySeconds: 5,
  postMarketOnly: false,
  maxRetries: 3,
  retryBackoffMinutes: 15,
  scope: 'lists',
  updatedAt: '2026-07-30T00:00:00.000Z',
};

function item(partial: Partial<SyncQueueItemDto> & Pick<SyncQueueItemDto, 'status' | 'symbol'>): SyncQueueItemDto {
  return {
    id: partial.id ?? '1',
    instrumentId: partial.instrumentId ?? 'inst-1',
    symbol: partial.symbol,
    status: partial.status,
    priority: partial.priority ?? 1,
    scheduledAt: partial.scheduledAt ?? 't',
    attempts: partial.attempts ?? 0,
    lastError: partial.lastError ?? null,
    createdAt: partial.createdAt ?? 't',
    updatedAt: partial.updatedAt ?? 't',
  };
}
describe('summarizeBackgroundSync', () => {
  it('shows off when auto-sync disabled', () => {
    const s = summarizeBackgroundSync({
      settings: { ...baseSettings, autoSyncEnabled: false },
      queue: [],
    });
    expect(s.label).toBe('Velas · off');
    expect(s.tone).toBe('off');
  });
  it('shows idle when queue empty', () => {
    const s = summarizeBackgroundSync({ settings: baseSettings, queue: [] });
    expect(s.label).toBe('Velas · al día');
    expect(s.tone).toBe('idle');
  });
  it('shows queue count when pending', () => {
    const s = summarizeBackgroundSync({
      settings: baseSettings,
      queue: [item({ status: 'pending', symbol: 'SAN.MC' }), item({ id: '2', status: 'pending', symbol: 'IBE.MC' })],
    });
    expect(s.label).toBe('Velas · cola 2');
    expect(s.tone).toBe('active');
  });
  it('shows symbol when processing', () => {
    const s = summarizeBackgroundSync({
      settings: baseSettings,
      queue: [item({ status: 'processing', symbol: 'AAPL' })],
    });
    expect(s.label).toContain('AAPL');
    expect(s.tone).toBe('active');
  });
});