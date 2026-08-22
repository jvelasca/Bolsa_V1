# PLAN R-12 — Pending-delete V2 purge (2026-08-22)

> **Padre:** [`pending-delete/README.md`](./pending-delete/README.md) · inventario [`inventory-r12-2026-08-21.md`](./pending-delete/inventory-r12-2026-08-21.md) · plan R-12 [`plan-r12-auditoria-ux-2026-08-21.md`](./plan-r12-auditoria-ux-2026-08-21.md).
> **Tests protectores:** commit `851b545` — `use-pending-orders.migration.test.ts`, `workspace-legacy-timeframe-favorites.test.ts`.
> **Re-verificación E8:** 2026-08-22 · HEAD al verificar: `5011ba5`.
> **Resultado:** **0 purges ejecutados.** Ningún ítem de riesgo alto cumple E8 hoy.

---

## 0. Criterio E8 (recordatorio)

1. **0 imports** en `apps/` + `packages/` (salvo tests que solo validan el alias/migrador).
2. **Sin lectura/escritura de storage** que dependa del nombre legacy (localStorage key o campo de workspace).
3. **Batería verde** (typecheck + tests afectados) tras quitar.

---

## 1. Re-verificación por ítem (grep/code search 2026-08-22)

| Ítem                           | E8 hoy  | Evidencia                                                                                                                                                                                    | Acción              |
| ------------------------------ | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| `readLegacyPendingOrders`      | **N**   | Reader + migrador one-shot en `use-pending-orders.ts` L16–27, L42–68; `localStorage["bolsa-trading-ui"]` read + `removeItem`. 0 writers del array legacy; migrador es el único runtime path. | **NO PURGE**        |
| `chartDataStrip`               | **N**   | Reader en `workspace-store-core.ts` L748 (`raw.chartDataStrip ?? …` → merge toolbar). Tipo en `chart-defaults.ts` L270. 0 writers TS; persist genérico puede reexpedir campo en blobs.       | **NO PURGE**        |
| `chartNewTabSeed`              | **N**   | Tipo `@deprecated` en `chart-defaults.ts` L247; merge en `chart-list-snapshot.ts` L484. Campo opcional en workspace persistido.                                                              | **NO PURGE**        |
| `newChartConfigSource`         | **N**   | Tipo `@deprecated` en `chart-defaults.ts` L244. Sin writers TS; puede existir en blobs `preferences`.                                                                                        | **NO PURGE**        |
| `readLegacyTimeframeFavorites` | **N**   | Reader + `LEGACY_TIMEFRAME_FAVORITES_KEY` en `workspace-store-core.ts` L648–663, usado en `normalizeWorkspace` L746. `localStorage["bolsa-chart-timeframe-favorites"]`.                      | **NO PURGE**        |
| `presetRuleGroups`             | **N/A** | API viva: callers en `hybrid-strategy.ts`, `research-platform.ts`, `strategy-gate-series.ts`; re-export `strategy-rules.ts` / `types.ts`.                                                    | **NO es candidato** |

### Micro-candidatos (fuera de matriz riesgo alto)

| Ítem                       | E8 hoy | Evidencia                                                                                                                                                                                      | Acción                            |
| -------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `ChartInspectorTab` (tipo) | **N**  | Fichero `chart-inspector-nav.ts` **LIVE** — imports en `ui-store`, `workspace-slice-layout`, `chart-inspector-panel`, `chart-toolbar-chart-bar`, etc. Tipo sin usos externos ≠ fichero muerto. | **NO PURGE**                      |
| `normalizeChartNewTabSeed` | **N**  | **0 call sites** en `apps/` + `packages/`. Export en `chart-new-tab-setup.ts` L128. Inventario exige tests de contrato antes de borrar.                                                        | **NO PURGE** (sin contract tests) |

---

## 2. Qué falta antes de cada purge (V2)

### 2.1 `readLegacyPendingOrders` + efecto migrador

| Gate                        | Detalle                                                                                                                                                                                           |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Métrica**                 | Telemetría client-side (opt-in o sample): conteo de sesiones con `localStorage["bolsa-trading-ui"]` presente y `state.pendingOrders.length > 0`. Objetivo: **0 blobs activos** durante N semanas. |
| **Flag migración completa** | Feature flag o constante de build `PENDING_ORDERS_LEGACY_MIGRATION_COMPLETE` tras ventana de métrica; desactiva lectura sin borrar código hasta fase final.                                       |
| **Test de ausencia**        | Test que falle si `readLegacyPendingOrders` o `localStorage.getItem("bolsa-trading-ui")` reaparece tras purge; mantener `use-pending-orders.migration.test.ts` como regresión hasta el corte.     |
| **Timeline sugerido**       | T+0 métrica → T+4–8 semanas ventana → flag ON en staging → T+1 semana prod → purge código + tests de ausencia.                                                                                    |

### 2.2 `readLegacyTimeframeFavorites` + `LEGACY_TIMEFRAME_FAVORITES_KEY`

| Gate                 | Detalle                                                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Métrica**          | Conteo de `localStorage["bolsa-chart-timeframe-favorites"]` no vacío al primer `normalizeWorkspace`.                           |
| **Flag**             | `TIMEFRAME_FAVORITES_LEGACY_MIGRATION_COMPLETE` — skip lectura legacy en normalize.                                            |
| **Test de ausencia** | Fallo de CI si la clave o la función vuelven tras purge; conservar `workspace-legacy-timeframe-favorites.test.ts` hasta corte. |
| **Timeline**         | Paralelo a 2.1; puede unificarse en un solo “storage legacy purge” gate.                                                       |

### 2.3 Campos workspace (`chartDataStrip`, `chartNewTabSeed`, `newChartConfigSource`)

| Gate                 | Detalle                                                                                                                                                                    |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Métrica**          | Scan de workspaces persistidos (export JSON / telemetría anónima): % docs con cada campo presente. Objetivo **0 %** en ventana.                                            |
| **Flag**             | `WORKSPACE_LEGACY_FIELDS_STRIP_COMPLETE` — normalizer deja de leer/mergear campos deprecated.                                                                              |
| **Test de ausencia** | Tests de contrato en `normalizeWorkspace` + `mergeChartListDocuments` sin referencias a campos legacy; fixture de blob pre-migración conservado solo en tests hasta corte. |
| **Timeline**         | Tras 2.1/2.2 estables; requiere migración one-shot de blobs server-side o re-save client-side.                                                                             |

### 2.4 `normalizeChartNewTabSeed` (micro, bajo riesgo)

| Gate              | Detalle                                                                                 |
| ----------------- | --------------------------------------------------------------------------------------- |
| **Pre-requisito** | Añadir `chart-new-tab-setup.test.ts` con contract tests del helper **antes** de borrar. |
| **Métrica**       | N/A (0 call sites); solo verificar que ningún import dinámico exista.                   |
| **Timeline**      | Fase independiente post contract tests; no bloquea migradores storage.                  |

---

## 3. Purge ejecutado en esta pasada

**Ninguno.** Ámbito `apps/web` + `packages/shared` chart/workspace/trading: todos los ítems de la matriz fallan al menos el criterio E8.2 (storage/runtime readers).

---

## 4. Tests ejecutados (protectores, sin cambios de código)

```bash
pnpm --filter @bolsa/web exec vitest run \
  src/features/trading/use-pending-orders.migration.test.ts \
  src/stores/workspace-legacy-timeframe-favorites.test.ts
```

Resultado: **9/9 passed** (2 files, 1.57s).

---

## 5. Resultados de batería (2026-08-22)

| Suite                                          | Tests | Resultado   |
| ---------------------------------------------- | ----- | ----------- |
| `use-pending-orders.migration.test.ts`         | 4     | ✅ pass     |
| `workspace-legacy-timeframe-favorites.test.ts` | 5     | ✅ pass     |
| **Total**                                      | **9** | **✅ pass** |

---

## 6. Próximo paso (coordinador)

1. Aprobar instrumentación de métricas (§2.1–2.3) sin tocar migradores.
2. Tras ventana + flag, re-ejecutar subagente purge con este plan como checklist.
3. **Prohibido:** wipe `localStorage`, quitar migradores, o borrar `chart-inspector-nav.ts` / `presetRuleGroups` sin E8 completo.
