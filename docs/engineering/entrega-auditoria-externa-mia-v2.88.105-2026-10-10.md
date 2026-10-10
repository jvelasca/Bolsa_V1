# Entrega a auditoría externa (MIA) — `v2.88.105-beta` · **Cierre de auditoría AUTO**: honestidad de lectura `S5` · identidad de estrategia · E2E reproducible · P&L realizado (`F2-3`) · motivo de ranking (`F2-4`) · DÍA-D declarado (`P4-3`) · simplificación UI (**UI + motor aditivo** · **`Δ motor ≠ 0`** · **`Δ decisión = 0`** · contrato **ampliado** · sin migración)

> **Fecha:** 2026-10-10 · **Producto:** `V2.88.105-beta` · **Package:** `2.11.105-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.104-beta` (tag anotado objeto `ee21e87e` → commit `4cdaffc8`; `Release tag CI` [`38068459963`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459963) **VERDE**).
> **Unidad de esta auditoría:** cerrar, en una sola entrega, las fases `F1`–`F7` del plan «Cierre de auditoría AUTO»: (1) **honestidad de lectura** del puente `S5`; (2) **identidad de la estrategia ejecutada** (separada de «mejor disponible»); (3) **E2E integrado reproducible** AUTO → DÍA-D; (4) **`F2-3`** P&L realizado agregado; (5) **`F2-4`** motivo de ranking por ciclo; (6) **`P4-3`** DÍA-D declarado (artefacto, no «en vivo»); y (7) **simplificación** de la UI AUTO.
> **Regla del hueco:** una afirmación que no se puede sostener se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; un fallo de lectura «No disponible»; **jamás** se rellena con `0` ni con verde; y **carga ≠ hueco**. `ranking ≠ decisión`, `propuesta ≠ posición materializada` y la separación SIM/dinero real se conservan.
> **`Δ motor ≠ 0` (aditivo) y `Δ decisión = 0`.** El diff **sí** mueve `packages/py/**`, pero **no** toca umbrales, reparto de capital, `TOP_N`/régimen/selección/protección: `F4` añade una **lectura** agregada, `F5` **sella** un hecho que el ranker ya calculaba y lo **proyecta**, `F6` solo **declara** metadatos. **Contrato HTTP ampliado** (`totalRealizedPnl` + `serving`; `contract:gen` regenerado, `contract:check` OK).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.105/README.md`](./evidence/v2.88.105/README.md).
> **Cita POST-TAG:** **PENDIENTE** (objeto → commit + `Release tag CI` + `replay-repro`) tras el run de CI del tag.

---

## 1. Qué se entrega (y qué NO)

**Se entrega**, en un único commit:

1. **`F0` Gate de viabilidad.** Nota read-only que decide UI-only vs motor: `F3` UI-only; `F4` motor + contrato sin Alembic; `F5`/`F6` motor. [`gate-f0-…md`](./gate-f0-identidad-estrategia-y-pnl-realizado-2026-10-10.md).
2. **`F1` Honestidad de lectura `S5`.** El **fallo del catálogo de instrumentos** se propaga y se declara **`No disponible`** (fallo), **no** «Sin dato todavía» (ausencia); manda sobre `loading` y el hueco de instrumento; fail-closed de `verifyHref`.
3. **`F2` E2E integrado reproducible.** El journey AUTO → `POST /api/backtests/run` **siembra** un ciclo AUTO durable (reutilizando el CLI dev `seed_auto_cycle_for_ui.py` como subproceso) y **limpia** en `afterAll`; deja de saltarse por falta de ciclo. Un `skipped` sigue siendo **declarado**.
4. **`F3` Identidad de la estrategia ejecutada.** Se **separan** «Mejor estrategia del valor (Finalistas TOP #1)» de «Estrategia ejecutada declarada por el ciclo» (sello `cycle.strategyVersion`) y se **declara** que la coincidencia es **heurística por token completo**.
5. **`F4` `F2-3` P&L realizado agregado.** Se publica el realizado **de todo el historial** (`totalRealizedPnl`, base **canónica** del tax report ⇒ **concilia** con `net_realized_gain`) y se pinta «Resultado realizado» en AUTO; `null`⇒«Sin dato todavía» (**nunca** `0`).
6. **`F5` `F2-4` motivo de ranking por ciclo.** El productor **sella** `opportunityComponents`; el paso `TOP_N` lo publica con su medición; la historia materializa el contexto `RANKING` humanizado (doble categoría: sin dato `UNKNOWN`).
7. **`F6` `P4-3` DÍA-D declarado.** La superficie declara `serving = PRECOMPUTED_ARTIFACT` (artefacto precalculado; **no** se recalcula en vivo). No se simula «en vivo».
8. **`F7` Simplificación UI AUTO.** TOP3 colapsa un `assetId` repetido; `rankNote` una sola vez por superficie; se retira un bloque inalcanzable en Riesgo y la nota de ranking duplicada en Operar.

**NO se entrega**, y se declara:

- **NO** se toca el **motor de decisión/ejecución**, el reparto de capital, los umbrales, ni `TOP_N`/régimen/selección/protección (`Δ decisión = 0`).
- **NO** hay migración (head Alembic intacto `052_top3_opportunities`).
- **NO** se emite `CONFIRMED` (reservado a PAPER); `F6` conserva las **cuatro capas no equivalentes** del DÍA-D.
- **NO** se resuelve `P4-3` como «en vivo»: el feedback DÍA-D **sigue** siendo artefacto precalculado por job offline (el cómputo exige un **replay durable pesado + `ensure_migrated`**, inviable en una petición HTTP).
- **NO** se cierra la deuda PARKED restante (`F2-1` posición por operación / `F2-2` `PortfolioDecision` durable).

---

## 2. Cambios verificables (todo con gate)

| Fase | Fichero(s) | Qué hace |
| --- | --- | --- |
| `F1` | `apps/web/src/features/auto/auto-operation-strategy.ts`, `use-auto-operation-strategy.ts` | Prioriza el **fallo del catálogo** como `No disponible`; fail-closed de `verifyHref`. |
| `F2` | `apps/web/e2e/helpers/auto-cycle-seed.ts`, `apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts` | Siembra durable (subproceso del CLI dev) + limpieza simétrica + assert sin residuo. |
| `F3` | `apps/web/src/features/auto/auto-operation-strategy.ts`, `apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx` | Separa «mejor del valor» de «ejecutada declarada»; declara la heurística. |
| `F4` | `packages/py/domain/src/bolsa_domain/tax_report.py`, `entities/account.py`; `packages/py/application/src/bolsa_application/accounts/{tax,summary}.py`; `apps/api-python/src/bolsa_api/schemas/{accounts,account_mappers}.py`; `packages/shared/src/accounts.ts`; `apps/web/src/features/auto/{auto-account-figures.ts,auto-home-page.tsx}`; `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts` | `compute_all_time_realized_pnl` (reutiliza `_compute_realized_gains`); `totalRealizedPnl` nullable en el DTO; figura «Resultado realizado». |
| `F5` | `packages/py/application/src/bolsa_application/{auto_v2_entry.py,auto_operational_monitor.py}`; `packages/shared/src/cognitive/{auto-ranking-motive.ts,auto-operation-story.ts,index.ts}` | Sella `opportunityComponents`; paso `TOP_N` publica `rank`/`score`/`regime`/`components`; contexto `RANKING` humanizado. |
| `F6` | `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py`; `apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.tsx`; contrato | `serving = PRECOMPUTED_ARTIFACT` en los 2 DTOs + línea de modo honesta en el panel. |
| `F7` | `apps/web/src/features/auto/{auto-top3-opportunities.ts,auto-top3-panel.tsx,auto-operar-page.tsx,auto-riesgo-page.tsx}` | Dedupe por `assetId`; `rankNote` una vez; retira bloque inalcanzable/duplicado. |
| Bump | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.105-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Frontend:** `tsc --noEmit` **OK**; `eslint src` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes); `vitest run` **294 ficheros / 2074 tests verdes**; `build` **OK**; `contract:check` **OK** (contrato regenerado).
- **Python:** `ruff` **All checks passed**; `lint-imports` **4 contratos kept, 0 broken**; `mypy` **544 source files, no issues**; `pytest domain+application` **2706 passed**; `pytest bump guard + api-python tocados` **46 passed**.
- **Shared (TS):** `auto-ranking-motive` + `auto-operation-story` **27 passed**.
- **E2E integrado `S5` (opt-in):** **3/3 verdes** contra stack real (FastAPI + PostgreSQL) con **teardown sin residuo** (0 reservas/fills/ciclos); hermano **mock** **2/2**.
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.105-beta`).
- **`Δ motor ≠ 0` (aditivo):** análisis de `replay-repro` en la [evidencia §4](./evidence/v2.88.105/README.md): `journalReasons` agrega **solo** `reasonCodes` (F5 añade otra clave ⇒ no cambia) y `cycleDetail` va **apagado por defecto** ⇒ el artefacto congelado sale **byte a byte igual**. La **autoridad** es el job CI `replay-repro` del tag.

---

## 4. Hallazgos y estado tras esta entrega

- **Honestidad de lectura (`S5`) — cerrada.** Fallo de catálogo ⇒ «No disponible»; hueco ⇒ «Sin dato todavía»; carga ⇒ «Cargando…».
- **Identidad de estrategia ejecutada — declarada.** «Mejor del valor» y «ejecutada declarada» separadas; coincidencia **heurística** declarada (la identidad exacta sigue pendiente de motor).
- **E2E integrado — reproducible.** El journey deja de saltarse por falta de ciclo; `skipped` solo si `uv`/python no están o el ciclo no consta.
- **`F2-3` P&L realizado — cerrado.** Cifra a primer nivel, `null` honesto cuando no es medible.
- **`F2-4` motivo de ranking — cerrado.** Materializado por ciclo, humanizado, `UNKNOWN` sin hecho durable.
- **`P4-3` — declarado (`PRECOMPUTED_ARTIFACT`).** No resuelto como «en vivo»; **abierto** como recompute real.
- **`F2-1`/`F2-2` (PARKED) — abiertos.**
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **294 ficheros / 2074 passed** |
| `pnpm --filter @bolsa/web run build` | **OK** |
| `pnpm --filter @bolsa/web run contract:check` | **OK** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `uv run mypy … --follow-imports=silent` | **544 source files, no issues** |
| `uv run pytest packages/py/domain/tests packages/py/application/tests -q` | **2706 passed** |
| `uv run pytest test_dia_d_bump_guard + api-python tocados -q` | **46 passed** (`2.11.105-beta`) |
| E2E integrado `S5` (opt-in) / mock | **3/3** / **2/2** |

---

## 6. Sello

- **Producto:** `V2.88.105-beta`. **Package:** `2.11.105-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP ampliado** (`totalRealizedPnl` + `serving`). **`Δ motor ≠ 0` aditivo · `Δ decisión = 0`.**
- **Añadidos:** `docs/engineering/evidence/v2.88.105/README.md`, este documento, `docs/engineering/gate-f0-identidad-estrategia-y-pnl-realizado-2026-10-10.md`; `apps/web/e2e/helpers/auto-cycle-seed.ts`, `apps/web/src/features/auto/auto-top3-panel.test.tsx`; `packages/py/domain/tests/test_tax_report_all_time_realized.py`, `packages/py/application/tests/test_account_summary_realized_pnl.py`, `apps/api-python/tests/test_account_summary_dto_realized_pnl.py`; `packages/shared/src/cognitive/auto-ranking-motive.ts`, `auto-ranking-motive.test.ts`.
- **Modificados:** `packages/py/{domain,application}/src/**` (`tax_report.py`, `account.py`, `accounts/{tax,summary}.py`, `auto_v2_entry.py`, `auto_operational_monitor.py`); `apps/api-python/src/bolsa_api/schemas/{accounts,account_mappers}.py`, `routes/auto_dia_d_feedback.py`; `packages/shared/src/{accounts.ts,cognitive/{auto-operation-story.ts,index.ts}}`; `apps/web/src/features/auto/**`, `apps/web/src/features/auto-monitor/**`; `apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`; `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`; `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`).
- **Tag anotado `v2.88.105-beta`:** **PENDIENTE** (objeto → commit + `Release tag CI` + `replay-repro`). Se exige `replay-repro` **`REPRODUCIDO`** pese al `Δ motor ≠ 0` (análisis de superficie no capturada en la evidencia).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir [`docs/engineering/evidence/v2.88.105/README.md`](./evidence/v2.88.105/README.md).
2. **Entrega MIA.** Leer este documento.
3. **`Δ decisión = 0`.** Revisar `packages/py/application/src/bolsa_application/{auto_v2_entry.py,auto_operational_monitor.py}`: `F5` **solo** sella/proyecta un desglose ya calculado; no cambia selección ni reparto.
4. **`F4` conciliancia.** `test_tax_report_all_time_realized.py` verifica `compute_all_time_realized_pnl == net_realized_gain` cuando todas las ventas caen en el ejercicio; `test_account_summary_realized_pnl.py` fija `None` (no `0`) sin ledger.
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pnpm --filter @bolsa/web run build
   pnpm --filter @bolsa/web run contract:check
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run lint-imports --config packages/py/.importlinter
   uv run pytest packages/py/domain/tests packages/py/application/tests -q
   uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **E2E integrado (opt-in).**
   ```bash
   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v288-s5
   ```
7. **Qué falsaría el sello:** que `F4`/`F5`/`F6` cambien una decisión · que un hueco se colapse a `0` · que `F5` pinte un código crudo · que `F6` emita `CONFIRMED` o simule «en vivo» · que `replay-repro` no reproduzca el artefacto congelado.
