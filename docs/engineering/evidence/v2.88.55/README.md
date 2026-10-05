# Evidencia `v2.88.55-beta` — `AUTO · UI`: **AUTO UI REFACTOR 2.0** (espacio AUTO con sub-navegación propia)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.55-beta` · **Package:** `2.11.55-beta` · **AsOf:** 2026-10-05 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 2.0`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK).

**Padre:** [`v2.88.54`](../v2.88.54/README.md) (tag → `c36e3658`, `Release tag CI` [`37328334494`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37328334494) VERDE) → [`v2.88.53`](../v2.88.53/README.md) → [`v2.88.52`](../v2.88.52/README.md).

**Decisión de alcance (declarada).** Mandato explícito: **«implementa el plan AUTO UI REFACTOR 2.0 y eleva la versión para que el auditor la revise desde GitHub»**. El sello arranca el **espacio AUTO** con sub-navegación propia (ADR-044 + spec). **NO** toca motor, contrato HTTP, migraciones ni el pipeline `DÍA-D`. Refactor **aditivo**: `/auto-monitor` y todas las pantallas existentes se conservan.

---

## 0. Qué añade este sello (y qué NO)

**Añade** la IA de producto del espacio AUTO, implementada de forma aditiva y sin motor:

1. **ADR-044** + **spec `spec-auto-ui-refactor-2-0-2026-10-05.md`**: congelan las cinco secciones (`Operar · Cartera · Riesgo · Análisis · Sistema`), la relación con ADR-040 (AUTO **no** es puerta L1), el contrato de accesibilidad y el mapa sección→superficie existente.
2. **Shell `/auto/*`**: `auto-nav.ts` (contrato de labels/rutas puro) + `auto-workspace-layout.tsx` (sub-nav persistente; **no** anida `<main>`; el `<h1>` lo aporta la sección).
3. **OPERAR canónico** `/auto/operar/operacion/:cycleId`: la operación única con selección en la URL y lectura causal.
4. **Secciones** que **componen** superficies ya certificadas (Cartera → `OperationsPanel`; Riesgo → integridad/recon; Análisis → `DiaDAutoPanel`/`OpsAutoEvidenceSection`; Sistema → ventana cruda del monitor/recon/auditoría).
5. **Entry point**: `AdminRail` (`AUTO` → `/auto`) + comandos de command palette. `/auto-monitor` intacto.
6. **Jerarquía `h1`/`h2`/`h3`** en el shell nuevo (cierra de raíz el `heading-order` en el espacio AUTO).

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** re-mide `DÍA-D`. **NO** implementa `PortfolioDecision` (`UI52-02`) ni el contrato de explicación por `cycleId`.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **ADR-040 intacto.** AUTO no es una sexta puerta L1. | Que AUTO aparezca como L1 en la barra superior o altere `Hoy · Mercado · Cartera · Asesor · Laboratorio`. | §3; `auto-nav.test.ts` (no colisión con `DAILY_NAV_ORDER`). |
| **2** | **Un solo `<main>` y un solo `<h1>` por ruta AUTO.** | Que `document.querySelectorAll('main').length > 1` dentro del shell AUTO, o que una sección no tenga `h1`. | §3; `auto-workspace-layout.test.tsx` (0 `<main>`, 1 `h1`), `auto-pages.test.tsx`. |
| **3** | **Secciones componen superficies existentes.** | Que una sección reimplemente el motor o re-derive cifras en vez de enlazar/citar. | §3 (mapa sección→superficie); ADR-044 §2. |
| **4** | **`Δ motor = 0`.** Ningún fichero de motor, umbral o contrato. | Que el diff toque motor/umbrales, o que `contract:check` no coincida. | §2 (`contract:check OK`). |
| **5** | **Selección en la URL.** El ciclo seleccionado viaja en la ruta `/auto/operar/operacion/:cycleId`. | Que el selector ignore la ruta o no navegue al cambiar de ciclo. | §3 (`auto-operacion-page.tsx`, `onSelectCycle`). |
| **6** | **`/auto-monitor` se conserva.** El refactor es aditivo. | Que `/auto-monitor` redirija o desaparezca. | §3; `app.tsx` (ruta intacta). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.55-beta`) |
| `@bolsa/web` `vitest` | **1397 passed** (`244` ficheros; **+11** sobre `v2.88.54`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |

> **Nota de método (declarada).** El barrido `axe` en **navegador real** de `v2.88.54` **no** se re-ejecuta en este sello (requiere app + API + auth levantados y `axe-core` inyectado; no forma parte del pipeline de este slice). Las **invariantes de landmark/encabezado** del shell nuevo sí quedan cubiertas por test (`auto-workspace-layout.test.tsx`: 0 `<main>` anidado, 1 `h1`; `auto-pages.test.tsx`: un `h1` por sección). **Hueco declarado**, no silenciado.

---

## 3. El refactor, en detalle

- **Contrato de navegación:** `apps/web/src/features/auto/auto-nav.ts` — `AUTO_NAV` (cinco secciones), `autoOperacionHref` (deep-link con codificación) y `autoSectionFromPathname` (sección activa; `/auto` → `operar`).
- **Shell:** `apps/web/src/components/layout/auto-workspace-layout.tsx` — `AutoWorkspaceLayout` (sub-nav + `Outlet`), `AutoSectionHeading` (el único `h1`) y `AutoSectionBlockHeading` (`h2`). No anida `<main>`.
- **Páginas de sección:** `apps/web/src/features/auto/auto-operar-page.tsx`, `auto-operacion-page.tsx`, `auto-cartera-page.tsx`, `auto-riesgo-page.tsx`, `auto-analisis-page.tsx` (`?tab=`), `auto-sistema-page.tsx`.
- **Rutas:** `apps/web/src/app.tsx` — `/auto` (layout) → `operar` / `operar/operacion/:cycleId` / `cartera` / `riesgo` / `analisis` / `sistema`; `/auto-monitor` intacto.
- **Entry point:** `components/layout/admin-rail.tsx` (`AUTO` → `/auto`) y `features/command-palette/command-registry.ts` (`nav-auto`, `nav-auto-<sección>`).
- **Viewport:** `lib/routes.ts` (`isAutoRoute`) + `components/layout/platform-shell.tsx` (el espacio AUTO llena el viewport sin que el `<main>` haga scroll de página).
- **Panel reutilizado:** `auto-operation-story-panel.tsx` acepta `cycleIdOverride`/`onSelectCycle` **opcionales** (ruta canónica); sin props conserva el comportamiento de `?cycle=` (tests de `v2.88.52`/`v2.88.53` intactos).

---

## 4. Límites declarados (NO se cierran aquí)

- **`PortfolioDecision` durable (`UI52-02`)**: sigue abierta (backend/spine).
- **Contrato de explicación por `cycleId`**: requiere mover `openapi.json`/`schema.d.ts`; fuera de este slice (la identidad ya se formalizó en `v2.88.53`).
- **`heading-order` de `v2.88.54`**: se cierra **de raíz** en el espacio AUTO; las **11 rutas heredadas** fuera de AUTO siguen siendo deuda declarada del sello anterior.
- **Barrido `axe` en vivo:** no re-ejecutado (§2, nota de método).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.

---

## 5. Cómo se reproduce

```bash
# 1) Guard backend de versión (meta.bump == package.json).
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) UI.
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `apps/web/src/features/auto/auto-nav.ts` (+ `auto-nav.test.ts`), `apps/web/src/features/auto/auto-operar-page.tsx`, `auto-operacion-page.tsx`, `auto-cartera-page.tsx`, `auto-riesgo-page.tsx`, `auto-analisis-page.tsx`, `auto-sistema-page.tsx` (+ `auto-pages.test.tsx`), `apps/web/src/components/layout/auto-workspace-layout.tsx` (+ test), `docs/adr/044-auto-workspace-information-architecture.md`, `docs/engineering/spec-auto-ui-refactor-2-0-2026-10-05.md`, `docs/engineering/evidence/v2.88.55/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.55-2026-10-05.md`.
- **Modificados:** `apps/web/src/app.tsx`, `apps/web/src/lib/routes.ts`, `apps/web/src/components/layout/platform-shell.tsx`, `apps/web/src/components/layout/admin-rail.tsx`, `apps/web/src/features/command-palette/command-registry.ts`, `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx`, `package.json` (`2.11.55-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el contrato HTTP no se mueve.
- **Ficheros de UI tocados (`apps/web/src/**`):** `app.tsx`, `lib/routes.ts`, `components/layout/{platform-shell,admin-rail,auto-workspace-layout}`, `features/auto/*`, `features/command-palette/command-registry.ts`, `features/auto-monitor/auto-operation-story-panel.tsx`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `714863c9` | `apps` `451fa1c9…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `f915934e` | pin `commit: 714863c9` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | `3c7601b5` (tag anotado `811f9b1f`) | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(posterior)_ | — |

---

## 7. Cita del CI (POST-TAG)

> **`Release tag CI`** del tag `v2.88.55-beta`: run [`37333856914`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37333856914) **VERDE** (`attempt 1`, `15:33:59Z → 15:41:33Z`; `12` jobs = `11` `success` + `playwright` integrado `skipped`; `certify` `success`; `python` `success` (ruff/imports/mypy/pytest offline); `frontend` `success` (typecheck/lint/test/build + `contract:check`); `shared` `success`; `decision-spine` `success`; `lifecycle-pg` `success`; `security (gitleaks)` `success`; `dr-verify` `success`; `a7-gate` `success`; `replay-repro` `success` **`REPRODUCIDO`** `sha256 1E3ADAC2…` = sello ⇒ **`Δ motor = 0` confirmado por CI**). **`GitHub Release` [`v2.88.55-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.55-beta) publicado** (pre-release). Ningún tag contiene su propio resultado de CI — límite estructural declarado, como en `v2.88.46`…`v2.88.54`.
