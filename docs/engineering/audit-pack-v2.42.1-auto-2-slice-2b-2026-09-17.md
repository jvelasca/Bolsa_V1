# Audit pack — V2.42 / AUTO-2 slice 2b: `TIME_EXIT`, `THESIS_EXIT`, ATR real y hallazgos H-1..H-7 (`1.67.1-beta`)

> **Para quién es esto:** quien audita `v2.42.1-beta` sin acceso al entorno de desarrollo. Afirmaciones
> verificables, mapa de código, matriz de mutación **medida**, comandos listos y límites declarados.
> **Arranque (orden de lectura):** [`arranque-auditor-v2-42-1-auto-2-slice-2b-2026-09-17.md`](./arranque-auditor-v2-42-1-auto-2-slice-2b-2026-09-17.md).
> **Base:** [`audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md`](./audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md)
> (slice 2a, tag `v2.42-beta`) y, dentro de él, el **§9** con los siete hallazgos de código que este slice
> cierra. Decisiones de alcance: [`traspaso-relevo-post-v2-42-auto-2-2026-09-17.md`](./traspaso-relevo-post-v2-42-auto-2-2026-09-17.md) §4.2 (D1..D6, con la
> firma del owner en D2/D3/D6).
> **Hoja de ruta:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §4.

**Bump:** `1.67.0-beta` → `1.67.1-beta`. **Migración: NINGUNA** (Alembic head sigue en
`042_portfolio_reservations`). El techo de mantenimiento (`holdingDeadlineAt`) y el nivel de invalidación
(`invalidationPrice`) viajan en el **mismo JSONB** `sim_auto_positions.position_state` (migración `040`):
la decisión **D5** del relevo era no abrir migración `043` y se ha respetado.

**Alcance:** cierra los E1/E2/E3 de `AUTO-2` (§4 del roadmap) y los **siete hallazgos H-1..H-7** del §9 del
pack de 2a.

---

## 1. Qué afirma esta versión (y qué no)

**Afirma**

1. **El techo de mantenimiento existe, se congela y vence.** El horizonte se resuelve por plantilla de
   política (`resolve_holding_horizon`) y se **escribe en el nacimiento** de la posición; la gestión recibe
   `now` **y** `expires_at` en el mismo acto. Alcanzado el techo, la posición **vende** (`TIME_STOP`) y el
   FSM queda con `TIME_EXIT` y el journal con `time_exit`.
2. **La invalidación confirmada de la tesis vende** (D2, firmada por el owner): `EXIT` real con
   `thesis_exit` en el journal, no un `REVIEW`. El juicio se apoya en hechos **persistidos** (nivel de
   invalidación congelado + peor adverso `maeR`), no en una recómputo del motor de señales.
3. **La marca del tick persiste.** El pico del trailing y el `maeR` se escriben en el espejo durable
   cuando **cambian de verdad** (dos sensores independientes, cada uno con su test): un reinicio no
   olvida el peor adverso ni el ancla del trailing.
4. **El ATR real se prefiere y la reserva se declara.** `AtrSource` calcula el ATR por símbolo desde
   barras; el worker deja de fabricar el 2 % en el origen y declara `atrSource` (`real`/`fallback`/
   `missing`) en el journal. Con `AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` una señal sin ATR real **no entra**
   (`atr_unknown`).
5. **Los siete hallazgos del §9 están cerrados** (H-1..H-7) con su gate: `RECONCILED` verificado,
   `PROTECT` con efecto nunca mudo, `PARTIAL_EXIT` sin armar trailing, sin pico no hay trailing,
   finitud con `math.isfinite`, `lifecycleState: null` degrada, y FSM **forward-only**.

**No afirma**

- **No** afirma haber medido PG real en la máquina del slice 2b: el DSN local no responde ni rechaza (el
  `connect` se cuelga, medido) ⇒ los **6 tests PG nuevos** se certifican en CI, no aquí. Cualquier
  afirmación en contrario sería falsa y este pack no la hace.
- **No** afirma que el criterio de salida completo de `AUTO-2` esté cerrado en producción: el **veto**
  de ATR nace **OFF** (D3: primero medir), el horizonte depende de que la plantilla de política tenga
  `max_holding_period_days`, y el emisor de `RECONCILED` sigue sin existir en el worker (la
  reconciliación real es de la fase siguiente).
- **No** afirma que el FSM repare: **declara**. Salir de `RECONCILIATION_REQUIRED` exige un hecho
  verificable o un `RECONCILED` explícito que hoy **nadie emite** en el camino del worker.
- **No** afirma paridad con el motor legacy en el camino flag-off: `protection_compat` (2a) sigue siendo
  el dueño de esa reproducción y aquí no se toca.

---

## 2. Punto de partida verificado (lo que este slice cierra)

| Deuda declarada en 2a                                        | Por qué era dinero                                                                                                         | Qué la cierra aquí                                                      |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `TIME_STOP` **inalcanzable** (`expires_at` nunca llegaba)    | una posición podía quedarse abierta indefinidamente con el capital y el riesgo ocupados                                    | B1, B2, B5 (deadline congelado + `now`/`expires_at` + evento y journal) |
| `THESIS_EXIT` fuera del FSM y `THESIS_INVALIDATION ⇒ REVIEW` | la posición **sobrevivía a su propia invalidación**: el AUTO declaraba la tesis rota y no vendía                           | B3, B4 (D2 firmado)                                                     |
| ATR **sintético** (2 % del precio) fabricado en el origen    | la geometría de riesgo se construía sobre un número inventado, y el veto no podía medirse                                  | B6, B7 (`AtrSource`, `atrSource`, `atr_unknown`, veto tras flag)        |
| Marca adversa **no durable** (vivía en la copia del tick)    | un reinicio olvidaba el peor adverso ⇒ una invalidación ya confirmada volvía a parecer intacta                             | B9 (dos sensores medidos por separado) y su test de reinicio            |
| §9: 7 hallazgos (H-1..H-7)                                   | avanzar sin cerrarlos habría construido encima de un FSM que acepta retrocesos, un no-op mudo y un stop inventado sin pico | B8..B11, cada uno con su mutación y su gate                             |

---

## 3. Matriz afirmación → código → test

### a) E1 · horizonte y `TIME_EXIT` (analytics puro + worker)

| Afirmación                                                    | Código                                                                    | Test                                                                                           |
| ------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| El horizonte se resuelve por plantilla, con default declarado | `exit_policy.resolve_holding_horizon` / `DEFAULT_MAX_HOLDING_PERIOD_DAYS` | `test_exit_plan.py::test_holding_horizon_matches_policy_templates`                             |
| El techo se **congela** al nacer y sobrevive al round-trip    | `position_state.holding_deadline_from`, `to_dict`/`from_dict`             | `test_holding_deadline_is_frozen_at_birth`, worker `..._clock_thesis.py`                       |
| Pasado el techo, la salida es real y con motivo propio        | `position_decision` (`TIME_STOP`), `_next_event` → `TIME`                 | `test_frozen_deadline_becomes_time_stop`, `test_decision_time_stop_exits_with_time_next_event` |
| El journal dice `time_exit` y el FSM queda en `EXIT_PENDING`  | `_v2_journal_exit_request`, `advance_lifecycle`                           | `test_v2_time_exit_sells_and_journals_time_exit`                                               |

### b) E3 · invalidación de tesis y `THESIS_EXIT`

| Afirmación                                                             | Código                                                         | Test                                                                                                                                   |
| ---------------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| El nivel de invalidación se congela (del plan o del stop estructural)  | `position_state._invalidation_level`                           | `test_thesis_invalidation_level_is_frozen_from_plan_or_stop`                                                                           |
| Sin nivel declarado **no** hay invalidación inventada                  | `exit_plan.is_thesis_invalidated`                              | `test_thesis_not_invalidated_without_declared_level`                                                                                   |
| Con nivel cruzado, la invalidación es un hecho, también tras recuperar | `worst_adverse_price` (sobre `maeR` persistido)                | `test_thesis_invalidated_when_frozen_level_is_crossed`, `..._survives_recovery_via_persisted_mae`                                      |
| La invalidación confirmada **vende** (`EXIT`, no `REVIEW`)             | `position_decision._action_from_plan`                          | `test_decision_thesis_invalidated_exits`, `test_thesis_invalidation_sells_full_position`, `test_thesis_invalidated_is_exit_not_review` |
| Bajo reconciliación `CRITICAL` el veto **se declara** (no se silencia) | rama de `recon_health == "CRITICAL"` en `_action_from_plan`    | `test_decision_thesis_invalidated_under_drift_reviews`, `test_thesis_invalidation_under_recon_drift_reviews_not_sells`                 |
| Un stop-out **no** se atribuye como salida por tesis                   | `_v2_journal_exit_request` (mira `primary_reason`, no el flag) | `test_v2_stop_out_is_not_declared_as_thesis_exit`                                                                                      |

### c) E2 · ATR real, declarado, y veto fail-closed

| Afirmación                                                       | Código                                                   | Test                                                                                                                  |
| ---------------------------------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| El ATR real se calcula desde barras (y no se inventa si no hay)  | `auto_v2_entry.AtrSource`                                | `test_atr_source_computes_real_atr_from_bars`, `..._fail_closed_without_bars`, `..._provider_error_is_not_a_number`   |
| El worker prefiere el real y declara el origen                   | `_v2_atr_geometry`, journal `atr_geometry`               | `test_v2_entry_uses_real_atr_geometry`, `test_v2_synthetic_atr_is_declared_as_fallback`                               |
| El veto convierte "sin ATR real" en NO ENTRY con motivo honesto  | `plan_v2_tick` + `portfolio_decision_engine.atr_unknown` | `test_plan_v2_tick_atr_required_vetoes_synthetic_geometry`, `..._allows_real_geometry`, `test_atr_required_reads_env` |
| La declaración del origen se emite una vez por (símbolo, origen) | `_v2_atr_journaled`                                      | cubierto por el no-inundación del journal del tick (`test_v2_journal_records_reason_codes`)                           |

### d) Hallazgos H-1..H-7 (§9 del pack de 2a)

| Hallazgo                                                                      | Código                                                      | Test                                                                                                                                                           |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **H-1** `RECONCILED` sólo desde degradado, con estado verificado y cantidad   | `position_lifecycle.apply_lifecycle_event`                  | `test_reconciled_rejected_from_non_degraded_state`, `test_reconciled_rejected_when_ledger_contradicts_target`, `test_reconciled_requires_verified_target`      |
| **H-2** todo `PROTECT` con efecto deja traza; la marca se persiste al cambiar | `_v2_protect_noop_stop`, `_mark_observation_changed`        | `test_v2_protect_is_never_silent`, `test_v2_adverse_mark_is_persisted_not_only_in_the_tick_copy`, `test_v2_favourable_mark_is_persisted_even_without_r_memory` |
| **H-3** `PARTIAL_EXIT` no arma el trailing                                    | `position_lifecycle.is_trail_armed`                         | `test_partial_exit_alone_does_not_arm_trailing`                                                                                                                |
| **H-4** sin pico no hay trailing (no se cae al precio de entrada)             | `position_lifecycle.compute_trail_stop`                     | `test_trail_stop_needs_a_watermark`, `test_trail_stop_needs_real_risk`                                                                                         |
| **H-5** finitud con `math.isfinite` (un `+inf` no pasa por positivo)          | `position_lifecycle._finite`, `position_state`, `exit_plan` | `test_non_finite_watermark_and_stop_are_rejected`                                                                                                              |
| **H-6** `lifecycleState: null` explícito degrada                              | `position_state.position_state_from_dict`                   | `test_rehydration_degrades_explicit_null_lifecycle`, `test_rehydration_validates_legacy_status_against_quantity`                                               |
| **H-7** FSM forward-only (ninguna transición retrocede)                       | `_LIFECYCLE_LADDER`, `_forward_target`, `_TRANSITIONS`      | `test_management_ladder_never_goes_backwards`                                                                                                                  |

### e) Red de seguridad de CI

| Fichero                                                        | Job offline                                                                                   | Job con PG real                                                             |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `packages/py/analytics/tests/test_position_lifecycle.py`       | `quality` (pase de `analytics`)                                                               | —                                                                           |
| `packages/py/application/tests/test_auto_v2_entry.py`          | `quality` (explícito)                                                                         | —                                                                           |
| `apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py` | `quality` (lo cubre el pase de directorio `apps/api-python/tests`) + `python` (**explícito**) | —                                                                           |
| `apps/api-python/tests/test_auto_v2_lifecycle_pg.py`           | `--ignore` (un skip mudo no certifica)                                                        | `auto-v2-durable-pg` / `lifecycle-pg` con `AUTO_V2_LIFECYCLE_PG_REQUIRED=1` |

---

## 4. Matriz de mutaciones **medida** (13 mutaciones, 13 rojos)

Método: cada mutación se aplica sobre el árbol de trabajo, se corre el **target acotado** y se revierte
comprobando que el fichero recupera **exactamente** su contenido de partida (si no, la medición se aborta).
Ninguna mutación se declara sin medir y ninguna se mide con el árbol moviéndose.

| #   | Mutación (rompe el comportamiento, no la línea)     | Rojos | Test que cae                                                                            |
| --- | --------------------------------------------------- | ----- | --------------------------------------------------------------------------------------- |
| M1  | La gestión no recibe `expires_at`                   | 1     | `test_v2_time_exit_sells_and_journals_time_exit`                                        |
| M2  | El techo no se congela en el nacimiento             | 5     | 3 de analytics + 2 de worker                                                            |
| M3  | `thesis_invalid=False` en la mesa                   | 1     | `test_v2_confirmed_thesis_invalidation_sells_full_position`                             |
| M4  | El stop-out se atribuye como `THESIS_EXIT`          | 1     | `test_v2_stop_out_is_not_declared_as_thesis_exit`                                       |
| M5  | La invalidación vuelve a `REVIEW` (conducta de 2a)  | 2     | `test_decision_thesis_invalidated_exits` + `test_thesis_invalidated_is_exit_not_review` |
| M6  | El ATR real se ignora                               | 2     | `test_v2_entry_uses_real_atr_geometry` + veto                                           |
| M7  | El veto por ATR real no veta                        | 1     | `test_plan_v2_tick_atr_required_vetoes_synthetic_geometry`                              |
| M8  | Sin pico el trailing cae al precio de entrada       | 2     | `test_trail_stop_needs_a_watermark`, `test_trail_stop_needs_real_risk`                  |
| M9  | `RECONCILED` se acepta desde cualquier estado       | 1     | `test_reconciled_rejected_from_non_degraded_state`                                      |
| M10 | La marca no se persiste por el sensor de **precio** | 1     | `test_v2_favourable_mark_is_persisted_even_without_r_memory`                            |
| M11 | `lifecycleState: null` explícito no degrada         | 1     | `test_rehydration_degrades_explicit_null_lifecycle`                                     |
| M12 | La escalera permite retroceder                      | 1     | `test_management_ladder_never_goes_backwards`                                           |
| M13 | La marca no se persiste por el sensor de **`maeR`** | 1     | `test_v2_adverse_mark_is_persisted_not_only_in_the_tick_copy`                           |

**Dos mutaciones nacieron verdes y el diagnóstico importa** (está en el CHANGELOG y aquí porque es
metodología, no ruido):

- **M5**: «desactivar» la rama del `EXIT` la dejaba pasar por la puerta de atrás (`suggested_action ==
"full_exit"`), así que la mutación era un **no-op semántico**. La mutación correcta es devolver
  `REVIEW` (la conducta exacta de 2a) y entonces sí cae.
- **M10/M13**: los dos sensores de la marca (pico en precio / `maeR`) **se tapaban entre sí**; cada
  mutación por separado quedaba verde. Se añadieron los **dos tests que aíslan cada sensor** (pico sin
  memoria en R y un **segundo** extremo adverso con el pico quieto) y ahora cada uno cae por su cuenta.

Un auditor debe poder reproducir esta tabla con el script de §7. Si alguna mutación **no** cae en su
árbol, la conclusión no es "el pack miente" sino "falta el test que la mata": se declara y se añade.

---

## 5. Cambios observables y breaking declarado (beta)

- **Journal**: motivos nuevos `time_exit`, `thesis_exit`, `atr_geometry` y el campo `atrSource`
  (`real`/`fallback`/`missing` / `atrRequired` / `vetoed`) en el detalle. Son **aditivos**.
- **Reason code nuevo de decisión**: `atr_unknown` (sustituye a un `risk_reward_below_threshold`
  engañoso cuando lo que falta es el ATR). Los consumidores que mapeen reason codes deben conocerlo.
- **Conducta cambiada (dinero)**: `THESIS_INVALIDATION` pasa de `REVIEW` a **`EXIT`**. Es la decisión D2
  firmada por el owner: **es intencional** y es el cambio más visible del slice.
- **Conducta cambiada (geometría)**: el ATR por defecto sigue siendo el sintético declarado (2 %), pero
  ya **no** se fabrica en el origen: si hay barras, se usa el real. Con
  `AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` el sintético deja de sostener entradas (opt-in, default OFF).
- **FSM**: `TIME_EXIT`/`THESIS_EXIT` son eventos nuevos; el FSM pasa a ser **forward-only** (una
  transición que antes retrocedía ahora es idempotente). Ningún consumidor de `ALLOWED_TRANSITIONS`
  pierde transiciones **hacia adelante**.

---

## 6. Límites declarados (lo que este slice NO resuelve)

1. **PG real sin medir en local** (motivo medido: DSN que no responde ni rechaza ⇒ `connect` colgado).
   La evidencia de durabilidad la aporta CI. **No** hay en este pack ninguna cifra de PG local.
2. **El veto de ATR nace OFF**: D3 pedía cablear y **medir** antes de flipear. La fracción de señales con
   ATR real no se mide aquí en producción; los contadores por origen son medición **interna** (los leen los
   tests, no se publican en ningún snapshot durable).
3. **`RECONCILED` sigue sin emisor** en el camino del worker: H-1 endurece la **puerta**, no la abre.
   Resolver una degradación sigue siendo trabajo de la reconciliación real (fase siguiente).
4. **Horizonte dependiente de plantilla**: si la plantilla de política no declara
   `max_holding_period_days`, el default (`DEFAULT_MAX_HOLDING_PERIOD_DAYS`) manda. La política por
   estrategia (no por template) sigue pendiente.
5. **`atr_source` no es estado durable**: no se persiste con la posición; se recalcula por tick desde
   barras. Un reinicio sin barras cae al sintético declarado (comportamiento fail-closed, no error).
6. **Dualidad `sim_auto_positions` vs `position_states` (ADR-033)**: sigue **declarada**, no unificada.
7. **El FSM declara, no repara** (heredado de 2a y todavía cierto).

---

## 7. Cómo reproducir la verificación

```bash
# 0) Estático con la invocación EXACTA de CI (no añadas packages/py/analytics/src: CI no lo compila)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# 1) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_lifecycle.py \
    packages/py/analytics/tests/test_exit_plan.py \
    packages/py/analytics/tests/test_position_decision.py \
    packages/py/application/tests/test_auto_v2_entry.py \
    packages/py/application/tests/test_position_manager.py \
    packages/py/application/tests/test_v127_golden_path_fail.py \
    apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py \
    apps/api-python/tests/test_auto_v2_worker_integration.py -q

# 2) Offline del job `quality` (lista y --ignore EXTRAÍDAS del YAML; los ficheros PG que en CI
#    saltan por falta de servidor se ignoran explícitamente si tu DSN local cuelga)
uv run pytest packages/py/domain/tests packages/py/market/tests packages/py/analytics/tests \
    packages/py/application/tests apps/api-python/tests -q --ignore=apps/api-python/tests/integration \
    $(grep -o '\-\-ignore=[^ ]*' .github/workflows/python-ci.yml | sort -u)

# 3) PG real (certificación). Un skip es FALLO.
AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q

# 4) Matriz de mutación (13 mutaciones; cada una debe poner el target en ROJO)
#    El script aplica / corre / revierte y aborta si un fichero no vuelve a su contenido exacto.
```

---

## 8. Evidencia de verificación

### 8.1 CI real de GitHub

Pendiente de sellado: se completa en el commit docs-only posterior al tag `v2.42.1-beta` (runs de
`Python CI` en `main` y en la ref del tag, y `Release tag CI`), con el mismo criterio que el pack de 2a:
la cifra que manda es la de CI, y la de local se declara con su procedencia.

### 8.2 Baterías locales (medidas en el árbol final del slice, antes de publicar)

- `ruff`: **All checks passed!** · `mypy`: **487 ficheros, 0 issues** · `lint-imports`: **4 kept / 0 broken**.
- Bloque **offline** del job `quality` (`python-ci.yml`): **1914 passed, 0 failed, 0 skipped** (51,7 s),
  con los **targets y los `--ignore` extraídos del YAML** por un runner que además **verifica que cada
  ruta existe** (una ruta inexistente aborta la medición en vez de medir otra cosa). Procedencia: 2 tests
  nuevos respecto a la medición anterior (el del pico sin memoria en R y su endurecimiento) y **6 ficheros
  PG movidos a `--ignore`** con motivo medido (en CI saltan rápido porque no hay servidor; aquí el
  `connect` del DSN **se queda colgado**), más `--noconftest` para no depender del conftest de la app (que
  también habla con PG).
- Bloque **offline** del job `python` de `release-tag-ci.yml`: **1925 passed, 0 failed, 0 skipped**
  (18,4 s), misma lista extraída del YAML y **mismo verificador de existencia de rutas** (este job corre
  un conjunto algo mayor: incluye ficheros de orquestador y del worker que el job `quality` no lista).
- **Hallazgo de proceso (declarado, no oculto)**: el primer intento de esta fase añadió a la lista de
  `quality` la ruta `packages/py/application/tests/test_auto_v2_lifecycle_clock_thesis.py`, que **no
  existe** (el fichero vive en `apps/api-python/tests`, que ese job ya recolecta entero). Con la
  invocación de pytest eso es **exit 4** y habría puesto **rojo** el job `quality`. Lo detectó el
  verificador de rutas al re-medir con la lista extraída del YAML, y está corregido: la ruta se eliminó
  (el pase de directorio ya lo cubre) y en `release-tag-ci.yml` se usa la ruta **correcta** explícita.
  Lección para la próxima fase: **medir con la lista extraída del YAML, nunca con una copia a mano**.
- Matriz de mutación: **13/13 rojos** (re-medida sobre el árbol final, con verificación de contenido
  exacto tras cada reversión).
- **PG real: no medido en local** (declarado arriba; el gate es de CI).

---

## 9. Auditoría externa: qué debería intentar romper

1. **El techo congelado**: ¿puede un reinicio recalcularlo? (busca cualquier camino que llame a
   `holding_deadline_from` fuera del nacimiento).
2. **La invalidación**: ¿hay alguna forma de que `is_thesis_invalidated` diga "sí" **sin** un nivel
   declarado, o de que un stop-out se lea como salida por tesis?
3. **El ATR**: ¿puede el worker fabricar geometría sintética **sin** declararla en el journal, o el veto
   activarse dejando entrar la candidata?
4. **La marca**: ¿hay un tick que cambie el estado de la marca y **no** se persista (pico y `maeR` son
   independientes: busca el caso en que uno cambie y el otro no)?
5. **El FSM**: ¿existe alguna secuencia de eventos que haga retroceder un estado? (la escalera es
   `OPEN < PROTECTED < T1_REACHED < PARTIAL_EXIT < TRAILING < EXIT_PENDING < CLOSED`).
6. **H-1**: ¿se puede salir de `RECONCILIATION_REQUIRED` con una cantidad que contradice el estado
   resuelto?
7. **CI**: ¿hay alguna **ruta inexistente** en las listas de `python-ci.yml`/`release-tag-ci.yml`? Con la
   invocación de pytest eso es **exit 4** (job rojo) y un runner con copia manual de la lista no lo ve
   (pasó en esta fase y se corrigió antes del sello: §8.2).
8. **Alcance**: ¿el slice declara en algún sitio algo que no haya medido? (el pack declara explícitamente
   que **PG no se midió en local** y que la lista de targetos se **extrae del YAML**; si encuentras una
   afirmación de lo contrario, es un hallazgo).
