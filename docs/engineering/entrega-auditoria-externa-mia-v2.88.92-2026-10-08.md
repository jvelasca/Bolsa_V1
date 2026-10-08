# Entrega a auditoría externa (MIA) — `v2.88.92-beta` · `UI`: **UI 6.x — barrido global de residuos declarados**

> **Fecha:** 2026-10-08 · **Producto:** `V2.88.92-beta` · **Package:** `2.11.92-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.91-beta` (tag anotado objeto `a34a6094` → commit `1e832b30`; `Release tag CI` [`37796847434`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37796847434) **VERDE**).
> **Unidad de esta auditoría:** cerrar la **deuda declarada** por `v2.88.91` en su [entrega](./entrega-auditoria-externa-mia-v2.88.91-2026-10-08.md) §4 —`Gate N` residual, `submitted ≠ fill`, residuos `Libro`/`Ledger` y el comodín `—` fuera de las superficies auditadas— y **extender el gate falsable** `R-G1` a **Mercado, Laboratorio y chrome** para que la jerga no reaparezca. Auditoría de origen: [`auditoria-ui-6-x-global-2026-10-08.md`](./auditoria-ui-6-x-global-2026-10-08.md) §9; contrato: [`spec-ui-contract-5-0-2026-10-08.md`](./spec-ui-contract-5-0-2026-10-08.md).
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente o `UNKNOWN` se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. El guion `—` queda **prohibido** en nivel 1.
> **`Δ AUTO decision/execution motor = 0`.** Todo el sello es UI/read-model y tests en `apps/web/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.92/README.md`](./evidence/v2.88.92/README.md).
> **Cita POST-TAG:** pendiente de `Release tag CI` (tag por crear).

**Sello dirigido (declarado).** Mandato: **una sola aplicación, un único lenguaje operativo en el primer nivel, sin residuos**. No se añaden funciones ni se toca el motor: se re-corta la superficie ya existente y se hace **falsable** cada afirmación con el gate (`first-level-gate.ts`, ahora con `findFirstLevelDashes`) que falla si la jerga o el comodín reaparecen fuera del nivel 3.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el cierre de los cinco residuos declarados en `v2.88.91` §4:

1. **`Gate N` residual.** Nuevo helper único [`gate-label.ts`](../../apps/web/src/components/gate-label.ts) (`gateHumanLabel`: `PASS`→«Sin bloqueos», `VETO`→«Bloqueado», `DEFERRED`→«Aplazado»; hueco → vocabulario Opción B), aplicado a la tira de mando ([`hoy-command-strip.tsx`](../../apps/web/src/features/trading/hoy-command-strip.tsx)) y a la cola de entrada ([`mesa-entry-queue-panel.tsx`](../../apps/web/src/features/operations/mesa-entry-queue-panel.tsx), filtro y celda).
2. **`submitted ≠ fill`.** Copy unificado a «Enviar una orden no significa que se haya ejecutado» en `account-venue-preference.tsx`, `live-virtual-order-gateway.tsx`, `live-virtual-banner.tsx` y `mesa-operational-bar.tsx`.
3. **`Libro`/`Ledger` de primer nivel.** Retirados en dashboard, cuentas (panel/wizard/settings), fiscal, screeners, `backtesting-tracker`, ayuda (`app-help-menu.tsx`, `mesa-tip-catalog.ts`), `paper-paths-copy` y los `*-propose-supervised`/`position-exit-drawer-actions`. **Identificadores de código y comentarios no se tocan.**
4. **Comodín `—`.** `findFirstLevelDashes` añadido al gate; los fallbacks `"—"` se sustituyen por `absentDataLabel()` en dashboard, cuentas, instrumentos, fiscal y screeners.
5. **Gate extendido.** Nuevo [`barrido-global-first-level.test.tsx`](../../apps/web/src/features/barrido-global-first-level.test.tsx) cubre Mercado, Laboratorio, chrome y las superficies del punto 4.

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se implementa el canal `LIVE` real: el canal se declara `SIMULADO`.
- **NO** se ejecuta el `playwright` **integrado** (E2E contra stack real): sigue `opt-in` y `skipped`. La certificación `axe` de la serie es **con mocks**.
- **NO** se cierran las deudas estructurales de la serie: `PortfolioDecision` durable, traza de materialización SIM, PIT histórico institucional y Execution Analysis.

---

## 2. Cambios verificables (todo con gate)

| # | Residuo de origen (`v2.88.91` §4) | Regla | Fichero(s) | Qué hace |
| --- | --- | --- | --- | --- |
| 1 | `Gate N` residual | `R-G1` | `gate-label.ts` (nuevo), `hoy-command-strip.tsx`, `mesa-entry-queue-panel.tsx`, `mesa-candidates-panel.tsx` | Humaniza la etiqueta de gate con un helper único. |
| 2 | `submitted ≠ fill` | `R-G1` | `account-venue-preference.tsx`, `live-virtual-order-gateway.tsx`, `live-virtual-banner.tsx`, `mesa-operational-bar.tsx` | Un solo copy de resultado en los cuatro puntos. |
| 3 | `Libro`/`Ledger` primer nivel | `R-G1` | `dashboard-page.tsx`, `account-detail-panel.tsx`, `tax-report-page.tsx`, `screeners-*.tsx`, `app-help-menu.tsx`, `backtesting-tracker.ts`, `paper-paths-copy.ts`, `*-propose-supervised.ts`, `position-exit-drawer-actions.tsx` | Fuera el alias deprecado del primer nivel; identificadores intactos. |
| 4 | Comodín `—` | `UI5-14`, `R-G1` | `first-level-gate.ts` (`findFirstLevelDashes`) + superficies del punto 4 | `—` prohibido en nivel 1; huecos con vocabulario Opción B. |
| 5 | Gate fuera de alcance | `R-G1`, `R-G2` | `barrido-global-first-level.test.tsx` (nuevo) | Falsabilidad en Mercado, Laboratorio, chrome y `—`. |
| Bump | — | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.92-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio esperado. `replay-repro` debe seguir **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (cita en §6 tras el CI).
- **Frontend local:** `typecheck` **OK** (exit 0); `lint` **0 errores** (`23` avisos `react-hooks/exhaustive-deps` preexistentes); **277 ficheros / 1687 tests verdes** (+1 fichero / +25 tests respecto a `2.11.91-beta`).
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.92-beta`).
- **`Δ motor = 0` local:** `git diff --name-only v2.88.91-beta -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **Cobertura del gate acotada.** `barrido-global-first-level.test.tsx` cubre las superficies del punto 4 y Mercado/Laboratorio/chrome; **no** sustituye una revisión humana del resto de la app. **Remediación:** ampliar el censo de superficies por oleadas con el mismo gate.
- **`Gate N` conservado** como dato de decisión (no es término prohibido): solo se humaniza su etiqueta.
- **`F-A2` — barrido `axe` en vivo.** Este sello certifica **con mocks**; la variante en vivo (stack real, `playwright` integrado) sigue `opt-in` y `skipped`. **Remediación:** activar el `playwright` integrado en el `Release tag CI`.
- **`UI52-02` — `PortfolioDecision` durable**; **traza de materialización SIM**; **PIT histórico institucional** y **Execution Analysis**: abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **277 ficheros / 1687 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.92-beta`) |
| `replay-repro` — CI | pendiente (**esperado `REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`**) |

---

## 6. Sello

- **Producto:** `V2.88.92-beta`. **Package:** `2.11.92-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `apps/web/src/components/gate-label.ts`, `apps/web/src/features/barrido-global-first-level.test.tsx`, `docs/engineering/evidence/v2.88.92/README.md`, este documento.
- **Modificados:** `apps/web/src/**` (trading, mesa, operations, confirm, accounts, dashboard, fiscal, instruments, screeners, help, settings, backtests, components), `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/auditoria-ui-6-x-global-2026-10-08.md` (§9).
- **Tag anotado `v2.88.92-beta`** — mensaje `UI 6.x global sweep (residuos declarados: Gate N, submitted-fill, Libro/Ledger, dash wildcard) - Delta motor = 0`. **`Release tag CI`:** pendiente.

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.92/README.md` en el árbol del commit del sello.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Contrato.** Leer `docs/engineering/spec-ui-contract-5-0-2026-10-08.md` (Bloque E + §5) y el `§9` de `docs/engineering/auditoria-ui-6-x-global-2026-10-08.md` (origen del barrido).
4. **`Δ motor = 0`.** Verificar que el diff del sello **no toca** `packages/py/**`, worker, umbrales, Alembic ni `contract:gen`:
   ```bash
   git diff --name-only v2.88.91-beta v2.88.92-beta -- packages/py   # vacío
   git rev-parse v2.88.91-beta:packages v2.88.92-beta:packages      # iguales
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Falsabilidad del primer nivel (`R-G1`).** Comprobar que fuera de `[data-technical-detail="true"]` **no** aparece `Recommendation`, `DecisionSession`, `Policy Gate`, `runId`, `cycleId`, `ledger`, `fills`, `DÍA-D`, `WFE`, `PBO`, `DSR`, ni el alias `Libro`, ni el guion `—`. El gate `first-level-gate.ts` + `barrido-global-first-level.test.tsx` (Mercado, Laboratorio, chrome, `—`) fallan si reaparecen.
7. **Falsabilidad de «una pantalla, una pregunta» (`R-G2`).** Confirmar que el primer bloque visible de cada pantalla responde su pregunta declarada y no describe el mecanismo.
8. **Falsabilidad del disclosure único (`RT-04`).** Confirmar que solo existe un `data-technical-detail` por bloque y que el rótulo es «Detalle técnico».
9. **Qué falsaría el sello:** que un dato ausente se pinte `0` o en verde · que el primer nivel reintroduzca jerga interna, `—` o el alias `Libro` · que aparezca un segundo mecanismo de profundidad · que el diff toque `packages/py/**`/motor/contrato/migraciones · que `replay-repro` no reproduzca `1E3ADAC2…`.
