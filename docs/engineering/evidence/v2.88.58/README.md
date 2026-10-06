# Evidencia `v2.88.58-beta` — `AUTO · UI`: **AUTO COCKPIT 1.0** (usuario básico: semáforo de realidad, identidad legible y cockpit OPERAR)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.58-beta` · **Package:** `2.11.58-beta` · **AsOf:** 2026-10-05 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 1.0 (Cockpit usuario básico)`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK).

**Padre:** [`v2.88.57`](../v2.88.57/README.md) (tag → `d44e00c9`, `Release tag CI` [`37344802844`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37344802844) VERDE) → [`v2.88.56`](../v2.88.56/README.md).

**Decisión de alcance (declarada).** Mandato: **«convertir AUTO en un cockpit legible para un usuario básico»** sobre la auditoría read-only [`auditoria-ui-auto-cockpit-2026-10-05.md`](../../auditoria-ui-auto-cockpit-2026-10-05.md), con la spec **congelada** [`spec-auto-cockpit-usuario-basico-2026-10-05.md`](../../spec-auto-cockpit-usuario-basico-2026-10-05.md) (F1–F4). Refactor **de UI/read-model**: **NO** toca motor, contrato HTTP, migraciones ni el pipeline `DÍA-D`.

---

## 0. Qué añade este sello (y qué NO)

**Añade** cuatro capacidades de lectura del espacio AUTO, sin motor:

1. **F1 — Semáforo de realidad monetaria (P1 `F-R1` cerrado).** `auto-reality.ts` (helper puro, **fail-closed**: sólo una cuenta `live` reclama dinero real; `simulated`/`paper`/desconocido → **virtual**) + `auto-reality-strip.tsx`, montado en `auto-workspace-layout.tsx` sobre el `<Outlet />`. Las cinco secciones declaran en primer nivel `DINERO VIRTUAL · AUTO DEMO` («No envía órdenes a XTB»), el tipo de cuenta legible y el capital (`NO MEDIDO` hasta que llega la respuesta, **nunca** `0`). **No** re-deriva: cablea `buildPaperAutoPosture` + cuenta activa + kill switch.
2. **F2 — Identidad legible de operación (P1 `F-O1` cerrado).** `auto-operation-identity.ts` (helper puro): la lista de OPERAR pasa de `instrumentId` a `AAPL · 03 oct · Largo · Abierto` (día de entrada **copiado** del sello de la etapa `SIGNAL`; dirección/estado del view model de `@bolsa/shared`). El `cycleId` deja de ser texto humano (vive en `data-cycle-id`/URL). Un campo ausente se declara `NO MEDIDO`.
3. **F3 — Cockpit OPERAR (P2 `F-O3` cerrado).** `auto-operar-page.tsx` se divide en **Oportunidades** (lanzadera que **enlaza** a la Mesa; **no** recalcula el ranking) y **Operaciones** (identidad legible + enlace canónico), con estados propios y distinguibles: `Cargando…`, error («No se pudieron cargar las operaciones»), vacío («Sin operaciones en la ventana») y `NO MEDIDO`. Un fallo de red deja de disfrazarse de «sin operaciones».
4. **F4 — Lenguaje plano y accesibilidad (P1 `F-J1`; P2 `F-J2`/`F-DUP1`/`F-A1` cerrados).** `auto-copy.ts` centraliza títulos/descripciones de las cinco secciones sin jerga de ingeniería; `auto-story-plain-labels.ts` traduce los nombres de etapa de la historia; se retira la **reconciliación duplicada** de `/auto/riesgo` (queda una sola vez dentro de AUTO); el conmutador de vista de DÍA-D (`dia-d-auto-panel.tsx`) pasa a **tablist WAI-ARIA completo** (`role="tabpanel"`/`aria-controls`/`aria-labelledby`/roving `tabIndex` + `ArrowLeft`/`ArrowRight`/`Home`/`End`), como el de ANÁLISIS.

**Optimización (declarada).** `AutoRealityStrip` consulta el kill switch con la **misma `queryKey`** que `useMesaEntriesBlocked` en vez de invocar ese hook entero, para no disparar `decision-board`/`incidentes` (que **no** usa) en cada una de las cinco rutas del shell.

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** re-mide `DÍA-D`. **NO** cierra `PortfolioDecision` (`UI52-02`), la explicación DÍA-D `cycleId`-resolutiva (`F-S1`) ni el barrido `axe` en vivo (`F-A2`).

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | Con una cuenta **`simulated`** (o desconocida), el semáforo declara **`DINERO VIRTUAL`**. | Que una cuenta no-`live` reclame dinero real. | §3; `auto-reality.test.ts`; `auto-reality-strip.test.tsx`. |
| **2** | El capital ausente se pinta **`NO MEDIDO`**, nunca `0`. | Que un hueco se renderice como `0` o `—` indistinguible. | §3; `auto-reality.test.ts`. |
| **3** | Dos ciclos del **mismo símbolo** se distinguen por texto visible (día/dirección/estado). | Que la lista vuelva a mostrar sólo `instrumentId`. | §3; `auto-operation-identity.test.ts`; `auto-pages.test.tsx`. |
| **4** | Un **fallo de red** en OPERAR muestra un estado de **error**, distinto del vacío. | Que un `isError` se pinte como «Sin operaciones». | §3; `auto-pages.test.tsx`. |
| **5** | El conmutador de vista de DÍA-D enlaza **tab↔panel** (`role="tabpanel"`/`aria-controls`) y navega por teclado. | Que falte el `tabpanel` o las flechas/Home/End. | §3; `dia-d-auto-panel.test.tsx`. |
| **6** | `Δ motor = 0`. | Que el diff toque motor/umbrales, o que `contract:check` no coincida. | §2 (`contract:check OK`). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.58-beta`) |
| `@bolsa/web` `vitest` | **1435 passed** (`249` ficheros; **+23** sobre `v2.88.57`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| `pnpm window:test` | **25/25** |
| `E2E_RUN=1 pnpm e2e -- gp-e2e-v28856 gp-e2e-v28857` | **6 passed** (mock, sin API; `workers=1` como CI) |

> **Nota de método (declarada).** El barrido `axe` en **navegador real** de `v2.88.54` **no** se re-ejecuta (requiere app + API + auth y `axe-core` inyectado); el hueco `F-A2` **sigue abierto**. Los nuevos estados (semáforo, identidad, error/vacío de OPERAR, tablist DÍA-D) se cubren por test unitario. **Hueco declarado**, no silenciado.

---

## 3. Las correcciones, en detalle

- **Realidad monetaria:** helper puro `buildAutoReality` (`features/auto/auto-reality.ts`) → `{ kind: 'live' | 'virtual', accountType, capital }`, **fail-closed** a `virtual`; `auto-reality-strip.tsx` lo pinta sobre el `<Outlet />` del shell (`auto-workspace-layout.tsx`).
- **Identidad de operación:** helper puro `buildOperationIdentity` (`features/auto/auto-operation-identity.ts`) → `AAPL · 03 oct · Largo · Abierto` (campos ausentes → `NO MEDIDO`); consumido por la lista de `auto-operar-page.tsx`.
- **Cockpit OPERAR:** `features/auto/auto-operar-page.tsx` — bloques **Oportunidades** (enlace) y **Operaciones** (identidad + enlace canónico), con estados `Cargando…`/error/vacío/`NO MEDIDO` distinguibles.
- **Lenguaje plano:** `features/auto/auto-copy.ts` (títulos/descripciones de las cinco secciones) + `features/auto/auto-story-plain-labels.ts` (etapas de la historia).
- **Sin duplicado:** `features/auto/auto-riesgo-page.tsx` deja de re-montar la reconciliación (queda una sola vez dentro de AUTO).
- **Accesibilidad DÍA-D:** `features/auto-monitor/dia-d-auto-panel.tsx` → tablist WAI-ARIA completo (tab↔panel + teclado).
- **Bump:** `package.json` (`2.11.58-beta`) + `meta.bump` de `apps/api-python/scripts/v2_89…v2_97`.
- **Re-anclaje del freeze:** `scripts/lib/window-forward.mjs` → pin `commit: dd3af96d`, `appsHash: 6f24ce28…` (`packages` sin cambio: `95cb0d69…`).

---

## 4. Límites declarados (NO se cierran aquí)

- **`PortfolioDecision` durable (`UI52-02`)**: sigue abierta (backend/spine).
- **Contrato de explicación DÍA-D verdaderamente `cycleId`-resolutivo (`F-S1`)**: la resolución sigue siendo por `symbol`; fase backend **F5**, fuera de este slice.
- **`F-A2` — barrido `axe` en vivo de `/auto/*`**: **no** re-ejecutado (§2, nota de método).
- **`F-S2`/`F-S3` (P3)**: densidad tipográfica (`text-[11px]`) e `h1` crudo de ausencia.
- **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): P3 abiertas.
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

# 3) Freeze del runner de la ventana.
pnpm window:test

# 4) E2E del cockpit AUTO (mock, sin API; workers=1 como CI).
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `apps/web/src/features/auto/{auto-reality.ts, auto-reality.test.ts, auto-reality-strip.tsx, auto-reality-strip.test.tsx, auto-operation-identity.ts, auto-operation-identity.test.ts, auto-story-plain-labels.ts, auto-story-plain-labels.test.ts, auto-copy.ts}`, `apps/web/src/components/layout/auto-workspace-layout.tsx` + `.test.tsx`, `docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md`, `docs/engineering/auditoria-ui-auto-cockpit-2026-10-05.md`, `docs/engineering/evidence/v2.88.58/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.58-2026-10-05.md`.
- **Modificados:** `apps/web/src/features/auto/auto-operar-page.tsx` + `auto-pages.test.tsx`, `apps/web/src/features/auto/auto-riesgo-page.tsx`, `apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx` + `dia-d-auto-panel.test.tsx`, `package.json` (`2.11.58-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el contrato HTTP no se mueve.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `dd3af96d` | `apps` `6f24ce28…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `7fc486d1` | pin `commit: dd3af96d` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | `e99c99c5` (tag anotado `v2.88.58-beta`) | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia §7) | _(este commit)_ | — |

---

## 7. Cita del CI (POST-TAG)

> **`Release tag CI`** del tag `v2.88.58-beta`: run [`37367672717`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37367672717) **VERDE** (`attempt 2`, `20:06:28Z → 21:49:10Z`). El **`attempt 1`** cayó por **infraestructura de GitHub**, no por producto: `The job was not acquired by Runner of type hosted even after multiple attempts` (`lifecycle-pg`/`python`/`a7-gate`/`decision-spine`/`security`/`playwright`/`shared` no arrancaron; en ese mismo attempt sí pasaron `frontend`, `replay-repro` y `dr-verify`); el rerun `--failed` los ejecutó en verde. Jobs `success`: `security` (gitleaks), `python` (ruff/imports/mypy/pytest offline; **`4538 passed / 45 skipped`**), `a7-gate`, `decision-spine`, `shared`, `playwright (mock E2E)` (`7m9s`), `lifecycle-pg` (Alembic + auth + golden restart), `frontend` (typecheck/lint/test/build + `contract:check`; **`Test Files 249 passed (249)`**), `replay-repro` (`5m14s`), `dr-verify`, `certify`; `playwright (integrated E2E)` **`skipped`** (opt-in, por diseño). **`replay-repro` `VEREDICTO REPRODUCIDO`** (`mismo CONTENIDO; el sello está en CRLF y este fichero en LF`) — `bytes 3340728`, `sha256` LF **`1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`** = sello ⇒ **`Δ motor = 0` confirmado por CI**. **`GitHub Release` [`v2.88.58-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.58-beta) publicado** (pre-release). Ningún tag contiene su propio resultado de CI — límite estructural declarado, como en `v2.88.46`…`v2.88.57`.
