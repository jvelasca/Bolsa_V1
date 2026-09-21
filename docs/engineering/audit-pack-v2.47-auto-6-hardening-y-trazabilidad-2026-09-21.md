# Audit-pack `V2.46.x` (hardening de AUTO-6) + `V2.47` (trazabilidad de ciclo) + `AUTO-7` slice 1 — `1.72.0-beta` (2026-09-21)

**Punto de partida:** tag **`v2.46-beta`** (commit de fase `a14b71d7`, tag → `5eb654b9`).
**Migración:** **SÍ** — `043_exit_identity_and_kill_state` → **`044_auto_cycle_trace`**.
**Bump:** `1.71.0-beta` → **`1.72.0-beta`**.
**Sonda de mutaciones:** [`apps/api-python/scripts/v2_44_mutation_audit.py`](../../apps/api-python/scripts/v2_44_mutation_audit.py)
(la matriz de la línea AUTO, extendida en esta pasada con M8–M18; ver §10).
**Sello:** tag anotado **`v2.47-beta`** (ver §12).

Este documento sigue la convención del repo: **lo que se midió, con el artefacto que lo produjo**. Donde algo
no se pudo medir, se declara **no medido** (no se rellena con un cero). El plan de la fase es
[`plan-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md`](./plan-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md)
y el relevo,
[`traspaso-relevo-post-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md`](./traspaso-relevo-post-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md).
Si el plan y este pack se contradicen, **manda el pack**.

---

## 0. Resumen: qué cierra esta pasada

| #   | Hallazgo / deuda                                                                                                      | Estado  | Evidencia (medida)                                                           |
| --- | --------------------------------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------- |
| 1   | `expected_value.py` **asumía geometría de LARGA** en toda su economía                                                 | CERRADO | `_risk_geometry`/`_target_r` direccionales + M8/M9/M10/**M18**               |
| 2   | La dirección del motor estaba fijada a `long` en tres sitios (dimensionado, snapshot y economía) sin una fuente única | CERRADO | `_ENTRY_DIRECTION` + `entry_direction()` (veto fail-closed de `SELL`)        |
| 3   | La parada dura vivía **en RAM** (un reinicio olvidaba el halt)                                                        | CERRADO | `_v2_load_kill_state` adopta el engagement durable + M17                     |
| 4   | La **liberación** con `reconciliation_id` no tenía emisor real                                                        | CERRADO | `POST /api/v1/risk/kill-switch/durable-release` (+ 2 tests PG)               |
| 5   | El Crash Day **no moría mid-fill** (el broker SIM liquidaba por tick)                                                 | CERRADO | matriz de inyección (6 herméticos + 2 PG)                                    |
| 6   | La concurrencia estaba probada **en sesiones**, no en **procesos**                                                    | CERRADO | `test_auto_v46_multiprocess_pg.py` (N procesos reales, 1 test)               |
| 7   | La cadena señal→PnL **no tenía identidad de ciclo consultable**                                                       | CERRADO | `cycle_id` determinista + migración `044` + M11/M12                          |
| 8   | La colisión de señales se resolvía **en silencio**                                                                    | CERRADO | journal `signal_superseded_by_candidate` + `allow_distinct_strategies` + M16 |
| 9   | No existía **auto-evaluación** por estrategia (AUTO-7)                                                                | CERRADO | `auto_self_evaluation.py` (puro) + feed + endpoint + M13/M14/M15             |
| 10  | El valor esperado **no se veía** en la cabina                                                                         | CERRADO | `expectedR`/`netExpectedCurrency` en DTO y en las dos superficies            |
| 11  | La cabina **no tenía móvil** (cero `md:`/`lg:` en los componentes clave)                                              | PARCIAL | primer slice: 6 componentes + `data-cabin-width` medible en test             |

---

## 1. El defecto de la auditoría: la economía era LARGO-only

`expected_value._risk_geometry` rechazaba `s >= e` —la geometría **invertida de una larga**— y
`estimate_trading_cost(..., direction="long")` estaba **hardcodeado**. El defecto era **latente** (el motor de
entrada AUTO también es largo-only: `decide_portfolio(direction="long")` fijo), pero es de la misma familia
exacta que el `stop_worsens` de larga que ya se corrigió en el kernel de trailing: **una pieza que solo sabe
leer una dirección**.

Qué cambia (y qué **no**):

- `_risk_geometry(direction=…)`: largo exige `stop < entry`; corto exige `stop > entry`; distancia `e − s`
  (largo) / `s − e` (corto). Un `direction` no reconocido devuelve `None` + `EV_GEOMETRY_UNMEASURED`.
- `_target_r(direction=…)`: largo `reward = t − e`; corto `reward = e − t` (el premio de una corta se mide
  **hacia abajo**). M10 lo fija: si se invierte, `test_a_short_target_r_is_measured_towards_a_lower_price`
  cae.
- `build_expected_value(direction=…)` propaga la dirección a `estimate_trading_cost`, de modo que la **pata de
  salida** de una corta se cobra sobre **su propio** stop. Nuevo motivo tipado
  **`EV_DIRECTION_UNSUPPORTED`**.
- **Fuente única** en el motor: `auto_v2_entry._ENTRY_DIRECTION: Final[Literal["long", "short"]]` y
  `entry_direction(signal)` (`BUY → long`, cualquier otra cosa → `None`). El dimensionado, el snapshot
  (`stop_distance`) y la economía leen **de ahí**: no hay dos direcciones que puedan discrepar.

**Por qué no se "arregló" habilitando SHORT**: el plan lo prohíbe explícitamente. Un `SELL` no se traduce a
largo **ni** entra al comparador: la oportunidad se declara no soportada y el motor sigue largo-only. Cuando
exista entrada corta, `entry_direction` es el único sitio donde mapearla.

**Nota de método (M18).** El test que ya existía para el coste corto
(`test_a_short_measures_its_round_trip_cost`) era **autorreferencial**: recalculaba el neto a partir del
propio `cost_currency`, así que **la mutación de la dirección del coste no lo mordía**. Se añadió
`test_a_short_is_charged_with_the_short_legs_not_with_the_long_ones`, con el **tarifario real de cuenta**
(donde el notional de salida **no** es el de entrada y long ≠ short). Sin ese test, M18 habría nacido verde y
el pack lo declararía como agujero; con él, M18 **muerde** (§10).

---

## 2. Parada dura DURABLE (P0 de la pasada anterior)

Huecos que cierra:

1. **Un reinicio olvidaba el halt.** `_v2_load_kill_state` ahora adopta el **engagement durable** al arrancar
   (con `engagement_id`, `reason` y `reengagements`) — M17 lo mide: si deja de adoptarlo, caen
   `test_the_reconciliation_failure_producer_persists_a_halt_across_a_crash` y
   `test_a_restored_halt_blocks_entry_but_not_the_protective_exit`.
2. **La liberación no tenía emisor de producción.** Ahora existe
   `POST /api/v1/risk/kill-switch/durable-release` (`DurableKillReleaseBody` →
   `DurableKillReleaseResponse`), que **exige `reconciliationId`** (`missing_reconciliation_id` si viene
   vacío), **no** habla con el proceso del worker (escribe la liberación durable y el worker la adopta en su
   siguiente turno), y responde `not_engaged` como **no-op idempotente** cuando la parada no estaba activa.
3. **`BROKER_DESYNC` sigue sin productor.** Se declara aquí: existe en el vocabulario de motivos y **ningún**
   camino de producción lo emite. No se inventó un engagement para "cubrirlo" (sería exactamente la clase de
   mentira que este repo persigue).

Golden hermético: `apps/api-python/tests/test_auto_v46_hardkill_recovery.py` (**5 tests**) — engage por el
productor real (`RECONCILIATION_FAILURE`) → persistencia → abandono del worker → **worker nuevo** sobre los
mismos stores → `HALTED` con `blocks_new_entry` (sin entrada nueva y con **salida protectora autorizada**) →
`release(reconciliation_id)` → `RUNNING`, verificando `engagement_id`/`reason`/`reengagements`.

Gemelo PG: `test_auto_v46_hardkill_recovery_pg.py` (**2 tests**), con la misma secuencia sobre PostgreSQL real.

---

## 3. Matriz de inyección de crash (exactly-once)

El Crash Day de proceso (v2.46) **no** podía morir _mid-fill_: el broker SIM liquidaba todas las tranchas en
el mismo tick, así que la ventana de muerte entre tranchas **no existía** — desviación declarada en el pack de
`v2.46`. Aquí se cubre **por inyección**, sin tocar el broker:

- `apps/api-python/tests/test_auto_v46_crash_injection_matrix.py` (**6 tests**) lanza `CrashInjected` en las
  costuras: `save_claim`, `start_apply` (capturado), `apply_finance` **antes** de `mark_applied` (aplicando) y
  **tras el primer chunk APPLIED** (fill parcial). Otro caso cubre el **lease vencido** y el reclaim. La
  herramienta vive **solo en test** (wrappers de store / de `apply_finance`), siguiendo el patrón de
  `test_a9_1_crash_battery.py`: **no** se añadieron rutas de producción.
- Invariante por punto: tras el "reinicio" (worker nuevo sobre los **mismos** stores durables) el efecto
  financiero es **exactly-once** y el FSM converge (`RETRY → APPLIED` o reclaim), **sin** segunda
  materialización y **sin** pérdida.
- Gemelo PG: `test_auto_v46_crash_injection_pg.py` (**2 tests**) en las transiciones críticas (aplicando y
  parcial), reutilizando `apply_execution_financial_once` y el reset de lease.

---

## 4. Concurrencia multi-proceso

| Capa            | Fichero                                    | Medida                                                                   |
| --------------- | ------------------------------------------ | ------------------------------------------------------------------------ |
| Hermética       | `test_auto_v46_concurrent.py`              | `N ∈ {2, 3, 5, 10}` (4 params + 1) · `Σ _order_seq == 1`, 1 reserva viva |
| Sesiones PG     | `test_concurrent_auto_pg.py`               | `N` parametrizado                                                        |
| **Procesos PG** | `test_auto_v46_multiprocess_pg.py` (NUEVO) | `N` procesos `bolsa_api.workers.scheduler_worker` reales                 |

El invariante del multi-proceso se mide **en la BD** (no en RAM): **1** orden distinta, **1** reserva, **1**
efecto financiero. Después se mata un proceso y se comprueba la convergencia de los restantes (patrón
`_spawn`/`_kill_hard`). Es la primera vez que AUTO certifica concurrencia **entre procesos**, no entre
sesiones del mismo proceso.

---

## 5. `cycle_id` híbrido (migración `044_auto_cycle_trace`)

**El problema.** La cadena señal→decisión→reserva→orden→fill→posición→salida→PnL no tenía **ninguna**
identidad común. El trazado inverso (de un fill a la decisión que lo autorizó) era imposible en la práctica.

**El diseño (híbrido, tal como lo fijó el owner).**

- **Acuñado determinista** por `(cuenta, señal)`: `cyc-<sha256(account_id ⊕ signal_id)[:12]>`, junto a la
  identidad de la decisión. Dos workers/procesos que evalúan la **misma** señal sobre la **misma** barra
  convergen al **mismo** ciclo (M11). Sin `signal_id` se conserva el fallback **aleatorio** histórico: no hay
  clave estable que reclamar, y un id compartido por accidente sería peor que no tenerlo.
- **Propagación por JSONB** donde ya había JSONB: `payload` del journal (clave **aditiva** `cycleId`),
  `V2TickPlan` (`cycle_for(symbol)`) y el `position_state` de la posición (que **congela** el ciclo al nacer:
  el fill lo hereda de ahí, no lo re-acuña).
- **Migración `044`** (`down_revision = "043_exit_identity_and_kill_state"`): `cycle_id` **nullable** +
  índice en `portfolio_reservations`, `auto_exit_orders` y `sim_fill_finance_context`. **Sin backfill**:
  `NULL` significa "fila anterior a `2.47`", que es información (**desconocido ≠ fabricado**).
- **Salida y fill**: el intent de salida hereda el ciclo de la posición que cierra y el contexto financiero del
  fill (entrada **o** salida) queda atado a su ciclo. Sin esas dos patas, el índice no sirve para nada.

Tests: `packages/py/application/tests/test_auto_v47_cycle_trace.py` (**11 tests**).

---

## 6. Identidad formal de señales

**El problema.** `_dedupe_candidates` colapsaba a **un** candidato por instrumento (`canonical_candidate_key`).
Cuando dos señales del mismo instrumento competían, una **desaparecía en silencio**: sin journal, sin motivo,
sin rastro.

**Lo que cambia.**

- El candidato superado se **journaliza**: `signal_superseded_by_candidate`, con **ambos** `signal_id` y
  `strategy_version` (M16: si el dedupe deja de devolver las superadas, caen tres tests).
- Opción **`allow_distinct_strategies`** (default **OFF** = el comportamiento de hoy): con ON, dos
  `strategy_version` distintos sobre la misma cuenta/instrumento/barra compiten como **dos oportunidades
  legítimas** y decide el **optimizador de cartera** (capital, correlación, riesgo), no el dedupe ciego.
- Si dos estrategias seleccionadas **no** son representables en una sola posición, se declara
  (`signal_distinct_strategy_not_representable`) en vez de emitir dos entradas sobre el mismo instrumento.

**Política por escrito:** la discriminación de oportunidades depende de `strategy_version` + `signal_id` +
**política de cartera**, **nunca** de `(cuenta, instrumento, barra)`.

Tests: `packages/py/application/tests/test_auto_v47_signal_identity.py` (**9 tests**).

---

## 7. `AUTO-7` slice 1 — self-evaluation puro, read-only

**Módulo puro** `packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py` (**16 tests**):
agrega por `strategyVersion` expectancy, win rate, profit factor, MAE/MFE, contribución al drawdown, slippage,
coste de rechazo y coste de oportunidad, y **reconcilia el embudo** de AUTO-5
(`seen == traded + rejected + expired + missed`).

**Disciplina de medición (lo que hace que esto valga):**

- Sin oportunidades, el embudo queda **abierto** (`seen = None`, `UNKNOWN`): **no** se cierra con un `0`
  inventado (M14 mide los tres tests que caen si se cierra).
- Un coste de rechazo sin **ambos** precios se declara **no medido** (`None`), jamás `0.0` (M13).
- Un ciclo con identidad repetida se cuenta **una vez** y se **declara** (`SELF_EVAL_DUPLICATE_CYCLE`) — la
  misma familia que un doble fill (M15).
- Un ciclo **sin** versión de estrategia **no se reparte** entre estrategias: va a un cubo declarado.
- `measurement` del informe es `UNKNOWN` si falta algo importante, y `sample_quality` bloquea el flag
  "decisivo" con muestras finas.

**Puente y superficie:** `auto_self_evaluation_feed.py` (**13 tests**) reconstruye ciclos desde
`SimFillFinanceContext` (FIFO, aperturas abiertas, ventas sin contrapartida, fills legacy sin `cycle_id`,
versiones en conflicto) y `GET /api/v1/auto/self-evaluation?version=…` lo expone (fail-closed sin ámbito de
cuenta; 2 tests de API).

**Read-only:** no modifica pesos, umbrales ni sizing. **Sin UI** en esta fase (declarado).

---

## 8. UI: valor esperado medido y primer slice móvil

### 8.1 El valor esperado, visible (sin inventar ceros)

- Backend: el journal de AUTO publica `expectedR`, `netExpectedCurrency`, `expectedMeasurement` y
  `expectedNotes` (aditivos). Cuando el optimizador **no** corrió (o no tenía candidato para esa clave), el
  valor se **recalcula con la misma geometría que dimensionó la decisión** (`_expected_value_for_decision`):
  lo publicado y lo decidido **no pueden discrepar**.
- Contrato: `DecisionJournalStudyDto` + regeneración de `openapi.json` y `schema.d.ts`
  (`contract:check` **OK**).
- Shared: `expected-value-copy.ts` (formateador **propio**: `+34.00 €`, `−12.50 €`, `0.80` R; el de dinero de
  la casa no añade signo ni moneda) y los campos en `EntryOperatingSizingV1` y en el panel «¿Por qué?».
- **Lo no medido no se pinta**: sin `expectedR` ni `netExpectedCurrency`, la fila/sección **no aparece** (los
  tests lo afirman explícitamente: "jamás un `0 €` inventado").

### 8.2 Móvil (primer slice, sin `md:`/`lg:` sueltos)

- Un **único** módulo de layout (`use-narrow-cabin.ts`): `useNarrowCabin`, `cabinRowClass`,
  `cabinRowValueClass`, `cabinWidth`.
- `use-media-query.ts` **endurecido**: `window.matchMedia` puede **no existir** (jsdom) — antes un componente
  que lo consultara reventaba; ahora degrada con `false` sin excepción.
- Stub de viewport para test (`test-viewport.ts`) + `vitest.setup.ts` (default **escritorio**, para no cambiar
  el significado de los tests existentes).
- Seis componentes adaptados —`entry-operating-summary`, `decision-explain-panel`, `operativa-cockpit-card`,
  `auto-desk-panel`, `f3-protect-stop-block`, `exit-route-view`— con `data-cabin-width` (`narrow`/`wide`) en
  la raíz: el layout es **medible en test** y **nada se oculta** al estrechar (se apila; los botones pasan a
  ancho completo; las rejillas colapsan a una columna).

**Lo que este slice NO es:** no es "la UI móvil terminada". Es el primer corte de la deuda más antigua, con los
componentes de más valor y sin tocar el resto (declarado en §10.2).

---

## 9. Verificación local medida (árbol final)

Comandos **exactos** de la casa. Los dos bloques offline usan el runner versionado
(`scripts/verify/offline_ci_run_yaml.py`), que **extrae los targets del YAML** y mide por **JUnit XML**.

| Comprobación                       | Comando                                                                                                             | Resultado                                                                                                          |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Estático (invocación de CI)        | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                             | **All checks passed!**                                                                                             |
| Tipos                              | `uv run mypy … --follow-imports=silent`                                                                             | **491 ficheros, 0 issues**                                                                                         |
| Fronteras                          | `uv run lint-imports --config packages/py/.importlinter`                                                            | **4 kept / 0 broken** (609 ficheros, 3248 deps)                                                                    |
| Evidencia del gobernador           | `uv run python apps/api-python/scripts/v2_43_governor_evidence.py`                                                  | **exit 0** y `git diff` **vacío**                                                                                  |
| Bloque `quality` de CI             | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`     | **2178 passed, 0 failed, 0 skipped**                                                                               |
| Bloque `python` del tag            | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores` | **2189 passed, 0 failed, 0 skipped**                                                                               |
| Suites PG nuevas **con sus gates** | `AUTO_*_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v46_*_pg.py -q -rs`                             | **5 passed, 0 skipped**                                                                                            |
| Suites nuevas (herméticas)         | `uv run pytest <las 12 suites nuevas/modificadas> -q`                                                               | **todas verdes** (conteo por fichero en §9.1)                                                                      |
| Frontend `shared`                  | `pnpm --filter @bolsa/shared build && … typecheck && … test`                                                        | **786 passed + 1 todo** (95 ficheros)                                                                              |
| Frontend `web`                     | `pnpm --filter @bolsa/web typecheck && … lint && … test && … build`                                                 | typecheck **OK** · lint **0 errores / 23 warnings** (deuda legacy) · **1290 passed** (229 ficheros) · build **OK** |
| Contrato API                       | `pnpm --filter @bolsa/web contract:check`                                                                           | **OK** (openapi.json y schema.d.ts coinciden)                                                                      |

### 9.1 El delta `+87`/`+87` es la comprobación de cobertura

`quality` pasa de **2091** (`v2.46`) a **2178**; el job `python` del tag, de **2102** a **2189**. El delta es
**exactamente 87 en los dos bloques**, y su reparto es:

| Fichero                                                                 | Nuevos | Vía de entrada                           |
| ----------------------------------------------------------------------- | ------ | ---------------------------------------- |
| `packages/py/analytics/tests/test_auto_self_evaluation.py`              | 16     | pase de directorio                       |
| `packages/py/analytics/tests/test_expected_value.py`                    | 7      | pase de directorio                       |
| `apps/api-python/tests/test_auto_v46_hardkill_recovery.py`              | 5      | pase de directorio                       |
| `apps/api-python/tests/test_auto_v46_crash_injection_matrix.py`         | 6      | pase de directorio                       |
| `apps/api-python/tests/test_auto_v47_self_evaluation_api.py`            | 2      | pase de directorio                       |
| `apps/api-python/tests/test_auto_v46_concurrent.py`                     | 3      | pase de directorio (parametrización `N`) |
| `packages/py/application/tests/test_auto_v47_cycle_trace.py`            | 11     | **registrado a mano**                    |
| `packages/py/application/tests/test_auto_v47_expected_value_journal.py` | 5      | **registrado a mano**                    |
| `packages/py/application/tests/test_auto_v47_signal_identity.py`        | 9      | **registrado a mano**                    |
| `packages/py/application/tests/test_auto_self_evaluation_feed.py`       | 13     | **registrado a mano**                    |
| `packages/py/application/tests/test_decision_journal_studies.py`        | 10     | **hallazgo de la pasada**                |
| **Total**                                                               | **87** |                                          |

Dos notas que importan:

1. **Los cuatro ficheros "registrados a mano" no entraban por ningún pase de directorio.** El job `quality` y
   el job `python` del tag enumeran `packages/py/application/tests` **fichero a fichero**: un fichero nuevo
   ahí **no corre** si no se registra. Al principio se registraron **solo** en `quality`, y la medida lo
   delató: **+77** en `quality` (2178 − 2091… medido entonces: 2168 − 2091) frente a **+39** en el tag
   (2141 − 2102) — la diferencia (**38**) es exactamente la de esos cuatro ficheros (11 + 5 + 9 + 13). Al
   registrarlos también en el job del tag, los dos deltas quedaron **iguales (+77/+77)**; con el fichero del
   punto 2, **+87/+87**. Que los dos bloques crezcan **lo mismo** es la comprobación de que ningún fichero
   nuevo se quedó fuera de una de las dos listas.
2. **Hallazgo de cobertura de la pasada (no de esta fase):**
   `packages/py/application/tests/test_decision_journal_studies.py` **existía desde `v2.44` y no estaba en la
   lista de NINGÚN job** (se comprobó con `rg` sobre `.github/workflows` y `scripts/`): sus 10 tests **no
   corrían en CI en ninguna parte**. Se registra aquí (y en el tag) porque esta pasada **modificó** el fichero
   (el journal del estudio de decisión). Es la misma deuda que `v2.42.2` cerró a mano para
   `test_auto_daily_journal.py`.

---

## 10. Matriz de mutaciones MEDIDA

**Sonda:** [`v2_44_mutation_audit.py`](../../apps/api-python/scripts/v2_44_mutation_audit.py) — la matriz de la
línea AUTO (M1–M7 son de `V2.44`/`AUTO-4` y se conservan), extendida en esta pasada con **M8–M18**. Patrón de
la casa: **copia en memoria**, restauración **sin** `git checkout --`, y huella `git status --porcelain` de
los ficheros tocados verificada **antes/después** (la sonda devuelve `exit 0` solo si el árbol queda intacto).
Medida el **2026-09-21** con `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py`.

| #       | Mutación aplicada (revertir el fix)                          | Rojos observados (medido)                                                                                                                                                                                                                  |
| ------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| M1      | el desempate del optimizador deja de comparar                | **2**: `test_a_tie_on_value_prefers_the_lower_risk`, `test_capital_picks_the_affordable_subset_…`                                                                                                                                          |
| M2      | las combinaciones no positivas dejan de descartarse          | **1**: `test_the_empty_set_wins_when_no_combination_has_a_positive_expectation`                                                                                                                                                            |
| M3      | el tope de combinatoria se ignora                            | **1**: `test_the_enumeration_cap_aborts_without_a_silent_greedy`                                                                                                                                                                           |
| M4      | una expectativa no medida entra como `0.0`                   | **1**: `test_an_unmeasured_expectation_is_never_scored_as_zero`                                                                                                                                                                            |
| M5      | una correlación DESCONOCIDA deja de ser infeasible           | **1**: `test_a_known_correlation_limit_makes_an_unknown_correlation_infeasible`                                                                                                                                                            |
| M6      | el journal miente con `edge_below_threshold`                 | **2**: `test_with_the_flag_on_the_rejected_candidate_publishes_its_real_score`, `…_unmeasurable_top_of_the_ranking_is_not_evaluated`                                                                                                       |
| M7      | con el flag ON el tick vuelve al ranking sin declararlo      | **4**: (los tres de M6 + `test_with_the_flag_on_the_approved_set_never_exceeds_the_top_n` + `test_v2_optimizer_on_without_an_economic_producer_is_fail_closed`)                                                                            |
| **M8**  | un stop corto del lado equivocado (`s <= e`) se acepta       | **1**: `test_a_short_with_a_long_stop_is_an_inverted_geometry`                                                                                                                                                                             |
| **M9**  | una dirección no soportada se asume larga                    | **1**: `test_an_unsupported_direction_is_declared_and_never_assumed_long`                                                                                                                                                                  |
| **M10** | el premio de una corta se mide al revés                      | **1**: `test_a_short_target_r_is_measured_towards_a_lower_price`                                                                                                                                                                           |
| **M11** | el `cycle_id` deja de ser determinista por `(cuenta, señal)` | **3**: `test_cycle_is_deterministic_by_account_and_signal`, `test_the_tick_plan_publishes_one_deterministic_cycle_per_candidate`, `test_an_approved_decision_carries_its_cycle_in_the_journal_and_reservation`                             |
| **M12** | el journal deja de publicar `cycleId`                        | **1**: `test_an_approved_decision_carries_its_cycle_in_the_journal_and_reservation`                                                                                                                                                        |
| **M13** | el coste de rechazo no medido se publica como `0.0`          | **1**: `test_rejection_cost_is_measured_only_with_both_prices`                                                                                                                                                                             |
| **M14** | sin oportunidades el embudo se declara `COMPLETE` con `0`    | **3**: `test_an_empty_report_is_unknown_not_complete`, `test_funnel_stays_open_without_opportunities_…`, `test_the_report_declares_what_fills_alone_cannot_measure`                                                                        |
| **M15** | un ciclo repetido deja de descartarse                        | **1**: `test_a_repeated_cycle_is_counted_once_and_declared`                                                                                                                                                                                |
| **M16** | el dedupe deja de declarar la candidata superada             | **3**: `test_the_default_policy_collapses_but_journals_the_superseded_candidate`, `test_the_canonical_winner_is_the_best_edge_regardless_of_arrival_order`, `test_duplicate_same_strategy_instrument_still_collapses_with_a_journal_trail` |
| **M17** | tras reiniciar, el HALT durable deja de adoptarse            | **2**: `test_the_reconciliation_failure_producer_persists_a_halt_across_a_crash`, `test_a_restored_halt_blocks_entry_but_not_the_protective_exit`                                                                                          |
| **M18** | la dirección deja de llegar al estimador de coste            | **1**: `test_a_short_is_charged_with_the_short_legs_not_with_the_long_ones`                                                                                                                                                                |

**Balance: 18 de 18 mutaciones muerden**; la línea base (sin mutación) queda **verde** en los nueve grupos de
suites, cada mutación se **restaura byte a byte** (`restaurado byte a byte: si` en las 18) y la huella de
`git status` de los cinco ficheros mutados es **idéntica** antes y después (**la sonda no alteró el árbol**).

### 10.1 El defecto REAL de la sonda que esta pasada destapó: el bytecode `.pyc`

La sonda reportó **una vez** un `<fallo sin detalle, revisar a mano>` en `test_expected_value.py` cuando el
fichero, corrido a mano, estaba **verde**. La causa no era el test: un `.pyc` solo se considera vigente si
coinciden el **mtime del fuente truncado a segundos** y su **tamaño**, y las mutaciones de esta matriz son
sustituciones del **mismo tamaño** (`e - t` por `t - e`, `if x:` por `if False:`). Escribir el mutante y
restaurar dentro del **mismo segundo** dejaba el `.pyc` del mutante "vigente" para el fuente restaurado: la
matriz podía reportar un rojo que **no** venía del árbol actual (o, peor, un falso "no detectado").

**Corrección:** la sonda borra el `.pyc` de **cada** módulo mutado antes de **cada** corrida y ejecuta pytest
con `PYTHONDONTWRITEBYTECODE=1`. Una sonda que mide bytecode cacheado no mide el árbol.

### 10.2 Otros límites declarados (no silenciosos)

- **El camino del "Crash Day" de proceso sigue liquidando por tick.** La ventana mid-fill se cubre **por
  inyección** (§3), no moviendo el broker SIM. Cambiar el broker es una decisión de producto, no de este
  parche.
- **`BROKER_DESYNC` sin productor** (§2).
- **La UI móvil es un slice**: seis componentes; el resto de la cabina sigue sin adaptar.
- **AUTO-7 sin UI** y **sin uso de sus métricas para calibrar nada** (es read-only por diseño).
- **`allow_distinct_strategies` default OFF**: la política nueva existe y está probada, pero **no** cambia el
  comportamiento por defecto de producción. Se enciende **por configuración** —
  `AUTO_ENGINE_SIM_V2_ALLOW_DISTINCT_STRATEGIES=1`, leída en `auto_v2_entry` (`V2Tunables`) — y encenderla es
  decisión del owner: cambia qué señales compiten entre sí.
- **`cycle_id` en filas antiguas es `NULL`** (sin backfill): un trazado inverso de una posición anterior a
  `2.47` **no** se puede completar, y eso es información, no un fallo.

---

## 11. Cómo verificarlo (para el auditor)

```bash
# Estático, tipos y fronteras (invocaciones EXACTAS de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió (byte-identidad + su self-check sigue gobernando)
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py   # vacío
uv run python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Los dos bloques offline de CI (targets e ignores EXTRAÍDOS del YAML, medida por JUnit XML)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
#   => 2178 y 2189 passed, 0 skipped (base 2091/2102 → +87 en AMBOS)

# Las suites que muerden los hallazgos (herméticas, sin PG)
uv run pytest packages/py/analytics/tests/test_expected_value.py \
              packages/py/analytics/tests/test_auto_self_evaluation.py \
              packages/py/application/tests/test_auto_v47_cycle_trace.py \
              packages/py/application/tests/test_auto_v47_signal_identity.py \
              packages/py/application/tests/test_auto_v47_expected_value_journal.py \
              packages/py/application/tests/test_auto_self_evaluation_feed.py \
              apps/api-python/tests/test_auto_v46_hardkill_recovery.py \
              apps/api-python/tests/test_auto_v46_crash_injection_matrix.py \
              apps/api-python/tests/test_auto_v47_self_evaluation_api.py -q

# Las capas PG con su gate (no basta con que no fallen: NO deben skipear)
AUTO_HARDKILL_PG_REQUIRED=1 AUTO_CRASH_INJECT_PG_REQUIRED=1 AUTO_MULTIPROCESS_PG_REQUIRED=1 \
  uv run pytest apps/api-python/tests/test_auto_v46_hardkill_recovery_pg.py \
                apps/api-python/tests/test_auto_v46_crash_injection_pg.py \
                apps/api-python/tests/test_auto_v46_multiprocess_pg.py -q -rs

# La migración y su ida/vuelta
uv run alembic -c packages/py/infrastructure/alembic.ini heads        # => 044_auto_cycle_trace

# La matriz de mutaciones (restaura desde memoria y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py   # 18 mutaciones, exit 0

# Frontend (invocaciones del job `frontend` de CI)
pnpm --filter @bolsa/shared build && pnpm --filter @bolsa/shared typecheck && pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web typecheck && pnpm --filter @bolsa/web lint && pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web contract:check
```

---

## 12. Sello

Pendiente de producirse al escribir este pack: commit de fase, `main`, tag **`v2.47-beta`** y CI real
observada con `gh` (`Python CI` en `main` y en la ref del tag + `Release tag CI` con los **seis** pasos
dedicados de `lifecycle-pg` y sus guards anti-skip). La evidencia (con los **runs** enlazados) se añade en el
commit de sellado docs-only, siguiendo la convención de `v2.43.2`/`v2.44`/`v2.45`/`v2.46`.

---

## 13. Errata de esta pasada (método)

1. **Comentarios dentro de un `run: >` (el hazard de `v2.40.2`, reincidido).** Al registrar los ficheros de
   test de `V2.47` en el job `quality` se añadieron las líneas de comentario **dentro** del bloque plegado.
   El runner offline lo detectó al instante (los `#`, `V2.47`, `(trazabilidad`… aparecieron como "rutas
   inexistentes"), lo que evitó colar un job que habría ejecutado **solo** la parte de la lista anterior al
   primer `#`. Los comentarios se movieron **fuera** del bloque (donde ya viven los de `V2.40.2` en el job del
   tag).
2. **Un test autorreferencial que "cubría" la dirección del coste sin cubrirla.** Ver §1 (M18). Se midió
   **antes** de declarar la mutación medida.
3. **Cuatro ficheros de test nunca registrados** (§9.1, encontró 1 de la pasada). El delta de los dos bloques
   offline pasó de **+77/+77** (los cuatro primeros ficheros) a **+87/+87** (más el de la pasada): la
   comprobación de que los dos bloques crezcan **igual** es lo que destapó que uno de ellos no estaba en
   ninguna lista.
4. **`.pyc` cacheado en la sonda** (§10.1): un falso rojo que parecía del árbol y venía del bytecode.

---

## 14. Freeze (congelado, no tocar sin motivo)

- **Comportamiento de `AUTO_ENGINE_SIM_V2=0`**: debe seguir siendo `v2.39.x`.
- **Comportamiento de `AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
- **`v2_43_governor_evidence.py`**: **byte a byte igual** y su `"bump"` se queda en `1.68.0-beta`.
- **Tabla del gobernador y sus umbrales**: **no** se tocan.
- **`v2.46-beta` y anteriores no se mueven**: `v2.47-beta` es **nueva y aditiva**.
- **Sin SHORT**: `entry_direction` devuelve `None` para `SELL`; ninguna ruta nueva permite entrada corta.
- **Sin backfill de `cycle_id`**: `NULL` = fila anterior a `2.47`.
- **Los gates PG** y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo **no** certifica.
- **La migración `044` es aditiva y nullable**: no reescribe ninguna fila existente.
