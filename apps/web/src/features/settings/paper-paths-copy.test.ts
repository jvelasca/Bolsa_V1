/**
 * Tests — copy unificada caminos demo / supervisado.
 */

import { describe, expect, it } from 'vitest';
import {
  PAPER_PATHS_COMPARE,
  PAPER_PATH_LAB,
  PAPER_PATH_PRODUCT_DECISION,
  PAPER_PATH_RADAR,
  PAPER_PATH_SUPERVISED,
  PAPER_PATH_MONITOR,
  defaultRequireValidatedBacktest,
} from '@/features/settings/paper-paths-copy';

describe('paper-paths-copy', () => {
  it('keeps Lab, Radar and Supervised distinct', () => {
    expect(PAPER_PATH_LAB.id).not.toBe(PAPER_PATH_RADAR.id);
    expect(PAPER_PATH_LAB.id).not.toBe(PAPER_PATH_SUPERVISED.id);
    expect(PAPER_PATH_LAB.cta).toMatch(/Desplegar en demo/);
    expect(PAPER_PATH_SUPERVISED.cta).toMatch(/Proponer/);
    expect(PAPER_PATH_RADAR.modeLabel).toMatch(/radar|demo/i);
    expect(PAPER_PATHS_COMPARE).toMatch(/Lab|demo/i);
    expect(PAPER_PATHS_COMPARE).toMatch(/Radar|Supervisado/i);
  });

  it('freezes product stance as demo active only (not broker Paper)', () => {
    expect(PAPER_PATH_PRODUCT_DECISION.asOf).toBe('2026-07-31');
    expect(PAPER_PATH_PRODUCT_DECISION.stance).toBe('demo_active_only');
    expect(PAPER_PATH_PRODUCT_DECISION.summary).toMatch(/DEMO|demo/i);
    expect(PAPER_PATH_LAB.libraryHint).toMatch(/checklist/i);
    expect(PAPER_PATH_LAB.finalistsHint).toMatch(/Checklist|demo/i);
    expect(PAPER_PATH_SUPERVISED.finalistsHint).toMatch(/Camino C|F3|Supervisado/i);
    expect(PAPER_PATH_MONITOR.warnLine).toMatch(/no ejecuta/i);
  });

  it('Monitor copy mentions CORE-R / no TOP overwrite stance', () => {
    expect(PAPER_PATH_MONITOR.blurb).toMatch(/CORE-R|retorno/i);
    expect(PAPER_PATH_MONITOR.blurb).toMatch(/mandato/i);
    expect(PAPER_PATH_MONITOR.warnLine).toMatch(/no ejecutan|no ejecuta/i);
    expect(PAPER_PATH_MONITOR.warnLine).toMatch(/TOP|Encolar/i);
  });

  it('defaults requireValidatedBacktest for paper_auto', () => {
    expect(defaultRequireValidatedBacktest('paper_auto')).toBe(true);
    expect(defaultRequireValidatedBacktest('alert')).toBe(false);
    expect(defaultRequireValidatedBacktest('inform_only')).toBe(false);
  });
});
