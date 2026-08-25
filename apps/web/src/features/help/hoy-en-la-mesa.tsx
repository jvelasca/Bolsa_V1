/**
 * Bloque compacto «Hoy en la mesa» — 3 pasos SEMI (Ayuda → Guía / Flujo).
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

/** Tres pasos del día en mesa (Trading → Proponer → Confirmar). */
export function HoyEnLaMesaBlock() {
  return (
    <section
      className="rounded-md border border-border bg-muted/25 px-3 py-2.5"
      data-testid="hoy-en-la-mesa"
    >
      <h3 className="text-sm font-semibold text-foreground">Hoy en la mesa</h3>
      <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>
          <strong className="text-foreground">Ver valor</strong> en{" "}
          <RouteLink to="/trading">Trading</RouteLink> (gráfico + Operativa).
        </li>
        <li>
          <strong className="text-foreground">Leer recomendación</strong> /{" "}
          <strong className="text-foreground">Proponer F3</strong>.
        </li>
        <li>
          <strong className="text-foreground">Firmar</strong> en{" "}
          <RouteLink to="/confirm">Confirmar</RouteLink> (página o panel desde
          Trading) — SEMI: la app propone, tú firmas; nunca sola.
        </li>
      </ol>
      <p className="mt-2 text-xs text-muted-foreground">
        La tira <strong className="text-foreground">Hoy</strong> proyecta el
        Decision Board: BUY solo con TradePlan TRIGGERED. Sin plan → WATCH
        (nunca BUY). T1/T2 del plan son del TradePlan, no permiso. Thesis Health
        / Exit / Bracket son avisos, no permiso. Posición abierta
        (PositionState) ≠ TradePlan; thin ≠ PositionState. Ciclo OPEN / PARTIAL
        / PROTECTED / CLOSED; mark/reduce ≠ orden broker. ExitPlan = razones
        canónicas (≠ auto-exit; thin «Salida» ≠ ExitPlan). ExecutionPlan PAPER =
        plan de envío (≠ broker; ≠ ExecuteTrade). ExitPermission = veto de
        salida (≠ check_opening; ≠ auto-exit). Kill switch bloquea aperturas y
        AUTO; el desriesgo humano SEMI (salir / proteger) no se niega a ciegas.
        Tras un fill, Operaciones muestra stop / T1 / T2 del plan persistido;
        qty/P&L sigue siendo el holding (contabilidad). Al firmar en Confirmar,
        el tamaño es el riesgo del TradePlan (no % caja); superar el plan exige
        motivo. Cadena de salida: ExitPlan propone, ExitPermission valida, tú
        firmas en SEMI (no es auto-exit; thin «Salida» y Lab Señales no son este
        puerto). Tras un cierre firmado, el plan se reduce o cierra.{" "}
        <strong className="text-foreground">Operaciones</strong> (
        <RouteLink to="/operations">Libro · Operaciones</RouteLink>) abre por
        posiciones: R/stop/T1/T2, advisory Salida, CTAs Revisar/Reducir/Salir
        encolan Confirm (no ejecutan).{" "}
        <strong className="text-foreground">Proteger</strong> encola stop amend
        advisory cuando ExitPlan o protectPlan lo sugieren. Barra operativa
        global (Trading + Operaciones): patrimonio, P&amp;L, cola Confirm,
        excepciones. Cola de entradas con filtros por estado/gate/símbolo
        (Vigilar…Descartado). «No operar hoy» → Journal{" "}
        <code className="text-[10px]">session_verdict</code> — 0 BUY puede ser
        un día excelente.
      </p>
    </section>
  );
}
