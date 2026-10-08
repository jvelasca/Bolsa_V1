# Evidencia `v2.88.88-beta` — `UI`: **UI REFACTOR 5.0 — Global User-First (implementación)**

**Producto:** `V2.88.88-beta` · **Package:** `2.11.88-beta` · **AsOf:** 2026-10-08. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`** y **contrato HTTP sin cambio**: todo el slice es UI/read-model en `apps/web/**`. No se tocan las constantes semánticas de `@bolsa/shared` (`CYCLE_STATUS_*`). Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.88-beta` junto al `package.json`.

**Contrato implementado:** [`spec-ui-contract-5-0-2026-10-08.md`](../../spec-ui-contract-5-0-2026-10-08.md) (`UI5-01`…`UI5-20`).
**Deuda auditada:** [`auditoria-ui-global-v2.88.87-2026-10-08.md`](../../auditoria-ui-global-v2.88.87-2026-10-08.md) (`G-01`…`G-13`).
**Entrega a auditoría externa:** [`entrega-auditoria-externa-mia-v2.88.88-2026-10-08.md`](../../entrega-auditoria-externa-mia-v2.88.88-2026-10-08.md).

## Mapeo `UI5-n` → fichero

| Regla | Hallazgo | Implementación |
| --- | --- | --- |
| `UI5-04` HOME cockpit | `G-01` | [`auto-home-page.tsx`](../../../../apps/web/src/features/auto/auto-home-page.tsx): se retiran la fila de tiles y el bloque «¿Qué está haciendo AUTO?» (repetían estado y operaciones); el reloj de decisión se fusiona en la pregunta «¿Qué está haciendo?»; el contador «N en curso» pasa junto a las operaciones. Orden: estado → oportunidades → operación → dinero → enlaces. |
| `UI5-05` «¿Qué puedo hacer?» | `G-12` | El bloque del TOP3 deja de colgar de «¿Qué puedo hacer?» y pasa a **Oportunidades**. |
| `UI5-06` TOP3 en tres niveles | `G-05` | `AutoTop3Panel` gana `compact`: HOME monta el resumen (`auto-home-top3`), OPERAR la vista completa (`auto-operar-top3`). |
| `UI5-07` Hoy vs AUTO | `G-06` | [`auto-operar-page.tsx`](../../../../apps/web/src/features/auto/auto-operar-page.tsx): copy «universo completo / subconjunto que AUTO usa» + enlace cruzado a `Hoy → Oportunidades` (`mesaOportunidadesHref()`); nota `Ranking ≠ decisión`. |
| `UI5-09` escalera universal | `G-02` | Nuevo [`auto-operation-ladder.ts`](../../../../apps/web/src/features/auto/auto-operation-ladder.ts) (`OPERATION_LADDER`, `operationLadderRungFromCycle`). Aplicado en la ficha ([`auto-operation-sheet.ts`](../../../../apps/web/src/features/auto/auto-operation-sheet.ts)) y en las filas de Operar. |
| `UI5-10` insignia de modo | `G-03` | Nuevo [`mode-badge.tsx`](../../../../apps/web/src/components/mode-badge.tsx) + [`operation-mode.ts`](../../../../apps/web/src/features/operations/operation-mode.ts) (derivación por evidencia, fail-closed). Aplicado en la ficha y en [`operations-panel.tsx`](../../../../apps/web/src/features/trading/operations-panel.tsx). |
| `UI5-11` `precio aplicado ≠ posición creada` | `G-02` | La escalera se detiene en «Ejecución parcial/completada»: sin traza de apply **nunca** rotula «Posición creada»; la nota viaja con el peldaño. |
| `UI5-03` nav visible de AUTO | `G-04` | [`auto-nav.ts`](../../../../apps/web/src/features/auto/auto-nav.ts) añade `tier` y reordena (`Cartera` antes que `Actividad`); [`auto-workspace-layout.tsx`](../../../../apps/web/src/components/layout/auto-workspace-layout.tsx) pinta 4 puertas + disclosure `<details>` «Más información ▾» (se abre solo si la ruta activa es secundaria). Rutas intactas. |
| `UI5-08` AdminRail en tres grupos | `G-09` | [`admin-rail.tsx`](../../../../apps/web/src/components/layout/admin-rail.tsx) agrupa Producto · Administración · Diagnóstico (encabezados ocultos en colapsado). Testids y chincheta intactos. |
| `UI5-13` Cartera única | `G-11`, `G-13` | [`auto-copy.ts`](../../../../apps/web/src/features/auto/auto-copy.ts) y el banner de [`auto-cartera-page.tsx`](../../../../apps/web/src/features/auto/auto-cartera-page.tsx) declaran «vista simulada de la misma cuenta» + enlace a Cartera; `CARTERA_POSICIONES_HINT` deja de decir «posiciones abiertas». |
| `UI5-17` Acción ≠ Navegación | `G-08` | Las superficies tocadas usan enlace subrayado para navegar (`Ver operación →`, `Ver oportunidades en la Mesa`) y reservan el botón a acciones reales. |
| `UI5-18` Riesgo human-first | `G-07` | [`auto-risk-summary.ts`](../../../../apps/web/src/features/auto/auto-risk-summary.ts) añade `verdict`/`verdictTone`/`verdictSentence` (`Controlado`/`Atención`/`Bloqueado`/`Sin dato todavía`); [`auto-riesgo-page.tsx`](../../../../apps/web/src/features/auto/auto-riesgo-page.tsx) lo pinta como primer bloque. |
| `UI5-16` copy TOP3 | `G-10` | [`auto-top3-panel.tsx`](../../../../apps/web/src/features/auto/auto-top3-panel.tsx): «Las 3 oportunidades que AUTO ha situado en los primeros puestos de su último análisis.» |

## Invariantes de honestidad (no negociables)

- **`UNKNOWN ≠ 0`.** Sin lectura o con medición `UNKNOWN`/`PARTIAL`, el modo, el veredicto de riesgo y el peldaño se declaran «Sin dato todavía»; nunca un verde ni un `0`.
- **No re-derivar.** El modo se afirma por evidencia (`HUMAN_MANUAL`) o por superficie (espacio AUTO); la escalera copia los hechos del ciclo; el veredicto de riesgo agrupa estado/portafolio/incidencias.
- **`Ranking ≠ decisión`.** El TOP3 sigue declarándose propuesta; el copy explicita que estar arriba no es comprar.
- **`Precio aplicado ≠ posición creada`.** La escalera no materializa sin traza de apply.
- **`Δ motor = 0`.** Sin cambios en motor, worker, umbrales, Alembic ni `contract:gen`; sin tocar `@bolsa/shared`.

## Verificación (local)

- `pnpm --filter @bolsa/web typecheck` → **OK**.
- `pnpm --filter @bolsa/web lint` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes, ajenos a este slice).
- `pnpm --filter @bolsa/web test` → **268 ficheros / 1593 tests verdes**.
- Suites nuevas: `auto-operation-ladder.test.ts`, `operation-mode.test.ts`, `mode-badge.test.tsx`; ampliadas: `auto-nav.test.ts` (orden + tiers), `auto-workspace-layout.test.tsx` (disclosure), `auto-home-page.test.tsx` (cada hecho una sola vez), `auto-risk-summary.test.ts` y `auto-riesgo-page.test.tsx` (veredicto), `auto-pages.test.tsx` (modo + peldaño), `auto-operation-sheet.test.ts` (escalera + modo), `admin-rail-items.test.tsx` (tres grupos + `AUTO` en Administración).
- **Guardián de bump:** `test_dia_d_bump_guard` **verde** (los 9 CLIs `v2_89`…`v2_97` sellan `2.11.88-beta` junto al `package.json`).
- **E2E (Playwright, mocks, `E2E_RUN=1`):**
  - [`gp-e2e-v28865-auto-axe-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-v28865-auto-axe-mock.spec.ts) → **14/14 verde**: **0 violaciones `critical`/`serious`** en las 8 rutas AUTO (`/auto`, `/auto/operar`, `/auto/operar/operacion/:cycleId`, `/auto/cartera`, `/auto/riesgo`, `/auto/analisis`, `/auto/sistema`, `/auto-monitor`), teclado de las pestañas de ANÁLISIS, teclado/ratón de la `AdminRail` **expandida**, responsive 390×844 y estados carga/error/vacío-no-medido. El assert de «vacío/no-medido» pasa de `auto-home-tile-auto` a `auto-home-q-working` (el tile se retiró en `UI5-04`). **Re-certificación de las rutas tocadas: hecha.**
  - [`gp-e2e-v28856-auto-ui-navigation-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-v28856-auto-ui-navigation-mock.spec.ts) + [`gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts) → **6/6 verde** (main/h1 únicos por ruta con la sub-navegación nueva, detalle técnico y deep-links).

### Hallazgo del `Release tag CI` (run `37741490506`) — corregido antes del re-anclaje

El primer `Release tag CI` del tag cayó en `playwright (mock E2E)`: el propio `gp-e2e-v28865` detectó **`color-contrast [serious] ×3`** en las 8 rutas AUTO. Nodos: los **rótulos de grupo** de la `AdminRail` (`UI5-08`), que usaban `text-muted-foreground/70` → `#67727f` sobre `#121821` = **3.64:1** (WCAG AA exige `4.5:1` a 10 px / peso normal). El paso local no lo vio porque la rail estaba **colapsada** y `axe` no evalúa los rótulos ocultos: la certificación quedaba a merced del estado de hover.

**Corrección (no se oculta el defecto, se arregla el color):**

1. [`admin-rail.tsx`](../../../../apps/web/src/components/layout/admin-rail.tsx): `text-muted-foreground/70` → `text-muted-foreground` (`#8b98a8` sobre `#121821` = **6.81:1** en oscuro; `#64748b` sobre `#ffffff` = **4.76:1** en claro). Ambas conformes.
2. [`gp-e2e-v28865`](../../../../apps/web/e2e/gp-e2e-v28865-auto-axe-mock.spec.ts): nuevo test que **ancla la rail expandida** (`hover` → `data-collapsed="0"`, comprueba que `AUTO` vive en el grupo `Administración`) y barre `axe` ahí. Antes del arreglo ese test falla; después, verde. La certificación de los rótulos deja de depender del hover accidental.

Re-verificado tras el arreglo: `typecheck` OK · `lint` 0 errores · `frontend` `1593 passed` · `gp-e2e-v28865` **14/14**.

## Qué no cambia

Motor AUTO de decisión/ejecución, ledger, posiciones, settlement, contrato HTTP y esquema (head `052_top3_opportunities`). Live/XTB real no se implementa: el canal se declara `SIMULADO`.

## Cita POST-TAG

**`Release tag CI` [`37748285829`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37748285829) VERDE** (tag anotado, objeto `b47ecb2f` → commit `021afbb4`):

- `12` jobs = `11` `success` + `playwright` integrado `skipped`; `certify` `success`.
- `python` `4594 passed / 45 skipped`; `frontend` `268 ficheros / 1593 passed`; `shared` `817 passed / 1 todo`; `playwright (mock E2E)` `96 passed / 21 skipped`; `lifecycle-pg` (Golden Day 2.0, Crash/Recovery, Concurrent AUTO, HardKill, crash injection, multiprocess AUTO) `success`; `contract:check` `critical=0 · warn=0`.
- `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` (`sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`, `3340728` bytes; 2ª corrida IDÉNTICA) ⇒ **`Δ motor = 0` confirmado por CI**.

**Antecedente (rojo, corregido antes del sello):** el primer tag apuntaba a `a2da85a7` y su `Release tag CI` [`37741490506`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37741490506) cayó en `playwright (mock E2E)` por el `color-contrast` de los rótulos de grupo de la `AdminRail` (detalle arriba). El tag se re-ancló al tip corregido `021afbb4`.

**`GitHub Release` `v2.88.88-beta` publicado** (pre-release): <https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.88-beta>.
