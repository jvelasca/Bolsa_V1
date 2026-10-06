# Evidencia `v2.88.62-beta` — `AUTO · UI`: **AUTO UI REFACTOR 3.0 — USER-FIRST COCKPIT**

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.62-beta` · **Package:** `2.11.62-beta` · **AsOf:** 2026-10-06 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 3.0`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-feedback-v2`, `dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK).

**Padre:** [`v2.88.61`](../v2.88.61/README.md) → [`v2.88.60`](../v2.88.60/README.md) → [`v2.88.59`](../v2.88.59/README.md).

**Decisión de alcance (declarada).** Se ejecuta el plan **AUTO UI REFACTOR 3.0 (S0–S4) como una ventana continua** y se sella **una vez** (`v2.88.62-beta`), siguiendo el precedente del repo de **absorber fases planificadas en un único sello** (`v2.88.61` absorbió la F5 de `v2.88.60`). Los números `v2.88.63`/`64`/`65` del plan **no se emiten**; su contenido viaja dentro de este árbol. **No** toca motor, contrato HTTP, migraciones ni el pipeline `DÍA-D`. Refactor **aditivo**: `/auto-monitor` y todas las pantallas existentes se conservan.

---

## 0. Qué añade este sello (y qué NO)

**Añade**, sin tocar el motor, la última milla de producto del espacio AUTO:

1. **Spec 3.0 congelada** (`spec-auto-ui-refactor-3-0-2026-10-06.md`) + **addendum ADR-044 §7** (HOME como landing de `/auto`): tres niveles de lenguaje, dos niveles de densidad, reagrupación de la historia y tabla de falsabilidad.
2. **S1 — HOME / cockpit** (`/auto` deja de redirigir a Operar): `AutoHomePage` + helper puro `auto-home-summary.ts`, entrada **HOME** en `auto-nav.ts` (`Resumen`, primera), estados propios (carga/error/vacío/no-medido) y las cuatro preguntas en 5 s.
3. **S2 — Operación única 3.0**: `EXPLANATION` deja de pertenecer a `group: "OPERATION"` (nuevo grupo `EXPLANATION`, read-model puro en `@bolsa/shared`); el panel se reorganiza en **HISTORIA / CONTEXTO / ¿QUÉ APRENDEMOS?** y el primer nivel usa lenguaje humano (`NO MEDIDO` → «Sin dato todavía», término técnico conservado en `title`).
4. **S3 — Dos niveles de densidad/lenguaje**: `auto-typography.ts` + `AutoTechnicalDetail` (bloque plegable «Detalle técnico»); **SISTEMA** invierte la jerarquía (estado en frases arriba, monitor bajo demanda); **RIESGO** gana una cabecera plana honesta (`buildAutoRiskSummary`, «Sin dato todavía» para lo no materializado); **CARTERA** declara DEMO antes de las acciones; **ANÁLISIS** reetiqueta las 4 pestañas como preguntas (misma URL `?tab=`).
5. **S4 — Certificación `axe`** (`gp-e2e-v28865-auto-axe-mock.spec.ts`): barrido real sobre las 8 rutas de `/auto/*` + `/auto-monitor`, teclado de las pestañas, responsive y estados, con **0 violaciones `critical`/`serious`**. Cierra **`F-A2`**.

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** re-mide `DÍA-D`. **NO** implementa `PortfolioDecision` (`UI52-02`) ni el contrato de explicación por `cycleId` (heredado de `v2.88.60`).

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **HOME responde las 4 preguntas en 5 s** sin entrar en Sistema. | Que una de las preguntas exija navegar a otra sección para responderse. | `auto-home-page.test.tsx`; `gp-e2e-v28865` (`/auto`). |
| **2** | **`/auto` monta la HOME** (no redirige a Operar). | Que `/auto` siga redirigiendo a `/auto/operar`. | `app.tsx`; `auto-nav.test.ts`; `gp-e2e-v28856`. |
| **3** | **`EXPLANATION` no se pinta dentro de los hechos.** | Que una etapa `group === "OPERATION"` sea `EXPLANATION`. | `auto-operation-story.test.ts`; `auto-operation-story-panel.test.tsx` (`data-group="EXPLANATION"`). |
| **4** | **El primer nivel no muestra jerga** (`cycleId`/`TOP_N`/`Fill`/`SETTLEMENT`/`venue`/`PAPER_D_EXECUTE`). | Que aparezcan sin traducir en primer nivel. | `auto-story-plain-labels.test.ts`; HOME/RIESGO/SISTEMA. |
| **5** | **RIESGO no inventa cifras.** | Que la cabecera muestre un número sin medición o rellene un hueco con `0`. | `auto-risk-summary.test.ts`; `auto-riesgo-page.test.tsx`. |
| **6** | **CARTERA declara DEMO antes de las acciones.** | Que `OperationsPanel` se monte sin el aviso DEMO por encima. | `auto-cartera-page.test.tsx` (orden DOM). |
| **7** | **Estados distintos** (carga ≠ error ≠ vacío ≠ no-medido). | Que el error se pinte como vacío o al revés. | `auto-home-page.test.tsx`; `gp-e2e-v28865` (carga/error/vacío). |
| **8** | **`/auto/*` con 0 violaciones `axe` `critical`/`serious`.** | Cualquier violación crítica/seria en las 8 rutas. | `gp-e2e-v28865` (13/13). |
| **9** | **`Δ motor = 0`.** Ningún fichero de motor, umbral o contrato. | Que el diff toque motor/umbrales, o que `contract:check` no coincida. | §2 (`contract:check OK`, huella `replay-repro` en CI de tag). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.62-beta`) |
| `@bolsa/shared` `vitest` | **813 passed** | 1 todo (`97` ficheros) |
| `@bolsa/shared` `build` (`tsc`) | limpio |
| `@bolsa/web` `vitest` | **1475 passed** (`255` ficheros; **+19** sobre `v2.88.61`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `eslint src/` (ficheros tocados) | **0 errores** |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden con el commit |
| `pnpm window:test` | **25 passed / 0 failed** |
| `E2E_RUN=1 pnpm e2e -- gp-e2e-v28865` (**nuevo**, `axe`) | **13 passed** — 0 `critical`/`serious` en las 8 rutas + teclado + responsive + estados |
| `E2E_RUN=1 pnpm e2e -- gp-e2e-v28856` (actualizado a la HOME) | **3 passed** — un `<main>` y un `<h1>` por ruta |

**Cobertura del barrido `axe` (evidencia `F-A2`):** `/auto`, `/auto/operar`, `/auto/operar/operacion/e2e-cycle-aaa`, `/auto/cartera`, `/auto/riesgo`, `/auto/analisis`, `/auto/sistema`, `/auto-monitor?mode=current`; **móvil** `390×844` en `/auto` y `/auto/analisis`; **teclado** (flechas + `End` en la tablist de ANÁLISIS); **estados** carga / error / vacío / no-medido. Etiquetas `wcag2a`+`wcag2aa`+`wcag21a`+`wcag21aa`.

---

## 3. El refactor, en detalle

- **Contrato de navegación:** `auto-nav.ts` — `AUTO_NAV` (HOME + cinco secciones), `AUTO_HOME_PATH`, `autoSectionFromPathname("/auto") → home` (la HOME no participa del `startsWith` por sección para no absorber `/auto/<sección>`); `command-registry.ts` no duplica el comando raíz.
- **HOME:** `auto-home-page.tsx` + `auto-home-summary.ts` (puro): estado del motor traducido, `HH:mm` determinista, cierre afirmable (`closed === false` + `COMPLETE`) para contar «abiertas», integridad operativa → Normal/Atención/Bloqueado.
- **Historia:** `auto-operation-story.ts` (`AutoOperationStoryGroup` = `OPERATION | CONTEXT | EXPLANATION`); `auto-operation-story-panel.tsx` en tres bloques + `StoryStageRow` reutilizable; `auto-story-plain-labels.ts` gana `plainStateLabel`.
- **Densidad:** `auto-typography.ts` (≥14 px primer nivel · 10–12 px técnico) y `auto-technical-detail.tsx` (`<details>` «Detalle técnico», cerrado por defecto).
- **RIESGO:** `auto-risk-summary.ts` (puro) — estado/integridad/incidencias medidos; riesgo por posición, máxima pérdida y límite diario **declarados** «Sin dato todavía» (no materializados aquí).
- **SISTEMA:** `buildAutoHomeSummary` reutilizado para el primer nivel; monitor/recon/auditoría bajo el detalle plegable.
- **CARTERA:** aviso `role="note"` «CARTERA DEMO — posiciones simuladas» antes de `OperationsPanel`.
- **ANÁLISIS:** pestañas como preguntas con `id`/URL intactos (`tab=dia-d` sigue siendo el deep-link del heatmap).
- **Accesibilidad:** `@axe-core/playwright` (`^4.13.0`, nueva devDependency) + `gp-e2e-v28865-auto-axe-mock.spec.ts`.

---

## 4. Límites declarados (NO se cierran aquí)

- **`PortfolioDecision` durable (`UI52-02`)**: abierta (backend/spine). La HOME la **declara** «Sin dato todavía»; no la inventa.
- **Contrato de explicación por `cycleId`**: heredado de `v2.88.60`.
- **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): P3 abiertas.
- **`CONFIRMED` NO se emite.**
- **Re-anclaje del freeze de la ventana** (`scripts/lib/window-forward.mjs`) y **tag/Release**: **cerrados** en este sello (ver §6 y §7).
- **NO** se re-mide `DÍA-D`: las cifras OOS se **heredan y citan**.

---

## 5. Cómo se reproduce

```bash
# 1) Guard backend de versión (meta.bump == package.json).
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) UI.
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check
pnpm window:test

# 3) Certificación axe (arranca Vite; API mockeada, sin stack Python).
E2E_RUN=1 pnpm --filter @bolsa/web exec playwright test gp-e2e-v28865 gp-e2e-v28856
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se citan.

---

## 6. Sello

- **Añadidos:** `docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md`, `docs/engineering/evidence/v2.88.62/README.md`, `apps/web/src/features/auto/{auto-home-page.tsx,auto-home-summary.ts,auto-risk-summary.ts,auto-typography.ts,auto-technical-detail.tsx}` (+ tests), `apps/web/e2e/gp-e2e-v28865-auto-axe-mock.spec.ts`.
- **Modificados:** `apps/web/src/app.tsx`, `features/auto/auto-nav.ts`, `features/auto/{auto-sistema-page.tsx,auto-riesgo-page.tsx,auto-cartera-page.tsx,auto-analisis-page.tsx,auto-story-plain-labels.ts}`, `features/auto-monitor/auto-operation-story-panel.tsx`, `packages/shared/src/cognitive/auto-operation-story.ts`, `apps/web/e2e/{gp-e2e-v28856-…, fixtures}` (spec), `docs/adr/044-…md`, `apps/web/package.json` (+ `@axe-core/playwright`), `package.json` (`2.11.62-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`.
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el contrato HTTP no se mueve.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `9690971d` | `apps` `8ad1efc2…` / `packages` `bdcb1d34…` |
| Bump de versión (`chore(release)`) | `42085822` | `2.11.62-beta` (package + `meta.bump` `v2_89`…`v2_97`) |
| Re-anclaje del freeze de la ventana (`chore(window)`) | `3245a529` | pin → `42085822` |
| **Commit del tag** (`docs(seal)`) | `7b9cdc14` | — |

---

## 7. Cita del CI (POST-TAG)

**Tag anotado `v2.88.62-beta`** (objeto `96bb7476…`) → tip `docs(seal)` `7b9cdc14`. **`Release tag CI` run [`37433048176`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37433048176) VERDE** (`attempt 2`): `11` jobs `success` (`security`, `shared`, `spine`, `frontend`, `python`, `playwright-mock`, `lifecycle-pg`, `replay-repro`, `dr-verify`, `a7-gate`, y `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño.

- `python`: `4544 passed / 45 skipped` (`ruff` `All checks passed!`).
- `frontend`: `255` ficheros / **`1475 passed`**; `contract:check` `passed=true · critical=0 · warn=0`.
- `replay-repro`: **`VEREDICTO REPRODUCIDO`** — `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` ⇒ **`Δ motor = 0` confirmado por CI** (mismo digest en las dos corridas; sellado en CRLF, fichero en LF).
- `dr-verify`: la **batería DR** (`db:dr:test · TCP`) pasa; el `attempt 1` cayó por un **fallo de infraestructura del action** en el *post-run* de `actions/setup-node@v5` (`Path Validation Error … caching`, cache miss por el `pnpm-lock.yaml` nuevo — no ejecutable producto), **ajeno al sello**; el re-run (`attempt 2`) fue **VERDE**.
- **`GitHub Release` `v2.88.62-beta` publicado** (pre-release): <https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.62-beta>.
