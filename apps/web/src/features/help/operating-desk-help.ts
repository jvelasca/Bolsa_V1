/**
 * Ayuda — mesa operativa diaria (Hoy · Mercado · Confirm).
 * Resumen para usuario básico primero; bloque experto después.
 * No duplica docs/engineering ni CURRENT_SYSTEM: solo lenguaje de producto.
 *
 * Sync: HELP_CONTENT_AS_OF · tip producto v1.41.3-beta (fase de pruebas).
 */

import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";

export const OPERATING_DESK_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  tipLabel: "v1.41.3-beta",
  phase: "pruebas",
} as const;

/** Primera tarjeta — lenguaje llano. */
export const OPERATING_DESK_SUMMARY = {
  title: "En pocas palabras",
  body: "Estás en fase de pruebas (BETA / demo). La mesa diaria te dice qué mirar y qué firmar; no compra sola. Hoy resume; Mercado opera; Confirm es la única firma.",
  bullets: [
    "Hoy — inbox del día (requiere atención, oportunidades, posiciones). Detalles detrás de «Avanzado».",
    "Mercado — listas, gráfico con niveles y operativa del valor. Ranking / calidad ≠ orden de compra.",
    "Confirm — firmas tú (SEMI). La app propone; nunca envía órdenes sola.",
    "Misma situación = misma frase y mismo botón en Hoy, Mercado, Journal y Operaciones.",
    "AUTO cuenta = BETA: armar con «ACTIVAR AUTO»; execute paper solo si el entorno lo permite (off por defecto). Consola → dry-run auto-propose mide hits sin ejecutar.",
  ],
} as const;

/** Ruta corta para tester / usuario básico. */
export const OPERATING_DESK_YOU_ARE_HERE = {
  title: "Cómo probar ahora (usuario básico)",
  body: "Ruta corta para validar la mesa en demo. No hace falta AUTO ni broker live.",
  steps: [
    "Cuenta DEMO activa · modo SEMI (barra inferior → Cuentas · Operativa).",
    "Valor en Estudio (universo supervisable). Sin Estudio no hay propuestas SEMI para ese ticker.",
    "Abre Hoy (/mesa): lee el inbox. Si pide acción, entra o ve a Mercado.",
    "En Mercado: mira la frase operativa (preparada / disparada / posición) y el botón principal.",
    "Proponer F3 o alarma Radar → Confirmar (drawer o /confirm) → firmas tú.",
    "Tras fill: Operaciones / Cartera muestran stop y objetivos del plan (si había plan). Trail y T1 son pistas, no órdenes.",
  ],
  pause:
    "Si ves «entradas bloqueadas», Gate en veto o kill switch: no intentes comprar por atajos (alarma, gráfico, Operar). Confirmar sigue siendo la firma; el bloqueo es deliberado.",
} as const;

/** Reglas de lectura diaria (básico). */
export const OPERATING_DESK_READ_RULES = {
  title: "Qué significa lo que ves",
  items: [
    {
      plain: "Calidad N/100 o ranking",
      meaning: "Informativo. No es permiso de compra.",
    },
    {
      plain: "Preparada / Disparada / Propuesta / Confirmada",
      meaning:
        "Fase de entrada antes de tener posición. Solo Confirmada implica firma hecha.",
    },
    {
      plain: "Stop operativo",
      meaning:
        "Nivel registrado en el plan/posición. No es automáticamente una orden stop en el broker.",
    },
    {
      plain: "T1 alcanzado",
      meaning: "El precio tocó el objetivo. No implica que ya esté gestionado.",
    },
    {
      plain: "Trail / trailing",
      meaning:
        "Propuesta de seguimiento. No sustituye el stop vigente ni firma sola.",
    },
    {
      plain: "Orden pendiente a precio",
      meaning:
        "Límite de entrada/salida pendiente. No protege la posición como un stop.",
    },
    {
      plain: "Asesor",
      meaning: "Explica (diario, opiniones). No firma ni encola F3.",
    },
  ],
} as const;

/**
 * Bloque experto — nombres de producto y coherencia entre pantallas.
 * Sin volcar ADRs ni releivos; enlaces de sync van al pie de Ayuda.
 */
export const OPERATING_DESK_EXPERT = {
  title: "Información avanzada (experto / tester)",
  intro:
    "Serie de proyección de mesa (Daily Operating → Operational Honesty) cerrada para pruebas. Misma verdad operativa en varias superficies; sin motores de ejecución nuevos en esta franja.",
  bullets: [
    "Hoy = Daily Desk: un inbox por atención (firmas, posiciones, cola). No es un segundo Mercado ni un panel de ranking en el chrome.",
    "Posición abierta → una verdad operativa (acción, CTA primaria, hint de ejecución) compartida en Mercado · Hoy · Journal · Operaciones.",
    "Sin posición → verdad de entrada (fase + CTA: preparar / revisar-confirmar / ver operaciones). Ranking ≠ BUY.",
    "Ruta de salida visual: Entrada → Proteger (stop) · T1 · T2 / trailing. Roles de lectura; Confirm sigue firmando salidas/reducciones.",
    "Bloqueo de entradas (kill + incidentes + veto de gate, fail-closed) alimenta la misma CTA/frase donde haya cockpit o ficha. Side-doors de proponer/comprar respetan el bloqueo.",
    "Orden pendiente alimenta el mismo hint de ejecución en Hoy / Mercado / Journal / Operaciones.",
    "Cola Confirm / «ya en Confirm» cuenta en la siguiente acción (no inventa un segundo botón de compra).",
    "protect_hint / thin «Salida» / Lab evaluate-exits ≠ autoridad de acción ni auto-exit. ExitPlan → permiso de salida → firma SEMI.",
    "Freeze de pruebas: Confirm = firma · PAPER_D_EXECUTE off · AUTO execute off · sin drag entry/exit · sin OCO producto.",
    "Fuera de esta franja (no esperar en UI): segundo Mercado, OpportunityScore, thaw estricto, push, móvil, confirms individualizados.",
  ],
  checkListTitle: "Checklist rápido de honestidad (pruebas)",
  checkList: [
    "Misma posición + mismo gate → misma CTA y frase en Mercado y Journal.",
    "Misma orden pendiente → mismo hint en Hoy / Operaciones / cockpit.",
    "Gate VETO o entradas bloqueadas → no aparece «Comprar» por atajo.",
    "Sin TradePlan vivo → Hoy no inventa BUY (queda en vigilar / WATCH).",
    "Asesor no propone F3; Confirm no se bypasea desde el gráfico.",
  ],
} as const;

/** Mapa corto L1 para Guía / Flujo (básico). */
export const OPERATING_DESK_NAV = {
  title: "Navegación del día",
  items: [
    {
      label: "Hoy",
      route: "/mesa",
      plain: "¿Qué debo hacer hoy? Inbox + Avanzado.",
    },
    {
      label: "Mercado",
      route: "/trading",
      plain: "Terminal: listas, gráfico, operativa, operaciones del valor.",
    },
    {
      label: "Cartera",
      route: "/mesa?view=posiciones",
      plain: "Posiciones / órdenes / historial (también bajo Avanzado).",
    },
    {
      label: "Confirmar",
      route: "/confirm",
      plain: "Firma humana SEMI (también drawer desde mesa).",
    },
    {
      label: "Asesor",
      route: "/research",
      plain: "Explica el día y opiniones; no ejecuta.",
    },
    {
      label: "Laboratorio",
      route: "/backtests",
      plain: "Investigar / simular (universo LAB; no es la mesa diaria).",
    },
  ],
} as const;
