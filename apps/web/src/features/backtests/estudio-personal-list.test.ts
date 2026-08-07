/**
 * Tests legacy — `resolveEstudioPersonalListId` alias de ADR-024.
 */

import { describe, expect, it } from 'vitest';
import {
  ESTUDIO_LIST_ID,
  ESTUDIO_LIST_NAME,
  ESTUDIO_PERSONAL_LIST_NAME,
  isEstudioPersonalListName,
  resolveEstudioPersonalListId,
} from '@bolsa/shared';

describe('Estudio personal list helpers (legacy alias)', () => {
  it('matches legacy personal name', () => {
    expect(isEstudioPersonalListName(ESTUDIO_PERSONAL_LIST_NAME)).toBe(true);
    expect(isEstudioPersonalListName('  estudio PERSONAL ')).toBe(true);
    expect(isEstudioPersonalListName('Estudio')).toBe(false);
  });

  it('resolves via ADR-024 (canónica / nombre / personal)', () => {
    expect(
      resolveEstudioPersonalListId([
        { id: 'ibex35', name: 'IBEX 35' },
        { id: ESTUDIO_LIST_ID, name: ESTUDIO_LIST_NAME },
      ]),
    ).toBe(ESTUDIO_LIST_ID);
    expect(
      resolveEstudioPersonalListId([
        { id: 'x', name: 'Estudio' },
      ]),
    ).toBe('x');
    expect(
      resolveEstudioPersonalListId([
        { id: 'est-1', name: 'Estudio personal' },
      ]),
    ).toBe('est-1');
  });
});
