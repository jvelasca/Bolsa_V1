/**
 * Bloque compacto «Hoy en la mesa» — inbox + Mercado + Confirm (Ayuda → Guía).
 * Solo resumen de ruta diaria; el bloque experto vive en `OperatingDeskExpertDetails`.
 */

import { Link } from "react-router-dom";
import { OPERATING_DESK_SYNC } from "@/features/help/operating-desk-help";

/** Inbox del día (Hoy) → Mercado → firma en Confirmar. */
export function HoyEnLaMesaBlock() {
  return (
    <section
      className="rounded-md border border-border bg-muted/25 px-3 py-2.5"
      data-testid="hoy-en-la-mesa"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">Hoy</h3>
        <p className="text-[11px] text-muted-foreground">
          Fase {OPERATING_DESK_SYNC.phase} · {OPERATING_DESK_SYNC.tipLabel}
        </p>
      </div>
      <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>
          <strong className="text-foreground">Abrir Hoy</strong> (
          <Link to="/mesa" className="font-medium text-primary hover:underline">
            Hoy
          </Link>
          ) — inbox: requiere acción, oportunidades, vigilar. Detalles detrás de
          «Ver detalles».
        </li>
        <li>
          <strong className="text-foreground">Operar en Mercado</strong> (
          <Link
            to="/trading"
            className="font-medium text-primary hover:underline"
          >
            Mercado
          </Link>
          ) — listas → gráfico con niveles → operativa contextual. Ranking ≠
          orden. Misma frase/CTA que en Hoy y Journal.
        </li>
        <li>
          <strong className="text-foreground">Firmar</strong> en Confirm (drawer
          o{" "}
          <Link
            to="/confirm"
            className="font-medium text-primary hover:underline"
          >
            /confirm
          </Link>
          ) — SEMI: la app propone, tú firmas; nunca sola.
        </li>
      </ol>
      <p className="mt-2 text-xs text-muted-foreground">
        Calidad N/100 ≠ BUY. Confirm es la única firma. Trail = propuesta, no
        stop vigente. T1 alcanzado ≠ gestionado. Entradas bloqueadas / Gate en
        veto = no comprar por atajos. Estudio empty ≠ unavailable. Asesor
        explica; no ejecuta.{" "}
        <Link
          to="/mesa?view=posiciones"
          className="font-medium text-primary hover:underline"
        >
          Cartera · Posiciones
        </Link>{" "}
        y Journal viven en «Ver detalles» / Asesor.
      </p>
    </section>
  );
}
