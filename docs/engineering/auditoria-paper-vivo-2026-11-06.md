# Auditoría del PAPER vivo — corte 2026-11-06 (BLOCKED por MATERIAL, no por kill switch)

- **Fecha del corte:** 2026-11-06 07:39Z (08:39 local) · corrida viva, `seq` durable **296**
- **Estado actual (§9):** la corrida **cerró sola** a las **11:40:35Z** con **400/400** ticks,
  `stopReason = completed`, `manifest.status = MEDIDO` y gate **`INCONCLUSIVE`**. Este documento
  conserva el corte original y añade el contraste (§4.4) y el cierre (§9); no se reescribió el
  diagnóstico de las 07:39Z.
- **Árbol que corre:** `.cursor/worktrees/window-seal-183` @ `d8a5d0f9` (pin operativo `3e092888`)
- **Base:** PostgreSQL `bolsa_v1` en **`065_auto_engine_intent`**
- **Naturaleza:** auditoría **read-only** (solo `SELECT`; `PGOPTIONS=-c default_transaction_read_only=on`)
  + una deuda de ciclo de vida cerrada **en rama aparte** (`fix/forward-lease-close-2026-11-06`),
  fuera del worktree pinneado. **No** se reinició ni señalizó el proceso, **no** se migró, **no** se
  lanzó otro `run-day`, **no** se tocó el sello.
- **Ampliación (§4.4):** contraste de H-1 a las **08:05Z** (`seq` durable **322**), mismo proceso
  vivo, misma base 065 y misma sesión read-only. Cierra la causa raíz que el corte de 07:39Z dejaba
  abierta, sin corregir nada ni tocar la corrida.
- **Predecesor:** [cadencia-paper-desbloqueo-2026-11-05.md](./cadencia-paper-desbloqueo-2026-11-05.md)
- **Nota de ubicación:** el plan pedía `docs/paper/`; ese directorio no existe. Se publica en
  `docs/engineering/`, que es donde vive el resto de expedientes PAPER.

## 0. Dictamen

| Medida | Valor | Lectura |
| --- | --- | --- |
| Proceso | vivo (`node` 19492 → `python` 43188) | tick cada ~62 s, lease `auto-sim-43188-496fe27b` gen 2 |
| `verdict` del gate | **`BLOCKED`** | `no closed cycles` + `insufficient measurable cycles per strategy` |
| Kill switch | **NO activo** | todos los ticks durables escriben `state=RUNNING` |
| Material | **congelado** desde 5/11 18:40Z | 13 fills, 3 posiciones abiertas, 1 salida, 0 cierres |
| Dinero real | **No** | `venue=paper`, ejecución simulada, sin ruta LIVE |
| Cobertura del árbol `.184` | **No certificada** | la corrida nace en `d8a5d0f9`, no en `05926dc` |
| BD | **065 conservada** | coherente con el árbol; **no migrar** con la corrida viva |

`BLOCKED` **no es un fallo del proceso**: es el diagnóstico correcto de un material que todavía no
tiene ningún ciclo cerrado. Lo que **sí** es un hallazgo es que el material está congelado desde
hace trece horas (§4).

## 1. Base exacta: qué árbol contiene el PAPER vivo

Coexisten tres árboles y solo uno conduce la corrida. La confusión de las auditorías previas viene
de mezclarlos.

| Árbol | HEAD | Migraciones | Rol |
| --- | --- | --- | --- |
| Raíz de desarrollo | `05926dc` (`chore/sello-2.11.184-beta`) | hasta **066** | código publicado; **no** es el que corre |
| Worktree `window-seal-183` | **`d8a5d0f9`** (pin `3e092888`) | hasta **065** | **este es el que corre** |
| Base `bolsa_v1` | — | `065_auto_engine_intent` | confirmado en `alembic_version` |

No falta ningún tramo 058-065: en
`packages/py/infrastructure/alembic/versions` del worktree están `058_estudio_daily_proposals` …
`065_auto_engine_intent`, y `066_account_evidence_policy` solo aparece en la rama `.184`.

**Cadena de procesos real** (corrige el “PID 27264”):

```text
powershell 27264  (lanzador: -File ...\Temp\ps-script-a086ec89-....ps1)
  └─ node   19492  (window-forward-runner.mjs run-day --force)  ← PID declarado en .run.lock/lock.json
       └─ python 16376  (.venv del worktree)
            └─ python 43188  (intérprete de uv; dueño real del lease 'auto-sim-43188-496fe27b')
```

`27264` no aparece en ninguna tabla ni endpoint porque es el PowerShell del lanzador. El PID que la
aplicación sí declara es **19492**, en
`operability_runs/window-runs/20261105/.run.lock/lock.json`.

## 2. Por qué `verdict=BLOCKED` (y por qué no es el kill switch)

El proceso vivo **no es** `PaperAutoEngine`. `v2_76_forward_market_material.py` no importa
`paper_auto_engine`, ni `PaperAuto`, ni `kill_switch`, ni `RISK_KILL`; el `BLOCKED` que aparece en
`forward.out.txt` lo imprime `_print_progress` a partir de `readiness.verdict`.

Prueba de que el kill switch no está puesto: el estado de cada tick durable se calcula con
`blocked = self._kill_active() or self._v2_kill_switch_halted()`. Todos los ticks del motor
`auto-window-1484e253` están en `state=RUNNING`: **296** al corte (los 66 de hoy, `seq` 231-296) y
**299** al re-verificar minutos después, sin una sola fila `BLOCKED`. Si el kill switch estuviera
activo, la columna diría `BLOCKED`. `RISK_KILL_SWITCH` tampoco existe en el `.env` del árbol.

El gate real, ejecutado contra la cuenta `1484e253d2d54645945a6b1d7` con la pieza del runner
(`_read_readiness` → `build_paper_material_readiness`, sello `paper_material_readiness_v3`):

```json
"verdict": "BLOCKED",
"blockers": ["no closed cycles", "insufficient measurable cycles per strategy"],
"producerBlockers": ["no closed cycles"],
"facts": {
  "durableFills": 13, "fillsWithCycle": 13, "buys": 9, "sells": 4,
  "reservations": 6, "reservationsWithCycle": 6, "reservationsLive": 0,
  "closedCycles": 0, "measurableCycles": 0, "maxMeasurableCyclesPerVersion": 0,
  "versionsWithoutClosedCycles": ["v283-window-a"]
},
"lineage": {
  "cycle": {"exitOrders": 1, "exitOrdersWithCycle": 1},
  "closure": {"closedCycles": 0, "closedCyclesWithRisk": 0}
}
```

Lectura: el linaje **está completo** (13/13 fills con `cycle_id`, 6/6 reservas con ciclo, 1/1
salida con ciclo). Lo único que impide `PRODUCER_READY` es que **ningún ciclo ha cerrado**, y eso
es exactamente lo que el gate declara. No hay defecto del instrumento.

## 3. El material, medido

| Hecho | Valor | Ventana (UTC) |
| --- | --- | --- |
| Fills durables | **13** (9 `buy` / 4 `sell`), 13 con `cycle_id`, 3 ciclos | 5/11 18:39:16 → 18:40:19 |
| Procedencia del precio | **13/13 `MARKET_CLOSE`** | — |
| Reservas | **6**: 3 `RELEASED_BY_FILL` (`fill`) y 3 `RELEASED_BY_CANCEL` (1 `tail_dead` + 2 `cancel`) | 5/11 18:39 → **6/11 07:39** |
| Órdenes de salida | **1** (`FILLED`, con `cycle_id`) | 5/11 18:40:18 |
| Posiciones abiertas | **3**: `0ade61…` 106.53 · `02f456…` 44.88 · `103c29…` 37.98 (`PARTIAL`) | sin cambios desde 18:40-18:41 |
| Barras de las 3 posiciones | `1d`, 1285-1286 filas, última barra **2026-11-05** | ingesta 5/11 17:29-17:52 |

Dos consecuencias que conviene retener:

1. **Los fills se ejecutaron con cierre durable, no con cotización viva.** El bridge sí sirve precio
   vivo hoy (verificado: `SAN.PA last 84.232` a las 07:36:20Z), así que es un problema del arranque
   del 5/11, no del momento actual. La base del watch solo tiene barras `1d` (última, 2026-11-05):
   no hay intradía para medir excursión.
2. **No hay ningún ciclo cerrado** porque de las 3 posiciones abiertas solo una ha tocado salida
   parcial (`103c29…`, `target_1` ejecutado el 5/11 18:40:19; `remaining_qty` 37.98). Un ciclo nace
   al cerrarse la posición completa, no al salir un tramo.

## 4. Hallazgo ABIERTO (H-1): el material se congeló y el motor dejó de declarar la gestión

No estaba en ninguna de las dos auditorías. Es el hallazgo que hay que perseguir **después** de que
la corrida cierre; aquí solo se documenta lo medido.

### 4.1 Qué se observa

- **Cero fills y cero órdenes de salida desde el 5/11 18:40:19Z** (~13 h, ~160 ticks: `seq` 134-296).
- Las **3 posiciones** siguen abiertas y **no se han vuelto a tocar**: `updated_at` =
  5/11 `18:40:19`, `18:40:19`, `18:41:21`.
- **Cambio de contenido de los ticks tras el parón largo**:

| Ticks | Ventana (UTC) | `reason` | `vetoes` |
| --- | --- | --- | --- |
| 133-134 | 5/11 18:39-18:40 | `hold_no_op`, `target_1` | 77-79 |
| 135-230 | 5/11 18:41 → 23:08 | `hold_no_op, trail` | 80 |
| **231-296** | **6/11 06:32 → 07:39** | **`idle`** | **0** |

- **Huecos de tick** (standby de la máquina, no fallos del runner): `18:48:49 → 19:41:44` (52 min),
  `20:14 → 20:52` (38 min), `21:31 → 22:53` (1 h 21 min) y **`23:08:20 → 06:32:38` (7 h 24 min)**.
  Tras el último hueco, el motor sigue ticando pero ya no declara ni el `hold_no_op` de sus
  posiciones ni los 80 vetos de entrada.

### 4.2 Las entradas se siguen intentando y cancelando, sin quedar en el tick

Las dos únicas reservas de hoy (`2323f09f…` y `0fc9b8ca…`, ambas del watch) se escribieron **y se
cancelaron dentro del mismo tick**: `status=RELEASED_BY_CANCEL`, `release_reason=cancel`
(`created_at = released_at`). Y se reescribieron a las **07:32:04Z** y otra vez a las **07:39:14Z**,
con los **mismos `reservation_id`** (`RES-dec-668b1a77105c`, `RES-dec-fa41785acf4b`) pero `tick_id`
y `created_at` nuevos.

Causa mecánica del “se reescribe”: `PostgresReservationStore.reserve` es un **upsert**
(`on_conflict_do_nothing` + `UPDATE` de todas las columnas escribibles, incluida `created_at`), y el
`reservation_id` se deriva de una identidad de decisión estable (`dec-…`). Consecuencia de
auditoría: **la tabla no es append-only para reintentos de la misma decisión**, así que el número de
intentos cancelados no es visible en la base; solo sobrevive el último.

En el mismo instante, el tick durable escribe `proposals=0`, `vetoes=0`, `reason=idle`
(`seq` 289 a las 07:32:04 y `seq` 296 a las 07:39:14). Es decir: **el tick declara “nada” mientras
crea y cancela dos reservas**. El contador `proposals` del `TurnReport` no refleja esos intentos.

### 4.3 Lo que NO se afirma

En el corte de las 07:39Z (auditoría original) no se declaraba causa raíz: las hipótesis abiertas
eran (a) que el parón de 7 h dejara el estado de gestión de posición a medias; (b) que el refresco
del decider B (cada 300 s) reintentara el mismo par de entradas y el cierre de turno las retirara
por “orden no materializada”; (c) que el contador `proposals`/`reason` midiera otra cosa que el
intento de entrada.

El contraste de §4.4, ejecutado a las 08:05Z sobre la misma corrida viva, **descarta (a) y (b) como
causa del cambio de contenido de los ticks** y confirma una cuarta: (d) ausencia de la barra de
ejecución `B` del día corriente. `reason=idle` sigue sin ser un estado del motor (§4.4.1): lo que
queda demostrado es **por qué el tick deja de declarar motivos**, no que el motor haya dejado de
evaluar.

### 4.4 Contraste H-1 (2026-11-06 08:05Z): la etapa que se interrumpe es la de PRECIO

Consulta **read-only** (`PGOPTIONS=-c default_transaction_read_only=on`, `SHOW
transaction_read_only` = `on`) contra la misma base `065`, con el proceso vivo intacto. Ventana
medida: `seq` 128-142, 224-236, 284-300 y el último tick (`seq` 322 a las 08:05:50Z).

#### 4.4.1 `idle` es relleno, no un estado medido

`_reason_text` (`auto_engine_state_store.py:63`) escribe `", ".join(reasons or ("idle",))`. Un tick
sin motivos declarados se persiste como `idle`. No existe en el motor una fase “idle”: la fase
operacional es la columna `activity` (`derive_activity`, `auto_simulation_worker.py:988-1019`).

#### 4.4.2 Lo medido, antes y después del hueco

| Ventana | `seq` | `activity` | `proposals` | `vetoes` | `pending_plans` | `reason` |
| --- | --- | --- | --- | --- | --- | --- |
| 5/11 18:31-18:32 | 131-132 | `ANALYZING` | 0 | **80** | 0 | `hold_no_op` |
| 5/11 18:39-18:40 | 133-134 | `APPLYING_RESULT` | 3 → 1 | 77 → 79 | 3 | `hold_no_op`, `target_1` |
| 5/11 18:41 → 23:08 | 135-230 | `ANALYZING` | 0 | **80** | 3 | `hold_no_op, trail` |
| **6/11 06:32 → 08:05** | **231-322** | **`ANALYZING`** | **0** | **0** | **3** | **`idle`** |

Los **92** ticks posteriores al hueco (231-322) son homogéneos: `state=RUNNING`,
`activity=ANALYZING`, `proposals=0`, `vetoes=0`, `pending_plans=3`, `reason=idle`. No hay una sola
fila `NO_ACTIVITY` ni un solo tick con `pending_plans=0`.

Lectura, en el orden en que descarta estados:

1. **No es “sin evaluación”**: `activity=ANALYZING` exige `decided > 0` (`derive_activity`), así que
   el bucle recorrió los 80 símbolos. `NO_ACTIVITY` habría sido el sello de un bucle no recorrido.
2. **No es “sin propuestas” en el sentido de planificador vacío**: el plan SÍ aprobó entradas; por
   eso hay reservas nuevas.
3. **No hay pérdida de estado de posición**: `pending_plans=3` y las 3 filas de
   `sim_auto_positions` siguen ahí; la readopción ocurrió.
4. **La etapa que se interrumpe es anterior a cualquier decisión por símbolo**: `vetoes=0` significa
   que **no se ejecutó ni un `_veto`**, y `hold_no_op` es un `_veto` (`auto_simulation_worker.py:8035`).
   Un tick con precio habría dejado al menos 77-80 vetos, como los 190 ticks anteriores. El único
   `continue` del bucle que **no** añade motivo está en `auto_simulation_worker.py:7940-7944`:
   `raw_price is None` ⇒ `_v2_note_price_missing(symbol)` y salto al siguiente símbolo. Con los 80
   símbolos en esa rama, `reasons` queda vacío y el tick se publica como `idle`.

#### 4.4.3 La causa mecánica: no existe barra `B` del 6/11

| Hecho medido | Valor |
| --- | --- |
| `AUTO_ENGINE_SIM_REAL_PRICE` en la config del runner | **`1`** (`scripts/lib/window-forward.mjs:897`) |
| Fuente de precio del tick | `OhlcvPriceSource` sobre el día de la barra **corriente** `B` (`_compose_price_source`, `auto_simulation_worker.py:9231-9257`) |
| Barras `1d` por día en la base | 3/11: 180 · 4/11: 180 · **5/11: 180 · 6/11: 0** |
| Última barra de las 3 posiciones | `2026-11-05T00:00:00Z` (`last_bar_today = null`) |
| Avisos `precio AUSENTE` | **80**, uno por símbolo del watch, agrupados en `forward.err.txt` líneas 7933-8012 |

`OhlcvPriceSource.execution()` devuelve `None` cuando la barra `B` no está persistida —ése es su
contrato fail-closed declarado, el mismo que documenta `CHANGELOG.md` (W-157-2: cobertura 1/80 ⇒
todo a `HOLD` fail-closed). Desde el cambio de día UTC no hay barra `2026-11-06`, así que **ningún**
símbolo tiene precio de ejecución: no se marca posición, no se dispara `trail`, no se emite orden y
no se veta nada, porque el bucle nunca llega al `RiskGate`.

#### 4.4.4 El parón de 7 h 24 min NO es la causa; es la coincidencia temporal

Los ticks 135-230 (18:41 → 23:08 del 5/11) siguen viendo precio porque `B = 2026-11-05` y esa barra
sí está ingerida. El hueco `23:08:20 → 06:32:38` **atraviesa la medianoche UTC**, y por eso el
primer tick posterior (`seq` 231) es el primero con `B = 2026-11-06`. Si la corrida hubiera seguido
sin interrupción, el cambio de contenido habría ocurrido igualmente en el primer tick después de las
00:00Z. La interrupción no dejó estado a medias: retrasó la observación del cruce de barra.

#### 4.4.5 Las reservas de hoy confirman la secuencia, no la contradicen

| `reservation_id` | `status` / `release_reason` | `created_at` | `released_at` | `tick_id` |
| --- | --- | --- | --- | --- |
| `RES-dec-668b1a77105c` | `RELEASED_BY_CANCEL` / `cancel` | 6/11 **08:05:50** | 6/11 **08:05:50** | `2026-11-06T08:05:50Z` |
| `RES-dec-fa41785acf4b` | `RELEASED_BY_CANCEL` / `cancel` | 6/11 **08:05:50** | 6/11 **08:05:50** | `2026-11-06T08:05:50Z` |

Los dos identificadores son **los mismos** que la auditoría vio a las 07:32:04Z y 07:39:14Z. La
consulta agrupada devuelve `n = 1` por identificador: el `upsert` de `PostgresReservationStore`
reescribe `created_at`, `released_at` y `tick_id` sobre la misma fila, de modo que el histórico de
reintentos no es visible en la base. Secuencia reconstruida, coherente con lo anterior:

1. `_v2_plan_tick` aprueba dos entradas y **reserva** (`RES-dec-*`) antes del bucle;
2. el bucle no encuentra precio de ejecución para ningún símbolo y no emite orden;
3. el cierre de turno (`_v2_reconcile_reservations(startup=False, only_ids=owned)`) retira la
   reserva huérfana **dentro del mismo tick** (`RELEASED_BY_CANCEL`, `cancel`);
4. el tick durable se escribe con `proposals=0`, `vetoes=0`, `reason=idle`.

Es decir: **la reserva prueba que hubo plan; la ausencia de `proposals` prueba que no hubo emisión.**
El contador `proposals` cuenta la propuesta que supera el gate (`auto_simulation_worker.py:8122`),
no la aprobación del planificador. Ambas cosas conviven sin contradicción.

#### 4.4.6 Consecuencia para el cierre de la corrida

- H-1 queda **documentado con causa raíz demostrada** por evidencia durable (no por inferencia):
  ausencia de barra de ejecución del día + contrato fail-closed del precio, con el bucle recorrido y
  el planificador activo.
- No hay corrupción de estado, ni efecto del lease, ni kill switch: `state=RUNNING` en las 92 filas.
- La corrida **no puede** cerrar ciclos ni generar material nuevo mientras no exista barra `B`: no es
  un defecto del instrumento ni del gate, y **no se corrige durante la medición**.
- Sí es una deuda de producto: un tick que recorre 80 símbolos, aprueba 2 entradas y se publica como
  `reason=idle` **sin declarar el motivo real** (precio ausente) incumple la honestidad que el resto
  del motor sí respeta. El arreglo (declarar `price_missing` como motivo y/o bloquear el arranque
  cuando `B` no está ingerida) se decide **después** del cierre, con su propio sello.
- Para la próxima medición: **no lanzar `run-day` si la barra del día corriente no está persistida**.
  Con `B` ausente, la corrida nace congelada y solo produce `idle`.

## 5. Correcciones a las auditorías recibidas

| Afirmación auditada | Veredicto | Evidencia |
| --- | --- | --- |
| “Faltan las migraciones 058-065 en el repo” | **Falso** | están en el worktree `d8a5d0f9`; el zip auditado era anterior |
| “El `BLOCKED` es casi con certeza `RISK_KILL_SWITCH=true`” | **Falso para esta corrida** | `v2_76` no importa el kill switch; los 296 ticks escriben `RUNNING` |
| “BD en 065 sin migrar, como corresponde” | **Cierto** | `alembic_version` = `065_auto_engine_intent`, coherente con el árbol |
| “PID 27264 es el proceso del motor” | **Impreciso** | 27264 es el PowerShell lanzador; el declarado es `node` 19492; el dueño del lease es `python` 43188 |
| “El `manifest.json` del día describe la corrida” | **Falso** | es del intento fallido de 18:30 (`HARD_ERROR`, `PREFLIGHT_ERROR`, commit `ccdb69a1`, pin `.183`); la corrida viva arrancó a las 18:39 con `--force` sobre `d8a5d0f9` |
| “120 ticks” | **Es el contador del bucle del runner** | a las 07:35:09Z iba por **160**; el `seq` durable (296) es otro contador y es compartido entre días (`AUTO_ENGINE_SIM_ENGINE_ID` estable) |
| “`pricesServed=80/80` no implica precio vivo” | **Cierto y relevante** | los 13 fills son `MARKET_CLOSE`; el bridge hoy sí sirve vivo |
| “El runner no libera el lease al terminar” | **Cierto** | `finally` solo hacía `engine.dispose()`; cerrado en §6 |
| “`ensure_migrated()` subiría la BD a 066 desde `.184`” | **Cierto** | se mantiene la prohibición de arrancar desde `.184` mientras viva el 43188 |
| “`forward.json` puede no existir todavía” | **Cierto** | no existe: el runner lo escribe al terminar y copia a `window-runs/20261105/forward.json` |
| “El expediente del 5/11 decía `BLOCKED` = no closed cycles” | **Cierto y confirmado hoy** | mismo bloqueador, medido contra la base |

## 6. Deuda CERRADA: liberación del lease al apagar

**Rama:** `fix/forward-lease-close-2026-11-06` (desde `05926dc`). **No** se aplicó al worktree
pinneado: su freeze sigue intacto y no se toca mientras la corrida esté viva.

Cambio en `apps/api-python/scripts/v2_76_forward_market_material.py`:

- `_run` declara `runtime: Any = None` antes del `try` (el preflight y los fallos de watch salen por
  el mismo `finally` sin runtime compuesto).
- el `finally` pasa de `await engine.dispose()` a `await _shutdown(runtime, engine)`.
- nuevo `_shutdown`: `await runtime.close()` **antes** de `engine.dispose()`, porque `close()` abre
  una sesión con el `session_factory` y el pool tiene que seguir vivo.

Por qué es seguro: `AutoSimRuntime.close()` solo suelta si dueño **y** generación siguen siendo los
de este runtime, así que el `close()` de un proceso que ya perdió el lease es un no-op y la
generación no retrocede (la valla de P7 no se debilita).

**Tests** (`apps/api-python/tests/test_v2_76_forward_release_lease.py`, 5 casos, sin PostgreSQL):

1. el apagado suelta el lease **antes** de liberar el pool;
2. sin runtime (preflight) solo libera el pool;
3. `close()` sin lease es no-op y **no** abre sesión;
4. `close()` suelta el lease de este proceso y limpia el estado;
5. un store roto no rompe el apagado: el lease se limpia igual;
6. si `close()` se interrumpe (`CancelledError`), el pool se libera igual.

Verificación ejecutada: `pytest` del fichero nuevo → **6 passed**; `pytest` del test hermano del
script → **6 passed**; `ruff check packages/py apps/api-python --config pyproject.toml` (la
invocación de CI) → **All checks passed**.

**Ojo con el freeze:** el script vive en `apps/`, que **sí** participa del pin. Este cambio exige un
`node scripts/window-pin.mjs --write` en el sello que lo incluya, y **no** debe ejecutarse desde el
worktree mientras corra el PID 43188. `auto_simulation_worker.py` **no** se modificó.

## 7. Reanclaje y migración 066: decisión

- **No se migra** mientras viva la corrida: `066_account_evidence_policy` se aplicaría sobre una base
  que el proceso está usando, y el árbol `d8a5d0f9` no conoce esa revisión.
- **No se lanza otro `run-day`**: el lock del `20261105` sigue tomado por el 19492 y `--force` no lo
  salta.
- **Cierre correcto (después de que el runner termine):** fusionar → sellar con 066 → `window:pin
  --write` → medir. Cualquier medición previa al reanclaje caduca en `STALE`.
- **Cobertura declarada:** esta corrida nace en `d8a5d0f9` y **no certifica** el cambio R1 de `.184`
  (geometría de stop anclada al precio de ejecución, ATR medido obligatorio). Tampoco certifica la
  066.

## 8. Cómo cerrar esta corrida (checklist)

1. Esperar el final natural: `--max-ticks 400` o `EVIDENCE_READY`. A las 07:35Z el runner iba por
   **160** ticks; con ~62 s/tick y sin nuevos parones quedan ~4 h. Los parones de standby alargan el
   reloj de pared, no el contador.
2. Al terminar, el runner escribe `operability_runs/forward-market-20261105.json` y lo copia a
   `window-runs/20261105/forward.json`; reescribe `manifest.json` con `steps.forward`,
   `windowProvenance` y `gate`, y anexa la fila al `ledger.jsonl`.
3. Verificar en ese JSON: `ticks` (≈400), `turnTotals`, `lastGateReason`, `priceSources`,
   `sample.blockers`, `sample.closedCycles`, `sample.measurableCycles`, `readiness.verdict`.
   **Esperado:** `closedCycles = 0` y `BLOCKED` con `no closed cycles`, salvo que alguna de las 3
   posiciones cierre antes.
4. La fila actual del ledger (`HARD_ERROR · PREFLIGHT_ERROR`, 18:35Z) es **histórica** del intento
   fallido: no es el resultado de esta corrida.
5. Abrir el diagnóstico de H-1 (§4) con la corrida ya cerrada.

## 9. Cierre natural de la corrida (2026-11-06 11:40Z)

La corrida llegó a los 400 ticks por su propio contador (`--max-ticks 400`), sin señal, sin
`--force` y sin reinicio. El runner completó además los pasos 3-5 del día.

### 9.1 Hechos del cierre

| Hecho | Valor medido |
| --- | --- |
| Fin del bucle | `11:40:35Z`, `stopReason = "completed"`, `ticks = 400` |
| Duración de pared | `61 300 790 ms` = **17 h 1 m 40 s** (incluye los parones de standby) |
| Proceso | PID 19492 y PID 43188 ya no existen; `lock.json` liberado |
| `forward.json` canónico ↔ copia | idénticos, `sha256 = 1baa95c3…47d91` |
| `window.json` ↔ `windowProvenance.windowJsonSha256` | `a648d67b…5a80` = `a648d67b…5a80` |
| `manifest.json` | `status = "MEDIDO"`, `finishedAt 11:40:48Z` |
| Pasos del día | `preflight 0 ok` · `forward 2 declared` · `journal 0` · `window 0` · `audit 0` |
| `alembic_version` | **`065_auto_engine_intent`** (sin cambios durante toda la corrida) |
| Freeze | `ok = true`, `apps 7a807716…`, `packages cf261bc0…` = `HEAD:apps`/`HEAD:packages` de `d8a5d0f9` |
| `commit` / pin del árbol | `3e092888` en los tres sitios (manifest, ledger, pin) |
| Gate de ventana | `INCONCLUSIVE` · días `2/4` · episodios `0/2` · ciclos `0/32` |
| Readiness | `BLOCKED` · `no closed cycles` + `insufficient measurable cycles per strategy` |

`steps.forward.exit = 2` **no es un fallo**: es el código declarado de “nivel `evidence` no
alcanzado” (`v2_76_forward_market_material.py:1014`), clasificado por el runner como
`kind = declared`, `hard = false`. Por eso el día queda `MEDIDO` y no `HARD_ERROR`.

### 9.2 Fila definitiva del ledger

`operability_runs/window-runs/ledger.jsonl` tiene **dos** filas con `day = 20261105`:

| `startedAt` | `status` | `steps.forward` | Lectura |
| --- | --- | --- | --- |
| `2026-11-05T18:35:16.305Z` | `HARD_ERROR` / `PREFLIGHT_ERROR` | ausente | **histórica**: intento fallido de `.183` |
| `2026-11-05T18:39:07.227Z` | **`MEDIDO`** | `exit 2 · declared` | **definitiva**: la corrida de 400 ticks |

Seleccionar por día sin mirar `startedAt` mezcla las dos. La definitiva es la segunda.

### 9.3 Material durable (sin cambios desde el 5/11 18:41Z)

| Métrica | Valor | Nota |
| --- | --- | --- |
| Fills | **13** | 13/13 `MARKET_CLOSE`, 3 `cycle_id`, 0 sin ciclo |
| Propuestas / órdenes / aperturas / cierres | `4 / 4 / 3 / 0` | `turnTotals` |
| Reservas | **6** | 3 `RELEASED_BY_FILL`, 1 `tail_dead`, 2 `cancel` |
| Posiciones abiertas | **3** | sin cambios desde `18:41:21Z` |
| Órdenes de salida | 1 | `FILLED` |
| Ciclos cerrados / medibles | **0 / 0** | `min_cycles_per_strategy = 32` |
| `decided` | **32 000** | `400 × 80` símbolos |

Reconciliación exacta con el ledger durable `auto_engine_ticks` (misma base, read-only):

| Concepto | Valor | Comprobación |
| --- | --- | --- |
| Ticks de la corrida | `seq` **133-532** | 400 filas |
| Ticks con motivos (`hold_no_op` / `trail`) | **98** | `vetoes = 7836` = 77 + 79 + 96×80 |
| Ticks `idle` | **302** | `seq` 231-532, `vetoes = 0`, `activity = ANALYZING` |
| Ticks `NO_ACTIVITY` | **0** | el bucle se recorrió en los 400 |
| `sum(proposals)` | **4** | coincide con `turnTotals.proposals` |

El 75,5 % de la corrida (302/400) se ejecutó **sin precio de ejecución**, tal como fija §4.4. El
material no cambió porque no podía cambiar: no hubo ni una marca, ni un `trail`, ni un cierre.

### 9.4 Dos defectos de telemetría que el cierre destapa

No invalidan el veredicto, pero deben declararse porque afectan a la trazabilidad:

- **`lastGateReason` no describe el último tick.** `forward.json` declara
  `["hold_no_op", "trail"]`, que es el último tick **con motivos**; el tick final (11:40:34Z) tiene
  `reason = idle` y `vetoes = 0`. El runner solo sobrescribe `last_gate_reason` cuando la lista de
  motivos no está vacía, así que un cierre por precio ausente se reporta con el motivo del mediodía
  anterior. Mismo patrón que H-1: el silencio se hereda.
- **`manifest.watchSize = 20` frente a `forward.watchSize = 80`.** El manifiesto y el ledger
  registran el `watchSize` de la **configuración**, no el del watch efectivo: la corrida arrancó con
  `--watch-from-estudio` (`watchSource = "estudio"`), que sustituyó el watch de 20 por 80 símbolos.
  La prueba es aritmética: `decided = 32 000 = 400 × 80`. El gate no consume `watchSize`, por lo que
  el veredicto no cambia; la provenance sí queda imprecisa.
- **`pricesServed = 80/80` no significa precio de ejecución.** Lo que el runner cuenta es el
  `MarketPriceSnapshot` del puente live. La fuente que decide (`OhlcvPriceSource`) devolvía `None`
  para los 80. Reportar “80/80 precios” con 302 ticks sin poder decidir es exactamente la confusión
  que §4.4 deshace.

### 9.5 Qué certifica y qué no

- **Certifica:** que la cadena PAPER ejecutó 400 ticks con freeze verificado sobre `d8a5d0f9`, sin
  kill switch, sin corrupción de estado y con material trazable hasta el fill.
- **No certifica:** el R1 de `.184` (no está en `d8a5d0f9`), ni la 066, ni el fix de lease (§6).
  Cualquier afirmación sobre esos cambios exige una corrida nueva **desde el árbol sellado**.
- **Veredicto:** `PAPER INCONCLUSIVE` con bloqueador declarado (`no closed cycles`). No se bajan
  umbrales ni se reinterpreta el gate.

## 10. Sello 2.11.185-beta, reanclaje y estado de la nueva medición

Ejecutado **después** de §9, en este orden: fix de lease → sello → migración → pin.

### 10.1 Cadena de commits

| Commit | Contenido |
| --- | --- |
| `ab815cac` | `fix(forward)`: `_shutdown` suelta el lease antes de disponer el pool (+ 6 tests) |
| `36e57032` | `docs(evidence)`: §4.4 y §9 de este expediente |
| `22a6b4bd` | merge **#100** del fix de lease |
| `3e10e243` | `chore(release)`: bump `2.11.185-beta` (paquete + 14 literales) + changelog |
| `31c2d3cd` | merge **#101** (sello) — commit etiquetado en el pin |
| `d66a0026` | `chore(window)`: reanclaje del pin |
| `5e82274d` | merge **#102** (pin) — `HEAD` |

### 10.2 Verificación de alineación (código ↔ pin ↔ migración)

| Comprobación | Resultado |
| --- | --- |
| `package.json version` | **`2.11.185-beta`** |
| `HEAD:apps` | `e9486e12f46f22dc10b535e22fb9c0d6715fd804` |
| `pin.appsHash` | `e9486e12f46f22dc10b535e22fb9c0d6715fd804` ✅ |
| `HEAD:packages` | `2de53cda49ed847dbd5d4b9572c826c6368ddc52` |
| `pin.packagesHash` | `2de53cda49ed847dbd5d4b9572c826c6368ddc52` ✅ |
| `31c2d3cd` (sello) es ancestro de `HEAD` | **sí** |
| `alembic_version` | **`066_account_evidence_policy`** (`ensure_migrated` desde el árbol sellado: `065 → 066`, `ok = true`) |
| `auto_simulation_worker.py` en `05926dc8..HEAD` | **sin cambios** (`Δ motor = 0`) |
| `node scripts/window-pin.mjs --check` | **freeze OK** (la nota de etiqueta `31c2d3cd ≠ 5e82274d` es esperada: el freeze son los dos tree hashes) |
| Pruebas | `test_dia_d_bump_guard` **2 passed** · `test_v2_76_forward_release_lease` **6 passed** · `window-forward.test.mjs` **50 pass / 0 fail** · `ruff` **All checks passed** |

**Caducidad declarada:** toda evidencia anterior a `5e82274d` queda **`STALE`**. La corrida `20261105`
nació en `d8a5d0f9` con pin `3e092888`: **no** certifica este árbol, ni el fix de lease, ni la 066.

### 10.3 Estado de la nueva medición: dos precondiciones medidas, ninguna cumplida

Antes de lanzar `run-day` se comprobaron las dos condiciones que el cierre de §4.4 dejó como
obligatorias. Ninguna se cumple todavía **a las 12:19Z**:

1. **La API de `:8000` no está lista.** Responde `503` con
   `schema_status = esquema 066 ≠ head esperado 065` y
   `provenance.package = 2.11.183-beta`, `git_sha = d8a5d0f9…`: es el proceso **anterior** al sello
   (PID 45672, `apps/api-python/run_dev.py`). `run-day` aborta en duro si la API no está lista, así que
   hay que **reiniciarla desde el árbol sellado**. No es una regresión: es la consecuencia esperada de
   migrar la base por delante del proceso que la servía.
2. **No existe barra del día corriente.** `ohlcv_bars` tiene **0** barras de `2026-11-06`; la última es
   del `2026-11-05` (ingerida a las `13:59:59Z` del 5/11). Lanzar ahora reproduciría H-1 **desde el
   primer tick** y el día entero sería `idle` con material cero. La barra del día llega, según el
   histórico medido, entre las `08:15Z` y las `14:00Z`.

La ventana útil de hoy es estrecha: **400 ticks × 61,3 s ≈ 6 h 50 min**, así que un arranque después de
las `17:05Z` terminaría pasada la medianoche UTC y volvería a congelarse (§4.4.4). Arrancar en cuanto
exista la barra —previsiblemente antes de las `14:30Z`— permite que las 400 vueltas terminen **antes
de medianoche**, sin repetir el tramo ciego.

## 11. Nueva medición (2026-11-06 22:14Z): intento abortado, relanzamiento sellado y desviaciones declaradas

### 11.1 El intento que arrancó antes de existir la barra

Hechos medidos, en orden:

- `ohlcv_bars` no tenía **ninguna** fila de `2026-11-06` a las `19:40Z`. La última diaria seguía siendo
  la del `2026-11-05`.
- A las `19:40:53Z` arrancó un `run-day` cuyo motor se ejecutó desde el worktree
  `.cursor/worktrees/window-seal-183` (árbol **pre-sello**, `d8a5d0f9`, pin `3e092888`), no desde la raíz
  sellada. Preflight `exit 0` (`HIGH_VOLATILITY`, 57/80 operables) y forward con `--max-ticks 400`.
- A las `19:40:58Z` la cola del API recibió **79** instrumentos (`POST /api/sync/queue/enqueue-stale`):
  el propio runner los encoló. El worker del API los fue drenando despacio (58 barras a las `22:10Z`,
  63 a las `22:26Z`, 73 a las `22:34Z`), de modo que el motor arrancó con **cobertura parcial de la
  barra `B`** y fail-closed por símbolo en el resto.
- Ese motor recorrió la barra `B` ya con barras parciales: ticks hasta `seq 567` (`22:11:40Z`,
  `hold_no_op, trail`, 1 `RELEASED_BY_FILL` a las `20:05:11Z`). **No es una corrida certificable**: el
  código ejecutado no es el del sello `2.11.185-beta` ni el de `066`, y su freeze no es `e9486e12`.
- A las `22:11:44Z` se detuvo el proceso (`/F`). El runner lo clasificó `forward.exit=1` →
  `manifest.status=HARD_ERROR` / `reason=FORWARD_ERROR` y escribió la fila `20261106` del ledger con ese
  veredicto (`startedAt 19:40:53Z`, `finishedAt 22:11:44Z`).

Evidencia conservada en `operability_runs/window-runs/20261106/attempt-1940z-oldtree/` (sha256):

| fichero | sha256 |
| --- | --- |
| `forward.err.txt` | `e209d50f1e94a7409c1d19b71f2cb654569dad2e58353eb20ea4ce1c48f56277` |
| `manifest.json` | `55b8ef8d85d5d61a193168c1ace878abdd18bc4defec29474ceb671d67a1cb41` |
| `preflight.json` | `eb6b0e06c8c5a730974da72eb53f5a55c29bb8d057a73a5a001474546dfea0e0` |

### 11.2 Relanzamiento desde el árbol sellado

- `node scripts/window-forward-runner.mjs run-day --force` desde la raíz sellada (`275c357d`, pin
  `appsHash e9486e12` / `packagesHash 2de53cda`, API `2.11.185-beta` sobre `066_account_evidence_policy`).
  El `--force` es legítimo: el día estaba marcado `HARD_ERROR`, no medido, y el intento anterior queda
  archivado como tal.
- `22:12:35Z` lock del día; `22:12:41Z` preflight `exit 0` (`HIGH_VOLATILITY`, **60/80** operables);
  `22:13:46Z` un tick omitido por el lease del dueño anterior (`auto-sim-18040…`, TTL hasta
  `22:14:40Z`); **`22:14:46Z` primer tick del árbol sellado** (`seq 568`), cadencia 60 s.

### 11.3 Desviaciones declaradas (no se corrigen, se miden)

1. **Frontera de medianoche UTC.** El arranque útil es a las `22:14Z`, no antes: 400 ticks × 60 s
   terminan hacia las `05:00Z`. El tramo posterior a `00:00Z` volverá a quedarse sin barra `B`
   (sábado sin sesión) y repetirá H-1 (§4.4). Se declarará como tramo ciego, no como ticks medidos.
2. **Cobertura de barra `B` parcial en el arranque.** Sólo 63 instrumentos tenían barra `2026-11-06`
   cuando empezó (73 a los 20 min, 92 a la medianoche, **96 a las `08:13Z`**). La cobertura **se
   estabilizó en 96/180**: el resto de instrumentos no son miembros de lista y el alcance de la cola es
   `scope=lists`, así que nunca se encolaron. Los símbolos sin barra `B` quedan fail-closed por diseño;
   el bloqueador se reporta con su cuenta exacta en el paquete final.
3. **La ingesta de la barra del día llegó tarde.** La tarea `BolsaV1_BarsSync` (17:40 local) terminó con
   resultado `0` pero la cola sólo se llenó a las `19:40:58Z`, disparada por el runner. Con la cola
   drenando a ~1 instrumento/minuto la cobertura completa (~180) no se alcanza hasta pasada la
   medianoche UTC.
4. **El runner programado no apunta al árbol sellado.** La línea de comandos del proceso de `19:40:53Z`
   ejecutaba `.cursor/worktrees/window-seal-183/scripts/window-forward-runner.mjs`: la tarea
   `BolsaV1_WindowForward` sigue registrada contra el worktree pre-sello. Re-registrarla
   (`task:install`) es deuda operativa abierta; no se tocó durante la medición.
5. **Fin de semana sin sesión.** `2026-11-07` y `2026-11-08` no tienen barra diaria; la siguiente
   ventana medible es el lunes `2026-11-09` a las 18:30 locales.

### 11.4 Contraste H-1 medido sobre el árbol sellado

La corrida sellada reproduce la firma de H-1 sin ambigüedad, y ahora con el código del sello:

| tramo | ticks | `ANALYZING` | con `proposals>0` | con `vetoes>0` | Σ `proposals` | Σ `vetoes` | `reason` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `2026-11-06 22:14Z`–`23:40Z` (barra `B` parcial, 63→92 instrumentos) | 29 | 29 | 0 | **29** | 0 | **2273** | `hold_no_op, trail` |
| `2026-11-07 07:40Z`–`08:11Z` (sábado, sin barra `B`) | 4 | 4 | 0 | **0** | 0 | **0** | `idle` |

Lectura: con barra `B` el mismo motor veta ~78 símbolos por tick (`2273/29`) y deja `reasons` poblado;
sin barra `B` recorre el bucle (`ANALYZING`), no decide ningún símbolo (`vetoes=0`) y `_reason_text`
rellena con `idle`. Es la confirmación de S3 (§4.4): **la frontera de barra, no el lease ni un estado
corrupto**. La máquina quedó en suspensión entre `23:40Z` y `07:40Z` (8 h), el mismo patrón de hueco que
la corrida anterior; ese tramo no se cuenta como medido.

Material acumulado del día: 4 fills, 3 reservas (2 `RELEASED_BY_CANCEL`, 1 `RELEASED_BY_FILL`),
`paper_forward_results = 0` → **0 ciclos cerrados**. El gate no puede pasar de `INCONCLUSIVE` con
`no closed cycles`: no se baja ningún umbral.

### 11.5 Corte de la corrida a las 24 h (2026-11-07 22:12:36Z)

Hechos medidos:

- La corrida sellada arrancó a las `2026-11-06T22:12:35.931Z` y su árbol de procesos (node + python)
  **desapareció a las `2026-11-07T22:12:36.986Z`**: 86 401 466 ms = **24 h + 1,5 s**, exacto.
- Quedó en **292/400** ticks (`seq 859`, último tick `22:12:31Z`), cortada a mitad de vuelta: el último
  tramo de `forward.err.txt` son peticiones `httpx` normales y **no hay traza de error, `KeyboardInterrupt`
  ni mensaje del runner**. `forward.json` **no existe**, `manifest.json` sigue siendo el del intento
  abortado de `19:40Z` y la fila `20261106` del ledger **no se reescribió** (`HARD_ERROR`).
- El corte es **externo al motor**: no hay límite de 24 h ni en `window-forward-runner.mjs` ni en
  `v2_76_forward_market_material.py`; el engine no declaró `stopReason`. Se declara como corte de
  sesión del proceso lanzador, no como fallo medido del motor.
- El `.run.lock` del día quedó huérfano (`pid 22708`, ya inexistente). El runner lo reclama solo en la
  siguiente ejecución (`lockDecision` con `pidAlive=false`); no requiere intervención.
- `ohlcv_bars` de `2026-11-06` **completó 180/180** instrumentos durante la madrugada del 7; la cobertura
  parcial del arranque (96) era de la cola `scope=lists`, no del proveedor.
- La tarea programada registró `20261107` como `NON_MARKET_DAY` (`18:23:52Z`) y no interfirió.

Consecuencia: **no hay artefacto definitivo de la corrida de `2026-11-06`** (sin `forward.json` ni
ledger reescrito), pero el hecho que decide el dictamen sí está medido: **0 ciclos cerrados en 292
ticks**, con la frontera de barra confirmada. La corrida no puede certificar el R1 de `.184`; el
siguiente intento debe ser una ventana completa de 400 ticks en día de sesión (lunes `2026-11-09`), y
antes hay que corregir la tarea programada para que apunte al árbol sellado.

## 12. Invariantes de esta auditoría

- `Δ motor = 0` en el worktree auditado; el cambio de §6 vive en una rama aparte y no se aplicó al
  árbol que corre.
- Sin DDL, sin `ensure_migrated`, sin `run-day`, sin señales al 43188/19492/27264.
- Ningún umbral del gate se bajó: `min_cycles_per_strategy = 32` sigue declarado.
- Un hueco se declara, no se rellena: los 7 h 24 min de standby no se cuentan como ticks medidos.
- **AUTO OFF** · **PAPER INCONCLUSIVE**.
