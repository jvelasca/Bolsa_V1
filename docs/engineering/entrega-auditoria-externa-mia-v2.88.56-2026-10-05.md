# Entrega a auditoría externa (MIA) — `v2.88.56-beta` · `AUTO · UI`: **AUTO UI REFACTOR 2.1**

> **Fecha:** 2026-10-05 · **Producto:** `V2.88.56-beta` · **Package:** `2.11.56-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.55-beta` (tag → `3c7601b5`, `Release tag CI` [`37333856914`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37333856914) **VERDE**).
> **Unidad de esta auditoría:** la **navegación canónica** de la operación AUTO (defecto **P2** de la auditoría de `v2.88.55`) y el pulido **P3** asociado (doble selección de OPERAR, ARIA de ANÁLISIS, wording de CARTERA). **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve (`contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.56/README.md`](./evidence/v2.88.56/README.md) (`§0`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.55`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** Mandato explícito: **«implementa el plan `v2.88.56 — AUTO UI REFACTOR 2.1`»**. El sello **no** añade funcionalidad de motor: corrige la **navegación canónica** y el **pulido UX** del espacio AUTO, de forma **aditiva**, con `Δ motor = 0`.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la corrección del espacio AUTO, todo **sin tocar el motor**:

1. **Navegación canónica (P2).** Los botones del `AutoOperationStoryPanel` («Detalle técnico», «Ver heatmap») dejan de escribir parámetros inertes sobre la ruta actual y navegan a `/auto-monitor?mode=current&cycle=<id>` y `/auto/analisis?tab=dia-d&view=feedback&window=…&symbol=…`, vía helpers puros (`autoTechnicalDetailHref`, `autoDiaDHref`).
2. **`cycle` no inerte.** El monitor enfoca/desplaza la tarjeta del ciclo (`data-cycle-focused="true"`).
3. **OPERAR sin doble selección (P3).** La lista de operaciones es la única fuente; la historia vive en su ruta canónica.
4. **Tabs WAI-ARIA completas (P3)** en ANÁLISIS: `aria-controls`↔`tabpanel`, roving `tabIndex` y teclado `ArrowLeft`/`ArrowRight`/`Home`/`End`.
5. **CARTERA honesta (P3).** Sin «Read-only»: estado/supervisión + acciones que **encolan** Confirm.
6. **E2E de navegación** (`gp-e2e-v28856`, mock) + invariantes `main`/`h1` por ruta AUTO.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se cierra **`PortfolioDecision`** (`UI52-02`), el **contrato de explicación por `cycleId`**, el **PIT histórico institucional** ni **Execution Analysis**.
- **NO** se emite `CONFIRMED`.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Contrato de navegación | `features/auto/auto-nav.ts` | `AUTO_MONITOR_PATH`, `autoTechnicalDetailHref(cycleId?)`, `autoDiaDHref({window,symbol})` (puros, con codificación). |
| Panel de operación | `auto-monitor/auto-operation-story-panel.tsx` | Botones → `navigate(...)` a los destinos canónicos. |
| Monitor | `auto-monitor/auto-monitor-page.tsx`, `auto-cycle-timeline.tsx` | Leen `?cycle=` y enfocan la `CycleCard` (`data-cycle-focused`, anillo, `scrollIntoView`). |
| OPERAR | `features/auto/auto-operar-page.tsx` | Lista = única selección; sin `AutoOperationStoryPanel` embebido. |
| ANÁLISIS | `features/auto/auto-analisis-page.tsx` | Tabs WAI-ARIA (roles, `aria-controls`/`tabpanel`, roving, teclado). |
| CARTERA | `features/auto/auto-cartera-page.tsx` | Descripción sin «Read-only». |
| E2E/mocks | `e2e/helpers/e2e-mock-routes.ts`, `e2e-mock-installers.ts`, `fixtures.ts`, `e2e/gp-e2e-v28856-auto-ui-navigation-mock.spec.ts` | Flag `auto`, payloads monitor/DÍA-D, installer + spec de navegación. |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.56-beta`) en `v2_89`…`v2_97`. |

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

- **Barrido `axe` en vivo no re-ejecutado.** El método de `v2.88.54` requiere app + API + auth y `axe-core` inyectado. Remediación: repetir el barrido sobre `/auto/*` en el siguiente sello de UI. Las **invariantes de landmark/encabezado** y el **contrato ARIA de tabs** sí van cubiertos por test.
- **`heading-order` fuera de AUTO (11 rutas, heredado de `v2.88.54`)**: deuda declarada.
- **`PortfolioDecision` durable (`UI52-02`)**, **contrato de explicación por `cycleId`**, **PIT institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): abiertos (spine/backend), fuera del pulido de UI.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): pre-existentes.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`2.11.56-beta`) |
| `@bolsa/web` `vitest` | **1402 passed** (`245` ficheros; +5 sobre `v2.88.55`) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`23` warnings pre-existentes) · **OK** |
| `E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856` | **3 passed** (mock, sin API) |

---

## 6. Sello

- **Producto:** `V2.88.56-beta`. **Package:** `2.11.56-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Añadidos:** `features/auto/auto-analisis-page.test.tsx`, `e2e/gp-e2e-v28856-auto-ui-navigation-mock.spec.ts`, `docs/engineering/spec-auto-ui-refactor-2-1-2026-10-05.md`, `docs/engineering/evidence/v2.88.56/README.md`, este documento.
- **Modificados:** `features/auto/{auto-nav,auto-nav.test,auto-operar-page,auto-analisis-page,auto-cartera-page,auto-pages.test}`, `features/auto-monitor/{auto-operation-story-panel,auto-operation-story-panel.test,auto-monitor-page,auto-cycle-timeline}`, `e2e/helpers/{e2e-mock-routes,e2e-mock-installers}`, `e2e/fixtures.ts`, `package.json` (`2.11.56-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `PENDIENTE` (se fija en `docs(seal)`) | `apps` `PENDIENTE` / `packages` `PENDIENTE` |
| Re-anclaje del freeze de la ventana (`chore`) | `PENDIENTE` | pin `commit: <funcional>` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | `PENDIENTE` | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(posterior)_ | — |

- **Tag:** `v2.88.56-beta` — `Release tag CI` **PENDIENTE** (se cita tras el push). Dentro del tag, la evidencia lo declara como `POST-TAG`.

---

## 7. Guion de auditoría desde GitHub

Todo lo necesario para auditar este sello vive en **GitHub**, sin clon local:

1. **Tag → evidencia.** Ir al release `v2.88.56-beta` (o al árbol del tag) y abrir `docs/engineering/evidence/v2.88.56/README.md`. Es la evidencia autocontenida (`§0`–`§7`); dentro del tag, `§7` (cita CI) se declara **POST-TAG**.
2. **Entrega MIA.** Leer este documento (pack de auditoría): qué se entrega/NO, cambios verificables, medición heredada, hallazgos abiertos y gates.
3. **Diseño.** `docs/engineering/spec-auto-ui-refactor-2-1-2026-10-05.md` (addendum 2.1) + `spec-auto-ui-refactor-2-0-2026-10-05.md` + `docs/adr/044-…md`: contienen el contrato de navegación (un destino por intención) y las afirmaciones falsables.
4. **CI del tag.** Abrir la pestaña **Actions** → `Release tag CI` del tag `v2.88.56-beta`. Comprobar `replay-repro` **REPRODUCIDO** (⇒ `Δ motor = 0`) y los jobs `python`, `frontend`, `shared`, `decision-spine`, `lifecycle-pg`, `security`, `certify` en **success**.
5. **Reproducción local (opcional).**
   ```bash
   git checkout v2.88.56-beta
   uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   pnpm --filter @bolsa/web test
   pnpm --filter @bolsa/web typecheck
   pnpm --filter @bolsa/web lint
   pnpm --filter @bolsa/web contract:check
   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856
   ```
6. **Qué falsaría el sello:** que «Detalle técnico»/«Ver heatmap» vuelvan a escribir parámetros sobre `/auto/operar[/operacion/:cycleId]` · que `?cycle=` no enfoque la tarjeta del ciclo · que OPERAR vuelva a duplicar la selección · que un `role="tab"` carezca de `aria-controls`/`tabpanel` o no responda al teclado · que `contract:check` no coincida · que el diff toque motor/umbrales · que `replay-repro` no reproduzca · que una ruta `/auto/*` no exponga un `h1`/`main` únicos.
