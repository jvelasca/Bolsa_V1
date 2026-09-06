/**
 * Ayuda — mesa operativa diaria (Hoy · Mercado · Confirm).
 * Resumen para usuario básico primero; bloque experto después.
 * No duplica docs/engineering ni CURRENT_SYSTEM: solo lenguaje de producto.
 *
 * Sync: HELP_CONTENT_AS_OF · tip producto v2.10.1-beta (fase de pruebas / freeze UI).
 */

import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";

export const OPERATING_DESK_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  tipLabel: "v2.10.1-beta",
  phase: "pruebas",
} as const;

/** Primera tarjeta — lenguaje llano. */
export const OPERATING_DESK_SUMMARY = {
  title: "En pocas palabras",
  body: "Estás en fase de pruebas (BETA / demo) con tip v2.10.1-beta. La mesa diaria te dice qué mirar y qué firmar; no compra sola. Hoy resume; Mercado opera; Confirm es la única firma. Broker live real está cerrado: solo PAPER / LIVE VIRTUAL de estudio.",
  bullets: [
    "Hoy — inbox del día (requiere atención, oportunidades, posiciones). Detalles detrás de «Avanzado».",
    "Mercado — listas, gráfico con niveles y operativa del valor. Ranking / calidad ≠ orden de compra.",
    "Confirm — firmas tú (SEMI). La app propone; nunca envía órdenes sola.",
    "Misma situación = misma frase y mismo botón en Hoy, Mercado, Journal y Operaciones.",
    "AUTO cuenta = BETA: armar con «ACTIVAR AUTO»; execute paper solo si el entorno lo permite (off por defecto).",
    "Camino completo del valor: Ayuda → Flujo → «Del activo a la operación» (Estudio → análisis → compra → stops).",
  ],
} as const;

/**
 * Índice usuario básico: del alta del activo hasta operar (stops incluidos).
 * Se muestra en Guía / Flujo / Trading.
 */
export const OPERATING_DESK_ASSET_JOURNEY = {
  title: "Del activo a la operación (usuario básico)",
  intro:
    "Ruta completa en demo: añadir un valor, analizarlo, pasarlo a Estudio y operar con firma humana. No hace falta AUTO ni broker live.",
  steps: [
    {
      title: "1. Añadir el activo",
      body: "Instrumentos (importar / buscar) o watchlist: suscribe un índice, crea una lista personal o marca el ticker en Valores. Sincroniza datos si hace falta (Ayuda → Datos de mercado). Quitar de lista ≠ borrar de la base de datos.",
    },
    {
      title: "2. Abrir el gráfico (Visualizados)",
      body: "En Mercado, abre el valor: entra en Visualizados (pestañas). Visualizados = scratch de gráficos; no es todavía supervisión. Una pestaña por ticker.",
    },
    {
      title: "3. Indicadores técnicos (TA)",
      body: "Barra del gráfico → Indicadores: añade medias, oscillators, etc. Si hay Finalista #1 adoptado, el switch «Finalista #1» superpone ese setup. Ranking / gauges TA en Operativa son informativos, no permiso de compra.",
    },
    {
      title: "4. Análisis fundamental (FA)",
      body: "Instrumentos → ficha del valor (score, ratios, filings) o gauges FA en Operativa. Ayuda → Análisis del valor. FA explica calidad; no firma ni encola F3.",
    },
    {
      title: "5. Pasar a lista Estudio",
      body: "Selección → «A Estudio» / «Pasar a Estudio». Estudio = universo supervisable (membresía explícita). Sin Estudio no hay propuestas SEMI/AUTO para ese ticker. Abrir/cerrar el gráfico no cambia la membresía.",
    },
    {
      title: "6. Supervisar y leer el día",
      body: "En Estudio: Supervisión ON + Actualizar / Redescubrir si aplica. Asesor → Opiniones explica dictámenes del día; Asesor no compra. Hoy muestra si ese valor pide atención.",
    },
    {
      title: "7. (Opcional) Laboratorio y mandato",
      body: "En Lab puedes probar estrategias y Adoptar un Finalista → mandato en Trading (qué estrategia gobierna). No es obligatorio para una compra SEMI manual/propuesta, pero alinea indicadores TOP#1 y el panel DECISIÓN.",
    },
    {
      title: "8. Modo SEMI y propuesta",
      body: "Cuenta en SEMI (barra inferior → Cuentas · Operativa). En Mercado mira la frase operativa (preparada / disparada / …) y la CTA. Proponer F3, alarma Radar o chip F3 → cola Confirm. Ranking ≠ BUY.",
    },
    {
      title: "9. Comprar: firmar en Confirm",
      body: "Drawer Confirm o /confirm: revisas tamaño, stop del plan y riesgo; firmas tú. El tamaño sigue el riesgo del TradePlan (no un % inventado de caja). Tras el fill DEMO, Operaciones / Cartera muestran la posición.",
    },
    {
      title: "10. Stop loss, objetivos y trail",
      body: "Stop operativo = nivel del plan/posición (protección). T1 / T2 = objetivos (take-profit de lectura); «T1 alcanzado» ≠ ya gestionado. Trail = propuesta de seguimiento, no sustituye el stop ni firma sola. «Proteger» actualiza el stop operativo vía Confirm. Orden pendiente a precio ≠ stop de posición.",
    },
    {
      title: "11. Salir o reducir",
      body: "Salidas / reducciones también pasan por Confirm (SEMI). La columna «Salida» o avisos de Lab no ejecutan solos. Tras cerrar, revisa Operaciones, Journal y Fiscal.",
    },
  ],
  pause:
    "Si ves «entradas bloqueadas», Gate en veto o kill switch: no compres por atajos. LIVE capital está cerrado; execute paper off por defecto. En Confirm con venue live: pasarela LIVE VIRTUAL (híbrido) · SIMULADO · ≠ settlement real.",
} as const;

/** Ruta corta para tester / usuario básico. */
export const OPERATING_DESK_YOU_ARE_HERE = {
  title: "Cómo probar ahora (ruta corta)",
  body: "Atajo diario cuando el valor ya está en Estudio. Para el camino completo desde cero, usa «Del activo a la operación» arriba / en Flujo.",
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
      plain: "Stop operativo (stop loss)",
      meaning:
        "Nivel registrado en el plan/posición para proteger. No es automáticamente una orden stop en el broker.",
    },
    {
      plain: "T1 / T2 (objetivos / take-profit)",
      meaning:
        "Niveles de objetivo del plan. «T1 alcanzado» = el precio tocó el nivel; no implica que ya esté gestionado.",
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
      plain: "Estudio vs Visualizados",
      meaning:
        "Estudio = lista supervisable (membresía). Visualizados = pestañas de gráfico abiertas (scratch).",
    },
    {
      plain: "Asesor",
      meaning: "Explica (diario, opiniones). No firma ni encola F3.",
    },
    {
      plain: "LIVE / broker",
      meaning:
        "Demo = PAPER. LIVE capital cerrado. Cualquier LIVE de estudio es VIRTUAL / SIMULADO hasta APP 100%. En Confirm (venue live) verás la pasarela híbrida: telegrama al broker + por qué · banner LIVE VIRTUAL · CTA «Firmar · Ejecutar en LIVE VIRTUAL (simulado)». ≠ settlement real · ≠ Accept LIVE.",
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
    "Cabina tip v2.10.1-beta certificable en pruebas. Misma verdad operativa en varias superficies. Freeze de producto UI: sin paneles nuevos; execute paper off; LIVE capital bloqueado (VIRTUAL / diseño).",
  bullets: [
    "Hoy = Daily Desk: un inbox por atención (firmas, posiciones, cola). No es un segundo Mercado ni un panel de ranking en el chrome.",
    "Posición abierta → una verdad operativa (acción, CTA primaria, hint de ejecución) compartida en Mercado · Hoy · Journal · Operaciones.",
    "Sin posición → verdad de entrada (fase + CTA: preparar / revisar-confirmar / ver operaciones). Ranking ≠ BUY.",
    "Ruta de salida visual: Entrada → Proteger (stop) · T1 · T2 / trailing. Roles de lectura; Confirm sigue firmando salidas/reducciones.",
    "Bloqueo de entradas (kill + incidentes + veto de gate, fail-closed) alimenta la misma CTA/frase donde haya cockpit o ficha. Side-doors de proponer/comprar respetan el bloqueo.",
    "Orden pendiente alimenta el mismo hint de ejecución en Hoy / Mercado / Journal / Operaciones.",
    "Cola Confirm / «ya en Confirm» cuenta en la siguiente acción (no inventa un segundo botón de compra).",
    "protect_hint / thin «Salida» / Lab evaluate-exits ≠ autoridad de acción ni auto-exit. ExitPlan → permiso de salida → firma SEMI.",
    "Freeze pruebas: Confirm = firma · PAPER_D_EXECUTE off · AUTO execute off · Arm ≠ Execute · sin OCO producto · LIVE capital no · LIVE VIRTUAL ≠ settlement real.",
    "Accept estricto Camino D sigue abierto (medir ≠ Accept). Pasarela LIVE VIRTUAL híbrida vive dentro de Confirm (no mesa nueva); settlement real / thaw capital = PARKED.",
    "Fuera de esta franja (no esperar en UI): segundo Mercado, OpportunityScore, push, móvil, confirms individualizados, thaw capital.",
  ],
  checkListTitle: "Checklist rápido de honestidad (pruebas)",
  checkList: [
    "Misma posición + mismo gate → misma CTA y frase en Mercado y Journal.",
    "Misma orden pendiente → mismo hint en Hoy / Operaciones / cockpit.",
    "Gate VETO o entradas bloqueadas → no aparece «Comprar» por atajo.",
    "Sin TradePlan vivo → Hoy no inventa BUY (queda en vigilar / WATCH).",
    "Asesor no propone F3; Confirm no se bypasea desde el gráfico.",
    "Venue paper · paperDExecuteEnv false salvo demo opt-in explícita del owner.",
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
