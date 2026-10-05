# Evidencia `v2.88.50-beta` — `AUTO · DÍA-D-4`: **cierre PIT por día, proyección de mediciones en reservas, 2 fixes de UI y arranque AUTO UI 1.0** (absorbe `v2.88.49-beta`)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.50-beta` · **Package:** `2.11.50-beta` · **AsOf:** 2026-10-05 · **Nature:** `INVESTIGACION` · **Fase:** `V2.93…V2.97 DIA-D AUTO` · **Δ motor = 0**.

**Schemas:** `dia-d-multi-band-v1` (`KIND = "DIA_D_AUTO_MULTI_BAND"`), `dia-d-thesis-exit-v5` (`KIND = "DIA_D_AUTO_THESIS_EXIT"`), `dia-d-multi-cycle-ledger-v7` (aditivo sobre `-v6`) y `dia-d-thesis-stop-sequences-v2` (`KIND = "DIA_D_AUTO_THESIS_STOP_SEQUENCES"`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración** (leer no escribe esquema). **Contrato HTTP:** `AutoMonitorReconciliationDto` gana 5 campos (`reasonMeasurement`/`callerMeasurement`/`agedMeasurement`/`graceWindowMeasurement`/`reconciliationMeasurement`); `openapi.json` y `schema.d.ts` regenerados (`contract:check` OK).

**Padres:** [`v2.88.49`](../v2.88.49/README.md) (**absorbido**: separación A/C del `THESIS_EXIT`, commit `e70b23fa`, **sin tag ni medición**) → [`v2.88.48`](../v2.88.48/README.md) (huella de decisión por ciclo) → [`v2.88.47`](../v2.88.47/README.md) (el nivel tocado no ejecutado) → [`v2.88.46`](../v2.88.46/README.md) (el nivel congelado ES el stop inicial) → [`v2.88.45`](../v2.88.45/README.md) (dónde viven los `THESIS_EXIT`).

**Decisión de versionado (declarada).** `v2.88.49-beta` estaba **commiteado** (`e70b23fa`) pero **sin tag ni medición**; su evidencia declaraba la medición como PENDIENTE. Se **absorbe** en un único sello `v2.88.50-beta` para no correr dos veces el pipeline: el **mismo** re-pipeline (a) corrige el **sesgo de universo punto-en-el-tiempo (PIT)** y (b) mide A/C sobre el universo corregido. La absorción queda registrada en `docs/engineering/versioning.md` (fila Git tag) y `docs/CURRENT_SYSTEM.md`. **Consecuencia esperada y cumplida:** las cifras citadas de `v2.88.41`…`v2.88.49` (38/38, 19/19, `expectancy`) **cambian**; se documenta el delta, no se reutilizan.

**Packages de evidencia (no versionados, `.gitignore`):**

- `operability_runs/dia-d-auto-pit-run1/` · `…-run2/` — `12` ledgers `dia-d-multi-cycle-ledger-v7` (secuencia + huella de decisión + `orderCreated`) por corrida.
- `operability_runs/dia-d-auto/multi-band-pit-run1.json` (`52 798 B`) · `multi-band-pit-run2.json` (`51 931 B`) — los plegados `v2_94` del universo PIT corregido.
- `operability_runs/dia-d-auto/thesis-exit-pit-run1a.json` (`184 445 B`) — el artefacto `dia-d-thesis-exit-v5`.
- `operability_runs/dia-d-auto/thesis-stop-sequences-2022_2026.json` (`291 275 B`) — el volcado `--sequences`.
- `artifacts/repro/replay-1.json` · `replay-2.json` — el replay regenerado en BD efímera (`3 445 622 B` cada uno).

---

## 0. Qué añade este sello (y qué NO)

Cinco bloques, todos **sin tocar el motor**:

1. **PIT por día (raíz del sesgo de muestra).** El watch multianual se anclaba al **último día del año** (`YYYY-12-31`). Un año **incompleto** (`2026`) tiene ese ancla en el futuro ⇒ **ningún** instrumento elegible ⇒ la muestra se declaraba `sin_universo_pit`. Peor: dentro de un año, anclar a `31-dic` **excluía** a los instrumentos **deslistados a mitad de año**. Ahora `candidate_ids(ene-01, dic-31)` resuelve la **ventana de elegibilidad** de cada instrumento y `bars_by_symbol` se **poda** a sus días elegibles (`eligible_days_by_symbol`), cinturón y tirantes.
2. **5 banderas de medición en reservas.** `reason`/`caller`/`aged`/`grace`/`reconciliation` viajan del audit al monitor, al DTO y a la UI; un `UNKNOWN` deja de ser indistinguible de `"?"` (se pinta `NO MEDIDO`).
3. **Dos fixes de UI:** la pestaña DÍA-D **deja de sondear** `/auto/operational-monitor` cada `20 s` (`enabled: mode === "current"`), y el tooltip de una celda `NOT_MEASURED` del heatmap pinta **`sin dato`** (no `0 ciclos · 0 errores`).
4. **Rojo de `main`:** `dia-d-auto-feedback-panel.test.tsx` asertaba la query de detalle antes de que el efecto la disparara; se arregla la **causa** (`waitFor`), no se relaja el test.
5. **AUTO UI REFACTOR 1.0 (piloto).** View-model puro `buildAutoOperationStory` (`@bolsa/shared`) que pliega los DTO existentes en **una operación** de `13` etapas, + pestaña «Operación». **No** se elimina ninguna pantalla.

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión (§3: `Δ motor = 0` demostrado). **NO** introduce contrafactuales. **NO** cierra la deuda de `stopBasisMismatchR` ni declara `CONFIRMED`.

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1`. La huella `decisionRoute`/`orderCreated` se **LEE** del estado ya producido por el worker; **no** re-ejecuta la decisión.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **El sesgo PIT era el ancla al `31-dic`.** Con PIT por día, `2026` pasa de `NOT_MEASURED (sin_universo_pit) 12/12` a **medido `12/12`**, y los años completos (`2022`–`2025`) **no cambian**. | Que `2026` siga sin medir, o que cualquiera de `2022`–`2025` mueva su `expectancy`/ciclos. | `coverage.perYear`: `2026` `{notMeasured: 0, measured: 12}`; `byYear` `2022 -0.4363` / `2023 +0.3658` / `2024 +1.2856` / `2025 +0.2477` **idénticos** al anclaje a `31-dic`. `2021` sigue **vacío `12/12`** (sin barras PIT en la ventana). |
| **2** | **El delta PIT es ADITIVO a la banda:** el global sólo suma los `22.25` ciclos/año de `2026`. | Que el global cambie por otra causa (se movería un año ya medido). | Global `bands.cycles.mean` `89.5 → 111.75` (**+22.25** = `2026`); `expectancyR.mean` `-0.0283 → +0.0111`; `se` `2.501 → 3.228`. |
| **3** | **El punto global NO es citable** ni antes ni después: la banda sigue cruzando el cero. | Que `crossesZeroR` pase a `false`. | `global.validity = {crossesZeroR: true, pointCitable: false, se: 3.228, ci95HalfWidth: 6.327}`; banda de R `[-17.290, +19.328]`. |
| **4** | **La capa v7 SEPARA el caso A del C sobre datos reales.** `decisionRoute = {materializado: 19, orden_creada_sin_fill: 23}` ⇒ **A (`stop_evaluado_sin_orden`) = `0`**. | Que aparezca cualquier ciclo en `stop_evaluado_sin_orden` o en `stop_evaluado_sin_materializar` (hueco). | `route` del artefacto v5; `stop_no_evaluado`/`sin_toque`/`sin_traza` = `0`. |
| **5** | **El decider SIEMPRE corrió:** `stopEvaluatedOnTouch` y `deciderRanOnTouch` = `42/42`. | Que algún toque no deje ni motivos ni etiqueta. | `stop evaluado en toque 42/42 (1.000)`; `decider corrió en toque 42/42 (1.000)`. |
| **6** | **La medición A/C cambia la muestra** de `38` a `42` observaciones `THESIS_EXIT` (universo PIT corregido), y la expectancy pasa a `-0.7150`. | Que `38` siga siendo el `n` global. | `detalle capturado sí · ciclos THESIS_EXIT 42 · con fricción COMPLETE 42`; `GLOBAL n= 42 exp -0.7150`. |
| **7** | **Determinismo del re-pipeline:** dos corridas `v2_94` ⇒ los `12` ledgers de ciclos **byte a byte idénticos**. | Que un `draw-XX` difiera. | `draw-00…draw-11` `IDÉNTICO` (§3). |
| **8** | **Determinismo del plegado:** dos corridas `v2_97` y dos `--sequences` ⇒ mismo `sha256`. | Que dos corridas difieran. | `thesis-exit-v5 = F865106D…` (`184 445 B`); `sequences = 2268FA79…` (`291 275 B`). |
| **9** | **Un hueco es `None`/`NOT_MEASURED`, nunca `0`:** las `5` banderas de reserva viajan como `"UNKNOWN"` salvo medición real; el tooltip de celda vacía dice `sin dato`. | Que aparezca un `0`/`"sí"` donde falta el dato. | Tests de `auto-reservation-panel` (`NO MEDIDO`) y `dia-d-auto-feedback-heatmap` (`sin dato`). |
| **10** | **`Δ motor = 0` DEMOSTRADO LOCALMENTE:** ninguna línea de motor cambia y el artefacto congelado **se reproduce byte a byte**. | Que el árbol del motor cambie o que el replay difiera del sello. | `git diff` de motor vacío; `replay-repro` **`REPRODUCIDO`** `24066225…` (`3 445 622 B`) en **dos** corridas (§3). |

---

## 2. Medición real (`PostgreSQL`, `K = 12` sorteos, años `2021-2026`)

### 2.1 Delta PIT (banda multirregimen, `dia-d-multi-band-v1`)

| Cubo | Anclaje `31-dic` (OLD) | PIT por día (NEW) | Lectura |
| --- | --- | --- | --- |
| `2021` | vacío `12/12` | vacío `12/12` | sin barras PIT en la ventana (declarado) |
| `2022` | `-0.4363` (`49.5` ciclo/sorteo) `citable` | **idéntico** | año completo ⇒ el ancla a `31-dic` ya era correcta |
| `2023` | `+0.3658` (`12.25`) no citable | **idéntico** | ídem |
| `2024` | `+1.2856` (`7.42`) `citable` | **idéntico** | ídem |
| `2025` | `+0.2477` (`20.33`) no citable | **idéntico** | ídem |
| `2026` | `NOT_MEASURED 12/12` (`sin_universo_pit`) | **`+0.1819` (`22.25`) no citable** | año **incompleto**: el ancla a `31-dic` era futura |
| **GLOBAL** | `-0.0283` · ciclos `89.5` · `[-0.1813, +0.1248]` | **`+0.0111`** · ciclos **`111.75`** · `[-0.1503, +0.1695]` | banda de R `[-17.290, +19.328]`, `crossesZeroR=true`, `pointCitable=false` |

`crossCheck.evidenceDrift=true` contra el plegado anterior, con `driftedKeys = [expectancyR, hitRate, measuredCycles, verdict, evidenceQuality]` — **esperado** y es exactamente el delta que este sello documenta.

> **Nota declarada (la corrección es más estrecha de lo que el plan arriesgaba).** Para el provider actual `active_until` = **última barra**, así que la **poda** por día suele ser **no-op**; el efecto REAL del arreglo es **incluir en el watch** a los que no sobrevivieron al cierre del año. Sobre años completos eso ya lo hacía el ancla a `31-dic`; el agujero medido estaba en el año **incompleto** (`2026`). La capacidad queda instalada para cuando exista un `active_until` real (delistados).

### 2.2 Correlación DECISIÓN↔CICLO con A/C separadas (`dia-d-thesis-exit-v5`, capa v7)

Cobertura: **`42` observaciones** `THESIS_EXIT` (pooled sobre sorteos), `11/12` sorteos con celda, `42` con fricción `COMPLETE`, una estrategia (`v283-window-a`) y una dirección (`long`), `9` símbolos.

| Métrica | Valor | Lectura |
| --- | --- | --- |
| `route` | `{materializado: 19, orden_creada_sin_fill: 23}` | **caso C = `23`**, caso **A = `0`**; `stop_evaluado_sin_materializar`/`stop_no_evaluado`/`sin_toque`/`sin_traza` = `0` |
| `routeByStructuralStopCandidate` | `materializado {candidate 19}` · `orden_creada_sin_fill {candidate 23}` | **`candidate 42/42`**: el nivel fue tocado en todos (reproduce `v2.88.47`/`v2.88.48`) |
| `stopEvaluatedOnTouch` | **`42/42` (`1.000`)** | `STRUCTURAL_STOP` en los motivos de **todos** los toques |
| `deciderRanOnTouch` | **`42/42` (`1.000`)** | el decider dejó huella en todos los toques |
| `stopFiredNotFilled` | `26/42` (`0.619`) | el stop disparó sin materializar: los `23` del caso C **+** `3` que sí materializaron en otro tick |
| Desambiguación (capa v5) | `{ruta_ambas: 38, ruta_mae: 4}` | `ruta_mark = 0`: la ruta es el **MAE persistido** |
| `stop cambió / break-even` | `7 / 6` | el trailing apretó el stop en una minoría |
| `días hasta el primer toque` | media `5.24` · mediana `0.00` | el toque suele ser el propio día del cierre |
| Concentración | `9` símbolos · top `0.33` · top semana `2025-W12` `0.19` | — |

**Desglose por año** (todos `fragile` o `insufficient_draws`): `2022 n=19 -0.7800` · `2023 n=2 -0.5783` · `2024 n=2 -0.5251` · `2025 n=15 -0.7091` · `2026 n=4 -0.7702`. **Por edad:** `1-3 n=1 -0.8236` · `4-10 n=24 -0.8136` · `11-30 n=14 -0.8767` · `>30 n=3 +0.7375`.

### 2.3 Lectura honesta

- **La separación A/C de `v2.88.49` FUNCIONA sobre datos reales.** El añadido de `v2.88.49`-absorbido era la ruta `orden_creada_sin_fill` (leer el INTENT durable por ciclo). Medido: **`A = 0`**, **`C = 23`**. Es decir, en los `42` `THESIS_EXIT` el stop disparó, el spine **creó siempre** el `ExitOrder` durable del ciclo, y lo que falló fue la **ejecución aguas abajo** (no hubo fill). La hipótesis "el stop se evaluó pero no se creó orden" queda **descartada en esta muestra**.
- **El hallazgo de `v2.88.47`/`v2.88.48` se reproduce** con el universo corregido: `candidate 42/42`, `stopEvaluatedOnTouch 42/42`, `deciderRanOnTouch 42/42`. La duplicidad semántica nivel↔stop sigue vigente (deuda).
- **La corrección PIT cambia la muestra y por tanto reescribe conclusiones.** El `n` global de `THESIS_EXIT` pasa de `38` a `42` sólo porque `2026` entra en el universo; la expectancy bruta pasa de `-0.7087` a `-0.7150`. Las cifras viejas **no** se reutilizan.
- **Nada de esto es citable como punto.** La banda global de R cruza el cero (`pointCitable=false`); los cubos son `fragile` por `n` pequeño.

---

## 3. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest` DÍA-D + guards + PIT + monitor (`test_dia_d_*`, `test_dia_d_bump_guard`, `test_v2_87_release_log`, `test_v2_93_pit_watch`, `test_universe_point_in_time*`, `test_auto_operational_monitor/audit`) | **277 passed** |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** (`659` ficheros) |
| `mypy` (gate CI: `domain/market/infrastructure/application/src` + `api-python/src`, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| `pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` (PG real, local; el test que rompió el attempt 1 del CI) | **2 passed** — `full_day` **`8.02 s`** (el día cierra `BUY→SELL` con el arnés de viaje completo, §7) + `restart` `22.63 s` |
| Web `vitest` (`src/features/auto-monitor`) | **22 passed** (7 ficheros) |
| `@bolsa/shared` build | limpio |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`24` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| `@bolsa/shared` `vitest` (`auto-operation-story.test.ts`) | **6 passed** |
| **Determinismo del re-pipeline** | `draw-00…draw-11` **byte a byte idénticos** entre `v2_94` run1 y run2; band artifact igual salvo `crossCheck` (run1 con `--check-against`): `sha256` normalizado `42A77E8F780CE9617848EB7AA09AFAF58E3FC0F914F164BEC45047685D2C9BBD` |
| **Determinismo del plegado** | `sha256 thesis-exit-v5 = F865106DCA7C4D05F605A1B11D2B75F68DFCCFF067551AA3AB0456F03CDBBF6F` (`184 445 B`); `sequences = 2268FA79F4A1151C23EABF7655B70866C8F375A9795906B048B7209DC6DBC2B3` (`291 275 B`) |
| **`Δ motor = 0` (`replay-repro` LOCAL)** | **`REPRODUCIDO`** — fixture congelado (`20` instrumentos, `25 700` barras) re-sembrado en una **BD efímera** (`bolsa_v1_repro`, `DROP/CREATE` antes de cada corrida); `assert-artifact` ⇒ `240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0` (`3 445 622 B` CRLF) / `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (LF) = **idéntico al sello**; **dos** corridas ⇒ **byte a byte idénticas** |
| **`Δ motor = 0` (árbol)** | `git diff` de `auto_simulation_worker.py`/`simulated_broker.py`/`replay_oos.py`/`sim_durable_store.py`/`market_operability.py`/`auto_v2_entry.py`/`v2_87_…` = **vacío**; la inyección de seed de `v2_94` se **restaura byte a byte** tras cada sorteo |
| **`Δ motor = 0` (confirmado por CI)** | `Release tag CI` del tag `v2.88.50-beta` — **attempt 1 ROJO** en `lifecycle-pg` por un flake del **arnés** (§7) con `replay-repro` **verde**; `attempt 2` (`935c76a0`) **ROJO** en `lifecycle-pg` por el **Golden Day 2.0 con precio real** (§8), también con `replay-repro` **verde**; **el run del tag re-anclado** ([`37297920781`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37297920781), `f48975bb`, `attempt 1`) **`SUCCESS`** con `replay-repro` `REPRODUCIDO` `1E3ADAC2…` ⇒ **cita en §9 (POST-TAG)** |
| **Golden Day 2.0 (precio real) tras el fix** | `pytest apps/api-python/tests/test_golden_day_v2_process_pg.py` ⇒ **2 passed** en `17 s` (antes: `1 failed` en `136 s`; el día **no** cerraba y el test agotaba los `_CLOSE_POLLS`) |
| **Suites PG del invariante de equity (`applied_fill_equity`)** | `test_a9_scheduler_process_pg_zero_human.py` + `test_auto_scheduler_real_pg_zero_human_intervention.py` ⇒ **4 passed** en `32 s` |
| **Unitarios puros (`packages/py`)** | `domain` + `market` + `analytics` + `application` + `ai` ⇒ **4006 passed, 1 skipped** (`test_vectorbt_optuna.py` no colecta: DLL de `numba` bloqueada por Smart App Control en el host de medición, ajeno al sello) |
| **`apps/api-python/tests` (pase de directorio completo)** | **922 passed** (`test_workspaces.py::test_workspaces_crud` sólo rojo por contaminación de BD entre tests del pase completo; aislado ⇒ **1 passed**) |

> **Nota de método (auditable).** Durante el primer intento, el `replay-repro` local dio artefactos **distintos** del sello. La causa **medida** fue que la corrida **run2** de `v2_94` estaba **en vuelo** e inyectaba temporalmente `seed=fill_seed(bar_tick_now + k, symbol)` en `auto_simulation_worker.py` (la inyección que restaura byte a byte al terminar cada sorteo): el replay importaba el worker con el seed desplazado. Una vez terminó `v2_94` (árbol restaurado), el replay reprodujo el sello **byte a byte** en dos corridas. Se declara para que un auditor no repita el falso negativo.

---

## 4. Límites declarados (NO se cierran aquí)

- **El arreglo PIT es real pero estrecho:** para el provider actual la **poda** por día es casi siempre **no-op** (`active_until` = última barra); sólo cambia la muestra del año **incompleto** (`2026`). La capacidad queda instalada para un `active_until` real (delistados), no ejercitada por el dato actual.
- **A vs C separados, causa NO nombrada:** se mide que en `C` se creó el INTENT y no hubo fill, pero **no** se nombra *por qué* no hubo fill (rechazo de cola, corte de parcial, latencia). `orderCreated` mide **existencia** de INTENT, no desenlace.
- **`decisionRoute` NO es contrafactual** y se **LEE**, no se re-ejecuta.
- **El nivel congelado SIGUE siendo el stop inicial** (deuda de `v2.88.45`…`v2.88.48`); `stopBasisMismatchR` sigue `P3`.
- **`n` pequeño:** `42` observaciones pooled (no `42` operaciones independientes); todos los cubos `fragile`.
- **REPLAY/OOS ≠ PAPER:** no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **NO** se emite.
- **AUTO UI 1.0 es un PILOTO:** el view-model es puro y no re-deriva cifras; **no** toca motor ni **borra** pantallas. La migración del resto de vistas queda como trabajo posterior.
- **La banda mide ruido del SORTEO del venue**, no incertidumbre de mercado ni del futuro; el determinismo (byte a byte) **no** es validez.

---

## 5. Cómo se reproduce

```bash
# 1) Re-pipeline del universo PIT corregido (12 sorteos con detalle v7), DOS corridas.
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail --from-year 2021 --to-year 2026 \
  --out-dir operability_runs/dia-d-auto-pit-run1 \
  --out operability_runs/dia-d-auto/multi-band-pit-run1.json
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail --from-year 2021 --to-year 2026 \
  --out-dir operability_runs/dia-d-auto-pit-run2 \
  --out operability_runs/dia-d-auto/multi-band-pit-run2.json
#    Los 12 draw-XX/multi-cycles.json deben ser byte a byte idénticos entre run1 y run2.

# 2) Plegar los THESIS_EXIT al artefacto v5 + volcar secuencias (dos veces = mismo sha256).
uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \
  --out-dir operability_runs/dia-d-auto-pit-run1 \
  --out operability_runs/dia-d-auto/thesis-exit-pit-run1a.json --sequences

# 3) Δ motor = 0 contra el fixture congelado (BD EFÍMERA, no se toca la BD de desarrollo).
#    El replay ESCRIBE estado durable, así que cada corrida parte de una BD recién sembrada:
#    se crea `bolsa_v1_repro` en el mismo PostgreSQL del `.env`, se apunta DATABASE_URL a ella,
#    se siembra el fixture y se corre v2_87. Repetir ⇒ MISMO sha256 (se ofusca la credencial).
export DATABASE_URL="<postgresql+psycopg>…/bolsa_v1_repro"   # BD efímera creada para la prueba
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py seed \
  --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson   # ⇒ 20 instr · 25 700 barras
WATCH="$(uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py \
  watch --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson)"
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py \
  --json --watch "$WATCH" --out artifacts/repro/replay-1.json
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py \
  assert-artifact --file artifacts/repro/replay-1.json   # ⇒ REPRODUCIDO (24066225…)
#    Repetir el bloque desde el DROP/CREATE ⇒ replay-2.json byte a byte idéntico.
#    (El orquestador que automatiza DROP/CREATE + siembra + dos corridas fue ad-hoc y vive
#     en `artifacts/repro/`, gitignored; el CI del tag corre la versión canónica.)
```

---

## 6. Sello

- **Añadidos:** `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` (+ test), `apps/web/src/features/auto-monitor/dia-d-auto-feedback-heatmap.test.ts`, `apps/web/src/features/auto-monitor/auto-reservation-panel.test.tsx`, `apps/api-python/tests/test_v2_93_pit_watch.py`, `docs/engineering/evidence/v2.88.50/README.md`.
- **Modificados:** `packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py` (`round6` para **cantidades**: el fold y `coerce_applied_fill_fact` dejan de cuantizar a 4 decimales; el **precio** y el `realized_pnl` siguen en `round4` — §8), `packages/py/application/src/bolsa_application/universe_point_in_time.py` (`candidate_ids`/`ids_by_day`/`eligible_days_by_symbol`), `universe_point_in_time_catalog.py` (`all_members`), `v2_91`/`v2_92`/`v2_93` (watch PIT por día + poda), `auto_operational_monitor.py` (`_reservation_view` con las `5` banderas), ruta `auto_operational_monitor.py` (DTO), `packages/shared/src/cognitive/auto-operational-monitor.ts`, `auto-monitor-page.tsx` (`enabled: mode === "current"` + pestaña «Operación»), `dia-d-auto-toolbar.tsx`, `auto-reservation-panel.tsx`, `dia-d-auto-feedback-heatmap.tsx` (`formatCellTooltip`), `dia-d-auto-feedback-panel.test.tsx` (`waitFor`), `packages/shared/src/cognitive/index.ts`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `v2_89`…`v2_97` (`meta.bump`), `package.json` (`2.11.50-beta`), `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` (arnés determinista con **viaje completo**, §7), `apps/api-python/tests/applied_fill_equity.py` (notional al **quantum del dinero**, §8), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado; la costura `capture_cycle_detail` sólo **lee** estado ya producido y su default sigue `False`; el `round6` del ledger vive en un **read-model** (sólo se consume en `readopt`/reconciliación, que en el replay parten de una BD recién sembrada) y su inercia sobre el artefacto está **medida** por ablación (§8.4); `replay-repro` **reproducido byte a byte** contra el fixture congelado (§3/§8.4, dos veces).
- **Tag:** `v2.88.50-beta` (anotado) → commit `f48975bb`; **`Release tag CI` run [`37297920781`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37297920781) VERDE** y **`GitHub Release` publicado** — cita completa **POST-TAG en §9** (este fichero, dentro del tag, la declara así por el límite estructural).

---

## 7. Incidencia de sello (declarada): rojo de `lifecycle-pg` por un flake del ARNÉS, y re-anclaje del tag

**Qué pasó.** El primer `Release tag CI` del tag `v2.88.50-beta` (run [`37277722008`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37277722008), **attempt 1**) cerró **ROJO**: `10` jobs en verde — incluido **`replay-repro`**, la certificación de `Δ motor = 0` en Linux —, `playwright` integrado `skipped` por diseño, y **`lifecycle-pg` en rojo**, que arrastra al agregado `certify`. El rojo es **un único test**:

```
FAILED apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py::test_a9_scheduler_process_full_day_pg_zero_human
AssertionError: el día AUTO del proceso debe cerrar el ciclo BUY→SELL (lados=['buy'], ticks=117, events=4, ledger=9)
```

**La causa es del ARNÉS de certificación, NO del sello.** El venue SIM sortea su ruido **por `(barra, instrumento, lado)`** (`draw_queue_noise(seed, side, instrument_id)`), pero la barrida determinista `_filling_instrument_id` sólo exigía que llenara la **entrada** (`side="buy"`) ⇒ el cierre del día quedaba a una **moneda al aire por barra**. Medición pura (sin BD ni proceso) con la MISMA derivación que el motor (`fill_seed(bar_tick(now, "1d"), id)` sobre `side=buy`/`side=sell`, `fill_chunks=_FILL_CHUNKS`, `qty=100`):

| Barra | `inst-a9proc-0000000000` BUY | `inst-a9proc-0000000000` SELL | Candidatos `0..63` que llenan BUY | Candidatos con **viaje completo** |
| --- | --- | --- | --- | --- |
| `20730` (`2026-10-04 UTC`) | llena | llena | `59` | `52` |
| `20731` (`2026-10-05 UTC`) | llena | **NO llena** (`fills=()`) | `54` | `45` |
| `20732` (`2026-10-06 UTC`) | llena | llena | `60` | `44` |

El candidato que elige la barrida es el **primero** (`inst-a9proc-0000000000`): el `2026-10-05` llenaba el **BUY** y tenía el **schedule de SELL VACÍO** ⇒ en la barra corriente **ninguna** salida podía materializarse y el gate «ciclo BUY→SELL» **no podía** pasar: de ahí `lados=['buy']` con `117` ticks y `0` ventas. El **mismo árbol** dio `lifecycle-pg` **VERDE** el `2026-10-04` (run [`37221439959`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37221439959)): **no** es una regresión de `v2.88.50`, es la **fecha**.

**Fix (la causa, no la aserción).** `_filling_instrument_id(..., round_trip=True)` exige que **AMBOS lados** llenen en las barras probadas. El **día completo** lo pide (⇒ elige `inst-a9proc-0000000002`, con viaje completo en `20731`/`20732`); el **restart** NO (retiene la posición con `AUTO_ENGINE_SIM_EXIT_AFTER_TICKS=1000`: sólo necesita la entrada). **Ninguna aserción se relaja** — el día sigue teniendo que cerrar `BUY→SELL`, quedar **plano** y con `pending == 0` —; el arnés queda documentado en el propio fichero con las cifras de esta tabla.

> **Nota de alcance:** el cambio vive en `apps/api-python/tests/` (**arnés**), no en `packages/` ni en el motor. El freeze del runner se **re-ancla** porque `appsHash` cambia con el fichero de test.

**Re-anclaje del tag (declarado).** El tag `v2.88.50-beta` ya estaba empujado y su `Release tag CI` era **rojo**, así que el tag se **re-ancló UNA vez**: `d0acc7ab` (freeze previo) → **`935c76a0`** (freeze re-anclado al fix del arnés `356aaf2a`). **Ningún `Release` de GitHub se había publicado** (el sello no estaba cerrado) y la corrección es **sólo del arnés**. Ese run también cerró **rojo** — por otra causa, ya del **producto** — y forzó un **segundo** re-anclaje que describe la **§8**; el CI del tag finalmente re-anclado (`f48975bb`) **salió VERDE** y se cita en la **§9** (POST-TAG).

---

## 8. Incidencia de sello (declarada): `lifecycle-pg` ROJO en el `attempt 2` por el Golden Day 2.0 con PRECIO REAL, y el defecto real que destapa

### 8.1 Qué pasó (citado)

El **segundo** `Release tag CI` del tag (`d0acc7ab` → re-anclaje `935c76a0`), run [`37282852860`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37282852860), cerró **ROJO**: `11` jobs en verde — incluido **`replay-repro`** y el arnés A9 ya corregido (§7) — y **`lifecycle-pg` en rojo**, que arrastra al agregado `certify`. El rojo esta vez **no** es del arnés: es el paso dedicado del **Golden Day 2.0** y cae **el segundo** de los dos tests del fichero (el primero pasó: `.F`):

```
FAILED apps/api-python/tests/test_golden_day_v2_process_pg.py::test_golden_day_v2_real_price_process_opens_and_closes_the_book_pg
AssertionError: el día con precio real debe cerrar los planes durables (time_exit); barras presentes al cierre=9
  ...
  bolsa_domain.errors.PermanentRejectionError: No tienes suficientes acciones. En cartera: 4e-06
```

**Reproducido en local el MISMO día y sobre el MISMO árbol** (`2 failed`→`1 failed, 1 passed` en `136 s`): **no** es un artefacto del runner, es un rojo **determinista del día** sobre el árbol sellado.

### 8.2 La causa raíz (medida, no supuesta): el libro publicaba MÁS posición que la cartera

El modo **precio real** (`AUTO_ENGINE_SIM_REAL_PRICE=1`) produce **tamaños fraccionarios** y el `SIMULATED` venue llena en **tranchas**. Las cantidades viven en `execution_events.qty` / `sim_fill_finance_context.quantity` como `Numeric(18, 6)` — el **quantum del dinero** —, pero el ledger de posición (`position_ledger.py`) **cuantizaba a 4 decimales** (`round4`, el quantum de la *casa*) tanto en `coerce_applied_fill_fact` como en el **fold**. Consecuencia medida en la fase de cierre:

| Vista | Cantidad |
| --- | --- |
| Cartera real (`positions.quantity`) = Σ tranchas aplicadas | **`490.000024`** |
| Posición canónica del libro (fold a 4 dp) | **`490.0001`** |

Al reiniciar (FASE 2 del test), el worker **re-adopta** la posición del libro canónico y **re-ancla** el `remaining_quantity` del plan durable a esa cantidad: la salida pide `490.0001` contra una cartera de `490.000024` ⇒ el **último chunk** muere con `PermanentRejectionError: … En cartera: 4e-06`, la posición **nunca** queda plana y el día **no cierra**. El `4e-06` del mensaje es exactamente el residuo `490.0001 − 490.000024` (`0,000076`) partido por el tamaño de chunk.

**Por qué el 04 salió verde y el 05 rojo (mismo árbol).** El arnés del Golden Day elige su instrumento con la barrida determinista `_filling_instrument_id`, que **depende de la barra corriente**; la barra cambia el **schedule de tranchas** del venue y por tanto **el residuo sub-4dp** de la suma aplicada. El mismo árbol dio `lifecycle-pg` **VERDE** el `2026-10-04` (run [`37221439959`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37221439959), tag `v2.88.48-beta`) y **ROJO** el `2026-10-05` (run `37282852860`). Es un **defecto latente del motor destapado por el dato**, no una regresión de `v2.88.50`: el ledger venía redondeando a 4 dp desde `v2.40.5`.

### 8.3 El fix (la causa, no la aserción)

1. **`packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py`** — nuevo `round6` (6 decimales) y uso en **cantidades** (`quantity`, `realized_qty`, `sold_qty`, `unmatched_exit_qty`, `remaining_qty`) y en `coerce_applied_fill_fact(quantity=…)`. Los **precios** (`round4(px)`) y el **P&L** (`realized_pnl=round4(…)`, magnitudes monetarias) **no** cambian: la cantidad es del mundo del DINERO (`Numeric(18,6)`), el precio y el P&L del de la casa. Efecto: `Σ fills aplicados` **es** la posición de la cartera, la salida pide exactamente lo que hay y el día cierra.
2. **`apps/api-python/tests/applied_fill_equity.py`** — el notional de cada fill se mide con el **quantum del dinero** (`ROUND_HALF_UP` a `0.000001`), porque `ledger_entries.amount`/`transactions.total` son `NUMERIC(18, 6)`: sumar los productos de 12 decimales dejaba un residuo de `≈2e-6` en una jornada real de `22` fills que el invariante de equity (tol `1e-6`) leía como descuadre. Medido así el invariante certifica el dinero al último decimal representable y sigue siendo una fuente **independiente** del `cash` (sale de eventos + contexto, no de las filas del ledger). **Medido sin este cambio: `equity 99641.830608 != initial+realized+unrealized 99641.830610`.**

**Ninguna aserción se relaja**: el día sigue teniendo que abrir, cerrar `BUY→SELL`, quedar **plano** (`positions = 0`), con `pending = 0` y sin fills sin materializar, y el invariante de equity sigue con la misma tolerancia.

### 8.4 Ablación declarada (qué NO se aplicó, y por qué): `position_state.py` NO se toca

Se probaron **tres** variantes y se midió cada una contra el fixture congelado (`assert-artifact`, `replay-repro` local, BD efímera `bolsa_v1_repro` `DROP/CREATE`):

| Variante | Golden Day 2.0 real | `replay-repro` | Veredicto |
| --- | --- | --- | --- |
| `position_ledger.py` (`round6` en cantidades) | **2 passed** | **`REPRODUCIDO`** `24066225…` (`3 445 622 B`) | **APLICADA** |
| `position_state.py` (`_round6` en `quantity`/`remaining_quantity`) | 2 passed | **NO reproducido** `1FC2CAF2…` (`3 755 749 B`): `book.cancelReleaseDays` `57 → 109` y la primera divergencia en `perDay[99]` (`RELEASE` `fill`↔`cancel`) | **DESCARTADA** (rompe `Δ motor = 0`) |
| Ambas | 2 passed | **NO reproducido** (idéntico a la anterior: el `position_state` explica **todo** el delta) | — |

La segunda variante cambia el **camino caliente de salida** (`remaining_quantity` a 6 dp ⇒ otra partición de tranchas, otra contabilidad de liberación de reservas) ⇒ `Δ motor ≠ 0`. La primera es inerte por construcción **y medido**: el ledger es un **read-model** que sólo se consume en `readopt`/reconciliación de posición, y el replay arranca de una BD **recién sembrada** (sin fills aplicados) ⇒ la lectura canónica es vacía y el artefacto sale **byte a byte** igual. Se declara porque un auditor debe saber que la inercia está **medida** (dos corridas) y no argumentada.

### 8.5 Verificación local (PG real)

```
pytest apps/api-python/tests/test_golden_day_v2_process_pg.py                         2 passed  (17 s)
pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py \
       apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py   4 passed  (32 s)
pytest packages/py/analytics packages/py/application packages/py/domain \
       packages/py/market packages/py/ai --ignore=…/test_vectorbt_optuna.py           4006 passed, 1 skipped
pytest apps/api-python/tests                                                       922 passed
ruff check packages/py apps/api-python --config pyproject.toml                     All checks passed!
lint-imports --config packages/py/.importlinter                                    4 kept, 0 broken (659 ficheros)
mypy (gate CI)                                                                     Success: no issues found in 531 source files
replay-repro local (fixture v2.88.7, BD efímera, 2 corridas)                       REPRODUCIDO 24066225… (3 445 622 B)
```

### 8.6 Segundo re-anclaje del tag (declarado)

El tag `v2.88.50-beta` se **re-ancló una segunda vez** (el primer re-anclaje lo describe §7): el árbol del fix de este §8 pasa a ser el tip. **SHAs publicados:** fix de producto §8.3 = `40876dac` (`apps` `e683160a…` / `packages` `7633be63…`); re-anclaje del freeze de la ventana = `f05459e3` (`chore(ventana)`, pinnea `commit: 40876dac` y **no** mueve el árbol porque `scripts/` no participa del pin); commit de sello/tag = `f48975bb` (POST-TAG respecto al tag anterior). **`Release` de GitHub:** publicado **después** del verde (§9). El cambio de §8.3 **no** es del arnés (toca `packages/py/analytics` y un helper de tests), así que se declara como **fix de producto**: el ledger deja de publicar más posición que la cartera cuando el tamaño es fraccionario.

**Verificación local sobre el árbol del sello (`f05459e3`, repetida tras el re-anclaje):** `uv run pytest apps/api-python/tests/test_golden_day_v2_process_pg.py -q` ⇒ **`2 passed in 16.94s`** (incluye el test **con precio real** que cayó en `attempt 2`); `uv run pytest apps/api-python/tests/applied_fill_equity.py` ⇒ verde; `replay-repro` local (fixture `v2.88.7`, BD efímera `bolsa_v1_repro`, `DROP/CREATE` + siembra entre corridas) ⇒ **`REPRODUCIDO`** `240662250347A2AA…` (`3 445 622 B`) en **las dos** corridas, `sha256` idéntico ⇒ **`Δ motor = 0`** re-confirmado sobre el árbol ya arreglado; `node --test scripts/lib/window-forward.test.mjs` ⇒ **`25 passed`**.

---

## 9. CI DEL TAG (POST-TAG): `Release tag CI` del tag re-anclado — **TODO VERDE**

El tag re-anclado (§8.6, tag → commit `f48975bb`) disparó el `Release tag CI` run [`37297920781`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37297920781) (`ref=refs/tags/v2.88.50-beta`, `attempt 1`, `2026-10-05T10:39:02Z → 10:47:25Z`) ⇒ **`SUCCESS`**.

| Job | Resultado |
| --- | --- |
| `python` (ruff/imports/mypy/pytest offline) | **`4537 passed, 45 skipped`** (`132.43 s`) · `ruff All checks passed!` · `imports 4 kept, 0 broken` · `mypy` limpio |
| `lifecycle-pg` | `Golden Day 2.0` **`2 passed in 16.71 s`** (incluye el test **con precio real** que cayó en el `attempt 2`) · lote `190 passed` (con el arnés A9 de §7 ya corregido) · `200 passed, 1 xfailed` (34 ficheros PG) · `account-isolation 45 passed` · `multiprocess AUTO 1 passed` |
| `replay-repro` | **`VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)`** `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (`3 340 728 B` LF = sello `3 445 622 B` CRLF) ⇒ **`Δ motor = 0` confirmado por CI** |
| `frontend` (typecheck/lint/test/build + contract:check) · `shared` · `decision-spine` · `a7-gate` · `dr-verify` · `security` (gitleaks) · `playwright (mock E2E)` · `certify` | **`success`** (los `11` jobs) |
| `playwright (integrated E2E, opt-in)` | `skipped` **por diseño** |

**Cadena de re-anclajes del tag (auditable):** `d0acc7ab` (freeze del sello funcional `6915ef66`) → `935c76a0` (`§7`: re-anclaje del freeze al fix del **arnés** `356aaf2a`) → `f48975bb` (`§8`: fix de **producto** `40876dac` + freeze de la ventana `f05459e3`, que pinnea `commit: 40876dac`). **Ningún `Release` de GitHub se había publicado** en ninguno de los dos re-anclajes.

**`GitHub Release` `v2.88.50-beta` publicado** (pre-release) con esta cita.

> **Límite estructural (declarado):** `Release tag CI` **sólo** corre al **empujar** el tag ⇒ **ningún tag puede contener su propio resultado de CI**. Este fichero, **dentro** del tag, declara la cita como `POST-TAG`; la cita real viaja en **esta** §9 (escrita en `main` **después** del tag) y en el **`Release`**.
