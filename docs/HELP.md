# Ayuda en la app — coordinación con trackers y docs

> **Sync:** `HELP_CONTENT_AS_OF` = **2026-08-04**  
> Ayuda «Datos de mercado» + Watchlist + «Análisis del valor» + **Backtesting** (Play ciclo, Lista AUTO **v1.3**, Finalistas A/C, Monitor + **CORE-R v1.12**, **DÍA D** Verify en LAB + **Reconciliación ADR-021** + contrafactual + continuidad lookback, Lab **CORE-B v0.2** · Lab Health Q0 · warm-up Q1.6) + Trading (**panel Operativa** · En estudio · IO · ADR-019 · **Mandato ADR-020 M1b BD** · **SEMI Confirm** · **AUTO prep A1–A5** sin execute) + **Asesor** (Diario · Opiniones · Alarmas · telemetría A0).  
> **Cierre etapa (auditoría):** [engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md](./engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md).  
> **Roadmap post-auditorías:** [engineering/improvement-roadmap-post-audits-2026-08-02.md](./engineering/improvement-roadmap-post-audits-2026-08-02.md) — Q0–Q3 hecho.  
> **Decisión freeze:** [engineering/post-audit-decision-freeze-2026-08-03.md](./engineering/post-audit-decision-freeze-2026-08-03.md) — C4 no · Belief congelado · `CORE_R_CRON` / `COST_MODEL_V2` off · **Camino D execute off** (prep A0–A5).  
> **Motor Estudio / Canales:** [ADR-022](./adr/022-estudio-daily-opinion-motor.md) · [pack Canales](./engineering/audit-pack-estudio-asesor-canales-2026-08-04.md).  
> **Prep AUTO (flag off):** [pack A0–A5](./engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md) · [checklist thaw](./engineering/camino-d-auto-thaw-checklist-2026-08-04.md) · [ADR-023 Proposed](./adr/023-camino-d-thaw.md) · [Risk Engine](./engineering/risk-engine-or-re-2026-08-04.md).  
> **Futuro Belief→Coach (brief, no código):** [engineering/belief-coach-brief-draft-2026-08-03.md](./engineering/belief-coach-brief-draft-2026-08-03.md).  
> **Biblioteca estrategias L0/L1:** [engineering/strategy-library-authoring-brief-2026-08-03.md](./engineering/strategy-library-authoring-brief-2026-08-03.md) — Genéricas · Optimizadas · Mis estrategias (prompt).  
> **DEMO operativa SEMI:** [engineering/demo-operating-modes-brief-2026-08-03.md](./engineering/demo-operating-modes-brief-2026-08-03.md) · [impl slice 1](./engineering/semi-demo-book-impl-slice1-2026-08-03.md) — MANUAL/SEMI · Confirm F3 · sizing 10%.  
> **Panel Operativa (mesa Trading):** [engineering/trading-operativa-panel-2026-08-04.md](./engineering/trading-operativa-panel-2026-08-04.md) — IO · En estudio · layout full-height.  
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
> Handoff: [engineering/session-handoff-2026-08-04-operativa.md](./engineering/session-handoff-2026-08-04-operativa.md) · [SEMI](./engineering/session-handoff-2026-08-03-semi.md) · [2026-08-01](./engineering/session-handoff-2026-08-01.md) · DÍA D: [engineering/backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) · Plan prueba: [engineering/operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md) · Lista AUTO: [engineering/list-auto-ops-2026-07-29.md](./engineering/list-auto-ops-2026-07-29.md).  
> (`apps/web/src/features/help/help-content-as-of.ts`)

La UI **Ayuda (?)** muestra guías y tableros de seguimiento.  
**Configuración (⚙)** solo tiene preferencias editables (incluida pestaña **BD**).

## Nomenclatura de producto

| En la app (español) | Código / URL (interno) |
|---------------------|------------------------|
| Análisis del valor | value-analysis / FA |
| Backtesting | backtests |
| Plataforma IA | ai / supervised F3 |
| Datos de mercado | data capture |
| Espacio de trabajo | workspace |

## Mapa sección → tracker → docs

| Sección Ayuda | Tracker / UI | Docs |
|---------------|--------------|------|
| **Backtesting** | `backtesting-tracker.ts` + Monitor (`strategy-monitor-panel.tsx`) | [research-lifecycle.md](./engineering/research-lifecycle.md), [roadmap post-auditorías](./engineering/improvement-roadmap-post-audits-2026-08-02.md), [estabilidad temporal](./engineering/stability-campaign-protocol-2026-08-02.md), [DÍA D](./engineering/backtesting-dia-d-premises-2026-07-31.md), [universos LAB/TRADING](./engineering/dual-universes-lab-trading-design-2026-08-02.md), [ADR-019](./adr/019-dual-universes-lab-vs-trading.md), [ADR-020 Mandato](./adr/020-operating-mandate-tenure.md), [operativa test](./engineering/operativa-test-plan-2026-07-31.md), [handoff 2026-08-01](./engineering/session-handoff-2026-08-01.md), [list-auto-ops](./engineering/list-auto-ops-2026-07-29.md), [ADR-009](./adr/009-backtesting-research-platform-h0.md), [ADR-018](./adr/018-fase2-evidence-store-v0.md) |
| **Trading** | panel **Operativa** (IO · En estudio · modos · kill switch · armado AUTO prep) + Mandato + alarmas → F3 | [operativa panel](./engineering/trading-operativa-panel-2026-08-04.md) · [TOP#1 chart](./engineering/chart-top1-indicator-switch-2026-08-03.md) · [demo-operating-modes](./engineering/demo-operating-modes-brief-2026-08-03.md) · [SEMI slice 1](./engineering/semi-demo-book-impl-slice1-2026-08-03.md) · [prep AUTO A0–A5](./engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md) · [ADR-019](./adr/019-dual-universes-lab-vs-trading.md) · [ADR-020](./adr/020-operating-mandate-tenure.md) · [ADR-023 Proposed](./adr/023-camino-d-thaw.md) |
| **Asesor** | Diario (ops R1–R4) · Opiniones Estudio · Alarmas/Avisos · telemetría A0 · Canales | [asesor-ui](./engineering/asesor-ui-2026-08-04.md) · [daily-ops](./engineering/daily-ops-report-brief-2026-08-04.md) · [pack Canales](./engineering/audit-pack-estudio-asesor-canales-2026-08-04.md) · [ADR-022](./adr/022-estudio-daily-opinion-motor.md) |
| Análisis del valor | `value-analysis-tracker.ts` | FA status / FIE |
| Datos de mercado | `data-market-tracker.ts` | data capture |
| Watchlist / listas | `watchlist-lists-tracker.ts` | lists-universes |
| Plataforma IA | `ai-platform-tracker.ts` | AI_PLATFORM_SOLUTION |
| Gráficos | `chart-platform-tracker.ts` | charts |

**Panel Operativa (Trading):** columna lateral a **altura completa** (hasta la barra de estado); Operaciones solo a su izquierda (bajo watchlist + gráfico). Secciones con scroll y altura ajustable:

- **Recomendación** — Índice Operativo (IO) · gauges TA/FA · «El n de N en Estudio» · TOP #1 / adopción.
- **Info** — mandato / Learning.
- **Configuración** — resumen a la derecha `Operativa: manual|semi|auto`; bloque titulado con el **nombre de la cuenta activa** (MANUAL/SEMI · % cash · máx. posiciones · geo).
  - **AUTO · prep** (pill disabled): riesgos Camino D · **Kill switch** (API runtime) · **Armar AUTO** doble confirm (`ACTIVAR AUTO`, solo localStorage) · `PAPER_D_EXECUTE` off.
  - Execute AUTO **no** liberado — [checklist thaw](./engineering/camino-d-auto-thaw-checklist-2026-08-04.md) · [pack A0–A5](./engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md).

### SEMI (usar ahora)

1. Cuenta DEMO activa · modo **SEMI** · valor en lista **Estudio**.  
2. Alarma / Proponer F3 → cola Confirm → humano ejecuta.  
3. Asesor → Opiniones: telemetría proxy (días / precisión / recall) alimenta P1–P4 del thaw.

### AUTO (solo prep)

No seleccionar. No poner `PAPER_D_EXECUTE=1` en demo compartida. ADR-023 sigue **Proposed** hasta evidencia.

Lista virtual **Estudio** = universo operativo (membresía explícita; abrir gráfico añade, cerrar pestaña no quita). Selección masiva en Valores → **A Estudio**. SEMI/AUTO exigen pertenencia; MANUAL no. Chips TA/FA de la barra del gráfico siguen configurables con ⋯. Detalle: [trading-operativa-panel-2026-08-04.md](./engineering/trading-operativa-panel-2026-08-04.md).

**Barra de estado (inferior Trading):** izquierda = conexión · cuenta Activa · métricas; derecha (ancho fijo) = **Colas** (Velas · CORE-R · F3 · Lista AUTO) + **Alarmas Radar** (badge nº). No redimensiona al cambiar conteos.

**Gráfico Trading — TOP#1:**
- Barra general (**Indicadores**): switch **Finalista #1 · todos**.
- Barra del gráfico en uso: switch **Finalista #1 · este**.
- Sin TOP: cartel «No hay indicador finalista». OFF quita solo `origin: finalist-top1`.
- Detalle: [chart-top1-indicator-switch-2026-08-03.md](./engineering/chart-top1-indicator-switch-2026-08-03.md).

(El resto de filas del mapa histórico se mantienen en los trackers; este archivo prioriza Backtesting operativo.)

## Backtesting DÍA D (usuario · sync 2026-08-02 · U2)

**LAB (ADR-019):** **Verificar D→hoy** en Backtesting · Análisis técnico (Cartera LAB). Trading = inversión diaria + panel **Operativa**. Detalle: [diseño dual](./engineering/dual-universes-lab-trading-design-2026-08-02.md) · [premisas](./engineering/backtesting-dia-d-premises-2026-07-31.md).

Guía en Ayuda → Backtesting (`BACKTESTING_DIA_D_GUIDE`). Plan: [operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md).

| Paso | Dónde | Qué hacer |
|------|--------|-----------|
| 1 | Backtesting → Probar | Bloque **Backtesting DÍA D** → fecha **pasada** |
| 2 | Mismo hub | **Play** hasta Finalistas (embudo ≤ D) |
| 3 | Resultado → Finalistas | En **#1** → **Verificar D→hoy** |
| 4 | Análisis técnico (LAB) | Banner Verificar + película · modos Manual / Semi / Auto |
| 5 | Semi/Manual | En cada señal → **Aceptar** (fill) / **Rechazar** (no fill; buy KO anula sell) |
| 6 | Opcional | **Pantalla completa** (efímera) · **Narrar con IA** · **Guardar Evidence** |
| 7 | Archivo | Ayuda → Backtesting (preview/JSON/Importar) |
| 8 | Salir | Banner → **Salir verificación** (sandbox LAB; no toca DEMO) |

Si el hub «desapareció» (solo película): **Salir pantalla completa** o **Salir verificación**, o recarga (full-bleed no se persiste).

Si no ves el CTA: la fecha DÍA D sigue en «hoy», o no hay Finalistas #1 con estrategia guardada.

## Mandato operativo (usuario · ADR-020 · M0–M3 + M1b)

Playbook **vigente** en TRADING por instrumento×cuenta, con historial de periodos.

| Paso | Dónde | Qué |
|------|--------|-----|
| 1 | Backtesting → Finalistas | **Checklist** / Adoptar → estado `adoptada` |
| 2 | Trading → panel Operativa · Info | Timeline **Mandato operativo** (tramo vigente + cerrados + flujo enlazado) |
| 3 | Trading → orden DEMO | El fill se **enlaza** al mandato vigente |
| 4 | Cambiar Finalista | Nuevo Adoptar → cierra tramo anterior (motivo *Cambio*) |
| 5 | Otro dispositivo | Tras migrate M1b: hydrate desde `GET /api/accounts/{id}/mandates` |

- **No** es Finalistas LAB ni un tag de setup por trade.  
- Cache cliente: `bolsa-mandate-tenures-v1` · `bolsa-mandate-trade-links-v1` · adopción en `bolsa-strategy-adoption-v1`.  
- **SoT multi-dispositivo (M1b):** PostgreSQL `mandate_tenures` / `mandate_trade_links` · sync `operating-mandate-sync.ts`.  
- Flujo enlazado = ventas − compras de fills ligados (no mark-to-market).  
- Doc: [ADR-020](./adr/020-operating-mandate-tenure.md) · auditoría [stage-audit…](./engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md).

## Reconciliación DÍA D (usuario · ADR-021 + v1.1)

Pregunta: *¿La operativa que habría elegido el día D (y verifico hasta hoy) es la misma o distinta que la Finalista #1 de ahora?*

| Paso | Qué |
|------|-----|
| 1 | Ten Finalistas operativos (**F-hoy**) con D = hoy |
| 2 | Fija DÍA D pasado → Play → se guarda **F-D** (experimento); **F-hoy no se pisa** |
| 3 | **Verificar D→hoy** con F-D#1 congelada (lookback 3y + carry de posición) |
| 4 | Informe **Reconciliación**: SAME_* / DRIFT_* / INCONCLUSIVE |
| 5 | Si F-hoy#1 ≠ F-D#1 → **contrafactual** OOS F-hoy + Δ pp |

Doc: [ADR-021](./adr/021-dia-d-reconciliation.md). Persistencia F-D: `bolsa-dia-d-experiment-top-v1`.

En **Análisis fundamental** con D en el pasado: la API pide `asOf=D`. Si hay ``statementPack`` (tras **refresh FA** del valor), reconstruye ratios desde estados ≤ D (`pointInTime=reconstructed`). Si no hay pack, **blocked**. El Composite corta TA a barras ≤ D.

Informe lateral: retorno/DD/ops del **gate** (+ referencia Auto) y bloque **Evidence** (band + narrativa; «Narrar con IA» opcional; «Guardar Evidence» → archivo local + Fase 2 `dia_d_session`).

**Reinicia api-python** tras actualizar código para rutas Evidence / asOf / CORE-R.

## Estabilidad Lab en embudo (Q3.2)

Tras Lab → **Guardar Finalistas**, el resumen Hold-out / WF / CPCV (mismo vocabulario que el checklist) queda en `coachFacts.labEvidence` y se muestra en Finalistas y en el panel **Operativa** (Recomendación). No es campaña multi-ventana ledger (eso sigue en Observatory / protocolo Q1.3).

## CORE-R / Monitor Finalistas (usuario · v1.13)

Guía en Ayuda → Backtesting (`BACKTESTING_CORE_R_GUIDE`). Detalle: [list-auto-ops § CORE-R](./engineering/list-auto-ops-2026-07-29.md).

| Paso | Qué |
|------|-----|
| 1 | Operativa → **Pasar a Estudio** los valores a supervisar (lista API canónica) |
| 2 | Operativa → Configuración → **Supervisión ON** (Lista AUTO + CORE-R sobre Estudio) · o Monitor → Auto-sync |
| 3 | Monitor → cola de revisiones · deep-links Lab / Finalistas / Checklist → **Hecho** |
| 4 | «Valorar cambio» + modo **SEMI** → **Adoptar** (abre mandato TOP#1; no auto en AUTO) |
| 5 | Opcional: **Narrar cola** · cadencia editable · chip **CORE-R N** · toast «Abrir Monitor» |
| 6 | **Hecho todos** cierra las abiertas de la lista actual |
| 7 | **Quitar de Estudio** = deja de supervisar ese valor (no cierra mandato solo) |

No pisa TOP · no auto-paper D. Cola: localStorage = cache; BD = SoT multi-dispositivo.  
Flags ops (off por defecto — ver [github-credentials-and-ops §9](./engineering/github-credentials-and-ops.md)): `CORE_R_CRON_ENABLED`, `COST_MODEL_V2_ENABLED`.

### Estudio = supervisión (ADR-024)

**Estudio** = único universo supervisable (lista API `estudio`). **Supervisión ON** arma Lab + CORE-R. El gráfico no mete valores. Quitar = unsubscribe. SEMI confirma operar/cambio de mandato. Detalle: [estudio-supervision-model-2026-08-06.md](./engineering/estudio-supervision-model-2026-08-06.md) · [ADR-024](./adr/024-estudio-supervision-universe.md).

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
