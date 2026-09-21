# Plan de fase — `V2.46.x` (hardening de AUTO-6) + `V2.47` (trazabilidad de ciclo) + `AUTO-7` slice 1 (`1.72.0-beta`)

**Fecha:** 2026-09-21 · **Punto de partida:** tag **`v2.46-beta`** (commit de fase `a14b71d7`, tag → `5eb654b9`).
**Migración:** **SÍ** — Alembic head pasa de `043_exit_identity_and_kill_state` a **`044_auto_cycle_trace`**
(columnas `cycle_id` **nullable e indexadas**). Es la primera migración de la línea `AUTO` desde `043`.
**Sello:** tag anotado **`v2.47-beta`** sobre el commit de sellado docs-only (ver §8.2).

Este plan es la **orden de trabajo** de la fase; el pack de evidencia es
[`audit-pack-v2.47-auto-6-hardening-y-trazabilidad-2026-09-21.md`](./audit-pack-v2.47-auto-6-hardening-y-trazabilidad-2026-09-21.md)
y el relevo es
[`traspaso-relevo-post-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md`](./traspaso-relevo-post-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md).
Si el plan y el pack se contradicen, **manda el pack** (el plan dice lo que se iba a hacer; el pack, lo que se midió).

---

## 0. Decisiones del owner

1. **El defecto de `expected_value.py` se corrige YA**, aunque hoy sea **latente** (el motor de entrada AUTO
   es largo-only): no se espera a que exista una ruta corta para dejar la economía direccional.
2. **Disciplina fail-closed al corregirlo**: la dirección se toma de un **único** helper explícito
   (`entry_direction`), `BUY → long`, y **todo lo demás degrada** (`EV_DIRECTION_UNSUPPORTED`), en vez de
   etiquetarse como largo. **No se habilita SHORT por la puerta de atrás.**
3. **`cycle_id` híbrido**: acuñado **determinista** por `(cuenta, señal)`; propagación por **JSONB** donde ya
   hay JSONB y **columna indexada** (migración) donde hay que **consultar** (reservas, exit orders, contexto
   financiero del fill). Sin backfill: `NULL` = fila anterior a `V2.47` (desconocido ≠ fabricado).
4. **Reparto en dos releases** (`V2.46.x` hardening y `V2.47` trazabilidad) — ver §7.1: el árbol entregado los
   sella **juntos** y la desviación queda declarada, con el motivo (la migración `044` hace imposible un sello
   `V2.46.x` "sin migración" una vez que la trazabilidad aterriza en el mismo árbol).
5. **AUTO-7 nace read-only**: agrega y **declara huecos**; no toca pesos, umbrales ni sizing.
6. **La UI no inventa ceros**: lo que no se midió **no se pinta**.

---

## 1. Invariante que instala

> _El valor esperado de una oportunidad se mide con **la geometría de su dirección**; un ciclo financiero
> (señal → decisión → reserva → orden → fill → posición → salida → PnL) tiene **una identidad determinista**
> que sobrevive al crash y al reinicio; una señal superada por otra **deja rastro** en el journal; y AUTO sabe
> **qué vio, qué rechazó y qué se perdió** — declarando siempre lo que no pudo medir._

---

## 2. Qué NO cambia (freeze)

- **`AUTO_ENGINE_SIM_V2=0`**: comportamiento `v2.39.x` intacto.
- **`AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
- **`v2_43_governor_evidence.py`**: **byte a byte igual**, `exit 0`, su `"bump"` conservado en `1.68.0-beta`.
- **Tabla del gobernador y sus umbrales**: no se tocan.
- **`v2.46-beta` y anteriores no se mueven**: refs publicadas y auditadas; `v2.47-beta` es **nueva y aditiva**.
- **Sin SHORT**: ninguna ruta nueva permite entrada corta; `entry_direction` devuelve `None` para `SELL` y la
  economía lo declara.
- **Los gates PG** y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo **no** certifica.

---

## 3. Piezas (qué se extiende, no qué se reinventa)

### 3.1 Economía direccional (`expected_value.py`, puro)

- `_risk_geometry` recibe `direction`: largo exige `stop < entry`, corto exige `stop > entry`, y la distancia
  se mide en el sentido de la operación. Una dirección **no reconocida** degrada (`EV_DIRECTION_UNSUPPORTED`),
  nunca se asume larga.
- `_target_r` también direccional (largo `reward = t − e`; corto `reward = e − t`).
- `build_expected_value` propaga la dirección a `estimate_trading_cost` (la pata de salida de una corta se
  cobra sobre su propio stop), y publica el motivo tipado cuando no la entiende.
- **Fuente única de la dirección** en el motor: `auto_v2_entry._ENTRY_DIRECTION`
  (`Final[Literal["long", "short"]]`) + `entry_direction(signal)`; el dimensionado, el snapshot y la economía
  leen de ahí (no hay dos direcciones que puedan discrepar).

### 3.2 Parada dura durable: `engage → crash → restart → HALTED → release → RUNNING`

- **Carga en arranque** (`_v2_load_kill_state`): no solo **adopta** los engagement durables, también adopta
  una **liberación** escrita desde fuera (API) si es **posterior** al engagement local — sin reiniciar el
  worker.
- **Vía de liberación con productor real** (`POST /api/v1/risk/kill-switch/durable-release`): exige
  `reconciliationId` **obligatorio** (un halt que se levanta "porque sí" no es auditable), escribe la
  liberación durable con `release_actor` y `release_reconciliation_id`, y **no** habla con el proceso del
  worker. `not_engaged` es un no-op idempotente, no un error.
- `BROKER_DESYNC` sigue **sin productor real**: se declara como motivo del `Literal` sin emisor (no se
  inventa un engagement para "cubrirlo").

### 3.3 Matriz de inyección de crash (exactly-once)

- Herramienta **solo de test** (sin rutas nuevas en producción): `test_auto_v46_crash_injection_matrix.py`
  inyecta `CrashInjected` en las costuras (`save_claim`, `start_apply`, `apply_finance` antes de
  `mark_applied`, primer chunk APPLIED, …) y comprueba que tras el "reinicio" (worker nuevo sobre los mismos
  stores) el efecto financiero es **exactly-once** y el FSM converge (`RETRY → APPLIED`/reclaim).
- **Gemelo PG** (`test_auto_v46_crash_injection_pg.py`) en las transiciones críticas, reutilizando
  `apply_execution_financial_once` y el reset de lease: es lo que cierra la desviación declarada del Crash Day
  (el broker SIM liquidaba todas las tranchas en el mismo tick ⇒ no había ventana de muerte mid-fill).

### 3.4 Concurrencia multi-proceso

- Hermético: `test_auto_v46_concurrent.py` **parametrizado** en `N ∈ {2, 3, 5, 10}` (invariante
  `Σ _order_seq == 1`, una sola reserva viva).
- Sesiones PG: `N` parametrizado en `test_concurrent_auto_pg.py`.
- **Multi-proceso real** (`test_auto_v46_multiprocess_pg.py`): `N` procesos `bolsa_api.workers.scheduler_worker`
  compitiendo por la **misma** cuenta/barra/señal; el invariante se mide **en la BD** (1 orden, 1 reserva, 1
  efecto financiero) y después se mata uno y se comprueba la convergencia del resto.

### 3.5 `cycle_id` híbrido (migración `044_auto_cycle_trace`)

- **Acuñado determinista** junto a la identidad de la decisión: `cyc-<sha256(cuenta ⊕ signal_id)[:12]>` (los
  workers duplicados **convergen** al mismo ciclo); sin `signal_id` se conserva el fallback aleatorio
  histórico (no hay clave estable que reclamar).
- **Propagación sin migración** donde ya hay JSONB: `payload` del journal (`cycleId`), `V2TickPlan` y
  `position_state` de `sim_auto_positions` (la posición nace con su ciclo y lo **congela**).
- **Migración `044_auto_cycle_trace`** (`down_revision = "043_exit_identity_and_kill_state"`): `cycle_id`
  **nullable** + índice en `portfolio_reservations`, `auto_exit_orders` y `sim_fill_finance_context`. **Sin
  backfill**: `NULL` = fila anterior a `2.47`.
- La salida **hereda** el ciclo de la posición que cierra y el fill (entrada o salida) queda atado a su ciclo:
  sin eso, el trazado inverso posición → fill → reserva/decisión es imposible.

### 3.6 Identidad formal de señales

- La política de colisión deja de ser **silenciosa**: el candidato descartado se **journaliza**
  (`signal_superseded_by_candidate`, con ambos `signal_id` y `strategy_version`).
- Opción `allow_distinct_strategies` (default **OFF** = comportamiento de hoy): dos `strategy_version`
  distintos sobre misma cuenta/instrumento/barra compiten como **dos oportunidades legítimas**, sujetas al
  **optimizador de cartera** (capital/correlación), no al dedupe ciego. Cuando dos estrategias seleccionadas
  no son representables en una sola posición, se declara
  (`signal_distinct_strategy_not_representable`) en vez de emitir dos veces.

### 3.7 `AUTO-7` self-evaluation (módulo puro, read-only)

- `packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py`: agrega por `strategyVersion`
  expectancy, win rate, profit factor, MAE/MFE, contribución al drawdown, slippage, coste de rechazo y coste
  de oportunidad, y **reconcilia el embudo** (`seen == traded + rejected + expired + missed`).
- **Declara huecos, no los rellena**: sin oportunidades el embudo queda **abierto** (`seen = None`), un coste
  sin precios se declara **no medido** (nunca `0.0`), un ciclo repetido se cuenta **una vez** y se declara, y
  un ciclo sin versión de estrategia **no se reparte** entre estrategias.
- El puente con lo durable vive en `auto_self_evaluation_feed.py` (reconstruye ciclos desde
  `SimFillFinanceContext`) y se expone en **`GET /api/v1/auto/self-evaluation?version=…`** (fail-closed sin
  ámbito de cuenta).
- **Sin UI en esta fase** (es la fase siguiente, `AUTO-8`/UI): el módulo no toca pesos ni sizing.

### 3.8 UI: valor esperado + primer slice móvil

- Backend: el journal de AUTO publica `expectedR`, `netExpectedCurrency`, `expectedMeasurement` y
  `expectedNotes` (aditivos); el DTO de estudio los lleva al cliente y `openapi.json`/`schema.d.ts` se
  regeneran.
- Shared: formateador **propio** (`expected-value-copy.ts`, con signo y `€`; el de dinero de la casa no añade
  ni signo ni moneda) y `expectedR`/`netExpectedCurrency` en `EntryOperatingSizingV1` y en el panel «¿Por
  qué?». **Lo no medido no se pinta** (ni un `0 €`).
- Móvil (deuda más antigua): primer slice responsivo sobre los seis componentes _cabin_ de más valor
  (`entry-operating-summary`, `decision-explain-panel`, `operativa-cockpit-card`, `auto-desk-panel`,
  `f3-protect-stop-block`, `exit-route-view`) con un **único** módulo (`use-narrow-cabin.ts`), el hook
  `use-media-query` **endurecido** (`matchMedia` puede no existir: jsdom) y un stub de viewport de test
  (`test-viewport.ts`). Cada componente declara su ancho con `data-cabin-width` para que el layout sea
  **medible** en test, y **nada se oculta** al estrechar (se apila, no se recorta).

### 3.9 Gate de CI

- `python-ci.yml` (`quality`): `--ignore` de las **tres** suites PG nuevas (sin PG en ese job, skipearían en
  mudo) y **registro explícito de los cuatro ficheros de test de aplicación nuevos** de `V2.47` (no entran por
  el pase de directorio de `packages/py/analytics/tests`): sin registro, sus gates no correrían **nunca**.
- `release-tag-ci.yml` (`lifecycle-pg`): gates `AUTO_HARDKILL_PG_REQUIRED`, `AUTO_CRASH_INJECT_PG_REQUIRED` y
  `AUTO_MULTIPROCESS_PG_REQUIRED`, con **paso dedicado** por suite, `set -o pipefail`, `tee` a log y **guard
  anti-skip** (`grep` de `skipped`), replicando el patrón de las gates ya existentes.

---

## 4. Gate (lo que mide el roadmap)

| Roadmap                                              | Cómo se mide aquí                                                                                                        |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| §8 `AUTO-6` — "un crash no duplica ni pierde"        | HardKill durable (engage→crash→restart→release) + matriz de inyección de crash + multi-proceso, **con gate obligatorio** |
| §9 `AUTO-7` — "toda oportunidad termina auditada"    | Embudo `seen == traded + rejected + expired + missed` con motivo y coste declarado; ausencia de dato **declarada**       |
| Deuda declarada de `v2.43.2` §3 (halt en RAM)        | Cerrada: la parada dura es **durable** y se relée en el arranque                                                         |
| Deuda declarada de `v2.43.2` §4 (release sin emisor) | Cerrada por la vía **operador/reconciliación** con `reconciliation_id` obligatorio                                       |
| Defecto de auditoría (EV largo-only)                 | `expected_value.py` direccional + veto fail-closed de `SELL` en el motor                                                 |

---

## 5. Criterios de salida

1. `ruff` / `mypy` / `lint-imports` limpios con las invocaciones **de CI**.
2. Los dos bloques offline (targets **extraídos del YAML**) verdes, y **todos** los ficheros de test nuevos
   dentro de la red (o registrados explícitamente).
3. Las suites PG nuevas verdes **con su gate** (no basta con que no fallen: no deben **skipear**).
4. Matriz de mutaciones **medida** (no esperada) y árbol **intacto** al terminar la sonda.
5. `v2_43_governor_evidence.py`: `git diff` vacío y `exit 0`.
6. Docs de la fase (plan + pack + relevo), `CHANGELOG` y **bump** de versión.

---

## 6. Límites previstos (declarar, no maquillar)

- **El reparto en dos releases se sella junto** (§7.1): el hardening de `AUTO-6.x` viaja en el mismo tag que
  la trazabilidad de `V2.47`.
- `BROKER_DESYNC` sigue **sin productor** (motivo del `Literal` con emisor ausente).
- El broker SIM sigue liquidando por tick en el camino del "Crash Day" de proceso: la ventana mid-fill se
  cubre con la **matriz de inyección** (PG), no moviendo el broker.
- La **UI de AUTO-7** no entra aquí; el endpoint queda servido y sin superficie.
- El gobernador sigue **default OFF** con umbrales sin calibrar (deuda de `AUTO-3` slice 1, intacta).

---

## 7. Estado de ejecución (cerrado 2026-09-21)

Las doce piezas del relevo se ejecutaron **en un solo árbol**:

| Pieza (id)            | Estado | Dónde se ve                                                                     |
| --------------------- | ------ | ------------------------------------------------------------------------------- |
| `ev-direction`        | HECHO  | `expected_value.py` direccional + `entry_direction` (veto fail-closed)          |
| `ev-tests`            | HECHO  | `test_expected_value.py` (19) + M8/M9/M10/**M18** de la matriz                  |
| `hardkill-hermetic`   | HECHO  | `test_auto_v46_hardkill_recovery.py` (5)                                        |
| `hardkill-pg-release` | HECHO  | `test_auto_v46_hardkill_recovery_pg.py` (2) + `POST …/durable-release`          |
| `crash-matrix`        | HECHO  | `test_auto_v46_crash_injection_matrix.py` (6) + gemelo PG (2)                   |
| `multiproc`           | HECHO  | `test_auto_v46_multiprocess_pg.py` (1) + `N ∈ {2,3,5,10}` en hermético y PG     |
| `ci-gates`            | HECHO  | ignores + gates + pasos anti-skip, **y** registro de los tests nuevos           |
| `cycle-id`            | HECHO  | migración `044`, `cycle_id` en journal/plan/posición/reserva/salida/fill        |
| `signal-identity`     | HECHO  | `candidate_key`, `allow_distinct_strategies`, journal de superadas              |
| `auto7`               | HECHO  | `auto_self_evaluation.py` (16) + `auto_self_evaluation_feed.py` (13) + endpoint |
| `ui-ev`               | HECHO  | `expected-value-copy.ts`, DTOs, `entry-operating-summary` y «¿Por qué?»         |
| `ui-mobile`           | HECHO  | `use-narrow-cabin.ts` + 6 componentes + `data-cabin-width` medible en test      |

### 7.1 Desviaciones declaradas frente a lo que este plan decía

1. **Un solo sello en vez de dos releases.** El plan repartía `V2.46.x` (hardening) y `V2.47`
   (trazabilidad) en dos releases. El árbol entregado los sella **juntos** en `1.72.0-beta` porque la
   migración `044` (trazabilidad) es **incompatible** con declarar un `V2.46.x` "sin migración" una vez que
   ambos trabajos conviven: partir el sello exigiría reescribir historia publicada. **Consecuencia
   honesta:** quien audite `V2.47` audita también el hardening de `AUTO-6.x`; el pack lo separa por fases.
2. **Se añadió un sensor que el plan no pedía explícitamente.** El plan pedía mutar "la propagación de
   `direction` a `estimate_trading_cost`"; la mutación **M18** existe, pero al medirla se comprobó que
   **ninguna** suite la mordía: el test del coste corto era **autorreferencial** (recalculaba el neto a partir
   del propio `cost_currency`). Se **endureció el test** (tarifario real de cuenta, donde la pata de salida de
   la corta se cobra sobre su propio stop) **antes** de declarar M18 medida. Es cobertura nueva, declarada.
3. **Se registraron cuatro ficheros de test en el job `quality`.** Los tests de aplicación de `V2.47`
   (`test_auto_v47_cycle_trace`, `test_auto_v47_expected_value_journal`, `test_auto_v47_signal_identity`,
   `test_auto_self_evaluation_feed`) **no** entraban por ningún pase de directorio del job `quality` (ese job
   enumera a mano `packages/py/application/tests`): sin registrarlos, sus gates no habrían corrido en CI
   **nunca**. Es exactamente la deuda que `v2.42.2` cerró a mano para `test_auto_daily_journal.py`.
4. **El `--ignore` del tag no se tocó para el hermético nuevo**: los dos ficheros herméticos de `V2.46.x`
   entran por el pase de directorio de `apps/api-python/tests` (comprobado en la medición del bloque `python`
   del tag, §8).
5. **El endpoint de liberación vive en el router de `risk`** (no en uno nuevo): es la superficie natural de
   la parada dura y evita duplicar el vocabulario de kill switch.

### 7.2 Límites (confirmados al ejecutar)

Los de §6, más: `expectedNotes` viaja en el `payload` **solo** cuando hay notas (no se publica una lista
vacía); el `expectedR`/`netExpectedCurrency` del journal se toma del **candidato del optimizador** cuando
existe y, si el optimizador no corrió, se **recalcula con la misma geometría que dimensionó la decisión**
(`_expected_value_for_decision`), de modo que lo publicado y lo decidido no puedan discrepar. `NULL` en
`cycle_id` significa "fila anterior a `2.47`", **nunca** "sin ciclo" (no hubo backfill).

---

## 8. Verificación (cada cifra, con el artefacto que la produjo)

| Comprobación                  | Comando (invocación de CI)                                                                                          | Resultado                         |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| Estático                      | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                             | **All checks passed!**            |
| Tipos                         | `uv run mypy … --follow-imports=silent`                                                                             | **491 ficheros, 0 issues**        |
| Fronteras                     | `uv run lint-imports --config packages/py/.importlinter`                                                            | **4 kept / 0 broken**             |
| Evidencia del gobernador      | `uv run python apps/api-python/scripts/v2_43_governor_evidence.py`                                                  | **exit 0** y `git diff` **vacío** |
| Bloque `quality` de CI        | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`     | ver §8 del pack                   |
| Bloque `python` del tag       | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores` | ver §8 del pack                   |
| Suites PG nuevas **con gate** | `AUTO_*_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v46_*_pg.py -q -rs`                             | **5 passed, 0 skipped**           |

### 8.1 Matriz de mutaciones

**MEDIDA** (no esperada): sonda `apps/api-python/scripts/v2_44_mutation_audit.py` — **18 mutaciones, 18
muerden**, restauración byte a byte verificada y huella de `git status` **intacta**. El detalle por mutación y
la nota de método del **bytecode** (`.pyc` con mtime a segundos ⇒ se borra el bytecode de cada módulo mutado y
se corre con `PYTHONDONTWRITEBYTECODE=1`) están en el §10 del pack.

### 8.2 Sello

Pendiente de producir en el momento de escribir este plan: commit de fase, `main`, tag `v2.47-beta` y CI real
observada con `gh` (bloques offline y CI del tag). La evidencia se añade en el commit de sellado docs-only, con
los **runs** enlazados (convención de `v2.43.2`/`v2.44`/`v2.45`/`v2.46`).
