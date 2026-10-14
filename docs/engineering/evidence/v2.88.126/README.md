# Evidencia `v2.88.126-beta` — cierre de `H5` y `H6` del recorrido funcional DÍA-D: el monitor admite consulta POR INSTRUMENTO y el CTA manual verifica la estrategia EJECUTADA del ciclo

> **Bump:** `2.11.125-beta` → **`2.11.126-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97` y del certificador `v2_98`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
>
> **Naturaleza:** incremento **mixto aditivo** — **backend** (`H5`: contrato HTTP + read-model + store de reservas) y **UI/shared** (`H6`). **`Δ decisión = 0`** (sin umbrales/reparto/`TOP_N`/régimen/selección/protección/ejecución) · **`Δ motor de decisión = 0`** (se toca el **read-model** del monitor y el **store** de reservas, no el motor) · **SIN migración** (head `053_dia_d_cycle_verifications`; **sin índice nuevo**) · **contrato HTTP ampliado de forma ADITIVA** (`contract:gen`/`contract:check` ✅). Tag **unsigned**.
>
> **Base:** `v2.88.125-beta`. Cierra **2 de los 3** huecos declarados en esa pasada ([`deuda-cierre-dia-d-h3-h5-h6-2026-10-13.md`](../../deuda-cierre-dia-d-h3-h5-h6-2026-10-13.md)); **`H3`** (etapa `EXIT` propia) **sigue ABIERTO**.

---

## 1. `H5` — el monitor admite consulta POR INSTRUMENTO (contrato aditivo, sin migración)

**Antes:** el endpoint del monitor operativo solo aceptaba `cycleId` / `limit`; no había forma de pedir «los ciclos de ESTE instrumento».

**Ahora:**

- **Contrato HTTP (aditivo).** [`auto_operational_monitor.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py): nuevo query `instrumentId` (`alias="instrumentId"`, `max_length=128`) y campo **aditivo** `filterInstrumentId` en `AutoOperationalMonitorDto` (eco honesto del filtro aplicado). `openapi.json` + `schema.d.ts` regenerados (`contract:gen`); `contract:check` ✅.
- **Read-model.** [`auto_operational_monitor.read_operational_monitor`](../../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py) acota la ventana de reservas al instrumento (**`cycle_id` MANDA**: si llegan ambos, el filtro por instrumento se ignora) y `build_operational_monitor` declara `filterInstrumentId` + la nota `filter_instrument_empty` cuando el filtro deja `cycles == []` (lista vacía **honesta**, nunca una lectura global).
- **Store.** [`reservation_store.list_recent_with_cycle`](../../../../packages/py/application/src/bolsa_application/reservation_store.py) gana `instrument_id: str | None = None` en Protocol + `InMemoryReservationStore` + `PostgresReservationStore` (filtra por `PortfolioReservationRow.instrument_id`); con `None` conserva el comportamiento previo **byte a byte**. **Sin índice nuevo / sin migración.**

**Criterio de aceptación FALSABLE (cumplido):**

1. `GET /auto/operational-monitor?instrumentId=<id>` devuelve **solo** ciclos de ese instrumento; con un `instrumentId` sin ciclos devuelve `cycles == []` (lista vacía honesta, no global).
2. Coexiste con `cycleId` sin ambigüedad: si ambos se pasan, `cycleId` manda y el ciclo ajeno sigue sin heredar hechos (`SIGNAL`/`SETTLEMENT` no `reached`).
3. El contrato gana el parámetro de forma **aditiva** (`contract:check` ✅) y `readOnly` se conserva; un `instrumentId` desconocido **no** cae a una lectura global.

**Mapeo criterio → test (evidencia):**

- **(1)** [`test_auto_operational_monitor_pg.py::test_monitor_filters_by_instrument_and_declares_the_filter`](../../../../apps/api-python/tests/test_auto_operational_monitor_pg.py) (PG real: `instrumentId="AAA"` ⇒ solo el ciclo AAA; `"ZZZ"` ⇒ `cycles == []` + `filter_instrument_empty`) y [`test_portfolio_reservation.py::test_store_recent_with_cycle_filters_by_instrument`](../../../../packages/py/application/tests/test_portfolio_reservation.py).
- **(2)** El mismo test PG: `cycleId` + `instrumentId` a la vez ⇒ se devuelve el ciclo del `cycleId`.
- **(3)** `contract:check` ✅ + [`test_auto_operational_monitor.py::test_filter_instrument_is_declared_and_empty_is_flagged`](../../../../packages/py/application/tests/test_auto_operational_monitor.py) (eco `filterInstrumentId`; sin filtro ⇒ `None`).

---

## 2. `H6` — el CTA «Verificar D→hoy» verifica la estrategia EJECUTADA (no el #1)

**Antes:** el CTA manual lanzaba la verificación con el `strategyDefinitionId` del **slot #1** del TOP y su `rank` (`rank: 1`), **aunque** el ciclo declarase **otra** estrategia ejecutada (`cycle.strategyPresetKey`) — la verificación podía apuntar a la estrategia equivocada.

**Ahora:**

- [`auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.ts): nuevo `resolveExecutedStrategySlot(presetKey, top, definition?)` que empareja por **igualdad EXACTA** la `strategyPresetKey` del ciclo contra el `strategyType` de **cualquier** slot del TOP (o el `presetKey` de la definición del #1). La vista gana `executedStrategyDefinitionId`/`executedStrategyLabel`/`executedStrategyRank`, `verifyTarget: "executed" | null` y `verifyGapReason`; `verifyHref` pasa a exigir **la ejecutada** (**fail-closed**: si no se resuelve ⇒ `verifyHref = null` y el CTA se **deshabilita** declarando el hueco, **nunca** cae al #1 en silencio). El bloque del #1 se conserva como **referencia**.
- [`auto-operation-story-panel.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx) (`useDiaDVerifyLaunch`): `startDiaDVerification` precarga la sesión DÍA-D LAB con la **ejecutada** (`executedStrategyDefinitionId` + su `rank` real), junto con el `cycleId`/`strategyPresetKey`/`strategyVersion` del ciclo.
- [`auto-operation-strategy-card.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx): nueva línea «Estrategia ejecutada (lo que se verifica)» (`data-testid="auto-operation-strategy-executed"` + `data-verify-target`) y CTA deshabilitado + hueco declarado cuando no se resuelve.

**Criterio de aceptación FALSABLE (cumplido):**

1. Con un ciclo que declara `strategyPresetKey` y un TOP #1 con identidad distinta (`data-match="differs"`), el CTA verifica la **estrategia EJECUTADA** del ciclo y la sesión DÍA-D LAB queda precargada con esa estrategia (y su `rank` real).
2. Con `match === "same"` (identidades exactas) el comportamiento **no cambia**.
3. Con el ciclo **sin** `strategyPresetKey` (hueco), el CTA declara «Sin dato todavía» y no afirma ninguna identidad (no cae silenciosamente al #1 sin declararlo).

**Mapeo criterio → test (evidencia):**

- **(1)** [`auto-operation-strategy.test.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.test.ts) (`differs` ⇒ `executedStrategyDefinitionId` del slot #3, `verifyTarget === "executed"`) y [`auto-operation-story-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.test.tsx) (la sesión LAB queda con `strategyDefinitionId` de la ejecutada, `rank` #3 y `cycleId`).
- **(2)** `auto-operation-strategy.test.ts` (ejecutada == #1 ⇒ misma identidad, `match === "same"`).
- **(3)** `auto-operation-strategy.test.ts` (sin `presetKey` ⇒ `verifyTarget === null`, `verifyHref === null`, `verifyGapReason` declara el hueco) y [`auto-operation-strategy-card.test.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.test.tsx) (CTA deshabilitado + hueco declarado).

---

## 3. Verificación (local)

| Comprobación | Resultado |
|--------------|-----------|
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `mypy` (lista CI: `packages/py/*/src` + `apps/api-python/src`) | **Success: no issues found in 554 source files** |
| `import-linter` (`--config packages/py/.importlinter`) | **4 kept, 0 broken** |
| `pytest packages/py/application/tests` (suite completa) | **2729 passed** |
| Focal store + read-model (`test_auto_operational_monitor.py` + `test_portfolio_reservation.py`) | **79 passed** |
| PG del monitor (`test_auto_operational_monitor_pg.py`, `-rs`) | **14 passed** |
| Focal web `H6` (`auto-operation-strategy` + `strategy-card` + `story-panel`) | **72 passed** (37 + 11 + 24) |
| `pnpm --filter @bolsa/web test` (suite completa) | **297 files / 2175 passed** |
| `pnpm --filter @bolsa/web typecheck` / `lint` | **OK** / **0 errores** |
| `contract:gen` + `contract:check` | **OK** (contrato aditivo sincronizado) |
| Censo de selección (`test_selection.py --missing`) | **0 sin declarar** |
| Guardián de bump (`test_dia_d_bump_guard`) | **1 passed** |
| `alembic heads` | `053_dia_d_cycle_verifications` (**sin migración**) |

---

## 4. Huecos declarados (NO cerrados; sin tocar el motor)

1. **`H3`** — la «señal de SALIDA» sigue **plegada** en `SETTLEMENT` (no hay etapa `EXIT` propia). Exige **ratificar el modelo semántico** (14 → 15 conceptos del relato) antes de tocar la superficie de la historia; **fuera del alcance** de esta pasada.
2. **Ventana PAPER longitudinal (`P3-2`/`P3-3`, ADR-046)** — el certificador **existe** (`v2.88.125`), pero la ventana **real** sigue **`NO MEDIDO`** (OPERACIÓN: ≥4 días de calendario / ≥2 episodios / ≥32 ciclos). **No** se emite `CONFIRMED`.
3. **Ola 6 (Consola avanzada)** — sigue abierta (nivel 3 explícito pendiente); `heading-order` (11 rutas L1) y `axe` (solo con mocks) siguen como deuda preexistente.
4. **P&L** — el DÍA-D certifica **identidad de fuentes y motivos**, no la **rentabilidad** ni la **magnitud** del resultado.

---

## 5. `Release tag CI` del sello — **verde** (con corrección declarada)

**Resultado.** `Release tag CI` [**38520405195**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38520405195) **verde en 15m24s**: **12/12 jobs `success`** + `certify` `success` (`playwright (integrated E2E, opt-in)` = `skipped` por diseño). Lo decisivo para este incremento:

| Job | Resultado | Qué certifica |
|-----|-----------|---------------|
| `playwright (integrated AUTO S5)` | **`success`** | El journey integrado del puente AUTO → estrategia → DÍA-D contra PG + API **reales**, con gates `E2E_S5_REQUIRED=1` + `E2E_INTEGRATION=1` + `E2E_ALLOW_DEV_DB=1` y **guard anti-skip sin `::error`**. |
| `playwright (mock E2E)` | **`success`** | La suite E2E **completa** de mocks (incluye `GP-E2E-S5`, con la nueva aserción de la rama **fail-closed** de `H6`). |
| `python (ruff/imports/mypy/pytest offline)` | **`success`** | `H5`: contrato aditivo + read-model + store (ruff/mypy/import-linter/pytest). |
| `frontend (typecheck/lint/test/build + contract:check)` | **`success`** | `H6` (UI/shared) + contrato sincronizado (`contract:gen`/`contract:check`). |
| `replay-repro` | **`success`** | El sello congelado **se reproduce** (`Δ decisión = 0`). |

**Identidad del sello.** Tag anotado `v2.88.126-beta` (**unsigned**), objeto `dcba2404`, apuntando al commit `7801474c`; `origin/main` == `HEAD` == `7801474c`.

**Corrección declarada (`v2.88.126 FIX CI`, commit `7801474c`).** El **primer** `Release tag CI` del sello (`38474776465`) salió **rojo** por los **dos** jobs E2E de `S5` — **no** por un defecto del código, sino porque los **fixtures** de test **no declaraban** la identidad de la estrategia **ejecutada** del ciclo (`strategyPresetKey`) y, con `H6`, el CTA «Verificar D→hoy» es **fail-closed**: al no poder resolver la ejecutada se **deshabilita** declarando el hueco (comportamiento **correcto** por diseño). Los specs esperaban el comportamiento **previo a `H6`** (CTA habilitado sin declarar la ejecutada).

Qué se cambió (solo fixtures + un test nuevo; **motor/decisión intactos**):

- [`e2e-mock-routes.ts`](../../../../apps/web/e2e/helpers/e2e-mock-routes.ts): `autoMonitorCycle` **declara** `strategyPresetKey` (default `sma_crossover`, que casa con el `strategyType` del TOP del mock) y se añade la opción `autoCyclePresetKey` para forzar el **desajuste**; el ciclo B queda **sin** clave (hueco honesto del contrato).
- [`seed_auto_cycle_for_ui.py`](../../../../scripts/dev/seed_auto_cycle_for_ui.py): el hecho durable `auto_entry_decision` **sella** la identidad EXACTA (`payload.strategyPresetKey`, que el monitor publica aditivo) y se añade `--strategy-preset-key` (default `sma_crossover`); `_resolve_strategy` **reutiliza/crea** la estrategia de esa MISMA clave (sello determinista).
- [`auto-cycle-seed.ts`](../../../../apps/web/e2e/helpers/auto-cycle-seed.ts): `seedAutoCycleForAccount` acepta `strategyPresetKey` y lo propaga al CLI.
- [`gp-v288-s5-...-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts): siembra el ciclo con `PRESET_KEY` y aserta `data-verify-target="executed"`.
- [`gp-e2e-s5-...-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts): aserta la rama **habilitada** y añade un test **nuevo** que fija la rama **fail-closed** (`presetKey` ausente del TOP ⇒ CTA deshabilitado + hueco declarado).

**Verificación local del fix.** `gp-e2e-s5` **3/3** · specs AUTO mock (`v28856`/`v28857`/`v28865`) **20/20** · integrada AUTO S5 (`E2E_S5_REQUIRED=1`, PG + API reales) **4/4** · `pnpm --filter @bolsa/web test` **2175 passed** · `typecheck`/`prettier`/`ruff check` **OK**. El tag se **movió** de `a6cd4fe3` a `7801474c` para que el sello apunte a un commit **verde** (mismo criterio que `v2.88.125-beta`).
