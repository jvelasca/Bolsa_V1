/**
 * Bloque compacto «Hoy en la mesa» — inbox + Mercado + Confirm (Ayuda → Guía).
 */

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

function RouteLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="font-medium text-primary hover:underline">
      {children}
    </Link>
  );
}

/** Inbox del día (Hoy) → Mercado → firma en Confirmar. */
export function HoyEnLaMesaBlock() {
  return (
    <section
      className="rounded-md border border-border bg-muted/25 px-3 py-2.5"
      data-testid="hoy-en-la-mesa"
    >
      <h3 className="text-sm font-semibold text-foreground">Hoy</h3>
      <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>
          <strong className="text-foreground">Abrir Hoy</strong> (
          <RouteLink to="/mesa">Hoy</RouteLink>) — inbox: requiere acción,
          oportunidades, vigilar. Detalles detrás de «Ver detalles».
        </li>
        <li>
          <strong className="text-foreground">Operar en Mercado</strong> (
          <RouteLink to="/trading">Mercado</RouteLink>) — listas → gráfico con
          niveles → operativa contextual. Ranking ≠ orden.
        </li>
        <li>
          <strong className="text-foreground">Firmar</strong> en Confirm (drawer
          o <RouteLink to="/confirm">/confirm</RouteLink>) — SEMI: la app
          propone, tú firmas; nunca sola.
        </li>
      </ol>
      <p className="mt-2 text-xs text-muted-foreground">
        Prioridad N/100 ≠ BUY. Confirm es la única firma. Trail = propuesta, no
        stop vigente. T1 alcanzado ≠ gestionado. Estudio empty ≠ unavailable.
        Asesor explica; no ejecuta.{" "}
        <RouteLink to="/mesa?view=posiciones">Cartera · Posiciones</RouteLink> y
        Journal viven en «Ver detalles» / Asesor.
      </p>
    </section>
  );
}
