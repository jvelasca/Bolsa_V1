import type { ChartDrawTool } from '@bolsa/shared';
import {
  organizeDrawToolFavorites,
  toggleDrawToolFavoriteList,
} from '@bolsa/shared';
import { describe, expect, it } from 'vitest';
import {
  drawingRailFamilyBlocks,
  extraFavoriteToolsForRail,
  isGroupRailToolActive,
  resolveGroupRailActivateTool,
  resolveGroupRailIconTool,
} from './chart-drawing-tools';

describe('chart drawing rail favorites', () => {
  const favorites = ['select', 'line', 'ray', 'hline', 'channel'] as const;

  it('lists only extra favorites once, in favorites order', () => {
    expect(extraFavoriteToolsForRail([...favorites])).toEqual(['ray', 'hline']);
  });

  it('does not duplicate active extra favorite on group icon', () => {
    expect(
      resolveGroupRailIconTool('lines', 'ray', { lines: 'ray' }, [...favorites]),
    ).toBe('line');
  });

  it('shows active non-extra tool on group icon', () => {
    expect(
      resolveGroupRailIconTool('lines', 'line', { lines: 'line' }, [...favorites]),
    ).toBe('line');
  });

  it('shows menu-only tool on group icon when active', () => {
    const favs = ['select', 'line', 'ray'] as const;
    expect(resolveGroupRailIconTool('lines', 'vline', {}, [...favs])).toBe('vline');
  });

  it('highlights only one rail slot for extra favorites', () => {
    expect(isGroupRailToolActive('lines', 'ray', [...favorites])).toBe(false);
    expect(isGroupRailToolActive('lines', 'line', [...favorites])).toBe(true);
    expect(isGroupRailToolActive('lines', 'vline', [...favorites])).toBe(true);
  });

  it('activates primary or last non-extra tool from group button', () => {
    expect(resolveGroupRailActivateTool('lines', { lines: 'ray' }, [...favorites])).toBe(
      'line',
    );
    expect(resolveGroupRailActivateTool('lines', { lines: 'line' }, [...favorites])).toBe(
      'line',
    );
    expect(resolveGroupRailActivateTool('lines', { lines: 'vline' }, [...favorites])).toBe(
      'vline',
    );
  });

  it('inserts new favorites next to siblings and keeps families grouped', () => {
    let favs: ChartDrawTool[] = ['select', 'line', 'channel', 'fibonacci'];
    favs = toggleDrawToolFavoriteList(favs, 'ray');
    expect(favs).toEqual(['select', 'line', 'ray', 'channel', 'fibonacci']);
    favs = toggleDrawToolFavoriteList(favs, 'hline');
    expect(favs).toEqual(['select', 'line', 'ray', 'hline', 'channel', 'fibonacci']);
    favs = toggleDrawToolFavoriteList(favs, 'cross');
    expect(favs).toEqual(['select', 'cross', 'line', 'ray', 'hline', 'channel', 'fibonacci']);
  });

  it('reorganizes messy persisted favorites into canonical bar order', () => {
    const messy: ChartDrawTool[] = ['fibonacci', 'ray', 'select', 'dot', 'line', 'cross', 'channel'];
    expect(organizeDrawToolFavorites(messy)).toEqual([
      'select',
      'cross',
      'dot',
      'ray',
      'line',
      'channel',
      'fibonacci',
    ]);
  });

  it('builds minimal family blocks with empty favorites', () => {
    const blocks = drawingRailFamilyBlocks([]);
    expect(blocks.every((block) => block.extraTools.length === 0)).toBe(true);
    expect(blocks.every((block) => block.slotCount === 1)).toBe(true);
    expect(blocks.every((block) => block.bracketed === false)).toBe(true);
  });

  it('builds unified family blocks with primary included in bracket count', () => {
    const favs = organizeDrawToolFavorites([
      'select',
      'cross',
      'dot',
      'line',
      'ray',
      'fibonacci',
    ] as ChartDrawTool[]);

    const cursor = drawingRailFamilyBlocks(favs).find((block) => block.groupId === 'cursor');
    const lines = drawingRailFamilyBlocks(favs).find((block) => block.groupId === 'lines');
    const fibonacci = drawingRailFamilyBlocks(favs).find((block) => block.groupId === 'fibonacci');

    expect(cursor).toMatchObject({
      extraTools: ['cross', 'dot'],
      slotCount: 3,
      bracketed: true,
      showMenu: true,
    });
    expect(lines).toMatchObject({
      extraTools: ['ray'],
      slotCount: 2,
      bracketed: true,
      showMenu: true,
    });
    expect(fibonacci).toMatchObject({
      extraTools: [],
      slotCount: 1,
      bracketed: false,
      showMenu: true,
    });
  });
});
