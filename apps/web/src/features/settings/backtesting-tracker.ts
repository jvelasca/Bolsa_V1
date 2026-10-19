/**
 * Tracker Ayuda → Backtesting.
 * Resumen no técnico primero; pantallas, seguimiento de plataforma y detalle después.
 * El detalle vivo está en docs (no duplicar aquí el lifecycle completo).
 *
 * Sync embudo 5 etapas + soft-ACK + Lista AUTO frescura v1.3 + DÍA D v0.11 + CORE-R v1.13 + CORE-B v0.2 + ADR-019 universos (2026-08-03).
 *
 * @see docs/HELP.md
 * @see docs/engineering/research-lifecycle.md
 * @see docs/engineering/list-auto-ops-2026-07-29.md
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md
 * @see docs/engineering/dual-universes-lab-trading-design-2026-08-02.md
 * @see docs/adr/019-dual-universes-lab-vs-trading.md
 * @see docs/engineering/operativa-test-plan-2026-07-31.md
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 * @see docs/engineering/session-handoff-2026-08-01.md
 * @see docs/adr/009-backtesting-research-platform-h0.md
 */

import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";

export const BACKTESTING_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  lifecycleDoc: "docs/engineering/research-lifecycle.md",
  improvementRoadmap:
    "docs/engineering/improvement-roadmap-post-audits-2026-08-02.md",
  stabilityProtocol:
    "docs/engineering/stability-campaign-protocol-2026-08-02.md",
  handoffDoc: "docs/engineering/session-handoff-2026-08-01.md",
  listAutoOps: "docs/engineering/list-auto-ops-2026-07-29.md",
  listsUniverses: "docs/engineering/lists-universes-design-2026-07-30.md",
  funnelHandoff: "docs/engineering/backtesting-funnel-handoff-2026-07-29.md",
  diaDPremises: "docs/engineering/backtesting-dia-d-premises-2026-07-31.md",
  dualUniverses:
    "docs/engineering/dual-universes-lab-trading-design-2026-08-02.md",
  adrUniverses: "docs/adr/019-dual-universes-lab-vs-trading.md",
  operativaTestPlan: "docs/engineering/operativa-test-plan-2026-07-31.md",
  adrH0: "docs/adr/009-backtesting-research-platform-h0.md",
  dataArch: "docs/BACKTESTING_DATA_ARCHITECTURE.md",
  adrEvidence: "docs/adr/018-fase2-evidence-store-v0.md",
  route: "/backtests",
} as const;

/** Orientación en lenguaje llano (primera tarjeta). */
export const BACKTESTING_SUMMARY = {
  title: "En pocas palabras",
  body: "Backtesting responde: «si hubiera seguido esta regla en el pasado, ¿qué habría pasado?». No es una predicción ni una orden de compra. Usas datos históricos de tu base local, eliges un valor (o una lista), una estrategia y un periodo; la app simula operaciones y te muestra el resultado en lenguaje claro.",
  bullets: [
    "Pantalla principal: Probar estrategia (valor o lista + matriz; periodo/capital en Opciones avanzadas).",
    "Play (ciclo ON): 1 Probar genéricas → 2 Coach (ACK¹) → 3 Lab → 4 Revalidar (ACK final) → 5 Finalistas. Lista = mismo × ticker.",
    "⋯ = diagrama de flujo con checks (Auto-ACK, Pausar ACK, atajo semifinal OFF, Lab si no mejora = no grabar).",
    "Lista AUTO: puedes ir a Trading mientras corre (barra de estado abajo). Tras reinicio, omite si no cambió nada.",
    "Universo → Lista: miembros con resumen (Finalistas / ★ / Lab / AUTO). Clic = pestaña Valor. Soft-cap 40 + confirm; filtro opcional «solo sin Finalistas».",
    "Finalistas: Checklist = demo activa (A); Rastreador = Radar (B); Proponer = Supervisado F3 (C). Distintos.",
    "Tras Lab, Finalistas/Coach muestran resumen Hold-out/WF/CPCV (`coachFacts.labEvidence`, Q3.2).",
    "DÍA D: fecha en Probar → Play (F-D sin pisar F-hoy) → Verificar D→hoy → reconciliación SAME/DRIFT (ADR-021).",
    "Universos: LAB = estudiar/verificar · TRADING = invertir DEMO + rail Coach. docs/adr/019-dual-universes-lab-vs-trading.md",
    "Monitor Finalistas: hub Probar / Ayuda — TOP + DEMO retorno % + adopción + cola CORE-R. Solo lectura; no es auto-paper.",
    "Cuentas: una Activa TRADING · hoy solo DEMO · Cartera LAB = sandbox research. docs/engineering/account-premises-demo-vs-paper-2026-07-31.md",
    "Unificación Research→Radar: docs/engineering/research-radar-unification-2026-07-31.md",
  ],
} as const;

export const BACKTESTING_YOU_ARE_HERE = {
  title: "Cómo empezar (usuario básico)",
  body: "Ruta corta para la primera prueba útil. No hace falta Optimizar a mano ni paper el primer día.",
  steps: [
    "Abre Backtesting (/backtests) → pestaña Probar estrategia.",
    "Elige un valor con histórico (periodo/capital en Opciones avanzadas; se recuerda tras reinicio).",
    "Pulsa Play (ciclo completo ON) → mapa 5 etapas hasta Finalistas (solo guarda TOP con mejora Lab).",
    "Lista IBEX/S&P/Estudio: modo Lista + Play = Lista AUTO (tandas ~40). Pref «Omitir si Finalistas frescos» ON. ≠ «Probar lista».",
    "En Lista valores, ojea el resumen por ticker; clic abre Valor/Detalle.",
    "Mientras corre: ve a Trading — footer con progreso. Tras reinicio, un 2º Play debe Omitir (histéresis: 1 barra diaria no fuerza re-embudo).",
    "Desde Finalistas: Checklist → demo activa (A), Rastreador → Screeners (B), o Proponer → Supervisado F3 (C).",
  ],
  pause:
    "Paper D (execute) es otra puerta — off por defecto (`PAPER_D_EXECUTE`). Primero entiende una prueba simple, Finalistas y el checklist.",
} as const;

/**
 * Explicación usuario (sin jerga): cómo el Laboratorio elige la operativa y los
 * parámetros de cada valor, cómo se confirma y cómo se decide entrar/salir.
 *
 * Es contenido de producto (Ayuda), no un doc de ingeniería: no promete rentabilidad
 * y declara los límites (NO CONFIRMADO / INCONCLUSIVE / SIMULADO).
 * Δ motor = 0 · Δ decisión = 0.
 */
export const BACKTESTING_STRATEGY_CHOICE_GUIDE = {
  title: "Cómo se elige la operativa de un valor (DÍA D), en sencillo",
  body: "La app no adivina el «mejor indicador»: prueba varias familias de estrategia con datos pasados, mide cada una en la parte del histórico que NO ha visto y solo deja como Finalista la que supera los controles. Después verifica, día a día, si lo que el motor habría hecho coincide con lo que de verdad pasó. Elegir bien no garantiza ganancias.",
  sections: [
    {
      title: "1. El embudo: de muchas reglas a una propuesta",
      bullets: [
        "Probar: eliges un valor (o una lista) y un periodo. Se prueban las estrategias genéricas (tendencia, momentum, reversión a la media, ruptura, combinadas) y las tuyas o Finalistas del valor.",
        "Coach: ordena las candidatas y deja el TOP ★ del valor (máximo 3, sin duplicar familia). El ranking es local y determinista; la IA solo narra y puede vetar con motivo. El Lab no empieza hasta que confirmas (ACK).",
        "Lab: para cada familia se busca la mejor combinación de parámetros (p. ej. medias 10/20/30 × 50/100/150; RSI 7/14/21 × 20/30 × 70/80; MACD 12/26/9 y 8/21/5). Esa búsqueda usa solo la primera parte del histórico (in-sample, IS).",
        "Revalidar: el campeón se mide en lo que no vio (hold-out, walk-forward y CPCV) y se calcula la probabilidad de que el buen resultado sea suerte (PBO) y el Sharpe deflactado (DSR). Si no aguanta, no se graba.",
        "Finalistas: solo se guarda lo que tiene runId, evidencia lab_validated y tu ACK final. El #1 es la operativa propuesta para ese valor, no una orden de compra.",
      ],
    },
    {
      title: "2. Cómo se mide «mejor» (sin magia)",
      bullets: [
        "Objetivo del Lab: score = retorno % − 0,25 × peor caída %. La misma vara para todos los candidatos, y queda registrada en el run.",
        "In-sample (IS): solo la primera parte del histórico. Fuera de muestra (OOS): el tramo final que el campeón no usó para elegir parámetros (10–40 %, con mínimo de 50 barras IS y 30 OOS).",
        "Walk-forward: 2–5 pliegues (por defecto 3). Se entrena con lo antiguo y se prueba con lo siguiente; se resume WFE (OOS/IS) y el % de pliegues positivos.",
        "CPCV: 4–6 grupos, 2 grupos de prueba, con purga y embargo (por defecto 5 barras) para no colar información del futuro.",
        "PBO (probabilidad de overfitting): <0,5 baja · 0,5–0,7 elevada · ≥0,7 alta. DSR: Sharpe corregido por haber probado muchas variantes (se exige ≥0,7).",
        "El campeón se elige pensando en OOS cuando todos los candidatos tienen OOS medido; un OOS con muy pocas operaciones (menos de 2) se penaliza, no se premia.",
      ],
    },
    {
      title: "3. Cómo se confirma (puertas que no se saltan)",
      bullets: [
        "Siete puertas del Lab: backtest (campeón con resultado positivo), robustness (PBO + CPCV), walk_forward (WFE medido), oos (resultado fuera de muestra), risk (drawdown medido), dsr (≥0,7) y coach (la aporta la fase Coach).",
        "Fail-closed: si una métrica falta, la puerta queda NOT_EVALUATED, que NO es PASS. Sin runId y sin evidencia lab_validated no hay Finalista.",
        "Confirmación humana: ACK en Coach y ACK final en Revalidar antes de escribir Finalistas. Watchlist no es supervisión: el valor debe estar en Estudio.",
        "DÍA D (fecha pasada): el embudo usa solo datos ≤ D y guarda un TOP de experimento (F-D) sin pisar tus Finalistas reales (F-hoy). «Verificar D→hoy» repite la operativa congelada F-D#1 (lookback 3 años + arrastre de posición) y la compara con F-hoy: SAME / DRIFT / INCONCLUSIVE.",
        "Evidencia DÍA-D del motor: 4 capas (ventana operativa; declarado vs ejecutado; evidencia fuera de muestra; ejecución real, reservada). El veredicto global siempre es NO CONFIRMADO: «CONFIRMED» no existe en el código.",
        "Suelos de muestra declarados: 5 ciclos por valor, acierto ≥0,5, 20 ciclos para «soportado» y 32 para «fuerte». Un dato ausente se muestra como «sin dato»; nunca se rellena con 0.",
        "La ventana PAPER se construye con hechos durables (fills, ciclos, journal), no con el permiso del día. Mientras no haya operación suficiente sigue INCONCLUSIVE: la app lo dice, no lo maquilla.",
      ],
    },
    {
      title: "4. Cómo se decide ENTRAR",
      bullets: [
        "Señal de la estrategia (barra diaria al cierre) → se descarta duplicada o caducada, con su motivo en el journal.",
        "Ranking explicable: edge 30 %, robustez 20 %, encaje de régimen 15 %, momentum 10 %, liquidez 10 %, riesgo/recompensa 10 %, calidad de ejecución 5 %. Un componente ausente vale 0 (no se inventa).",
        "Solo se evalúan las mejores del tick (TOP_N = 5 por defecto) y se exige un edge mínimo (0,30 por defecto). Quedar fuera del TOP no es «mala señal»: es «no evaluada».",
        "Barrera de régimen POR VALOR: un LONG no se abre en tendencia bajista confirmada (BEAR_TREND); RISK_OFF/CRISIS son vetos globales; UNKNOWN no opera (fail-closed). Así un valor bajista no veta a los demás.",
        "Geometría: stop = entrada − 1,5 × ATR (o el stop propio de la estrategia); T1 = 1R y T2 = 2R si la estrategia no aporta objetivos. Sin stop ni ATR verificable no hay entrada (atr_unknown).",
        "Tamaño por riesgo, no por caja: máximo 1 % del patrimonio por operación, 20 % por posición, 40 % por sector y 6 % de riesgo abierto total; comisión, spread y slippage entran en el presupuesto.",
        "El plan (TradePlan) pasa por el permiso de apertura y se convierte en orden/reserva; en SEMI lo firmas tú en Confirmar; en AUTO solo se ejecuta en PAPER (dinero virtual).",
      ],
    },
    {
      title: "5. Cómo se decide SALIR",
      bullets: [
        "Se revisa en cada tick contra la posición, con un orden único de prioridad: kill switch > salida por régimen > salida por riesgo > manual > stop estructural > tesis invalidada > riesgo de cartera > T1 > T2 > trailing > tiempo.",
        "Stop estructural: si el precio toca el stop vigente, se cierra. T1/T2: con la plantilla por defecto (moderate) se reduce un 30 % en T1 y otro 30 % en T2; T2 no da por hecho T1.",
        "Trailing: el stop solo se aprieta a favor (ratchet); nunca se aleja. Tiempo: si se agota el plazo del plan o el techo de mantenimiento (45 días por defecto), se plantea la salida.",
        "Tesis invalidada: el nivel se fijó al nacer la posición y se confirma con el peor precio adverso registrado (MAE), no solo con el precio de ahora.",
        "Gobernador: kill switch, modo solo-salidas y RISK_OFF pueden ordenar desriesgo; las salidas protectoras no se bloquean por una reconciliación en drift.",
        "En SEMI, reducir o salir también se firma en Confirmar. Los avisos del Lab o la columna «Salida» no ejecutan solos; en AUTO el cierre se hace en PAPER.",
      ],
    },
  ],
  notes: [
    "Esto explica el criterio, no promete rentabilidad: un backtest bueno puede fallar en el futuro y la app lo declara (NO CONFIRMADO / INCONCLUSIVE).",
    "Toda la operativa es SIMULADA (PAPER / dinero virtual). No se envían órdenes reales a ningún bróker.",
    "La evidencia agregada DÍA-D es del VALOR; lo exacto es la fila del ciclo verificado (con su identidad de estrategia).",
    "Dónde verlo: Laboratorio → Finalistas (checklist) · Auto-monitor → tarjeta P3 «Estrategia que sustenta la señal» · panel DÍA-D.",
    "Doc: docs/HELP.md · docs/engineering/explicacion-estrategia-p3-p4-2026-10-16.md · docs/adr/021-dia-d-reconciliation.md · ADR-046/047.",
  ],
} as const;

/** Cómo arrancar Backtesting DÍA D (verificación D→hoy). */
export const BACKTESTING_DIA_D_GUIDE = {
  title: "Backtesting DÍA D — cómo arrancar",
  body: "Simula que «hoy» es una fecha pasada (D), construye un TOP experimento (F-D) solo con datos ≤ D sin pisar Finalistas operativos (F-hoy), y verifica en LAB qué habría pasado de D a hoy. Al final: reconciliación SAME/DRIFT vs F-hoy #1 (ADR-021).",
  steps: [
    "Opcional pero recomendado: con D = Hoy, deja Finalistas operativos (F-hoy) ya guardados para el valor.",
    "Backtesting → selector «Hoy · fecha» / «DÍA D · fecha» → elige una fecha pasada.",
    "Play (ciclo completo): el embudo usa solo datos ≤ D y guarda F-D (experimento). F-hoy en BD no se pisa.",
    "En Finalistas verás aviso de experimento F-D. Pulsa «Verificar D→hoy» (usa F-D #1 congelada).",
    "Análisis técnico LAB: banner Verificar + película (Cartera LAB; no escribe la DEMO).",
    "Modo Auto / Semi / Manual como siempre. Revisa Evidence + panel «Reconciliación DÍA D» (SAME_* / DRIFT_*).",
    "Opcional: Pantalla completa · Narrar con IA · Guardar Evidence · Salir verificación.",
  ],
  notes: [
    "F-hoy = Finalistas operativos (BD). F-D = TOP experimento local (bolsa-dia-d-experiment-top-v1). V = sesión Verificar D→hoy.",
    "Si F-D #1 ≈ F-hoy #1 y OOS va bien → SAME_CONFIRMED. Si es distinta y OOS bien → DRIFT_BETTER (revisar Finalistas).",
    "Contrafactual: si F-hoy#1 ≠ F-D#1, Verify también simula F-hoy#1 en D→hoy y muestra Δ pp en reconciliación.",
    "El origen temporal se ve junto a «Backtesting»: Hoy = calendario real; DÍA D = embudo ≤ esa fecha.",
    "Favoritos ★ de fechas se guardan en este dispositivo.",
    "Sin fecha en el pasado no aparece el CTA «Verificar D→hoy».",
    "Semi/Manual: solo Aceptar ejecuta el fill. Rechazar un buy anula también su sell.",
    "FA as-of / Evidence / fullBleed: igual que antes (ADR-019 LAB).",
    "Doc: docs/adr/021-dia-d-reconciliation.md · premisas DÍA D · pnpm test:operativa",
  ],
} as const;

/** Monitor + cola CORE-R (reevaluación; no auto-paper). */
export const BACKTESTING_CORE_R_GUIDE = {
  title: "CORE-R / Monitor — cola de revisión",
  body: "Tras Lista AUTO (o con DEMO vinculada al TOP), el Monitor encola juicios a revisar. No pisa Finalistas ni despliega paper. No cambia el mandato de Trading hasta que aceptes la propuesta (SEMI) o lo cambies a mano.",
  steps: [
    "Abre Monitor: hub Probar (desplegable) o Ayuda → Backtesting (panel debajo de DÍA D).",
    "Elige la lista (ideal: «Estudio» canónica, o IBEX). Filas con TOP muestran demo/paper + retorno % si hay cuenta vinculada.",
    "Pulsa «Encolar revisiones»: mezcla informe Lista AUTO + PnL DEMO ≤ −5% (Lab) / ≤ −10% (cambio).",
    "Abre Lab / Finalistas / Checklist desde la cola; marca «Hecho» al cerrar.",
    "SEMI + «Valorar cambio»: «Adoptar» abre mandato TOP#1 (ADR-020). AUTO no auto-adopta.",
    "Opcional: «Narrar cola» (heurística; LLM si hay Ollama).",
    "Opcional: «Auto-sync» / Supervisión ON (3 cadencias en ···; prefiere «Estudio») · chip · toast · «Hecho todos».",
  ],
  notes: [
    "Sandbox DÍA D ≠ DEMO live. CORE-R lee DEMO/paper vinculadas al TOP (prefer simulated).",
    "Cola/informe: localStorage = cache; BD = SoT multi-dispositivo.",
    "Cron servidor opcional (CORE_R_CRON_ENABLED): informe BD + PnL DEMO (−5/−10); toast remoto multi-dispositivo al hidratar.",
    "Chip barra / toast «Abrir Monitor» → Ayuda · Monitor. También /backtests?tab=run&focus=monitor",
    "Hecho todos cierra abiertas de la lista actual (no borra; clearDone limpia done).",
    "Toast solo si added > 0 (sin ruido en ticks vacíos).",
    "Reanálisis LAB ≠ cambio de mandato TRADING. AUTO execute no auto-adopta.",
    "No es auto-paper D. No overwrite de TOP active.",
    "Ops: pnpm test:operativa · ISSUES.md · CORE-R · list-auto-ops § CORE-R / §5.2",
  ],
} as const;

export const BACKTESTING_SCREENS = [
  {
    id: "probar",
    title: "Probar estrategia",
    plain:
      "Wizard: valor o lista + matriz. Periodo/capital en Opciones avanzadas.",
    detail:
      "Play ciclo = embudo hasta Finalistas. Lista + Play = Lista AUTO (frescura/Omitido; keep-alive en Trading). «Probar lista» = Fase C.",
  },
  {
    id: "dia-d",
    title: "Backtesting DÍA D",
    plain:
      "Fecha «hoy simulado» en Probar → embudo ≤ D → Finalistas #1 «Verificar D→hoy» → LAB Análisis técnico.",
    detail:
      "Cartera LAB ≠ DEMO. Manual/Semi/Auto. Pantalla completa efímera + Guardar Evidence. ADR-019 / dual-universes-lab-trading-design.",
  },
  {
    id: "resultado",
    title:
      "Resultado (Análisis técnico / fundamental / Coach / Lab / Finalistas / Lista AUTO)",
    plain:
      "Pestañas del panel derecho: técnico (gráfico/replay), fundamental (Tarjeta Valor), TOP ★, laboratorio y campaña.",
    detail:
      "Análisis técnico = Detalle clásico (sin FA mezclado). Análisis fundamental = Tarjeta Valor + Composite + filings. Finalistas: Checklist (A) y Proponer (C).",
  },
  {
    id: "estrategias",
    title: "Biblioteca",
    plain: "Genéricas, Mis estrategias y Finalistas del valor.",
    detail:
      "Lista first; filtros alcance/TF/origen. Paper solo vía checklist del resultado (sin atajo Paper).",
  },
  {
    id: "optimizar",
    title: "Lab · Optimizar",
    plain: "Busca mejores parámetros; no declara «lista para invertir».",
    detail:
      "Mismo Lab del embudo. Empty state → Coach. Memoria CORE-B v0.2 (meseta/pico + familia por horizonte). Lab no escribe Finalistas → Reanalizar con Coach.",
  },
  {
    id: "anteriores",
    title: "Pruebas anteriores / Research",
    plain: "Histórico de lo ya ejecutado para revisar y comparar.",
    detail:
      "Lista acotada (default 20, ⚙). Enlace al ledger Research. Vacío → CTA Probar.",
  },
  {
    id: "monitor-ayuda",
    title: "Monitor Finalistas",
    plain: "Tablero de estado por lista: TOP, paper, último Proponer.",
    detail:
      "En hub Probar (desplegable abajo) y Ayuda → Backtesting. TOP + DEMO % + cola CORE-R (Encolar / Narrar / Auto-sync). Solo lectura; no auto-paper D.",
  },
] as const;

/** Seguimiento de plataforma — badges alineados con research-lifecycle.md. */
export const BACKTESTING_TRACKING = [
  {
    id: "ui-abc",
    title: "Wizard + resultado + listas",
    status: "listo" as const,
    plain:
      "Hub Probar (matriz + Coach + Lab + Finalistas) operativo; catálogo 21 genéricas.",
  },
  {
    id: "full-cycle",
    title: "Play ciclo completo (1 valor)",
    status: "listo" as const,
    plain:
      "⋯ diagrama de flujo: ACK¹→Lab, Lab sin mejora=no grabar, ACK final. Soft-ACK / Pausar. Atajo semifinal OFF.",
  },
  {
    id: "list-auto",
    title: "Lista AUTO (ciclo × N)",
    status: "listo" as const,
    plain:
      "Lista + Play: embudo × ticker (tandas de 40; sin truncar; tope 500). Keep-alive + barra Trading. Frescura v1.3. ≠ Fase C.",
  },
  {
    id: "list-auto-freshness",
    title: "Frescura / Omitido (post-reinicio)",
    status: "listo" as const,
    plain:
      "Huella local+DB; histéresis lastBar (1d ≤5d → bar_hysteresis; stamp no desliza). Reevaluar resto = forzar.",
  },
  {
    id: "dia-d",
    title: "Backtesting DÍA D (v0.11 · ADR-019)",
    status: "listo" as const,
    plain:
      "asOf + gate + full-bleed efímero + Evidence en LAB. Salir verificación restaura el hub. Cartera LAB ≠ DEMO.",
  },
  {
    id: "lab-core-b",
    title: "Lab memoria (CORE-B v0.2)",
    status: "listo" as const,
    plain:
      "Adopción → espacio guiado (meseta ancha / pico estrecho). Sin semilla: familia = adopción → horizonte perfil → SMA.",
  },
  {
    id: "finalists-to-tracker",
    title: "Finalistas → Rastreador (B)",
    status: "listo" as const,
    plain:
      "CTA Rastreador crea TrackerDefinition (assisted) y abre Screeners. Camino B ≠ A ≠ C. Ver research-radar-unification.",
  },
  {
    id: "finalists-paper",
    title: "Finalistas → checklist paper",
    status: "listo" as const,
    plain:
      "CTA Checklist en Finalistas (runId) abre Detalle + checklist. Camino A manual; no es auto-paper D.",
  },
  {
    id: "finalists-supervised",
    title: "Finalistas → Supervisado F3",
    status: "listo" as const,
    plain:
      "CTA Proponer (lab_validated): FA+perfil → cola F3 (origen Finalistas) + foco Confirm. Camino C ≠ A ≠ D.",
  },
  {
    id: "strategy-monitor",
    title: "Monitor Finalistas (MVP)",
    status: "listo" as const,
    plain:
      "Hub Probar + Ayuda: TOP + DEMO retorno % + Proponer. Cola CORE-R (Encolar / Narrar / cron shell). Solo lectura; D congelado.",
  },
  {
    id: "core-r-queue",
    title: "CORE-R cola revisión (Monitor)",
    status: "listo" as const,
    plain:
      "ADR-024: Estudio canónica + Supervisión ON + Adoptar SEMI · BD SoT. Sin overwrite TOP ni auto-paper D.",
  },
  {
    id: "lab-ui",
    title: "Laboratorio Optimizar (P3–P9)",
    status: "cerrado" as const,
    plain:
      "OOS/WF, checklist pre-demo, EdgeReport y adopt están hechos; el track UI del lab está en pausa deliberada.",
  },
  {
    id: "fase2",
    title: "Fase 2 — evidencia científica (P2.A–P2.F)",
    status: "listo" as const,
    plain:
      "Hipótesis, evidencia, creencia y nodos de conocimiento existen en backend (sin auto-live). La UI cognitiva profunda sigue congelada.",
  },
  {
    id: "auto-paths",
    title: "Paper / auto: puertas etiquetadas",
    status: "listo" as const,
    plain:
      "A checklist · B radar · C Supervisado · Monitor estado · D Paper D (propose + execute gated PAPER_D_EXECUTE). Screeners FA→whitelist→D.",
  },
  {
    id: "frozen",
    title: "Aún no (congelado)",
    status: "congelado" as const,
    plain:
      "Discovery automático, Planner IA, Decay/Pruning, UI cognitiva completa. Execute paper sigue off-by-default (no es auto de producción).",
  },
] as const;

export const BACKTESTING_IDEAS = [
  {
    id: "no-crystal",
    title: "No es una bola de cristal",
    body: "El pasado no garantiza el futuro. Una curva bonita puede ser suerte o sobreajuste.",
  },
  {
    id: "vs-bh",
    title: "Siempre mira vs buy & hold",
    body: "Si no mejoras a comprar y mantener (con costes), la regla no aporta valor práctico.",
  },
  {
    id: "oos",
    title: "Validar fuera de muestra",
    body: "Antes de desplegar en la demo activa, usa hold-out o walk-forward en Optimizar y el checklist pre-demo.",
  },
  {
    id: "ledger",
    title: "Todo deja rastro",
    body: "Las pruebas quedan en el historial de research para auditar qué se probó y con qué parámetros.",
  },
  {
    id: "auto-paths",
    title: "Varias puertas, ninguna «auto de producción»",
    body: "Checklist (A) ≠ Radar (B) ≠ Proponer F3 (C). El Monitor solo muestra estado. Auto completo (D) congelado.",
  },
  {
    id: "list-auto-fresh",
    title: "Lista AUTO no debe recalcular por capricho",
    body: "Si periodo/costes/perfil/lote no cambiaron, el 2º Play omite. Histéresis v1.3: pocas barras nuevas (1d ≤5d) también Omitido. «Reevaluar resto» fuerza.",
  },
] as const;

export const BACKTESTING_NEXT = [
  "Cierre código 2026-08-01 OK · siguiente = smoke UI humano",
  "Smoke UI a fondo: operativa-test-plan D1–D12 + R1–R9",
  "Smoke UI: DÍA D → Análisis fundamental badge reconstructed/blocked",
  "Smoke UI: reinicio → Play IBEX → mayoritariamente Omitido (histéresis v1.3)",
  "Checklist FA APP: refresh · Tarjeta CAPM/ADV · Screener · Paper D dry-run",
  "Ops: pnpm test:operativa · test:operativa:smoke · test:fa · test:coach",
  "Handoff: docs/engineering/session-handoff-2026-08-01.md",
  "Congelado: auto-paper D · Lab P3–P9 / Belief · activar CORE_R_CRON / COST_MODEL_V2 sin decisión ops",
] as const;

export function backtestingStatusLabel(
  status: (typeof BACKTESTING_TRACKING)[number]["status"],
): string {
  if (status === "listo") return "Listo";
  if (status === "cerrado") return "Cerrado / en uso";
  return "Congelado";
}
