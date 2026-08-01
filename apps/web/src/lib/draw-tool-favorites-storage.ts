import type { ChartDrawTool } from '@bolsa/shared';
import { IMPLEMENTED_DRAW_TOOLS, normalizeDrawToolFavorites } from '@bolsa/shared';

const STORAGE_KEY = 'bolsa-draw-tool-favorites';

export function readDrawToolFavoritesLocal(): ChartDrawTool[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ChartDrawTool[];
    if (!Array.isArray(parsed)) return null;
    return normalizeDrawToolFavorites(parsed, IMPLEMENTED_DRAW_TOOLS);
  } catch {
    return null;
  }
}

export function writeDrawToolFavoritesLocal(favorites: ChartDrawTool[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
  } catch {
    // quota / private mode
  }
}
