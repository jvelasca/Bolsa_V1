/**
 * Carrusel DÍA D — mismo espíritu que listas Trading:
 * predeterminados (visibles vía …) + personalizados editables/borrables.
 */

export const DIA_D_CAROUSEL_KEY = "bolsa-dia-d-carousel-v1";
/** Legacy: solo fechas ISO personalizadas. */
export const DIA_D_FAVORITES_KEY = "bolsa-dia-d-favorites-v1";
export const DIA_D_CUSTOM_MAX = 12;

const ISO_RE = /^\d{4}-\d{2}-\d{2}$/;

export function isValidDiaDIso(value: string): boolean {
  return ISO_RE.test(value.trim());
}

export function startOfLocalYearIso(ref: Date = new Date()): string {
  return `${ref.getFullYear()}-01-01`;
}

function clampPastIso(iso: string, ref: Date = new Date()): string {
  const today = `${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}-${String(ref.getDate()).padStart(2, "0")}`;
  return iso > today ? today : iso;
}

export function monthsAgoIso(months: number, ref: Date = new Date()): string {
  const d = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
  d.setMonth(d.getMonth() - months);
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return clampPastIso(iso, ref);
}

export function yearsAgoIso(years: number, ref: Date = new Date()): string {
  const d = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
  d.setFullYear(d.getFullYear() - years);
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return clampPastIso(iso, ref);
}

/** Predeterminados del carrusel (no borrables). */
export type DiaDPresetId = "3m" | "6m" | "9m" | "1y" | "2y";

export type DiaDPresetDef = {
  id: DiaDPresetId;
  label: string;
  resolve: (ref?: Date) => string;
};

export const DIA_D_PRESETS: readonly DiaDPresetDef[] = [
  { id: "3m", label: "Hace 3 meses", resolve: (ref) => monthsAgoIso(3, ref) },
  { id: "6m", label: "Hace 6 meses", resolve: (ref) => monthsAgoIso(6, ref) },
  { id: "9m", label: "Hace 9 meses", resolve: (ref) => monthsAgoIso(9, ref) },
  { id: "1y", label: "Hace 1 año", resolve: (ref) => yearsAgoIso(1, ref) },
  { id: "2y", label: "Hace 2 años", resolve: (ref) => yearsAgoIso(2, ref) },
] as const;

export const DIA_D_DEFAULT_VISIBLE_PRESETS: readonly DiaDPresetId[] = [
  "3m",
  "6m",
  "9m",
  "1y",
  "2y",
];

export type DiaDCustomEntry = {
  iso: string;
  /** Etiqueta opcional; si falta se muestra dd/mm/yyyy. */
  label?: string;
};

export type DiaDCarouselPrefs = {
  /** Predeterminados visibles en el carrusel. */
  visiblePresetIds: DiaDPresetId[];
  /** Fechas personalizadas (editables / borrables). */
  customs: DiaDCustomEntry[];
};

export function defaultDiaDCarouselPrefs(): DiaDCarouselPrefs {
  return {
    visiblePresetIds: [...DIA_D_DEFAULT_VISIBLE_PRESETS],
    customs: [],
  };
}

export function formatDiaDDisplay(iso: string): string {
  const raw = iso.trim();
  if (!isValidDiaDIso(raw)) return raw || "—";
  const [y, m, d] = raw.split("-");
  return `${d}/${m}/${y}`;
}

function sanitizeCustoms(raw: unknown): DiaDCustomEntry[] {
  if (!Array.isArray(raw)) return [];
  const out: DiaDCustomEntry[] = [];
  for (const item of raw) {
    if (typeof item === "string" && isValidDiaDIso(item)) {
      const iso = item.trim();
      if (!out.some((c) => c.iso === iso)) out.push({ iso });
    } else if (item && typeof item === "object") {
      const iso =
        typeof (item as DiaDCustomEntry).iso === "string"
          ? (item as DiaDCustomEntry).iso.trim()
          : "";
      if (!isValidDiaDIso(iso)) continue;
      if (out.some((c) => c.iso === iso)) continue;
      const label =
        typeof (item as DiaDCustomEntry).label === "string"
          ? (item as DiaDCustomEntry).label!.trim() || undefined
          : undefined;
      out.push({ iso, label });
    }
    if (out.length >= DIA_D_CUSTOM_MAX) break;
  }
  return out.sort((a, b) => b.iso.localeCompare(a.iso));
}

function sanitizeVisiblePresets(raw: unknown): DiaDPresetId[] {
  const allowed = new Set(DIA_D_PRESETS.map((p) => p.id));
  if (!Array.isArray(raw)) return [...DIA_D_DEFAULT_VISIBLE_PRESETS];
  const out: DiaDPresetId[] = [];
  for (const id of raw) {
    if (typeof id !== "string" || !allowed.has(id as DiaDPresetId)) continue;
    if (!out.includes(id as DiaDPresetId)) out.push(id as DiaDPresetId);
  }
  return out.length > 0 ? out : [...DIA_D_DEFAULT_VISIBLE_PRESETS];
}

function migrateLegacyFavorites(): DiaDCustomEntry[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(DIA_D_FAVORITES_KEY);
    if (!raw) return [];
    return sanitizeCustoms(JSON.parse(raw));
  } catch {
    return [];
  }
}

export function loadDiaDCarouselPrefs(): DiaDCarouselPrefs {
  const fallback = defaultDiaDCarouselPrefs();
  if (typeof localStorage === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(DIA_D_CAROUSEL_KEY);
    if (!raw) {
      const legacy = migrateLegacyFavorites();
      if (legacy.length === 0) return fallback;
      const migrated = { ...fallback, customs: legacy };
      saveDiaDCarouselPrefs(migrated);
      return migrated;
    }
    const o = JSON.parse(raw) as Partial<DiaDCarouselPrefs>;
    return {
      visiblePresetIds: sanitizeVisiblePresets(o.visiblePresetIds),
      customs: sanitizeCustoms(o.customs),
    };
  } catch {
    return fallback;
  }
}

export function saveDiaDCarouselPrefs(prefs: DiaDCarouselPrefs): void {
  if (typeof localStorage === "undefined") return;
  try {
    const clean: DiaDCarouselPrefs = {
      visiblePresetIds: sanitizeVisiblePresets(prefs.visiblePresetIds),
      customs: sanitizeCustoms(prefs.customs),
    };
    localStorage.setItem(DIA_D_CAROUSEL_KEY, JSON.stringify(clean));
  } catch {
    // ignore
  }
}

export function isPresetVisible(
  prefs: DiaDCarouselPrefs,
  id: DiaDPresetId,
): boolean {
  return prefs.visiblePresetIds.includes(id);
}

export function togglePresetVisible(
  prefs: DiaDCarouselPrefs,
  id: DiaDPresetId,
): DiaDCarouselPrefs {
  const set = new Set(prefs.visiblePresetIds);
  if (set.has(id)) set.delete(id);
  else set.add(id);
  const visiblePresetIds = DIA_D_PRESETS.map((p) => p.id).filter((pid) =>
    set.has(pid),
  );
  return { ...prefs, visiblePresetIds };
}

export function addCustomDiaD(
  prefs: DiaDCarouselPrefs,
  iso: string,
  label?: string,
): DiaDCarouselPrefs {
  const date = iso.trim();
  if (!isValidDiaDIso(date)) return prefs;
  const rest = prefs.customs.filter((c) => c.iso !== date);
  const entry: DiaDCustomEntry = {
    iso: date,
    label: label?.trim() || undefined,
  };
  return {
    ...prefs,
    customs: sanitizeCustoms([entry, ...rest]),
  };
}

export function updateCustomDiaD(
  prefs: DiaDCarouselPrefs,
  prevIso: string,
  next: { iso: string; label?: string },
): DiaDCarouselPrefs {
  if (!isValidDiaDIso(next.iso)) return prefs;
  const without = prefs.customs.filter(
    (c) => c.iso !== prevIso && c.iso !== next.iso.trim(),
  );
  return {
    ...prefs,
    customs: sanitizeCustoms([
      { iso: next.iso.trim(), label: next.label?.trim() || undefined },
      ...without,
    ]),
  };
}

export function removeCustomDiaD(
  prefs: DiaDCarouselPrefs,
  iso: string,
): DiaDCarouselPrefs {
  return {
    ...prefs,
    customs: prefs.customs.filter((c) => c.iso !== iso),
  };
}

export type DiaDCarouselChip =
  | {
      kind: "preset";
      id: DiaDPresetId;
      label: string;
      iso: string;
    }
  | {
      kind: "custom";
      id: string;
      label: string;
      iso: string;
    };

/** Chips visibles en el carrusel (predeterminados marcados + personalizados). */
export function resolveDiaDCarouselChips(
  prefs: DiaDCarouselPrefs,
  ref: Date = new Date(),
): DiaDCarouselChip[] {
  const chips: DiaDCarouselChip[] = [];
  for (const preset of DIA_D_PRESETS) {
    if (!prefs.visiblePresetIds.includes(preset.id)) continue;
    chips.push({
      kind: "preset",
      id: preset.id,
      label: preset.label,
      iso: preset.resolve(ref),
    });
  }
  for (const custom of prefs.customs) {
    chips.push({
      kind: "custom",
      id: `custom:${custom.iso}`,
      label: custom.label?.trim() || formatDiaDDisplay(custom.iso),
      iso: custom.iso,
    });
  }
  return chips;
}

/** @deprecated aliases for older imports/tests */
export const DIA_D_QUICK_PRESETS = DIA_D_PRESETS;
export type DiaDQuickPresetId = DiaDPresetId;

export function loadDiaDFavorites(): string[] {
  return loadDiaDCarouselPrefs().customs.map((c) => c.iso);
}

export function saveDiaDFavorites(dates: string[]): void {
  const prefs = loadDiaDCarouselPrefs();
  saveDiaDCarouselPrefs({
    ...prefs,
    customs: sanitizeCustoms(dates),
  });
}

export function addDiaDFavorite(current: string[], iso: string): string[] {
  const prefs = addCustomDiaD(
    { ...defaultDiaDCarouselPrefs(), customs: sanitizeCustoms(current) },
    iso,
  );
  return prefs.customs.map((c) => c.iso);
}

export function removeDiaDFavorite(current: string[], iso: string): string[] {
  return current.filter((d) => d !== iso);
}

export function toggleDiaDFavorite(current: string[], iso: string): string[] {
  if (current.includes(iso)) return removeDiaDFavorite(current, iso);
  return addDiaDFavorite(current, iso);
}
