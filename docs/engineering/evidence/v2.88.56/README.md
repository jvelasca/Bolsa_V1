# Evidencia `v2.88.56-beta` — `AUTO · UI`: **AUTO UI REFACTOR 2.1** (navegación canónica y pulido UX)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.56-beta` · **Package:** `2.11.56-beta` · **AsOf:** 2026-10-05 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 2.1`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK).

**Padre:** [`v2.88.55`](../v2.88.55/README.md) (tag → `3c7601b5`, `Release tag CI` [`37333856914`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37333856914) VERDE) → [`v2.88.54`](../v2.88.54/README.md).

**Decisión de alcance (declarada).** Mandato explícito: **«implementa el plan `v2.88.56 — AUTO UI REFACTOR 2.1`»**. El sello cierra el defecto funcional **P2** de la auditoría externa de `v2.88.55` (botones del `AutoOperationStoryPanel` inertes desde `/auto/*`) y el pulido **P3** asociado (doble selección en OPERAR, ARIA de las tabs de ANÁLISIS, wording de CARTERA). **NO** toca motor, contrato HTTP, migraciones ni el pipeline `DÍA-D`. Refactor **aditivo**: `/auto-monitor` y todas las pantallas existentes se conservan.

---

## 0. Qué añade este sello (y qué NO)

**Añade** la corrección de navegación del espacio AUTO, sin motor:

1. **Helpers canónicos puros** en `auto-nav.ts`: `AUTO_MONITOR_PATH`, `autoTechnicalDetailHref(cycleId?)` y `autoDiaDHref({ window?, symbol? })`.
2. **Botones del `AutoOperationStoryPanel`** → navegan a los destinos canónicos (`/auto-monitor?mode=current&cycle=…`, `/auto/analisis?tab=dia-d&view=feedback&window=…&symbol=…`) mediante `useNavigate`.
3. **`cycle` no inerte**: `AutoMonitorPage` lo lee en `mode=current` y `AutoCycleTimeline` enfoca/desplaza la `CycleCard` correspondiente (`data-cycle-focused="true"` + anillo).
4. **OPERAR sin doble selección**: la lista de operaciones es la única fuente; se retira el `AutoOperationStoryPanel` embebido.
5. **Tabs WAI-ARIA completas** en ANÁLISIS: `id`/`aria-controls`/roving `tabIndex` + `role="tabpanel"` con `id`/`aria-labelledby`/`tabIndex`, y teclado `ArrowLeft`/`ArrowRight`/`Home`/`End`.
6. **CARTERA honesta**: se retira el «Read-only» de la descripción (contiene acciones que **encolan** Confirm).
7. **E2E** `gp-e2e-v28856-auto-ui-navigation-mock.spec.ts` (mock): `Operar → Operación → detalle técnico/DÍA-D` + un `<main>`/`h1` por ruta.

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** re-mide `DÍA-D`. **NO** cierra `PortfolioDecision` (`UI52-02`) ni el contrato de explicación por `cycleId`.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **Navegación canónica.** «Detalle técnico» va a `/auto-monitor?mode=current&cycle=<id>`; «Ver heatmap» a `/auto/analisis?tab=dia-d&view=feedback&window=…&symbol=…`. | Que los botones escriban parámetros sobre la ruta actual (`/auto/operar[/operacion/:cycleId]`). | §3; `auto-operation-story-panel.test.tsx`; E2E `gp-e2e-v28856`. |
| **2** | **`cycle` no es inerte.** `/auto-monitor?mode=current&cycle=X` enfoca la `CycleCard` de `X`. | Que el monitor ignore `cycle`. | §3; E2E (`data-cycle-focused="true"`). |
| **3** | **Una sola fuente de selección en OPERAR.** | Que coexistan la lista y el selector interno del story panel. | §3; `auto-pages.test.tsx` (`story-stub` ausente). |
| **4** | **Contrato ARIA de tabs.** Cada `role="tab"` tiene `aria-controls`↔`tabpanel` y responde a flechas/Home/End. | Que falte el vínculo `aria-controls`/`tabpanel` o la selección por teclado. | §3; `auto-analisis-page.test.tsx`. |
| **5** | **CARTERA no es read-only.** La descripción declara estado/supervisión + acciones que encolan Confirm. | Que la descripción afirme «Read-only». | §3 (`auto-cartera-page.tsx`). |
| **6** | **Un solo `<main>` y un `h1` por ruta AUTO.** | Que una ruta AUTO anide un segundo `<main>` (excluido el keep-alive de Backtests) o carezca de `h1`. | §3; E2E (invariantes por ruta). |
| **7** | **`Δ motor = 0`.** Ningún fichero de motor, umbral o contrato. | Que el diff toque motor/umbrales, o que `contract:check` no coincida. | §2 (`contract:check OK`). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.56-beta`) |
| `@bolsa/web` `vitest` | **1402 passed** (`245` ficheros; **+5** sobre `v2.88.55`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| `E2E_RUN=1 pnpm e2e -- gp-e2e-v28856` | **3 passed** (mock, sin API) |

> **Nota de método (declarada).** El barrido `axe` en **navegador real** de `v2.88.54` **no** se re-ejecuta (requiere app + API + auth y `axe-core` inyectado). Las invariantes de landmark/encabezado y el contrato ARIA quedan cubiertas por test unitario (`auto-analisis-page.test.tsx`) y por el E2E de navegación. **Hueco declarado**, no silenciado.

---

## 3. La corrección, en detalle

- **Contrato de navegación:** `apps/web/src/features/auto/auto-nav.ts` — `AUTO_MONITOR_PATH = "/auto-monitor"`, `autoTechnicalDetailHref(cycleId?)` (`/auto-monitor?mode=current[&cycle=…]`), `autoDiaDHref({ window, symbol })` (`/auto/analisis?tab=dia-d&view=feedback[&window=&symbol=]`), con codificación vía `URLSearchParams`.
- **Panel de operación:** `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` — `openTechnicalDetail` → `navigate(autoTechnicalDetailHref(selected?.cycleId))`; `openDiaDHeatmap` → `navigate(autoDiaDHref({ window: latestWindow, symbol }))`.
- **Monitor:** `auto-monitor-page.tsx` lee `searchParams.get("cycle")` y lo pasa a `AutoCycleTimeline` como `focusCycleId`; `auto-cycle-timeline.tsx` marca (`data-cycle-focused`, anillo `border-primary`) y hace `scrollIntoView` de la tarjeta.
- **OPERAR:** `auto-operar-page.tsx` — la lista (`auto-operar-operation-link` → `/auto/operar/operacion/:cycleId`) es la única selección.
- **ANÁLISIS:** `auto-analisis-page.tsx` — patrón WAI-ARIA de tabs completo + roving `tabIndex` + `onKeyDown` (`ArrowLeft`/`ArrowRight`/`Home`/`End`).
- **CARTERA:** `auto-cartera-page.tsx` — descripción de estado/supervisión + acciones que encolan Confirm.
- **E2E/mocks:** `apps/web/e2e/helpers/e2e-mock-routes.ts` (flag `auto?: boolean` + payloads del monitor y DÍA-D), `e2e-mock-installers.ts`/`fixtures.ts` (`installAutoWorkspaceMocks`), `e2e/gp-e2e-v28856-auto-ui-navigation-mock.spec.ts`.

---

## 4. Límites declarados (NO se cierran aquí)

- **`PortfolioDecision` durable (`UI52-02`)**: sigue abierta (backend/spine).
- **Contrato de explicación por `cycleId`**: requiere mover `openapi.json`/`schema.d.ts`; fuera de este slice.
- **`heading-order` de las 11 rutas heredadas fuera de AUTO**: deuda declarada del sello `v2.88.54`.
- **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): P3 abiertas.
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

# 3) E2E de navegación AUTO (mock, sin API).
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `apps/web/src/features/auto/auto-analisis-page.test.tsx`, `apps/web/e2e/gp-e2e-v28856-auto-ui-navigation-mock.spec.ts`, `docs/engineering/spec-auto-ui-refactor-2-1-2026-10-05.md`, `docs/engineering/evidence/v2.88.56/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.56-2026-10-05.md`.
- **Modificados:** `apps/web/src/features/auto/{auto-nav.ts, auto-nav.test.ts, auto-operar-page.tsx, auto-analisis-page.tsx, auto-cartera-page.tsx, auto-pages.test.tsx}`, `apps/web/src/features/auto-monitor/{auto-operation-story-panel.tsx, auto-operation-story-panel.test.tsx, auto-monitor-page.tsx, auto-cycle-timeline.tsx}`, `apps/web/e2e/helpers/{e2e-mock-routes.ts, e2e-mock-installers.ts}`, `apps/web/e2e/fixtures.ts`, `package.json` (`2.11.56-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el contrato HTTP no se mueve.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `PENDIENTE` (se fija en `docs(seal)`) | `apps` `PENDIENTE` / `packages` `PENDIENTE` |
| Re-anclaje del freeze de la ventana (`chore`) | `PENDIENTE` | pin `commit: <funcional>` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | `PENDIENTE` | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(posterior)_ | — |

---

## 7. Cita del CI (POST-TAG)

> **PENDIENTE.** El tag `v2.88.56-beta` se cita aquí tras el push y el `Release tag CI`. Ningún tag contiene su propio resultado de CI — límite estructural declarado, como en `v2.88.46`…`v2.88.55`.
