# Ayuda en la app — coordinación con trackers y docs

> **Sync:** `HELP_CONTENT_AS_OF` = **2026-08-31** (fase pruebas tip **v1.41.3-beta** · Daily Desk + Operational Honesty · **Cuentas UX**: Movimientos fecha/hora + export CSV/JSON · Operativa MANUAL/SEMI/AUTO · AdminRail Perfiles + Estadísticas stub · Ayuda `operating-desk-help.ts`)  
> Nav L1: **Hoy** · **Mercado** (terminal) · **Cartera** · **Asesor** · **Laboratorio**. Firma en Hoy → Confirmar (`/confirm`). Señales bajo Mercado. Consola / Decisiones / Journal no son puertas L1.  
> Mesa diaria: **Hoy** = inbox por atención · **Mercado** = cockpit (verdad entrada/posición/salida) · **Confirmar** = única firma · misma CTA/frase/hint entre superficies · entradas bloqueadas fail-closed. Menús: **Laboratorio** (`/backtests`) · **Asesor**. **AUTO cuenta** = UI BETA-D (`ACTIVAR AUTO` + `PAPER_D_EXECUTE` opt-in, default off). SEMI: _La app propone operaciones sobre tu Universo. Tú las firmas aquí. Nunca se envían solas._ En Ayuda (Guía, **Flujo y módulos**, Trading) — **«Hoy»** + «En pocas palabras» + «Cómo probar» + `<details>` experto. Tips «?» de mesa en Operativa / Confirmar. Confirm en **panel lateral** desde Operativa / chip F3.  
> **Cierre etapa (auditoría):** [engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md](./engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md).  
> **Roadmap post-auditorías:** [engineering/improvement-roadmap-post-audits-2026-08-02.md](./engineering/improvement-roadmap-post-audits-2026-08-02.md) — Q0–Q3 hecho.  
> **Decisión freeze:** [engineering/post-audit-decision-freeze-2026-08-03.md](./engineering/post-audit-decision-freeze-2026-08-03.md) — C4 no · Belief congelado · `CORE_R_CRON` / `COST_MODEL_V2` off · **Camino D execute off** (prep A0–A5).  
> **Motor Estudio / Canales:** [ADR-022](./adr/022-estudio-daily-opinion-motor.md) · [pack Canales](./engineering/audit-pack-estudio-asesor-canales-2026-08-04.md).  
> **Prep AUTO (BETA-D Accepted):** [pack A0–A5](./engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md) · [checklist thaw](./engineering/camino-d-auto-thaw-checklist-2026-08-04.md) · [ADR-023 Accepted BETA-D](./adr/023-camino-d-thaw.md) · [Risk Engine](./engineering/risk-engine-or-re-2026-08-04.md).  
> **Futuro Belief→Coach (brief, no código):** [engineering/belief-coach-brief-draft-2026-08-03.md](./engineering/belief-coach-brief-draft-2026-08-03.md).  
> **Biblioteca estrategias L0/L1:** [engineering/strategy-library-authoring-brief-2026-08-03.md](./engineering/strategy-library-authoring-brief-2026-08-03.md) — Genéricas · Optimizadas · Mis estrategias (prompt).  
> **DEMO operativa SEMI:** [engineering/demo-operating-modes-brief-2026-08-03.md](./engineering/demo-operating-modes-brief-2026-08-03.md) · [impl slice 1](./engineering/semi-demo-book-impl-slice1-2026-08-03.md) — MANUAL/SEMI · Confirm F3 · sizing 10%.  
> **Panel Operativa (mesa Trading):** [engineering/trading-operativa-panel-2026-08-04.md](./engineering/trading-operativa-panel-2026-08-04.md) — IO · Recomendación/Info · modos en barra.  
> **Estudio supervisión (ADR-024):** [modelo](./engineering/estudio-supervision-model-2026-08-06.md) · [UI procesos](./engineering/estudio-process-status-ui-2026-08-06.md) · [handoff UI](./engineering/session-handoff-2026-08-06-estudio-process-ui.md).  
> **Visualizados / listas UX:** [visualizados-list-ux](./engineering/visualizados-list-ux-2026-08-06.md) · [handoff](./engineering/session-handoff-2026-08-06-visualizados-list-ux.md).  
> **Chart TOP#1:** [engineering/chart-top1-indicator-switch-2026-08-03.md](./engineering/chart-top1-indicator-switch-2026-08-03.md).  
> **Auditoría (paquete único post-Q3):** [engineering/audit-pack-post-audits-2026-08-03.md](./engineering/audit-pack-post-audits-2026-08-03.md).  
> **Engineering Index / round 2 externas:** [engineering/engineering-index-2026-08-03.md](./engineering/engineering-index-2026-08-03.md) · [audit-ext-round2-triage](./engineering/audit-ext-round2-triage-2026-08-03.md).  
> **Respuesta auditoría 1 (ingesta+FIE):** [engineering/audit1-response-ingest-fie-2026-08-03.md](./engineering/audit1-response-ingest-fie-2026-08-03.md).  
> **Respuesta auditoría 2 (Lab backtests):** [engineering/audit2-response-backtests-lab-2026-08-03.md](./engineering/audit2-response-backtests-lab-2026-08-03.md).  
> **Premisas de proyecto:** [PROJECT_PREMISES.md](./PROJECT_PREMISES.md) — **documentar todo** (docs + docstrings/JSDoc).  
> **Docstrings (código):** [engineering/code-documentation-standard-2026-08-03.md](./engineering/code-documentation-standard-2026-08-03.md) — lotes 1–4 hechos; lote 5 prep AUTO forward-only.  
> **Repo:** público en GitHub (`jvelasca/Bolsa_V1`) para auditorías externas · PR stage [#29](https://github.com/jvelasca/Bolsa_V1/pull/29).  
> **Universos:** [LAB vs TRADING](./adr/019-dual-universes-lab-vs-trading.md) · [diseño](./engineering/dual-universes-lab-trading-design-2026-08-02.md) · [Mandato](./adr/020-operating-mandate-tenure.md) · [Reconciliación DÍA D](./adr/021-dia-d-reconciliation.md).  
> Configuración → **BD** (estado PostgreSQL, purga de huérfanos y demos cerradas).  
> **Espacios de trabajo:** chip superior → gestor (nuevo blanco / duplicar / renombrar); arranque = último activo.  
> Handoff: [Visualizados UX](./engineering/session-handoff-2026-08-06-visualizados-list-ux.md) · [Estudio procesos UI](./engineering/session-handoff-2026-08-06-estudio-process-ui.md) · [Estudio supervisión](./engineering/session-handoff-2026-08-06-estudio-supervision.md) · [Operativa](./engineering/session-handoff-2026-08-04-operativa.md) · [SEMI](./engineering/session-handoff-2026-08-03-semi.md) · [2026-08-01](./engineering/session-handoff-2026-08-01.md) · DÍA D: [engineering/backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) · Plan prueba: [engineering/operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md) · Lista AUTO: [engineering/list-auto-ops-2026-07-29.md](./engineering/list-auto-ops-2026-07-29.md).  
> (`apps/web/src/features/help/help-content-as-of.ts`)

La UI **Ayuda (?)** muestra guías y tableros de seguimiento.  
**Configuración (⚙)** solo tiene preferencias editables (incluida pestaña **BD**).

## Nomenclatura de producto

| En la app (español) | Código / URL (interno)                      |
| ------------------- | ------------------------------------------- |
| Hoy                 | `/mesa` (label producto; interno Mesa)      |
| Mercado             | `/trading` (terminal)                       |
| Cartera             | Posiciones / Órdenes / Historial            |
| Confirmar           | `/confirm` (también Hoy → Confirmar)        |
| Señales             | `/screeners` (bajo Mercado)                 |
| Laboratorio         | `/backtests` (alias histórico: Backtesting) |
| Backtesting         | alias de Laboratorio (`/backtests`)         |
| Plataforma IA       | ai / docs tracker; firma viva en Confirmar  |
| Datos de mercado    | data capture                                |
| Espacio de trabajo  | workspace                                   |

## Mapa sección → tracker → docs

| Sección Ayuda       | Tracker / UI                                                                                                                                         | Docs                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Flujo y módulos** | `workflow-modules-section.tsx` + **«Hoy»** (`hoy-en-la-mesa.tsx`) + **mesa operativa** (`operating-desk-help.ts` básico→experto) · tips `mesa-tip-*` | [research-lifecycle.md](./engineering/research-lifecycle.md), [ADR-019](./adr/019-dual-universes-lab-vs-trading.md), [diseño dual](./engineering/dual-universes-lab-trading-design-2026-08-02.md), [domain-language](./domain-language.md), [ARCHITECTURE](./ARCHITECTURE.md) — contenido de producto en tracker Ayuda, no copiar releivos aquí                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **Backtesting**     | `backtesting-tracker.ts` + Monitor (`strategy-monitor-panel.tsx`)                                                                                    | [research-lifecycle.md](./engineering/research-lifecycle.md), [roadmap post-auditorías](./engineering/improvement-roadmap-post-audits-2026-08-02.md), [estabilidad temporal](./engineering/stability-campaign-protocol-2026-08-02.md), [DÍA D](./engineering/backtesting-dia-d-premises-2026-07-31.md), [universos LAB/TRADING](./engineering/dual-universes-lab-trading-design-2026-08-02.md), [ADR-019](./adr/019-dual-universes-lab-vs-trading.md), [ADR-020 Mandato](./adr/020-operating-mandate-tenure.md), [operativa test](./engineering/operativa-test-plan-2026-07-31.md), [handoff 2026-08-01](./engineering/session-handoff-2026-08-01.md), [list-auto-ops](./engineering/list-auto-ops-2026-07-29.md), [ADR-009](./adr/009-backtesting-research-platform-h0.md), [ADR-018](./adr/018-fase2-evidence-store-v0.md) |
| **Trading**         | panel **Operativa** (IO · Mandato) · lista **Estudio** (Supervisión · Actualizar/Redescubrir) · modos en barra · alarmas → F3                        | [operativa panel](./engineering/trading-operativa-panel-2026-08-04.md) · [ADR-024](./adr/024-estudio-supervision-universe.md) · [UI procesos](./engineering/estudio-process-status-ui-2026-08-06.md) · [TOP#1 chart](./engineering/chart-top1-indicator-switch-2026-08-03.md) · [demo-operating-modes](./engineering/demo-operating-modes-brief-2026-08-03.md) · [SEMI slice 1](./engineering/semi-demo-book-impl-slice1-2026-08-03.md) · [prep AUTO A0–A5](./engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md) · [ADR-019](./adr/019-dual-universes-lab-vs-trading.md) · [ADR-020](./adr/020-operating-mandate-tenure.md) · [ADR-023 Accepted BETA-D](./adr/023-camino-d-thaw.md)                                                                                                                                        |
| **Asesor**          | Diario (ops R1–R4) · Opiniones Estudio · Alarmas/Avisos · telemetría A0 + A6 · Canales                                                               | [asesor-ui](./engineering/asesor-ui-2026-08-04.md) · [daily-ops](./engineering/daily-ops-report-brief-2026-08-04.md) · [pack Canales](./engineering/audit-pack-estudio-asesor-canales-2026-08-04.md) · [ADR-022](./adr/022-estudio-daily-opinion-motor.md) · A6 [`traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md`](./engineering/traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md)                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Análisis del valor  | `value-analysis-tracker.ts`                                                                                                                          | FA status / FIE                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Datos de mercado    | `data-market-tracker.ts`                                                                                                                             | data capture                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Watchlist / listas  | `watchlist-lists-tracker.ts` · **Visualizados** (pestañas) · columnas IO · foco Cartera→Estudio                                                      | [lists-universes](./engineering/lists-universes-design-2026-07-30.md) · [Visualizados UX](./engineering/visualizados-list-ux-2026-08-06.md) · [handoff](./engineering/session-handoff-2026-08-06-visualizados-list-ux.md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Plataforma IA       | `ai-platform-tracker.ts`                                                                                                                             | AI_PLATFORM_SOLUTION                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Gráficos            | `chart-platform-tracker.ts`                                                                                                                          | charts                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |

**Panel Operativa (Trading):** columna lateral a **altura completa** (hasta la barra de estado); Operaciones solo a su izquierda (bajo watchlist + gráfico). Secciones:

- **Recomendación** — Índice Operativo (IO) · gauges TA/FA · chips **acción package** (LONG/WAIT/EXIT) + **Fit · PASS/VETO** (o `Fit · —` si no hay dato) · «El n de N en Estudio» · TOP #1 / adopción · Proponer F3.
- **Info** — mandato / Learning / Outcomes.

**Modo de cuenta (MANUAL / SEMI / AUTO)** — no va en el panel por valor. En **Cuentas → Configuración** los botones de modo son grandes y con connotación visible. Barra inferior: badge **`OPERATIVA: …`**. Clic → misma Config · Operativa (`DemoBookModePanel`: sizing · kill switch · armado AUTO).  
**AdminRail:** Overview · Cuentas · **Perfiles** (catálogo) · **Estadísticas** (próximamente) · Fiscal · Consola.  
**Movimientos (cuenta):** Depósito/Retirada simétricos · fecha/hora por fila · export CSV/JSON.
**AUTO cuenta (BETA-D):** pill seleccionable tras escribir `ACTIVAR AUTO` (armado local; se desarma al salir). Execute paper sigue **opt-in** `PAPER_D_EXECUTE=1` (default off). Arm UI ≠ permiso server. Lista AUTO del Lab es otra pieza. Thaw **estricto** sigue deuda — [checklist](./engineering/camino-d-auto-thaw-checklist-2026-08-04.md) · [ADR-023](./adr/023-camino-d-thaw.md).

### SEMI (usar ahora)

_La app propone operaciones sobre tu Universo. Tú las firmas aquí. Nunca se envían solas._

**«Hoy»** (Ayuda → Guía / Flujo / Trading): (1) Inbox en Hoy · (2) Operar en Mercado · (3) Firmar en Confirmar. «En pocas palabras» + «Cómo probar ahora» para usuario básico; «Información avanzada» (colapsable) para tester/experto — coherencia de CTA entre superficies, bloqueo de entradas, freeze BETA. No sustituye Confirmar.

1. Cuenta DEMO activa · modo **SEMI** (barra / Cuentas) · valor en lista **Estudio** (Universo en vigilancia).
2. Alarma / Proponer F3 → **Confirmar** (panel lateral desde Mercado, o página `/confirm`) → humano firma y ejecuta.
3. Asesor → Opiniones: telemetría proxy (días / precisión / recall) alimenta P1–P4 del thaw.

> **Firma SEMI (contrato):** al **aceptar** (`Confirmar`), la operación firma contra la propuesta original (`DecisionPackage`). Si lo que firmas **no coincide** con lo propuesto (otro valor o cambiar compra↔venta), se **rechaza con «rechazado por el sistema»** y el ítem **sale de la cola** (no se ejecuta nada). Editar tamaño/precio **sí** es válido. Cuando no hay propuesta original (`contract: ausente`) la firma sigue como antes. Detalle: `traspaso-relevo-f0-6-cierre-apertura-siguiente-2026-08-24.md` (D2).
>
> **Chips de mesa (U4):** en Operativa (y en la barra del gráfico si hay package en cola) ves la **acción del DecisionPackage** y el **Fit** (PASS/VETO) ya calculado. Sin dato de Fit → `Fit · —` (fail soft; nunca se inventa PASS). No sustituyen la firma en Confirmar.
>
> **Proyección F3 en gráfico (U5):** con propuesta en cola para el valor activo, el gráfico muestra una **línea de precio** (p. ej. `F3 · LONG @ …`) y un atajo **Firmar** al panel Confirmar. Solo visual — no ejecuta ni bypasea la firma SEMI.

### AUTO (BETA-D · no producción)

Cuentas → Operativa → Auto: escribir **`ACTIVAR AUTO`** para armar (local). Execute DEMO solo si `PAPER_D_EXECUTE=1`. Sin esa env, la UI puede armarse pero el servidor **no** ejecuta. No confundir con **Lista AUTO** del Laboratorio. Broker live **no**. Thaw estricto (60d/50/70/55) **abierto**.

**Decision Spine (v1.8):** tesis (`DecisionPackage`) ≠ plan (`TradePlan` v0: WATCH / ARMED / TRIGGERED / BLOCKED / EXPIRED) ≠ permiso (`check_opening`). Ranking / TOP / dictamen **no** son BUY. Thesis Health · Exit Radar · Bracket en Hoy son **avisos**, no firman ni mutan el stop.

**Orden pendiente a precio (H1 · ADR-033):** el diálogo de operación y Operaciones muestran una orden con **precio límite**, no un «stop». No protege la posición; se ejecuta si el mercado alcanza ese precio. El stop del plan vive en PositionState (cuando esté cableado), no en `pending_orders`.

**Kill switch (H2 · ADR-033):** bloquea **aperturas** nuevas y **automatismos** AUTO. No niega a ciegas el desriesgo humano en SEMI (salir / proteger / reducir). Cuentas → Operativa.

**Posición persistida (P1 · ADR-033):** tras un fill de apertura con TradePlan TRIGGERED (Confirm SEMI, o pending con snapshot), Operaciones muestra stop / T1 / T2 / estado del plan. Qty y P&L siguen el holding (contabilidad). Sin plan → «sin plan persistido».

**Firma de riesgo (P2 · ADR-033):** al firmar en Confirmar, el tamaño es el del TradePlan (riesgo € / distancia al stop), no un % de caja. El ticket muestra qty sugerida/máx, stop, pérdida estimada y R. Superar el plan exige un motivo. Sin plan TRIGGERED, el ticket no inventa stop ni R.

**Cadena de salida (P3 · ADR-033):** ExitPlan propone (mantener / proteger / reducir / salir) → ExitPermission valida → tú firmas en Confirmar. No es auto-exit. Lab Señales (`evaluate-exits`) y thin «Salida» de Hoy **no** son este puerto. Tras un cierre o reduce firmado, el plan persistido se actualiza (PARTIAL / CLOSED). La columna Salida en Operaciones es aviso, no un botón que ejecute.

**Estudio** = lista API canónica (universo supervisable). Abrir/cerrar gráfico **no** cambia membresía. Selección → **Pasar a Estudio** / **A Estudio** (alta = Actualizar ligero de esos valores; Redescubrir sigue manual). SEMI/AUTO exigen pertenencia; MANUAL no.

**Visualizados** = pestañas de gráfico abiertas (scratch). **Quitar** cierra pestañas. **Por IO** ordena por Índice Operativo (mejor a la izq.; misma métrica que Operativa). Columnas opcionales (⋯): IO · TA · FA · ★ Dict. · Postura. Al buscar o cambiar de pestaña: lista prioritaria **Cartera → Estudio → resto** y scroll del valor al tope (bajo cabecera). Detalle: [visualizados-list-ux-2026-08-06.md](./engineering/visualizados-list-ux-2026-08-06.md) · [ADR-024](./adr/024-estudio-supervision-universe.md) · [operativa](./engineering/trading-operativa-panel-2026-08-04.md).

**Barra de estado (inferior Trading):** izquierda = conexión · cuenta Activa · **`OPERATIVA: …`** · métricas; derecha (ancho fijo) = **Colas** (Velas · CORE-R · F3 · Lista AUTO) + **Alarmas Radar** (badge nº).

**Gráfico Trading — TOP#1:**

- Barra general (**Indicadores**): switch **Finalista #1 · todos**.
- Barra del gráfico en uso: switch **Finalista #1 · este**.
- Sin TOP: cartel «No hay indicador finalista». OFF quita solo `origin: finalist-top1`.
- Detalle: [chart-top1-indicator-switch-2026-08-03.md](./engineering/chart-top1-indicator-switch-2026-08-03.md).

(El resto de filas del mapa histórico se mantienen en los trackers; este archivo prioriza Backtesting operativo.)

## Backtesting DÍA D (usuario · sync 2026-08-02 · U2)

**LAB (ADR-019):** **Verificar D→hoy** en Backtesting · Análisis técnico (Cartera LAB). Trading = inversión diaria + panel **Operativa**. Detalle: [diseño dual](./engineering/dual-universes-lab-trading-design-2026-08-02.md) · [premisas](./engineering/backtesting-dia-d-premises-2026-07-31.md).

Guía en Ayuda → Backtesting (`BACKTESTING_DIA_D_GUIDE`). Plan: [operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md).

| Paso | Dónde                  | Qué hacer                                                                      |
| ---- | ---------------------- | ------------------------------------------------------------------------------ |
| 1    | Backtesting → Probar   | Bloque **Backtesting DÍA D** → fecha **pasada**                                |
| 2    | Mismo hub              | **Play** hasta Finalistas (embudo ≤ D)                                         |
| 3    | Resultado → Finalistas | En **#1** → **Verificar D→hoy**                                                |
| 4    | Análisis técnico (LAB) | Banner Verificar + película · modos Manual / Semi / Auto                       |
| 5    | Semi/Manual            | En cada señal → **Aceptar** (fill) / **Rechazar** (no fill; buy KO anula sell) |
| 6    | Opcional               | **Pantalla completa** (efímera) · **Narrar con IA** · **Guardar Evidence**     |
| 7    | Archivo                | Ayuda → Backtesting (preview/JSON/Importar)                                    |
| 8    | Salir                  | Banner → **Salir verificación** (sandbox LAB; no toca DEMO)                    |

Si el hub «desapareció» (solo película): **Salir pantalla completa** o **Salir verificación**, o recarga (full-bleed no se persiste).

Si no ves el CTA: la fecha DÍA D sigue en «hoy», o no hay Finalistas #1 con estrategia guardada.

## Mandato operativo (usuario · ADR-020 · M0–M3 + M1b)

Playbook **vigente** en TRADING por instrumento×cuenta, con historial de periodos.

| Paso | Dónde                            | Qué                                                                        |
| ---- | -------------------------------- | -------------------------------------------------------------------------- |
| 1    | Backtesting → Finalistas         | **Checklist** / Adoptar → estado `adoptada`                                |
| 2    | Trading → panel Operativa · Info | Timeline **Mandato operativo** (tramo vigente + cerrados + flujo enlazado) |
| 3    | Trading → orden DEMO             | El fill se **enlaza** al mandato vigente                                   |
| 4    | Cambiar Finalista                | Nuevo Adoptar → cierra tramo anterior (motivo _Cambio_)                    |
| 5    | Otro dispositivo                 | Tras migrate M1b: hydrate desde `GET /api/accounts/{id}/mandates`          |

- **No** es Finalistas LAB ni un tag de setup por trade.
- Cache cliente: `bolsa-mandate-tenures-v1` · `bolsa-mandate-trade-links-v1` · adopción en `bolsa-strategy-adoption-v1`.
- **SoT multi-dispositivo (M1b):** PostgreSQL `mandate_tenures` / `mandate_trade_links` · sync `operating-mandate-sync.ts`.
- Flujo enlazado = ventas − compras de fills ligados (no mark-to-market).
- Doc: [ADR-020](./adr/020-operating-mandate-tenure.md) · auditoría [stage-audit…](./engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md).

## Reconciliación DÍA D (usuario · ADR-021 + v1.1)

Pregunta: _¿La operativa que habría elegido el día D (y verifico hasta hoy) es la misma o distinta que la Finalista #1 de ahora?_

| Paso | Qué                                                                              |
| ---- | -------------------------------------------------------------------------------- |
| 1    | Ten Finalistas operativos (**F-hoy**) con D = hoy                                |
| 2    | Fija DÍA D pasado → Play → se guarda **F-D** (experimento); **F-hoy no se pisa** |
| 3    | **Verificar D→hoy** con F-D#1 congelada (lookback 3y + carry de posición)        |
| 4    | Informe **Reconciliación**: SAME*\* / DRIFT*\* / INCONCLUSIVE                    |
| 5    | Si F-hoy#1 ≠ F-D#1 → **contrafactual** OOS F-hoy + Δ pp                          |

Doc: [ADR-021](./adr/021-dia-d-reconciliation.md). Persistencia F-D: `bolsa-dia-d-experiment-top-v1`.

En **Análisis fundamental** con D en el pasado: la API pide `asOf=D`. Si hay `statementPack` (tras **refresh FA** del valor), reconstruye ratios desde estados ≤ D (`pointInTime=reconstructed`). Si no hay pack, **blocked**. El Composite corta TA a barras ≤ D.

Informe lateral: retorno/DD/ops del **gate** (+ referencia Auto) y bloque **Evidence** (band + narrativa; «Narrar con IA» opcional; «Guardar Evidence» → archivo local + Fase 2 `dia_d_session`).

**Reinicia api-python** tras actualizar código para rutas Evidence / asOf / CORE-R.

## Estabilidad Lab en embudo (Q3.2)

Tras Lab → **Guardar Finalistas**, el resumen Hold-out / WF / CPCV (mismo vocabulario que el checklist) queda en `coachFacts.labEvidence` y se muestra en Finalistas y en el panel **Operativa** (Recomendación). No es campaña multi-ventana ledger (eso sigue en Observatory / protocolo Q1.3).

## CORE-R / Monitor Finalistas (usuario · v1.13)

Guía en Ayuda → Backtesting (`BACKTESTING_CORE_R_GUIDE`). Detalle: [list-auto-ops § CORE-R](./engineering/list-auto-ops-2026-07-29.md).

| Paso | Qué                                                                                                  |
| ---- | ---------------------------------------------------------------------------------------------------- |
| 1    | Valores → **Pasar a Estudio** (lista API + Actualizar ligero de los nuevos)                          |
| 2    | Lista **Estudio** → banner **Supervisión ON** (Lista AUTO + CORE-R) · o Monitor → Auto-sync          |
| 3    | Monitor → cola de revisiones · deep-links Lab / Finalistas / Checklist → **Hecho**                   |
| 4    | «Valorar cambio» + modo **SEMI** (barra/Cuentas) → **Adoptar** (abre mandato TOP#1; no auto en AUTO) |
| 5    | Opcional: **Narrar cola** · cadencia editable · chip **CORE-R N** · toast «Abrir Monitor»            |
| 6    | **Hecho todos** cierra las abiertas de la lista actual                                               |
| 7    | **Eliminar de la lista** = deja de supervisar ese valor (no cierra mandato solo)                     |

No pisa TOP · no auto-paper D. Cola: localStorage = cache; BD = SoT multi-dispositivo.  
Flags ops (off por defecto — ver [github-credentials-and-ops §9](./engineering/github-credentials-and-ops.md)): `CORE_R_CRON_ENABLED`, `COST_MODEL_V2_ENABLED`.

### Estudio = supervisión (ADR-024)

**Visualizados** = lista virtual de pestañas/búsqueda (scratch; no supervisión).  
**Estudio** = único universo supervisable (lista API `estudio`). **Supervisión ON** (banner) arma Lab + CORE-R. Cadencias: chips V·F·R + **(···)** del banner.

| UI                               | Significado                                                                                                                       |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Bajo el nombre                   | Resumen procesos: `al día` · `toca V` / `toca F·R` · `sin sync` (+ barra al actualizar)                                           |
| Columna Procesos (opcional)      | Iconos Vigilia · Frescura · Redescubrir                                                                                           |
| Chips banner (V·F·R)             | Cadencia de cada capa; clic abre configuración                                                                                    |
| **Actualizar** / **Redescubrir** | Barra inferior al seleccionar: velas+vigilia+frescura · embudo costoso (confirm). Alta a Estudio lanza Actualizar, no Redescubrir |
| Pausa ⏸ (banner)                 | Termina el valor en curso y para (`Termina XXX y para…`); no corta a mitad del valor                                              |
| `OPERATIVA: Semi` (barra)        | Modo de la **cuenta** → clic abre Cuentas · Operativa                                                                             |

SEMI confirma operar/cambio de mandato. Detalle: [modelo](./engineering/estudio-supervision-model-2026-08-06.md) · [UI procesos](./engineering/estudio-process-status-ui-2026-08-06.md) · [ADR-024](./adr/024-estudio-supervision-universe.md) · [handoff](./engineering/session-handoff-2026-08-06-estudio-process-ui.md).

## Lista AUTO frescura (v1.3) + tandas

Lista AUTO procesa **toda** la lista en tandas de ~40 (ya no recorta a 40). Confirmación al lanzar si N>40; preferencia «No preguntar tandas» (N>200 siempre confirma). Tope duro 500.

Tras reinicio, un 2º Play sobre la misma lista debe **Omitir** si periodo/costes/perfil no cambiaron y la última barra no aporta señal nueva (`1d` ≤5 días → `bar_hysteresis`). «Reevaluar resto» fuerza (solo LAB).

**Reanalizar ≠ cambiar Trading:** CORE-R propone en Monitor; el mandato (ADR-020) solo cambia si lo aceptas (SEMI) o lo cambias a mano. AUTO execute no auto-adopta. Detalle: [list-auto-ops §5.2](./engineering/list-auto-ops-2026-07-29.md).

## Batería offline (antes de smoke UI)

```bash
pnpm test:operativa          # DÍA D + CORE-R (web + py + smoke API opcional)
pnpm test:operativa:smoke    # API live (reinicia api primero)
pnpm test:coach              # embudo / Lista AUTO / CORE-P (+ smoke API opcional)
pnpm test:coach:smoke        # CORE-P multi-perfil live (API)
pnpm test:coach:api          # ASGI multi-perfil (DB) + smoke live
```

## UX diálogo

El diálogo de Ayuda usa **ancho y alto fijos** (`max-w-4xl` + altura viewport) para que cambiar de sección no redimensione la ventana; el cuerpo hace scroll interno.
