/**
 * Arquitectura de información del espacio AUTO (ADR-044).
 *
 * Labels/rutas unit-testables sin montar el shell. La sub-navegación NO es una
 * sexta puerta L1 de ADR-040: es un espacio con alcance propio accesible desde la
 * AdminRail y la command palette. Las cinco secciones agrupan superficies ya
 * existentes (Mesa, Mercado, Consola operativa, Laboratorio, Asesor) por enlace.
 *
 * @see docs/adr/044-auto-workspace-information-architecture.md
 * @see docs/engineering/spec-auto-ui-refactor-2-0-2026-10-05.md
 */

/** Nombre de producto del espacio. */
export const AUTO_LABEL = "AUTO" as const;

/** Raíz del espacio (redirige a la sección por defecto). */
export const AUTO_ROOT_PATH = "/auto" as const;

/** Sección por defecto (la historia de operación es la vista de trabajo). */
export const AUTO_OPERAR_PATH = "/auto/operar" as const;
export const AUTO_CARTERA_PATH = "/auto/cartera" as const;
export const AUTO_RIESGO_PATH = "/auto/riesgo" as const;
export const AUTO_ANALISIS_PATH = "/auto/analisis" as const;
export const AUTO_SISTEMA_PATH = "/auto/sistema" as const;

/** Base de la operación canónica (selección por `cycleId` en la URL). */
export const AUTO_OPERACION_BASE_PATH = "/auto/operar/operacion" as const;

/**
 * Monitor experto (ventana cruda). Vive FUERA del espacio `/auto/*` (ADR-044): es la
 * superficie técnica del monitor, no una sexta sección. Los deep-links de la operación
 * canónica apuntan aquí para el "detalle técnico".
 */
export const AUTO_MONITOR_PATH = "/auto-monitor" as const;

export const AUTO_SECTION = {
  operar: "operar",
  cartera: "cartera",
  riesgo: "riesgo",
  analisis: "analisis",
  sistema: "sistema",
} as const;

export type AutoSectionId = (typeof AUTO_SECTION)[keyof typeof AUTO_SECTION];

export type AutoNavItem = {
  id: AutoSectionId;
  label: string;
  path: string;
  hint: string;
};

/** Sub-navegación del espacio AUTO (orden de producto). */
export const AUTO_NAV: { label: string; items: readonly AutoNavItem[] } = {
  label: AUTO_LABEL,
  items: [
    {
      id: AUTO_SECTION.operar,
      label: "Operar",
      path: AUTO_OPERAR_PATH,
      hint: "Oportunidades, operaciones y la operación seleccionada",
    },
    {
      id: AUTO_SECTION.cartera,
      label: "Cartera",
      path: AUTO_CARTERA_PATH,
      hint: "Posiciones, órdenes e historial",
    },
    {
      id: AUTO_SECTION.riesgo,
      label: "Riesgo",
      path: AUTO_RIESGO_PATH,
      hint: "Riesgo abierto, límites e integridad financiera",
    },
    {
      id: AUTO_SECTION.analisis,
      label: "Análisis",
      path: AUTO_ANALISIS_PATH,
      hint: "DÍA-D, evidencia, estrategias e investigación",
    },
    {
      id: AUTO_SECTION.sistema,
      label: "Sistema",
      path: AUTO_SISTEMA_PATH,
      hint: "Salud AUTO, broker, reconciliación y auditoría",
    },
  ],
} as const;

/** Deep-link a la operación canónica. Sin `cycleId`, vuelve a la sección Operar. */
export function autoOperacionHref(cycleId?: string | null): string {
  const id = cycleId?.trim();
  return id
    ? `${AUTO_OPERACION_BASE_PATH}/${encodeURIComponent(id)}`
    : AUTO_OPERAR_PATH;
}

/**
 * Deep-link al detalle técnico (ventana actual del monitor experto). El `cycle`
 * preselecciona y enfoca el ciclo en la vista `current` (no es un parámetro inerte).
 */
export function autoTechnicalDetailHref(cycleId?: string | null): string {
  const params = new URLSearchParams({ mode: "current" });
  const id = cycleId?.trim();
  if (id) params.set("cycle", id);
  return `${AUTO_MONITOR_PATH}?${params.toString()}`;
}

/**
 * Deep-link a la explicación DÍA-D (Análisis · pestaña DÍA-D · sub-vista feedback).
 * Mueve el destino al workspace AUTO (`/auto/analisis`), no a la URL del monitor.
 * Preselecciona la ventana y enfoca el símbolo si se conocen.
 */
export function autoDiaDHref(input?: {
  window?: string | null;
  symbol?: string | null;
}): string {
  const params = new URLSearchParams({ tab: "dia-d", view: "feedback" });
  const window = input?.window?.trim();
  const symbol = input?.symbol?.trim();
  if (window) params.set("window", window);
  if (symbol) params.set("symbol", symbol);
  return `${AUTO_ANALISIS_PATH}?${params.toString()}`;
}

/**
 * Sección activa a partir del pathname. Devuelve `null` si la ruta no es del
 * espacio AUTO (permite al shell decidir si monta la sub-navegación).
 */
export function autoSectionFromPathname(pathname: string): AutoNavItem | null {
  if (pathname === AUTO_ROOT_PATH) {
    return (
      AUTO_NAV.items.find((item) => item.id === AUTO_SECTION.operar) ?? null
    );
  }
  const target =
    pathname.startsWith(`${AUTO_OPERACION_BASE_PATH}/`) ||
    pathname === AUTO_OPERACION_BASE_PATH
      ? AUTO_OPERAR_PATH
      : pathname;
  return (
    AUTO_NAV.items.find(
      (item) => target === item.path || target.startsWith(`${item.path}/`),
    ) ?? null
  );
}

/** Label de una sección por id (para el `<title>`/encabezados). */
export function autoSectionLabel(id: AutoSectionId): string {
  return AUTO_NAV.items.find((item) => item.id === id)?.label ?? AUTO_LABEL;
}
