# Entrega a auditoría externa (MIA) — `v2.88.57-beta` · `AUTO · UI`: **AUTO UI REFACTOR 2.1.1**

> **Fecha:** 2026-10-05 · **Producto:** `V2.88.57-beta` · **Package:** `2.11.57-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.56-beta` (tag → `54a3a7f2`, `Release tag CI` [`37339483917`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37339483917) **VERDE**).
> **Unidad de esta auditoría:** la **integridad del deep-link** de la operación AUTO (defecto **«Deep-link inválido»** de la auditoría externa de `v2.88.56`). **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve (`contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.57/README.md`](./evidence/v2.88.57/README.md) (`§0`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.56`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** Mandato explícito: **«Corregir el deep-link inválido de la operación AUTO (P2 de integridad)»**. El sello **no** añade funcionalidad de motor: cierra un defecto de **integridad de navegación** del espacio AUTO de forma **quirúrgica**, con `Δ motor = 0`.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la integridad del deep-link, todo **sin tocar el motor**:

1. **Selección explícita resuelta (P2).** `resolveAutoOperationSelection` distingue «sin selección» de «selección no resuelta»: un `cycleId` explícito (ruta o `?cycle=`) que no existe en la ventana **no** cae a `cycles[0]`.
2. **Estado «Operación no encontrada».** Se declara el id pedido y **no** se pinta la historia de otra operación (ni etapas ni contexto). El selector de ciclos queda como vía de recuperación.
3. **Render honesto.** El `<ol>`/contexto solo se montan con un ciclo válido; el botón «Detalle técnico» se oculta sin ciclo.
4. **E2E de integridad** (`gp-e2e-v28857`, mock): ruta inválida, `?cycle=` inválido y ruta válida (regresión).

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se cierra **`PortfolioDecision`** (`UI52-02`), la **explicación DÍA-D `cycle_id`-resolutiva**, el **PIT histórico institucional** ni **Execution Analysis**.
- **NO** se emite `CONFIRMED`.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Resolución de selección | `features/auto-monitor/auto-operation-story-panel.tsx` | Helper puro `resolveAutoOperationSelection`; `notFound = id explícito ∧ hasLoaded ∧ sin coincidencia`; sin id explícito mantiene `cycles[0]`. |
| Estado «no encontrada» | `auto-monitor/auto-operation-story-panel.tsx` | `data-testid="auto-operation-story-not-found"` + `data-cycle-id`; sin `<ol>`/contexto/botón técnico sin ciclo. |
| Página | `features/auto/auto-operacion-page.tsx` | El `h1` mantiene el id pedido (`cycle?.instrumentId ?? cycleId`). |
| Tests unit | `auto-monitor/auto-operation-story-panel.test.tsx`, `features/auto/auto-pages.test.tsx` | Ruta y `?cycle=` inválidos + helper; h1 con el id pedido sin inventar otro ciclo. |
| E2E/mocks | `e2e/gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts` (+ `fixtures.ts`, `e2e-mock-routes.ts` reutilizados) | Ruta inválida, `?cycle=` inválido y ruta válida (regresión). |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.57-beta`) en `v2_89`…`v2_97`. |

---

## 3. Medición (cifras heredadas de `v2.88.50`/`v2.88.51`, NO re-medidas)

Sin cambio de motor **ni de muestra**, este sello no re-corre el pipeline. Se **citan** las cifras vigentes de [`v2.88.50`](./evidence/v2.88.50/README.md):

| Métrica (`v2.88.50`) | Valor |
| --- | --- |
| `route` (A/C, `dia-d-thesis-exit-v5` capa v7) | `{materializado: 19, orden_creada_sin_fill: 23}` ⇒ **A = `0`**, **C = `23`** |
| `stopEvaluatedOnTouch` / `deciderRanOnTouch` | **`42/42`** / **`42/42`** |
| `candidate` (`structuralStopCandidate`) | **`42/42`** |
| `THESIS_EXIT` (n) | **`42`** |
| Expectancy bruta global | `-0.7150` |
| Banda global de R | `[-17.290, +19.328]`, `crossesZeroR = true`, **`pointCitable = false`** |

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **Barrido `axe` en vivo no re-ejecutado.** El método de `v2.88.54` requiere app + API + auth y `axe-core` inyectado. Remediación: repetir el barrido en el siguiente sello de UI. El estado «no encontrada» sí va cubierto por test unitario y E2E.
- **`heading-order` fuera de AUTO (11 rutas, heredado de `v2.88.54`)**: deuda declarada.
- **`PortfolioDecision` durable (`UI52-02`)**, **explicación DÍA-D `cycle_id`-resolutiva**, **PIT institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): abiertos (spine/backend), fuera del alcance de integridad de UI.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): pre-existentes.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`2.11.57-beta`) |
| `@bolsa/web` `vitest` | **1412 passed** (`245` ficheros; +10 sobre `v2.88.56`) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`23` warnings pre-existentes) · **OK** |
| `E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857` | **6 passed** (mock, sin API) |

---

## 6. Sello

- **Producto:** `V2.88.57-beta`. **Package:** `2.11.57-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Añadidos:** `e2e/gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts`, `docs/engineering/spec-auto-ui-refactor-2-1-1-2026-10-05.md`, `docs/engineering/evidence/v2.88.57/README.md`, este documento.
- **Modificados:** `features/auto-monitor/{auto-operation-story-panel,auto-operation-story-panel.test}`, `features/auto/auto-pages.test`, `package.json` (`2.11.57-beta`), `v2_89`…`v2_97` (`meta.bump`), `docs/engineering/spec-auto-ui-refactor-2-1-2026-10-05.md`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `287a15b5` | `apps` `0556be2f…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `a30acb07` | pin `commit: 287a15b5` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | _(pendiente)_ | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(posterior)_ | — |

- **Tag:** `v2.88.57-beta` (anotado sobre el commit del sello; funcional `287a15b5` + `chore(window)` `a30acb07`). El resultado del `Release tag CI` se cita **POST-TAG** en la evidencia `§7` y en el `Release`.

---

## 7. Guion de auditoría desde GitHub

Todo lo necesario para auditar este sello vive en **GitHub**, sin clon local:

1. **Tag → evidencia.** Ir al release `v2.88.57-beta` (o al árbol del tag) y abrir `docs/engineering/evidence/v2.88.57/README.md`. Es la evidencia autocontenida (`§0`–`§7`); dentro del tag, `§7` (cita CI) se declara **POST-TAG**.
2. **Entrega MIA.** Leer este documento (pack de auditoría): qué se entrega/NO, cambios verificables, medición heredada, hallazgos abiertos y gates.
3. **Diseño.** `docs/engineering/spec-auto-ui-refactor-2-1-1-2026-10-05.md` (addendum 2.1.1) + `spec-auto-ui-refactor-2-1-2026-10-05.md` + `docs/adr/044-…md`: contienen el contrato de resolución y las afirmaciones falsables.
4. **CI del tag.** Abrir la pestaña **Actions** → `Release tag CI` del tag `v2.88.57-beta`. Comprobar `replay-repro` **REPRODUCIDO** (⇒ `Δ motor = 0`) y los jobs `python`, `frontend`, `shared`, `decision-spine`, `lifecycle-pg`, `security`, `certify` en **success**.
5. **Reproducción local (opcional).**
   ```bash
   git checkout v2.88.57-beta
   uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   pnpm --filter @bolsa/web test
   pnpm --filter @bolsa/web typecheck
   pnpm --filter @bolsa/web lint
   pnpm --filter @bolsa/web contract:check
   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857
   ```
6. **Qué falsaría el sello:** que un `cycleId` inexistente vuelva a caer a `cycles[0]` o pinte etapas de otro ciclo · que un `?cycle=` inválido se ignore · que el `notFound` se dispare con un id válido o durante la carga · que el botón «Detalle técnico» se muestre sin ciclo · que `contract:check` no coincida · que el diff toque motor/umbrales · que `replay-repro` no reproduzca.
