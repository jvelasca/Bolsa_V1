# Audit-pack `AUTO-15` Data Gate PERSISTIDO — `1.81.0-beta` (2026-09-23)

**Fase:** `V2.56` · **Rótulo:** `AUTO-15` · **Bump:** `1.80.0-beta` → **`1.81.0-beta`** · **Tag:**
`v2.56-beta` (cifras de CI en §11, añadidas en el commit de docs **posterior** al sello) · **Fase
anterior:** `V2.55` / `AUTO-14` (tag `v2.55-beta` →
`e29e6227`, `Release tag CI` `35889751810` **GREEN**: `10 success` + `1 skipped`, job `python` del tag
**`2575 passed / 38 skipped`**, PR de auditoría [#64](https://github.com/jvelasca/Bolsa_V1/pull/64)).

**SÍ hay migración:** Alembic head `044_auto_cycle_trace` → **`045_adaptive_gate_state`** (aditiva, sin
backfill, `upgrade`/`downgrade` **simétricos e idempotentes**). Sin SHORT, sin UI nueva, sin cambio de
contrato de API ni de DTO y **sin clave nueva en el journal durable** (la proyección por lista blanca
`_ALLOCATION_KEYS = ("riskMultipliers", "evidenceAxis")`, `auto_adaptive_journal.py:58`, queda **byte a
byte igual**). El gobernador y su evidencia quedan **intactos**. Adaptive **sigue siendo recomendador
read-only** y con el flag **OFF** el camino de producción es **byte-idéntico** a `v2.55`: sin racha que
leer ni que escribir, esta fase **no ejecuta ni un I/O nuevo**.

---

## 0. Resumen: qué instala esta pasada

`AUTO-13` graduó la salud de lo que Adaptive sabe de sí mismo con dos hechos: un **contador de fallos
consecutivos del sink** del journal y un **ancla de antigüedad**. El ancla ya era durable (sale del
`asOf` de la última fila publicada); el contador vivía **solo en la memoria del proceso**, así que

```
WORKER 1 → 2 fallos del sink (DEGRADED) → CRASH → WORKER 2 → 0 fallos → OK
```

El sistema olvidaba la racha con la que estaba juzgando su propia evidencia. Y **no es
reconstruible**: un fallo de escritura no dejó fila en `decision_journal_entries`, y el ancla mide
*publicación*, no *error*. Deducirla sería inventar la prueba que el invariante exige.

Esta pasada la **persiste**:

1. **Tabla nueva** `adaptive_gate_state` — una fila por `(account_id, engine_id)`, con
   `sink_failures` (consecutivos), `last_failure_at`, `last_success_at`, `updated_at`.
2. **Store propio** (`adaptive_gate_store.py`): contrato puro + gemelo in-memory + PG, con
   **incremento atómico** (`INSERT … ON CONFLICT DO UPDATE SET sink_failures = sink_failures + 1`) y
   **reset sin amplificación** (`UPDATE … WHERE sink_failures > 0`).
3. **El worker** la **siembra al arrancar** (una vez por proceso, antes del primer plan), la
   **incrementa** cuando el sink falla y la **resetea** cuando publica.
4. **El gate** se sella (`auto15-v1`) y **declara la procedencia** de la racha
   (`sinkFailuresDurable`), **sin** tocar umbrales, la tabla estado→efecto ni la precedencia.

Superficie nueva: `packages/py/infrastructure/alembic/versions/045_adaptive_gate_state.py`,
`AdaptiveGateStateRow` (`tables.py:2736`), `packages/py/application/src/bolsa_application/adaptive_gate_store.py`,
las costuras `apps/api-python/tests/test_auto_v56_auto15_data_gate_durable_seam.py` (**9** tests) y
`apps/api-python/tests/test_auto_v56_auto15_data_gate_pg.py` (**6** tests).
Superficie tocada: `auto_simulation_worker.py` (contador, siembra, escritura, cableado, declaración del
tick), `auto_adaptive_data_gate.py` (sello + campo de procedencia), `tables.py` (fila ORM), los dos
workflows de CI y la sonda de mutaciones.

---

## 1. El invariante: **«no acusar sin prueba» sobrevive a un reinicio**

> La racha con la que el gate juzga la salud de su propia evidencia **no puede depender de que el
> proceso siga vivo**. Si se pierde, el gate se cree sano con un journal que lleva días fallando; y si
> se **inventa**, acusa con una prueba que nadie midió. Ni una cosa ni la otra: se **lee** de estado
> durable, se **declara** su procedencia y, cuando no hay constancia, el hueco se **dice**.

Es la misma familia de P0 que `AUTO-3` cerró para la parada dura («la parada DURA pertenecía a la
MEMORIA del proceso, así que un crash las olvidaba», `versions/043_exit_identity_and_kill_state.py:4-11`)
y la ventana que `AUTO-13` **declaró** como límite suyo (audit-pack `v2.54`, §3, y la primera pregunta
abierta de su arranque de auditor).

**Cinco corolarios, todos con test y con mutación que los mata:**

- **Sin fila no hay racha: la ausencia es información.** `load` devuelve `None`, la siembra arranca en
  `0` y lo **declara**; **nunca** se crea una fila "por si acaso" (el camino sano no escribe jamás).
- **La procedencia se declara, no gradua.** La misma racha da el **mismo** estado con y sin store: el
  gate **no** cambia de opinión porque el número venga de la BD (test
  `test_the_provenance_of_the_streak_is_declared_and_never_grades`).
- **Sin amplificación.** Un despliegue sano **no paga una escritura por tick**: el reset solo escribe
  si había racha viva (`WHERE sink_failures > 0`) y nunca crea la fila.
- **Un fallo de lectura no se convierte en fallo ni en salud.** Store ausente, fila ilegible o lectura
  rota ⇒ racha `0` + **motivo en el log** + `sinkFailuresDurable = false` (el hueco declarado, que es
  el límite que sigue existiendo).
- **La sesión del tick queda limpia.** El store escribe en la **misma** sesión del turno: un fallo de
  escritura hace `rollback` y **sube** el error; sin él, el siguiente store del turno moriría con
  `PendingRollbackError` y esa traza rota tumbaría el compromiso de capital (mismo contrato que el sink
  de `AUTO-10`, `auto_simulation_worker.py:5029-5060`).

---

## 2. El estado durable: tabla, fila y store

`045_adaptive_gate_state` (`revision = "045_adaptive_gate_state"`, `:40`; `down_revision = "044_auto_cycle_trace"`,
`:41`) crea la tabla y su índice con el patrón de `028`–`044`: helpers `_table_exists` (`:49`) /
`_index_exists` (`:57`), creación idempotente (`_create_gate_state`, `:62`) y `downgrade` **simétrico**
(índice y después tabla, `:106-109`).

| Punto | `ruta:línea` |
| --- | --- |
| Tabla `adaptive_gate_state` + PK `(account_id, engine_id)` | `045_adaptive_gate_state.py:66-82` |
| Índice `adaptive_gate_state_account_failures_idx` | `045_adaptive_gate_state.py:92` |
| Fila ORM (espejo de `AutoKillStateRow`, `tables.py:2693`) | `tables.py:2736` |
| Contrato puro + gemelo in-memory | `adaptive_gate_store.py:46` / `:153` |
| Store PG | `adaptive_gate_store.py:207` |
| Incremento ATÓMICO (`ON CONFLICT DO UPDATE`) | `adaptive_gate_store.py:234-268` |
| Reset condicional (`WHERE sink_failures > 0`) | `adaptive_gate_store.py:270-292` |
| `rollback` + `raise` en fallo de escritura | `adaptive_gate_store.py:255-265` / `:284-290` |

**Decisiones finas, medidas.**

- **Incremento atómico, no `load`+`save`.** La racha es justo el dato que no puede perder un fallo por
  una carrera entre dos lectores: el `+1` lo hace la base.
- **`autocommit` explícito** (patrón de `kill_switch_store.py`): el `commit` lo controla la llamada, y
  el test PG comprueba que se ve desde **otra** sesión.
- **Imports de la fila perezosos por método** (el patrón de la casa): `bolsa_application` no arrastra
  `sqlalchemy` al importarse.
- **Clamp defensivo** (`sink_failures_from_state`, `:72`): una fila con un número imposible no fabrica
  una racha negativa — se lee `0`.
- **PK `(account_id, engine_id)`**: decisión ratificada por el propietario. Con `(account_id)` a secas,
  dos motores de la misma cuenta compartirían racha y uno **curaría** el fallo del otro.

**Preguntas incómodas.**

- ¿Puede `record_success` escribir sin racha viva por alguna puerta (p. ej. `autocommit=False`)?
  Búscalo en la mutación `M111`.
- ¿Puede `load` devolver la fila de **otra** clave si el motor viene vacío? (`M112`.)
- ¿Y si el `rollback` de un fallo de escritura se lleva por delante trabajo **ya** escrito en la misma
  sesión? El store escribe la racha al final del camino del sink (después del commit de la reserva de
  entrada), y el `except` **sube** el error: no hay silencio.

---

## 3. El worker: sembrar al arrancar, escribir sin amplificar

| Punto | `ruta:línea` |
| --- | --- |
| Contador de proceso + bandera de procedencia | `auto_simulation_worker.py:753` / `:757` |
| Store en el constructor | `auto_simulation_worker.py:826` |
| Siembra de la racha **antes** del primer plan | `auto_simulation_worker.py:3588` (dentro de `_v2_recover_adaptive_state`, `:3565`) |
| Gateado por `adaptive_enabled` | `auto_simulation_worker.py:3581-3583` |
| Lectura durable (+ fail-open declarado) | `auto_simulation_worker.py:3484` (`_v2_recover_adaptive_gate_streak`) |
| Incremento al fallar | `auto_simulation_worker.py:3469` → `:3524` |
| Reset al publicar (sin amplificar) | `auto_simulation_worker.py:3481` → `:3549` |
| Entra al gate como el MISMO hecho | `auto_simulation_worker.py:3334` (`sink_failures=`) + `:3337` (procedencia) |
| Cableado de producción (misma sesión del tick) | `auto_simulation_worker.py:5599-5605` → `:5625` |

**Decisiones finas, medidas.**

- **La siembra va ANTES de los atajos del lector del journal.** Es un hecho de **otro** eje (el sink
  que escribe), y el caso en que más importa —el journal fallando— es justo el que deja
  `read_ok = False`: si se sembrara después del atajo, un reinicio durante un journal roto arrancaría
  en `0` y se habría perdido la racha **precisamente** cuando hacía falta (comentario en `:3583-3587`).
- **Una vez por proceso** y **gateado**: con el flag OFF no hay I/O nuevo
  (`if not self._v2_tunables.adaptive_enabled: return`, `:3581`).
- **Una sola escritura por transición**, sobre la sesión del tick, con el mismo contrato de sesión que
  el sink del ciclo.
- **La racha durable MANDA**: si el store contesta, su número sustituye al de proceso (`:3469`);
  si el store falta o falla, queda la de proceso **declarada** (`sinkFailuresDurable = false`).

**Preguntas incómodas.**

- ¿Se puede quedar la racha **durable** en 3 y la de **proceso** en 5 (o al revés) sin que nadie lo
  declare? El incremento devuelve el número persistido y el log lo publica: si divergen, es un hallazgo.
- ¿Se siembra **dos** veces si el proceso recibe dos ticks? `_v2_adaptive_state_recovered` lo impide
  (`:3579-3581`).
- ¿Qué pasa con el flag **ON→OFF** en caliente (tunables)? La racha se escribe solo cuando el camino
  Adaptive corre; con OFF no hay escritura, y la que había se queda como constancia.

---

## 4. La declaración: sello `auto15-v1` y el hecho `sinkFailuresDurable`

- **`DATA_GATE_POLICY_VERSION` → `auto15-v1`** (`auto_adaptive_data_gate.py:76`). Cambia la
  **procedencia** de uno de los hechos, así que el sello sube; **no** cambian los umbrales
  (`DATA_GATE_SINK_FAILURES_STALE_DEFAULT = 3`, `:80`), la tabla estado→efecto ni la precedencia
  `BLOCKED > STALE > DEGRADED > OK`: el diff de esas líneas es **vacío**.
- **`sinkFailuresDurable`** (`:152`, publicado en `:189`): dice si la racha entró **desde** el estado
  durable o nació en el proceso. Es un hecho **declarado por el llamante**, no una inferencia del gate,
  y por defecto es `false` (`:253`): sin declaración, **no** se afirma durable.
- **`ADAPTIVE_POLICY_VERSION` NO se toca** (sigue `auto14-v1`): la regla de **reparto** no cambia y
  subirla sería mentir sobre ella.
- **Sin consecuencia de mismatch.** El sello del gate **no** entra en ninguna maquinaria de comparación:
  `policy_version_mismatch` que recibe el gate viene del **estado Adaptive** (`auto_simulation_worker.py:3348`),
  no de `DATA_GATE_POLICY_VERSION` (uso medido: literal del módulo + campo de la lectura). Por eso esta
  subida **no** marca un tick `STALE` en las filas históricas —a diferencia del sello `auto14-v1`, que
  **sí** se compara sobre el journal—, y así se declara.

---

## 5. La costura del reinicio (con CONTROL) y la certificación contra PostgreSQL real

- **Costura hermética** (`test_auto_v56_auto15_data_gate_durable_seam.py`, **9** tests, por el camino
  real del worker): `3` fallos del sink ⇒ `STALE`; **proceso nuevo** con el mismo store ⇒ el gate sigue
  viendo la racha; una publicación intermedia ⇒ el reinicio lee `0`; y el **control negativo**: **sin**
  store, el proceso nuevo lee `0` y su gate vuelve a `OK` (el límite que la fase cierra, medido).
- **PG real** (`test_auto_v56_auto15_data_gate_pg.py`, **6** tests, job `auto-v2-durable-pg` con
  `ADAPTIVE_GATE_PG_REQUIRED=1`): roundtrip de la `045` (`upgrade`/`downgrade`/`upgrade`), la racha
  **sobrevive a una sesión nueva** y el gate la sigue viendo, incremento atómico por clave, reset que no
  amplifica, y la **sesión del tick queda usable** tras un fallo de escritura (transacción envenenada a
  mano con `SELECT 1/0`).

---

## 6. Matriz de mutaciones (`M108…M118`): 11/11 muerden

| # | Mutación | Invariante que ataca |
| --- | --- | --- |
| `M108` | el arranque deja de sembrar la racha durable | el reinicio **olvida** la racha |
| `M109` | el fallo se cuenta y **no** se escribe | persistencia aparente |
| `M110` | la fila se lee y el valor se **descarta** | I/O pagada para nada |
| `M111` | el reset escribe aunque no haya racha viva | **amplificación** en el camino sano |
| `M112` | el `load` deja de casar la cuenta | racha de **otra** cuenta |
| `M113` | el estado ilegible se declara **durable** | un `0` sin constancia como hecho probado |
| `M114` | el estado ilegible se cuenta como **fallo** | racha **inventada** por un hueco de lectura |
| `M115` | la procedencia cambia y el **sello no** | dos formas de medir sin declararlo |
| `M116` | `sinkFailuresDurable` se publica **sin store** | constancia durable afirmada sin prueba |
| `M117` | la escritura fallida **no** limpia la sesión del tick | sesión envenenada tras un fallo declarado |
| `M118` | el reset fallido **no** limpia la sesión del tick | lo mismo por la puerta del reset |

La corrida **completa** de la matriz está en §8.

---

## 7. Verificación (lo medido, y lo que no se pudo medir aquí)

- **Compuertas §3 del relevo, con el comando de CI** (no rutas sueltas):
  `ruff check packages/py apps/api-python --config pyproject.toml` **`All checks passed!`**;
  `mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent`
  **`0` errores en `498` ficheros**; `lint-imports --config packages/py/.importlinter` ⇒ **`4 kept, 0 broken`**.
  *(Nota de método: `ruff check <rutas>` **sin** `--config pyproject.toml` resuelve el `pyproject` del
  paquete y reporta falsos `I001` —se reprodujo también sobre el ya certificado `kill_switch_store.py`—:
  la fase se midió con el comando de CI.)*
- **Unit de la fase:** `test_auto_adaptive_data_gate.py` **32** (HEAD **29**: **+3**), con el bloque
  `AUTO-15` completo: el sello literal, la procedencia declarada **sin** mover el estado (misma racha ⇒
  misma lectura salvo el campo nuevo) y el defecto **no** durable cuando el llamante no declara.
- **Unit nuevo del store** `test_adaptive_gate_store.py` (**10 tests**, nuevo): racha consecutiva, reset
  que conserva el rastro, reset que **no escribe** sin racha viva, racha **por clave** que no se filtra,
  clamp de un número imposible, `to_dict` con sus nombres y el **contrato de sesión** (una sesión que
  falla recibe exactamente un `rollback`, ningún `commit`, y el error **sube**).
- **Costura nueva** `test_auto_v56_auto15_data_gate_durable_seam.py` (**9 tests**) por el camino real del
  worker y **con control negativo** (sin store el reinicio lee `0` y el gate vuelve a `OK`), más store
  roto, publicación que cura, y la declaración del tick con y sin procedencia durable.
- **PG real** `test_auto_v56_auto15_data_gate_pg.py` (**6 tests**) contra el PostgreSQL del compose:
  **`6 passed`** — roundtrip de la `045`, reinicio real, atomicidad por clave, reset sin amplificación y
  sesión del tick usable tras un fallo de escritura.
- **Tramo de la fase:** `test_auto_adaptive_data_gate.py` (32) + `test_adaptive_gate_store.py` (10) +
  `test_auto_v56_auto15_data_gate_durable_seam.py` (9) ⇒ **`51 passed`** (`+ PG 6` ⇒ **`57`**), `0` rojos.
- **Delta simétrico FICHERO A FICHERO contra `HEAD`** (nunca restando totales). Un solo fichero de test
  **modificado**; los otros tres son **nuevos** (no existen en `HEAD`):

  | Fichero | HEAD vs fase | Rojos | Causa declarada |
  | --- | --- | --- | --- |
  | `packages/py/analytics/tests/test_auto_adaptive_data_gate.py` | **`29 passed`** (HEAD `29`; árbol `13817` B → `16090` B) | **ninguno** | — |
  | `packages/py/application/tests/test_adaptive_gate_store.py` | **no existe en `HEAD`** | — | unit **nuevo** de la fase |
  | `apps/api-python/tests/test_auto_v56_auto15_data_gate_durable_seam.py` | **no existe en `HEAD`** | — | costura **nueva** de la fase |
  | `apps/api-python/tests/test_auto_v56_auto15_data_gate_pg.py` | **no existe en `HEAD`** | — | certificación **PG nueva** de la fase |

  **Desviación medida respecto al plan, declarada:** el plan preveía «rojos declarados» (el sello del gate
  y el campo nuevo) y la medida dice **`0` rojos**: el literal `auto13-v1` **no** estaba fijado por ningún
  test de `HEAD` (el test del sello lo **añade** esta fase) y `sinkFailuresDurable` es **aditivo** en
  `as_dict()` (nadie comprobaba la igualdad exacta del diccionario). Se publica la **cifra medida**, no la
  prevista, y el original se restauró **byte a byte** (sha256 verificado).
- **Matriz de mutaciones COMPLETA** (`M1…M118`): **`118/118` muerden**, **`0`** etiquetas en `NADA`,
  **`0`** fragmentos ausentes, restauración **byte a byte** y huella `git status` **idéntica** antes y
  después (`intacto: la sonda no altero el arbol`). Las **11** nuevas (`M108…M118`) muerden, cada una como
  mínimo sobre un test **con nombre** (detalle en §6 y en la salida de la sonda).
- **Gobernador y contrato durable intactos** (medido): `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py`
  y `git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py` ⇒ **vacíos**, y el
  script del gobernador ⇒ **`exit 0`**.
- **Lo que no se pudo medir aquí:** la batería offline **completa** de los jobs `quality`/`python` del tag
  (su recolección incluye suites PG que importan `asyncpg`, ausente en esta máquina). **Ese límite lo
  cierra la CI del tag** (§11), medida.

---

## 8. Límites declarados (no silenciosos)

- **Solo se persiste la racha**, no el estado del gate ni el plan: el gate sigue siendo una **lectura**
  del tick.
- **No hay TTL ni decadencia.** Una racha durable de un proceso muerto mantiene el gate degradado hasta
  la **primera publicación**, que la resetea («se cura en un tick»). Un TTL sería una heurística no
  declarada; una racha vieja es prueba real de que hubo fallos.
- **La granularidad es `(account_id, engine_id)`**, no por venue ni por sink: es la misma clave con la
  que se identifica el motor Adaptive.
- **Persiste el conteo consecutivo, no el histórico**: las fechas (`last_failure_at`, `last_success_at`)
  son el rastro auditable, y el reset **no** las borra.
- **El flag Adaptive sigue OFF**: sin él, esta fase **no ejecuta** ni lectura ni escritura.
- **Fuera de alcance, sin tocar:** UI, SHORT, backfill y el resto de preguntas abiertas del §9 del
  arranque del auditor.

---

## 9. Freeze respetado

No se toca el sello de `V2.53`/`V2.54`/`V2.55`, `auto_adaptive_journal.py` (**byte a byte igual**), el
contrato de `decision_journal_entries`, `yahoo_circuit_breaker.py`, `ADAPTIVE_ADVERSE_REGIMES`, los
umbrales de rotación, el **gobernador** (`v2_43_governor_evidence.py`: **diff vacío** y script `exit 0`)
ni la tabla estado→efecto del gate. **Sin UI**, sin SHORT, sin backfill; `*.md` **sin `prettier`**;
`governor.json` sigue **sin trackear**.

---

## 10. Sellado

El paquete de cierre (este pack, el [relevo](./traspaso-relevo-post-v2.56-auto-15-data-gate-persistido-2026-09-23.md),
el [arranque del auditor](./arranque-auditor-v2.56-auto-15-data-gate-persistido-2026-09-23.md) y el
[del agente siguiente](./arranque-agente-post-v2.56-auto-15-2026-09-23.md), `CHANGELOG.md`,
`PROJECT_STATE.md`, el índice y el bump `1.81.0-beta`) viaja **dentro** del tag. **Excepción declarada:**
esta §11 con los runs de CI **medidos** se añade en el commit de docs **posterior** al sello (mismo
patrón que `AUTO-13`/`AUTO-14`): el run del tag no existe hasta que el tag se empuja, así que la tabla se
**mide** en lugar de predecirse.

---

## 11. CI del sello `v2.56-beta`

**Se mide, no se predice:** el run del tag no existe hasta que el tag se empuja, así que estas cifras se
añaden en el **commit de docs posterior al sello** (mismo patrón que `AUTO-13`/`AUTO-14`), citando cada una
el run que la produjo. Este pack se lee **con** ese commit: si la tabla no está, la CI del tag **no está
medida todavía**.
