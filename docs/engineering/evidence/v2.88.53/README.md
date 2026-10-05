# Evidencia `v2.88.53-beta` — `AUTO · UI`: **AUTO UI REFACTOR 1.1** (operación única consolidada)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.53-beta` · **Package:** `2.11.53-beta` · **AsOf:** 2026-10-05 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 1.1` · **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK; `openapi.json`/`schema.d.ts` no se mueven).

**Padre:** [`v2.88.52`](../v2.88.52/README.md) (tag → `2fccbf53`, `Release tag CI` [`37319677455`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37319677455) VERDE) → [`v2.88.51`](../v2.88.51/README.md) → [`v2.88.50`](../v2.88.50/README.md).

**Decisión de alcance (declarada).** La auditoría externa (MIA) de `v2.88.52` aprobó sin bloquear y dejó **tres P3**: `UI52-01` (EXIT puede aparecer `REACHED` junto a SETTLEMENT usando el mismo hecho), `UI52-02` (falta traza durable de decisión de cartera) y `UI52-03` (la explicación se resuelve esencialmente por símbolo). Este sello cierra **`UI52-01` y `UI52-03` solo en `packages/shared` + `apps/web`** (sin tocar contrato HTTP) y **consolida la operación única** quitando el doble montaje `operation`/`current`. **NO** implementa `PortfolioDecision` (`UI52-02`, backend/contrato), **NO** diseña la navegación global (`UI52-04`) y **NO** re-corre el pipeline `DÍA-D` (cifras OOS **heredadas y citadas**).

---

## 0. Qué añade este sello (y qué NO)

Tres bloques, todos **de UI / read-model** (cero motor):

1. **`EXIT` plegado en `SETTLEMENT`** (`UI52-01`): el view-model declara `EXIT.foldedInto = "SETTLEMENT"` mientras no exista traza durable propia de salida. La UI **no** pinta dos filas `REACHED` por el mismo hecho financiero; la intención de salida queda como **nota** de la liquidación. Con un paso durable `EXIT`, `foldedInto = null` y vuelve a ser fila independiente (falsable).
2. **Identidad explícita de la explicación** (`UI52-03`, frontend-only): `AutoOperationStoryExplanationInput.identity` (`cycleId`, `instrument`, `strategyVersion`, `direction`, `entryDay`) se expone como hechos; `timeframe`/`régimen` se declaran `NO MEDIDO` (el artefacto DÍA-D no los materializa). La resolución sigue siendo por instrumento; migrar el contrato a `cycleId` + ejes es deuda declarada.
3. **Operación única consolidada**: se elimina el doble montaje de reservas/concurrencia en modo `operation`; un botón «Detalle técnico (ventana actual)» lleva al crudo/experto (`mode=current`). Mapa de superficies: `operation` = historia + contexto; `current` = crudo/experto; `dia-d` = sandbox. Nomenclatura fijada: **14 conceptos del modelo**, no «14 etapas».

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** introduce estados `STALE`/`BLOCKED`. **NO** re-mide `DÍA-D`. **NO** implementa `PortfolioDecision`.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **`EXIT` se pliega en `SETTLEMENT`.** Sin traza durable de salida, `foldedInto === "SETTLEMENT"` y `EXIT.facts` está vacío (no duplica el hecho financiero). | Que `EXIT.foldedInto !== "SETTLEMENT"` o que `EXIT.facts` copie los de `SETTLEMENT`. | §3.1; `auto-operation-story.test.ts` («pliega EXIT en SETTLEMENT…»). |
| **2** | **Una sola fila `REACHED` por hecho.** El panel pinta 12 filas de operación (sin `EXIT`) y la intención de salida es **nota** de la liquidación. | Que el panel pinte una fila `EXIT` independiente o dos `REACHED` por el mismo hecho. | §3.1; `auto-operation-story-panel.test.tsx` («12 filas… EXIT plegado»). |
| **3** | **Plegado falsable.** Con un paso durable `EXIT` en el ciclo, `foldedInto === null` y la etapa muestra sus propios hechos. | Que exista un paso `EXIT` y la etapa siga plegada. | §3.1; `auto-operation-story.test.ts` («despliega EXIT como fila propia…»). |
| **4** | **Identidad de la explicación.** `EXPLANATION` expone `cycleId`/estrategia/`entryDay` (del sello de la SEÑAL) y declara `NO MEDIDO` los ejes no materiales. | Que la explicación no exponga los ejes, o que afirme `timeframe`/`régimen` sin dato. | §3.2; `auto-operation-story.test.ts` («expone la identidad…»). |
| **5** | **Sin duplicación de paneles.** El modo `operation` **no** monta reservas/concurrencia; ofrece «Detalle técnico» → `mode=current`. | Que `operation` vuelva a montar `AutoReservationPanel`/`AutoConcurrencyPanel`. | §3.3; `auto-operation-story-panel.test.tsx` («lleva al detalle técnico…»). |
| **6** | **`Δ AUTO decision/execution motor = 0`.** Sólo cambian el view-model `@bolsa/shared` y la UI; ningún fichero de motor. | Que `git diff` de motor no esté vacío. | §2 (`git diff` sin ficheros de motor; contrato HTTP sin cambio). |
| **7** | **Sin cambio de contrato HTTP.** `openapi.json`/`schema.d.ts` no se mueven. | Que `contract:check` no coincida. | §2 (`contract:check OK`). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.53-beta`) |
| Web `vitest` (suite completa) | **1386 passed** (`241` ficheros) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| `@bolsa/shared` `vitest` | **810 passed | 1 todo** (`97` ficheros) |
| `@bolsa/shared` build | limpio |

> **Nota de método (auditable).** El único error rojo de la sesión fue de **tipos** en `auto-operation-story.ts` (un ternario `ownExit ? null : "SETTLEMENT"` ensanchado a `string` por el literal): se anotó la constante `foldedInto: AutoOperationStoryStageId | null` y se corrigió el tipo, **sin** relajar ninguna regla ni aserción.

---

## 3. El refactor, en detalle

### 3.1 `EXIT` plegado en `SETTLEMENT` — `auto-operation-story.ts`

- `AutoOperationStoryStage` gana `foldedInto: AutoOperationStoryStageId | null` (etapa que absorbe la fila; `null` = fila propia). `STORY_STAGE_SPECS.EXIT` declara `foldedInto: "SETTLEMENT"` (semántica del modelo); el build lo recalcula de forma **falsable**: `stepsById.has("EXIT") ? null : "SETTLEMENT"`.
- La rama `EXIT` del build **no** copia `facts` de `SETTLEMENT` cuando se pliega (evita duplicar el hecho financiero) y mantiene la `derivedNote` «salida = intención/motivo; el hecho durable es la liquidación».
- Tras construir las 14 etapas, la nota de una etapa plegada se **agrega** a la fila que la absorbe: `SETTLEMENT` recibe la intención de salida como nota (una sola fila `REACHED`, spec §4.2).
- El array del modelo sigue teniendo las **14 etapas** (contrato interno intacto); el plegado es de **presentación** (el panel filtra `foldedInto === null`).

### 3.2 Identidad de la explicación — `auto-operation-story.ts` + `auto-operation-story-panel.tsx`

- Nuevo `AutoOperationStoryExplanationIdentity` (`cycleId` · `instrument` · `strategyVersion` · `direction` · `entryDay` · `timeframe` · `regime`) y campo `identity` en `AutoOperationStoryExplanationInput`.
- `buildExplanationStage` añade los ejes como `facts` con medición honesta: los presentes `COMPLETE`; los ausentes (`timeframe`/`régimen`) `UNKNOWN` ⇒ `NO MEDIDO`. Nota: «resuelta por instrumento (DÍA-D); ejes no materiales por ciclo = NO MEDIDO».
- El panel construye la identidad desde el **ciclo seleccionado**: `cycleId`/`instrument`/`strategyVersion`/`direction` del DTO y `entryDay` copiado del `at` del paso `SIGNAL` (no re-derivado). La resolución por instrumento y el enlace «Ver heatmap de {symbol}» se mantienen.

### 3.3 Operación única consolidada — `auto-operation-story-panel.tsx`

- Se elimina el bloque que montaba `AutoReservationPanel` + `AutoConcurrencyPanel` dentro de `operation` (evita el doble montaje con `current`).
- Se añade el botón «Detalle técnico (ventana actual)» (`data-testid="auto-operation-story-open-technical"`) que escribe `mode=current` en la URL (mismo patrón `setSearchParams` que el selector de ciclo y el enlace a DÍA-D).
- El panel filtra las filas a `group === "OPERATION" && foldedInto === null` ⇒ **12 filas** (14 conceptos − `OPPORTUNITY` contexto − `EXIT` plegado).

---

## 4. Límites declarados (NO se cierran aquí)

- **`UI52-02` (traza durable de decisión de cartera / `PortfolioDecision`)**: sigue **abierta**; es de spine/backend + contrato HTTP, fuera de este sello.
- **`UI52-04` (navegación global `OPERAR · CARTERA · RIESGO · ANÁLISIS · SISTEMA`)**: sigue **abierta** (objetivo post-1.0 del spec).
- **Identidad por `cycleId` en el contrato**: la UI **formaliza** los ejes y declara `NO MEDIDO` lo no material, pero **migrar el artefacto DÍA-D** (indexar por `cycleId`/`strategy`/`timeframe`/`entryDay`) es deuda de contrato; en 1.1 **no** se toca el contrato.
- **PIT histórico institucional** (P3) y los `23 orden_creada_sin_fill` (futura Execution Analysis) siguen **abiertos**; `CONFIRMED` **NO** se emite.
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.51`/`v2.88.50` se **heredan y citan**.

---

## 5. Cómo se reproduce

```bash
# 1) Guard backend de versión (meta.bump == package.json).
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) UI.
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `docs/engineering/evidence/v2.88.53/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.53-2026-10-05.md`.
- **Modificados:** `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` (+ test), `docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md`, `package.json` (`2.11.53-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el cambio vive en un view-model puro (`@bolsa/shared`) y en la UI; el contrato HTTP no se mueve.
- **Tag:** `v2.88.53-beta` (anotado) — **cita POST-TAG** del `Release tag CI` (escrita en `main` **después** del tag) y del `GitHub Release`.

---

## 7. Cita del CI (POST-TAG)

> **`Release tag CI`** del tag `v2.88.53-beta`: **POST-TAG** (pendiente de creación/empuje del tag).
>
> Como en `v2.88.46`…`v2.88.52`, el job sólo corre al empujar el tag ⇒ **ningún tag contiene su propio resultado de CI** (límite estructural declarado). La cita larga se añadirá en `main` tras el tag: `replay-repro` debe reproducir el `sha256` del árbol congelado ⇒ **`Δ motor = 0` confirmado por CI**.
