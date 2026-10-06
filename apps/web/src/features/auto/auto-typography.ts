/**
 * AUTO UI REFACTOR 3.0 (S3) — dos niveles de densidad tipográfica (spec 3.0 §1.8).
 *
 * El primer nivel (usuario) habla en frases y usa ≥ 14 px; el detalle técnico usa 10–12 px y vive
 * siempre bajo un encabezado «Detalle técnico» (ver `AutoTechnicalDetail`). No se mezclan: una
 * superficie de primer nivel no debe bajar de `text-sm`.
 */

/** Texto de primer nivel (usuario básico): 14 px. */
export const AUTO_USER_TEXT = "text-sm" as const;
/** Titular de primer nivel: 16 px. */
export const AUTO_USER_TITLE = "text-base" as const;
/** Texto de detalle técnico: 12 px. */
export const AUTO_TECH_TEXT = "text-xs" as const;
/** Metadato de detalle técnico: 10 px. */
export const AUTO_TECH_META = "text-[10px]" as const;
