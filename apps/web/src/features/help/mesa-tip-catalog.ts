/**
 * Catálogo de tips de mesa operativa (coach-marks «?» · no branding IA).
 * @see apps/web/src/features/help/mesa-tip-button.tsx
 */

export type MesaTipId =
  | "operativa-proponer"
  | "confirm-firmar"
  | "operativa-recomendacion"
  | "operativa-confirm-drawer"
  | "operativa-fit-chip"
  | "chart-f3-projection"
  | "confirm-ticket-preview"
  | "confirm-risk-signature"
  | "operational-console";

export type MesaTip = {
  id: MesaTipId;
  title: string;
  /** 2–4 frases cortas (scannable). */
  body: string;
  /** Ruta opcional (Link React Router). */
  linkTo?: string;
  linkLabel?: string;
};

export const MESA_TIPS: Record<MesaTipId, MesaTip> = {
  "operativa-proponer": {
    id: "operativa-proponer",
    title: "Proponer F3",
    body: "Envía una propuesta supervisada a la cola de Confirmar (Camino C). No ejecuta la orden: solo encola. Necesitas modo SEMI y el valor en Estudio. Luego firmas tú en Confirmar.",
    linkTo: "/confirm",
    linkLabel: "Ir a Confirmar",
  },
  "confirm-firmar": {
    id: "confirm-firmar",
    title: "Firmar en Confirmar",
    body: "SEMI: la app propone; tú firmas. Al aceptar, la operación se ejecuta contra la propuesta. Nunca se envían órdenes solas. Si cambias valor o sentido (compra↔venta), el sistema rechaza.",
    linkTo: "/confirm",
    linkLabel: "Abrir Confirmar",
  },
  "operativa-recomendacion": {
    id: "operativa-recomendacion",
    title: "Recomendación (Operativa)",
    body: "Pulso IO/TA/FA, dictamen y TOP #1 del Lab para el valor activo. Úsalo para decidir si Proponer F3. No sustituye la firma humana en Confirmar.",
    linkTo: "/trading",
    linkLabel: "Ir a Trading",
  },
  "operativa-confirm-drawer": {
    id: "operativa-confirm-drawer",
    title: "Cola Confirm (panel)",
    body: "Abre Confirmar al lado de la mesa (panel deslizante) sin salir del gráfico. El flujo SEMI es el mismo: preview → firmas tú. La página completa Confirmar sigue en el menú.",
    linkTo: "/confirm",
    linkLabel: "Abrir Confirmar (página)",
  },
  "operativa-fit-chip": {
    id: "operativa-fit-chip",
    title: "Acción package y Fit",
    body: "El chip LONG/WAIT/EXIT refleja la acción del DecisionPackage en cola (o vacío si aún no hay propuesta). Fit · PASS/VETO usa el gate/encaje ya calculado; si no hay dato, verás Fit · — (nunca se inventa PASS). Firmar sigue en Confirmar.",
    linkTo: "/confirm",
    linkLabel: "Ir a Confirmar",
  },
  "chart-f3-projection": {
    id: "chart-f3-projection",
    title: "Proyección F3 en gráfico",
    body: "Si hay una propuesta en cola Confirmar para el valor del gráfico, verás una línea horizontal de precio (p. ej. F3 · LONG @ …). Es solo una pista visual: no ejecuta. El botón Firmar abre Confirmar; la firma SEMI sigue siendo tuya.",
    linkTo: "/confirm",
    linkLabel: "Ir a Confirmar",
  },
  "confirm-ticket-preview": {
    id: "confirm-ticket-preview",
    title: "Preview de ticket",
    body: "Antes de firmar verás notional, comisión (perfil de la cuenta) y margen estimado (libre / orden). Es solo información: no envía la orden. Confirmar Intent inspecciona; Ejecutar en PAPER|LIVE sigue siendo la firma humana SEMI.",
    linkTo: "/confirm",
    linkLabel: "Abrir Confirmar",
  },
  "confirm-risk-signature": {
    id: "confirm-risk-signature",
    title: "Firma de riesgo",
    body: "Con TradePlan TRIGGERED, el tamaño es el riesgo del plan (qty / stop / pérdida €), no un % de caja. Superar el plan exige un motivo. Sin plan, el ticket no inventa stop ni R.",
    linkTo: "/confirm",
    linkLabel: "Abrir Confirmar",
  },
  "operational-console": {
    id: "operational-console",
    title: "Consola operacional",
    body: "Panel read-only de salud ops: OE-1 Autoeval, readiness OR-6, recon OI-6 y incidentes DEX-3. PASS ≠ permiso operar. No firma ni ejecuta — Confirm sigue siendo la única firma. Posiciones en Libro · Operaciones.",
    linkTo: "/operational-console",
    linkLabel: "Abrir Consola ops",
  },
};

export function getMesaTip(id: MesaTipId): MesaTip {
  return MESA_TIPS[id];
}

export const MESA_TIP_IDS = Object.keys(MESA_TIPS) as MesaTipId[];
