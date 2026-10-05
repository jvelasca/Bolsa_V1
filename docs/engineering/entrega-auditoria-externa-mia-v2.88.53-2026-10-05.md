# Entrega a auditoría externa (MIA) — `v2.88.53-beta` · AUTO · UI: **AUTO UI REFACTOR 1.1** (operación única consolidada)

> **Fecha:** 2026-10-05 · **Producto:** V2.88.53-beta · **Package:** `2.11.53-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.52-beta` (tag → `2fccbf53`, `Release tag CI` `37319677455` **VERDE**).
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`/**`"UNKNOWN"`**, **nunca** `0`.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve (`contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.53/README.md`](./evidence/v2.88.53/README.md) (`§0`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.52`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** La auditoría de `v2.88.52` aprobó sin bloquear y dejó tres `P3`: `UI52-01` (EXIT duplicaba `REACHED` con SETTLEMENT), `UI52-02` (sin traza durable de decisión de cartera) y `UI52-03` (explicación esencialmente por símbolo). Este sello cierra **`UI52-01` y `UI52-03` en frontend/shared** y consolida la operación única; **NO** toca el motor, **NO** cambia el contrato HTTP y **NO** implementa `PortfolioDecision`.

---

## 1. Qué se entrega (y qué NO)

**Se entregan** tres bloques de UI/read-model, todos **sin tocar el motor**:

1. **`EXIT` plegado en `SETTLEMENT`** (`UI52-01`): `EXIT.foldedInto = "SETTLEMENT"` mientras no exista traza durable propia de salida. La UI pinta **una sola fila `REACHED`** por el hecho financiero; la intención de salida queda como **nota** de la liquidación. Con traza propia de `EXIT`, vuelve a ser fila independiente.
2. **Identidad de la explicación** (`UI52-03`): `AutoOperationStoryExplanationIdentity` (`cycleId` · `instrument` · `strategyVersion` · `direction` · `entryDay`) expuesta como hechos; `timeframe`/`régimen` declarados `NO MEDIDO` (el artefacto DÍA-D no los materializa). Resolución por instrumento mantenida; migrar el contrato a `cycleId` + ejes es deuda declarada.
3. **Operación única consolidada**: se quita el doble montaje de reservas/concurrencia en `operation`; botón «Detalle técnico (ventana actual)» → `mode=current`. Nomenclatura fijada: **14 conceptos del modelo**.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se implementa **`PortfolioDecision`** (`UI52-02`: traza durable de decisión de cartera) — es de spine/backend.
- **NO** se diseña la **navegación global** (`UI52-04`: `OPERAR · CARTERA · RIESGO · ANÁLISIS · SISTEMA`) — objetivo post-1.0 del spec.
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se borra ninguna pantalla (refactor **aditivo**); **NO** se inventan estados `STALE`/`BLOCKED`.
- **NO** se emite `CONFIRMED`.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| Plegado EXIT | `packages/shared/src/cognitive/auto-operation-story.ts` | `foldedInto` en la etapa; `EXIT.foldedInto = "SETTLEMENT"` (falsable: `null` si hay paso durable `EXIT`); no copia los `facts` de la liquidación; su nota se agrega a `SETTLEMENT`. |
| Identidad de la explicación | `packages/shared/src/cognitive/auto-operation-story.ts` | `AutoOperationStoryExplanationIdentity` + hechos de identidad (`cycleId`/estrategia/`entryDay`…) con `NO MEDIDO` en los ejes no materiales. |
| Operación única | `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` | Filtra `foldedInto === null` (12 filas); identidad desde el ciclo; sin doble montaje de reservas/concurrencia; botón «Detalle técnico (ventana actual)» → `mode=current`. |
| Tests | `@bolsa/shared` + `@bolsa/web` | Story-model (`12`); story panel (`5`, incl. plegado EXIT, identidad y detalle técnico); page (`6`); suite web **1386 passed**. |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.53-beta`) en `v2_89`…`v2_97`. |

> **Nota de método.** El único rojo de la sesión fue de **tipos** (un ternario `ownExit ? null : "SETTLEMENT"` ensanchado a `string`): se anotó la constante. **Ninguna** aserción se relajó.

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
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`2.11.53-beta`) |
| Web `vitest` (suite completa) | **1386 passed** (`241` ficheros) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`23` warnings pre-existentes) · **OK** |
| `@bolsa/shared` vitest / build | **810 passed** (+1 todo) · limpio |
| **`Δ motor = 0` (árbol)** | `git diff` de motor **vacío**; sólo view-model puro (`@bolsa/shared`) + UI + docs |
| **`Δ motor = 0` (CI)** | `Release tag CI` del tag `v2.88.53-beta` — **cita POST-TAG** (ver §6/§7) |

---

## 5. Límites declarados (no se cierran aquí)

1. El refactor es de **view-model/UI**, no de motor: `Δ AUTO decision/execution motor = 0`.
2. **`UI52-02`** (`PortfolioDecision`, traza durable de decisión de cartera) sigue **abierta**: spine/backend + contrato.
3. **`UI52-04`** (navegación global) sigue **abierta**: objetivo post-1.0 del spec.
4. La identidad de la explicación se **formaliza** en la UI; migrar el artefacto DÍA-D a `cycleId` + ejes es deuda de contrato (no en 1.1).
5. **No se introducen** `STALE`/`BLOCKED`: el DTO de ciclo no los produce hoy.
6. **PIT histórico institucional** (listings/delistings/sector) sigue **abierto** (`P3` científico).
7. **REPLAY/OOS ≠ PAPER:** `P3-2`/`P3-3` **ABIERTAS**; `CONFIRMED` **NO** se emite.
8. **`n` pequeño** y banda global que cruza cero (heredado, sin cambios): nada es citable como punto.

---

## 6. Sello

- **Producto:** `V2.88.53-beta`. **Package:** `2.11.53-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Ficheros añadidos:** `docs/engineering/evidence/v2.88.53/README.md`, esta entrega.
- **Ficheros modificados:** `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` (+ test), `docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md`, `package.json` (`2.11.53-beta`), `v2_89`…`v2_97` (`meta.bump`), `scripts/lib/window-forward.mjs` (re-anclaje del freeze), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.

### 6.1 Cadena de commits y SHAs (auditable)

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `2b7f1940` | `apps` `9fcd4452…` / `packages` `371105fc…` |
| Re-anclaje del freeze de la ventana (`chore`) | `b41ec173` | pin `commit: 2b7f1940` (no mueve árbol) |
| **Commit del tag** | _(pendiente de crear el tag)_ | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(posterior)_ | — |

- **Tag:** `v2.88.53-beta` (**anotado**) — **pendiente** de creación/empuje; `Release tag CI` **PENDIENTE** (cita POST-TAG). `GitHub Release` **pendiente**.

---

## 7. Guion de auditoría desde GitHub (paso a paso)

Todo lo anterior se verifica **sin clonar el repo**:

1. **Objeto inmutable.** Abrir el tag `v2.88.53-beta` (o `…/tree/v2.88.53-beta`). El commit del tag debe ser el del **sello funcional** (§6.1).
2. **Evidencia cruda dentro del tag.** Leer `docs/engineering/evidence/v2.88.53/README.md`: las **7** afirmaciones falsables con su forma de romperse, la tabla de gates y el detalle del refactor.
3. **Plegado de EXIT.** En el árbol del tag, `auto-operation-story.ts` debe declarar `foldedInto: "SETTLEMENT"` en `EXIT` y calcularlo como `ownExit ? null : "SETTLEMENT"`; el panel debe filtrar `foldedInto === null`.
4. **Identidad de la explicación.** `buildExplanationStage` debe exponer `cycleId`/`estrategia`/`día entrada` y declarar `timeframe`/`régimen` `NO MEDIDO`; el panel debe construir la identidad desde el ciclo.
5. **Sin duplicación.** En `auto-operation-story-panel.tsx` no debe aparecer `AutoReservationPanel`/`AutoConcurrencyPanel`; el botón «Detalle técnico (ventana actual)» debe fijar `mode=current`.
6. **La doctrina del hueco.** Un valor sin muestra con `measurement: "COMPLETE"` **degrada** a `NO MEDIDO` (vía `formatMonitorFactValue`).
7. **`Δ motor = 0` sin re-ejecutar.** En el run del tag, el job `replay-repro` debe imprimir el mismo `sha256` del sello congelado; si coincide, el motor no se movió.
8. **Qué NO creer.** Que este sello re-mida algo (§3: cifras heredadas). Que implemente `PortfolioDecision` (§5.2). Que reestructure la navegación global (§5.3). Que `DECISION` sea un hueco por bug (es una decisión declarada).
