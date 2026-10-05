# Entrega a auditoría externa (MIA) — `v2.88.52-beta` · AUTO · UI: **AUTO UI REFACTOR 1.0** (modelo semántico implementado)

> **Fecha:** 2026-10-05 · **Producto:** V2.88.52-beta · **Package:** `2.11.52-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.51-beta` (tag → `fa487409`, `Release tag CI` `37305844986` **VERDE**).
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`/**`"UNKNOWN"`**, **nunca** `0`.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve (`contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.52/README.md`](./evidence/v2.88.52/README.md) (`§0`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.51`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** El auditor externo pidió **implementar** el `AUTO UI SEMANTIC MODEL 1.0` que `v2.88.51` **congeló por escrito**, para poder comparar `2.88.51 → 2.88.52`. Este sello **implementa el modelo en el view-model y la UI**; **NO** re-corre el pipeline `DÍA-D` (A/C cerrada en `v2.88.50`) y **NO** reestructura la navegación global.

---

## 1. Qué se entrega (y qué NO)

**Se entregan** cuatro bloques de UI/read-model, todos **sin tocar el motor**:

1. **View-model semántico** (`@bolsa/shared`, `buildAutoOperationStory`): 14 etapas con `kind` (`FACT`/`DERIVED`/`CONTEXT`/`EXPLANATION`) y `group` (`OPERATION`/`CONTEXT`); **`SELECTION` (TOP-N) ≠ `DECISION`** (`NOT_MEASURED`, sin traza durable de decisión de cartera); **`EXIT` (DERIVED) ≠ `SETTLEMENT` (FACT)**; **`OPPORTUNITY`** movida al bloque `context` (PIT/régimen/ranking `NO MEDIDO`); hechos **crudos** (formateo en la UI).
2. **`MeasurementValue`/`MeasurementBadge`** unificados: representación única valor + medición sobre `@bolsa/shared`; un hueco se rotula `NO MEDIDO`/`PARCIAL`, nunca una cifra sin medición. Refactor de los 4 paneles AUTO.
3. **Operación por defecto + selección en URL**: `mode` (por defecto `operation`), `cycle`, `day`, `window`, `symbol` viven en la query; `enabled: mode !== "dia-d"`.
4. **Enlace EXPLICACIÓN → DÍA-D**: «Ver heatmap de {symbol}» con símbolo/ventana preseleccionados.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se reestructura la navegación global (`OPERAR · CARTERA · RIESGO · ANÁLISIS · SISTEMA`: objetivo post-1.0 del spec).
- **NO** se borra ninguna pantalla (refactor **aditivo**); **NO** se inventan estados `STALE`/`BLOCKED` (el DTO de ciclo no los produce).
- **NO** se nombra la causa de los `23 orden_creada_sin_fill` (futura **Execution Analysis**); **NO** se emite `CONFIRMED`.

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1`. Este sello **no** re-ejecuta nada.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| View-model semántico | `packages/shared/src/cognitive/auto-operation-story.ts` | 14 etapas con `kind`/`group`; `SELECTION` ← `TOP_N`; `DECISION` `NOT_MEASURED` (`sourceStepId: null`); `EXIT` `DERIVED` de `SETTLEMENT`; bloque `context`; hechos crudos. |
| Componente de medición | `apps/web/src/components/measurement-value.tsx` | `MeasurementValue` (valor + medición; `incomplete="annotate"|"withhold"`) y `MeasurementBadge`; formateo delegado en `@bolsa/shared`. |
| Refactor de paneles | `auto-cycle-timeline.tsx`, `auto-reservation-panel.tsx`, `auto-concurrency-panel.tsx`, `auto-operation-story-panel.tsx` | Consumen `MeasurementValue`; el PnL usa `withhold` ⇒ bug del PnL de `v2.88.50` imposible por accidente. |
| URL | `auto-monitor-page.tsx`, `dia-d-auto-panel.tsx`, `dia-d-auto-feedback-panel.tsx` | `readAutoMonitorMode` (default `operation`); `useSearchParams` para `mode`/`cycle`/`day`/`window`/`symbol`. |
| Enlace DÍA-D | `auto-operation-story-panel.tsx` | Botón en `EXPLANATION` → `?mode=dia-d&view=feedback&window=<latest>&symbol=<symbol>`. |
| Tests | `@bolsa/shared` + `@bolsa/web` | Story-model `10`; `measurement-value` `8`; story panel `4`; page `6`; día-d/ventana/símbolo; suite web **1385 passed**. |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.52-beta`) en `v2_89`…`v2_97`. |

> **Nota de método.** El único rojo de la sesión fue un import/hook **sin usar** detectado por `tsc`/`eslint` (`navigate`); se eliminó el hook sobrante. **Ninguna** aserción se relajó.

---

## 3. Medición (cifras heredadas de `v2.88.50`, NO re-medidas)

Sin cambio de motor **ni de muestra**, este sello no re-corre el pipeline. Se **citan** (no se reutilizan como nuevas) las cifras vigentes de [`v2.88.50`](./evidence/v2.88.50/README.md):

| Métrica (`v2.88.50`) | Valor |
| --- | --- |
| `route` (A/C, `dia-d-thesis-exit-v5` capa v7) | `{materializado: 19, orden_creada_sin_fill: 23}` ⇒ **A = `0`**, **C = `23`** |
| `stopEvaluatedOnTouch` / `deciderRanOnTouch` | **`42/42`** / **`42/42`** |
| `candidate` (`structuralStopCandidate`) | **`42/42`** |
| `THESIS_EXIT` (n) | **`42`** |
| Expectancy bruta global | `-0.7150` |
| Banda global de R | `[-17.290, +19.328]`, `crossesZeroR = true`, **`pointCitable = false`** |

**Por qué no se re-mide:** la investigación A/C quedó **cerrada** en `v2.88.50` (`A = 0`); este sello es de UI/read-model y no toca ninguna costura.

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
| --- | --- |
| `pytest packages/py/application/tests/test_auto_operational_monitor.py apps/api-python/tests/test_dia_d_bump_guard.py` | **53 passed** |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (`659` ficheros) |
| `mypy` (gate CI, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| Web `vitest` (suite completa) | **1385 passed** (`241` ficheros) |
| Web `vitest` (auto-monitor + `measurement-value`) | **40 passed** (`8` ficheros) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`24` warnings pre-existentes) · **OK** |
| `@bolsa/shared` vitest / build | **808 passed** (+1 todo) · limpio |
| **`Δ motor = 0` (árbol)** | `git diff` de motor **vacío**; sólo view-model puro (`@bolsa/shared`) + UI + docs |
| **`Δ motor = 0` (CI)** | `Release tag CI` del tag `v2.88.52-beta` — **cita POST-TAG** (ver §6/§7) |

---

## 5. Límites declarados (no se cierran aquí)

1. El refactor es de **view-model/UI**, no de motor: `Δ AUTO decision/execution motor = 0`.
2. **La navegación global no se reestructura** (`OPERAR · CARTERA · RIESGO · ANÁLISIS · SISTEMA`): objetivo post-1.0, documentado en el spec.
3. **No se introducen** `STALE`/`BLOCKED`: el DTO de ciclo no los produce hoy; no se inventan.
4. **PIT histórico institucional** (listings/delistings/sector) sigue **abierto** (`P3` científico).
5. **REPLAY/OOS ≠ PAPER:** `P3-2`/`P3-3` **ABIERTAS**; `CONFIRMED` **NO** se emite.
6. **`n` pequeño** y banda global que cruza cero (heredado, sin cambios): nada es citable como punto.
7. `DECISION` queda `NOT_MEASURED` **a propósito**: no hay traza durable de decisión de cartera por ciclo; se declara en vez de igualarla a `TOP_N`.

---

## 6. Sello

- **Producto:** `V2.88.52-beta`. **Package:** `2.11.52-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Ficheros añadidos:** `apps/web/src/components/measurement-value.tsx`, `apps/web/src/components/measurement-value.test.tsx`, `docs/engineering/evidence/v2.88.52/README.md`, esta entrega.
- **Ficheros modificados:** `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), los `4` paneles AUTO + `auto-monitor-page.tsx` + `dia-d-auto-panel.tsx` + `dia-d-auto-feedback-panel.tsx` (+ tests), `package.json` (`2.11.52-beta`), `v2_89`…`v2_97` (`meta.bump`), `scripts/lib/window-forward.mjs` (re-anclaje del freeze), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.

### 6.1 Cadena de commits y SHAs (auditable)

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | _(hash del commit funcional)_ | `apps` `…` / `packages` `…` |
| Re-anclaje del freeze de la ventana (`chore`) | _(hash del chore)_ | pin `commit: <funcional>` (no mueve árbol) |
| **Commit del tag** | _(hash del tag)_ | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(hash POST-TAG)_ | — |

- **Tag:** `v2.88.52-beta` (**anotado**) → **PENDIENTE** de crear/empujar; la cita del `Release tag CI` y del `GitHub Release` se añade aquí en el commit **POST-TAG** de `main`.

---

## 7. Guion de auditoría desde GitHub (paso a paso)

Todo lo anterior se verifica **sin clonar el repo**:

1. **Objeto inmutable.** Abrir el tag: `https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.52-beta` (o `…/tree/v2.88.52-beta`). El commit del tag debe ser el del **sello funcional** (§6.1).
2. **Evidencia cruda dentro del tag.** Leer `docs/engineering/evidence/v2.88.52/README.md`: las **8** afirmaciones falsables con su forma de romperse, la tabla de gates y el detalle del refactor.
3. **Cita del CI (fuera del tag, por diseño).** En el **`Release`**: `Release tag CI` del tag `v2.88.52-beta` **VERDE** con `replay-repro` ⇒ `Δ motor = 0` (cita larga en la evidencia **`§7`**, escrita en `main` POST-TAG). *(Dentro del tag, la evidencia declara la cita como `POST-TAG`: límite estructural, no hueco.)*
4. **El modelo, verificado contra el código.** En el árbol del tag, `auto-operation-story.ts` debe exponer `SELECTION` con `sourceStepId: "TOP_N"` y `DECISION` con `sourceStepId: null`; `EXIT` con `kind: "DERIVED"` y `sourceStepId: "SETTLEMENT"`; `OPPORTUNITY` en `group: "CONTEXT"` y un bloque `context` con PIT/régimen/ranking `NO MEDIDO`.
5. **La doctrina del hueco.** En `measurement-value.tsx`, un valor sin muestra y `measurement: "COMPLETE"` debe **degradar** a `NO MEDIDO` (vía `formatMonitorFactValue`); con `incomplete="withhold"` una cifra no afirmable se retiene. Revertir esa degradación debe **romper** `measurement-value.test.tsx`.
6. **La selección en URL.** Abrir `/auto-monitor` sin query ⇒ pestaña **Operación** activa; `/auto-monitor?mode=current` ⇒ ventana cruda; `?mode=dia-d&view=feedback&window=…&symbol=BBB` ⇒ feedback con `BBB` resaltado.
7. **El enlace EXPLICACIÓN → DÍA-D.** Con un artefacto de feedback disponible, la etapa `EXPLANATION` muestra «Ver heatmap de {symbol}» y navega a `?mode=dia-d&view=feedback&window=<latest>&symbol=<symbol>`.
8. **`Δ motor = 0` sin re-ejecutar.** En el run del tag, el job `replay-repro` debe imprimir el mismo `sha256` del sello congelado; si coincide, el motor no se movió.
9. **Qué NO creer.** Que este sello re-mida algo (§3: cifras heredadas). Que se haya reestructurado la navegación global (§5.2). Que se borre alguna pantalla (refactor aditivo). Que `DECISION` sea un hueco por bug (§5.7: es una decisión declarada).
