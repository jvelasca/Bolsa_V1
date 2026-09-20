# Audit-pack v2.45-beta — AUTO-5 · Golden Day 2.0 (el día real y su embudo)

**Fecha:** 2026-09-20 · **Ref:** `v2.45-beta` (`1.70.0-beta`) · **Plan de fase:**
[`plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md`](./plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md) §7 ·
**Arranque del auditor:** [`arranque-auditor-v2.45-auto-5-golden-day-2-0-2026-09-20.md`](./arranque-auditor-v2.45-auto-5-golden-day-2-0-2026-09-20.md).

- **Bump:** `1.69.0-beta` → `1.70.0-beta`.
- **Migración:** **NINGUNA** (Alembic head sigue en `043_exit_identity_and_kill_state`).
- **Gobernador:** `apps/api-python/scripts/v2_43_governor_evidence.py` **intacto** (`git diff` vacío) y
  `exit 0`, con `"bump"` conservado en `1.68.0-beta`.
- **Tags previos:** `v2.43-beta`…`v2.44-beta` **no se mueven**; `v2.45-beta` es ref nueva y aditiva.

---

## 1. El invariante que instala (en una frase)

Hasta `v2.44`, el «día» se medía **por commit** con reloj/precio/decider **inyectados**. AUTO-5
certifica el día en **dos capas independientes**:

1. **Capa hermética (por commit):** toda oportunidad del día termina en **exactamente** un estado
   final, `seen == traded + rejected + expired + missed`, con **motivo** en cada estado no operado y
   **coste de oportunidad** declarado cuando el dato existe — y **declarado como no medido** cuando no.
2. **Capa real (al sellar el tag):** el día lo conduce el **proceso real**
   `python -m bolsa_api.workers.scheduler_worker` sobre **PostgreSQL real**, con gate fail-if-skipped
   propio (`AUTO_GOLDEN_DAY_V2_PG_REQUIRED`).

La disciplina que lo hace auditable es la del repo: **lo que no se mide se declara**
(`UNKNOWN`/`PARTIAL` + `notes`), nunca un `0` que se leería como "coste cero".

---

## 2. Piezas nuevas

### 2.1 Embudo, atribución y medición — `packages/py/application/src/bolsa_application/auto_daily_journal.py`

- Dataclasses nuevas: `OpportunityRow` (`:96`), `OperationMeasurement` (`:119`), `OpportunityCost`
  (`:134`) — `SimJournalRow` gana `strategy_version` (`:74`).
- `AutoDailyReport` gana campos **aditivos** (`:155`): `seen/traded/rejected/expired/missed`,
  `funnel_measurement`, `rejection_reasons`, `strategy_traded`/`strategy_exits`, `mae_mfe`/
  `mae_mfe_measurement`, `opportunity_cost`/`opportunity_cost_measurement` y `notes`.
  `funnel_closed` (`:202`) exige `funnel_measurement == COMPLETE`.
- Disciplina de medición: `MEASUREMENT_UNKNOWN`/`PARTIAL`/`COMPLETE` (`:58-60`).
- Agregadores puros: `_opportunity_breakdown` (`:474`), `_opportunity_costs` (`:516`),
  `_mae_mfe` (`:574`); el cierre del embudo vive en `build_auto_daily_report` (`:587`, `:667`, `:685`).

| Regla                                                       | Comportamiento                                                           |
| ----------------------------------------------------------- | ------------------------------------------------------------------------ |
| Estado fuera del vocabulario                                | **no** se cuenta: `opportunity_status_unknown` + embudo **abierto**      |
| No operada sin motivo                                       | `rejection_without_reason` (una decisión en silencio **rompe** el día)   |
| `seen` declarado ≠ filas construidas                        | `funnel_seen_mismatch` (faltan oportunidades por explicar)               |
| Sin oportunidades aportadas                                 | `funnel_measurement = UNKNOWN` (**no** `0`)                              |
| Unas rechazadas medidas y otras no                          | `opportunity_cost_measurement = PARTIAL` + `opportunity_cost_unmeasured` |
| `reference_price` ausente/`0`, o `subsequent_price` ausente | coste `UNKNOWN`, `missed_return = None` (**no** `0`)                     |
| MAE/MFE con una pata ausente                                | `mae_mfe_measurement = PARTIAL`/`UNKNOWN` + `mae_mfe_unmeasured`         |

### 2.2 Reason codes — `packages/py/application/src/bolsa_application/auto_reason_codes.py`

`:198-209`: `OPPORTUNITY_TRADED/REJECTED/EXPIRED/MISSED`, `OPPORTUNITY_STATUSES` (frozenset),
`OPPORTUNITY_COST_UNMEASURED`, `MAE_MFE_UNMEASURED`. Un motivo nuevo **no** reutiliza un literal
existente que signifique otra cosa (lección de `v2.44`: `edge_below_threshold` para una no
seleccionada habría sido falso).

### 2.3 Identidad de estrategia (sin migración) — `auto_v2_entry.py` + `auto_simulation_worker.py`

- `strategyVersion` entra en el `payload` JSONB de las decisiones V2: propuesta (`auto_v2_entry.py:1403`,
  `:1750`, `:1791`). Sin versión, la clave se **omite** (la ausencia es información; jamás se inventa
  un `"unversioned"`).
- El cierre **hereda** la versión de la **posición** (`auto_simulation_worker.py`, `_journal_position_event`).
- `_strategy_version_from_source` (`auto_simulation_worker.py:361`) reconoce **además** la fuente
  `auto-2.0:<version>` (`_V2_ENTRY_SOURCE_PREFIX`, `:341`): sin eso, el fill/cierre del camino V2
  quedaba con versión NULL **en silencio**.

### 2.4 Productores del día (worker)

`opportunity_rows()` (`:1044`), `seen_signals()` (`:1054`), `operation_measurements()` (`:1058`),
`_v2_mfe_mae_snapshot` (`:1062`), `_v2_record_operation_measurement` (`:1068`) y
`_v2_measure_opportunity_costs` (`:2738`). El contador `seen_signals` es **independiente** de las
filas: así un «faltó una oportunidad por explicar» es **detectable**, no silencioso.

### 2.5 Capa real del tag — `apps/api-python/tests/test_golden_day_v2_process_pg.py` (NUEVO)

Dos fases, sin `run_tick()` y sin decider scripteado:

- **Fase 1 (apertura):** el proceso real abre **una posición V2 por instrumento** del watch (3
  instrumentos, 3 sectores), con `fills > orders` (la cola SIM parte la orden en tranchas ⇒
  `sim_fill_finance_context` tiene más filas que `venue_order_id` distintos), todo en `APPLIED`.
- **Fase 2 (cierre):** se detiene el proceso, se lleva el **techo de mantenimiento durable**
  (`holdingDeadlineAt` del JSONB de `sim_auto_positions`) al pasado y **se reinicia el mismo engine**:
  el worker **rehidrata** el plan y vende por `time_exit`; libro canónico **plano**, todo `APPLIED` y
  cada fill con su transacción.
- **Ids deterministas:** `_filling_instrument_id` barre ids puros y exige, en **toda** la ventana de
  ticks, `≥2` tranchas en BUY y SELL **completa**; sin eso el día sería una moneda al aire (rojo
  espurio). Si ningún candidato cumple, el test falla con diagnóstico propio.
- **Gate:** `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1` ⇒ un skip es **fallo duro**; sin la env y sin PG hace
  `skip` honesto.

### 2.6 Cableado CI

- `python-ci.yml` (`quality`) y `release-tag-ci.yml` (`python`): el fichero PG se añade a los
  `--ignore` (jobs offline, sin PG). Comentarios **fuera** del bloque `run: >`.
- `release-tag-ci.yml` (`lifecycle-pg`): `AUTO_GOLDEN_DAY_V2_PG_REQUIRED: '1'` en `env` (`:518`),
  paso dedicado de pytest con `set -o pipefail` + `tee /tmp/golden-day-v2-pg.log` (`:656-662`) y
  **guard anti-skip** (`:664-674`) que exige log no vacío y **cero** `skipped`.

---

## 3. Matriz afirmación → código → test

| Afirmación                                           | Código                              | Test                                                                    |
| ---------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------- |
| El embudo es partición exhaustiva                    | `auto_daily_journal.py:474,667`     | `test_day_funnel_covers_every_opportunity_exactly_once`                 |
| Estado no catalogado deja el embudo abierto          | `:667`                              | `test_day_unknown_opportunity_status_keeps_funnel_open`                 |
| Una rechazada sin motivo se declara                  | `:474`                              | `test_day_rejection_without_reason_is_declared_not_dressed`             |
| El `seen` descuadrado se declara                     | `:685`                              | `test_day_funnel_declares_seen_mismatch_when_an_opportunity_is_dropped` |
| Sin oportunidades no se publica `0`                  | `:685`                              | `test_day_without_opportunities_declares_funnel_unknown_not_zero`       |
| Coste medido vs declarado no medido                  | `:516`                              | `test_day_opportunity_cost_measured_and_declared_when_missing`          |
| MAE/MFE `PARTIAL` con una pata ausente               | `:574`                              | `test_day_mae_mfe_aggregate_declares_partial_when_a_leg_is_missing`     |
| MAE/MFE `COMPLETE` con ambas patas                   | `:574`                              | `test_day_mae_mfe_complete_when_both_legs_present`                      |
| Salidas atribuidas por estrategia                    | `:516`/`build_auto_daily_report`    | `test_day_strategy_exits_attributed_from_close_rows`                    |
| El día del worker tipa cada rechazo y le pone precio | `auto_v2_entry.py` + worker         | `test_v2_golden_day_funnel_types_every_rejection_and_prices_its_cost`   |
| El `payload` lleva la identidad de estrategia        | `auto_v2_entry.py:1403`             | `test_v2_golden_day_journal_payload_carries_strategy_identity`          |
| La fuente `auto-2.0:` se reconoce                    | `auto_simulation_worker.py:341,370` | `test_strategy_version_from_source_reads_v2_entry_proposal`             |
| El día real abre y cierra el libro (PG)              | `test_golden_day_v2_process_pg.py`  | `test_golden_day_v2_real_process_opens_and_closes_the_book_pg`          |

---

## 4. Matriz de mutaciones (MEDIDA, no esperada)

`apps/api-python/scripts/v2_45_mutation_audit.py` — **8/8 muerden**, restauración **byte a byte** desde
memoria (nunca `git checkout --`) y huella `git status --porcelain` **intacta** antes/después
(`exit 0`). Corrida completa: `1.052.176 ms` (17,5 min), con `DATABASE_URL` a un puerto cerrado para
que el teardown de `apps/api-python/tests/conftest.py` falle al instante en vez de colgarse.

| #   | Mutación                                               | Suite que mordió                                                     | Test en rojo                                                                                                           |
| --- | ------------------------------------------------------ | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| M1  | una rechazada sin motivo deja de declararse            | `test_auto_daily_journal.py`                                         | `test_day_rejection_without_reason_is_declared_not_dressed`                                                            |
| M2  | un estado no catalogado deja de declararse             | `test_auto_daily_journal.py`                                         | `test_day_unknown_opportunity_status_keeps_funnel_open`                                                                |
| M3  | el `seen` del productor descuadrado deja de declararse | `test_auto_daily_journal.py`                                         | `test_day_funnel_declares_seen_mismatch_when_an_opportunity_is_dropped`                                                |
| M4  | un coste no medible se publica como `0` medido         | `test_auto_daily_journal.py`                                         | `test_day_opportunity_cost_measured_and_declared_when_missing`                                                         |
| M5  | una pata MAE/MFE ausente se da por completa            | `test_auto_daily_journal.py`                                         | `test_day_mae_mfe_aggregate_declares_partial_when_a_leg_is_missing`                                                    |
| M6  | las salidas dejan de atribuirse                        | `test_auto_daily_journal.py` + `test_auto_v2_golden_day_evidence.py` | `test_day_strategy_exits_attributed_from_close_rows`, `test_v2_golden_day_journal_evidences_time_exit_and_thesis_exit` |
| M7  | el journal V2 omite `strategyVersion`                  | `test_auto_v2_golden_day_evidence.py`                                | `test_v2_golden_day_journal_payload_carries_strategy_identity`                                                         |
| M8  | la propuesta V2 deja de atribuir versión               | `test_auto_simulation_worker.py`                                     | `test_strategy_version_from_source_reads_v2_entry_proposal`                                                            |

Línea base (sin mutación) de las tres suites: **ningún rojo**. Huella final de los tres ficheros:
idéntica a la inicial ⇒ _«intacto: la sonda no alteró el árbol»_.

---

## 5. Verificación medida (2026-09-20, máquina del autor)

| Medida                                      | Comando                                                                                                   | Resultado                                                    |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Ruff                                        | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                   | **0** (se corrigieron 3 `I001` propios antes de medir)       |
| Mypy                                        | `uv run mypy … --follow-imports=silent`                                                                   | **489 files, 0 issues**                                      |
| Import-linter                               | `uv run lint-imports --config packages/py/.importlinter`                                                  | **4 kept, 0 broken**                                         |
| Gobernador                                  | `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py`                                          | **vacío** + `exit 0`                                         |
| Suites nuevas juntas                        | `pytest test_auto_daily_journal.py test_auto_v2_golden_day_evidence.py test_auto_simulation_worker.py -q` | **44 passed**                                                |
| Baseline `quality` (del YAML, JUnit)        | `offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`                        | **2087 passed, 0 skipped, 0 failed** (v2.44: 2075 ⇒ **+12**) |
| Baseline `python` del tag (del YAML, JUnit) | `offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores`                    | **2098 passed, 0 skipped, 0 failed** (v2.44: 2086 ⇒ **+12**) |
| Mutaciones                                  | `uv run --no-sync python apps/api-python/scripts/v2_45_mutation_audit.py`                                 | **8/8 muerden**, huella intacta, `exit 0`                    |

**Tests nuevos (12):** 9 en `packages/py/application/tests/test_auto_daily_journal.py` + 2 en
`apps/api-python/tests/test_auto_v2_golden_day_evidence.py` + 1 en
`apps/api-python/tests/test_auto_simulation_worker.py`. El `+12` coincide en **ambos** bloques offline.

### Capa real (PG + proceso): medida también en LOCAL

**Corrección de procedencia frente al arranque del plan:** esta máquina **sí** tenía PostgreSQL
alcanzable (contenedor `bolsa-postgres` **sano** en `localhost:5432`, con el DSN de `docker-compose.yml`),
así que la capa real **no** hubo que dejarla solo al CI: se midió en local con
`AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`, **`1 passed`** en **10,05 s**, y seis corridas en solitario de
8,89 / 9,66 / 9,85 / 9,88 / 9,90 / 10,05 s.

**Límite de método medido (declarado también en el propio fichero):** el barrido de residuos del conftest
(`purge_all_residuals` borra **toda** cuenta ajena y todo instrumento `inst-%` al terminar la **sesión**
de pytest) hace que **dos sesiones de pytest simultáneas contra la misma base se borren los datos entre
sí** — se reprodujo: el motor quedaba reintentando liquidaciones (`retry_scheduled`) contra filas ya
borradas y la fase de apertura agotaba su presupuesto. **No** es un defecto del motor ni del test: es el
teardown de la otra sesión. En CI el fichero corre en un **paso dedicado**, sin sesiones solapadas.

La cifra del `lifecycle-pg` del tag (con su guard anti-skip) la produce el **run del tag** y se registra
en §9.

---

## 6. Comandos exactos de CI

```bash
# El gobernador NO se movió: debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Bloques offline extraídos del YAML (medida por JUnit XML, no copia a mano)
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml \
  quality --with-pg-ignores
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml \
  python --with-pg-ignores

# Matriz de mutaciones
uv run --no-sync python apps/api-python/scripts/v2_45_mutation_audit.py

# Capa real: necesita PostgreSQL (la corre el job lifecycle-pg del tag con el gate)
AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1 uv run pytest \
  apps/api-python/tests/test_golden_day_v2_process_pg.py -q --tb=short -rs
```

---

## 7. Límites declarados y deuda diferida

### 7.1 Desviaciones frente al plan §3.1 (declaradas, no maquilladas)

El plan pedía que el **día real** certificase nueve cosas. Se certifican **cuatro** en la capa real y las
otras **cinco** en la capa hermética, donde precio, reloj y decider se **inyectan**:

| Punto del plan §3.1                           | Capa real (PG + proceso)                                                          | Capa hermética                                                              |
| --------------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 1. 3–10 señales                               | **sí** (3, una por instrumento/sector)                                            | sí                                                                          |
| 1b. ≥2 estrategias                            | **no**: el spine determinista es `unversioned` (`auto_simulation_worker.py:1728`) | **sí** (`orb-1` ×2 y `meanrev-2`)                                           |
| 2. `fills > orders`                           | **sí** (tranzas de la cola SIM)                                                   | sí                                                                          |
| 3. T1 parcial + trailing + cierre por régimen | **no**: precio SIM **plano** (`flat_price_script`) y horizonte 21–90 d            | **sí** (`test_auto_v2_golden_day_evidence.py`: `time_exit` + `thesis_exit`) |
| 4. libro plano                                | **sí** (canónico `positions` a cero)                                              | sí                                                                          |
| 5. todo `APPLIED` + fill con transacción      | **sí** (espejo durable vs `transactions.idempotency_key`)                         | sí                                                                          |
| 6. `Σ exit_reasons == exits`                  | **no** (los planes `sim_auto_positions` se retiran al cerrar)                     | **sí**                                                                      |
| 7. atribución por estrategia desde la BD      | **no** (D2: el bucle SIM AUTO **no** escribe el journal durable)                  | **sí**                                                                      |
| 8. MAE/MFE leídos de la BD                    | **no** (D2 + el plan se retira al cerrar)                                         | **sí** (del `mfe_mae` del JSONB)                                            |
| 9. coste de oportunidad de las rechazadas     | **no** (D2)                                                                       | **sí** (precio posterior; `unmeasured` declarado si falta)                  |

**Por qué el día real no puede con 3/7/8/9:** el precio del camino SIM real es **plano** (no hay env que
cambie el `price_script` del proceso) y el horizonte de la plantilla es de **21–90 días**; y el bucle AUTO
SIM acumula el journal **en memoria** (el `DecisionJournalEntryRow` lo escriben los casos de uso de la
API, no el worker), así que no hay journal durable del que agregar atribución, MAE/MFE ni coste. Cambiar
cualquiera de las dos cosas es **producción**, no certificación.

### 7.2 Límites (heredados o confirmados)

1. **El día real cierra por el seam durable, no por geometría.** La fase 2 detiene el proceso, lleva el
   **techo de mantenimiento** (`holdingDeadlineAt`) al pasado y **reinicia el mismo engine**: el plan se
   **rehidrata** y vende por `time_exit`. El cierre por geometría se certifica en la capa hermética.
2. **Sin productor de economía en el tick** para el día real (heredado de `AUTO-4`): `p_win`/medias
   son de `AUTO-7`.
3. **MAE/MFE se recogen, no se calibran** (calibrar stop/T1/T2/trailing/tiempo es `AUTO-7`).
4. **El coste de oportunidad se recoge, no decide**: ninguna regla se relaja por esta medición.
5. **Correlación de hoy, no matriz por pares** (heredado de `AUTO-4`).
6. **La identidad de estrategia viaja en `payload` JSONB**: consultable, **no** indexada.
7. **Presupuesto de tiempo del job del tag**: el día real alarga `lifecycle-pg`; medido ~10 s por corrida
   en local, con techo declarado por fase (120 s) que **falla con diagnóstico**.
8. **Límite de método:** no correr dos sesiones de pytest en paralelo contra la misma base (ver §5).

---

## 8. Reproducibilidad e inventario

Ficheros tocados por la fase (14 + 2 docs nuevos de auditoría):

```
CHANGELOG.md
package.json                                                       1.69.0-beta → 1.70.0-beta
docs/engineering/PROJECT_STATE.md
docs/engineering/engineering-index-2026-08-03.md
docs/engineering/audit-pack-v2.45-auto-5-golden-day-2-0-2026-09-20.md          (NUEVO)
docs/engineering/arranque-auditor-v2.45-auto-5-golden-day-2-0-2026-09-20.md    (NUEVO)
.github/workflows/python-ci.yml
.github/workflows/release-tag-ci.yml
packages/py/application/src/bolsa_application/auto_reason_codes.py
packages/py/application/src/bolsa_application/auto_daily_journal.py
packages/py/application/src/bolsa_application/auto_v2_entry.py
packages/py/application/tests/test_auto_daily_journal.py
apps/api-python/src/bolsa_api/background/auto_simulation_worker.py
apps/api-python/tests/test_auto_v2_golden_day_evidence.py
apps/api-python/tests/test_auto_simulation_worker.py
apps/api-python/tests/test_golden_day_v2_process_pg.py                         (NUEVO)
apps/api-python/scripts/v2_45_mutation_audit.py                               (NUEVO)
```

**NO se toca:** `apps/api-python/scripts/v2_43_governor_evidence.py`, ninguna migración Alembic, los
dos ficheros con CRLF/LF pendientes, ni `governor.json` (generado, sin trackear).

---

## 9. Sello

- **Commit de fase: `ad800262`** (17 ficheros, `+2581/−16`) — el cuerpo de la fase.
- **Commit de corrección: `0fc85c17`** — contrato declarado del id determinista + límite de método medido
  (dos sesiones de pytest en paralelo contra la misma base).
- **`Python CI` GREEN 5/5 en `main`** (run
  [`35520898909`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35520898909)): `quality` **2087
  passed, 38 skipped, 0 failed** en 72,43 s (los **+12** exactos de los tests nuevos), `auto-v2-durable-pg`
  **43 passed** (sin cambio: no hay migración), `paper-forward-pg` **2**, `grammar-discovery-pg` **21**,
  `lifecycle-pg` **13**. `Gitleaks` GREEN (run
  [`35520899318`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35520899318)).
- **Tag `v2.45-beta` → `1abfc7fb`** (commit docs-only de sellado). **`Release tag CI` GREEN** con
  `certify (aggregate + artifact)` en `success` (run
  [`35522747332`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35522747332), 8m8s): job `python`
  offline **2098 passed, 35 skipped** en 42,75 s (los **+12** sobre los 2086 de `v2.44-beta`),
  `lifecycle-pg` **148 + 45 passed** y el **paso dedicado del día real**
  (`Pytest Golden Day 2.0 (proceso scheduler V2 + PG, fail if skipped)` con
  `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`) **1 passed en 9,32 s**; su guard anti-skip (`log no vacío` +
  `grep` de `skipped`) **pasó**; `a7-gate`, `decision-spine`, `dr-verify`, `shared`, `security
(gitleaks)` y `frontend` en `success`; `playwright (integrated E2E)` `skipped` por opt-in.
- **En la ref del tag**, `Python CI` GREEN 5/5 (run
  [`35522747381`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35522747381), 2m14s): `quality`
  **2087 passed, 38 skipped** en 91,47 s y `auto-v2-durable-pg` **43 passed**, idénticos al commit de
  fase; `Optimize lab` GREEN (run
  [`35522747321`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35522747321)) y `Fase 2 scientific`
  GREEN (run [`35522747311`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35522747311)).
