/**
 * Tests — guías Ayuda Backtesting (DÍA D + CORE-R) y sync docs.
 *
 * Si cambias pasos de producto, actualiza estas aserciones y HELP.md.
 */

import { describe, expect, it } from 'vitest';
import { HELP_CONTENT_AS_OF } from '@/features/help/help-content-as-of';
import {
  BACKTESTING_CORE_R_GUIDE,
  BACKTESTING_DIA_D_GUIDE,
  BACKTESTING_NEXT,
  BACKTESTING_SUMMARY,
  BACKTESTING_SYNC,
  BACKTESTING_TRACKING,
} from '@/features/settings/backtesting-tracker';

describe('backtesting-tracker help guides', () => {
  it('keeps HELP_CONTENT_AS_OF aligned with BACKTESTING_SYNC', () => {
    expect(BACKTESTING_SYNC.asOf).toBe(HELP_CONTENT_AS_OF);
    expect(BACKTESTING_SYNC.diaDPremises).toMatch(/backtesting-dia-d-premises/);
    expect(BACKTESTING_SYNC.operativaTestPlan).toMatch(/operativa-test-plan/);
  });

  it('DÍA D guide covers full-bleed ephemeral, Evidence, Operaciones restore', () => {
    expect(BACKTESTING_DIA_D_GUIDE.steps.length).toBeGreaterThanOrEqual(8);
    const blob = [...BACKTESTING_DIA_D_GUIDE.steps, ...BACKTESTING_DIA_D_GUIDE.notes].join(
      ' ',
    );
    expect(blob).toMatch(/Pantalla completa/i);
    expect(blob).toMatch(/no se persiste|no persiste|efímera|recargar/i);
    expect(blob).toMatch(/Operaciones|docks/i);
    expect(blob).toMatch(/Guardar Evidence/i);
    expect(blob).toMatch(/preview|JSON|Importar|Ayuda|archivo/i);
    expect(blob).toMatch(/Narrar/i);
    expect(blob).toMatch(/api-python|API/i);
    expect(blob).toMatch(/test:operativa/);
  });

  it('CORE-R guide covers enqueue, narrate, shell cron', () => {
    const blob = [...BACKTESTING_CORE_R_GUIDE.steps, ...BACKTESTING_CORE_R_GUIDE.notes].join(
      ' ',
    );
    expect(blob).toMatch(/Encolar/i);
    expect(blob).toMatch(/Narrar/i);
    expect(blob).toMatch(/Auto-sync|app abierta|shell/i);
    expect(blob).toMatch(/Hecho todos|Abrir Monitor|toast|chip|barra/i);
    expect(blob).toMatch(/no auto-paper|No es auto-paper/i);
    expect(blob).toMatch(/localStorage/i);
  });

  it('summary bullets mention DÍA D and Monitor CORE-R', () => {
    const bullets = BACKTESTING_SUMMARY.bullets.join(' ');
    expect(bullets).toMatch(/DÍA D/);
    expect(bullets).toMatch(/CORE-R|Monitor/);
  });

  it('tracking marks dia-d, core-r and lab-core-b as listo', () => {
    const dia = BACKTESTING_TRACKING.find((r) => r.id === 'dia-d');
    const cr = BACKTESTING_TRACKING.find((r) => r.id === 'core-r-queue');
    const lab = BACKTESTING_TRACKING.find((r) => r.id === 'lab-core-b');
    const fresh = BACKTESTING_TRACKING.find((r) => r.id === 'list-auto-freshness');
    expect(dia?.status).toBe('listo');
    expect(dia?.title).toMatch(/v0\.11/);
    expect(dia?.plain).toMatch(/efímero|Operaciones/i);
    expect(cr?.status).toBe('listo');
    expect(cr?.plain).toMatch(/v1\.8|Hecho todos|toast/i);
    expect(lab?.status).toBe('listo');
    expect(lab?.plain).toMatch(/meseta|horizonte|CORE-B/i);
    expect(fresh?.plain).toMatch(/v1\.3|bar_hysteresis|histéresis/i);
  });

  it('NEXT points at operativa smoke and congelados', () => {
    const next = BACKTESTING_NEXT.join(' ');
    expect(next).toMatch(/test:operativa/);
    expect(next).toMatch(/operativa-test-plan|D1|smoke/i);
    expect(next).toMatch(/multi-dispositivo|Congelado|P3–P9/i);
    expect(next).toMatch(/handoff-2026-08-01/);
  });
});
