/**
 * AUTO · CARTERA (ADR-044) — posiciones, órdenes e historial.
 *
 * Compone la superficie existente de operaciones (misma que el Libro en Hoy)
 * y enlaza historial, cuentas y riesgo. **NO** es una superficie read-only: incluye
 * acciones operativas (reducir / salir) que **encolan** Confirm; Confirm es la única firma.
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { OperationsPanel } from "@/features/trading/operations-panel";
import { CARTERA_RIESGO_PATH } from "@/features/confirm/daily-nav";
import { AUTO_SECTION_COPY } from "@/features/auto/auto-copy";

export function AutoCarteraPage() {
  return (
    <div className="space-y-6" data-testid="auto-cartera-page">
      <AutoSectionHeading
        title={AUTO_SECTION_COPY.cartera.title}
        description={AUTO_SECTION_COPY.cartera.description}
      />

      <div
        role="note"
        data-testid="auto-cartera-demo-banner"
        className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm"
      >
        <p className="font-semibold">CARTERA DEMO — posiciones simuladas</p>
        <p className="text-muted-foreground">
          No se envían órdenes reales a XTB. Reducir o salir encola una
          propuesta; Confirm es la única firma.
        </p>
      </div>

      <section className="space-y-2" aria-labelledby="auto-cartera-ops-heading">
        <AutoSectionBlockHeading id="auto-cartera-ops-heading">
          Posiciones y órdenes
        </AutoSectionBlockHeading>
        <OperationsPanel />
      </section>

      <section
        className="space-y-2"
        aria-labelledby="auto-cartera-links-heading"
      >
        <AutoSectionBlockHeading id="auto-cartera-links-heading">
          Historial y cuentas
        </AutoSectionBlockHeading>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <li>
            <Link to="/history" className="underline hover:text-primary">
              Historial · ledger y fills
            </Link>
          </li>
          <li>
            <Link to="/accounts" className="underline hover:text-primary">
              Cuentas
            </Link>
          </li>
          <li>
            <Link
              to={CARTERA_RIESGO_PATH}
              className="underline hover:text-primary"
            >
              Riesgo abierto y límites
            </Link>
          </li>
        </ul>
      </section>
    </div>
  );
}
