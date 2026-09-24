# Arranque del auditor — `v2.56-beta` (AUTO-15 · Data Gate PERSISTIDO)

**Fecha:** 2026-09-23 · **Ref a atacar:** tag **`v2.56-beta`** (`1.81.0-beta`) ·
**Pack que manda:** [`audit-pack-v2-56-auto-15-data-gate-persistido-2026-09-23.md`](./audit-pack-v2-56-auto-15-data-gate-persistido-2026-09-23.md).
Si algo de este arranque contradice al pack, **manda el pack**. El plan de fase (ratificado) es
[`plan-v2-56-auto-15-data-gate-persistido-2026-09-23.md`](./plan-v2-56-auto-15-data-gate-persistido-2026-09-23.md)
y el relevo cerrado
[`traspaso-relevo-post-v2.56-auto-15-data-gate-persistido-2026-09-23.md`](./traspaso-relevo-post-v2.56-auto-15-data-gate-persistido-2026-09-23.md).

Las `ruta:línea` de este documento están **verificadas en el árbol el 2026-09-23**. Cada afirmación trae
**el comando exacto** para medirla. Este documento existe para que no gastes presupuesto redisculpiendo lo
ya medido.

**Contexto del sello:** la fase entera viaja en **fast-forward** sobre `e29e6227` (el commit sellado de
`AUTO-14`), **sin merge commit** y sin rama de fase: el padre inmediato del commit sellado es
`b96ae624` (el plan ratificado, tras los dos commits de docs del sello de `AUTO-14`). **Hay un RE-SELLO
declarado**: el primer CI del tag (sobre `c62ac459`) salió **rojo** porque
`apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` ancla la head de Alembic en
`_ALEMBIC_HEAD` y la fase la subió a `045` sin bumpear esa constante (**5** aserciones que solo corren en
los jobs PG); el fix es de una línea y el tag apunta ahora a **`8ad54416`**, con `c62ac459` conservado en
la historia y su rojo **declarado** (§11.1 del pack). **Superficie de auditoría:** el **PR draft** de la
rama `auto-15-data-gate-persistido` se abre **después** del sello **solo** para revisar con comentarios en
línea; su diff medido es el de la fase (**22 ficheros, `+2994/−24`**) y **no** es vehículo de merge. **SÍ
hay migración:** Alembic head `044_auto_cycle_trace` → **`045_adaptive_gate_state`**.

---

## 0. Si solo tienes una hora

1. **§2 — el store** (es *el* diseño de la fase: qué se escribe, cuándo y **cuándo no** se escribe nada).
2. **§3 — la siembra del worker** (¿se siembra antes o después de los atajos del lector del journal? Es
   el punto donde un reinicio durante un journal roto se juega la racha).
3. **§4 — la declaración y el sello** (¿se puede confundir un `0` durable con un `0` de proceso? **no
   debe**).
4. **§1 — el invariante**: «no acusar sin prueba» sobrevive a un reinicio.

---

## 1. El invariante (ataca contra él, no contra el estilo)

**La racha con la que el gate juzga su propia evidencia no puede depender de que el proceso siga vivo**,
y **tampoco** puede inventarse cuando no hay constancia: se **lee**, se **declara** su procedencia y,
sin fila, el hueco se dice.

| Punto | `ruta:línea` |
| --- | --- |
| Tabla del estado durable (PK `(account_id, engine_id)`) | `packages/py/infrastructure/alembic/versions/045_adaptive_gate_state.py:66-82` |
| Fila ORM | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py:2736` |
| Contrato puro y gemelo in-memory | `packages/py/application/src/bolsa_application/adaptive_gate_store.py:46` / `:153` |
| Store PG | `adaptive_gate_store.py:207` |
| Clamp defensivo de la racha leída | `adaptive_gate_store.py:72` (`sink_failures_from_state`) |
| Sello del gate | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py:76` (`auto15-v1`) |
| Hecho de procedencia | `auto_adaptive_data_gate.py:152` / `:189` / `:253` |
| Conexión al gate en el tick | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:3334` / `:3337` |

**Preguntas incómodas.**

- ¿Hay **algún** camino en el que un `0` sin constancia durable se publique como hecho medido? El campo
  `sinkFailuresDurable` está para eso: sin él, un lector no distingue «no se observó» de «se olvidó».
- ¿Y al revés: puede `sinkFailuresDurable = true` con `sink_failures = 0` **sin** que nadie haya
  consultado el store? Es la mentira simétrica; por defecto es `false` y solo lo pone quien puede
  afirmarlo (siembra, incremento o reset contestado).
- ¿Puede el `rollback` de un fallo de escritura llevarse por delante trabajo ya escrito en la misma
  sesión del tick? El store escribe **después** del commit de la reserva de entrada y el error **sube**
  para declararse.

---

## 2. El estado durable: qué se escribe, y qué **no**

`PostgresAdaptiveGateStore` (`adaptive_gate_store.py:207`) escribe en la **misma sesión del tick** con
`autocommit` explícito (patrón de `kill_switch_store.py`), con `rollback` + `raise` en el fallo
(`:255-265`, `:284-290`).

| Operación | Qué hace | Línea |
| --- | --- | --- |
| `load` | la fila de la clave, o `None` (sin constancia durable) | `:218` |
| `record_failure` | `INSERT … ON CONFLICT (account_id, engine_id) DO UPDATE SET sink_failures = sink_failures + 1` y devuelve la racha resultante | `:234-268` |
| `record_success` | `UPDATE … WHERE sink_failures > 0` (devuelve `0` y **no escribe** si no había racha) | `:270-292` |
| `commit` | hace durable lo escrito | `:294` |

**Decisiones finas, medidas.**

- **El `+1` lo hace la base**: un `load`+`save` perdería un fallo concurrente, y la racha es justo el dato
  que no puede perderse.
- **El camino sano no escribe**: sin racha viva no hay `UPDATE` que ejecutar (ni fila que crear). Un
  despliegue sano **no paga una escritura por tick**.
- **Nunca se crea la fila "por si acaso"**: `record_success` sobre una clave sin fila devuelve `0` y la
  clave sigue **sin** fila (test PG `test_the_reset_writes_once_and_does_not_amplify_when_idle`).
- **Sin backfill**: la ausencia de fila es información (racha `0` declarada), nunca un `0` fabricado.

**Preguntas incómodas.**

- ¿Se puede quedar la racha **durable** en `N` y la de **proceso** en otro número sin que nadie lo
  declare? El incremento devuelve el persistido y el log lo publica (`:3469-3472`).
- ¿Puede una clave "olvidada" (fila con racha de hace meses) mantener el gate degradado para siempre?
  **Sí, y está declarado**: no hay TTL (§8 del pack). La primera publicación la resetea. Si crees que eso
  es un defecto, es un hallazgo **de producto**, no de implementación: el TTL no está y no se finge.
- ¿El índice `(account_id, sink_failures)` se usa para algo hoy, o es coste de escritura sin lector?
  Declarado en el pack: se crea para «¿qué motores de esta cuenta arrastran racha?»; **hoy no lo lee
  nadie** — pregunta abierta (§9), no defecto silencioso.

---

## 3. El worker: sembrar al arrancar, escribir sin amplificar

| Punto | `ruta:línea` |
| --- | --- |
| Contador de proceso + bandera de procedencia | `auto_simulation_worker.py:753` / `:757` |
| Store del constructor (hermético/tests) | `auto_simulation_worker.py:826` |
| Siembra: `_v2_recover_adaptive_gate_streak` | `auto_simulation_worker.py:3484` |
| Se llama **antes** del primer plan y del atajo del lector | `auto_simulation_worker.py:3588` (dentro de `:3565`) |
| Gate del flag (`adaptive_enabled`) | `auto_simulation_worker.py:3581-3583` |
| Incremento en el fallo del sink | `auto_simulation_worker.py:3469` → `:3524` |
| Reset al publicar | `auto_simulation_worker.py:3481` → `:3549` |
| Cableado de producción (una sesión por tick) | `auto_simulation_worker.py:5599-5605` → `:5625` |

**La decisión que más importa (y su porqué).** La siembra va **antes** de los atajos del lector del
journal: la racha de fallos es un hecho de **otro** eje (el sink que escribe), y el escenario en que más
importa —el journal **roto**— es justo el que deja `read_ok = False`; si se sembrara después de ese atajo,
un reinicio durante un journal roto arrancaría en `0` y habría perdido la racha **precisamente** cuando
hacía falta (comentario en `:3583-3587`, y su mutación `M108`).

**Preguntas incómodas.**

- ¿Se puede sembrar **dos** veces en un proceso (dos ticks, dos recover)? `_v2_adaptive_state_recovered`
  (`:3579-3581`) lo cierra.
- ¿Qué pasa si el store falla **al incrementar**? La racha cae al proceso, `sinkFailuresDurable = false`
  y el error se loguea (`:3536-3547`): se pierde durabilidad, **no** la cuenta del turno.
- ¿Y si falla **al resetear** después de publicar? La publicación ya ocurrió; el reset fallido se declara
  y la racha durable **se queda** —el proceso pierde la memoria de la curación—: es el peor caso
  declarado de la fase (una racha curada se vería como viva hasta el siguiente reinicio). **Búscalo.**

---

## 4. La declaración y el sello (medir ≠ publicar de más)

- **`DATA_GATE_POLICY_VERSION` → `auto15-v1`** (`auto_adaptive_data_gate.py:76`): cambia la
  **procedencia** de uno de los hechos. **No** cambian los umbrales (`:80`), la tabla estado→efecto ni la
  precedencia: el diff de esas líneas es **vacío**.
- **`sinkFailuresDurable`** (`:152`) viaja en `as_dict()` (`:189`) y por defecto es `false` (`:253`).
- **`ADAPTIVE_POLICY_VERSION` NO se toca** (`auto14-v1`): la regla de **reparto** no cambia.
- **Sin consecuencia de mismatch:** `policy_version_mismatch` que recibe el gate sale del **estado
  Adaptive** (`auto_simulation_worker.py:3348`), no de `DATA_GATE_POLICY_VERSION`; por eso este sello
  **no** marca un tick `STALE` en filas históricas (a diferencia de `auto14-v1`).

**Preguntas incómodas.**

- ¿El sello del gate se **compara** en algún sitio (y por tanto podría crear un `STALE` no declarado)?
  Mídelo con `rg "DATA_GATE_POLICY_VERSION" -g '*.py'`: solo literal del módulo, campo de la lectura y un
  test del sello.
- ¿`sinkFailuresDurable` se cuela en el journal durable? La proyección por lista blanca
  (`auto_adaptive_journal.py:58`) es de `allocation`; el gate **no** se proyecta: compruébalo con
  `git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py` (**vacío**).

---

## 5. La costura del reinicio (con CONTROL) y la certificación PG

- **Costura hermética** (`apps/api-python/tests/test_auto_v56_auto15_data_gate_durable_seam.py`, **9**
  tests): `3` fallos ⇒ `STALE`; proceso **nuevo** con el mismo store ⇒ sigue `STALE`; publicación
  intermedia ⇒ el reinicio lee `0`; **control negativo**: **sin** store el proceso nuevo lee `0` y su gate
  vuelve a `OK`; store roto ⇒ racha `0` + motivo + `sinkFailuresDurable = false`.
- **PG real** (`apps/api-python/tests/test_auto_v56_auto15_data_gate_pg.py`, **6** tests): roundtrip de la
  `045`, la racha **sobrevive a la sesión nueva**, el incremento es atómico por clave y **no** se
  contagia, el reset **no** amplifica, y la sesión del tick queda **usable** tras un fallo de escritura
  (transacción envenenada con `SELECT 1/0`).

**Preguntas incómodas.**

- ¿La costura del reinicio mide el **reinicio** o solo llama al método de siembra? El proceso 2 se
  construye **sin** contador previo y su gate se lee por el mismo método del tick (`_v2_adaptive_data_gate`).
- ¿El control negativo (sin store) sigue existiendo como test propio? Sí: sin él, un `0` de proceso y un
  `0` durable se verían igual.
- ¿La certificación PG puede **skippear** en la CI? No: `ADAPTIVE_GATE_PG_REQUIRED=1` convierte el skip
  en **FALLO duro** (patrón del repo).

---

## 6. Mutaciones que YA se midieron (no las redisculpas)

`M108`…`M118` (**11**), todas mordiendo, con la matriz **completa** (`M1…M118`) en **`118/118`**, `0` en
`NADA` y el árbol intacto. El detalle, en el pack (§6). Las que más se acercan a un hallazgo real son:

| # | Qué rompe | Dónde mira el auditor |
| --- | --- | --- |
| `M109` | el fallo se cuenta y **no** se escribe | persistencia aparente |
| `M111` | el reset escribe sin racha viva | **amplificación** en el camino sano |
| `M113` | el estado ilegible se declara durable | un `0` sin constancia como prueba |
| `M117` | la escritura fallida no limpia la sesión | sesión del turno envenenada |

---

## 7. Comandos exactos (no los reinventes)

```bash
# Estático (los de CI, no rutas sueltas)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió: diff VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# El contrato durable NO se movió: diff VACÍO
git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py

# La migración SÍ se movió: head = 045_adaptive_gate_state
uv run alembic -c packages/py/infrastructure/alembic.ini heads

# La GUARDIA de head también (esto fue el rojo del primer tag, §11.1 del pack):
# ``_ALEMBIC_HEAD`` debe casar con la head real, y solo lo comprueban los jobs PG.
rg -n "_ALEMBIC_HEAD" apps/api-python/tests/test_discovery_evidence_snapshot_pg.py

# La suite PG del gate, contra el PostgreSQL del compose (~2 s)
uv run pytest apps/api-python/tests/test_auto_v56_auto15_data_gate_pg.py -q --tb=short -rs

# El tramo de la fase (unit + costura hermética; el PG va aparte)
uv run pytest packages/py/analytics/tests/test_auto_adaptive_data_gate.py \
              packages/py/application/tests/test_adaptive_gate_store.py \
              apps/api-python/tests/test_auto_v56_auto15_data_gate_durable_seam.py -q

# La matriz de mutaciones (mide, restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M108 M109 M110
```

**Al correr la matriz:** el `stdout` de Python va **bufferizado por bloques** y el `tee` no ayuda: el log
puede aparecer entero al final. Para saber por dónde va, mira el `mtime` de los ficheros mutados.
Interrumpir la tarea **no mata** al hijo en Python, y el script reescribe ficheros en bucle: comprueba
procesos y `git status` **antes** de dar la corrida por cerrada; si queda un mutante, restaura con
`git checkout -- <fichero>` y verifica `git hash-object` contra `HEAD:<fichero>`.

---

## 8. Qué NO es un hallazgo (declarado de antemano)

- Que **no haya TTL** para una racha vieja: es una **decisión declarada** (§8 del pack) y el patrón del
  mismatch de política de `AUTO-13`: una racha vieja es prueba **real** de que hubo fallos, y la cura es
  la primera publicación.
- Que el **índice** `(account_id, sink_failures)` no tenga lector hoy: se declara como coste de escritura
  asumido por si el diagnóstico por cuenta hace falta.
- Que con el **flag OFF** no haya ni un I/O nuevo: es el diseño; sin él el camino publicado es
  byte-idéntico a `v2.55`.
- Que el gate **no** cambie de estado por la procedencia de la racha: el gate juzga el **hecho**, no su
  origen; lo que se declara es la procedencia, no un criterio nuevo.
- Que el fallo del **reset** deje la racha durable viva hasta el siguiente reinicio: es el peor caso
  **declarado** de la fase (§3), y no hay camino que lo silencie.
- Los rojos de las suites **PG** en local sin PostgreSQL: la CI las mide con
  `ADAPTIVE_GATE_PG_REQUIRED=1` (fail-if-skipped).
- **Los dos rojos iniciales del tag por tests PREEXISTENTES** (§11.3 del pack): el test PG intermitente
  `test_concurrent_auto_pg.py` (de `V2.46`, `1` rojo en `5` corridas medidas) y el teardown de vitest que
  envenena el exit code con los **`1290`** tests en verde (`mandate-tenure-pnl.test.ts`). **No** están en el
  diff de la fase y se re-ejecutaron: son **deuda declarada**, no hallazgos de `AUTO-15`. **Sí** es
  hallazgo legítimo si demuestras que el fallo depende de algo que esta fase cambió.
- **Sin UI** para `AUTO-7`…`AUTO-15`: todo esto es observable por el journal y los logs del tick.

---

## 9. Preguntas abiertas que el autor NO cierra

1. **¿Debe caducar una racha durable?** Hoy no caduca (ni TTL ni decadencia): una racha de un proceso
   muerto mantiene el gate degradado hasta la primera publicación. ¿Es la política correcta, o el tiempo
   debería contar sin evidencia nueva? (Candidato **D** del arranque del agente.)
2. **¿El diagnóstico por cuenta se usa alguna vez?** El índice `(account_id, sink_failures)` se creó para
   «¿qué motores de esta cuenta arrastran racha?» y hoy no lo lee nadie. ¿Se le da lector (UI/diagnóstico)
   o se retira?
3. **El coste sigue siendo estimado**: el R neto cae a `PARTIAL` y con él la celda a
   `cell_net_unmeasured`. Mientras el coste no sea **medido**, el eje del R neto y las celdas solo actúan
   donde la medición alcanza. (Candidato **C**.)
4. **Los umbrales siguen declarados, no calibrados** (`sink_failures_stale = 3`,
   `journal_gap_blocked = 10`, `evaluation_cycle_seconds = 60.0`, `min_trades`, `confidence_prior = 20`,
   `severe_decay_factor = 0.5`, `recovery_step_cycles = 3`). ¿Con qué evidencia se sostienen?
5. **¿La racha debe persistir el histórico de fallos intermitentes?** Hoy se guarda el **consecutivo**
   (con las dos fechas como rastro). Un sink que falla 1 de cada 3 ticks no llega a `STALE` nunca: ¿es
   suficiente el consecutivo, o el patrón intermitente merece otro hecho declarado?

---

## 10. Lo que **no** debes asumir

- Que un test verde proteja nada: exige **el control**. En esta fase el control es el reinicio **sin**
  store (que vuelve a `OK`): si ese test desaparece, la costura deja de probar lo que dice.
- Que `118/118` y `0` en `NADA` signifiquen cobertura: significan que **esas 118** mordieron. Una
  **nueva** forma de romper el invariante es un hallazgo legítimo.
- Que el filtro de la sonda sea `--only`: se le pasan los rótulos **como argumentos** (`… M108 M109`).
- Que `git show HEAD:<f> > <f>` sea seguro en PowerShell: **fabrica bytes nulos**. Escribe con Python
  **como bytes** y **verifica la restauración**.
- Que las cifras del `CHANGELOG` sean la CI: son la selección local; las del tag citan su run.

---

## 11. Formato del hallazgo

```
P0/P1/P2 · afirmación · ruta:línea · comando exacto · salida · ¿ya declarado en §8/§9 o en el §8 del pack?
```

Las cifras del **tag** citan el run de `Release tag CI` que las produjo (tabla en el §11 del pack); las
locales citan el comando y su salida. **Ninguna cifra se atribuye a un artefacto que no la produjo.**
