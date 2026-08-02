# Research lifecycle (flujo operativo)

> Documento **operativo** (no filosófico). Complementa [ADR-016](../adr/016-research-persistence-model.md), [ADR-017](../adr/017-baseline-v1-5-research-observatory.md) y [domain-language.md](../domain-language.md).  
> Para nuevos desarrolladores: el camino completo en minutos.  
> **Ayuda en app:** pestaña Backtesting ← tracker `apps/web/src/features/settings/backtesting-tracker.ts` ([HELP.md](../HELP.md)).

**Sync:** 2026-08-02 · **Baseline v1.5** ([ADR-017](../adr/017-baseline-v1-5-research-observatory.md)) · Fase 1 + 1.5 · **Fase 2 P2.A–P2.F cerrada** ([ADR-018](../adr/018-fase2-evidence-store-v0.md)) · Batería `pnpm test:fase2` · Track lab UI P3–P9 cerrado · Embudo coach A–D + **Play ciclo** + **Lista AUTO frescura v1.3** · Finalistas → paper (A) / Supervisado (C) · **Monitor Finalistas** + **CORE-R v1.8** · **Backtesting DÍA D v0.11** · **CORE-B v0.2** · **ADR-019 dos universos LAB/TRADING** ([diseño](./dual-universes-lab-trading-design-2026-08-02.md) · [premisas](./backtesting-dia-d-premises-2026-07-31.md) · [plan prueba](./operativa-test-plan-2026-07-31.md)) · Handoff: [session-handoff-2026-08-01.md](./session-handoff-2026-08-01.md) · ops [list-auto-ops-2026-07-29.md](./list-auto-ops-2026-07-29.md).

---

## Resumen (no técnico)

Backtesting simula «qué habría pasado» con una regla en el pasado. No predice el futuro ni compra sola.

1. Abre **Backtesting** → **Probar estrategia**.
2. Elige un valor (o **Lista**) con histórico; periodo/capital en **Opciones avanzadas**.
3. **Play** (ciclo ON por defecto) encadena **1 Probar → 2 Coach → 3 Lab → 4 Revalidar → 5 Finalistas**. En Lista: el mismo embudo por cada ticker (máx. 40).
4. Alternativa manual: **Probar + coach** → Lab → Reanalizar → Guardar Finalistas.
5. Desde **Finalistas**: **Checklist** = deploy en **cuenta activa DEMO** (A); **Proponer** = Supervisado F3 (C). Distintos; ninguno es broker Paper.
6. En Ayuda → Backtesting: **Monitor Finalistas** = estado TOP/demo/Proponer (solo lectura). Plan D: Screeners propose/execute sobre DEMO (`PAPER_D_EXECUTE` off-by-default).
7. **DÍA D (verificación):** en Probar, fecha pasada en **Backtesting DÍA D** → Play → Finalistas **#1** → **Verificar D→hoy** → LAB Análisis técnico (película ± pantalla completa; Manual/Semi/Auto; Guardar Evidence; **Salir verificación**). Cartera LAB ≠ DEMO. Guía: [HELP.md § DÍA D](../HELP.md) · [premisas](./backtesting-dia-d-premises-2026-07-31.md) · [universos](./dual-universes-lab-trading-design-2026-08-02.md) · [plan](./operativa-test-plan-2026-07-31.md).
8. **CORE-R:** Monitor → Encolar / Narrar / Auto-sync · chip · toast **Abrir Monitor**. No pisa TOP. Ops: `pnpm test:operativa`.

**Premisa cuentas:** [account-premises-demo-vs-paper-2026-07-31.md](./account-premises-demo-vs-paper-2026-07-31.md) — una Activa **TRADING**; hoy solo DEMO · Cartera LAB = sandbox research.

**Universos:** [ADR-019](../adr/019-dual-universes-lab-vs-trading.md) — LAB (estudiar/verificar) ≠ TRADING (operar + rail Coach) · puente Adoptar / Abrir estudio.

Detalle: Ayuda (?) → **Backtesting** (tarjetas DÍA D + CORE-R). Cierre de sesión: [handoff 2026-07-29](./backtesting-funnel-handoff-2026-07-29.md).

---

## 1. Fase 1 — un backtest H0

```text
POST /api/backtests/run
        │
        ▼
┌───────────────────────┐
│ Backtest Engine       │  event-driven (ADR-009)
│ + costes reales PnL   │  commission / slippage / spread
│ + métricas brutas     │  Sharpe… en payload / is_metrics
└───────────┬───────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
backtest_runs   research_trials
(Experiment)    (ledger K, append-only)
     │             │
     └──────┬──────┘
            ▼
   API Response { run, trialId, metrics… }
            ▼
           UI
```

| Persistencia | Rol |
|--------------|-----|
| `backtest_runs` (+ trades) | Artefacto Experiment H0 |
| `research_trials` | Asiento científico (\(K\), params, métricas, `proposed_by`) |

**No en Fase 1 / 1.5:** Belief, Knowledge, Discovery Vector completo, Gate research.

---

## 1.5 Research Observatory (activa)

Capa de **solo lectura** sobre el ledger. Sin conceptos semánticos nuevos.

```text
research_trials
      │
      ▼
GET /research/trials
GET /research/trials/{id}
GET /research/instruments/{id}/summary
GET /research/summary
      │
      ▼
UI /research  (Dashboard · History)
UI /backtests (bloque Research en resultado)
```

| Entrega | Estado |
|---------|--------|
| F1.5.1 API consulta | ✅ |
| F1.5.2 Resultado BT (trialId, K, costes, IS) | ✅ |
| F1.5.3 Research History | ✅ |
| F1.5.4 Dashboard mínimo | ✅ |
| P5–P9 explotación lab UI | ✅ pausado — ver § «Cierre temporal — track laboratorio UI» |

**Criterio de salida → Fase 2:** madurez del laboratorio (API estable, UI inspeccionable, volumen de trials con sentido estadístico) — no calendario.

---

## 2. Optimize (hook ledger)

```text
POST /api/backtests/optimize[…]
        │
        ▼
optimization_runs  (job + result)
        │
        ├── por cada trial evaluado
        │         ▼
        │   research_trials  (k_contribution += 1)
        └── best params en result JSON
```

`trial_records` (RFC-008 cognitivo) **≠** `research_trials` (QROS).

---

## 3. Fases posteriores (mapa mental)

```text
research_trials
      │
      ▼
research_evidence     (P2.A — hecho)
      │
      ▼
hypothesis_beliefs    (P2.C — hecho)
      │
      ▼
knowledge_nodes       (P2.D — hecho; Consolidation explícita)
      │
      ▼
Reasoning → DecisionPackage → Trading Gate (RFC-008)
```

---

## 4. Checklist

### Fase 1

- [x] Motor aplica costes al equity/PnL  
- [x] Métricas ampliadas en respuesta + `is_metrics`  
- [x] Migración Prisma `research_trials`  
- [x] `RunAndSaveBacktest` escribe trial + devuelve `trialId`  
- [x] Hook optimize → trials  
- [x] Tests: costes; trial; \(K\) sumable  

### Fase 1.5

- [x] `GET /research/trials` (+ filtros / sort / paginación)  
- [x] `GET /research/trials/{id}`  
- [x] `GET /research/instruments/{id}/summary`  
- [x] `GET /research/summary` (dashboard lab)  
- [x] UI resultado BT: trialId, K, costes, métricas IS  
- [x] Research History + Dashboard  

### Disciplina (auditoría)

Objetivo Fase 1.5: **observabilidad**. Nada de Belief, Discovery Score, Curiosity, Knowledge Graph ni Planner IA.

Activación Fase 1.5: orden *«VAMOS con todo»* (2026-07-24).

**Baseline oficial:** [ADR-017](../adr/017-baseline-v1-5-research-observatory.md) — prioridad = explotar el laboratorio; Fase 2 solo por madurez empírica.

### Explotación (scripts)

Batería IBEX 35 → ledger \(K\) (mismos use-cases que la API):

```bash
python scripts/research/run_ibex35_battery.py
python scripts/research/run_ibex35_battery.py --optimize-top 2 --optimize-max-trials 30
python scripts/research/cross_family_consolidation.py
```

Inspección: UI `/research` (Dashboard / History) · notebooks en `research/observations/`.

### Criterio científico — abrir una nueva familia (C4+)

Una nueva familia **solo** se ejecuta si responde una pregunta que las familias existentes (SMA / RSI / MACD) **no pueden** responder.

| Cumple | Ejemplo |
|--------|---------|
| Sí | «¿La reversión por volatilidad (Bollinger) rompe el ranking de activo observado en C3.5?» — contraste fuertes vs débiles |
| No | «Añadir Stochastic porque existe en el catálogo» sobre los 35 a ciegas |

Tras C3.5: **pausa evaluativa**. Opciones documentadas en [cross-family notebook](../../research/observations/2026-07-24-ibex35-cross-family.md). Deuda técnica: [ISSUES.md](../../research/observations/ISSUES.md).

**Instrumentación (2026-07-24):** grids futuros escriben el mismo `is_metrics` IS que human (`sharpeRatio`, Sortino, Calmar, …). Sin backfill de K ya consumido.

---

## Producto UI — Fase A (wizard «Probar estrategia»)

Decisión de producto (2026-07-24): la pantalla principal de backtesting es el wizard **Probar estrategia** (lenguaje simple + tips `(i)`), con **un valor** y **periodo real** (`dateFrom`/`dateTo` o historial completo). Pestañas secundarias: Mis estrategias · Optimizar · Pruebas anteriores.

| Fase | Alcance |
|------|---------|
| **A** (hecho) | Wizard 1 instrumento + periodo + presets/guardadas |
| **B** (hecho) | Resultado visual unificado (veredicto + flechas + replay + equity + trades + análisis) |
| **C** (hecho) | Listas → N runs + ranking (cliente secuencial, máx. 40) |
| **D / P3–P3.O** (hecho / cerrado) | Optimizar guiado → lab (OOS/WF/CPCV/PBO, EdgeReport lite, Mejor OOS, adopt stash íntegro) |
| **P4 / P4.B** (hecho) | Checklist pre-paper (+ OOS/WF) + layout resultado redimensionable |
| **P5** (hecho) | Research History/detalle: columna Lab (WFE/PBO/Edge desde `blocks`) |
| **P2** (hecho / ampliado 2026-07-27) | Batería genéricas + coach profundo + techos ★ + TOP-3 persistido (`instrument_strategy_tops`) |
| **P6** (hecho) | Coach → Optimizar: hint hold-out/WF según barras (heurístico, sin LLM) |
| **P7** (hecho) | Paper post-checklist: snapshot lab en cuenta + UI honesta |
| **P8** (hecho) | EdgeReport lab → `edge_reports` cognitivo (sin auto-live) |
| **P9** (hecho) | Adopt → trial.blocks con provenance lab + ER id en Observatory |

API: `POST /api/backtests/run` acepta `dateFrom` / `dateTo` además de `limit`. Params del trial incluyen el rango.

**Fase B:** una sola composición en `BacktestResultView` — veredicto en lenguaje claro, gráfico de precio con flechas compra/venta (replay opcional), equity + lista de operaciones sincronizadas, análisis/trial bajo «Análisis detallado».

**Layout (2026-07-24):** hub `/backtests` rellena el viewport; `BacktestHubLayout` permite arrastrar separadores wizard↔resultado (horizontal en desktop, vertical en móvil) y, dentro del resultado, gráfico↔inferior y patrimonio↔operaciones. Preferencias en `localStorage` (`bolsa-backtest-layout-v1`).

**Fase C:** universo «Lista» en el wizard → `GET /api/lists/{id}` + N× `POST /api/backtests/run` (secuencial, cancelable). Ranking en UI (`BacktestRankingTable`) por Sharpe / retorno / drawdown / ops; clic → detalle unificado (Fase B). Sin endpoint batch ni entidad «campaña» aún.

### P1 — Baseline buy & hold + periodo para IA (2026-07-24)

Cada `run_backtest` escribe en `is_metrics`:

| Campo | Significado |
|-------|-------------|
| `buyHoldReturnPct` | Comprar al inicio del periodo y mantener (sin costes) |
| `excessReturnPct` | Retorno estrategia − buy & hold |

UI: bloque «Baseline» en el resultado; ranking ordenable por **Vs buy & hold**.

**Periodo por defecto:** `Todo el historial` (máx. 10 000 velas sincronizadas). Un año solo sirve para humo rápido; para que la IA explore indicadores/estrategias con criterio, preferir historial completo o ≥3–5 años y validar después en un subperiodo (p. ej. último año).

### P2 — Explorar valor (batería + coach) (2026-07-24; coach profundo 2026-07-27; coherencia TOP 2026-07-28)

Atajo **Probar + coach** / lote de genéricas (universo = un valor):

1. Ejecuta la batería completa de genéricas (`ALL_PRESET_COACH_KEYS` = catálogo `STRATEGY_PRESET_KEYS`, **21** presets a 2026-07-28). La lista corta `EXPLORE_PRESET_BATTERY` (~8) queda solo como referencia histórica.
2. Misma ventana / capital / costes / timeframe del wizard (**Opciones avanzadas** en el panel izquierdo).
3. Panel **Coach · TOP a futuro**:
   - **Quién elige el TOP-3:** ranking **local-AT** (determinista). La LLM (`POST /api/ai/backtest-coach/analyze`) **solo narra**; no sustituye `recommendations`.
   - **Sesgo a futuro (~48% del score):** tercios de equity (temprana / media / **reciente**). Una estrategia que brilló hace años y flojea ahora puntúa bajo aunque el % total sea alto.
   - Los tercios se **fijan en la fila de matriz** (`periodReturns`) al cerrar cada run OK y pasan a explore — no dependen del caché React Query / prune.
   - **Dedupe** por `strategyType`; **diversidad** por familia en el TOP-3 (estilo portfolio multi-strategy: no 3 clones de tendencia).
   - **Suelos de calidad:** tramo reciente / vs B&H flojos → `qualityFlagged` + penalización (evita crowning de “muy mala” si hay alternativas).
   - **Estabilidad UI:** mientras la batería corre **no** se muestra un TOP provisional; el ★ se fija al terminar el lote.
   - Empates: no-flagged → no-fallback → score → futureBias → late → excess → Sharpe → `strategyType`.
   - Tarjetas: Total · reciente · vs B&H · tercios; aviso si usó fallback suave.
4. **Techos de estrellas:** `evidenceLevel=in_sample_only` → máx. ★3; `lab_validated` → hasta ★5. UI con **medias estrellas** (pasos 0.5).
5. **CTAs Coach (copy 2026-07-28):**
   | Botón | Efecto |
   |-------|--------|
   | **Abrir Lab · #1** | Prefill Lab zona #1; el usuario lanza la búsqueda |
   | **Pasar las N al Lab** | Tablero 3 columnas + encola hasta N jobs (config editable por zona) |
   | **Lab** / **Lab (aprox.)** en tarjeta | Igual que Abrir Lab para esa candidata (proxy SMA/RSI si no hay grid nativo) |
   | **Guardar TOP-3** | Semifinal (`status=semifinal`, in-sample). Opcional si no se quiere Lab |
   | **Reanalizar con Coach** (desde Lab) | Persiste Mejores que mejoraron → re-simula → Coach² (`lab_validated`, ★≤5). Sin mejora: opcional «Llevar» solo aviso |
   | **Guardar Finalistas** (Coach²) | `active` + `lab_validated`. Lab **nunca** escribe Finalistas |

**Lab P0 (2026-07-28):** al «Pasar al Lab», SMA/proxies encolan **H0 + Optuna** (el panel une candidatos; mismo criterio que Play). RSI/MACD → grid H0. Cada zona muestra hero **Mejoró / Sin mejora** + badge `Corrió: engine · trials · OOS/WF`. No hace falta Play. Banner de actividad + progreso por zona mientras analiza.

**Lab P1 (2026-07-28):** heatmap de scores (fast×slow / RSI) + **top-5** + detección de **meseta** (vecinos ±tol). Si falla guardar el Mejor al «Reanalizar con Coach», **se bloquea** el handoff completo (`resolveLabReanalyzeGate`). Smoke CAF: `lab-coach-caf-smoke.test.ts` (3 Mejores mismo `presetKey` + `definitionId` distintos; soft ACK post-Lab).
6. Bloques colapsables: Análisis AT / Comparativa vs B&H / **Resultados de la batería** (tabla % histórica; distinta del TOP ★).
7. Persistencia: `PUT /api/instruments/{id}/strategy-top` · `GET …/strategy-top`. `GET /strategies` limit **200**.
8. **Calidad:** `pnpm test:coach` (coherencia multi-instrumento + Guardar TOP-3 + **doble auditoría** A/A2/B/C + red-team + quorum).
9. **Doble auditoría (2026-07-28 → F2–F5):** Motor A shortlist → Motor B heurístico (siempre) + veto tipado LLM narrador → **Auditor C adversario** (prompt distinto, allowlist) → shadow A2 → gate TOP-3 → **red-team** (hard/soft) → **quorum UI** (chips A/A2/B/C + por qué #1) → badge Consenso/Discrepancia/Débil. Post-Lab (`coachPass=post_lab`): soft-fail no fuerza ACK si #1 limpia.

**No es:** “la IA elige las 3 mejores entre todas las sims históricas del valor”. Solo el lote actual (genéricas ± Mis estrategias según prefs). **Reutilizar lote** si fingerprint (valor/periodo/costes/TF + set de `rowId`) coincide — prefs Asistente «Reutilizar lote si no cambió» (default ON). «Incluir Mis estrategias» añade `saved:*` al Universo (tope matriz 40).

Sin declarar «lista para invertir». El TOP persistido es semifinal del embudo (coach → lab → checklist → paper).

#### Catálogo de genéricas (2026-07-28)

Fuente única: `packages/shared/src/strategy-presets.json` (+ enum Prisma `BacktestStrategyType`).

Ampliación v2 (además de SMA/RSI/MACD/BB/CCI…): `donchian_breakout`, `adx_di_trend`, `ichimoku_tk_cross`, `vwap_reclaim`, `supertrend_follow`.  
Motor: `_series_for_spec` en `rules_engine.py` + OHLC real en `BacktestBarInput` / `run_backtest`.  
Migración: `packages/database/prisma/migrations/20260727120000_expand_strategy_presets_v2`.

#### Hub UX Probar (2026-07-28)

| Pieza | Comportamiento |
|-------|----------------|
| **Matriz** | CTA **Probar + coach** = filtro activo (o selección). Finalistas re-ejecuta defs guardadas (preset completo del catálogo; fix 2026-07-28). Asistente Universo = todas las genéricas. |
| **Opciones avanzadas** | Periodo, capital, TF, comisión, slippage, import gráfico (resumen en la línea del `<details>`) |
| **Resultado** | Al elegir valor → pestaña Detalle con preview (gráfico + B&H). Con prueba: Detalle/Coach/Lab/Finalistas; barras global/temporal con acciones en la misma fila |
| **Análisis global / Datos temporales** | Franjas apiladas a ancho completo; en Análisis global, **Últimos 12m** (estrategia / B&H / Δ) a la derecha; si el detalle es Finalista del valor, badge **TOP #n** + ★ del slot |
| **Paper / Supervisado** | Checklist → Desplegar (A). Finalistas: Checklist + Proponer (C). Biblioteca: Usar sin atajo Paper. Radar = B etiquetado. Monitor en Ayuda |
| **Research** | Pruebas anteriores → enlace ledger; Detalle chip Research; Observatory Resumen/Historial |
| **Biblioteca / Lab / Historial (UI 2026-07-28)** | Biblioteca first + filtros; Lab empty→Coach; Historial lista + ⚙ tope; Config con historial/matriz/recordatorios |

#### Embudo A+B (2026-07-27)

| Pieza | Rol |
|-------|-----|
| **A — Motor coach** | Ranking local + `periodReturns` / ventanas equity + techos ★ + `buildCoachFacts` hacia LLM |
| **B — InstrumentStrategyTop** | Persistencia TOP-3 por valor/TF (`ART-INSTRUMENT-TOP`) como semifinal |
| **C — Promoción lab** | Adoptar Mejor con OOS/WF/CPCV → TOP `active` + `lab_validated` |
| **D — Asistente rail** | Mapa 5 etapas: Probar → Coach → Lab → Revalidar → Finalistas |

#### Embudo D — Asistente de exploración (2026-07-27; ciclo 2026-07-28; mapa 5 + ACK 2026-07-30)

| Pieza | Rol |
|-------|-----|
| **Rail** | `BacktestAssistantRail` — chips 1…5 + Play / ↻ / (⋯) |
| **Play: ciclo completo** | Pref `fullCycleOnPlay` (default ON): Probar → Coach → Lab TOP-3 → Revalidar (Coach²) → Finalistas en **1 valor** |
| **Handoff Lab→Coach²** | Con ciclo activo, al terminar zonas con ≥1 Mejor ≥ ancla → auto «Reanalizar con Coach» |
| **Auto Finalistas** | Tras Coach²: guarda `active` + `lab_validated` solo si hubo mejora Lab y TOP guardable; si no, **no pisa** TOP active previo. Settle marca `finalistsSaved` / `finalistsSkipped` (no ✓ falso) |
| **Soft-ACK / ACK¹** | ACK se resetea solo al cambiar lote. Prefs: `requireAckBeforeLab` (ON), `autoAckOnCycle` (ON), `pauseIfAckNeeded` (OFF), `saveSemifinalSkipLab` (OFF). Diagrama en (⋯) |
| **Sin mejora Lab** | No Revalidar · no grabar · Finalistas intactos (rama fija del diagrama) |
| **Play paso a paso** | Pref OFF: un paso por clic (comportamiento previo) |
| **Coach: encolar Lab TOP-3** | Pref `(…)` → al entrar en Coach puede encolar Lab |
| **Abrir Lab · #1** | Prefill sin encolar (revisar y lanzar a mano) |
| **Umbral ≥ ancla** | «Guardar Mejor y probar» solo si Mejor ≥ ancla (OOS preferido) + evidencia lab |
| **Mis estrategias → TOP** | Filtro Finalistas por `strategyDefinitionId` de slots |
| **Progreso sesión** | Los ✓ son de esta pasada. ↻ reinicia el embudo (y cancela ciclo) |

Siguiente fuera de este embudo: Moat/Management o rf live (opcional). **Monitor Finalistas MVP** = estado solo lectura.

**Handoff sesión 2026-07-29:** [backtesting-funnel-handoff-2026-07-29.md](./backtesting-funnel-handoff-2026-07-29.md) (mapa código, smoke, continuación mañana).

**Diseño 1-Play + CORE Coach/Lab (reanálisis, pendiente de implementar):** [assistant-play-funnel-design-2026-07-29.md](./assistant-play-funnel-design-2026-07-29.md).

#### Lista AUTO — campaña por watchlist (2026-07-28 · frescura 2026-07-30)

| Pieza | Rol |
|-------|-----|
| **Entrada** | Modo Universo **Lista** + Play con `fullCycleOnPlay` ON |
| **Átomo** | Mismo ciclo completo 1 valor (Coach → Lab → Coach² → Finalistas) |
| **Bucle** | Secuencial por `instrumentIds` (soft cap **40**, igual que Fase C) |
| **Settle** | Avance tras save / skip Lab / omitido frescura / anti-hang |
| **Cancel** | ↻ del Asistente aborta la campaña |
| **≠ Fase C** | «Probar lista» = 1 estrategia × N → ranking |
| **UX lista** | Play sin elegir estrategia; «Probar lista» en `<details>` |
| **Tablero** | Estados + Δ + Reeval (CORE-R) + Últ. búsqueda; pestaña Lista AUTO |
| **Pausa / Stop** | Pausa persiste reinicio; Stop → siguiente Play continúa; Forzar = ignore frescura |
| **Segundo plano** | Keep-alive al salir a Trading; chip en barra de estado + badge nav |
| **Frescura v1.3** | Huella local+DB; histéresis `lastBarDate` (1d ≤5d → `bar_hysteresis`; stamp no desliza); omitir tras reinicio si igual |
| **CORE-B Lab v0.2** | Memoria adopción + meseta→espacio; familia por defecto = adopción → horizonte perfil → SMA |
| **Doc operativa** | [`list-auto-ops-2026-07-29.md`](./list-auto-ops-2026-07-29.md) · handoff [`session-handoff-2026-07-30.md`](./session-handoff-2026-07-30.md) |

No confundir con wizard multi-instrumento Fase C.

#### CORE-R — Reevaluación continua de estrategia (**CRÍTICO · v0–v1.8 · 2026-07-31 / 08-01**)

| Pieza | Rol |
|-------|-----|
| **Qué** | Comprobar si Finalistas / estrategia en curso siguen siendo adecuados o conviene optimizar / cambiar |
| **v0** | Juicio post-settle Lista AUTO · columna Reeval · informe `bolsa-core-r-report-v1` |
| **v1** | Monitor → **Encolar revisiones** · cola humana (`bolsa-core-r-review-queue-v1`) · deep-links |
| **v1.1** | Degradación OOS (PBO / edge / credibilidad / retorno) en juicio |
| **v1.2** | PnL live DEMO/paper en Monitor · cola por −5%/−10% · scheduler lite (panel abierto) |
| **v1.3** | **Narrar cola** (`/api/ai/core-r/review-evidence`) · heurística + LLM opcional |
| **v1.4** | **Cron shell** (`CoreRSchedulerHost`) mientras la app está abierta |
| **v1.5** | **Chip barra** «CORE-R N» → Ayuda · Monitor · deep-link hub `focus=monitor` |
| **v1.6** | **Toast** si tick encola filas (`added > 0`) |
| **v1.7** | Toast con acción **Abrir Monitor** |
| **v1.8** | **Hecho todos** (`dismissOpen`) · selector chip zustand estable |
| **Pendiente** | Cron multi-dispositivo (report/cola en servidor) |
| **≠ D** | No es auto-paper; no pisa `active`. Ver `ISSUES.md` · CORE-R |
| **Ops** | `pnpm test:operativa` |

#### Biblioteca — alcance S3 + historial (2026-07-28)

| Pieza | Rol |
|-------|-----|
| **Alcance** | `universe.instrumentIds` vacío = **reutilizable**; no vacío = **ajuste** a valor(es). Expuesto en `GET /api/strategies` como `instrumentIds`. |
| **Filtros Mis estrategias** | Búsqueda + alcance + timeframe + origen (`mine-strategies-filters.ts`) |
| **Pruebas anteriores** | Tope configurable ⚙ (default **20**, rango 5–100); prune en BD al guardar prefs |

#### Embudo C — Promoción lab → TOP active (2026-07-27)

| Pieza | Rol |
|-------|-----|
| **Trigger** | «Guardar Mejor y probar» con evidencia hold-out / walk-forward / CPCV (`canPromoteTopFromLabEvidence`) |
| **Merge** | `buildLabPromotionUpsert`: candidato lab → slot #1 (`source=optimized`); conserva hasta 2 slots coach previos |
| **Persist** | `PUT …/strategy-top` con `status=active`, `evidenceLevel=lab_validated` (techo ★5 en coach) |
| **Sin OOS** | Solo guarda la estrategia; no toca el TOP (sigue semifinal / in-sample) |
| **Handoff paper (2026-07-29)** | Finalistas con `runId`: CTA **Checklist** → Detalle + checklist pre-paper (Camino A). Sin re-Lab ni deploy directo. |
| **Handoff Supervisado (2026-07-29)** | Finalistas `lab_validated`: CTA **Proponer** → propose FA+perfil → cola F3 origen **Finalistas** → Ayuda scroll a Confirm. Humano confirma. ≠ paper A ≠ auto D. |

#### Monitor Finalistas MVP (2026-07-29)

| Pieza | Rol |
|-------|-----|
| **Dónde** | Hub Probar (desplegable) + Ayuda → Backtesting (`strategy-monitor-panel.tsx`) |
| **Entrada** | Watchlist/lista elegida (soft cap **40**, mismo que Lista AUTO / Fase C); en hub prefills la lista del Universo |
| **Filas** | TOP status + evidenceLevel + #1; DEMO/paper vinculado (`strategyDefinitionId` + `labEvidence` + retorno %); último Proponer F3 origen Finalistas |
| **Enlaces** | Finalistas · Checklist (`?openAnalysis=1` → Detalle + checklist) · F3 (si hay ítem en cola) |
| **CORE-R** | Encolar informe + PnL; cron shell; chip barra; toast al encolar |
| **No es** | Auto-paper D, cron multi-dispositivo, deploy, execute, unificación A/B |

Helpers: `strategy-monitor.ts`. Copy: `PAPER_PATH_MONITOR`. Handoff: [backtesting-funnel-handoff-2026-07-29.md](./backtesting-funnel-handoff-2026-07-29.md).

### P3 — Optimizar guiado (2026-07-24; CTAs 2026-07-28)

Desde el coach (**Abrir Lab · #1** / **Lab** en tarjeta / **Pasar las N al Lab**) o el detalle (**Lab**):

1. Abre la pestaña **Lab** (o hub Optimizar) con semilla (`OptimizeSeed`): instrumento, capital, timeframe, anclas.
2. Familias nativas de grid: SMA / RSI / MACD. Otros presets usan **proxy** (nota `optimizeFamilyProxyNote`).
3. «Encolar» dispara jobs; «Abrir Lab» solo prefills — el usuario lanza.
4. No declara «lista para paper»; adoptar Mejor ≥ ancla con evidencia OOS.

### P3.B — Laboratorio (espacio + ancla + Δ) (2026-07-25)

UI **Optimizar** como laboratorio (no caja negra):

| Pieza | Comportamiento |
|-------|----------------|
| Ancla | Periodos + métricas de la operativa original (seed), no baseline fija 20/50 |
| Espacio | Editor min / max / paso → listas de periodos; combina válidas (`rápida < lenta`) |
| Criterio | Visible: `score = return% − 0.25 × maxDD%` (mismo que el motor) |
| Progreso | `trialCount` / `trialsTotal` + `bestScore` mientras `status=processing` (H0 await; VectorBT/Optuna vía poller del hilo) |
| Comparación | Tabla Ancla / Mejor / Candidatos con Δ params · return · DD · score |
| Guardar | Candidato → estrategia propia SMA (luego «Probar» en el wizard) |

API: `optimization_runs.payload.trialsTotal`; `update_progress` mid-job; result incluye `trialsTotal`.

### P3.C — Hold-out OOS + familias RSI/MACD (2026-07-25)

| Pieza | Comportamiento |
|-------|----------------|
| Hold-out | `oosPct` (p. ej. 0.2): búsqueda solo en IS; re-evalúa ancla y trials en OOS. **No** es walk-forward |
| Resultado | `oosPct`, `isBarCount`, `oosBarCount`, `splitTimestamp`; cada trial puede llevar `oosMetrics` |
| Ledger | OOS en `research_trials.blocks.oosMetrics` (IS sigue en `is_metrics` / `is_score`) |
| Familias | `strategyFamily`: `sma_crossover` \| `rsi_mean_reversion` \| `macd_signal_cross` |
| Motores | VectorBT/Optuna siguen SMA-only; RSI/MACD = grid H0 (`rsi_grid_h0` / `macd_grid_h0`) |
| UI | Selector de familia + espacio RSI/MACD; columnas Ret./Score OOS; guardar estrategia propia por familia |

### P3.D — Tras el Mejor + métodos múltiples (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Tras Mejor | Pasos 1–3 + botones **Guardar Mejor y probar** / **Solo guardar** |
| Adoptar | Guarda estrategia SMA/RSI/MACD → abre Probar → **lanza backtest** con mismo valor / TF / barras |
| Métodos | SMA: checkboxes Grid + VectorBT + Optuna (varios a la vez); se unen candidatos por params |
| Contenedor | Jobs ~1600px de ancho para la tabla de comparación |

### P3.E — Walk-forward expandido (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Modo | `walkForwardFolds` (2–5); **excluye** `oosPct` (hold-out) |
| Algoritmo | Expanding: pliegue \(i\) entrena en segmentos \(0..i\), valida en \(i+1\) |
| Por pliegue | Re-optimiza grid H0 en train → mejor IS → evalúa en test OOS |
| Resultado | `walkForward` (media/σ OOS de seleccionados + detalle por pliegue); tabla = último pliegue + su OOS |
| Motores | Solo H0 (SMA/RSI/MACD). Optuna/VectorBT no en WF v1 |
| No es | CPCV, PBO, embargo/purge (WFE lab sí: ver P3.I) |

### P3.F — Elegir «Mejor» por OOS (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Problema | La búsqueda sigue en IS, pero el pico IS suele sobreajustar |
| Default | Con hold-out/WF, «Mejor» = mayor **score OOS**; toggle a Score IS |
| UI | Etiqueta `Mejor OOS` / `Mejor IS (no OOS)` si divergen; aviso al adoptar |
| Fusión multi-método | Si hay OOS, gana el mejor OOS por params |
| Calidad | OOS con &lt; 2 ops se penaliza al rankear (evidencia débil) |

### P3.G — OOS con warm-up + adoptar sin cold-start (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Bug detectado | Cortar el BT de adopción en `splitTimestamp` dejaba SMA/RSI/MACD **sin warm-up** → resultados peores/engañosos |
| OOS en lab | `_eval_oos_for_grid`: indicadores sobre IS+OOS; **trading solo en OOS** (`trade_from_index`) |
| Adoptar | **Guardar Mejor y probar** relanza la ventana completa del lab (`barLimit`) con warm-up |
| Evidencia OOS | Sigue en el lab + stash/checklist P4.B — no se re-corta el periodo al split |
| Verificación | `pnpm test:optimize` (batería completa) · `python scripts/research/verify_oos_warmup.py` |

### P3.H — Orden API = Mejor OOS (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Problema | Con hold-out, `trials[0]` era el pico **IS**; clientes/scripts que toman el primero veían un «Mejor» engañoso |
| Fix | `rank_trials_for_result` tras `_attach_oos` (hold-out y WF): orden por score OOS; OOS con &lt; 2 ops penalizado (misma regla que UI) |
| Sin OOS | Sigue orden por score IS |
| Tests | `test_part_rank_trials_*` + assembly + smoke API comprueba que `trials[0]` es el mejor OOS |

### P3.I — WFE + estabilidad walk-forward (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| WFE lab | `walkForwardEfficiency` = media score OOS / media score IS (solo si media IS &gt; 0) |
| Por pliegue | `folds[].walkForwardEfficiency` = OOS/IS del campeón de ese pliegue |
| Estabilidad | `oosCv` = σ/|media| OOS; `positiveOosFoldShare` = fracción de pliegues con OOS ≥ 0 |
| UI | Bloque WF muestra WFE (aceptable ≥0.7 / frágil ≥0.5 / débil) + CV + pliegues OOS≥0 |
| Checklist | Aviso si WFE &lt; 0.5, CV &gt; 1 o &lt;50% pliegues OOS≥0 (aunque media OOS ≥ 0) |
| Ledger | Campos WFE/CV/share en `blocks.walkForward` |
| No es | CPCV, PBO ni edge de producción |

### P3.J — CI batería Optimizar (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Workflow | `.github/workflows/optimize-lab.yml` → `pnpm test:optimize` en push/PR (paths del lab) |
| Smoke API | Opcional en CI (`OPTIMIZE_API_REQUIRED=0`); contrato DTO WFE validado en el job |
| Local | Con API + OHLCV: `OPTIMIZE_API_REQUIRED=1 pnpm test:optimize` |

### P3.K — CPCV ligero (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Request | `cpcvGroups` (4–6), `cpcvPurgeBars` / `cpcvEmbargoBars` (0–20); **prioridad** sobre WF y hold-out |
| Algoritmo | N grupos contiguos; C(N,2) paths; test = 2 grupos; purge antes + embargo después de cada bloque test |
| Por path | Re-optimiza grid H0 en train purgado → mejor IS → OOS con warm-up |
| Resultado | `cpcv` (media/σ/WFE/CV/share + paths); tabla = último path + su OOS |
| UI | Tercer modo exclusivo; solo H0; historial largo recomendado |
| No es | CPCV de eventos (PBO CSCV lab sí: ver P3.N) |

### P3.L — WFE lab → Evidence Engine (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Provenance | `suite.wfeSource`: `lab_score` \| `sharpe` |
| Preferencia | `EvidenceEngineInput.lab_walk_forward_efficiency` gana sobre Sharpe WFE |
| Ledger | `blocks.labEvidence` + WFE en `walkForward` / `cpcv` |
| UI | Credibility hint (solo WFE lab) tras WF/CPCV; checklist usa WFE lab |
| Shared | `pickLabWalkForwardEfficiency` / `applyLabWfeToSuite` / `credibilityHintFromLabWfe` |
| No es | EdgeReport completo automático (MC/DSR: ver P3.M) |

### P3.M — EdgeReport lab lite (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Cuándo | Tras optimize (hold-out / WF / CPCV / IS) si el campeón tiene ≥3 ops cerradas |
| Suite | MC permutation + PSR/DSR (`trialsN` = trials del lab) + WFE lab (`wfeSource: lab_score`) |
| Trades | Round-trips del Mejor; ventana OOS con warm-up cuando hay hold-out/WF/CPCV |
| Resultado | `edgeReport` en API + `blocks.edgeReport` / checklist `edge_report` |
| UI | Bloque banda + credibility + MC p + DSR/PSR/WFE |
| No es | Auto-live / Belief (persistencia cognitiva lite: ver P8) |

### P3.N — PBO CSCV lab (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Cuándo | Automático al cerrar **CPCV** (S par ≥4; si grupos=5 → S=4) |
| Matriz | Scores lab de hasta 40 candidatos × S segmentos (warm-up hasta el segmento) |
| Algoritmo | CSCV Bailey et al.: splits C(S,S/2); λ=logit(rango OOS del campeón IS); PBO=fracción λ≤0 |
| Resultado | `pbo` + `cpcv.pbo`; checklist avisa si PBO ≥ 0.5; nota en EdgeReport |
| UI | En bloque CPCV: PBO + banda (bajo / elevado / alto) |
| No es | PBO sobre eventos/labels, ni CSCV con S=16 clásico (lab usa 4–6) |

### P3.O — Cierre laboratorio Optimizar (2026-07-26)

Slice de producto **cerrado** (Fase D / P3–P3.N + P4/P4.B). Closeout:

| Pieza | Comportamiento |
|-------|----------------|
| Adopt stash | `buildOosEvidenceForAdopt`: WF/CPCV (+ PBO/Edge) no se degradan a hold-out por `oosMetrics` del último path; hold-out conserva Edge del resultado |
| UI | Copy CPCV menciona PBO CSCV lab; franja resumen modo · WFE · PBO · Edge · «lab, no producción» |
| Checklist | Tras adoptar, stash → `resolveOosEvidence` → paper gate con CPCV/PBO/Edge |
| Fuera de alcance | PBO eventos S=16, Belief/Knowledge, auto-live (edge_reports lab: P8) |

### Batería de tests — laboratorio Optimizar

Comando único (piezas + conjunto):

```bash
pnpm test:optimize
# equivalente: node scripts/research/verify_optimize_battery.mjs

# Smoke HTTP (API + BD + OHLCV). Obligatoria si:
OPTIMIZE_API_REQUIRED=1 pnpm test:optimize
```

| Fase | Qué cubre |
|------|-----------|
| 1 Python | hold-out, WF/WFE, CPCV, PBO, EdgeReport→edge_reports (P8), paper (P7), adopt blocks (P9), OOS warm-up, grids |
| 2 Script | regresión cold-start vs warm-up (`verify_oos_warmup.py`) |
| 3 Web | rank Mejor OOS, WFE/CPCV/PBO/Edge, Observatory Lab+ER (P5/P9), coach hint (P6), paper (P7), adopt stash |
| 4 API* | `verify_optimize_api_smoke.py` — SKIP si API caída; FAIL si `OPTIMIZE_API_REQUIRED=1` |

Pipeline assembly (sin DB): `packages/py/application/tests/test_optimize_pipeline_battery.py`.

#### Política de calidad (obligatoria en cada mejora)

Optimizar es **parte crítica** de la app. Cada cambio debe:

1. Añadir/actualizar **tests de pieza** (Python y/o Vitest).
2. Extender el **conjunto** (`test_optimize_pipeline_battery.py` y/o tests UI) si cambia el flujo.
3. Registrar archivos nuevos en `scripts/research/verify_optimize_battery.mjs` (`pyTests` / `webTests`).
4. Documentar el comportamiento aquí (sección P3.x / P4.x).
5. Pasar **`pnpm test:optimize`** en verde antes de dar por cerrado.

No basta con “funciona a ojo”: debe ser correcto, reproducible y de máxima calidad (warm-up OOS, Mejor por OOS, orden API=OOS, WF/CPCV + WFE lab→evidence, adoptar sin cold-start, checklist honesto). Regla Cursor: `.cursor/rules/optimize-lab-quality.mdc`. CI: workflow **Optimize lab**.

### P4 — Checklist pre-paper (2026-07-24)

En el resultado unificado:

1. Bloque **Checklist pre-paper** con checks heurísticos (ops, vs B&H, drawdown, muestra, estrategia guardada, ack in-sample).
2. El botón **Desplegar en paper** solo se habilita sin bloqueos duros y con avisos reconocidos.
3. Crea cuenta paper desde el `runId` **solo si** hay `strategyDefinitionId` (API 400 si falta; checklist lo bloquea).
4. No es gate de producción — solo evita despliegue a ciegas en UI (evidencia lab: P7).

### P4.B — OOS / WF en checklist (2026-07-26)

| Pieza | Comportamiento |
|-------|----------------|
| Check `oos_validation` | Sin evidencia → warn + ack; hold-out/WF con score≥0 → pass; score&lt;0 → warn + ack |
| Fuente | `research_trials.blocks` (ledger; tras P9 el adopt ya escribe provenance) o stash de sesión |
| Ack in-sample | Copy distinto si ya hay OOS/WF pass (sigue siendo simulación) |
| Límite | No inventa edge; no sustituye CPCV/PBO; el stash sigue siendo respaldo UX, no fuente única |

**Layout resultado:** resumen redimensionable con scroll (`headerHeightPct`), splits gráfico/inferior y patrimonio/ops (también apilado), prefs en `localStorage` (`bolsa-backtest-layout-v2`). Durante la película el balance muestra patrimonio y ops en esa fecha.

### P9 — Adopt provenance durable + Observatory ER (2026-07-27)

Cierra el hueco «adopt → solo stash de sesión»:

| Pieza | Comportamiento |
|-------|----------------|
| Request | `POST /backtests/run` acepta `labEvidence` opcional |
| Persistencia | `RunAndSaveBacktest` → `trial.blocks` vía `trial_blocks_from_lab_evidence_snapshot` (`mode: adopt_provenance`) |
| UI adopt | «Guardar Mejor y probar» envía el snapshot lab al nuevo H0 |
| Observatory | Columna Lab muestra `ER {persistedEdgeReportId}` si existe (P8) |
| Nota | No revalida OOS en el H0; es copia de provenance del laboratorio |
| No es | Belief, auto-live, re-ejecutar CPCV en el adopt |

### P8 — EdgeReport lab → edge_reports (2026-07-27)

Tras optimize con EdgeReport lite (≥3 ops campeón), se persiste en la tabla cognitiva `edge_reports`:

| Pieza | Comportamiento |
|-------|----------------|
| Hook | `ProcessOptimizationRun` / sync optimize-and-save → `persist_lab_edge_report_if_present` |
| Mapper | Suite lab → `StatisticalSuiteResult`; notes incluyen `lab_lite · not auto-live` |
| Resultado | `edgeReport.persistedEdgeReportId` en API + `blocks.edgeReport` |
| `auto_trial` | **False** (no ensucia Effectiveness) |
| UI | Optimizar muestra id persistido si existe |
| No es | Auto-live, Belief, production gate; `autoLiveEligible` del lab se ignora / fuerza false al persistir |

### P7 — Paper post-checklist + evidencia lab (2026-07-27)

Al **Desplegar en paper**, la cuenta guarda provenance lab (no gate de producción):

| Pieza | Comportamiento |
|-------|----------------|
| Persistencia | `settings_json.labEvidence` (kind · WFE · PBO · Edge · trialId…) |
| Fuente | Preferir `research_trials.blocks` del run (tras P9 el adopt ya copia provenance); si vacío, hint del checklist/stash |
| API | `labEvidence` opcional en `DeployPaperAccountRequest`; DTO cuenta expone `labEvidence` |
| UI | Banner al llegar a `/accounts` + línea «Evidencia lab» en detalle paper |
| Checklist | Sin `strategyDefinitionId` → **fail** (el API lo exige) |
| No es | Belief, auto-live, gate de producción (`edge_reports` lite = P8, aparte de este snapshot en cuenta) |

### P6 — Coach → Optimizar con hint OOS/WF (2026-07-27)

La exploración y el resultado BT son **solo in-sample**. Al abrir Optimizar desde coach/detalle, el lab preactiva validación según barras:

| Barras | Prefill |
|--------|---------|
| &lt; 250 | Sin hold-out/WF (historial corto) |
| 250–799 | Hold-out ~20% |
| ≥ 800 | Walk-forward expandido (3 pliegues) |

| Pieza | Comportamiento |
|-------|----------------|
| Heurística | `suggestOptimizeValidation` → `OptimizeSeed.validationHint` |
| Coach | Bullet + next step con el mismo hint (`buildExploreCoachNote`) |
| Panel | Aplica hint al cargar seed (desactiva CPCV); muestra razón en banner origen |
| No es | LLM, CPCV automático, ni declarar edge / paper listo |

### P5 — Lab evidence en Research Observatory (2026-07-27)

Explotación del ledger (ADR-017): la validación lab ya está en `research_trials.blocks`; el Observatory la hace visible.

| Pieza | Comportamiento |
|-------|----------------|
| Fuente | `extractOosEvidenceFromTrial` sobre `blocks` (hold-out / WF / CPCV + PBO + Edge) |
| History | Columna **Lab** compacta (modo · WFE · PBO · Edge) |
| Detalle | Bloque «Validación lab» en `ResearchTrialResultBlock` (también en resultado BT si hay trial) |
| API | Sin cambios — list/detail ya devolvían `blocks` |
| No es | Belief/Knowledge, gate de producción (`edge_reports` lab: P8; adopt durable: P9) |

---

## Cierre temporal — track laboratorio UI (P3–P9)

**Estado (2026-07-27):** pausa deliberada del track lab. El laboratorio Optimizar + explotación Observatory/paper está **cerrado y documentado**. Fase 2 abierta solo vía [ADR-018](../adr/018-fase2-evidence-store-v0.md) (Evidence v0); Belief/Knowledge siguen congelados.

### Mapa entregado

| ID | Entrega |
|----|---------|
| **P3–P3.O** | Lab Optimizar: hold-out, WF, CPCV, PBO CSCV, EdgeReport lite, Mejor OOS, WFE→evidence, adopt stash |
| **P4 / P4.B** | Checklist pre-paper (+ OOS/WF/CPCV/PBO/Edge) |
| **P5** | Research History: columna Lab desde `blocks` |
| **P6** | Coach → Optimizar: prefill hold-out/WF por barras |
| **P7** | Paper: `settings_json.labEvidence` + UI honesta |
| **P8** | Optimize → fila en `edge_reports` (sin auto-live; `auto_trial=false`) |
| **P9** | Adopt → `trial.blocks` con provenance + `ER …` en Observatory |

### Flujo extremo a extremo (referencia)

```text
Explorar valor (IS)
      │ coach P6 → hint OOS/WF
      ▼
Optimizar (hold-out | WF | CPCV+PBO) + EdgeReport lite
      │ P8 → edge_reports (cognitivo, no auto-live)
      │ P3.O stash + ranking OOS
      ▼
Guardar Mejor y probar (adopt)
      │ P9 → labEvidence en POST /backtests/run → trial.blocks
      ▼
Resultado H0 + checklist pre-paper (ledger o stash)
      │ P7 → deploy-paper + settings_json.labEvidence
      ▼
Cuenta paper («Evidencia lab · … · no producción»)
      │
      ▼
/research History · columna Lab (+ ER id si P8)
```

### Cómo verificar al reanudar

```bash
pnpm test:optimize
# Con API + OHLCV reales:
OPTIMIZE_API_REQUIRED=1 pnpm test:optimize
```

Regla Cursor: `.cursor/rules/optimize-lab-quality.mdc` · CI: workflow **Optimize lab**.

### Fuera de alcance del track lab (sigue vigente)

| Tema | Motivo |
|------|--------|
| Discovery / Planner IA / Decay+Pruning / UI cognitiva | Congelado tras P2.F; dominio Evidence→MKL stub cerrado |
| PBO eventos / CSCV S=16 | Lab usa S=4–6 sobre scores |
| Auto-live / production gate | Solo provenance + checklist UX |
| `macd-signal-ema-warmup` | Deuda en `research/observations/ISSUES.md` |

### Narrativa unificada — caminos a paper / auto (NO OLVIDAR)

> **Estado:** decisión de producto **2026-07-28** — mantener radar etiquetado; auto completo (D) congelado.  
> **Ampliación 2026-07-29:** Finalistas abre Camino A (Checklist) y Camino C (Proponer); Monitor MVP = estado solo lectura.  
> Complementa [ADR-010](../adr/010-platform-kernel-radar-execution.md) · [RFC-008](../rfc/008-cognitive-decision-architecture.md) · Ayuda Backtesting · `paper-paths-copy.ts` · [handoff 2026-07-29](./backtesting-funnel-handoff-2026-07-29.md).

Hoy existen **varias puertas etiquetadas**. No son el mismo producto:

| Camino | Qué es | Rigor | Estado |
|--------|--------|-------|--------|
| **A. Lab → checklist → deploy paper** | Tras BT/Optimizar / Finalistas Checklist, checklist pre-paper + `labEvidence` en la cuenta | Alto (OOS/WF/PBO visibles) | Hecho — deploy **manual** desde resultado (sin atajo Biblioteca) |
| **B. Tracker `paper_auto`** | Hit de rastreador → `ExecutionPolicy` + Gate hard | Gate sí; checklist lab opcional vía `requireValidatedBacktest` (default ON al crear) | Existe — etiquetado **«Paper automático (radar)»** |
| **C. Supervisado** | Propose → humano confirma | Medio | F3 / DecisionSession · **entrada Finalistas** (Proponer) + chart/scan · origen en cola |
| **Monitor (pre-D)** | Tablero de estado TOP/paper/Proponer por lista | N/A (solo lectura) | MVP en Ayuda Backtesting — **no ejecuta** |
| **D. Auto paper «completo»** | Monitor de estrategia adoptada + ejecución paper sin clic | Exige ranking TA+FA+perfil + monitor ejecutor | **Congelado** |
| **E. Live auto** | Órdenes reales | Production gate | Dry-run / fuera de alcance |

**Reglas de producto (congelar en cabeza del equipo):**

1. No llamar «listo para invertir» ni «auto de producción» al camino B.
2. **Decisión 2026-07-28:** no unificar A+B en un solo «auto». Mantener B etiquetado; D solo cuando existan monitor ejecutor + FA + perfil.
3. Orden de madurez: manual (A) → supervisado (C) → auto paper (D) → live (E). El Monitor MVP no salta a D.
4. IA **coordina y explica**; el Gate **autoriza**; el motor **ejecuta**. El LLM no salta el Gate.

**UI (2026-07-29):** copy en `paper-paths-copy.ts` (A/B/C/Monitor) · políticas default `requireValidatedBacktest` en paper_auto · Biblioteca sin botón Paper · Finalistas Checklist/Proponer · cola F3 con origen · Monitor en Ayuda.

Cuando se retome Fundamental + ranking por perfil + ejecución, esta tabla es el checklist de unificación — no inventar un tercer on-ramp de ejecución.

---

## Fase 2 — Evidence / Belief / Knowledge

Normativa: [ADR-018](../adr/018-fase2-evidence-store-v0.md) · contratos [ADR-016 §2.3](../adr/016-research-persistence-model.md) · niveles [ADR-012](../adr/012-scientific-validation-knowledge-evolution.md).

### Roadmap de slices

| ID | Entrega | Estado |
|----|---------|--------|
| **P2.A** | `hypotheses` stub + `research_evidence` + clasificador A–D + emit desde trial + API GET | hecho |
| **P2.B** | Hypothesis CRUD + falsifiers stub + link `research_trials.hypothesis_id` | hecho |
| **P2.C** | Belief Engine v0 (`hypothesis_beliefs` + update desde Evidence) | hecho |
| **P2.D** | Knowledge nodes v0 + Consolidation stub | hecho |
| **P2.E** | Research Tree mínimo | hecho |
| **P2.F** | Sync MKL stub (RFC-008) | hecho |

### P2.A — Evidence Store v0 (hecho 2026-07-27)

| Pieza | Comportamiento |
|-------|----------------|
| ADR | [018](../adr/018-fase2-evidence-store-v0.md) |
| Migración | `packages/database/prisma/migrations/20260727120000_research_evidence` |
| Tablas | `hypotheses` (stub), `research_evidence` (append-only) |
| Nivel | D sin experimento; C = IS/hold-out; B = WF/CPCV lab; A no automático |
| Emisión | Tras insertar `research_trials` (H0 + optimize) → 1 evidence |
| API | `GET /research/evidence`, `GET /research/evidence/{id}` |
| No es | Belief, Knowledge, gate de trading |

```bash
# Migración (entorno local/CI con DB):
pnpm --filter @bolsa/database exec prisma migrate deploy

# Pieza Evidence:
pnpm exec pytest packages/py/application/tests/test_research_evidence.py -q

# Hooks BT siguen en batería lab:
pnpm test:optimize
```

### P2.B — Hypothesis CRUD + falsifiers (hecho 2026-07-27)

| Pieza | Comportamiento |
|-------|----------------|
| API | `POST/GET/PATCH /research/hypotheses`, list con `status`/`kind` |
| Falsifiers | Obligatorios (≥1); stub `{id, description, kind, params?}` — kinds: `metric_threshold` \| `narrative` \| `regime_break` \| `other` |
| Link trial | `PATCH /research/trials/{id}/hypothesis` · filtro `?hypothesisId=` · `hypothesisId` en `POST /backtests/run` |
| Evidence | Hereda `hypothesis_id` del trial al emitir (P2.A) |
| No es | Belief updates, UI Observatory de hipótesis, auto-evaluación de falsifiers |

```bash
pnpm exec pytest packages/py/application/tests/test_hypotheses.py packages/py/application/tests/test_research_evidence.py -q
pnpm test:optimize
```

### P2.C — Belief Engine v0 (hecho 2026-07-27)

| Pieza | Comportamiento |
|-------|----------------|
| Tablas | `hypothesis_beliefs` (mutable 1:1 hyp) + `belief_history` (append-only) |
| Prior | Al crear hipótesis: belief=0.35, CI≈[0.15,0.55], n=0 |
| Update | Evidence con `hypothesis_id` → `belief ± α·w·sign` (`belief_lab_v0`); CI estrecha con n |
| Sign | Heurística lab: score/WFE, PBO≥0.5, edgeBand, failCode |
| α | C=0.08 · B=0.18 · A=0.28 · D=0 (n no sube en D) |
| API | `GET …/hypotheses/{id}/belief`, `GET …/belief/history` |
| Idempotencia | Mismo `evidence_id` no reaplica |
| No es | Consolidation/Knowledge, decay/pruning, UI, gate trading |

```bash
pnpm --filter @bolsa/database exec prisma migrate deploy
pnpm exec pytest packages/py/application/tests/test_belief_engine.py packages/py/application/tests/test_hypotheses.py packages/py/application/tests/test_research_evidence.py -q
pnpm test:optimize
```

### P2.D — Knowledge + Consolidation stub (hecho 2026-07-27)

| Pieza | Comportamiento |
|-------|----------------|
| Tabla | `knowledge_nodes` (estadios ADR-013: CANDIDATE→…→DEPRECATED) |
| Consolidation | **Explícita** `POST …/consolidate` — nunca automática |
| Gates | n≥3 · belief≥0.55 · CI width≤0.40 · Evidence ≥B · sin contexts_fail · landscape ack · sin nodo activo |
| Resultado | Nodo `EMERGING` + hyp `status=consolidated` (`consolidation_lab_v0`) |
| API | `GET …/consolidation` · `POST …/consolidate` · `GET /research/knowledge` · deprecate |
| No es | Auto-promote, Decay/Pruning, Landscape real, UI |

### P2.E — Research Tree mínimo (hecho 2026-07-27)

| Pieza | Comportamiento |
|-------|----------------|
| Tabla | `research_tree_edges` (soft-delete) |
| Tipos | SUPPORTS · CONTRADICTS · DEPENDS_ON · SPECIAL_CASE_OF · GENERALIZES · CORRELATED_WITH · HYPOTHESIZED_CAUSES |
| Prohibido | `CAUSES` (ADR-012 L1) |
| Auto | Tras Consolidation: evidence→hyp SUPPORTS + hyp→knowledge GENERALIZES |
| API | `GET/POST /research/tree/edges` · `DELETE …/{id}` (soft) |

### P2.F — MKL sync stub (hecho 2026-07-27)

| Pieza | Comportamiento |
|-------|----------------|
| Tabla | `mkl_sync_events` (append-only) |
| Fact | `ScientificKnowledgeFact` + notes `not_auto_live` |
| Sync | `POST /research/knowledge/{id}/sync-mkl` (dryRun / promoteToAccepted) |
| Promote | EMERGING → ACCEPTED al sync real (stub); no autoriza órdenes |
| API | sync + `GET …/mkl-sync` |

### Batería Fase 2 (obligatoria)

```bash
pnpm --filter @bolsa/database exec prisma migrate deploy
pnpm test:fase2
# API live:
FASE2_API_REQUIRED=1 pnpm test:fase2
```

Regla Cursor: `.cursor/rules/fase2-scientific-quality.mdc` · CI: workflow **Fase 2 scientific**.

**Fase 2 dominio (P2.A–P2.F) cerrada.** Siguientes ampliaciones (Decay/Pruning, Discovery, Planner, UI Observatory) fuera de este paquete.
