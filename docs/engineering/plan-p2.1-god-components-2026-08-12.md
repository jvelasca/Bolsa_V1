# Plan — P2.1 God-components (workspace-store + backtests-page) · 2026-08-12

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de
> Auditoría consolidada, tras F5c).
> **Fuentes de verdad:** [traspaso-f5c-frontend-cleanup-2026-08-12.md](./traspaso-f5c-frontend-cleanup-2026-08-12.md)
> (§5 deuda P2.1) · [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md)
> (fila P2.1) · protocolo 3 fases M5.
> **Rama de ejecución:** `stage/p2.1-god-components-2026-08-12` (desde base `bce6066` = tip F5c).
> **Regla del hilo:** NO tocar código fuera del alcance P2.1. Batería (typecheck+lint+test) por paso.
> **Estado:** COMPLETADO 2026-08-12 (workspace-store 3982→89 líneas + backtests-page 5129→4509;
> batería verde: typecheck, lint, test 714 web + 10 shared, build). Cierre + traspaso en §8.

---

## 0. Alcance pactado (decisión del usuario, este hilo)

El usuario eligió **"montar el plan de ambos, ejecutar por slices con batería por paso"** (FASE 1/2 ya
levantada, ver §3). Objetivo P2.1 = **D5 cero features**: reducir la "god-ness" de los dos ficheros.

1. **`workspace-store.ts`** (3982 líneas) — un solo store Zustand monolítico `create`+`persist`.
2. **`backtests-page.tsx`** (5129 líneas) — un solo componente orquestador `BacktestsPage`.

---

## 1. Hechos de diagnóstico FASE 1 (confirmados en código)

### 1.1 `workspace-store.ts` — acoplamiento REAL (corrige el mapa previo)

- **Un solo documento persistido** `workspace.document`: `create` en L1203, `persist` en L1204
  (key `bolsa-workspace-meta`), interfaz `WorkspaceState` L884–1175, state inicial L1206–1213,
  config persist L3957–3973 (`partialize` → solo `activeWorkspaceId`/`recents`/`chartPersistBackup`,
  `merge` custom L3964–3972).
- **~129 acciones** repartidas en 11 dominios. **CRÍTICO:** la práctica totalidad de setters mutan el
  **mismo objeto `state.workspace`** (una sola `WorkspaceDocument`) y muchos llaman a la **misma
  función transversal** `scheduleWorkspaceServerSave(get)` (autosave/backup).
- **Acoplamiento externo mínimo:** solo `getWorkspaceUiBridge()` (import `workspace-ui-bridge.ts`,
  usado para drawing-editor y inspector nav). **No hay** lecturas cruzadas de otros stores.
- **Revelación de diseño (importante):** por esto, **el slicing "a N stores paralelos" NO es seguro**:
  rompería el contrato de un documento persistido único (todos los slices escribirían el mismo
  `workspace` y habría doble persist/merge sobre la misma key). El patrón correcto y verificado por
  Zustand es **componer slices dentro de UN solo `create`+`persist`** (mismo contrato, mismo persist,
  cero riesgo de consumidor/rendimiento).

### 1.2 `backtests-page.tsx` — acoplamiento REAL

- `export function BacktestsPage()` L303, JSX L3790–5128. **Sin props**; estado 100% local
  (`~70 useState`, `15 useRef`) inyectado a los **~30 subpaneles por props** (verificado: ningún
  subpanel importa hooks del orquestador; no hay contexto compartido).
- **NO consume `useWorkspaceStore`** (verificado en imports L1–289). Stores que sí:
  `useActiveAccount`, `useDiaDTradingSessionStore`, `useAlertsStore`, `useSupervisedF3QueueStore`,
  `useListAutoActivityStore`.
- **4 bloques objetivo** con rangos reales:
  - `runListBatch` L1243–1307 (batería Ranking; aislado, único caller JSX).
  - `runCoachBattery` L1437–1609 (batería Coach; devuelve `{okCount,error}`; multi-caller).
  - `startOptimizeFromExplore` L1939–1957 (abre optimización guiada; **el más desacoplado**).
  - `settleFullCycle` L2764–2966 (settle Lista AUTO; **acumulador transversal**, 11 call sites).
- **Acoplamiento entre bloques:** `runCoachBattery`↔`settleFullCycle` comparten `coachPass`,
  `coachGate`, `fullCycleActive`, `assistantProgressRef`, `resultFocus`, `listAutoRef`,
  `assistantStatus` (secuencia de ciclo). `runListBatch`↔`runCoachBattery` se abortan mutuamente
  vía `batchAbortRef`/`exploreAbortRef`. `startOptimizeFromExplore` es casi puro passthrough.
- **Cadena real de orquestación:** `playAssistantSequence` → `chooseAssistantStep` →
  `executeAssistantStep` → `runExploreValue` → `runCoachBattery`; Lista AUTO vía `queueListAutoTicker`
  → `settleFullCycle` → (bucle ticker).

---

## 2. Decisiones de diseño (P2.1)

### 2.1 `workspace-store.ts` — composición de slices (NO stores paralelos)

Refactor **estructural que conserva el contrato**: el store público `useWorkspaceStore` sigue siendo
`create<WorkspaceState>()(persist(...))` DE UNA sola pieza, pero sus ~129 acciones se **diseccionan en
ficheros slice** que cada uno exporta un definidor tipado de acciones, compuesto en el store final.

- **Slice mechanism (transversal):** persist + autosave/backup + `chartPersistBackup` +
  `scheduleWorkspaceServerSave` → un slice `workspace-persistence-slice.ts`.
- **Slices de dominio** (cada uno solo muta `workspace` + marca `isDirty`/aislado):
  - `workspace-layout-slice.ts` (listPanel/rightPanel/inspector/dock/sub-panels).
  - `workspace-chart-slice.ts` (tabs, activeChartId, chartConfig, timeframes, series, toolbar).
  - `workspace-list-slice.ts` (list, listColumns, membership, chartListContext).
  - `workspace-indicators-slice.ts` (instances, presets, templates, favorites).
  - `workspace-drawings-slice.ts` (drawings, templates, drawTool favorites, style memory).
  - `workspace-crud-slice.ts` (switch/create/duplicate/rename/delete, saveToServer, bootstrap,
    remote-sync) — orquesta el documento + summaries.
- **Tipado:** cada slice define su porción de `WorkspaceState`; el store compone con
  `...layoutSlice(set,get)`, etc. Tipos `WorkspaceState` e interfaces de documento se mantienen
  centralizados (no se toca el shape; cero cambio de contrato con los ~48 consumidores).
- **Consumidores (~48):** cambios **cero** — el export `useWorkspaceStore` y todas las firmas de
  acciones quedan idénticas. Solo cambia la organización interna del fichero.

> Ejecución por pasos atómicos (uno por slice) con batería entre commits, no un mega-commit.

### 2.2 `backtests-page.tsx` — extracción de los 4 bloques a capa de orquestación

Los 4 bloques cierran sobre decenas de setters/refs → **no react-islands** (M5 Diseño B agotado, nota de
cierre). Patrón elegido: extraer la **lógica** de los bloques a **módulos puros/hook** bajo
`features/backtests/` que reciben un **contexto tipado** (`BacktestRunCtx`) con los setters/refs que
necesitan, y que `BacktestsPage` cablea.

- **Paso 1 (fácil, aislado):** `startOptimizeFromExplore` → `lib/start-optimize-from-explore.ts`
  (solo lee 4 piezas + navegación). Máxima ROI/línea menor.
- **Paso 2:** `runListBatch` → `lib/run-list-batch.ts` (input: aborts + setters batch).
- **Paso 3:** `runCoachBattery` → `lib/run-coach-battery.ts` (input: el montón de estado Coach).
- **Paso 4 (mayor riesgo):** `settleFullCycle` → `lib/settle-full-cycle.ts` (acumulador; input: el
  puerto común `coachPass/resultFocus/fullCycleActive/assistant*/listAuto*` compartido con el paso 3).
  Este paso declara un **puerto de avance de ciclo** común para paso 3+4.

El estado sigue viviendo en `BacktestsPage`; los módulos son **funciones puras de orquestación** que
reciben el contexto y devuelven el siguiente estado/cambios. Reduce la "orquestación" dentro del
componente a cableado de llamadas, dejando `backtests-page.tsx` por debajo del umbral de god-component.

---

## 3. Estado del mapa (FASE 1/2 completada)

- `workspace-store`: **mapa completo** (129 acciones/11 dominios/6 clusters/1 slice transversal;
  persist + singleton contract confirmado → composición de slices, NO stores paralelos). Fuente:
  análisis anclado a líneas de este hilo.
- `backtests-page`: **mapa completo** de los 4 bloques + inventario ~70 useState/15 useRef + grafo de
  acoplamiento + 2º store (ver §1.2). 30 subpaneles ya extraídos (M5); el orquestador solo queda con
  lógica/estado.

---

## 4. Validadción / batería por paso

Cada commit de esta fase debe pasar (en `apps/web`), como en F5c:

- `pnpm --filter @bolsa/web typecheck` → exit 0.
- `pnpm --filter @bolsa/web lint` → 0 errores.
- `pnpm --filter @bolsa/web test` → 714 passed (141 f) — sin regresiones.
- Batería base registrada en `bce6066` (F5c): web typecheck✓ lint✓ test 714✓ · shared 10✓.

---

## 5. Fuera de alcance

- No se toca el shape de `WorkspaceState` ni los DTOs (fase F5a §6 fidelidad).
- No se tocan los **8 `as unknown as`** (bridges intencionales → F5a §6).
- No se toca duplicación TS↔Py restante (P2.6 residue → fase con acuerdo de diseño).
- No se abren N stores paralelos: P2.1 conserva el singleton document/autosave.
- M7 code-splitting / Vite F3.7 (dev-stack), ajeno.

---

## 6. Registro

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                  |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Rama `stage/p2.1-god-components-2026-08-12` desde base `bce6066` (tip F5c).                                                                                                                                                                                                                                             |
| 2026-08-12 | FASE 1+2: mapa completo de `workspace-store` y `backtests-page` + decision de diseno (slices compuestos / bloques a lib) + este plan.                                                                                                                                                                                   |
| 2026-08-12 | **Decisión usuario:** aprobado "compose-slices dentro de UN solo create+persist" (§2.1). Ejecución por slices con batería por paso.                                                                                                                                                                                     |
| 2026-08-12 | **workspace-store COMPLETO** (commit `18a8878`): `workspace-store.ts` 3982→89 líneas de composición; `workspace-store-core.ts` (helpers+interfaz+tipos) + 7 slices `workspace-slice-{layout,charts,indicators,drawings,toolbar,list,account}.ts`. Persist `bolsa-workspace-meta` byte-idéntico. Cero cambios de lógica. |
| 2026-08-12 | **backtests-page COMPLETO** (commit `0fcdc8b`): `backtests-page.tsx` 5129→4509 líneas; `lib/backtest-orchestration.ts` (729 líneas) `createBacktestOrchestration(ctx)` con contexto tipado devuelve `runListBatch/runCoachBattery/startOptimizeFromExplore/settleFullCycle`. Cero cambios de lógica.                    |
| 2026-08-12 | **Batería final P2.1**: web typecheck ✓, lint 0 errores (2 warnings pre-existentes en un effect no tocado), test **714 passed (141 f)**, build ✓; shared **10 passed**.                                                                                                                                                 |

---

## 7. Cierre — resultado alcanzado

P2.1 **COMPLETADO** con cero cambios de comportamiento (D5). Dos god-components descompuestos sin tocar
su lógica:

| Componente                                           | Antes                               | Después                                                                                | Mecánica                                                                                                                                                                                                                                                                |
| ---------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/web/src/stores/workspace-store.ts`             | 3982 líneas, ~100 acciones, 1 store | 89 líneas de composición + `workspace-store-core.ts` + 7 slices `workspace-slice-*.ts` | compose-slices dentro de **UN solo** `create<WorkspaceState>()(persist(...))`; persist `bolsa-workspace-meta` con `partialize`/`merge` byte-idéntico                                                                                                                    |
| `apps/web/src/features/backtests/backtests-page.tsx` | 5129 líneas                         | 4509 líneas                                                                            | Extracción de `runListBatch/runCoachBattery/startOptimizeFromExplore/settleFullCycle` → `lib/backtest-orchestration.ts` (729 líneas) `createBacktestOrchestration(ctx)` con contexto tipado `BacktestOrchestrationCtx`; re-instanciación en render (sin stale closures) |

**Batería final (verde):** web typecheck 0 · lint 0 errores · test **714 passed (141 f)** · build 0 ·
shared test **10 passed**. Commits: `18a8878` (workspace-store) · `0fcdc8b` (backtests-page).

## 8. Traspaso al próximo hilo

### Residuo P2.1 sin tocar (deuda diferida — mismo inventario que trajo F5c)

- **8 `as unknown as`**: bridges tipados intencionales a `Record<string, unknown>` para
  serialización. Sustituir por DTOs → fase fidelidad contratos (**F5a §6**).
- **Duplicación TS↔Py restante**: `ai-indicator-series` ↔ `technical_rating`/`data_quality`;
  `execution-policies`/`position-policies`/`tracker-definitions`/`tax-report` ↔ py. Exige acuerdo de
  diseño de fuente de verdad, no tocado (P2.6 residue).
- **Deuda previa sin resolver**: P1.9 API thin (hilo propio), P1.3 auth full (D4 diferido),
  F5a §6 fidelidad DTOs/openapi-fetch, mypy preexistente por fases.

### Texto de traspaso (pegable en el próximo chat)

> CONTEXTO INMEDIATO: P2.1 god-components **COMPLETADO** en rama
> `stage/p2.1-god-components-2026-08-12` (desde `stage/f5c-frontend-cleanup-2026-08-12`, base `bce6066`).
>
> - **workspace-store** 3982→89 líneas: `workspace-store-core.ts` + 7 slices `workspace-slice-*.ts`
>   compuestos en **UN solo** `create+persist` (`bolsa-workspace-meta`, partialize/merge byte-idénticos).
> - **backtests-page** 5129→4509 líneas: orquestación extraída a `lib/backtest-orchestration.ts`
>   `createBacktestOrchestration(ctx)` (`runListBatch/runCoachBattery/startOptimizeFromExplore/settleFullCycle`).
> - BATERÍA (verde): web typecheck 0 ✓ lint 0 errores ✓ test **714✓ (141 f)** ✓ build ✓ · shared **10✓**.
> - COMMITS: `18a8878` (workspace-store) · `0fcdc8b` (backtests-page).
> - RAMA: `stage/p2.1-god-components-2026-08-12`, pushada, tree limpio.
>
> DEUDA REGISTRADA → fases posteriores:
>
> - **P2.8 residue "as unknown as" (8)**: bridges tipados a `Record<string, unknown>` → F5a §6 DTOs.
> - **P2.6 residue**: duplicación TS↔Py restante (ai-indicator-series ↔ technical_rating/data_quality;
>   execution-policies/position-policies/tracker-definitions/tax-report ↔ py) → requiere acuerdo de fuente de verdad.
> - **Deuda previa**: P1.9 API thin (hilo propio), P1.3 auth full (D4), F5a §6 fidelidad DTOs, mypy.
>
> Lee PRIMERO: `docs/engineering/plan-p2.1-god-components-2026-08-12.md` (§7-§8 cierre) y sus fuentes
> (`traspaso-f5c-frontend-cleanup-2026-08-12.md` §4-§7, `audit-consolidado-internas-externas-2026-08-11.md`).
> NO toques código fuera del alcance de la fase que se declare.
