# Traspaso M5 — cierre formal de los frentes `list-values-panel.tsx` + `instruments-page.tsx` (orquestación) · I.1–I.2

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `b54efd0` (frentes list-values e instruments **CERRADOS**) · árbol limpio · sincronizado con origin ·
pasos I.1 `7fb2ea8` · I.2 `b54efd0` · docs cierre (este commit)
**Origen:** [traspaso-m5-continuacion-orquestacion-2026-08-10.md](./traspaso-m5-continuacion-orquestacion-2026-08-10.md)
(punto de entrada FASE 1) + registro **§7.6.d** de
[dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

**Nota de versionado:** este documento es el **cierre formal y definitivo** de ambos frentes para feature-slicing.
Es independiente pero sucesor del doc de entrada listado en "Origen" (que queda como punto de arranque FASE 1).
A partir del HEAD `b54efd0`, este es el único de entrada para el siguiente hilo de M5.

---

## 1. Qué se cerró en este hilo (FASE 1 diagnóstico + 2 pasos atómicos Diseño B)

Tras el cierre formal de backtest-explore (E.1–E.5, M5 en pausa), la continuación retomó M5 atacando la
**orquestación** de los dos frentes de mejor valor/riesgo según §2.3 del cierre anterior: `list-values-panel.tsx` (1.395)
e `instruments-page.tsx` (1.222).

### FASE 1 (diagnóstico, sin cambios)

- **Batería base en HEAD `d4dc779` verificada:** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (solo M7).
- **`list-values-panel.tsx` (1.395):** ya feature-sliced. Solo restaban **2 islas JSX presentacionales de bajo riesgo**
  extraíbles como Diseño B: la **caja de búsqueda** (input + dropdown Yahoo) y la **barra de acciones de selección**.
  El resto es **orquestación pura** (estado de selección, queries, handlers de Estudio/importación, efectos).
- **`instruments-page.tsx` (1.222):** ya feature-sliced. **NO quedan islas de bajo riesgo.** La única masa JSX (el slot
  `list` de `InstrumentsHubSplitLayout`, cabecera sticky + grid) es de **acoplamiento alto** (layout/drag/resize/sort +
  ~10 callbacks y estado de columna del store).

### FASE 2 (plan + aprobación del usuario)

El usuario aprobó la opción **Diseño B**: plan atómico **solo para `list-values-panel.tsx`** (2 pasos) y **cerrar
`instruments-page.tsx`** como ya feature-sliced.

### FASE 3 (ejecución, aprobado)

| Paso | Commit | Componente extraído | Dependencias / Props | Reducción orquestador |
|------|--------|---------------------|----------------------|----------------------|
| I.1 | `7fb2ea8` | `ListSearchBox` (`list-search-box.tsx`) — búsqueda + dropdown catálogo/Yahoo | ~10 (`query`, `debouncedQuery`, `remoteSearchFetching`, `results{catalog,external}`, `importingYahoo`, `showDropdown`, `hasResults`, `onSubmit`, `onSelectCatalog`, `onSelectExternal`) | −49 (1.395 → 1.346) |
| I.2 | `b54efd0` | `ListSelectionToolbar` (`list-selection-toolbar.tsx`) — barra de acciones de selección (`data-testid="list-selection-actions"`) | ~12 (`count`, `viewingEstudio`, `viewingVisualizados`, `updatingSelected`, `sortingByIo`, `selectedInEstudioCount`, `onAddToEstudio`, `onRemove`, `onReorderByIo`, `onOpenCharts`, `onUpdateSelected`, `onClear`) | −104 (1.346 → **1.242**) |

**Reducción total del frente:** `list-values-panel.tsx` de **1.395 → 1.242 líneas (−153)**.

**Patrón — Diseño B (consistente en todo M5):** la lógica de ciclo/handlers (submit de búsqueda, `visualizeFromSearch`,
`handleExternalHit`, add/remove de Estudio, reordenar por IO, abrir gráficos, `updateSelectedInstruments`, limpiar
selección) **permanece en el orquestador** como props-closure; el JSX presentacional se traslada fielmente. La guarda
`{selectionEnabled && selectedInstrumentIds.size > 0}` y los efectos (debounce, auto-kick Estudio, scroll) **no se
mueven**. Se retiraron imports de `lucide-react` que quedaban huérfanos (`Search` en I.1; 7 iconos en I.2).
`data-testid="list-selection-actions"`, `role` y `aria-label` se preservan intactos.

**Batería verde (I.1 → I.2):** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (warnings code-splitting
pre-existentes = M7) en cada paso.
**Cobertura verificada:** JSX presentacional sin test directo; los tests de lógica del feature `trading/lists-tab`
(`list-selection`, `sort-visualizados-by-io`, `list-recommendation-columns`, `fetch-io-scores-for-sort`) pasan intactos.

---

## 2. Decisión de cierre y punto de entrada del siguiente hilo

### 2.1 Estado final — frente `list-values-panel.tsx` → 1.242 líneas — CERRADO

- **Extraídos (I.1+I.2):** `ListSearchBox` (búsqueda + dropdown Yahoo) y `ListSelectionToolbar` (barra de acciones de
  selección). El orquestador conserva toda la lógica de ciclo/orquestación (estado de selección, queries, handlers de
  Estudio/Visualizados, efectos de auto-kick y debounce).
- **Restante:** orquestación pura (no JSX autocontenido extraíble de bajo riesgo). **Se RECOMIENDA y APRUEBA CERRAR**
  el frente aquí.

### 2.2 Estado final — frente `instruments-page.tsx` → 1.222 líneas — CERRADO (ya feature-sliced)

- **Sin islas de bajo riesgo.** La única masa JSX (el slot `list` de `InstrumentsHubSplitLayout`: cabecera sticky +
  grid de filas con drag/reorder/resize/sort + menú de columnas) es de **acoplamiento alto** con el orquestador y el
  store de preferencias (`useInstrumentsHubPreferencesStore`). Extraerlo exigiría ~20+ props y ~10 callbacks levantando
  estado de drag/resize, con riesgo residual real de romper la sincronización del column-layout — **no aporta valor** y
  contradice el criterio de riesgo de M5.
- **Nota:** la lógica pura de esta pantalla ya está test MTS (`instruments-hub-column-layout.test.ts`,
  `instruments-hub-model.test.ts`, `instruments-hub-scores.test.ts`, `instruments-hub-trackers.test.ts`, etc.).

### 2.3 Recomendación para el siguiente hilo

**M5 sigue en pausa por decisión del usuario.** Con estos dos frentes cerrados, el orden de valor/riesgo restante:

1. **Higiene M0/§6.2 CRLF** de `backtests-page.tsx` como commit de formateo propio (M0, fuera del alcance de M5).
2. **Refactor a custom hooks** (extraer handlers/queries de orquestación de los frentes grandes — requiere
   recalibración explícita).
3. **No recomendado:** `chart-drawings-layer.tsx` (1.979, peor valor/riesgo).
4. F4.8 `backtests-page.tsx` (5.127) — **ya sin islas JSX**; el objetivo <3.500 sigue lejos porque el resto es
   orquestación, no JSX autocontenido.

> **Nota transversal:** el área Coach/TOP (backtest-explore, strategy-matrix, instrument-strategy-top, coach-top-save)
> exige la regla `coach-top-quality.mdc` y la batería `pnpm test:coach` en cualquier hilo que la toque. NO aplica a
> list-values/instruments.

---

## 3. Reglas del juego (mantener en el nuevo chat)

- **Protocolo sagrado** del traspaso M5: FASE 1 diagnóstico (sin cambios) → FASE 2 plan atómico + aprobación →
  FASE 3 ejecución + **batería completa por cada paso** (typecheck + lint 0 errores + **test 140/707** + build) +
  `git commit --no-verify` + push + registro §7.6.
- **No tocar backend (M3/M4/M6)** ni **M7** (dev-stack: chunk >500 kB / crash Vite).
- Herramientas: `pnpm` sí en PATH; shell **PowerShell** (no `&&`; usar `;`). Commits con `--no-verify` (CRLF/prettier).
- Push a `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar.

## 4. Estado de referencia para validar batería

| Comando | Esperado |
|---------|----------|
| `pnpm --filter @bolsa/web typecheck` | exit 0 |
| `pnpm --filter @bolsa/web lint` | 0 errores (cosmético Node no bloqueante) |
| `pnpm --filter @bolsa/web test` | 140 ficheros / 707 tests, 0 fallos |
| `pnpm --filter @bolsa/web build` | exit 0 (solo warnings code-splitting = M7) |

- Ficheros nuevos del frente (importados desde `list-values-panel.tsx`):
  `apps/web/src/features/trading/lists-tab/list-search-box.tsx` y
  `apps/web/src/features/trading/lists-tab/list-selection-toolbar.tsx`. `instruments-page.tsx` **intacto**.

---

_Traspaso de cierre de los frentes list-values e instruments de M5. 2026-08-10._
