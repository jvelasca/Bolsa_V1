# Entrega a auditoría externa (MIA) — `v2.88.50-beta` · AUTO · **DÍA-D-4: cierre PIT por día, proyección de mediciones en reservas, 2 fixes de UI y arranque AUTO UI 1.0**

> **Fecha:** 2026-10-05 · **Producto:** V2.88.50-beta · **Package:** `2.11.50-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.49-beta` (**absorbido**: separación A/C del `THESIS_EXIT`, commit `e70b23fa`, **sin tag ni medición**) → `v2.88.48-beta` (huella de decisión por ciclo).
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`/**`"UNKNOWN"`**, **nunca** `0`; el neto sólo se afirma con fricción `COMPLETE`.
> **`Δ decisión motor = 0`.** Ningún fichero de motor tocado. **`Δ motor = 0` DEMOSTRADO LOCALMENTE Y CONFIRMADO POR CI:** el artefacto congelado de `replay-repro` **se reproduce byte a byte** contra el fixture sellado.
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.50/README.md`](./evidence/v2.88.50/README.md) (`§1`–`§9`).
> **Nota de auditabilidad:** como en `v2.88.46`/`v2.88.47`/`v2.88.48`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). En **este** sello la cita es **doble**: la del tag tiene **dos re-anclajes declarados** (`§7`/`§8` de la evidencia) y su run final **VERDE** se publica en el **`Release`** y en `main` **`745d2a94`** (evidencia `§9`) ⇒ **el objeto se cierra sin placeholders**.

---

## 1. Qué se entrega (y qué NO)

**Se entregan** cinco bloques, todos **sin tocar el motor**:

1. **PIT por día (raíz del sesgo de muestra).** El watch multianual se anclaba al **último día del año** (`YYYY-12-31`): un año **incompleto** (`2026`) tiene ese ancla en el futuro ⇒ **ningún** instrumento elegible ⇒ muestra declarada `sin_universo_pit`; y dentro de un año, anclar a `31-dic` **excluía** a los **deslistados a mitad de año**. Ahora `candidate_ids(ene-01, dic-31)` + `eligible_days_by_symbol` resuelven la ventana de elegibilidad **por día** y **podan** `bars_by_symbol` (cinturón y tirantes), aplicado a `v2_91`/`v2_92`/`v2_93`.
2. **Proyección de las `5` banderas de medición en reservas.** `reason`/`caller`/`aged`/`graceWindow`/`reconciliation` **Measurement** viajan del audit al monitor (`_reservation_view`), al DTO de ruta (`AutoMonitorReconciliationDto`) y al tipo `@bolsa/shared`; un `UNKNOWN` deja de ser indistinguible de `"?"` (la UI pinta `NO MEDIDO`).
3. **Dos fixes de UI.** La pestaña DÍA-D **deja de sondear** `/auto/operational-monitor` cada `20 s` (`enabled: mode === "current"`), y el tooltip de una celda `NOT_MEASURED` pinta **`sin dato`** (no `0 ciclos · 0 errores`).
4. **Rojo de `main` arreglado en la CAUSA.** `dia-d-auto-feedback-panel.test.tsx` asertaba la query de detalle antes de que el efecto la disparara; se corrige con `waitFor`, **no** se relaja la aserción.
5. **AUTO UI REFACTOR 1.0 (piloto).** View-model **puro** `buildAutoOperationStory` (`@bolsa/shared`) que pliega los DTO existentes en **una operación** de `13` etapas (`OPPORTUNITY → … → EXPLANATION`), accesible como pestaña **«Operación»**. **No** elimina pantallas.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (§4: `Δ motor = 0` demostrado y confirmado por CI).
- **NO** hay contrafactuales: `decisionRoute`/`orderCreated` se **LEEN** del estado ya producido por el worker; no se re-ejecuta la decisión.
- **NO** se nombra la **causa** de que un `orden_creada_sin_fill` (caso **C**) no llegue a fill (rechazo de cola, corte de parcial, latencia): `orderCreated` mide **existencia** de INTENT, no desenlace.
- **NO** se cierra la deuda `stopBasisMismatchR` ni la duplicidad semántica nivel↔stop; **NO** se emite `CONFIRMED`.
- **NO** se migra el resto de la UI: el piloto es **una** pestaña.
- **NO** se reutilizan las cifras viejas: la corrección PIT **cambia la muestra** y las cifras citadas en `v2.88.41`…`v2.88.49` (`38`, `19/19`, `expectancy`) quedan **re-medidas**.

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1`.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| Helpers PIT puros | `packages/py/application/src/bolsa_application/universe_point_in_time.py` | `candidate_ids(universe, start, end)` (ids cuya ventana de elegibilidad **intersecta** el rango) e `ids_by_day(universe, days)` + `eligible_days_by_symbol` — fail-closed y deterministas. |
| Catálogo PIT | `universe_point_in_time_catalog.py` | `all_members` (superconjunto del año, no sólo supervivientes). |
| Arneses multianuales | `v2_91_dia_d_longitudinal.py`, `v2_92_dia_d_attribution.py`, `v2_93_dia_d_multi.py` | `watch_by_day` por día elegible; el watch del motor pasa a ser la **unión** y `bars_by_symbol` se **poda** por símbolo; `watchSource`/cobertura declarados; `limits` pasa de «anonymous POR AÑO» a **per-day**. |
| Banderas en reservas | `packages/py/application/src/bolsa_application/auto_operational_monitor.py` | `_reservation_view` copia por evento las `5` `*Measurement` desde `payload`. |
| DTO de ruta | `apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py` | `AutoMonitorReconciliationDto` gana los `5` campos (`str`, default `"UNKNOWN"`). |
| Tipo shared | `packages/shared/src/cognitive/auto-operational-monitor.ts` | los `5` campos en `reconciliations`. |
| UI reservas | `apps/web/src/features/auto-monitor/auto-reservation-panel.tsx` | `formatMeasurementLabel(row.reasonMeasurement)`/`callerMeasurement`; `aged`/`graceWindowSeconds` con su medición; `UNKNOWN` ⇒ `NO MEDIDO`. |
| UI monitor | `auto-monitor-page.tsx` | `useAutoOperationalMonitor({ enabled: mode === "current" })` + pestaña **«Operación»**. |
| UI heatmap | `dia-d-auto-feedback-heatmap.tsx` | tooltip de celda `NOT_MEASURED` ⇒ `sin dato`. |
| Test flaky de `main` | `dia-d-auto-feedback-panel.test.tsx` | `waitFor` sobre la query de detalle (causa, no aserción). |
| Piloto UI 1.0 | `packages/shared/src/cognitive/auto-operation-story.ts` + `auto-operation-story-panel.tsx` | view-model puro `buildAutoOperationStory` (13 etapas, «NO MEDIDO nunca es 0») + panel. |
| Guardián | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` en `v2_89`…`v2_97` (`2.11.50-beta`). |
| Tests nuevos | `test_v2_93_pit_watch.py`, `test_universe_point_in_time*`, `auto-operation-story.test.ts`, `dia-d-auto-feedback-heatmap.test.ts`, `auto-reservation-panel.test.tsx` | caso «deslistado a mitad de año sólo opera su tramo» + los dos fixes de UI con test rojo→verde. |
| Ledger / artefacto | `dia-d-multi-cycle-ledger-v7` (aditivo sobre `-v6`), `dia-d-thesis-exit-v5`, `dia-d-thesis-stop-sequences-v2` | `orderCreated` + `decisionRoute` ∈ {`materializado`, `orden_creada_sin_fill`, `stop_evaluado_sin_orden`, `stop_evaluado_sin_materializar`, `stop_no_evaluado`, `sin_toque`, `sin_traza`} — tupla **cerrada**; un hueco es `None`, **nunca** `0`. |

---

## 3. Medición real (PostgreSQL, `K = 12` sorteos, años `2021-2026`)

### 3.1 Delta PIT (banda multirregimen, `dia-d-multi-band-v1`)

| Cubo | Anclaje `31-dic` (OLD) | PIT por día (NEW) | Lectura |
| --- | --- | --- | --- |
| `2021` | vacío `12/12` | vacío `12/12` | sin barras PIT en la ventana (declarado) |
| `2022` | `-0.4363` (`49.5` ciclos) `citable` | **idéntico** | año completo ⇒ el ancla a `31-dic` ya era correcta |
| `2023` | `+0.3658` (`12.25`) no citable | **idéntico** | ídem |
| `2024` | `+1.2856` (`7.42`) `citable` | **idéntico** | ídem |
| `2025` | `+0.2477` (`20.33`) no citable | **idéntico** | ídem |
| `2026` | **`NOT_MEASURED 12/12`** (`sin_universo_pit`) | **`+0.1819` (`22.25`) no citable** | año **incompleto**: el ancla a `31-dic` era futura |
| **GLOBAL** | `-0.0283` · ciclos `89.5` · `[-0.1813, +0.1248]` | **`+0.0111`** · ciclos **`111.75`** · `[-0.1503, +0.1695]` | banda de R `[-17.290, +19.328]` · `crossesZeroR=true` · **`pointCitable=false`** |

`crossCheck.evidenceDrift=true` contra el plegado anterior, `driftedKeys = [expectancyR, hitRate, measuredCycles, verdict, evidenceQuality]` — **esperado**: es el delta que este sello documenta.

### 3.2 Correlación DECISIÓN↔CICLO con A/C separadas (`dia-d-thesis-exit-v5`, capa v7)

Cobertura: **`42` observaciones** `THESIS_EXIT` pooled (`11/12` sorteos con celda, `42` con fricción `COMPLETE`, una estrategia `v283-window-a`, una dirección `long`, `9` símbolos).

| Métrica | Valor | Lectura |
| --- | --- | --- |
| `route` | `{materializado: 19, orden_creada_sin_fill: 23}` | **caso C = `23`**, caso **A = `0`**; el resto de rutas `= 0` |
| `routeByStructuralStopCandidate` | `candidate 42/42` | el nivel fue **tocado** en todos (reproduce `v2.88.47`/`v2.88.48`) |
| `stopEvaluatedOnTouch` | **`42/42` (`1.000`)** | `STRUCTURAL_STOP` en los motivos de todos los toques ⇒ `stop_no_evaluado = 0` |
| `deciderRanOnTouch` | **`42/42` (`1.000`)** | el decider dejó huella en todos los toques |
| `stopFiredNotFilled` | `26/42` (`0.619`) | los `23` del caso C **+** `3` que sí materializaron en otro tick |
| `stop cambió / break-even` | `7 / 6` | el trailing apretó el stop en una minoría |
| Expectancy bruta (global) | `-0.7150` (`n = 42`) | antes `-0.7087` (`n = 38`): **cambia la muestra**, no el motor |
| Concentración | `9` símbolos · top `0.33` · top semana `2025-W12` `0.19` | — |

**Desglose por año** (todos `fragile` o `insufficient_draws`): `2022 n=19 -0.7800` · `2023 n=2 -0.5783` · `2024 n=2 -0.5251` · `2025 n=15 -0.7091` · `2026 n=4 -0.7702`.
**Por edad:** `1-3 n=1 -0.8236` · `4-10 n=24 -0.8136` · `11-30 n=14 -0.8767` · `>30 n=3 +0.7375`.

### 3.3 Lectura honesta

- **La separación A/C de `v2.88.49` FUNCIONA sobre datos reales:** `A = 0`, `C = 23`. El spine **siempre** creó el `ExitOrder` durable del ciclo; lo que falló fue la **ejecución aguas abajo**. La hipótesis «el stop se evaluó y no se creó orden» queda **descartada en esta muestra**.
- **El hallazgo de `v2.88.47`/`v2.88.48` se reproduce** con el universo corregido (`candidate 42/42`, `stopEvaluatedOnTouch 42/42`, `deciderRanOnTouch 42/42`).
- **La corrección PIT reescribe conclusiones:** el `n` de `THESIS_EXIT` pasa de `38` a `42` **sólo** porque `2026` entra en el universo.
- **Nada de esto es citable como punto:** la banda global de R cruza el cero (`pointCitable=false`) y todos los cubos son `fragile` por `n` pequeño.

### 3.4 Determinismo

- **Re-pipeline:** los `12` ledgers de ciclos (`draw-00…draw-11/multi-cycles.json`) **byte a byte idénticos** entre `v2_94` run1 y run2.
- **Plegado:** `sha256 thesis-exit-v5 = F865106DCA7C4D05F605A1B11D2B75F68DFCCFF067551AA3AB0456F03CDBBF6F` (`184 445 B`); `sequences = 2268FA79F4A1151C23EABF7655B70866C8F375A9795906B048B7209DC6DBC2B3` (`291 275 B`).

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
| --- | --- |
| `pytest` DÍA-D + guards + PIT + monitor | **277 passed** |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (`659` ficheros) |
| `mypy` (gate CI, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| `pytest apps/api-python/tests/test_golden_day_v2_process_pg.py -q` | **2 passed** (`17 s`) — incluye el test **con precio real** que cayó en el `attempt 2` |
| `pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` | **2 passed** — `full_day` `8.02 s` + `restart` `22.63 s` |
| Unitarios puros `packages/py` | **4006 passed, 1 skipped** |
| `apps/api-python/tests` (pase de directorio) | **922 passed** |
| Web `vitest` (`src/features/auto-monitor`) · `@bolsa/shared` vitest | **22 passed** (7 ficheros) · **6 passed** |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`24` warnings pre-existentes) · **OK** |
| `node --test scripts/lib/window-forward.test.mjs` | **25 passed** |
| Determinismo re-pipeline / plegado | `draw-XX` idénticos · `F865106D…` / `2268FA79…` |
| **`Δ motor = 0` (`replay-repro` LOCAL)** | **`REPRODUCIDO`** `240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0` (`3 445 622 B` CRLF) / `1E3ADAC2…` (`3 340 728 B` LF) = **idéntico al sello**; **2 corridas byte a byte** |
| **`Δ motor = 0` (árbol)** | `git diff` de `auto_simulation_worker.py`/`simulated_broker.py`/`replay_oos.py`/`sim_durable_store.py`/`market_operability.py`/`auto_v2_entry.py`/`v2_87_…` = **vacío** |
| **`Δ motor = 0` (CI)** | `Release tag CI` [`37297920781`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37297920781) **VERDE**: `replay-repro` `REPRODUCIDO` `1E3ADAC2…` |

---

## 5. Límites declarados (no se cierran aquí)

1. `Δ motor = 0`; sin migración; no se mueve ningún umbral, `TOP_N` ni allocation; sin contrafactuales.
2. **El arreglo PIT es real pero estrecho:** para el provider actual `active_until` = última barra ⇒ la **poda** por día es casi siempre **no-op**; el efecto medido está en el año **incompleto** (`2026`). La capacidad queda instalada para un `active_until` real (deslistados), **no** ejercitada por el dato actual.
3. **A vs C separados, causa NO nombrada** (se mide la **existencia** del INTENT, no el desenlace del fill).
4. **`decisionRoute` no es contrafactual** y se **lee**, no se re-ejecuta.
5. **El nivel congelado SIGUE siendo el stop inicial** (deuda `v2.88.45`…`v2.88.49`); `stopBasisMismatchR` sigue `P3`.
6. **`n` pequeño:** `42` observaciones **pooled** (no `42` operaciones independientes); todos los cubos `fragile`.
7. **REPLAY/OOS ≠ PAPER:** no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **NO** se emite.
8. **AUTO UI 1.0 es un PILOTO:** el view-model es puro, no re-deriva cifras y **no** borra pantallas.
9. **La banda mide el ruido del SORTEO del venue**, no incertidumbre de mercado ni del futuro; el determinismo (byte a byte) **no** es validez.
10. **Dos re-anclajes del tag** (§7/§8 de la evidencia): el objeto sellado necesitó corregir un flake **del arnés** y, después, un defecto **del producto** destapado por CI. Ambas correcciones están declaradas con causa medida y ablación; **ninguna** aserción se relajó.

---

## 6. Sello

- **Producto:** `V2.88.50-beta`. **Package:** `2.11.50-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`).
- **Ficheros añadidos:** `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` (+ test), `apps/web/src/features/auto-monitor/dia-d-auto-feedback-heatmap.test.ts`, `apps/web/src/features/auto-monitor/auto-reservation-panel.test.tsx`, `apps/api-python/tests/test_v2_93_pit_watch.py`, `docs/engineering/evidence/v2.88.50/README.md`, esta entrega.
- **Ficheros modificados:** `position_ledger.py` (`round6` en **cantidades**; precio y `realized_pnl` siguen en `round4`), `universe_point_in_time.py`, `universe_point_in_time_catalog.py`, `v2_91`/`v2_92`/`v2_93`, `auto_operational_monitor.py`, ruta `auto_operational_monitor.py`, `packages/shared/src/cognitive/auto-operational-monitor.ts`, `auto-monitor-page.tsx`, `dia-d-auto-toolbar.tsx`, `auto-reservation-panel.tsx`, `dia-d-auto-feedback-heatmap.tsx`, `dia-d-auto-feedback-panel.test.tsx`, `packages/shared/src/cognitive/index.ts`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `v2_89`…`v2_97` (`meta.bump`), `package.json`, `test_a9_scheduler_process_pg_zero_human.py` (arnés con **viaje completo**), `applied_fill_equity.py` (notional al **quantum del dinero**), `scripts/lib/window-forward.mjs`, `CHANGELOG.md`, `CURRENT_SYSTEM.md`, `versioning.md`.

### 6.1 Cadena de commits y SHAs (auditable)

| Rol | Commit | Árboles |
| --- | --- | --- |
| Sello funcional | `6915ef66` | `apps` `cc0fdda6…` / `packages` `a706e357…` |
| Freeze del sello funcional | `d0acc7ab` | — |
| **Re-anclaje 1** — fix del **arnés** (`round_trip=True`) | `356aaf2a` | — |
| Freeze re-anclado 1 | `935c76a0` | — |
| **Re-anclaje 2a** — fix de **producto** (`round6`) | `40876dac` | `apps` `e683160a…` / `packages` `7633be63…` |
| Re-anclaje 2b — freeze de la ventana | `f05459e3` | pin `commit: 40876dac` |
| **Commit del tag** | `f48975bb` | (mismos árboles que `40876dac`) |
| Cita **POST-TAG** (evidencia `§9`) | `745d2a94` | — |

- **Tag:** `v2.88.50-beta` (anotado) → **`f48975bb`**.
- **`Release tag CI`** run [`37297920781`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37297920781) **VERDE** (`attempt 1`, `2026-10-05T10:39:02Z → 10:47:25Z`): **`11 jobs success`** + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` **`4537 passed / 45 skipped`** (`132.43 s`); `lifecycle-pg` **`Golden Day 2.0 2 passed in 16.71 s`** (incluye el test con precio real que cayó en el `attempt 2`) + lote `190 passed` + `200 passed, 1 xfailed`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0` confirmado por CI**.
- **`GitHub Release`** `v2.88.50-beta` **publicado** (pre-release).
- **Artefactos descargables** del run: `replay-oos-durable-v2.88.7` (`306 720 B`) y `release-tag-ci-summary` (`414 B`).

---

## 7. Guion de auditoría desde GitHub (paso a paso)

Todo lo anterior se verifica **sin clonar el repo**:

1. **Objeto inmutable.** Abrir el tag: `https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.50-beta` (o `…/tree/v2.88.50-beta`). El commit del tag debe ser **`f48975bb`**.
2. **Evidencia cruda dentro del tag.** Leer `docs/engineering/evidence/v2.88.50/README.md` (**`§1`–`§8`** dentro del tag). Ahí están: las **10** afirmaciones falsables con su forma de romperse, la tabla del **delta PIT**, la de **A/C**, los gates y los **dos** re-anclajes (`§7` = flake del arnés; `§8` = Golden Day con precio real).
3. **Cita del CI (fuera del tag, por diseño).** En el **`Release`**: `Release tag CI` `37297920781` **VERDE** con `replay-repro` ⇒ `Δ motor = 0`. La cita larga está también en la evidencia **`§9`**, escrita en `main` en `745d2a94`. *(El tag declara la cita como `POST-TAG` en `§3`/`§6`/`§8.6`: es el límite estructural, no un hueco.)*
4. **`Δ motor = 0` sin re-ejecutar.** Descargar el artefacto **`replay-oos-durable-v2.88.7`** del run y comprobar su `sha256` de **contenido LF** contra `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (`3 340 728 B` LF = sello `3 445 622 B` CRLF). Si coincide, el motor no se movió.
5. **Reproducción completa (opcional, requiere PostgreSQL).** Evidencia `§5` da los comandos exactos: `v2_94 … --from-year 2021 --to-year 2026` **dos veces** (los `12` `draw-XX/multi-cycles.json` deben salir byte a byte idénticos) y `v2_97 … --sequences` (debe dar `F865106D…` / `2268FA79…`). Para el replay: `replay_oos_input_fixture.py seed` + `v2_87_replay_oos_durable_cycle.py` sobre una **BD efímera**.
6. **Doctrina del hueco.** Buscar cualquier `0` donde falta el dato: no debe existir. En la UI se lee `NO MEDIDO` (reservas) y `sin dato` (heatmap); en los artefactos, `None`/`"UNKNOWN"`/`NOT_MEASURED`.
7. **Qué NO creer.** Que el determinismo valide: no lo hace (§5.9). Que `A = 0` cierre el caso A: sólo en **esta** muestra. Que la UI 1.0 sea el rediseño completo: es un **piloto**.
