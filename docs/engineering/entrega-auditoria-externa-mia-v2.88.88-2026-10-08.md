# Entrega a auditoría externa (MIA) — `v2.88.88-beta` · `UI`: **UI REFACTOR 5.0 — Global User-First** (contrato congelado `UI5-01`…`UI5-20` + implementación)

> **Fecha:** 2026-10-08 · **Producto:** `V2.88.88-beta` · **Package:** `2.11.88-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.87-beta` (tag anotado objeto `be7af907` → commit `6b70da1f`; `Release tag CI` [`37685922011`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37685922011) **VERDE**).
> **Unidad de esta auditoría:** la **coherencia entre superficies** y la **densidad de la primera capa** de toda la app (no dentro de AUTO). El diseño se congela en [`spec-ui-contract-5-0-2026-10-08.md`](./spec-ui-contract-5-0-2026-10-08.md) (`UI5-01`…`UI5-20`), se decide en [`ADR-045`](../adr/045-ui-contract-5-0.md) y se implementa en este sello; la deuda de origen está en [`auditoria-ui-global-v2.88.87-2026-10-08.md`](./auditoria-ui-global-v2.88.87-2026-10-08.md) (`G-01`…`G-13`).
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente o `UNKNOWN` se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde.
> **`Δ AUTO decision/execution motor = 0`.** Todo el slice es UI/read-model en `apps/web/**`: sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, **sin tocar `@bolsa/shared`** (el árbol de `packages/` no se mueve). **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.88/README.md`](./evidence/v2.88.88/README.md).
> **Cita POST-TAG:** `Release tag CI` [`37748285829`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37748285829) **VERDE** (`12` jobs = `11` `success` + `playwright` integrado `skipped`; `certify` `success`; `python` `4594 passed / 45 skipped`; `frontend` `268` ficheros / `1593 passed`; `shared` `817 passed / 1 todo`; `playwright (mock E2E)` `96 passed / 21 skipped`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0` confirmado por CI**). Tag anotado `v2.88.88-beta` (objeto `b47ecb2f` → commit `021afbb4`), **re-anclado** desde `a2da85a7` (ver §4, hallazgo `H-1`).

**Sello dirigido (declarado).** Mandato: **una sola aplicación, un único lenguaje operativo**. La decisión de diseño es **no** añadir funciones nuevas y **no** tocar el motor: se re-corta la superficie ya existente (primera capa más fina, gramática única de operación, jerarquía de navegación explícita) y se hace **falsable** cada afirmación con un test. Se acepta como coste declarado que dos reglas del diagrama `UI5-08` quedan **parcialmente** implementadas (§4).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el contrato `UI5-01`…`UI5-20` implementado sobre UI/read-model:

1. **HOME de AUTO sin duplicidades (`UI5-04`).** Se retiran la fila de tiles y el bloque «¿Qué está haciendo AUTO?» (repetían el estado y la lista de operaciones); el reloj de decisión se funde en la pregunta «¿Qué está haciendo?» y el contador «N en curso» pasa junto a las operaciones. Orden: estado → oportunidades → operación → dinero → enlaces. **Cada hecho se pinta una sola vez.**
2. **Escalera universal de operación (`UI5-09`/`UI5-11`/`UI5-20`).** Nuevo [`auto-operation-ladder.ts`](../../apps/web/src/features/auto/auto-operation-ladder.ts): `Orden preparada → Orden enviada → Esperando ejecución → Ejecución parcial → Ejecución completada → Posición creada → Posición cerrada`, con sus **no-equivalencias**. Sin traza de *apply*, AUTO **nunca** rotula «Posición creada`: `Precio aplicado ≠ posición creada`.
3. **Insignia de modo por operación (`UI5-10`).** Nuevo [`mode-badge.tsx`](../../apps/web/src/components/mode-badge.tsx) + [`operation-mode.ts`](../../apps/web/src/features/operations/operation-mode.ts): derivación por **evidencia** (`HUMAN_MANUAL`, prefijo `manual-`) o por superficie, **fail-closed** (sin evidencia no se afirma un modo humano).
4. **Sub-navegación de AUTO revelada por niveles (`UI5-03`).** Cuatro puertas visibles (`Resumen · Operar · Cartera · Actividad`) y `Riesgo · Análisis · Sistema` bajo un disclosure «Más información». **Las rutas no cambian**; el disclosure se abre solo si la ruta activa es secundaria.
5. **`AdminRail` agrupada (`UI5-08`).** Tres bloques (`Producto` · `Administración` · `Diagnóstico`) con encabezados ocultos en modo colapsado; `AUTO` vive en `Administración`, como fija el diagrama §1.3.
6. **Cartera como vista de la misma cuenta (`UI5-13`).** El banner y el copy declaran «vista simulada de la misma cuenta» con enlace a Cartera; `CARTERA_POSICIONES_HINT` deja de decir «posiciones abiertas».
7. **Riesgo human-first (`UI5-18`).** Veredicto `Controlado`/`Atención`/`Bloqueado`/`Sin dato todavía` como primer bloque de `/auto/riesgo`.
8. **Acción ≠ Navegación ≠ Información (`UI5-17`).** En las superficies tocadas, navegar es enlace subrayado; el botón queda para acciones reales.
9. **TOP3 en tres niveles y copy (`UI5-05`/`UI5-06`/`UI5-16`).** El TOP3 deja de colgar de «¿Qué puedo hacer?»; `compact` en HOME, completo en Operar; copy «Las 3 oportunidades que AUTO ha situado en los primeros puestos de su último análisis.»
10. **Hoy vs AUTO (`UI5-07`).** Se explica que el TOP3 es el **subconjunto** que AUTO usa y se enlaza al universo completo, con la nota `Ranking ≠ decisión`.

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`, confirmado por `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`; `contract:check` `critical=0 · warn=0`).
- **NO** se toca `packages/**` (el árbol de `packages/` es idéntico antes y después del slice).
- **NO** se implementa el canal `LIVE` real: el canal se declara `SIMULADO`.
- **NO** se ejecuta el `playwright` **integrado** (E2E contra stack real): sigue `opt-in` y quedó `skipped`. La certificación `axe` de este sello es **con mocks**, no en vivo.
- **NO** se cierran las deudas estructurales de la serie: `PortfolioDecision` durable, traza de materialización SIM, PIT histórico institucional y Execution Analysis.
- **NO** se re-mide el motor: las cifras de la serie se **heredan y citan**.

---

## 2. Cambios verificables (todo con gate)

| Regla | Hallazgo | Fichero(s) | Qué hace |
| --- | --- | --- | --- |
| `UI5-04` | `G-01` | `auto-home-page.tsx` (+ `.test.tsx`) | Cockpit sin duplicidades: fuera tiles y bloque «¿Qué está haciendo AUTO?»; reloj fundido en la pregunta; contador junto a operaciones. |
| `UI5-05` | `G-12` | `auto-home-page.tsx` | El TOP3 deja de colgar de «¿Qué puedo hacer?»; pasa a **Oportunidades**. |
| `UI5-06` | `G-05` | `auto-top3-panel.tsx` (+ `use-auto-top3-opportunities.ts`) | Nueva prop `compact`: resumen en HOME (`auto-home-top3`), completo en Operar (`auto-operar-top3`). |
| `UI5-07` | `G-06` | `auto-operar-page.tsx` | Copy «universo completo / subconjunto que AUTO usa» + enlace cruzado a `Hoy → Oportunidades`; nota `Ranking ≠ decisión`. |
| `UI5-09` | `G-02` | `auto-operation-ladder.ts` (+ `.test.ts`) | Escalera canónica + mapeo desde el ciclo (`operationLadderRungFromCycle`) + no-equivalencias. |
| `UI5-10` | `G-03` | `components/mode-badge.tsx` (+ `.test.tsx`), `features/operations/operation-mode.ts` (+ `.test.ts`) | Insignia `AUTO`/`SEMI`/`MANUAL` · `SIMULADO`; derivación fail-closed por evidencia. |
| `UI5-11` | `G-02` | `auto-operation-sheet.ts`/`-view.tsx`, `auto-operar-page.tsx` | La escalera se detiene en ejecución sin traza de apply: nunca «Posición creada». |
| `UI5-03` | `G-04` | `auto-nav.ts` (+ `.test.ts`), `components/layout/auto-workspace-layout.tsx` (+ `.test.tsx`) | `tier` primaria/secundaria; 4 puertas + disclosure «Más información»; rutas intactas. |
| `UI5-08` | `G-09` | `components/layout/admin-rail.tsx` (+ `admin-rail-items.test.tsx`) | Tres grupos; encabezados ocultos en colapsado; `AUTO` en `Administración`; testids y chincheta intactos. |
| `UI5-13` | `G-11`, `G-13` | `auto-copy.ts`, `auto-cartera-page.tsx`, `features/confirm/daily-nav.ts` | Cartera = vista simulada de la misma cuenta; se retira «posiciones abiertas». |
| `UI5-16` | `G-10` | `auto-top3-panel.tsx` | Copy del TOP3 explícito. |
| `UI5-17` | `G-08` | superficies tocadas | Navegar = enlace subrayado; botón = acción real. |
| `UI5-18` | `G-07` | `auto-risk-summary.ts` (+ `.test.ts`), `auto-riesgo-page.tsx` (+ `.test.tsx`) | `verdict`/`verdictTone`/`verdictSentence`; veredicto como primer bloque. |
| `UI5-20` | `G-02` | `auto-operation-ladder.ts`, `auto-pages.test.tsx` | Gramática única aplicada de forma transversal. |
| Contrato | — | `docs/engineering/spec-ui-contract-5-0-2026-10-08.md`, `docs/adr/045-ui-contract-5-0.md`, `docs/domain-language.md` §4.2 | Regla congelada, decisión y vocabulario. |
| Bump | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.88-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio. `replay-repro` **`REPRODUCIDO`** en CI (`sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`, `3340728` bytes; 2ª corrida IDÉNTICA) ⇒ **`Δ motor = 0`**.
- **Frontend local:** `typecheck` **OK**; `lint` **0 errores** (`23` avisos `react-hooks/exhaustive-deps` preexistentes); `268` ficheros / **`1593` tests verdes**.
- **Frontend en CI:** `268` ficheros / `1593 passed`; `shared` `817 passed / 1 todo`; `contract:check` `critical=0 · warn=0`.
- **E2E `axe` (mocks):** `gp-e2e-v28865` **`14/14`** — **0 violaciones `critical`/`serious`** en las 8 rutas AUTO (`/auto`, `/auto/operar`, `/auto/operar/operacion/:cycleId`, `/auto/cartera`, `/auto/riesgo`, `/auto/analisis`, `/auto/sistema`, `/auto-monitor?mode=current`), teclado de las pestañas de ANÁLISIS, teclado/ratón de la `AdminRail` **expandida**, responsive 390×844 y estados carga/error/vacío-no-medido.
- **E2E de navegación (mocks):** `gp-e2e-v28856` + `gp-e2e-v28857` **`6/6`** — `<main>`/`h1` únicos por ruta con la sub-navegación nueva y deep-links de operación.
- **Batería `playwright (mock E2E)` en CI:** `96 passed / 21 skipped`.
- **Python en CI:** `4594 passed / 45 skipped`; `lifecycle-pg` (Golden Day 2.0 + Crash/Recovery + Concurrent AUTO + HardKill + crash injection + multiprocess AUTO) `success`.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`H-1` — el CI del primer tag cayó y el tag se re-ancló (cerrado, se declara).** El `Release tag CI` [`37741490506`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37741490506) del tag inicial (`a2da85a7`) cayó en `playwright (mock E2E)`: el propio `gp-e2e-v28865` detectó **`color-contrast [serious] ×3`** en las 8 rutas AUTO. Nodos: los **rótulos de grupo** de la `AdminRail` (`UI5-08`) con `text-muted-foreground/70` → `#67727f` sobre `#121821` = **3.64:1** (AA exige `4.5:1` a 10 px / peso normal). El paso **local no lo vio** porque la rail estaba colapsada y `axe` no evalúa rótulos ocultos: la certificación quedaba a merced del estado de *hover*. **Remediación aplicada:** se corrige el **color** (no se oculta el defecto) a `text-muted-foreground` (**6.81:1** en oscuro, **4.76:1** en claro) y se añade un test que **ancla la rail expandida** y barre `axe` ahí (antes del arreglo ese test falla; después, verde). Commit `909ae711`; tag re-anclado a `021afbb4`. **Lección declarada:** un `axe` que depende de un estado ganado por *hover* no certifica; la certificación debe anclar el estado.
- **`UI5-08b` — el bloque `Producto` del rail no son los atajos L1 del diagrama.** El diagrama §1.3 de la spec lista `Producto` como `Hoy · Mercado · Cartera · Asesor · Laboratorio`; en el rail, `Producto` contiene **solo `Overview`** (los atajos L1 viven en la barra superior, no en el rail) y el resto de items quedan en `Administración`/`Diagnóstico`. **Remediación:** decidir si el rail duplica la L1 o si el diagrama §1.3 se corrige (reducir `Producto` a `Overview`); no se añaden rutas nuevas para «cumplir» un diagrama.
- **`heading-order` (best-practice) en 11 rutas L1** — abierto desde `v2.88.54`; preexistente y fuera del alcance de este sello.
- **`F-A2` — barrido `axe` en vivo.** El sello certifica `/auto/*` **con mocks**; la variante **en vivo** (stack real, `playwright` integrado) sigue `opt-in` y `skipped`. **Remediación:** activar el `playwright` integrado en el `Release tag CI`.
- **`UI52-02` — `PortfolioDecision` durable**; **traza de materialización SIM**; **PIT histórico institucional** y **Execution Analysis**: abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este slice.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `pnpm --filter @bolsa/web typecheck` | **OK** |
| `pnpm --filter @bolsa/web lint` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web test` | **268 ficheros / 1593 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.88-beta`) |
| `E2E_RUN=1 pnpm e2e -- gp-e2e-v28865` | **14/14** (0 `critical`/`serious`) |
| `E2E_RUN=1 pnpm e2e -- gp-e2e-v28856 gp-e2e-v28857` | **6/6** |
| `python` (ruff / import-linter / mypy / pytest) — CI | **`4594 passed / 45 skipped`** |
| `frontend` (typecheck/lint/test/build + `contract:check`) — CI | **`1593 passed`**; `critical=0 · warn=0` |
| `shared` (build/typecheck/test + `pnpm window:test`) — CI | **`817 passed / 1 todo`** |
| `lifecycle-pg` (Alembic + auth + Golden Day 2.0 + crash/concurrency/multiprocess) — CI | **`success`** |
| `replay-repro` — CI | **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`** |

---

## 6. Sello

- **Producto:** `V2.88.88-beta`. **Package:** `2.11.88-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/` **sin mover**.
- **Añadidos:** `apps/web/src/components/mode-badge.tsx` (+ `.test.tsx`), `apps/web/src/features/operations/operation-mode.ts` (+ `.test.ts`), `apps/web/src/features/auto/auto-operation-ladder.ts` (+ `.test.ts`), `docs/adr/045-ui-contract-5-0.md`, `docs/engineering/spec-ui-contract-5-0-2026-10-08.md`, `docs/engineering/auditoria-ui-global-v2.88.87-2026-10-08.md`, `docs/engineering/evidence/v2.88.88/README.md`, este documento.
- **Modificados:** `apps/web/**` (AUTO + layout + trading + confirm), `apps/web/e2e/gp-e2e-v28865-auto-axe-mock.spec.ts`, `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/domain-language.md`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| Funcional (`feat(ui)`) | `fb7b5212` | `apps` `0608382c…` / `packages` `49f70ff5…` |
| Bump de versión (`chore(seal)`) | `a2da85a7` | `apps` `24d028d9…` / `packages` `49f70ff5…` |
| Corrección de contraste (`fix(ui)`) | `909ae711` | `apps` `6710c8f3…` / `packages` `49f70ff5…` |
| **Commit del sello (`chore(seal)`, re-anclaje)** | **`021afbb4`** | `apps` `6710c8f3…` / `packages` `49f70ff5…` |
| Cita POST-TAG (`docs(seal)`, tip) | `7f26ae5f` | `apps` `6710c8f3…` / `packages` `49f70ff5…` |
| Tag anotado `v2.88.88-beta` | objeto `b47ecb2f` → **`021afbb4`** | `Release tag CI` [`37748285829`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37748285829) **VERDE** (`replay-repro` `REPRODUCIDO` ⇒ `Δ motor = 0`) |

- **Re-anclaje:** el tag se movió de `a2da85a7` a `021afbb4` tras corregir `H-1` (§4). El run rojo queda citado a propósito: el auditor puede leer la causa y el arreglo.
- **`scripts/` no participa del pin** de la ventana (`scripts/lib/window-forward.mjs` **no se toca** en este sello; `pnpm window:test` verde en CI).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.88/README.md` en el árbol del commit del sello (`021afbb4`).
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Contrato.** Leer `docs/engineering/spec-ui-contract-5-0-2026-10-08.md` (reglas `UI5-01`…`UI5-20`) y `docs/adr/045-ui-contract-5-0.md` (decisión). La deuda de origen: `docs/engineering/auditoria-ui-global-v2.88.87-2026-10-08.md` (`G-01`…`G-13`).
4. **Base.** `docs/engineering/evidence/v2.88.87/README.md` y `…/v2.88.86/…`.
5. **`Δ motor = 0`.** Verificar que el diff del slice **no toca** motor, worker, umbrales, Alembic ni `contract:gen`, y que `packages/` **no se mueve**:
   ```bash
   git diff --name-only fb7b5212^ 7f26ae5f -- packages/   # vacío
   git rev-parse fb7b5212:packages 7f26ae5f:packages      # iguales (49f70ff5…)
   ```
6. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web typecheck
   pnpm --filter @bolsa/web lint
   pnpm --filter @bolsa/web test
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28865 gp-e2e-v28856 gp-e2e-v28857
   ```
7. **Falsabilidad de la gramática.** Comprobar en `auto-operation-ladder.ts` que sin traza de *apply* **no** existe el peldaño «Posición creada», y en `operation-mode.ts` que sin evidencia `HUMAN_MANUAL` **no** se afirma un modo humano (fail-closed).
8. **Falsabilidad del contraste (`H-1`).** Confirmar en `admin-rail.tsx` que los rótulos de grupo usan `text-muted-foreground` (sin modificador de opacidad), y que `gp-e2e-v28865` ancla la rail **expandida** antes de barrer `axe`.
9. **Qué falsaría el sello:** que un dato ausente se pinte `0` o en verde · que la escalera salte a «Posición creada» sin traza · que la insignia de modo afirme `MANUAL` sin evidencia · que la sub-navegación pierda o renombre una ruta · que `AdminRail` vuelva a ser una lista plana · que el diff toque motor/contrato/migraciones o mueva `packages/` · que `replay-repro` no reproduzca `1E3ADAC2…`.
