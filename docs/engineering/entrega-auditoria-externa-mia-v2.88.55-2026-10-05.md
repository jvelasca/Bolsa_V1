# Entrega a auditoría externa (MIA) — `v2.88.55-beta` · `AUTO · UI`: **AUTO UI REFACTOR 2.0**

> **Fecha:** 2026-10-05 · **Producto:** `V2.88.55-beta` · **Package:** `2.11.55-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.54-beta` (tag → `c36e3658`, `Release tag CI` [`37328334494`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37328334494) **VERDE**).
> **Unidad de esta auditoría:** el **espacio AUTO** (cinco secciones) y su contrato de navegación/accesibilidad. **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve (`contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.55/README.md`](./evidence/v2.88.55/README.md) (`§0`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.54`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** Mandato explícito: **«implementa el plan AUTO UI REFACTOR 2.0 y eleva la versión para que el auditor la revise desde GitHub»**. El sello **no** añade funcionalidad de motor: introduce la **IA de producto del espacio AUTO** (sub-navegación propia), de forma **aditiva** (todas las pantallas y `/auto-monitor` se conservan) y con `Δ motor = 0`.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el arranque del espacio AUTO, todo **sin tocar el motor**:

1. **Diseño congelado.** [ADR-044](./../adr/044-auto-workspace-information-architecture.md) (espacio AUTO, relación con ADR-040, contrato de accesibilidad, refactor aditivo) + [spec](./spec-auto-ui-refactor-2-0-2026-10-05.md) (mapa sección→superficie, criterio de admisión, orden narrativo, falsabilidad).
2. **Shell `/auto/*`.** Sub-navegación persistente `Operar · Cartera · Riesgo · Análisis · Sistema`; `main` único (lo aporta el shell), un `h1` por ruta y jerarquía `h1`/`h2`/`h3`.
3. **OPERAR canónico.** `/auto/operar/operacion/:cycleId` con la operación única y selección en la URL; lectura causal: qué pasó → por qué → riesgo → broker → resultado → DÍA-D.
4. **Secciones que componen, no reimplementan.** Cartera → `OperationsPanel`; Riesgo → integridad/recon; Análisis → `DiaDAutoPanel` + `OpsAutoEvidenceSection` (+ enlaces a Laboratorio/Asesor); Sistema → ventana cruda del monitor + recon + auditoría.
5. **Entry point.** `AdminRail` (`AUTO` → `/auto`) y comandos de command palette. **No** se crea una sexta puerta L1.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se implementa **`PortfolioDecision`** (`UI52-02`) ni el **contrato de explicación por `cycleId`**.
- **NO** se emite `CONFIRMED`.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Contrato de navegación | `features/auto/auto-nav.ts` | `AUTO_NAV` (5 secciones), `autoOperacionHref`, `autoSectionFromPathname` (puro; sin colisión con `daily-nav`). |
| Shell | `components/layout/auto-workspace-layout.tsx` | Sub-nav persistente; `AutoSectionHeading` (`h1`) y `AutoSectionBlockHeading` (`h2`); **no** anida `<main>`. |
| OPERAR | `features/auto/auto-operar-page.tsx`, `auto-operacion-page.tsx` | Lista de operaciones + operación canónica `/auto/operar/operacion/:cycleId`. |
| Cartera / Riesgo / Análisis / Sistema | `features/auto/auto-{cartera,riesgo,analisis,sistema}-page.tsx` | Componen paneles existentes + enlaces cruzados; Análisis con sub-pestañas en `?tab=`. |
| Rutas | `app.tsx` | `/auto` (layout) + secciones; `/auto-monitor` **intacto**. |
| Entry point | `admin-rail.tsx`, `command-registry.ts` | `AUTO` → `/auto`; comandos `nav-auto`, `nav-auto-<sección>`. |
| Viewport | `lib/routes.ts`, `platform-shell.tsx` | `isAutoRoute`; el espacio AUTO llena el viewport. |
| Panel reutilizado | `auto-monitor/auto-operation-story-panel.tsx` | `cycleIdOverride`/`onSelectCycle` **opcionales** (comportamiento previo intacto). |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.55-beta`) en `v2_89`…`v2_97`. |

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

- **Barrido `axe` en vivo no re-ejecutado.** El método de `v2.88.54` (navegador real + `axe-core 4.10.2`) requiere app + API + auth levantados, fuera del pipeline de este slice. Remediación: repetir el barrido sobre las rutas `/auto/*` en el siguiente sello de UI que lo habilite. Las **invariantes de landmark/encabezado** sí van cubiertas por test.
- **`heading-order` fuera de AUTO (11 rutas, heredado de `v2.88.54`).** Se cierra de raíz **dentro** del espacio AUTO (jerarquía correcta en el shell nuevo); las 11 rutas heredadas siguen siendo deuda declarada.
- **`PortfolioDecision` durable (`UI52-02`)** y **contrato de explicación por `cycleId`**: abiertas (spine/backend), fuera del refactor visual.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): pre-existentes.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`2.11.55-beta`) |
| `@bolsa/web` `vitest` | **1397 passed** (`244` ficheros; +11 sobre `v2.88.54`) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`23` warnings pre-existentes) · **OK** |

---

## 6. Sello

- **Producto:** `V2.88.55-beta`. **Package:** `2.11.55-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Añadidos:** `features/auto/*` (+ tests), `components/layout/auto-workspace-layout.tsx` (+ test), `docs/adr/044-…md`, `docs/engineering/spec-auto-ui-refactor-2-0-2026-10-05.md`, `docs/engineering/evidence/v2.88.55/README.md`, este documento.
- **Modificados:** `app.tsx`, `lib/routes.ts`, `components/layout/platform-shell.tsx`, `components/layout/admin-rail.tsx`, `features/command-palette/command-registry.ts`, `features/auto-monitor/auto-operation-story-panel.tsx`, `package.json` (`2.11.55-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `714863c9` | `apps` `451fa1c9…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `f915934e` | pin `commit: 714863c9` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | `3c7601b5` (tag anotado `811f9b1f`) | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(posterior)_ | — |

- **Tag:** `v2.88.55-beta` (anotado `811f9b1f` → commit `3c7601b5`) — `Release tag CI` [`37333856914`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37333856914) **VERDE** (`replay-repro` **REPRODUCIDO** `sha256 1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI). `GitHub Release` [`v2.88.55-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.55-beta) **publicado** (pre-release).

---

## 7. Guion de auditoría desde GitHub

Todo lo necesario para auditar este sello vive en **GitHub**, sin clon local:

1. **Tag → evidencia.** Ir al release [`v2.88.55-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.55-beta) (o al árbol del tag) y abrir [`docs/engineering/evidence/v2.88.55/README.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.55-beta/docs/engineering/evidence/v2.88.55/README.md). Es la evidencia autocontenida (`§0`–`§7`); dentro del tag, `§7` (cita CI) se declara **POST-TAG**.
2. **Entrega MIA.** Leer este documento (pack de auditoría): qué se entrega/NO, cambios verificables, medición heredada, hallazgos abiertos y gates.
3. **Diseño.** [ADR-044](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.55-beta/docs/adr/044-auto-workspace-information-architecture.md) + [spec](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.55-beta/docs/engineering/spec-auto-ui-refactor-2-0-2026-10-05.md): contienen el mapa sección→superficie y las afirmaciones falsables.
4. **CI del tag.** Abrir la pestaña **Actions** → `Release tag CI` del tag `v2.88.55-beta` (o `gh run list --branch v2.88.55-beta`). Comprobar `replay-repro` **REPRODUCIDO** (⇒ `Δ motor = 0`) y los jobs `python`, `frontend`, `shared`, `decision-spine`, `lifecycle-pg`, `security`, `certify` en **success** (`playwright` integrado queda `skipped` por opt-in).
5. **Reproducción local (opcional).**
   ```bash
   git checkout v2.88.55-beta
   uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   pnpm --filter @bolsa/web test
   pnpm --filter @bolsa/web typecheck
   pnpm --filter @bolsa/web lint
   pnpm --filter @bolsa/web contract:check
   ```
6. **Qué falsaría el sello:** que `contract:check` no coincida · que el diff toque motor/umbrales · que el `Release tag CI` no reproduzca el artefacto (`replay-repro` fallido) · que una ruta `/auto/*` no exponga un `h1`/`main` únicos.
