/**
 * AutoWorkspaceLayout — shell del espacio AUTO (ADR-044).
 *
 * Aporta la **sub-navegación persistente** de las cinco secciones (Operar ·
 * Cartera · Riesgo · Análisis · Sistema) y monta la sección activa por `Outlet`.
 *
 * Accesibilidad (contrato de ADR-044 §3):
 * - El `<main>` **único** lo aporta `PlatformShell`; este layout NO anida otro.
 * - El `<h1>` de página lo aporta cada sección vía `AutoSectionHeading`, de modo
 *   que cada ruta expone exactamente un `h1` (y la jerarquía `h1 → h2 → h3`).
 *
 * @see docs/adr/044-auto-workspace-information-architecture.md
 */

import { NavLink, Outlet } from "react-router-dom";
import { AUTO_NAV } from "@/features/auto/auto-nav";
import { AutoRealityStrip } from "@/features/auto/auto-reality-strip";
import { cn } from "@/lib/utils";

export function AutoWorkspaceLayout() {
  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row"
      data-testid="auto-workspace"
    >
      <nav
        aria-label="Secciones AUTO"
        className="flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-card/40 p-2 md:w-48 md:flex-col md:overflow-visible md:border-b-0 md:border-r"
      >
        {AUTO_NAV.items.map((item) => (
          <NavLink
            key={item.id}
            to={item.path}
            title={item.hint}
            data-testid={`auto-nav-${item.id}`}
            className={({ isActive }) =>
              cn(
                "flex items-center rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground",
                isActive && "bg-accent text-primary",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-auto">
        <div className="mx-auto max-w-6xl p-4 sm:p-6">
          <AutoRealityStrip />
          <Outlet />
        </div>
      </div>
    </div>
  );
}

/**
 * Encabezado de sección AUTO: el **único** `h1` de la ruta. Las secciones usan
 * `<h2>` para sus bloques y los componentes reutilizados aportan `<h3>` (tarjeta).
 */
export function AutoSectionHeading({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <header className="space-y-1">
      <h1 className="font-serif text-2xl font-semibold tracking-tight">
        {title}
      </h1>
      {description ? (
        <p className="text-sm text-muted-foreground">{description}</p>
      ) : null}
    </header>
  );
}

/** `<h2>` de bloque dentro de una sección AUTO (resumen operativo arriba). */
export function AutoSectionBlockHeading({
  id,
  children,
}: {
  id: string;
  children: React.ReactNode;
}) {
  return (
    <h2
      id={id}
      className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
    >
      {children}
    </h2>
  );
}
