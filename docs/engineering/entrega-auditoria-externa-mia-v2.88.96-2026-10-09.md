# Entrega a auditoría externa (MIA) — `v2.88.96-beta` · `FASE 3`: **cierre de las 2 observaciones de `S1`–`S3` (UI/producto · Δ motor = 0)**

> **Fecha:** 2026-10-09 · **Producto:** `V2.88.96-beta` · **Package:** `2.11.96-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.95-beta` (tag anotado objeto `778c5ec9` → commit `52ba2a26`; `Release tag CI` [`37892237594`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37892237594) **VERDE**).
> **Unidad de esta auditoría:** que las **dos observaciones menores** del self-review de `v2.88.95-beta` queden cerradas **sin cambiar la semántica** de los slices `S1`–`S3`: cobertura explícita de `S2` en `completo`+`prepared`, y `indicatorSpecs` reales (detalle de estrategia) en `S3`.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. `ranking ≠ decisión` y `propuesta ≠ posición materializada` se conservan.
> **`Δ motor = 0`.** El diff vive en `apps/web/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.96/README.md`](./evidence/v2.88.96/README.md).
> **Cita POST-TAG:** tag anotado `v2.88.96-beta` (objeto `74e3fcf4` → commit `de3e5222`); `Release tag CI` [`37894478961`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37894478961) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `frontend` `281` ficheros / `1753` passed; `python` `4596 passed / 45 skipped`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el cierre de las dos observaciones de `v2.88.95-beta`:

1. **`S2` — cobertura `completo`.** Test nuevo que fija que en `focusMode = "completo"` + `phase = "prepared"` con `Entrada ≠ Trigger` coexisten ambas líneas, igual que en `simple`. La rama es compartida; el test la blinda.
2. **`S3` — `indicatorSpecs` reales.** El panel de Finalistas resuelve hasta ~3 `strategyDefinitionId` vía `GET /api/strategies/{id}` (`StrategyDefinitionDetailDto.definition`) y usa `definition.indicatorSpecs` como **fuente preferida**, con `presetIndicatorSpecs(strategyType)` como fallback. Helper puro y falsable `buildStrategyDefinitionRefMap`.

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se implementa `S4-agregador-evidencia`: no se emite `CONFIRMED`.
- **NO** se cierran `P4-3`, `P2-4` ni la deuda PARKED (`F2-1`…`F2-4`).

---

## 2. Cambios verificables (todo con gate)

| # | Observación | Fichero(s) | Qué hace |
| --- | --- | --- | --- |
| 1 | `S2` sin test `completo` | `operational-plan-chart-levels.test.ts` | Test de coexistencia `Entrada ≠ Trigger` en `prepared` + `completo`. |
| 2 | `S3` sin `indicatorSpecs` vivos | `instrument-strategy-top-panel.tsx`, `finalist-indicators-reason.test.ts` | Resolución `definition.indicatorSpecs` → preset; helper puro `buildStrategyDefinitionRefMap`. |
| Bump | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.96-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio esperado. `replay-repro` debe seguir **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (cita en el commit post-tag).
- **Frontend local:** `typecheck` **OK** (exit 0); `eslint src` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes); **281 ficheros / 1753 tests verdes** (+3).
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.96-beta`).
- **`Δ motor = 0` local:** `git diff --name-only -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`P2-4` — T1/T2 en `sr-only` con Journey activo.** **ABIERTO**: fuera del alcance de `S1`–`S3`.
- **`P4-2`/`P4-4` — veredicto DÍA-D fragmentado y `CONFIRMED` reservado.** **NO LANZADO** (materia de `S4`).
- **`P4-3` — medición por artefacto CLI, no en vivo.** **ABIERTO**.
- **Deuda PARKED FASE 2 (`F2-1`…`F2-4`)**.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **281 ficheros / 1753 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.96-beta`) |
| `git diff --name-only -- packages/py` | **vacío** ⇒ **`Δ motor = 0`** |
| `replay-repro` — CI | **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`** (`Release tag CI` [`37894478961`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37894478961) **VERDE**) |

---

## 6. Sello

- **Producto:** `V2.88.96-beta`. **Package:** `2.11.96-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `docs/engineering/evidence/v2.88.96/README.md`, este documento.
- **Modificados:** `apps/web/src/features/backtests/instrument-strategy-top-panel.tsx`, `apps/web/src/features/backtests/finalist-indicators-reason.test.ts`, `apps/web/src/features/charts/operational-plan-chart-levels.test.ts`, `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **Tag anotado `v2.88.96-beta`** — objeto `74e3fcf4` → commit `de3e5222`; mensaje `FASE 3 close S1-S3 observations (S2 completo coverage, S3 real indicatorSpecs via strategy detail) - Delta motor = 0`. **`Release tag CI`** [`37894478961`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37894478961) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.96/README.md`.
2. **Entrega MIA.** Leer este documento.
3. **Origen.** Leer la [entrega de `v2.88.95`](./entrega-auditoria-externa-mia-v2.88.95-2026-10-09.md) (los slices y su semántica).
4. **`Δ motor = 0`.**
   ```bash
   git diff --name-only v2.88.95-beta -- packages/py   # vacío
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Falsabilidad `S2` completo.** `operational-plan-chart-levels.test.ts` falla si en `completo` no coexisten `Entrada` y `Trigger` con precios distintos.
7. **Falsabilidad `S3` detalle.** `finalist-indicators-reason.test.ts` falla si `buildStrategyDefinitionRefMap` no toma `definition.indicatorSpecs` del detalle, o si pierde el `presetKey` del summary sin detalle.
8. **`S4` no lanzado.** Confirmar que no existe un veredicto único que emita `CONFIRMED`.
9. **Qué falsaría el sello:** que el diff toque `packages/py/**`/motor/contrato/migraciones · que `S2`/`S3` cambien su semántica · que `S3` deduzca indicadores del catálogo del gráfico · que `S4` se lance o emita `CONFIRMED` · que `replay-repro` no reproduzca `1E3ADAC2…`.
