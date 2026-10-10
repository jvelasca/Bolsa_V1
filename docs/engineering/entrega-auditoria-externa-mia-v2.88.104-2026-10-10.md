# Entrega a auditoría externa (MIA) — `v2.88.104-beta` · `UI 8.x`: **puente AUTO → DÍA-D (`S5`) + refactor DRY del lanzamiento DÍA-D** (UI-only · `Δ motor = 0` · `Δ contrato = 0` · sin migración)

> **Fecha:** 2026-10-10 · **Producto:** `V2.88.104-beta` · **Package:** `2.11.104-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.103-beta` (tag anotado objeto `0bd6d81d` → commit `b65fe227`; `Release tag CI` [`38032301155`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38032301155) **VERDE**).
> **Unidad de esta auditoría:** sellar, como **UI-only**, el **puente `S5` AUTO → DÍA-D**: desde la operación de AUTO, la **estrategia/indicadores ganadores** que la sustentan y el **CTA «Verificar D→hoy»** hacia el verificador DÍA-D de Laboratorio, más el **refactor DRY** de ese lanzamiento.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde; y **carga ≠ hueco** (mientras carga se rotula «Cargando...»). `ranking ≠ decisión` y `propuesta ≠ posición materializada` se conservan.
> **`Δ motor = 0`.** El diff vive en `apps/web/**`, `docs/**`, el `.github/workflows/release-tag-ci.yml` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia** (`contract:check` OK; sin `contract:gen`).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.104/README.md`](./evidence/v2.88.104/README.md).
> **Cita POST-TAG:** Tag anotado **`v2.88.104-beta`** (objeto `ee21e87e` → commit `4cdaffc8`); `Release tag CI` [`38068459963`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459963) **VERDE** (`11` jobs `success` + `certify` `success`; `playwright (integrated E2E, opt-in)` **`skipped`** — un `skipped` no certifica); `Python CI` tag [`38068459986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459986) y `main` [`38068458074`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068458074) **VERDES**; `Frontend CI` tag [`38068459902`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459902) y `main` [`38068458156`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068458156) **VERDES**; `Fase 2 scientific` tag [`38068459905`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459905) · `Optimize lab` tag [`38068459974`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459974) y `main` [`38068458226`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068458226) · `Gitleaks` [`38068458070`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068458070) **VERDES**; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…929A37E7` ⇒ **`Δ motor = 0` confirmado por CI**. Tag **unsigned**.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el cierre del hueco confirmado en la [auditoría operativa diaria §5](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) —desde la operación de AUTO no había camino a la estrategia/indicadores ganadores que la sustentan ni al verificador DÍA-D bajo demanda— en un único commit UI-only:

1. **Helper puro + hook (`S5`).** [`auto-operation-strategy.ts`](../../apps/web/src/features/auto/auto-operation-strategy.ts) + [`use-auto-operation-strategy.ts`](../../apps/web/src/features/auto/use-auto-operation-strategy.ts): desde la operación de AUTO resuelve el **UUID del instrumento por ticker** (`getInstruments`), el **TOP #1 de Finalistas** (`getInstrumentStrategyTop`), los **indicadores** y la **razón** (`getStrategy` + `strategySlotToIndicatorLabels`/`readRecommendationReasons`). **Fail-closed:** hueco → «Sin dato todavía» (**nunca** `0`); fallo de lectura → «No disponible».
2. **Tarjeta + CTA.** [`auto-operation-strategy-card.tsx`](../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx) (`AutoOperationStrategyCard`) con el CTA **«Verificar D→hoy»** que entra la sesión DÍA-D LAB (`mode:'auto'`) y navega a `diaDVerifyHref`.
3. **Refactor DRY del lanzamiento DÍA-D.** [`use-dia-d-verify-launch.ts`](../../apps/web/src/features/trading/use-dia-d-verify-launch.ts) (`useDiaDVerifyLaunch`) unifica el lanzamiento **duplicado** en `auto-operation-story-panel.tsx` y `instrument-strategy-top-panel.tsx`. Sin cambio de comportamiento.
4. **Heurística de coincidencia ENDURECIDA.** `resolveAutoOperationStrategyMatch` pasa de **contención** sobre tokens normalizados (falso positivo: sello `ma` contenido en `smacrossover`) a **igualdad por token completo** (`same`/`differs`/`unknown`).
5. **Honestidad UI.** `rank != 1` se **declara**; razones completas (hasta 5); y **'carga ≠ hueco'** (bandera `loading`: en carga NO se declara un falso «Sin dato todavía», se muestra «Cargando...»).
6. **Higiene E2E + tooling dev.** `afterAll` en el spec integrado limpia el `strategy-top` **global** (`DELETE`); `scripts/dev/seed_auto_cycle_for_ui.py` siembra/limpia un ciclo AUTO durable + TOP en la BD dev (`--cleanup`, idempotente).

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el worker, la reserva, las posiciones, el settlement ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`; sin `contract:gen`).
- **NO** se toca `packages/py/**`.
- **NO** se recalcula ranking ni score: la tarjeta **lee** el TOP #1 tal cual.
- **NO** se emite la confirmación reservada: la verificación DÍA-D sigue siendo el verificador del Laboratorio.
- **NO** se cierra `P4-3` ni la deuda PARKED FASE 2 (`F2-3`/`F2-4`).

---

## 2. Cambios verificables (todo con gate)

| # | Trabajo | Fichero(s) | Qué hace |
| --- | --- | --- | --- |
| 1 | Helper + hook `S5` | `apps/web/src/features/auto/auto-operation-strategy.ts`, `use-auto-operation-strategy.ts` | Resuelve UUID por ticker, TOP #1, indicadores y razón; fail-closed («Sin dato todavía»/«No disponible»). |
| 2 | Regresión del helper | `apps/web/src/features/auto/auto-operation-strategy.test.ts` | Cubre resolución y heurística de coincidencia (igualdad por token completo). |
| 3 | Tarjeta + CTA | `apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx`, `auto-operation-strategy-card.test.tsx` | «Estrategia que sustenta la señal» + CTA «Verificar D→hoy» que entra DÍA-D LAB `mode:'auto'`. |
| 4 | Refactor DRY | `apps/web/src/features/trading/use-dia-d-verify-launch.ts`, `auto-operation-story-panel.tsx`, `instrument-strategy-top-panel.tsx` | Unifica el lanzamiento duplicado; sin cambio de comportamiento. |
| 5 | Heurística endurecida | `apps/web/src/features/auto/auto-operation-strategy.ts` | De contención a igualdad por token completo (`ma` deja de coincidir con `smacrossover`). |
| 6 | Honestidad UI | `apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx`, `auto-operation-story-panel.test.tsx` | `rank != 1` declarado; razones completas; `loading` ⇒ «Cargando...» (no falso hueco). |
| 7 | Higiene E2E + mock | `apps/web/e2e/gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts`, `gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`, `apps/web/e2e/helpers/e2e-mock-routes.ts` | Specs del puente; `afterAll` limpia el `strategy-top` global (DELETE). |
| 8 | CI `S5` | `.github/workflows/release-tag-ci.yml` | Filtros del puente `S5` en `playwright` mock e integrado. |
| 9 | Tooling dev | `scripts/dev/seed_auto_cycle_for_ui.py` | Siembra/limpia ciclo AUTO durable + TOP en BD dev (idempotente, `--cleanup`). |
| Bump | Sello declarado | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.104-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio. `git diff --name-only -- packages/py apps/api-python` → **vacío** (antes del `meta.bump`) ⇒ **`Δ motor = 0`** (a confirmar por `replay-repro` en el `Release tag CI` del tag).
- **Frontend local:** `typecheck` **OK** (exit 0); `eslint src` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes); **293 ficheros / 2060 tests verdes**; `build` **OK**; `contract:check` **OK**.
- **E2E mock `S5`:** 2/2 verdes.
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.104-beta`).
- **Verificación real en navegador:** ciclo dev `cyc-ui-970fde76031a`, instrumento ACS (UUID `cmtzslah50007xn9c7ftx7y4l`): tarjeta `#1 SMA exit sim` · indicador `SMA` · 2 razones · sello del ciclo `sma_crossover` ⇒ «Coincide»; CTA → `/backtests?tab=run&instrumentId=cmtzslah50007xn9c7ftx7y4l&focus=detail&verify=1`; sin TOP declara «Sin dato todavía: no hay Finalistas (TOP) para este valor» y deshabilita el CTA. Capturas en [`evidence/v2.88.104`](./evidence/v2.88.104/README.md).

---

## 4. Hallazgos y estado tras esta entrega

- **Puente AUTO → DÍA-D (`S5`) — cerrado.** La operación de AUTO ya lleva a la estrategia/indicadores que la sustentan y al verificador DÍA-D bajo demanda.
- **Falso positivo de coincidencia — cerrado.** La heurística exige **igualdad por token completo**; `ma` ya no coincide con `smacrossover`.
- **`'carga ≠ hueco'` — declarado.** Durante la carga se muestra «Cargando...»; el hueco real sigue siendo «Sin dato todavía»; el fallo de lectura sigue siendo «No disponible».
- **`rank != 1` — declarado.** No se etiqueta como `#1` lo que no lo es.
- **`P4-3` — medición por artefacto CLI, no en vivo.** **ABIERTO** (fuera del alcance de `S5`).
- **Deuda PARKED FASE 2 (`F2-3`/`F2-4`)** — **abierta**.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **293 ficheros / 2060 passed** |
| `pnpm --filter @bolsa/web run build` | **OK** |
| `pnpm --filter @bolsa/web run contract:check` | **OK** |
| E2E mock `S5` (`gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts`) | **2/2 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.104-beta`) |
| `git diff --name-only -- packages/py apps/api-python` | **vacío** ⇒ **`Δ motor = 0`** |

---

## 6. Sello

- **Producto:** `V2.88.104-beta`. **Package:** `2.11.104-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `docs/engineering/evidence/v2.88.104/README.md`, este documento; `apps/web/src/features/auto/auto-operation-strategy.ts`, `auto-operation-strategy.test.ts`, `use-auto-operation-strategy.ts`; `apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx`, `auto-operation-strategy-card.test.tsx`; `apps/web/src/features/trading/use-dia-d-verify-launch.ts`; `apps/web/e2e/gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts`, `apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`; `scripts/dev/seed_auto_cycle_for_ui.py`.
- **Modificados:** `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx`, `auto-operation-story-panel.test.tsx`; `apps/web/src/features/backtests/instrument-strategy-top-panel.tsx`; `apps/web/e2e/helpers/e2e-mock-routes.ts`; `.github/workflows/release-tag-ci.yml`; `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`); `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/PROJECT_STATE.md`, `docs/engineering/backlog-trabajo-2026-08-20.md`, `docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`.
- **Tag anotado `v2.88.104-beta` (objeto `ee21e87e` → commit `4cdaffc8`):** `Release tag CI` [`38068459963`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459963) **VERDE** (`11` jobs `success` + `certify` `success`; `playwright (integrated E2E, opt-in)` **`skipped`**); `Python CI` tag [`38068459986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459986) · `Frontend CI` tag [`38068459902`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459902) · `Fase 2 scientific` tag [`38068459905`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459905) · `Optimize lab` tag [`38068459974`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38068459974) **VERDES**; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…929A37E7` ⇒ **`Δ motor = 0` confirmado por CI**.

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir [`docs/engineering/evidence/v2.88.104/README.md`](./evidence/v2.88.104/README.md).
2. **Entrega MIA.** Leer este documento.
3. **Origen.** Leer la [auditoría operativa diaria §5](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) (donde se confirmó el hueco del puente AUTO → DÍA-D).
4. **`Δ motor = 0`.**
   ```bash
   git diff --name-only v2.88.103-beta -- packages/py   # vacío
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pnpm --filter @bolsa/web run build
   pnpm --filter @bolsa/web run contract:check
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Reproducción en navegador (dev).**
   ```bash
   python scripts/dev/seed_auto_cycle_for_ui.py          # siembra ciclo + TOP en BD dev (idempotente)
   # abrir /auto/operar/operacion/cyc-ui-970fde76031a  → tarjeta «Estrategia que sustenta la señal»
   python scripts/dev/seed_auto_cycle_for_ui.py --cleanup
   ```
7. **Falsabilidad de la heurística.** `auto-operation-strategy.test.ts` falla si un token contenido (p. ej. `ma` en `smacrossover`) vuelve a declararse `same`.
8. **Falsabilidad del fail-closed.** Test falla si un hueco se rellena con `0`, si un fallo de lectura deja de ser «No disponible», o si en carga se declara un falso «Sin dato todavía».
9. **Falsabilidad de la honestidad.** Test falla si `rank != 1` se etiqueta como `#1` o si las razones se recortan por debajo de las disponibles (hasta 5).
10. **Qué falsaría el sello:** que el diff toque `packages/py/**`/motor/contrato/migraciones · que `contract:gen` cambie el contrato · que la tarjeta recalcule ranking/score · que un hueco se colapse a `0` · que `replay-repro` no reproduzca `1E3ADAC2…`.
