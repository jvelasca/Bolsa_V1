/**
 * Tests — export / import / etiquetas archivo Evidence DÍA D (v0.10).
 */

import { describe, expect, it } from 'vitest';
import type { DiaDSessionEvidenceV1 } from '@/features/trading/dia-d-session-evidence';
import {
  buildDiaDEvidenceExport,
  diaDEvidenceExportFilename,
  formatDiaDArchiveRowLabel,
  parseDiaDEvidenceImport,
  parseDiaDEvidenceImportText,
} from '@/features/trading/dia-d-evidence-archive-io';
import type { DiaDEvidenceArchiveItem } from '@/stores/dia-d-evidence-archive-store';

const evidence: DiaDSessionEvidenceV1 = {
  schemaVersion: 'dia_d_session_evidence_v1',
  band: 'favorable',
  confidence: 'HIGH',
  claims: ['c1'],
  warnings: [],
  metrics: {
    mode: 'auto',
    returnPct: 12.34,
    maxDrawdownPct: 4,
    tradeCount: 3,
    finalEquity: 11_000,
    autoReturnPct: 12.34,
    returnDeltaVsAutoPct: 0,
    accepted: 3,
    rejected: 0,
  },
  paragraphs: ['p1', 'p2', 'p3'],
  disclaimer: 'sandbox',
};

const item: DiaDEvidenceArchiveItem = {
  id: 'dde-1',
  instrumentId: 'inst-1',
  symbol: 'ACS',
  strategyLabel: 'SMA',
  mode: 'auto',
  diaD: '2024-01-15',
  endDate: '2024-12-31',
  savedAt: '2026-07-31T12:00:00.000Z',
  researchEvidenceId: 'ev-abc',
  engine: 'heuristic',
  evidence,
};

describe('dia-d-evidence-archive-io', () => {
  it('formats compact row label', () => {
    expect(formatDiaDArchiveRowLabel(item)).toMatch(/2024-01-15/);
    expect(formatDiaDArchiveRowLabel(item)).toMatch(/auto/);
    expect(formatDiaDArchiveRowLabel(item)).toMatch(/\+12\.3%/);
  });

  it('builds export envelope with schema', () => {
    const exp = buildDiaDEvidenceExport(item, '2026-07-31T18:00:00.000Z');
    expect(exp.schemaVersion).toBe('dia_d_evidence_export_v1');
    expect(exp.exportedAt).toBe('2026-07-31T18:00:00.000Z');
    expect(exp.item.id).toBe('dde-1');
    expect(exp.item.researchEvidenceId).toBe('ev-abc');
  });

  it('builds safe download filename', () => {
    expect(diaDEvidenceExportFilename(item)).toBe(
      'dia-d-evidence-ACS-2024-01-15-auto.json',
    );
  });

  it('round-trips export envelope', () => {
    const exp = buildDiaDEvidenceExport(item);
    const parsed = parseDiaDEvidenceImport(exp);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.item.symbol).toBe('ACS');
    expect(parsed.item.evidence.band).toBe('favorable');
    expect(parsed.item.researchEvidenceId).toBe('ev-abc');
  });

  it('accepts bare archive item', () => {
    const parsed = parseDiaDEvidenceImport(item);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.item.mode).toBe('auto');
  });

  it('rejects garbage', () => {
    expect(parseDiaDEvidenceImportText('not-json').ok).toBe(false);
    expect(parseDiaDEvidenceImport({ schemaVersion: 'x' }).ok).toBe(false);
    expect(
      parseDiaDEvidenceImport({
        schemaVersion: 'dia_d_evidence_export_v1',
        item: { symbol: 'ACS' },
      }).ok,
    ).toBe(false);
  });
});
