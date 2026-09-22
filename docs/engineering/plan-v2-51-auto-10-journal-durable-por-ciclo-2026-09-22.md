# Plan `AUTO-10` — Journal durable por ciclo (`cycleId` + `marketRegime`) — `V2.51` / `1.76.0-beta`

**Estado:** cerrado (pasos 1–6 **cerrados** y verificados) · **Fecha:** 2026-09-22 · **Fase anterior:** `V2.50` / `AUTO-9`
(sellada: tag `v2.50-beta` → `e724f19d`, `Release tag CI` `35726585605` **GREEN**).

**Decisiones ratificadas por el usuario (2026-09-22):**

1. **Rótulo** `AUTO-10` / `V2.51` / `1.76.0-beta`.
2. **Punto de escritura:** en la **APERTURA** del ciclo (el régimen que importa para
   `strategy × regime` es el de la decisión, y es el mismo instante en el que ya se crea la reserva de
   entrada: mismo punto, misma transacción lógica).
3. **Sin migración:** `decision_id` **determinista** derivado del `cycle_id` + **dedupe en LECTURA**
   (última gana). Coherente con la promesa de `AUTO-9` de no añadir esquema.

---

## 0. El hueco exacto que cierra esta fase

`AUTO-9` dejó el régimen por ciclo **declarado** (`CycleRisk.regime = None` + nota `regime_not_durable`) y
no inventado: por eso `netExpectancyR` sigue **no medido en producción**. La causa, medida con el código
delante, no es un dato que falte en el esquema: es una **escritura que no existe**.

| Pieza | Ancla | Estado hoy |
| --- | --- | --- |
| Tabla durable del spine | `decision_journal_entries` (ADR-029 F1, `010_decision_journal_entries`) | existe, con índices `account_created`, `decision_id`, `session_id` |
| API de escritura | `SqlAlchemyJournalRepository.append()` (`journal_repository.py:45`: `session.add` + `flush`, **sin** commit) | existe, pero **solo** la usa `api/dependencies.py:517` |
| Régimen por turno | `auto_simulation_worker.py:1299` `_v2_regime()` (override `:1305`, `regime_source` `:1311`) | existe y **ya se usa** en la decisión (`:1584`) |
| Identidad de ciclo | `_v2_cycle_for()` `:2048` (posición abierta → si no, plan del tick) | existe |
| Escritura del régimen | `self._v2_journal.append(entry)` (`:2803`, `:3490`) | **en memoria**: lista del proceso, se pierde al reiniciar |
| Relación `cycleId` ↔ `decision_id` | `auto_v2_entry.py:1744-1768`: mismo `key` ⇒ `dec-<sha256(key)[:12]>` / `cyc-<sha256(key)[:12]>` | **determinista por intercambio de prefijo** |

Mediciones de la sonda de coste (`apps/api-python/scripts/a9_cycle_regime_read_cost_probe.py`, paso 1 de
`AUTO-9`): leer por `decision_id` **derivado** cae en el índice (barato); leer por `payload` obliga a scan
secuencial del JSONB (caro). Y un aviso que esta fase debe respetar: **la forma `cyc-<12 hex>` no prueba
procedencia** (el fallback `uuid4` tiene la misma forma), así que la lectura **confirma** el `cycleId` en
el payload antes de creerse el régimen.

## 1. Invariante que instala `AUTO-10`

> **El régimen por ciclo, o es durable, o se declara.** Ningún consumidor inventa `UNKNOWN`: o lee un
> régimen escrito en el journal durable y confirmado por payload, o el hueco sigue declarado
> (`regime_not_durable`). Es la extensión natural del invariante de `AUTO-9` (*medir o declarar, nunca
> inventar*) al lado de la **escritura**.

## 2. Diseño (lo ratificado, con su porqué)

1. **`decision_id` por intercambio de prefijo.** `cycle_id` es `cyc-<x>`; el `decision_id` que le
   corresponde es `dec-<x>` **con la misma `<x>`**. Vale para los dos casos porque ambas piezas se acuñan
   del mismo `key` (`sha256` cuando hay señal, `uuid4` cuando no). Si el `cycle_id` **no** empieza por
   `cyc-`, no se deriva nada: se escribe con `decision_id` propio y se **declara** que la lectura por
   índice no lo alcanza.
2. **Sin migración.** No se añade índice único ni columna: el dump de la entrada lleva `cycleId` y
   `marketRegime` en el `payload` (JSONB ya existente). Los duplicados de reintento se resuelven en
   **lectura** (gana la confirmación más nueva, ordenado por `created_at`), y se **declaran** (nota medida),
   no se silencian. *Matiz medido en el paso 4*: "la más nueva" se mide **entre las filas que confirman**
   el ciclo, no entre todas las de su `decision_id`, porque la entrada de ventana comparte `decision_id`
   con la traza y es más nueva que ella; contar todas convertiría un ciclo con régimen escrito en hueco.
3. **Escritura en la apertura, fail-closed declarado.** La entrada se emite donde nace el ciclo
   (`_v2_track_entry`, `:3537`) / se crea la reserva de entrada (`:3826`). Si el sink durable falta o
   falla, **el turno no se tumba** (mismo patrón que `_journal_position_event`, `:3501`) pero el fallo
   **no** se convierte en éxito: queda declarado para que el hueco no mienta.
4. **Seam inyectable, no acoplamiento.** El worker recibe un escritor de journal por constructor,
   exactamente como `reservation_store` (`:574`) y `regime_source` (`:562`): inyectable en tests, `None`
   en el camino hermético. El runner con `session_factory` (`:4548`) es quien lo construye.

## 3. Pasos, con su gate

| # | Paso | Gate |
| --- | --- | --- |
| 1 | **Constructor puro** `build_auto_cycle_regime_entry(...)`: deriva `decision_id` por prefijo, arma `payload` con `cycleId` + `marketRegime` + `strategyVersion`, y devuelve `None` (no-op declarado) si falta `cycle_id` | tests de borde: sin `cycle_id` ⇒ `None`; `cycle_id` sin prefijo `cyc-` ⇒ `decision_id` propio y declarado; régimen `None` ⇒ `UNKNOWN` **declarado**, nunca inventado; `payload` estable (golden) |
| 2 | **Puerto de escritura en el worker** en la **apertura** + inyección del seam (y su cableado real en el runner: `build_cycle_regime_sink(session)` sobre la sesión del tick) | test de seam: con sink ⇒ una entrada por ciclo; sin sink ⇒ turno intacto y hueco declarado; sink que revienta ⇒ turno intacto, fallo declarado; y el sink real **commitea** (sin commit la fila moriría al cerrar la sesión) |
| 3 | **Lector**: el productor de `AUTO-9` (`cycle_risk`) recibe `regime_by_cycle` desde el journal durable (por `decision_id` derivado **y** confirmación de `payload['cycleId']`) y el hueco pasa de `regime_not_durable` a `COMPLETE` | sonda de coste con números antes/después (`a9_cycle_regime_read_cost_probe.py`); test de que sin confirmación de payload **no** se cierra el hueco |
| 4 | **Dedupe en lectura** (última gana) + nota declarada por duplicados | test con dos entradas del mismo ciclo: gana la más nueva; la nota dice cuántas |
| 5 | **Mutaciones** `M34–M41` sobre constructor, puerto y lector (`v2_44_mutation_audit.py`) | todas **muerden** con el árbol intacto |
| 6 | **Verificación y sello**: `ruff` + `mypy` + `import-linter` + suites (delta **simétrico**), docs (`PROJECT_STATE`, `CHANGELOG`, índice, pack, relevo), bump `1.76.0-beta`, tag `v2.51-beta` | árbol limpio y CI verde |

### 3.1 Medición del paso 3 (números delante, sin supuestos)

Sonda `a9_cycle_regime_read_cost_probe.py` sobre la base real (PostgreSQL 16.14, `bolsa_v1`, 1348
filas en `decision_journal_entries`, 56 buffers, 3 pasadas por consulta):

| Vía | Plan | Coste medido |
| --- | --- | --- |
| (a) por `decision_id` derivado, **UN** ciclo | Bitmap Index Scan sobre `decision_journal_entries_decision_id_idx` | 0,028–0,042 ms |
| (b) por `payload->>'cycleId'`, un ciclo | Seq Scan (1347 filas descartadas por filtro) | 0,124–0,146 ms |
| (c) **la consulta del lector** (15 ciclos por tanda, `decision_id = ANY(...)` + `event_type`) | **Seq Scan** | 0,082–0,086 ms |

Lo que esto corrige, y se declara en el código (`journal_repository.list_by_decision_ids` y
`auto_cycle_regime_reader`): con **un** id el índice sí se usa (y es ~4× más barato que el
recorrido), pero con una **tanda** sobre una tabla pequeña el planner prefiere recorrerla —le sale
más barato que N sondas de índice— y el coste sigue siendo sub-milisegundo. El supuesto "la lectura
por `decision_id` derivado cae en el índice (barato)" es cierto **por id**, no por tanda a este
volumen. A escala **no está medido**: si el spine crece hasta hacer caro el recorrido, la decisión
es un índice parcial o de expresión (familia de la `045`), nunca cambiar la identidad del ciclo.

El circuito completo (escribir → sobrevivir → leer) se certifica además con PG real en
`test_auto_v2_durable_pg.py::test_auto_cycle_regime_trace_is_durable_and_readable_from_another_session`:
la traza se lee desde **otra sesión** por el `decision_id` derivado, el régimen devuelto es el del
turno que DECIDIÓ (`BULL_TREND`) y la identidad `cyc-<x>` ↔ `dec-<x>` se comprueba sobre datos
reales. Y se verificó que el test **muerde**: desconectar el sink en `run_tick` lo pone rojo.

### 3.2 Dedupe declarado (paso 4)

Semántica exacta, publicada en ``CycleRegimeReading``: ``duplicates`` cuenta **por ciclo las filas de
más** que la lectura descartó al quedarse con la traza ganadora, y ``collapsed_rows`` es su suma. Dos
fronteras que se declaran en vez de decidirse en silencio:

- **Gana la confirmación más nueva**, no la fila más nueva: el mismo ``decision_id`` lo comparte la
  entrada de ventana del ciclo, que es más nueva que su traza. Deduplicar por "la primera que llegue"
  sin mirar el evento convertiría un ciclo con régimen escrito en hueco.
- **Un ciclo sin confirmación no cuenta como duplicado**: sin ganadora no hay nada colapsado, y
  llamarlo duplicado confundiría el motivo del hueco (``unconfirmed``).

El worker lo declara sin gritar: con huecos va dentro del ``warning``; solo con duplicados, un
``info`` (``auto_sim v2 adaptive cycle regime duplicates``). Un reintento del tick es normal; un
duplicado anómalo, no: por eso se ve.

### 3.3 Mutaciones del tramo (paso 5) — y un hallazgo que obliga a corregir la matriz

**Las ocho nuevas** se verificaron primero **filtradas** (`M34…M41`) para no arrastrar las 33 anteriores,
y las ocho muerden con **nombre**: M34 `identidad derivada` (4 rojos), M35 `payload sin cycleId` (3), M36
`régimen disfrazado` (2), M37 `sink sin usar` (5), M38 `sink sin commit` (2), M39 `sin confirmar` (3), M40
`dedupe por llegada` (1, justo la frontera de confirmación), M41 `duplicado silencioso` (3).

**El hallazgo.** Al correr la matriz **completa**, cuatro mutaciones ya **no encontraban su fragmento** y
la sonda lo decía en voz baja y **seguía**:

| Etiqueta | Estado | Causa medida |
| --- | --- | --- |
| `M25` (hysteresis de régimen) | **muerta ya en `HEAD` (`df2002e7`)** | `ruff format` colapsó el `return (...)` a una línea; el fragmento era multilínea |
| `M26` (muestra decisoria) | **muerta ya en `HEAD` (`df2002e7`)** | el `expectancy_ok = (` se reformateó a una línea larga |
| `M33` (worker sin denominador) | **muerta ya en `HEAD` (`df2002e7`)** | la llamada se partió en tres líneas tras escribir la mutación |
| `M30` (hueco silencioso) | **la rompió este tramo** (paso 3) | el retorno pasó a pasar `regime_source_durable` y el fragmento era el viejo |

Consecuencia declarada, sin adornos: la afirmación **`33/33 muerden`** que sellaron `V2.50` (plan,
audit-pack, relevo y `PROJECT_STATE`) **no era reproducible al nivel de "todos los fragmentos aplican"**:
tres de esas etiquetas llevaban desde `df2002e7` sin medir nada. La matriz no mentía en lo que midió, pero
**afirmaba cobertura que no tenía**, y la sonda no lo impedía.

**El cierre, en dos partes.** (1) Los cuatro fragmentos se han reescrito contra el código real y **las
cuatro muerden** otra vez (M25: 1 rojo en `test_rotation_regime_hysteresis_dead_zone`; M26: 1; M30: 4;
M33: 3). (2) La sonda **ya no puede perder cobertura en silencio**: un fragmento ausente pasa a ser un
**fallo de la sonda** (`!! mutaciones SIN medir (fragmento ausente)`, salida distinta de 0), con el mismo
criterio que ya abortaba cuando el fragmento aparecía más de una vez. La run completa imprime ahora
`medidas: N/N (ninguna se quedo sin fragmento)`.

**Medición final del tramo: `41/41` muerden**, 0 `NADA (la mutacion NO se detecta)`, 41 restauraciones
byte a byte y huella `git status` **idéntica** antes y después (`intacto: la sonda no altero el arbol`).

## 4. Verificación del tramo (paso 6, medida)

**Bloques offline, con la MISMA extracción antes y después** (base medida apartando el trabajo con
`git stash -u` para correr la batería en `HEAD`, no restando contra extracciones antiguas):

| Bloque (targets del YAML)                       | Base `HEAD` | Con la fase | Rojos | Delta |
| ----------------------------------------------- | ----------- | ----------- | ----- | ----- |
| `quality` (`python-ci.yml`)                     | 2321        | **2368**    | **0** | **+47** |
| job `python` del tag (`release-tag-ci.yml`)     | 2329        | **2376**    | **0** | **+47** |

El delta es la cuenta exacta de la fase: **+10** contrato puro (`test_auto_cycle_journal.py`) **+17**
lector (`test_auto_cycle_regime_reader.py`) **+8** costura de escritura **+10** costura de lectura **+2**
`test_cycle_risk.py`. La durabilidad real suma **+1** en el job `durable-pg`.

**Un rojo local declarado, no silenciado.** La primera corrida de `quality` marcó
`test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once` (PG **sin
`--ignore`** en el YAML del job `python`, luego en CI se **salta** por no haber PostgreSQL, pero en local
corre contra la base de desarrollo). Aislado pasa (**1 passed**) y la batería re-ejecutada da
**2368/2368**: es contaminación de orden de la base local, no un cambio de esta fase. La base `HEAD` se
midió con el mismo script y el mismo estado, así que el **delta no se ve afectado**.

**Compuertas:** `ruff check packages/py apps/api-python --config pyproject.toml` **limpio** · `mypy`
**0 errores / 494 ficheros** · `import-linter` **4/4** · PG (`auto_v2_durable_pg` +
`portfolio_reservation_pg` + `auto_v2_lifecycle_pg`, con `AUTO_V2_DURABLE_PG_REQUIRED=1`) **14 passed**.

**Mutaciones:** `41/41` (§3.3), 0 no detectadas, árbol intacto.

## 5. Límites declarados de `AUTO-10` (no silenciosos)

- **Solo ciclos del worker `AUTO`**: ciclos históricos ya cerrados sin entrada durable siguen declarando
  su hueco; `AUTO-10` **no** reescribe el pasado.
- **`netExpectancyR` sigue necesitando su propia cadena**: que el régimen sea durable cierra el eje
  `strategy × regime`, pero la expectativa neta en R depende además de que existan ciclos medidos con
  coste; `AUTO-10` no promete que el número aparezca, promete que el **insumo** deja de faltar.
- **La UI sigue sin exponer `AUTO-7`/`AUTO-8`/`AUTO-9`** (deuda ya declarada en `V2.50`); esta fase no
  la toca.
- **`governor.json` sigue sin trackear**: se mantiene tal cual.
- **Coste del lector a escala: no medido.** A este volumen la tanda del lector recorre la tabla y
  cuesta <0,1 ms (ver §3.1); el punto en el que el planner cambiaría a índice no está medido, y
  `AUTO-10` no lo afirma. Si el spine crece, la decisión es un índice (parcial o de expresión),
  nunca cambiar la identidad del ciclo.

## 6. Freeze / no tocar

- **No** se reabre el sello de `V2.50` (tag `v2.50-beta` quieto en `e724f19d`).
- **No** se toca `prettier` para `*.md` (decisión del tramo de tooling: `*.md` fuera de `prettier` +
  `tools/fix_md_spacing.py` como reparador determinista).
- **No** se cambia el contrato de `expectancy_r` / `net_expectancy_r` ni la política `auto9-v1`: si el
  contrato de evidencia cambia, sube `adaptivePolicyVersion` (sería `auto10-v1`) y eso es una decisión
  aparte, no un efecto colateral.
