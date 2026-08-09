/**
 * Batería IBEX 35 — coherencia operativa offline (lista completa).
 */

import { describe, expect, it } from 'vitest';
import { IBEX35_INSTRUMENTS } from '@bolsa/shared';
import {
  formatIbex35AuditReport,
  runIbex35OperativaAudit,
} from '@/features/backtests/ibex35-operativa-audit';
import { LIST_AUTO_MAX_INSTRUMENTS } from '@/features/backtests/backtest-list-auto';

describe('IBEX35 operativa audit (offline)', () => {
  it('catálogo compartido tiene 35 símbolos y cabe en soft cap', () => {
    expect(IBEX35_INSTRUMENTS).toHaveLength(35);
    expect(IBEX35_INSTRUMENTS.length).toBeLessThanOrEqual(LIST_AUTO_MAX_INSTRUMENTS);
    const symbols = new Set(IBEX35_INSTRUMENTS.map((i) => i.symbol));
    expect(symbols.size).toBe(35);
  });

  it('simula lista completa: coach diverso + Lista AUTO + política ciclo', () => {
    const report = runIbex35OperativaAudit();
    console.log(formatIbex35AuditReport(report));

    expect(report.instrumentCount).toBe(35);
    expect(report.snapshots).toHaveLength(35);
    expect(report.passed).toBe(true);
    expect(report.criticalCount).toBe(0);
    expect(report.softFallbackRate).toBe(0);
    expect(report.stickyTop1Share).toBeLessThan(0.75);

    // Con perfiles rotados debe haber ≥2 presets distintos en #1
    expect(Object.keys(report.top1Frequency).length).toBeGreaterThanOrEqual(2);

    const codes = new Set(report.findings.map((f) => f.code));
    expect(codes.has('list_auto_complete')).toBe(true);
    expect(codes.has('cycle_preserve_active')).toBe(true);
    expect(codes.has('sticky_top1')).toBe(false);
  });

  it('detecta TOP #1 pegajoso (fallo operativo)', () => {
    const report = runIbex35OperativaAudit({ forceStickyTop1: true });
    expect(report.passed).toBe(false);
    expect(report.findings.some((f) => f.code === 'sticky_top1' && f.severity === 'critical')).toBe(
      true,
    );
  });

  it('detecta soft-fallback masivo sin periodReturns', () => {
    const report = runIbex35OperativaAudit({ forceSoftFallback: true });
    expect(report.softFallbackRate).toBeGreaterThan(0.4);
    expect(
      report.findings.some((f) => f.code === 'soft_fallback_rate' && f.severity === 'critical'),
    ).toBe(true);
    expect(report.passed).toBe(false);
  });
});
