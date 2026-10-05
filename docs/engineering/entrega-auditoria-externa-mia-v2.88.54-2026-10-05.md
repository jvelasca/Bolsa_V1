# Entrega a auditoría externa (MIA) — `v2.88.54-beta` · UI: **Auditoría UI / accesibilidad de las 15 rutas** (críticos a 0)

> **Fecha:** 2026-10-05 · **Producto:** V2.88.54-beta · **Package:** `2.11.54-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.53-beta` (tag → `c5e6354c`, `Release tag CI` [`37323748100`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37323748100) **VERDE**).
> **Unidad de esta auditoría:** la **ruta** (15 rutas de nivel 1). **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve (`contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.54/README.md`](./evidence/v2.88.54/README.md) (`§0`–`§7`) · **informe falsable:** [`docs/engineering/auditoria-ui-v2.88.54-2026-10-05.md`](./auditoria-ui-v2.88.54-2026-10-05.md).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.53`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** Mandato explícito: **«eleva la versión y auditar toda la parte UI»**. Primero se selló `v2.88.53` (gates + tag + CI + Release) y **después** se abrió `2.11.54-beta` para esta auditoría. El sello **no** añade funcionalidad: corrige **accesibilidad y estructura** en frontend (JSX/atributos accesibles/clases) y documenta **un** hallazgo abierto.

---

## 1. Qué se entrega (y qué NO)

**Se entregan** los arreglos derivados del barrido, todos **sin tocar el motor**:

1. **Críticos a 0.** `button-name` ×2 (`/screeners`: botones *icon-only* de ejecutar/eliminar rastreador) y `select-name` ×1 (`/screeners`, `/alerts`: `<select>` de preset/guardada bajo un `legend` que no los etiqueta) → `title`/`aria-label` explícitos.
2. **`nested-interactive` a 0 (506 nodos).** Filas `div[role="button"][tabindex=0]` **con botones dentro** (`/instruments`, 303) y pestaña de gráfico `div[role="button"]` con botón de cerrar dentro (`/trading`, 203) → interactividad redundante eliminada conservando la vía de teclado.
3. **`landmark-one-main` + `region` a 0 en `/trading` (200 nodos).** La rama de Trading montaba `<div>`; ahora `<main>` (una sola `main` visible por ruta). El `<aside>` del rail de dibujo → `<div>` (evita `landmark-complementary-is-top-level`). `/trading` queda con **0 violaciones**.
4. **`page-has-heading-one` a 0 (10 rutas).** El título de página pasa a `<h1>` en 9 vistas; `sr-only` en `/trading`.
5. **`color-contrast` a 0 (25 nodos).** Se retira la **opacidad apilada** sobre `--bolsa-muted-foreground` (que por sí solo cumple ≈6:1 y hundía el texto meta de 8–12 px a 2.72–4.36:1). El token de tema **no** se toca.
6. **`link-in-text-block` a 0 (7 nodos).** Subrayado permanente en los enlaces de prosa (contraste enlace/contexto 1.17:1 < 3:1 exigido).
7. **Sondas de texto limpias.** Ninguna ruta pinta `undefined`/`NaN`/`null` de JavaScript.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se cierra `heading-order` (§4, abierto declarado).
- **NO** se implementa **`PortfolioDecision`** (`UI52-02`) ni la **navegación global** (`UI52-04`).
- **NO** se emite `CONFIRMED`.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Nombre accesible | `screeners/trackers-panel.tsx`, `screeners/scan-runner-form.tsx`, `alerts/signal-alerts-section.tsx` | `title`/`aria-label` en 2 botones *icon-only* y 4 `<select>` de estrategia. |
| Interactividad anidada | `instruments/instruments-page.tsx`, `trading/charts-zone.tsx` | Fuera `role="button"`/`tabIndex` de la fila (queda el `<button>` interno) y pestaña de gráfico = dos botones hermanos. |
| *Landmarks* / `h1` | `layout/platform-shell.tsx`, `charts/chart-drawing-sidebar.tsx` | Rama Trading → `<main>` + `<h1 class="sr-only">`; rail de dibujo `<aside>` → `<div>`. |
| `h1` de página | `dashboard-page`, `backtests-page`, `instruments-page`, `accounts-page`, `screeners-page`, `alerts-page`, `tax-report-page`, `confirm-content`, `history-page` | Título de página `h2` → `h1`. |
| Contraste | `trading/cabin-visual.ts`, `trading/operator-cabin-ui.tsx`, `trading/trading-status-bar.tsx`, `trading/trading-app-threads.tsx`, `trading/lists-tab/list-carousel.tsx`, `instruments/instruments-page.tsx`, `instruments/instruments-hub-filter-bar.tsx`, `backtests/strategy-filter-carousel.tsx` | Retirada de opacidad apilada (`/55`…`/90`, `opacity-60/70`) sobre texto meta. |
| Enlaces de prosa | `screeners-page`, `research-page`, `tax-report-page`, `operational-console-page` | `underline` permanente en 7 enlaces dentro de párrafos. |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.54-beta`) en `v2_89`…`v2_97`. |

> **Nota de método (auditable).** Durante el sellado se detectó una tanda de barrido **no válida** (resultado idéntico en las 15 rutas, medido mientras la suite `vitest` corría en la misma máquina ⇒ DOM a medio montar). Se descartó y se repitió el barrido **con diagnóstico de `main`/`h1` por ruta**, aceptando sólo medidas con `main = 1` y `h1` correcto. Es exactamente el modo de fallo que un auditor externo debe poder reproducir.

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

## 4. Hallazgo abierto (declarado, con remediación)

**`heading-order`** — `moderate`, **best-practice**, **1 nodo** por ruta, en **11 rutas**. Tras promover el título de página a `<h1>`, el siguiente encabezado en el árbol es un `<h3>` de tarjeta/sección: se salta el nivel `h2`. Nodos literales: `/overview` → `<h3>Cuenta demo EUR</h3>`; `/backtests` → `<h3 class="tracking-tight text-sm font-semibold">`; `/accounts` → `<h3 class="text-lg font-semibold">Cuenta demo EUR</h3>`; `/research` → `<h3 class="font-semibold tracking-tight text-base">Lab Health</h3>`.

- **Por qué no se cierra en este sello:** es best-practice (no une fallo WCAG A/AA) y el arreglo correcto es re-escalar la jerarquía completa (`h1` página · `h2` sección · `h3` sub-apartado), lo que toca los títulos de tarjeta de muchas features y merece su propia tarea con revisión visual.
- **Remediación acotada propuesta:** promover a `<h2>` el primer encabezado de tarjeta/sección de cada página (un nodo por ruta, según `axe`).
- **Declaración de honestidad:** el sello **no introduce** `heading-order` (ya existía en `/research`, `/operational-console` y `/auto-monitor`); sustituye `page-has-heading-one` (10 rutas) por `heading-order` (11 rutas) al dar a las páginas un `h1` real. Ambos son `moderate`/best-practice, y el `h1` es prerequisito de un árbol correcto.

**Otra deuda declarada:** `23` warnings `react-hooks/exhaustive-deps` de `eslint` (**0 errores**), pre-existentes y ajenos a este sello.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`2.11.54-beta`) |
| `node --test scripts/lib/window-forward.test.mjs` | **25 passed / 0 fail** |
| `@bolsa/shared` build + `vitest` | limpio · **810 passed · 1 todo** (`97` ficheros) |
| `@bolsa/web` `vitest` | **1386 passed** (`241` ficheros) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`23` warnings pre-existentes) · **OK** |
| Barrido `axe-core 4.10.2` (15 rutas, navegador real) | **0 `critical` · 0 `serious`**; `heading-order` (`moderate`, 1 nodo) en 11 rutas |

---

## 6. Sello

- **Producto:** `V2.88.54-beta`. **Package:** `2.11.54-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Ficheros modificados (46 en el commit funcional `425292fd`):** 28 ficheros de UI (`apps/web/src/**`), `packages/shared/src/cognitive/auto-operation-story.ts` (+ su test), `package.json` (`2.11.54-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md` y los 3 documentos de auditoría.
- **Añadidos:** `docs/engineering/evidence/v2.88.54/README.md`, `docs/engineering/auditoria-ui-v2.88.54-2026-10-05.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.54-2026-10-05.md`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `425292fd` | `apps` `b5babdb2…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `5a680084` | pin `commit: 425292fd` (no mueve árbol) |
| **Commit del tag** | _(a rellenar)_ | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(posterior)_ | — |

- **Tag:** `v2.88.54-beta` (anotado) — **cita POST-TAG** del `Release tag CI` y del `GitHub Release` (pendiente de escribir tras el tag).
