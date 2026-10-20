# Evidencia `v2.88.153-beta` — identidad del indicador ganador, S5-04 estable y documentación reconciliada

> **Naturaleza:** sello **posterior y acotado** a `v2.88.152-beta`. **`Δ motor = 0`** ·
> **`Δ decisión = 0`** · contrato HTTP **aditivo** ·
> **migración `057_top3_opportunity_identity`** (nullable, sin backfill).
>
> **Bump** `2.11.152-beta` → **`2.11.153-beta`** (+ `meta.bump` de los **13** CLIs) y tag
> anotado **`v2.88.153-beta`**. La evidencia de `.152` **no se reescribe**: solo se
> reconcilia su recuento de jobs y el matiz del E2E integrado (ver §8).
>
> **AUTO sigue OFF** y la ventana PAPER sigue **`INCONCLUSIVE`**. Un CI verde no certifica
> rentabilidad.

## 1. El hueco

La foto cross-asset `top3_opportunities` guardaba `asset_id`, `combined`, `components`,
`regime` y `reasons`, pero **no** la identidad de la estrategia ganadora. El lector durable
fijaba `bestScoredPresetKey: None` y la UI declaraba «la foto cross-asset no lo sella»: no
se podía contrastar la estrategia **ejecutada** del ciclo contra la **mejor puntuada** del
ranking, solo contra su puesto/activo.

Además, el journey integrado `GP-V288-S5-04` era frágil en arranque en frío (transformación
de módulos de Vite + sync de OHLCV) y la documentación de `.152` mezclaba 12 jobs + `certify`
con «13 jobs», y contaba `165/22` donde la suite medida daba `166/23`.

## 2. Qué cambió (y qué no)

| Pieza | Cambio |
| --- | --- |
| [`opportunity_ranker.py`](../../../../packages/py/analytics/src/bolsa_analytics/cognitive/opportunity_ranker.py) | `OpportunityScore` gana `strategy_preset_key`/`strategy_version` opcionales; `score_opportunity` los copia y `rank_opportunities` los preserva en cada copia. |
| [`auto_v2_entry.py`](../../../../packages/py/application/src/bolsa_application/auto_v2_entry.py) | `_score_from_signal` pasa la identidad que **ya declara** la `V2Signal`. |
| [`top3_opportunities.py`](../../../../packages/py/application/src/bolsa_application/top3_opportunities.py) · [`top3_opportunity_store.py`](../../../../packages/py/application/src/bolsa_application/top3_opportunity_store.py) | `Top3Opportunity`/`Top3OpportunityRecord` transportan la identidad; se conserva en selección, colapso a activo base y `to_records()`/`to_dict()`. |
| [`tables.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py) · [`057_top3_opportunity_identity.py`](../../../../packages/py/infrastructure/alembic/versions/057_top3_opportunity_identity.py) | Columnas `strategy_preset_key`/`strategy_version` `String`, `nullable=True`; `down_revision = "056_auto_ops_jobs"`; sin índice, default ni backfill. |
| [`top3_opportunity_repository.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/top3_opportunity_repository.py) | `Top3OpportunityInput`, `Top3OpportunityRowRecord`, `_map()` y `save()` escriben/leen las columnas. |
| [`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) | `read_top3_snapshot` selecciona la identidad; `resolve_executed_vs_best` publica `bestScoredPresetKey`, `bestScoredStrategyVersion`, `presetMatch` y `versionMatch` **solo si ambos términos existen**; `strategyMeasurement` mide la identidad por separado de la comparación rank/activo. `build_chain_evidence_artifact` deja de forzar `None`. |
| [`top3_opportunities.py` (ruta)](../../../../apps/api-python/src/bolsa_api/api/v1/routes/top3_opportunities.py) · [`auto_estudio_chain.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_chain.py) | DTO aditivo con `strategyPresetKey`/`strategyVersion`; el límite textual de la ruta deja de afirmar que la foto no sella identidad. |
| [`estudio-chain-evidence.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-chain-evidence.tsx) · [`estudio-daily-ops.ts`](../../../../packages/shared/src/estudio-daily-ops.ts) | Muestra el preset/versión reales y el veredicto `presetMatch`/`versionMatch`; si faltan, declara el hueco con `absentDataLabel()`. La versión no duplica la `v` (`v1` ≠ `vv1`). |
| [`trading-dia-d-replay-panel.tsx`](../../../../apps/web/src/features/trading/trading-dia-d-replay-panel.tsx) | Estado observable: `data-run-state="idle|running|ready|error"`, `data-testid="dia-d-session-evidence"` y `dia-d-run-error` visible. |
| [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts) | `beforeAll` pre-sincroniza OHLCV (`yearsBack: 5` + `meta.count > 0`) y precalienta `/auto/operar` y `/backtests`; S5-04 registra `waitForResponse` **antes** del clic y espera `data-run-state="ready"`; el hook declara `test.setTimeout(240_000)`. |

**No** se tocan: umbrales, pesos A/B, `TOP_N`, régimen, sizing, entradas/salidas,
orquestador ni el replay OOS. El cambio en `build_chain_evidence_artifact` es de
**publicación de metadatos**; no altera ninguna decisión.

## 3. Reglas duras de la identidad

1. **Nunca se infiere.** Si la fila no declara preset/versión, viaja `None`. No se deduce del
   ticker, del rank ni del TOP.
2. **Coincidencia exige ambos términos.** `presetMatch`/`versionMatch` son `True`/`False` solo
   con ejecutada y ganadora presentes; si falta una, `None` («no se puede afirmar»).
3. **Mediciones separadas.** `measurement` sigue midiendo el contraste rank/activo;
   `strategyMeasurement` mide la identidad. Un hueco de identidad **no** degrada una
   comparación de puesto que sí se pudo hacer, pero tampoco se disfraza.
4. **Histórico honesto.** Las fotos anteriores a la 057 quedan `NULL` y se leen como
   desconocidas: **no hay backfill** ni identidad reconstruida a posteriori.
5. **La UI declara el hueco.** No convierte `null` en «coincide»; muestra «Sin dato» y explica
   que la foto no sella identidad.

## 4. Verificación (medida)

| Comprobación | Resultado |
| --- | --- |
| `pytest` focalizado de identidad (`test_opportunity_ranker`, `test_top3_opportunities`, `test_auto_chain_durable_reader`, `test_auto_estudio_chain_route`, `test_top3_opportunities_route`) | **58 passed** |
| `pytest` PG de migración/cadena (`test_discovery_evidence_snapshot_pg`, `test_auto_v57_auto16_applied_cost_pg`, `test_auto_v88_27_durable_facts_idempotent_pg`, `test_dia_d_cycle_verification_pg`, `test_signal_alerts_v111_pg`) | **47 passed** (incluye `upgrade`/`downgrade` que atraviesan la 057) |
| `pytest apps/api-python/tests packages/py/application/tests -q` | **4104 passed / 1 failed**: `test_a9_scheduler_process_full_day_pg_zero_human`, fallo **declarado** y preexistente (el día AUTO deja `26.5` en el libro; no toca el camino de identidad y se reproduce en aislamiento). En una corrida anterior de la batería PG aparecieron **deadlocks** de migración (`test_migration_038…`) porque el servidor dev de la API mantiene `AccessShareLock` sobre las tablas que el `downgrade` altera — **en aislamiento 1 passed** |
| `vitest run src/features/auto-monitor` | **21 ficheros · 168 tests passed** |
| `vitest run` (suite web completa) | **313/313 ficheros · 2314 tests passed** |
| `playwright` S5 integrado (1 corrida, `E2E_S5_REQUIRED=1`) | **8 passed en 59,5 s** (sin retries; **S5-04: 4,2 s**) |
| `playwright` S5 integrado (`--repeat-each=3`) | **24 passed** (3 × 8, sin retries; **S5-04: 4,1–4,5 s**) |
| `typecheck` (monorepo) | **OK** (`4 successful / 4`) |
| `lint` (monorepo) | **0 errores**, 23 avisos preexistentes |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` | **`Contracts: 4 kept, 0 broken.`** |
| `pnpm types:py` | **`Success: no issues found in 567 source files`** |
| `contract:check` | **OK** (cambio aditivo; `openapi.json`/`schema.d.ts` coinciden) |
| `alembic heads` (desde `packages/py/infrastructure`) | **`057_top3_opportunity_identity (head)`** |
| `pnpm window:test` | **50 passed** |
| `pnpm window:freeze` | **`freeze OK (0b2417bf)`** (`appsHash eb380c14…`, `packagesHash c6a6d9d9…`) |
| `replay-repro` local (fixture congelado + PostgreSQL) | **`REPRODUCIDO (render del sello, byte a byte)`**: `sha256 01429BCC…B7476`, `3 488 758` bytes (mismo contenido LF `3 383 461`); 2ª corrida **idéntica** ⇒ **`Δ decisión = 0`** |

**Flaky declarado en la suite de UI.** En una corrida de la suite web completa con la suite
Python completa en paralelo, `dia-d-auto-run.test.tsx` «declara el fallo de transporte sin
confundirlo con sin artefacto» agotó `Test timed out in 5000ms`; **en aislamiento 6 passed** y
la suite completa, repetida sin carga concurrente, volvió a pasar **313/313 ficheros ·
2314/2314 tests**. No se tocó `testTimeout` ni `retries`.

## 5. S5-04: de la fragilidad al estado observable
- El fixture exige, **antes** del journey, `POST /api/instruments/{id}/sync { yearsBack: 5 }`
  y `GET /api/instruments/{id}/ohlcv` con `meta.count > 0`; un fallo aquí es **fallo de
  fixture**, no un `skipped`.
- `beforeAll` precalienta `/auto/operar` y `/backtests` para pagar la transformación de Vite
  una sola vez. El precalentamiento **no** relaja los gates: si falla, se anota y las
  aserciones reales siguen siendo el gate.
- El host DÍA-D publica `data-run-state`; S5-04 registra `waitForResponse` del
  `POST /api/backtests/run` **antes** del clic, exige 2xx, espera `dia-d-session-evidence` y
  `data-run-state="ready"`, y falla con el texto de `dia-d-run-error` si aparece.
- Resultado local: **8/8 en el primer intento** (59,5 s) y **24/24 con `--repeat-each=3`**, sin
  retries, con **S5-04 en 4,1–4,5 s** en las cuatro ejecuciones: el `beforeAll` precalienta la
  transformación de módulos y el journey deja de pagar el arranque en frío. El `beforeAll`
  declara `test.setTimeout(240_000)` porque el fixture (gate + seed + precalentamiento) excede
  el timeout por defecto de hook (30 s).

## 6. `lifecycle-pg` en rojo el 2026-10-20: el sweep de `test_a9…` elegía un fill PARCIAL

El `Release tag CI` del primer intento puso `lifecycle-pg (Alembic + auth + golden restart)`
en **rojo** con `test_a9_scheduler_process_pg_zero_human`: «el día AUTO no deja el libro
plano: quedan **26.500000** (`inst-a9proc-0000000002`)». **No era una regresión del sello**
(el diff no toca motor, broker, scheduler ni sizing: `Δ motor = 0`), era un **defecto de
determinismo del propio harness**, dependiente del día:

- `_filling_instrument_id` elige el instrumento **puro y determinista** a partir de
  `bar_tick(now, "1d")` y `bar_tick(now + 1d, "1d")`. Con el cambio de fecha, la barrida deja
  de elegir el candidato de ayer.
- El probe aceptaba cualquier `simulated_fill_schedule` con `fills` **no vacío**, pero ese
  schedule parte la cantidad en chunks y **puede terminar en parcial**
  (`cumulative_filled_quantity < quantity`). Medido para la barra `20746`:
  `inst-a9proc-0000000002` llenaba el BUY **entero** y el SELL solo **73,5** de 100 ⇒ el libro
  quedaba con **26,5** y el gate «día plano» caía **sin que el motor hubiera cambiado**.
- **Arreglo (solo test, sin relajar ninguna aserción):** el probe exige **llenado TOTAL**
  (`cumulative_filled_quantity == quantity`) en ambos lados y en las dos barras probadas — el
  mismo criterio que el `require_full=True` de `test_auto_fill_cycle_seal_pg.py` (sello
  `.137`). Con la barra de hoy elige `inst-a9proc-0000000003`, que llena BUY y SELL enteros.
- **Medido:** `pytest test_a9_scheduler_process_pg_zero_human.py` ⇒ **2 passed en 32,0 s**
  (antes: `1 failed` en **121,4 s**, agotando el presupuesto de 120 s).

Este hallazgo se declara explícitamente porque **el sello anterior lo tenía latente**: el
mismo árbol habría pasado en verde un día y en rojo al siguiente, sin código de por medio.

## 7. Límites declarados (sin fabricar)

- **AUTO sigue OFF**; no se enciende la cadencia ni el orquestador.
- La prueba demuestra **trazabilidad**, **no** rentabilidad. Sin ciclos PAPER reales la
  ventana sigue **`INCONCLUSIVE`**.
- La identidad es **metadato auditable**: una foto histórica sin identidad se declara
  desconocida; no se rellena ni se deduce.
- La migración es **aditiva y nullable**: el `downgrade` elimina las dos columnas y no toca
  filas históricas.
- `test_a9_scheduler_process_pg_zero_human` quedó **rojo** en la primera corrida (local y CI)
  por el defecto de determinismo del harness descrito en §6; **corregido** (probe de llenado
  TOTAL) y verificado **2 passed en 32,0 s**. El motor no se tocó.
- En la batería PG de migración/cadena apareció **1 deadlock** (`test_migration_038_roundtrip`)
  porque el servidor dev de la API estaba vivo (`AccessShareLock` sobre las tablas que el
  `downgrade` altera); **pasa en aislamiento**. No se mató el servidor del usuario para forzar
  un verde. La corrida completa posterior de `apps/api-python/tests` +
  `packages/py/application/tests` no volvió a reproducirlo (**4104 passed / 1 failed**, y el
  único fallo es el `test_a9…` declarado). Tras la corrección de §6 el test pasa; la suite
  completa no se repitió entera (13 min) porque el único rojo era ese test, ya verificado en
  aislamiento.
- `replay-repro` **sí se ejecutó en local**: se sembró el fixture congelado (20 instrumentos /
  25 700 barras) y el artefacto salió con el SHA-256 del sello. La 2ª corrida fue **idéntica**
  ⇒ **`Δ decisión = 0`**. El artefacto vive en `artifacts/` (ignorado por git).
- Operativa **100 % SIM**; no se envían órdenes reales.

## 8. Freeze y migración

- `alembic heads` = `057_top3_opportunity_identity`. `upgrade` y `downgrade` se ejercitan en
  los tests PG (`054 ↔ head`, y las rutas que bajan a 046/048/054 y vuelven a head).
- `window:freeze` **OK** sobre los tree hashes del árbol actual. El pin conserva un `commit`
  anterior; el freeze real son los dos hashes (`appsHash`/`packagesHash`), y `--check` los
  valida.
- No se re-mide la ventana PAPER: sigue necesitando **OPERACIÓN**, no software.

## 9. Publicación

**Bump y tag.** Este sello sí publica: `package.json` pasa a **`2.11.153-beta`**, los **13**
CLIs DÍA-D sellan el mismo `meta.bump` (el literal congelado del replay de `v2_87` sigue en
`2.11.0-beta`, protegido por `test_v2_87_frozen_replay_bump_stays_pinned`) y el tag
**anotado** `v2.88.153-beta` se empuja a `origin`, lo que dispara `Release tag CI`.

**Migración.** El head de Alembic pasa de `056_auto_ops_jobs` a
**`057_top3_opportunity_identity`**: dos columnas `String` `nullable=True`, sin índice, sin
default y **sin backfill**. El histórico queda `NULL` y se lee como desconocido.

**Reconciliación de `.152`.** La evidencia `.152` queda corregida en dos puntos de hecho (no
se reescribe el sello): el `Release tag CI` cierra con **12 jobs `success` + `certify` = 13
éxitos totales y 1 job `skipped`**, y el E2E integrado de S5 **sí se ejecutó** en el gate duro
`playwright (integrated AUTO S5)` (verde con 1 flaky y reintento), distinto del job opt-in
`playwright (integrated E2E, opt-in)`, que está `skipped` y no certifica.

**CI del sello.** Ver la cita POST-TAG más abajo (§10): hasta que el run no cierre con
`certify: success`, este sello **no** está certificado.

**Fuera de este sello.** Cualquier promoción a `CONFIRMED` o certificación de rentabilidad:
la ventana PAPER sigue `INCONCLUSIVE` porque depende de OPERACIÓN, no de software.

## 10. Cita POST-TAG

_Pendiente: se completa con el id del run, `conclusion`, recuento de jobs, resultado de
`replay-repro` y comportamiento de S5-04 en CI cuando `Release tag CI` cierre._
