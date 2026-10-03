# Evidencia cruda — `v2.88.34-beta` (AUTO: **bucle de realimentación POR VALOR** sobre el sandbox DÍA-D AUTO + vista en `/auto-monitor`)

> **Objeto:** package **`2.11.34-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** entrega de **investigación/sandbox** sobre el motor AUTO. Convierte el **DÍA-D AUTO** de `v2.88.33` (foto de **un día**) en un **bucle de realimentación POR VALOR** sobre una **ventana `D0..D1`**: por cada **instrumento** agrega lo **declarado**, lo **ejecutado** (hechos durables de cada `D`, leídos read-only) y el **OOS real** posterior, emite un **veredicto** (`CONFIRMED`/`MIXED`/`REFUTED`/`NOT_MEASURED`) y un **catálogo de errores** (`SOFTWARE`/`OPERATIONAL`/`DATA`); se sirve por una ruta **read-only** y se pinta (descriptivo + gráfico) en `/auto-monitor`.
> **`Δ decisión motor = 0`:** no se toca motor, gobernador, `TOP_N`, umbrales, allocation, pesos A/B ni migraciones. `AutoSimulationWorker` y los módulos congelados **no se editan**: el barrido solo los **conduce** con reloj/precio/stores en memoria.
> **Padre:** [`evidence/v2.88.33/README.md`](../v2.88.33/README.md) (DÍA-D AUTO por día).
> **Nomenclatura:** `AUTO engineering release = v2.88.34-beta` · `application package = 2.11.34-beta`.

---

## 0. Qué entrega este sello

| # | Pieza | Qué hace |
|---|---|---|
| **1 · Lógica pura** | `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py` | `build_value_scorecard(...)`, `build_day_matrix(...)`, `classify_error(...)`/`normalize_error(...)`, `summarize_feedback(...)` y `build_dia_d_feedback_artifact(...)`: veredicto **por valor** `CONFIRMED \| MIXED \| REFUTED \| NOT_MEASURED`, **catálogo de errores** `SOFTWARE \| OPERATIONAL \| DATA` (reutiliza el vocabulario ya existente de `auto_reason_codes` / `market_operability`) y la **matriz valor × día**. Un valor no medido viaja `None` + `NOT_MEASURED`; **nunca `0`**. Sin reloj ni ULID: `sort_keys=True` y determinista. Reutiliza los primitivos de `dia_d_auto.py` (`compare_declared_vs_executed`, veredictos `MATCH/DIVERGENT/NOT_MEASURED`) y el **gate global** `window_gate(...)` de `operability_window.py` (el veredicto por valor lo **complementa**, no lo sustituye). |
| **2 · CLI del barrido** | `apps/api-python/scripts/v2_90_dia_d_feedback.py` | `--from D0 --to D1` (o `--at D --days N`), `--watch-size`, `--horizon-days`, `--account-id`, `--out`. Reutiliza el **harness hermético** de `v2_89`/`v2_86`/`v2_87`: corre el replay una sola vez sobre el rango, lee **read-only** los hechos durables de cada `D` (`sim_fill_finance_context`, `portfolio_reservations`, `auto_exit_orders`, `decision_journal_entries`, `execution_events`), mide el **OOS real** posterior a `D1` y escribe `operability_runs/dia-d-auto/feedback-<D0>_<D1>.json` (gitignored). |
| **3 · Ruta read-only** | `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py` | `GET /api/auto/dia-d-feedback` (listado + último artefacto) y `GET /api/auto/dia-d-feedback/{window}` (artefacto de una ventana). Fail-closed: sin cuenta visible ⇒ vacío con `no_account_scope`; sin artefacto ⇒ `available=false` + `artifact_not_found`; ventana inválida ⇒ `invalid_window`. Registrada en `router.py` (tag `auto`). |
| **4 · Contrato** | `apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts` + `apps/web/src/lib/api.ts` | Regenerado (`contract:gen`); métodos `getAutoDiaDFeedbackList` / `getAutoDiaDFeedback`. DTO `DiaDFeedbackByDayDto` tipado (`realizedR`/`cycles`/`errors`). |
| **5 · UI** | `apps/web/src/features/auto-monitor/use-auto-dia-d-feedback.ts`, `dia-d-auto-feedback-panel.tsx`, `dia-d-auto-feedback-heatmap.tsx`, `dia-d-auto-feedback-chart.tsx`, `dia-d-auto-error-list.tsx`, `dia-d-auto-panel.tsx` | Sub-vista **«Feedback por valor»** dentro del modo DÍA-D (`role="tablist"`, junto a **«Sandbox por día»**): resumen global + **tabla por valor** (`Valor \| Veredicto \| R medio \| Hit rate \| n medido \| Cobertura \| Errores`), **heatmap valor × día**, **curva de R acumulado** (`lightweight-charts` `LineSeries`), **catálogo de errores** con badges y **límites declarados**. Las queries de feedback son **perezosas** (solo se disparan al abrir la pestaña): el monitor «Ventana actual» no paga llamadas extra. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | Un valor con `measuredCycles < MIN_VALUE_CYCLES` (5) es `NOT_MEASURED`, y **no** se relaja el suelo. | Bajar el suelo para «confirmar» una muestra pequeña. | `test_dia_d_auto_feedback.py` (17 tests): `test_not_measured_below_sample_floor` |
| **C2** | `REFUTED` **gana** a `MIXED`: una divergencia de software en un paso determinista (`SIGNAL`/`ORDER`/`FILL`) o `expectancyR <= 0` refuta, con independencia del resto. | Priorizar `MIXED` cuando hay una divergencia `DIVERGENT`. | `test_refuted_wins_over_mixed`, `test_software_divergence_refutes` |
| **C3** | `CONFIRMED` exige **las tres**: `expectancyR > 0`, `hitRate >= MIN_VALUE_HIT_RATE` (0.5) y **cero** errores de software. Positivo con hit rate bajo ⇒ `MIXED`, no `CONFIRMED`. | Aceptar `CONFIRMED` con `hitRate < 0.5`. | `test_mixed_when_positive_but_hit_rate_below_floor` |
| **C4** | Un hueco **nunca** se rellena con `0`: `0` es una **medición** ("no pasó nada") y `None` un **hueco**. | Convertir el hueco en `0.0` en el pliegue. | `test_gap_is_not_zero` / aserciones de no-coerción |
| **C5** | La clasificación de errores es **aislada** por familia: cada `code` cae en un solo `kind` (`SOFTWARE`/`OPERATIONAL`/`DATA`). | Mapear un código a dos familias o a `None` silencioso. | `test_error_taxonomy_is_disjoint`, `test_unknown_reason_is_not_an_error` |
| **C6** | El artefacto es **determinista**: mismo estado ⇒ mismo payload byte a byte (sin reloj ni aleatoriedad). | Introducir un timestamp/ULID en el builder. | `test_artifact_is_deterministic` |
| **C7** | La ruta es **fail-closed** y respeta el **scope de cuenta**: sin cuenta ⇒ `no_account_scope`; sin artefacto ⇒ `available=false`; ventana inválida ⇒ `invalid_window`. | Devolver el artefacto con scope `None` o con ventana malformada. | `test_auto_dia_d_feedback_route.py` (7 tests) |
| **C8** | El monitor actual **no** se degrada: la sub-vista de feedback **no** dispara queries al montarse en modo sandbox. | Consultar `getAutoDiaDFeedbackList` incondicionalmente al montar el panel. | `dia-d-auto-feedback-panel.test.tsx` (2 tests: `NO MEDIDO` nunca `0`; no-query en modo sandbox) |
| **C9** | El CLI es **read-only**: las únicas lecturas son barras, sectores y hechos durables; el motor corre con stores en memoria y **no** fabrica cubos durables. | Añadir un `save`/`commit` durable o backdatear `created_at`. | Cabecera del CLI + `_read_*` sin escrituras; artefacto en `operability_runs/` (gitignored) |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest packages/py/application/tests/test_dia_d_auto_feedback.py apps/api-python/tests/test_auto_dia_d_feedback_route.py -q` | **24 passed** (`17` núcleo + `7` ruta) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** (arreglados 2 × `I001` en `v2_90_dia_d_feedback.py`) |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (649 ficheros, 3543 dependencias) |
| `uv run mypy packages/py/domain/src … packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 521 source files** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** (`tsc -b --noEmit`) |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** (`dia-d-auto-feedback-panel.test.tsx` 2 · `dia-d-auto-panel.test.tsx` 2 · `auto-monitor-page.test.tsx` 1 · `auto-monitor.test.tsx` 9) |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** (sin regresión del runner) |
| CLI de humo (`--at 2026-09-15 --days 2 --history-days 30 --horizon-days 5`) | replay `37/37` días (term. `2026-09-22`, `fills=0 vetoes=740 vivas=0 riesgo=0.00 libro=COMPLETE`); artefacto `operability_runs/dia-d-auto/feedback-2026-09-14_2026-09-15.json` (25651 B · `sha256 85B0D5A070C8B779AC40459DA1D2EBDE1AE8538E27EA4FE8F16BB93BCCB23A33`); **20 valores** (confirmados=0 mixtos=0 refutados=0 **n/d=20**), **errores 0/0/0**, gate **`INCONCLUSIVE`** (el comportamiento honesto esperado: un `D` histórico sin hechos durables y sin ciclos medidos) |

> **CLI de humo con barras selladas.** El rango de humo (`2026-09-14..2026-09-15`) se corrió sobre las barras
> congeladas de `docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson` sembradas en la PG local
> (rango `2021-09-14 … 2026-09-29`). Los **20** valores salen `NOT_MEASURED` y **no** se fabrica ningún
> `0`: en cuanto la ventana PAPER opere esos `D` y existan ciclos cerrados, el veredicto y el catálogo de
> errores se **recalculan sin cambiar código**.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **No sustituye la ventana PAPER.** El cubo de calendario sale del **reloj de pared**
   (`sim_fill_finance_context.created_at`); un replay **no** fabrica cubos durables. `≥4 días` /
   `≥2 episodios` / `≥32 ciclos` sigue **abierta** (aquí el gate se declara `INCONCLUSIVE`).
2. **No cierra `P3-2`/`P3-3`** ni `H-4`: es evidencia de **investigación**, clase distinta.
3. **Muestras por valor pequeñas** ⇒ `NOT_MEASURED` será **frecuente**; el suelo de muestra
   (`MIN_VALUE_CYCLES = 5`) se **declara** en `limits`, **no** se relaja para «confirmar».
4. **La detección de divergencia de software es heurística** (pasos deterministas
   `SIGNAL`/`ORDER`/`FILL`), **no** una prueba de bug: informa, no sentencia.
5. **El lado «ejecutado» sigue `NOT_MEASURED` en días históricos** hasta que la ventana PAPER opere ese
   `D`. No se rellena con `0`: se declara el hueco.
6. **El artefacto es hermético por CLI, no por HTTP.** El motor AUTO no corre en el proceso FastAPI
   (vive en `scheduler_worker`, env-gated): la ruta **solo sirve** el artefacto ya escrito.
7. **`AUTO_ENGINE_SIM_REAL_PRICE` se fija a `0`** en el barrido: el precio del replay es el
   `price_script` histórico inyectado (opens reales), no una lectura en vivo. No se fuerza régimen ni se
   baja ningún umbral.
8. **Freeze del runner:** este sello **mueve el árbol** `apps`/`packages`; el runner de la ventana se
   **re-ancló** a los hashes del árbol sellado (`WINDOW_CONFIG.appsHash` = `69bd72d81c64d24937f6e6af325e866586d76a71`;
   `packagesHash` = `2c15ecb8b017793f38bfee307d3573398b9d6ead`; `commit` = `v2.88.34-beta`). **Los hashes son exactos
   tras el commit de esta entrega** (`lint-staged` reformatea el frontend en el pre-commit, así que el árbol
   `apps` commiteado se recalcula por hash y el pin se fija a **ese** valor: `apps` `69bd72d8…`, distinto del
   `0f9b83cb…` estimado antes de commitear). `git rev-parse "HEAD:apps" "HEAD:packages"` devuelve el par
   pineado. `pnpm window:test` (25/25) **no** se ve afectado.
   **Re-anclaje posterior (2026-10-03, cierre `G2`):** el cierre de `G2`/`OBS-19` tocó **tests** bajo
   `apps/` y el `seed.ts` bajo `packages/` (**CI+tests, `Δ motor = 0`**), moviendo el árbol a `apps`
   `71c3024c…` / `packages` `21b2585b…`; `WINDOW_CONFIG` se **re-ancló** a esos hashes (`commit` =
   `05c429a8`). El par de arriba (`69bd72d8…`/`2c15ecb8…`) describe el árbol **del sello** y deja de ser
   el vigente; el pin vivo verificado es `freeze OK · apps 71c3024c… · packages 21b2585b…`.

---

## 4. Comandos (reproducir)

```bash
# Tests puros + ruta read-only
python -m pytest packages/py/application/tests/test_dia_d_auto_feedback.py apps/api-python/tests/test_auto_dia_d_feedback_route.py -q

# Gates de CI (comandos EXACTOS)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent

# Contrato + UI
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor

# Barrido multi-día (read-only)
uv run --no-sync python apps/api-python/scripts/v2_90_dia_d_feedback.py --at 2026-09-15 --days 2 --history-days 30 --horizon-days 5
#   -> operability_runs/dia-d-auto/feedback-2026-09-14_2026-09-15.json

# Runner de la ventana (sin regresión)
pnpm window:test
```

---

## 5. Sello

- **Versión:** `2.11.34-beta` (base `2.11.33-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py`, `packages/py/application/tests/test_dia_d_auto_feedback.py`, `apps/api-python/scripts/v2_90_dia_d_feedback.py`, `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py`, `apps/api-python/tests/test_auto_dia_d_feedback_route.py`, `apps/web/src/features/auto-monitor/{use-auto-dia-d-feedback.ts,dia-d-auto-feedback-panel.tsx,dia-d-auto-feedback-heatmap.tsx,dia-d-auto-feedback-chart.tsx,dia-d-auto-error-list.tsx,dia-d-auto-feedback-panel.test.tsx}`.
- **Ficheros modificados:** `apps/api-python/src/bolsa_api/api/v1/router.py`, `apps/web/src/lib/api.ts`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `apps/web/src/features/auto-monitor/{auto-monitor-page.tsx,dia-d-auto-panel.tsx}`, `scripts/lib/window-forward.mjs`, `package.json`, `CHANGELOG.md`, docs.
- **`Δ motor = 0`:** ningún fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`) tocado.
- **CI DE TAG (POST-TAG, 2026-10-03):** `Release tag CI` run [`37109548555`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37109548555) (`ref=refs/tags/v2.88.34-beta`, HEAD `a98996ed`) → **`SUCCESS`**: **11 jobs `success`** (`security`, `shared`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño. `shared` **Window runner guards** (`pnpm window:test`) → `# tests 25 · # pass 25 · # fail 0`. `python`: `4370 passed, 45 skipped` = **+46** sobre `v2.88.32` (mismos 45 skips) · `Contracts: 4 kept, 0 broken.` · `mypy 521 source files`. `frontend`: **`237` ficheros / `1359` tests** · `passed=true · critical=0 · warn=0`. `lifecycle-pg` **VERDE** (golden `190` + account-isolation `45` + Golden Day 2.0 `2` · Crash/Recovery `2` · Concurrent AUTO `3` · HardKill `2` · crash injection `2` · multiprocess AUTO `1`). `replay-repro` → `REPRODUCIDO` (`1E3ADAC2…`, idéntico a `v2.88.25`–`v2.88.32`, 2ª corrida IDÉNTICA). **`git rev-parse "HEAD:apps" "HEAD:packages"` = `69bd72d8…` / `2c15ecb8…`** = los del freeze.

---

## 6. Gobernanza al día (`G7`)

Documentación de sistema puesta al día en **este mismo sello** (requisito `G7` del
[criterio de salida de `-beta`](../../criterio-salida-beta-2026-10-01.md)):

- [`docs/CURRENT_SYSTEM.md`](../../../CURRENT_SYSTEM.md): **AsOf `V2.88.34`** + sección del tramo `v2.88.20`…`v2.88.34` (antes anclado en `V2.88.19`).
- [`docs/PROJECT_PREMISES.md`](../../../PROJECT_PREMISES.md): nueva **§5 — Operativa AUTO/PAPER** (ventana forward + bucle `DÍA-D AUTO`), enlazada en el índice §0.
- [`docs/engineering/criterio-salida-beta-2026-10-01.md`](../../criterio-salida-beta-2026-10-01.md): §3 re-medido a **2026-10-03 / `v2.88.34-beta`** (`G1`–`G4` siguen ❌; `G7` pasa a ✅).
- [`docs/engineering/versioning.md`](../../versioning.md): tabla de las **5 verdades** actualizada + nota de higiene sobre la regla 3 (el package deja de estar congelado desde `2.11.x`).

**Nada de esto toca motor ni contrato:** es documentación de sistema. La **enmienda de la regla 3** de
`versioning.md` y la **ordenación de `G1`–`G4`** son del **propietario** (criterio §4).
