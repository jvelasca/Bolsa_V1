# Evidencia `v2.88.57-beta` — `AUTO · UI`: **AUTO UI REFACTOR 2.1.1** (integridad del deep-link de operación)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.57-beta` · **Package:** `2.11.57-beta` · **AsOf:** 2026-10-05 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 2.1.1`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK).

**Padre:** [`v2.88.56`](../v2.88.56/README.md) (tag → `54a3a7f2`, `Release tag CI` [`37339483917`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37339483917) VERDE) → [`v2.88.55`](../v2.88.55/README.md).

**Decisión de alcance (declarada).** Mandato explícito: **«Corregir el deep-link inválido de la operación AUTO (P2 de integridad)»**. El sello cierra el único defecto relevante de la auditoría externa de `v2.88.56`: un `cycleId` explícito (ruta canónica `/auto/operar/operacion/:cycleId` o `?cycle=` en `/auto-monitor?mode=operation`) que **no existe** en la ventana caía silenciosamente a `cycles[0]`, mostrando el encabezado del id pedido con la historia de **otra** operación. Refactor **quirúrgico**: **NO** toca motor, contrato HTTP, migraciones ni el pipeline `DÍA-D`.

---

## 0. Qué añade este sello (y qué NO)

**Añade** la integridad de deep-link del espacio AUTO, sin motor:

1. **Resolución explícita y pura.** `resolveAutoOperationSelection` (helper exportado en `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx`) distingue «sin selección» de «selección no resuelta»: `notFound = id explícito ∧ datos cargados ∧ sin coincidencia`. Durante la carga NO declara ausencia (evita un falso negativo); sin id explícito se conserva el fallback histórico a `cycles[0]`.
2. **Estado «Operación no encontrada».** `data-testid="auto-operation-story-not-found"` + `data-cycle-id`; **no** se pinta el `<ol>` de la operación ni el bloque de contexto, ni el botón «Detalle técnico» sin ciclo.
3. **Selector como recuperación.** El selector de ciclos permanece (ningún botón `aria-pressed`), de modo que un deep-link inválido no deja al operador sin salida.
4. **Tests.** `auto-operation-story-panel.test.tsx` (ruta y `?cycle=` inválidos + helper), `auto-pages.test.tsx` (h1 con el id pedido, sin inventar otro ciclo) y E2E mock `gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts` (ruta inválida, `?cycle=` inválido y ruta válida de regresión).

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** re-mide `DÍA-D`. **NO** cierra `PortfolioDecision` (`UI52-02`) ni el contrato de explicación `cycle_id`-resolutiva.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | Un `cycleId` de ruta inexistente **no** muestra otra operación. | Que vuelva a seleccionar `cycles[0]` o pinte etapas cuando no hay coincidencia. | §3; `auto-operation-story-panel.test.tsx`; E2E `gp-e2e-v28857`. |
| **2** | Un `?cycle=` explícito inexistente se comporta igual. | Que el monitor caiga a `cycles[0]`. | §3; E2E `gp-e2e-v28857`. |
| **3** | La ruta válida sigue mostrando la operación seleccionada. | Que `notFound` se dispare con un id válido o durante la carga. | §3; `resolveAutoOperationSelection` (caso `hasLoaded:false`); E2E. |
| **4** | El deep-link inválido no anuncia un destino técnico sin ciclo. | Que el botón «Detalle técnico» siga visible sin ciclo seleccionado. | §3; `auto-operation-story-panel.test.tsx`. |
| **5** | `Δ motor = 0`. | Que el diff toque motor/umbrales, o que `contract:check` no coincida. | §2 (`contract:check OK`). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.57-beta`) |
| `@bolsa/web` `vitest` | **1412 passed** (`245` ficheros; **+10** sobre `v2.88.56`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| `E2E_RUN=1 pnpm e2e -- gp-e2e-v28856 gp-e2e-v28857` | **6 passed** (mock, sin API) |

> **Nota de método (declarada).** El barrido `axe` en **navegador real** de `v2.88.54` **no** se re-ejecuta (requiere app + API + auth y `axe-core` inyectado). El estado «no encontrada» se cubre por test unitario y por el E2E de deep-link. **Hueco declarado**, no silenciado.

---

## 3. La corrección, en detalle

- **Helper puro:** `resolveAutoOperationSelection({ cycles, overrideCycleId, queryCycleId, hasLoaded })` → `{ requestedCycleId, selectedCycle, notFound }`. `requestedCycleId = override.trim() || query.trim() || null`; `notFound = requestedCycleId !== null ∧ hasLoaded ∧ sin coincidencia`; `selectedCycle = notFound ? null : (coincidencia ?? cycles[0] ?? null)`.
- **Panel:** `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` — `hasLoaded = !isLoading && !isError && view != null`; render condicional de `<ol>`/contexto/botón técnico; bloque `auto-operation-story-not-found`.
- **Página:** `apps/web/src/features/auto/auto-operacion-page.tsx` — el `h1` mantiene el id pedido (`cycle?.instrumentId ?? cycleId`); el estado de ausencia vive en el panel.
- **Tests:** `auto-operation-story-panel.test.tsx` (2 de UI + 7 del helper), `auto-pages.test.tsx` (1), E2E `gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts` (3).
- **Bump:** `package.json` (`2.11.57-beta`) + `meta.bump` de `apps/api-python/scripts/v2_89…v2_97`.
- **Re-anclaje del freeze:** `scripts/lib/window-forward.mjs` → pin `commit: 287a15b5`, `appsHash: 0556be2f…` (`packages` sin cambio: `95cb0d69…`).

---

## 4. Límites declarados (NO se cierran aquí)

- **`PortfolioDecision` durable (`UI52-02`)**: sigue abierta (backend/spine).
- **Contrato de explicación DÍA-D verdaderamente `cycle_id`-resolutivo**: la resolución sigue siendo por `symbol`; fuera de este slice.
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

# 3) E2E de navegación e integridad de deep-link AUTO (mock, sin API).
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28857
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `apps/web/e2e/gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts`, `docs/engineering/spec-auto-ui-refactor-2-1-1-2026-10-05.md`, `docs/engineering/evidence/v2.88.57/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.57-2026-10-05.md`.
- **Modificados:** `apps/web/src/features/auto-monitor/{auto-operation-story-panel.tsx, auto-operation-story-panel.test.tsx}`, `apps/web/src/features/auto/auto-pages.test.tsx`, `package.json` (`2.11.57-beta`), `v2_89`…`v2_97` (`meta.bump`), `docs/engineering/spec-auto-ui-refactor-2-1-2026-10-05.md` (addendum §6), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el contrato HTTP no se mueve.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `287a15b5` | `apps` `0556be2f…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `a30acb07` | pin `commit: 287a15b5` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | `d44e00c9` (tag anotado `8af24105`) | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia §7) | `91cf61e1`… _(posterior)_ | — |

---

## 7. Cita del CI (POST-TAG)

> **`Release tag CI`** del tag `v2.88.57-beta`: run [`37344802844`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37344802844) **VERDE** (`attempt 1`, `16:57:35Z → 17:05:40Z`; `10` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `security`/`shared`/`decision-spine`/`frontend` (typecheck/lint/test/build + `contract:check`)/`python`/`playwright-mock`/`lifecycle-pg`/`dr-verify`/`a7-gate` `success`; `replay-repro` `success` **`REPRODUCIDO`** `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` = sello ⇒ **`Δ motor = 0` confirmado por CI**; `lifecycle-pg` certifica Golden Day 2.0, Crash/Recovery, Concurrent AUTO, HardKill, crash-injection y multiprocess con gate fail-if-skipped). `frontend` `vitest` **1412 passed** (`245` ficheros). **`GitHub Release` [`v2.88.57-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.57-beta) publicado** (pre-release). Ningún tag contiene su propio resultado de CI — límite estructural declarado, como en `v2.88.46`…`v2.88.56`.
