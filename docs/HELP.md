# Ayuda en la app — coordinación con trackers y docs

> **Sync:** `HELP_CONTENT_AS_OF` = **2026-08-03**  
> Ayuda «Datos de mercado» + Watchlist + «Análisis del valor» + **Backtesting** (Play ciclo, Lista AUTO **v1.3**, Finalistas A/C, Monitor + **CORE-R v1.12**, **DÍA D** Verify en LAB + **Reconciliación ADR-021** + contrafactual + continuidad lookback, Lab **CORE-B v0.2** · Lab Health Q0 · warm-up Q1.6) + Trading (rail Coach · ADR-019 · **Mandato ADR-020 M1b BD**).  
> **Cierre etapa (auditoría):** [engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md](./engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md).  
> **Roadmap post-auditorías:** [engineering/improvement-roadmap-post-audits-2026-08-02.md](./engineering/improvement-roadmap-post-audits-2026-08-02.md) — Q0–Q3 hecho.  
> **Decisión freeze:** [engineering/post-audit-decision-freeze-2026-08-03.md](./engineering/post-audit-decision-freeze-2026-08-03.md) — C4 no · Belief congelado · `CORE_R_CRON` / `COST_MODEL_V2` off.  
> **Futuro Belief→Coach (brief, no código):** [engineering/belief-coach-brief-draft-2026-08-03.md](./engineering/belief-coach-brief-draft-2026-08-03.md).  
> **Biblioteca estrategias L0/L1:** [engineering/strategy-library-authoring-brief-2026-08-03.md](./engineering/strategy-library-authoring-brief-2026-08-03.md) — Genéricas · Optimizadas · Mis estrategias (prompt).  
> **DEMO operativa SEMI:** [engineering/demo-operating-modes-brief-2026-08-03.md](./engineering/demo-operating-modes-brief-2026-08-03.md) · [impl slice 1](./engineering/semi-demo-book-impl-slice1-2026-08-03.md) — MANUAL/SEMI · Confirm F3 · sizing 10%.  
> **Auditoría (paquete único post-Q3):** [engineering/audit-pack-post-audits-2026-08-03.md](./engineering/audit-pack-post-audits-2026-08-03.md).  
> **Engineering Index / round 2 externas:** [engineering/engineering-index-2026-08-03.md](./engineering/engineering-index-2026-08-03.md) · [audit-ext-round2-triage](./engineering/audit-ext-round2-triage-2026-08-03.md).  
> **Respuesta auditoría 1 (ingesta+FIE):** [engineering/audit1-response-ingest-fie-2026-08-03.md](./engineering/audit1-response-ingest-fie-2026-08-03.md).  
> **Respuesta auditoría 2 (Lab backtests):** [engineering/audit2-response-backtests-lab-2026-08-03.md](./engineering/audit2-response-backtests-lab-2026-08-03.md).  
> **Premisas de proyecto:** [PROJECT_PREMISES.md](./PROJECT_PREMISES.md) — **documentar todo** (docs + docstrings/JSDoc).  
> **Docstrings (código):** [engineering/code-documentation-standard-2026-08-03.md](./engineering/code-documentation-standard-2026-08-03.md) — lotes 1–4 hechos; forward-only al tocar código nuevo.  
> **Repo:** público en GitHub (`jvelasca/Bolsa_V1`) para auditorías externas.  
> **Universos:** [LAB vs TRADING](./adr/019-dual-universes-lab-vs-trading.md) · [diseño](./engineering/dual-universes-lab-trading-design-2026-08-02.md) · [Mandato](./adr/020-operating-mandate-tenure.md) · [Reconciliación DÍA D](./adr/021-dia-d-reconciliation.md).  
> Configuración → **BD** (estado PostgreSQL, purga de huérfanos y demos cerradas).  
> **Espacios de trabajo:** chip superior → gestor (nuevo blanco / duplicar / renombrar); arranque = último activo.  
> Handoff: [engineering/session-handoff-2026-08-03-semi.md](./engineering/session-handoff-2026-08-03-semi.md) (SEMI libro DEMO) · [2026-08-01](./engineering/session-handoff-2026-08-01.md) (cierre racha) · previo [07-31](./engineering/session-handoff-2026-07-31.md) · DÍA D: [engineering/backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) · Plan prueba: [engineering/operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md) · Lista AUTO: [engineering/list-auto-ops-2026-07-29.md](./engineering/list-auto-ops-2026-07-29.md).  
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
| **Trading** | rail Coach + Libro DEMO + Mandato + alarmas → F3 | [demo-operating-modes](./engineering/demo-operating-modes-brief-2026-08-03.md) · [SEMI slice 1](./engineering/semi-demo-book-impl-slice1-2026-08-03.md) · [ADR-019](./adr/019-dual-universes-lab-vs-trading.md) · [ADR-020](./adr/020-operating-mandate-tenure.md) |

**Gráfico Trading — TOP#1:** en la barra global (junto a Indicadores), el switch **TOP#1** pinta/quita los indicadores del Finalista #1 del valor y timeframe del gráfico (`origin: finalist-top1`). No ejecuta mandato; OFF no toca indicadores manuales.
| Análisis del valor | `value-analysis-tracker.ts` | FA status / FIE |
| Datos de mercado | `data-market-tracker.ts` | data capture |
| Watchlist / listas | `watchlist-lists-tracker.ts` | lists-universes |
| Plataforma IA | `ai-platform-tracker.ts` | AI_PLATFORM_SOLUTION |
| Gráficos | `chart-platform-tracker.ts` | charts |

(El resto de filas del mapa histórico se mantienen en los trackers; este archivo prioriza Backtesting operativo.)

## Backtesting DÍA D (usuario · sync 2026-08-02 · U2)

**LAB (ADR-019):** **Verificar D→hoy** en Backtesting · Análisis técnico (Cartera LAB). Trading = inversión diaria + rail Coach. Detalle: [diseño dual](./engineering/dual-universes-lab-trading-design-2026-08-02.md) · [premisas](./engineering/backtesting-dia-d-premises-2026-07-31.md).

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
| 2 | Trading → rail Coach | Timeline **Mandato operativo** (tramo vigente + cerrados + flujo enlazado) |
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

Tras Lab → **Guardar Finalistas**, el resumen Hold-out / WF / CPCV (mismo vocabulario que el checklist) queda en `coachFacts.labEvidence` y se muestra en Finalistas y en el rail Coach. No es campaña multi-ventana ledger (eso sigue en Observatory / protocolo Q1.3).

## CORE-R / Monitor Finalistas (usuario · v1.12)

Guía en Ayuda → Backtesting (`BACKTESTING_CORE_R_GUIDE`). Detalle: [list-auto-ops § CORE-R](./engineering/list-auto-ops-2026-07-29.md).

| Paso | Qué |
|------|-----|
| 1 | Monitor (Probar o Ayuda) → elige lista con TOP |
| 2 | **Encolar revisiones** (informe Lista AUTO + PnL DEMO ≤ −5%/−10%) |
| 3 | Deep-links Lab / Finalistas / Checklist → **Hecho** |
| 4 | Opcional: **Narrar cola** · **Auto-sync app abierta** (cron shell) |
| 5 | Chip **CORE-R N** · toast «Abrir Monitor» (shell o cron servidor / otro device) |
| 6 | **Hecho todos** cierra las abiertas de la lista actual |

No pisa TOP · no auto-paper D. Cola: localStorage = cache; BD = SoT multi-dispositivo.  
Flags ops (off por defecto — ver [github-credentials-and-ops §9](./engineering/github-credentials-and-ops.md)): `CORE_R_CRON_ENABLED`, `COST_MODEL_V2_ENABLED`.

## Lista AUTO frescura (v1.3)

Tras reinicio, un 2º Play sobre la misma lista debe **Omitir** si periodo/costes/perfil no cambiaron y la última barra no aporta señal nueva (`1d` ≤5 días → `bar_hysteresis`). «Reevaluar resto» fuerza. Detalle: [list-auto-ops](./engineering/list-auto-ops-2026-07-29.md).

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
