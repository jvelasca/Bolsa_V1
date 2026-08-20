/**
 * Convenciones de formato número/fecha del frontend (locale es-ES).
 *
 * Centraliza el locale "es-ES" (y las opciones de `Intl` usadas en la app)
 * que antes se repetía inline como `toLocaleString("es-ES", ...)` en ~30
 * ficheros, para que el formato sea coherente y testeable en un único punto
 * (hallazgo P2.8 de la auditoría consolidada).
 *
 * Nota: los helpers preservan exactamente la semántica `Intl` de los call
 * sites que sustituyen; no cambian el valor formateado.
 */

const ES_LOCALE = "es-ES";

/** Fecha+tiempo por defecto (equivalente a `new Date(iso).toLocaleString("es-ES")`). */
export function formatDateTime(value: string | Date): string {
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleString(ES_LOCALE);
}

/** Día+tiempo corto (equivalente a `{ dateStyle: "short", timeStyle: "short" }`). */
export function formatDateTimeShort(value: string | Date): string {
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleString(ES_LOCALE, {
    dateStyle: "short",
    timeStyle: "short",
  });
}

/** Día 2-dígitos + mes corto + año + hora:minuto (patrón usado en listados). */
export function formatDateTimeCompact(value: string | Date): string {
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleString(ES_LOCALE, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Fecha corta día+mes+año (equivalente a `{ day: "2-digit", month: "short", year: "numeric" }`). */
export function formatDate(value: string | Date): string {
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleDateString(ES_LOCALE, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Número con el separador de miles/decimals es-ES (equivalente a `n.toLocaleString("es-ES")`). */
export function formatNumber(value: number): string {
  return value.toLocaleString(ES_LOCALE);
}

/** Número con opciones `Intl.NumberFormat` explícitas (locale es-ES). */
export function formatNumberWith(
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  return value.toLocaleString(ES_LOCALE, options);
}

/** Fecha con opciones `Intl.DateTimeFormat` explícitas (locale es-ES). */
export function formatDateWith(
  value: string | Date,
  options?: Intl.DateTimeFormatOptions,
): string {
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleDateString(ES_LOCALE, options);
}

/** Fecha+tiempo con opciones `Intl.DateTimeFormat` explícitas (locale es-ES). */
export function formatDateTimeWith(
  value: string | Date,
  options?: Intl.DateTimeFormatOptions,
): string {
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleString(ES_LOCALE, options);
}

/** Número entero (0 decimales), usado para conteos grandes. */
export function formatNumber0(value: number): string {
  return value.toLocaleString(ES_LOCALE, { maximumFractionDigits: 0 });
}

/** Número con 4–6 decimales (tipo de cambio). */
export function formatFxRate(value: number): string {
  return value.toLocaleString(ES_LOCALE, {
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  });
}

/**
 * Parsea un importe/cantidad escrito con formato numérico es-ES de forma
 * tolerante, normalizando el separador de miles antes de parsear.
 *
 * - Soporta separador de miles `.`, decimal `,` y decimal-punto `.` a la vez.
 * - `"1.500"` -> 1500, `"1,5"` -> 1.5, `"1.500,75"` -> 1500.75, `"1.5"` -> 1.5.
 * - Devuelve `null` si el valor no es numérico válido (o está vacío).
 */
export function parseLocalizedNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  // Quita los `.` que actúan como separador de miles: seguidos de exactamente
  // 3 dígitos y a continuación otro separador o el final (p.ej. `1.500`).
  const noThousands = trimmed.replace(/\.(?=\d{3}(\.|,|$))/g, "");
  // Convierte la `,` decimal en `.` decimal-punto.
  const normalized = noThousands.replace(",", ".");
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}
