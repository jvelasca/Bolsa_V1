# Audit-pack `AUTO-10` Journal durable por ciclo (`cycleId` + `marketRegime`) — `1.76.0-beta` (2026-09-22)

**Fase:** `AUTO-10` (línea AUTO) · **Bump:** `1.75.0-beta` → **`1.76.0-beta`** · **Migración:** **NO**
(Alembic head sigue en `044_auto_cycle_trace`) · **SHORT:** no · **UI nueva:** no · **Backfill:** no ·
**Contrato de API:** sin cambio.
**Plan de la fase:**
[`plan-v2-51-auto-10-journal-durable-por-ciclo-2026-09-22.md`](./plan-v2-51-auto-10-journal-durable-por-ciclo-2026-09-22.md)
· **Relevo:** [`traspaso-relevo-post-v2.51-auto-10-journal-durable-por-ciclo-2026-09-22.md`](./traspaso-relevo-post-v2.51-auto-10-journal-durable-por-ciclo-2026-09-22.md)
**Sello:** commit de **código** `8dda5e3a` (19 ficheros, `+2242/−38`) + commit de **documentos de fase**
`dba3d4f8` (este pack, el relevo y el índice). **Tag anotado** `v2.51-beta` → objeto **`f9930db4`** →
commit **`dba3d4f8`**: los tres documentos de fase viajan **dentro** del tag, como en `v2.47`–`v2.50`.
`package.json` → **`1.76.0-beta`**. **CI real: 10/10 `success`** sobre el tag (§7).

---

## 0. Resumen: qué instala esta pasada

| #   | Deuda heredada de `V2.50`                                                        | Estado    | Evidencia (medida)                                            |
| --- | ------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------- |
| 1   | El journal del worker era **en memoria** ⇒ el régimen por ciclo no era durable   | **CERRADO** | `auto_cycle_journal.py` + sink con `commit` (M34–M38) (§1)     |
| 2   | `cycle_risk` declaraba `regime_not_durable` **siempre**                          | **CERRADO** | lector + confirmación de payload + `regime_not_found` (§2)     |
| 3   | «Basta con creer una fila por `decision_id`»                                     | **CORREGIDO** | la forma no prueba origen: se **confirma** `payload['cycleId']` (§2) |
| 4   | Un reintento del tick podía duplicar la traza sin que nadie lo supiera            | **CERRADO** | dedupe declarado: `duplicates` + `collapsedRows` (§3)          |
| 5   | `M25`/`M26`/`M33` de la matriz **no aplicaban** y la sonda **seguía**             | **CORREGIDO** | fragmentos reescritos + sonda que **falla** si faltan (§4)     |

**Lo que esta pasada NO promete** (declarado, no escondido): ciclos históricos ya cerrados sin entrada
durable siguen declarando su hueco (`AUTO-10` no reescribe el pasado); `netExpectancyR` sigue
necesitando además ciclos **medidos con coste** (esta fase garantiza el **insumo** del eje
`strategy × regime`, no que el número aparezca); el cooldown sigue **en memoria** y la UI de
`AUTO-7`/`AUTO-8`/`AUTO-9` sigue sin existir.

---

## 1. El invariante: **lo que se escribe es el régimen del turno que decidió**

El módulo nuevo es `packages/py/application/src/bolsa_application/auto_cycle_journal.py` (contrato
**puro**): `cycle_decision_id()` y `build_auto_cycle_regime_entry()`. Tres reglas duras, **cada una con
test y con mutación**:

1. **La identidad se deriva, no se recalcula** (`auto_cycle_journal.py:52`, prefijos en `:48`–`:49`).
   `cyc-<x>` → `dec-<x>` por **intercambio de prefijo**: es la **misma** clave la que acuña ciclo y
   decisión (el digest `sha256` es el mismo, medido en la sonda de `V2.50`), así que no se inventa un
   identificador nuevo ni se pide una migración: se usa el **índice ya existente**
   `decision_journal_entries_decision_id_idx`. → **M34** (4 rojos).
2. **Sin identidad no hay entrada, y no se finge** (`auto_cycle_journal.py:96` para el `cycle_id`
   ausente, `:61`–`:64` para el que no tiene forma, `:105` para el flag). Sin `cycle_id` ⇒ `None`
   (no-op declarado, no una fila de ciclo vacío); con `cycle_id` sin forma `cyc-` ⇒ se escribe igualmente
   con `decision_id` propio y **`cycleIdDerived = False`**, para que el lector sepa que el índice **no**
   alcanza ese ciclo en lugar de creer que lo alcanzó y no estaba. → **M35** (3 rojos).
3. **El régimen ausente se declara** (`auto_cycle_journal.py:104`). `marketRegime = None` **y**
   `regimeMeasurement = UNKNOWN` en el payload: un `UNKNOWN` de relleno parecería un valor medido. →
   **M36** (2 rojos).

**El orden no es un detalle: primero el dinero, después la traza.** `_v2_journal_cycle_regime` se llama
**después** de commitear el compromiso de capital del ciclo (`_v2_persist_tick_reservations`): si la
traza falla, el dinero sigue comprometido y el hueco se declara; al revés se habría publicado un ciclo
que no llegó a existir. → **M37** (5 rojos).

**Un `flush` no es un `commit`.** El sink real (`build_cycle_regime_sink(session)`, en `run_tick`) hace
`append` **y** `commit` sobre la sesión del tick: sin el `commit` la fila moriría al cerrar la sesión y el
hueco volvería a mentir por omisión. En el fallo hace `rollback` **y re-lanza**: sin el `rollback` la
sesión quedaría envenenada y rompería el resto del turno (fail-open **declarado**, no accidental). →
**M38** (2 rojos).

---

## 2. El lector: la forma **no** prueba origen

`packages/py/application/src/bolsa_application/auto_cycle_regime_reader.py` es puro sobre un puerto de
lectura (`RegimeFetch`). Pregunta por el `decision_id` **derivado** y **confirma** antes de creerse nada:
`payload['cycleId']` tiene que ser **exactamente** el ciclo pedido y `event_type` el esperado. El porqué
está medido, no supuesto: el `decision_id` de un ciclo lo comparte su entrada de **ventana**
(`AUTO_CYCLE_WINDOW`), y el fallback aleatorio acuña un `cycle_id` con **la misma forma** `cyc-<uuid>` —
o sea que «hay una fila con ese `decision_id`» es compatible con «no sé nada de este ciclo». → **M39**
(3 rojos).

**Los tres huecos se declaran por separado**, porque no son el mismo hecho:

| Hueco           | Qué significa                                                        |
| --------------- | -------------------------------------------------------------------- |
| `unconfirmed`   | hay fila con ese `decision_id`, pero **no es usable** (otro evento, otro `cycleId`, o régimen declarado `None`) |
| `absent`        | **no** hay fila                                                      |
| `not_derivable` | el `cycle_id` no tiene forma `cyc-`: el índice **no lo alcanza** y no se adivina |

Tandas acotadas (`DEFAULT_REGIME_CHUNK = 500`) e invariante de **orden**: el mapa y los huecos no
dependen del orden de entrada ni de `cycle_id` repetidos (pedido una vez).

**`cycle_risk` parte el hueco en dos.** `CYCLE_RISK_REGIME_NOT_DURABLE` (no hay fuente durable: el
comportamiento exacto de `AUTO-9`) y **`CYCLE_RISK_REGIME_NOT_FOUND`** (la fuente **se consultó** y el
régimen no está). Distinguirlos es el punto: «no lo miré» y «no está» no son el mismo hecho, y
confundirlos convertiría una avería del lector en una propiedad del ciclo. El lector **no** toca el
régimen ya medido: el flag solo cambia el **motivo del hueco**.

---

## 3. Dedupe declarado: gana la **confirmación** más nueva

La idempotencia acordada en el plan era «sin migración: `decision_id` determinista + dedupe en **lectura**
(última gana)». Al medirla aparecieron **dos fronteras** que la frase corta no cubría, y ambas tienen test:

1. **Gana la confirmación más nueva, no la fila más nueva.** La entrada de **ventana** comparte
   `decision_id` y es **más nueva** que la traza de apertura; deduplicar por llegada haría que un ciclo
   **con** régimen escrito apareciera como hueco. → **M40** (1 rojo, justo esta frontera).
2. **Un ciclo sin confirmación no cuenta como duplicado.** Sin ganadora no hay nada colapsado: contarlo
   inflaría `duplicates` y confundiría el motivo del hueco (`absent`/`unconfirmed`, no «duplicado»).

Por eso `CycleRegimeReading` gana `duplicates` (por ciclo, las filas **de más**) y `collapsed_rows` (su
suma), visibles en `as_dict()`: un reintento del tick **no** es un fallo, pero **se declara** para que un
duplicado anómalo no sea invisible. → **M41** (3 rojos). El worker no grita por un reintento: con huecos,
la nota va dentro del `warning`; solo con duplicados, un `info`.

---

## 4. La matriz de mutaciones, y un hallazgo que obliga a corregir el sello `v2.50`

**Las ocho nuevas** (`M34…M41`) se verificaron primero **filtradas** y muerden con nombre. Al correr la
matriz **completa**, cuatro etiquetas ya **no encontraban su fragmento** y la sonda lo decía **y seguía**:

| Etiqueta | Estado medido                                        | Causa                                                     |
| -------- | ---------------------------------------------------- | --------------------------------------------------------- |
| `M25`    | **muerta ya en `HEAD` (`df2002e7`)**                 | `ruff format` colapsó el `return (...)` a una línea        |
| `M26`    | **muerta ya en `HEAD` (`df2002e7`)**                 | el `expectancy_ok = (` se reformateó a una línea larga     |
| `M33`    | **muerta ya en `HEAD` (`df2002e7`)**                 | la llamada del worker se partió en tres líneas             |
| `M30`    | **la rompió este tramo** (paso 3)                    | el retorno pasó a llevar `regime_source_durable`           |

Comprobado contra el propio `HEAD` (`git show HEAD:…`): los fragmentos de `M25`, `M26` y `M33` **no
existen** en el árbol sellado. Consecuencia declarada: la afirmación **`33/33 muerden`** de `v2.50`
(plan, audit-pack, relevo y `PROJECT_STATE`) **no era reproducible** al nivel de *«todos los fragmentos
aplican»*: aplicaban **30/33**. La matriz no mintió en lo que midió, pero **afirmaba cobertura que no
tenía**, y la sonda no lo impedía. Enmiendas escritas en los cuatro documentos (§ de cada uno); el
**código** de `v2.50` no cambia: se corrige la afirmación, no el producto.

**Cierre, en dos partes.** (1) Los cuatro fragmentos se reescribieron contra el código real y **muerden**
otra vez (M25: 1 rojo, M26: 1, M30: 4, M33: 3). (2) La sonda **ya no puede perder cobertura en
silencio**: un fragmento ausente pasa a ser un **fallo de la sonda** (`!! mutaciones SIN medir (fragmento
ausente)`, salida distinta de 0), con el mismo criterio con el que ya abortaba si aparecía más de una
vez; la corrida imprime `medidas: N/N`.

**Medición final: `41/41` muerden**, 0 `NADA (la mutacion NO se detecta)`, 41 restauraciones byte a byte
y huella `git status` **idéntica** antes y después (`intacto: la sonda no altero el arbol`).

---

## 5. Coste del lector: medido, y el supuesto corregido

Sonda `apps/api-python/scripts/a9_cycle_regime_read_cost_probe.py`, PostgreSQL 16.14 sobre la base de
desarrollo (**1348 filas** de journal, 15 ciclos por tanda):

| Vía                                        | Medición              |
| ------------------------------------------ | --------------------- |
| Un `decision_id` (índice)                  | **0,028–0,042 ms**    |
| Un ciclo por `payload->>'cycleId'` (JSONB) | **0,124–0,146 ms**    |
| **La tanda del lector** (`decision_id` en `ANY`) | **0,082–0,086 ms** |

El plan daba por hecho «la lectura por `decision_id` cae en el índice». Es cierto **por id** (0,03 ms
frente a 0,13 ms), pero **la tanda** la resuelve el planner recorriendo la tabla, y a este volumen es
**sub-milisegundo**: el planner elige `Seq Scan` para el `ANY` aunque exista el índice. Se declara en el
**código** (`list_by_decision_ids`), en la **sonda** (veredicto explícito) y en el plan (§3.1 y límite
«coste a escala: no medido»). Si el spine crece, la decisión es un índice parcial o de expresión —
**nunca** cambiar la identidad del ciclo.

---

## 6. Evidencia medida

| Bloque (targets del YAML)                   | Base `HEAD` | Con la fase | Rojos | Delta   |
| ------------------------------------------- | ----------- | ----------- | ----- | ------- |
| `quality` (`python-ci.yml`)                 | 2321        | **2368**    | **0** | **+47** |
| job `python` del tag (`release-tag-ci.yml`) | 2329        | **2376**    | **0** | **+47** |

**La base se midió con la misma extracción y el mismo árbol**, apartando el trabajo con `git stash -u`
para correr la batería en `HEAD` (`2321` y `2329`), y **no** restando contra extracciones antiguas: las
cifras publicadas de `v2.50` (`2287`/`2298`) se obtuvieron con una lista de targets **distinta** (50
frentes frente a los actuales), así que restarlas habría sido un número inventado. El delta es la cuenta
exacta de la fase: **+10** contrato puro **+17** lector **+8** costura de escritura **+10** costura de
lectura **+2** `test_cycle_risk.py`.

**Un rojo local, declarado y explicado.** La primera corrida de `quality` marcó
`test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once`. Ese fichero
**no** lleva `--ignore` en el YAML del job `python`: en CI **se salta** (no hay PostgreSQL en ese job),
pero en local **corre** contra la base de desarrollo y sufre contaminación de orden. Aislado pasa
(**1 passed**) y la batería re-ejecutada da **2368/2368**. La base `HEAD` se midió con el mismo estado,
así que el **delta no se ve afectado**; se declara para que nadie lo lea como un verde limpio.

**Compuertas:** `ruff check packages/py apps/api-python --config pyproject.toml` **limpio** · `mypy`
**0 errores / 494 ficheros** · `import-linter` **4/4** · PG con `AUTO_V2_DURABLE_PG_REQUIRED=1`
(`auto_v2_durable_pg` + `portfolio_reservation_pg` + `auto_v2_lifecycle_pg`) **14 passed**.

**Test nuevo que muerde el circuito completo:** `test_auto_v2_durable_pg.py::test_auto_cycle_regime_trace_is_durable_and_readable_from_another_session`
escribe la traza en un turno del worker, la lee desde **otra sesión** con `build_cycle_regime_reader`
(`decision_id` derivado + `payload['cycleId']` confirmado) y limpia sus filas en el `finally`. Se
comprobó que **muerde** al desconectar el sink de `run_tick`: sin el cableado real, la lectura queda vacía.

**Registro en CI simétrico:** `test_auto_cycle_journal.py` y `test_auto_cycle_regime_reader.py` van
**explícitos** en los dos jobs (viven en `packages/py/application/tests`, que no tiene pase de directorio
en ninguno); las dos costuras entran por el pase de directorio de `apps/api-python/tests`.

---

## 7. Sello y CI

Commit de **código** **`8dda5e3a`** — `feat(v2.51): AUTO-10 journal durable por ciclo (cycleId +
marketRegime) (1.76.0-beta)` —, **19 ficheros**, `+2242/−38` — **más** el commit de **documentos de fase**
(este pack, el relevo y el índice). **Tag anotado** `v2.51-beta` → commit de documentos, para que los tres
viajen **dentro** del tag. Push a `main` en **fast-forward** y el tag **empujado de uno en uno** (lección
de `v2.49`: **no** usar `--follow-tags` con tags locales antiguos, porque más de tres tags en un push
**no** disparan los workflows de tag en GitHub).

**CI: 10/10 `success` sobre el tag** (observado con `gh`, no supuesto). El tag disparó los cinco
workflows y todos cerraron en verde; el push a `main` disparó los suyos, también verdes:

| Ref          | Workflow           | Run                                                                            |
| ------------ | ------------------ | ------------------------------------------------------------------------------ |
| `v2.51-beta` | **Release tag CI** | [`35787648126`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787648126) |
| `v2.51-beta` | Python CI          | [`35787648092`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787648092) |
| `v2.51-beta` | Frontend CI        | [`35787648145`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787648145) |
| `v2.51-beta` | Optimize lab       | [`35787647996`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787647996) |
| `v2.51-beta` | Fase 2 scientific  | [`35787648173`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787648173) |
| `main`       | Python CI          | [`35787635754`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787635754) |
| `main`       | Frontend CI        | [`35787635696`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787635696) |
| `main`       | Optimize lab       | [`35787635767`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787635767) |
| `main`       | Fase 2 scientific  | [`35787635669`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787635669) |
| `main`       | Gitleaks           | [`35787635685`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787635685) |

En `Release tag CI`, los diez jobs de decisión en verde (`python`
ruff/imports/mypy/pytest offline, `decision-spine`, `lifecycle-pg`, `dr-verify`, `a7-gate`, `frontend` con
`contract:check`, `playwright` mock, `shared`, `security`) y `certify` agregado, con el único job
**opt-in** de E2E integrado omitido, como está diseñado.

**La certificación PG del tramo corrió de verdad, y se comprobó por su nombre.** El job
`auto-v2-durable-pg` del tag (`Python CI`) dio **45 passed** —los mismos **45** que colecciona la lista
exacta de sus siete ficheros en local— y el test nuevo
`test_auto_cycle_regime_trace_is_durable_and_readable_from_another_session` está **entre los 45
recolectados**: la escritura durable y la lectura desde **otra sesión** quedan certificadas en CI, no solo
en local. El job `quality` del mismo run dio **2334 passed, 38 skipped**: la diferencia con el local
(2368) son las suites PG que ese job **ignora** por diseño (en CI no hay PostgreSQL ahí), que es
exactamente el mecanismo por el que el rojo local declarado en §6 **no** existe en CI.

**Este §7 se escribe DESPUÉS del tag**, en el commit de enmienda inmediatamente posterior (precedente:
la enmienda del sello movido de `v2.50`), porque la tabla necesita runs reales: el pack y el relevo sí
viajan **dentro** de `v2.51-beta`, y el commit de enmienda lo declara.

**Addendum `V2.52` — los *check-runs* del commit del tag, uno por uno (medido, no supuesto).** La
verificación anterior se hizo sobre los **workflow runs**; queda declarado el otro contador, porque
los dos **no** coinciden y la diferencia se lee como un `pending` fantasma en la UI:

```text
gh api repos/jvelasca/Bolsa_V1/commits/dba3d4f8/check-runs --paginate | Group conclusions
  27 success · 1 skipped
gh api repos/jvelasca/Bolsa_V1/commits/dba3d4f8/status
  {"state":"pending","total":0}
```

Los **28 *check-runs*** son `success` (27) + `skipped` (1, el E2E integrado **opt-in** que el
`Release tag CI` omite a propósito) ⇒ **cero rojos y cero pendientes en Actions**. El
`{"state":"pending","total":0}` viene de la **Status API** (el mecanismo *legacy* que publica
estados por commit), no de Actions: con **0** statuses publicados, GitHub la deja en `pending`
eternamente. Es decir, el commit del tag está **verificado**: la `pending` que se ve en la UI no
es un job sin terminar, es un contador distinto que nadie alimenta.

---

## 8. Freeze (no tocar sin motivo)

- `AUTO_ENGINE_SIM_V2=0` ⇒ sigue comportándose como `v2.39.x`; el gobernador y su evidencia ⇒ **byte a
  byte iguales**, `"bump"` conservado, `exit 0`.
- La tabla `decision_journal_entries` y su índice `decision_journal_entries_decision_id_idx` ⇒ **no** se
  tocan (sin migración; Alembic head sigue en `044_auto_cycle_trace`).
- `v2.50-beta` y anteriores ⇒ **no** se mueven (sus sellos siguen siendo auditables con lo que
  declararon); la **enmienda** al `33/33` se escribe en `docs/`, no reescribe el tag.
- `RiskAllocator` / `portfolio_decision_engine.py` ⇒ **no** se tocan.
- La política de planes ya emitidos (`auto9-v1` y anteriores) ⇒ **no** se reescribe.
- Sin SHORT. Sin migración. Sin backfill.
