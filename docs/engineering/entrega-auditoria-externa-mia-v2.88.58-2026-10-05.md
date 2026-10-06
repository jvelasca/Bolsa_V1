# Entrega a auditoría externa (MIA) — `v2.88.58-beta` · `AUTO · UI`: **AUTO COCKPIT 1.0**

> **Fecha:** 2026-10-05 · **Producto:** `V2.88.58-beta` · **Package:** `2.11.58-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.57-beta` (tag → `d44e00c9`, `Release tag CI` [`37344802844`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37344802844) **VERDE**).
> **Unidad de esta auditoría:** el **cockpit AUTO para usuario básico** (hallazgos de la audit. [`auditoria-ui-auto-cockpit-2026-10-05.md`](./auditoria-ui-auto-cockpit-2026-10-05.md), F1–F4). **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve (`contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.58/README.md`](./evidence/v2.88.58/README.md) (`§0`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.57`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** Mandato: **«convertir AUTO en un cockpit legible para un usuario básico»**. El sello **no** añade funcionalidad de motor: es un refactor de **UI/read-model** (F1–F4) con `Δ motor = 0`.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el cockpit AUTO 1.0, todo **sin tocar el motor**:

1. **F1 — Semáforo de realidad monetaria (P1 `F-R1`):** AUTO declara en primer nivel `DINERO VIRTUAL · AUTO DEMO`, el tipo de cuenta y el capital (`NO MEDIDO` si ausente); **fail-closed** a virtual salvo cuenta `live`.
2. **F2 — Identidad legible de operación (P1 `F-O1`):** la lista de OPERAR distingue ciclos por `AAPL · 03 oct · Largo · Abierto` (día/dirección/estado), no por `instrumentId`/`cycleId`.
3. **F3 — Cockpit OPERAR (P2 `F-O3`):** Oportunidades (lanzadera) y Operaciones (identidad + enlace), con estados **error ≠ vacío ≠ carga ≠ no medido**.
4. **F4 — Lenguaje plano y accesibilidad (P1 `F-J1`; P2 `F-J2`/`F-DUP1`/`F-A1`):** copy sin jerga, etiquetas de etapa traducidas, reconciliación **no** duplicada en `/auto/riesgo` y tablist WAI-ARIA completo en DÍA-D.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se cierra **`PortfolioDecision`** (`UI52-02`), la **explicación DÍA-D `cycleId`-resolutiva** (`F-S1`), el **barrido `axe` en vivo** (`F-A2`), el **PIT histórico institucional** ni **Execution Analysis**.
- **NO** se emite `CONFIRMED`.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Semáforo de realidad (F1) | `features/auto/auto-reality.ts`, `auto-reality-strip.tsx`, `components/layout/auto-workspace-layout.tsx` | Helper puro fail-closed (`live` vs `virtual`) + franja montada sobre el `<Outlet />` del shell; capital `NO MEDIDO` si ausente. |
| Identidad de operación (F2) | `features/auto/auto-operation-identity.ts` | `buildOperationIdentity` → `AAPL · 03 oct · Largo · Abierto`; campos ausentes → `NO MEDIDO`. |
| Cockpit OPERAR (F3) | `features/auto/auto-operar-page.tsx` | Bloques Oportunidades/Operaciones; estados error/vacío/carga/`NO MEDIDO` distinguibles. |
| Lenguaje plano (F4) | `features/auto/auto-copy.ts`, `features/auto/auto-story-plain-labels.ts` | Copy de las cinco secciones sin jerga; etapas de la historia traducidas. |
| Sin duplicado (F4) | `features/auto/auto-riesgo-page.tsx` | Deja de re-montar la reconciliación (queda una sola vez dentro de AUTO). |
| Accesibilidad DÍA-D (F4) | `features/auto-monitor/dia-d-auto-panel.tsx` | Tablist WAI-ARIA completo (tab↔panel + flechas/Home/End), como ANÁLISIS. |
| Tests unit | `auto-reality.test.ts`, `auto-reality-strip.test.tsx`, `auto-operation-identity.test.ts`, `auto-story-plain-labels.test.ts`, `auto-pages.test.tsx`, `auto-workspace-layout.test.tsx`, `dia-d-auto-panel.test.tsx` | Cubren los seis afirmaciones falsables de `§1` (evidencia). |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.58-beta`) en `v2_89`…`v2_97`. |

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

- **`F-A2` — barrido `axe` en vivo de `/auto/*` no ejecutado.** El método de `v2.88.54` requiere app + API + auth y `axe-core` inyectado. Remediación: spec `axe` propio para `/auto/*` en el siguiente sello de UI.
- **`F-S1` — explicación DÍA-D `cycleId`-resolutiva:** la resolución sigue por `symbol`; requiere contrato de artefacto por `cycleId` (fase backend **F5**).
- **`F-S2`/`F-S3` (P3):** densidad tipográfica (`text-[11px]`) e `h1` crudo de ausencia.
- **`PortfolioDecision` durable (`UI52-02`)**, **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): abiertos (spine/backend).
- **`heading-order` fuera de AUTO (11 rutas, heredado de `v2.88.54`)**: deuda declarada.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): pre-existentes.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`2.11.58-beta`) |
| `@bolsa/web` `vitest` | **1435 passed** (`249` ficheros; +23 sobre `v2.88.57`) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`23` warnings pre-existentes) · **OK** |
| `pnpm window:test` | **25/25** |
| `E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857` | **6 passed** (mock, sin API; `workers=1` como CI) |

---

## 6. Sello

- **Producto:** `V2.88.58-beta`. **Package:** `2.11.58-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Añadidos:** `features/auto/{auto-reality,auto-reality.test,auto-reality-strip,auto-reality-strip.test,auto-operation-identity,auto-operation-identity.test,auto-story-plain-labels,auto-story-plain-labels.test,auto-copy}.ts(x)`, `components/layout/auto-workspace-layout.tsx` + `.test.tsx`, `docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md`, `docs/engineering/auditoria-ui-auto-cockpit-2026-10-05.md`, `docs/engineering/evidence/v2.88.58/README.md`, este documento.
- **Modificados:** `features/auto/auto-operar-page.tsx` + `auto-pages.test.tsx`, `features/auto/auto-riesgo-page.tsx`, `features/auto-monitor/dia-d-auto-panel.tsx` + `dia-d-auto-panel.test.tsx`, `package.json` (`2.11.58-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `dd3af96d` | `apps` `6f24ce28…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `7fc486d1` | pin `commit: dd3af96d` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | `e99c99c5` (tag anotado `v2.88.58-beta`) | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia `§7`) | _(este commit)_ | — |

- **Tag:** `v2.88.58-beta` (anotado sobre el commit del sello `e99c99c5`; funcional `dd3af96d` + `chore(window)` `7fc486d1` + `docs(seal)`) — `Release tag CI` [`37367672717`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37367672717) **VERDE** (`attempt 2`; `attempt 1` cayó por **infraestructura de GitHub** —`The job was not acquired by Runner of type hosted`— y el rerun `--failed` salió verde; jobs `success`: `security`/`python` (**`4538 passed / 45 skipped`**)/`a7-gate`/`decision-spine`/`shared`/`playwright (mock E2E)`/`lifecycle-pg`/`frontend` (**`Test Files 249 passed (249)`**)/`replay-repro`/`dr-verify`/`certify`; `playwright (integrated E2E)` `skipped` por diseño; **`replay-repro` `REPRODUCIDO`** `sha256 1E3ADAC2…` ⇒ **`Δ motor = 0` confirmado por CI**); **`GitHub Release` [`v2.88.58-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.58-beta) publicado** (pre-release). Dentro del tag, la evidencia lo declara como `POST-TAG`.

---

## 7. Guion de auditoría desde GitHub

Todo lo necesario para auditar este sello vive en **GitHub**, sin clon local:

1. **Tag → evidencia.** Ir al release `v2.88.58-beta` (o al árbol del tag) y abrir `docs/engineering/evidence/v2.88.58/README.md`. Es la evidencia autocontenida (`§0`–`§7`); dentro del tag, `§7` (cita CI) se declara **POST-TAG**.
2. **Entrega MIA.** Leer este documento (pack de auditoría): qué se entrega/NO, cambios verificables, medición heredada, hallazgos abiertos y gates.
3. **Diseño.** `docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md` (spec congelada F1–F4) + `docs/engineering/auditoria-ui-auto-cockpit-2026-10-05.md` (auditoría read-only): contienen el contrato y las afirmaciones falsables.
4. **CI del tag.** Abrir la pestaña **Actions** → `Release tag CI` del tag `v2.88.58-beta`. Comprobar `replay-repro` **REPRODUCIDO** (⇒ `Δ motor = 0`) y los jobs `python`, `frontend`, `shared`, `decision-spine`, `lifecycle-pg`, `security`, `certify` en **success**.
5. **Reproducción local (opcional).**
   ```bash
   git checkout v2.88.58-beta
   uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   pnpm --filter @bolsa/web test
   pnpm --filter @bolsa/web typecheck
   pnpm --filter @bolsa/web lint
   pnpm --filter @bolsa/web contract:check
   pnpm window:test
   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857
   ```
6. **Qué falsaría el sello:** que una cuenta no-`live` reclame dinero real · que el capital ausente se pinte como `0` · que la lista de OPERAR vuelva a mostrar sólo `instrumentId` · que un fallo de red se muestre como «Sin operaciones» · que el tablist DÍA-D omita el `tabpanel`/teclado · que `contract:check` no coincida · que el diff toque motor/umbrales · que `replay-repro` no reproduzca.
