# Plan `AUTO-11` — Estado Adaptive durable y recuperación — `V2.52` / `1.77.0-beta`

**Estado:** cerrado (pasos 1–6 **cerrados** y verificados) · **Fecha:** 2026-09-23 · **Fase anterior:**
`V2.51` / `AUTO-10` (sellada: tag `v2.51-beta` → `dba3d4f8`, `Release tag CI` `35787648126` **GREEN**).

**Decisiones ratificadas por el propietario (2026-09-23):**

1. **Cooldown durable hoy, por el journal** — se **deriva** del journal ya existente
   (`adaptive_recommendation`), **sin migración**: Alembic head sigue en `044_auto_cycle_trace`. La
   tabla de estado dedicada queda para más adelante, si el volumen lo pide.
2. **Alcance `AUTO-11` core** — durabilidad del cooldown + recomendación Adaptive durable +
   recuperación tras crash + reconciliación del journal. `confidence` y la ventana
   recent/long/decay quedan para `AUTO-12`/`AUTO-13`.
3. **Higiene incluida en la misma fase** — los tres hallazgos de la auditoría de `v2.51-beta`
   entran aquí (duplicados vs filas de más en el lector de régimen, orden robusto de `created_at`
   en `cycle_risk`, y el régimen releído por ciclo en el worker).

---

## 0. El hueco exacto que cierra esta fase

`AUTO-8`/`AUTO-8.1`/`AUTO-9` dejaron el **cooldown** (la pausa mínima de `min_pause_cycles`) vivo
en una lista del proceso: `self._v2_adaptive_paused_cycles` en
`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`. Su semántica es correcta
(hysteresis + pausa mínima, ya probada), pero su **memoria** no sobrevive al proceso. Consecuencia
medida en la auditoría de `v2.51-beta`: un reinicio **levanta una pausa antes de su ventana
mínima**, y la evidencia de que hubo una decisión Adaptive se pierde. Es el mismo defecto que
`AUTO-10` cerró para el régimen, un piso más arriba.

| Pieza | Ancla | Estado antes de esta fase |
| --- | --- | --- |
| Estado del cooldown | `self._v2_adaptive_paused_cycles` | existe, **en memoria**: se pierde al reiniciar |
| Plan Adaptive | `_v2_build_adaptive_plan` (`build_adaptive_plan`) | existe, recomendador read-only con multiplicador en `[0, 1]` |
| Evidencia de la recomendación | — | **no se publicaba**: no había fila durable que dijera con qué contador se decidió |
| Journal durable del spine | `decision_journal_entries` (ADR-029 F1) | existe, con índice por `decision_id` y `event_type`; ya lo usan `AUTO-4`, `AUTO-10` |
| Reconciliación ciclo ↔ régimen | — | **no existía**: un `RESERVATION COMMITTED → CRASH → NO JOURNAL` no se detectaba |
| Orden de `created_at` en `cycle_risk` | `_entry_candidates` | ordenaba **texto** (funciona con ISO fijo, no está garantizado) |
| `duplicates` en el lector de régimen | `CycleRegimeReading` | contaba **todas** las filas de más, incluidas las no confirmantes |

## 1. Invariante que instala `AUTO-11`

> **El estado Adaptive, o es durable, o se declara.** El cooldown no vive en la lista del proceso:
> se **reconstruye** del journal durable al arrancar, se **publica** la evidencia de cada
> recomendación (con el contador que **entró** a decidir, no el posterior) y, si la historia no
> alcanza o no se puede leer, el contador arranca **vacío y declarado** — nunca se finge «no hay
> pausas».

Y el corolario de autoridad, que **no** cambia:

> Adaptive **sigue siendo recomendador read-only**. Lo único que cambia es **dónde vive su
> memoria**: el journal durable en vez de la lista del proceso.

## 2. Diseño (lo ratificado, con su porqué)

1. **Cooldown derivado del journal, sin migración.** La evidencia que faltaba es la que hace falta
   para reconstruir: cada evaluación Adaptive publica una fila `adaptive_recommendation` con el
   `pausedCycles` que **entró** a la decisión. El estado se **deriva** recorriendo esas filas
   **nuevas→viejas** (como las sirve `list_entries`) y contando la **racha trailing** de
   evaluaciones pausadas por versión de política.
2. **Primero el dinero, después la traza.** El orden replica el precedente de `AUTO-10`: la
   recomendación se persiste **después** de que el motor determinista la consumió y después de
   commitear la reserva. Así el journal **nunca** registra una recomendación que no llegó a
   aplicarse — y un crash antes del sink deja, como mucho, una evaluación sin evidencia, que el
   relector declara como hueco (`insufficient_history`).
3. **Contador saturado, no exacto.** `rebuild_paused_cycles` satura en `min_pause_cycles + 1`: el
   plan solo necesita saber «ya cumplió su ventana mínima», no el número exacto. Saturar mantiene
   la reconstrucción **independiente del volumen** de historia retenida.
4. **Continuidad de política, declarada.** Si la política en curso cambió (`auto9-v1` → otra), el
   contador **se conserva** (no se resetea: resetear es justo el bug) y desde el siguiente turno
   mandan los umbrales nuevos; la mezcla se **declara** (`policy_version_mismatch`) en vez de
   reescribir la historia.
5. **Seam inyectable, no acoplamiento.** El worker recibe `adaptive_sink` y `adaptive_reader` por
   constructor, exactamente como `cycle_regime_sink`/`cycle_regime_reader`: inyectables en tests y
   `None` en el camino hermético. Con el flag Adaptive **OFF**, cero I/O y comportamiento
   byte-idéntico.
6. **Fail-open declarado.** El sink commitea él mismo y hace `rollback` ante fallo (sin el
   `rollback`, la sesión envenenada tumbaría el compromiso de capital del mismo turno). Una
   escritura rota deja el turno intacto y el fallo lo **declara** el worker: la observabilidad no
   puede tumbar el dinero.

## 3. Pasos, con su gate

| # | Paso | Gate |
| --- | --- | --- |
| 1 | **Contrato puro** `auto_adaptive_journal.py`: `AUTO_ADAPTIVE_RECOMMENDATION_EVENT = "adaptive_recommendation"`, `adaptive_recommendation_decision_id(account, asOf)` determinista (`dec-adap-<hash(account, asOf)>`) y `build_adaptive_recommendation_entry(...)` con `payload` estable (`asOf`, `policyVersion`, `regime`, `rotation`, `allocation`, `healthByStrategy`, `pausedCycles`) | sin `plan` ⇒ `None` (no-op declarado, nunca fila vacía); dos cuentas o dos turnos ⇒ identidades distintas; régimen ausente ⇒ **declarado**, nunca inventado; el contador publicado es el que **entró** a decidir |
| 2 | **Recuperación pura** `auto_adaptive_recovery.py`: `AdaptiveStateReading` + `rebuild_paused_cycles(rows, *, min_pause_cycles, ...)` | racha trailing por versión (corta en la primera evaluación **activa** o cuando la versión desaparece del plan); saturación en `min_pause_cycles + 1`; `insufficient_history` si hay menos filas que la ventana; `read_ok=False` ⇒ contador **vacío** y hueco declarado; invariante al orden de entrada; dedupe de un reintento del sink |
| 3 | **Reconciliación** `auto_cycle_reconciliation.py` + `list_recent_with_cycle` en `reservation_store` (Protocol + `InMemory` + `Postgres`) | ciclo con reserva durable y **sin** traza de régimen confirmada ⇒ declarado; traza **sin** reserva ⇒ declarada; ciclo **no consultado** ⇒ motivo propio, no un hueco disfrazado |
| 4 | **Higiene** (los tres hallazgos) — ver §3.3 | `duplicates` cuenta **solo** trazas confirmantes de más y `extra_rows` todas las filas de más; `created_at` se ordena por **instante** y el no-parseable se declara; el régimen del turno se lee **una vez** y todos los ciclos publican el mismo |
| 5 | **Cableado en el worker**: sink/reader por sesión, recuperación **una vez por proceso**, persistencia de la recomendación tras `plan_v2_tick`, reconciliación al arranque | con sink ⇒ una fila por evaluación; sin sink ⇒ turno intacto y hueco declarado; sink que revienta ⇒ turno intacto, fallo declarado; la recuperación siembra el contador **antes** de decidir; flag OFF ⇒ **cero** lecturas |
| 6 | **Verificación y sello**: `ruff` + `mypy` + `import-linter` + suites (delta **simétrico**), mutaciones `M42…M59`, docs (`PROJECT_STATE`, `CHANGELOG`, índice, pack, relevo), bump `1.77.0-beta`, tag `v2.52-beta` | árbol limpio y CI verde |

### 3.1 El contrato puro del paso 1

`build_adaptive_recommendation_entry(...)` proyecta el `AdaptivePlan` **tal cual se decidió**, sin
recalcular nada y sin adornarlo:

- **`decision_id` determinista por turno** — `dec-adap-<hash(account, asOf)>`. Un reintento del
  mismo turno **no** duplica evidencia; y como la cuenta entra en la clave, dos cuentas del mismo
  instante no colisionan.
- **Payload estable**: `event`, `asOf`, `policyVersion`, `regime`, `rotation` (`paused` +
  `byStrategy[{strategyVersion, active, reason}]`), `allocation` (`riskMultipliers` +
  `evidenceAxis`, tomados de `AdaptivePlan.as_dict()`) y `healthByStrategy` (vía
  `AdaptivePlan.evidence_for`).
- **`pausedCycles`**: el contador que **entró** a decidir. Publicar el posterior sería publicar un
  estado que el plan no consumió — la evidencia dejaría de explicar la decisión.
- **Lo no medido se declara, no se disfraza**: un régimen ausente viaja como ausencia declarada
  (nunca un `UNKNOWN` de relleno que parezca valor), y una estrategia sin evidencia no inventa
  multiplicador.

### 3.2 La reconstrucción del paso 2

Semántica exacta, publicada en `AdaptiveStateReading`:

- `paused_cycles` — el contador reconstruido por versión de política; `paused` es la misma lista
  ordenada y `bounded` nombra las versiones cuya racha encontró su corte dentro de la ventana.
- `saturated` — alguna racha tocó el techo (`min_pause_cycles + 1`), así que el valor publicado es
  el **techo**, no el número exacto.
- `policy_versions` — las versiones vistas, de nuevas a viejas; `policy_version_mismatch` cuando la
  versión en curso no es la de las filas (o cuando la historia mezcla versiones y no hay política en
  curso declarada).
- `evaluated` — cuántas evaluaciones Adaptive sostienen la lectura; `collapsed` cuenta las filas
  repetidas del **mismo** turno que el dedupe descartó.
- `unreadable` — filas que no se pudieron interpretar. Una fila ilegible **corta** la racha y se
  cuenta: no se afirma una pausa que no se puede leer.
- `insufficient_history` — la ventana **no** se llenó: la racha es un **suelo**, no el número real.
  `read_ok=False` ⇒ contador **vacío**: «no pude leer» **no** puede leerse como «no hay pausas»
  (y cero filas leídas con `read_ok=True` tampoco es lo mismo que no haber podido leer).

Tres fronteras que se declaran en vez de decidirse en silencio: la racha **corta** en la primera
evaluación activa (una reactivación termina la pausa) y también cuando la versión **desaparece** del
plan de un turno (fuera del plan cuenta a 0 en el mapa vivo), el contador se cuenta en
**evaluaciones Adaptive** (turnos donde el plan se computó), que es la semántica real de
`min_pause_cycles`, y un **reintento** del sink para el mismo turno no infla la racha (dedupe por
identidad de turno). El núcleo `rebuild_paused_cycles(rows, *, min_pause_cycles)` devuelve
`(counts, reasons, collapsed)` y es la pieza que fija el contrato.

### 3.3 Higiene (paso 4) — los tres hallazgos, y por qué importan

1. **Lector de régimen, `duplicates` vs `extra_rows`.** La traza de régimen y la entrada de
   decisión del ciclo **comparten `decision_id` por diseño**, así que en el camino durable el grupo
   tiene dos filas en **todo** ciclo normal. Contar todas como «duplicado» daba un **baseline
   distinto de cero** y ahogaba la única señal que interesa vigilar (una traza escrita dos veces).
   Ahora `duplicates` cuenta **solo trazas confirmantes de más** y `extra_rows` cuenta **todas** las
   filas de más, incluidas las no confirmantes.
2. **Orden de `created_at` en `cycle_risk`.** El denominador de `R` se elegía ordenando `created_at`
   como **texto**: correcto solo mientras el formato fuera ISO de ancho fijo. Ahora se parsea a
   **instante** y se ordena por `(instante, reservation_id)`, con el no-parseable **al final** y
   **declarado** (`CYCLE_RISK_UNDATED_RESERVATION`) — se cierra el invariante implícito sin tocar el
   camino de escritura.
3. **Régimen releído por ciclo en el worker.** `_v2_regime()` y `_v2_instant()` se llamaban **dentro**
   del bucle de reservas, así que un turno con varios ciclos podía publicar regímenes distintos (o
   un régimen distinto del que decidió). Se **hojean fuera** del bucle: todos los ciclos del turno
   publican el régimen que decidió.

**Un cuarto hallazgo, aparecido al medir las mutaciones de esta fase (declarado, no escondido).** Al
correr la matriz filtrada se midió que **`M39` (`sin confirmar`) había dejado de morder**:
`_confirmed_regime` volvía a comprobar el `payload['cycleId']` **después** de que el camino de
lectura ya hubiera filtrado por él (`traces`), así que esa segunda guarda era **inobservable** —la
sonda no podía morderla y **afirmaba una cobertura que no tenía**, exactamente la lección del
`33/33` de `V2.51`—. Cierre: la identidad de la traza pasa a vivir en **un solo sitio**
(`_is_trace`) que usan el recuento de trazas y la lectura del régimen, y `M39` muta esa guarda
**compartida**. `M39` muerde otra vez (3 rojos, incluido `test_a_row_of_another_cycle_is_not_believed`).
También se corrigió la sonda para dos fragmentos derivados por esta fase (`M38`, que ahora aparece
dos veces porque el sink Adaptive es calcado del de la traza del ciclo, y `M40`/`M41`, que citaban
un nombre intermedio que la higiene renombró): los tres se reescribieron contra el código real y
**muerden**.

## 4. Verificación del tramo (paso 6, medida)

**Bloques offline, con la MISMA extracción que CI** (la lista de targets se lee del propio YAML y
se corre sin PostgreSQL, igual que el job, para que los `skipped` sean los mismos):

| Bloque (targets del YAML)                   | Base `v2.51` (CI) | Con la fase (local, sin PG) | Rojos | Delta |
| ------------------------------------------- | ----------------- | --------------------------- | ----- | ----- |
| `quality` (`python-ci.yml`)                 | 2334 / 38 sk.     | **2398 / 38 sk.**           | **0** | **+64** |
| job `python` del tag (`release-tag-ci.yml`) | —                 | **2409 / 35 sk.**           | **0** | **+64** |

El delta es la cuenta exacta de la fase, medida **fichero a fichero** contra `HEAD` (no restando
totales de fases anteriores, cuyos targets y entorno no son los mismos):

- **+13** `test_auto_adaptive_journal.py` (nuevo) · **+16** `test_auto_adaptive_recovery.py`
  (nuevo) · **+10** `test_auto_cycle_reconciliation.py` (nuevo) · **+21**
  `test_auto_v52_auto11_adaptive_state_seam.py` (nuevo) = **+60**.
- **+3** en `test_cycle_risk.py` (`HEAD` **23** → **26**) y **+1** en
  `test_auto_cycle_regime_reader.py` (`HEAD` **17** → **18**) = **+4**.

La coherencia se comprueba sola: los `skipped` del bloque `quality` son **38** en CI y **38** aquí
(la estructura de `--ignore` es idéntica), y `2334 + 64 = 2398`. Los dos ficheros de test
**modificados** se corrieron además en su versión de `HEAD` contra el código de la fase: las **23**
de `test_cycle_risk.py` pasan (**el cambio de orden de `created_at` es retrocompatible**) y en
`test_auto_cycle_regime_reader.py` falla **exactamente 1** —
`test_the_newest_CONFIRMING_row_wins_over_a_newer_window_entry`—, que es la expectativa que la
propia fase actualiza al separar `duplicates` de `extra_rows`: el rojo está **nombrado y
justificado**, no es una regresión oculta.

**Compuertas:** `ruff check packages/py apps/api-python --config pyproject.toml` **limpio**
(`I001` de un import desordenado en la costura, corregido con `--fix` **solo sobre ese fichero**) ·
`mypy` (gate real de CI, `--follow-imports=silent`) **0 errores / 497 ficheros** ·
`import-linter` **4/4** contratos `KEPT`.

**Mutaciones:** sonda `apps/api-python/scripts/v2_44_mutation_audit.py`, **matriz completa**.

- **`59/59` muerden**, **0** `NADA (la mutacion NO se detecta)`, **0** fragmentos ausentes, 59
  restauraciones byte a byte y huella `git status` de los ficheros tocados **idéntica** antes y
  después (`intacto: la sonda no altero el arbol`).
- Las **18 nuevas** (`M42…M59`) muerden con nombre: M42 identidad sin cuenta (1 rojo), M43 fila sin
  plan (1), M44 régimen disfrazado (1), M45 contador normalizado (1), M46 racha sin corte (**7**),
  M47 saturación sin techo (1), M48 dedupe caído (1), M49 historia corta silenciada (3), M50 hueco
  aprobado (4), M51 no preguntado disfrazado (2), M52 trazas contadas como filas (1), M53 filas de
  más silenciadas (4), M54 antigüedad por texto (2), M55 fecha ilegible silenciada (1), M56
  contador de salida (1), M57 recuperación que no siembra (2), M58 reconciliación muda (1), M59 flag
  OFF ignorado (1).
- **Tres fragmentos derivados por la propia fase** (`M38`, `M40`, `M41`) se reescribieron contra el
  código real: `M38` porque el sink Adaptive es calcado del de la traza del ciclo (el fragmento
  pasó a aparecer **dos** veces y la sonda **abortaba**, que es lo correcto) y `M40`/`M41` porque
  citaban un nombre intermedio que la higiene renombró.
- **Y un cuarto, el que importa**: `M39` (`sin confirmar`) había dejado de morder —la guarda de
  `cycleId` quedaba **duplicada e inobservable** en el camino de lectura—. Se midió, se declaró y
  se cerró en §3.3 (identidad de traza en un solo sitio). Ahora muerde **3** rojos, incluido
  `test_a_row_of_another_cycle_is_not_believed`.

## 5. Límites declarados de `AUTO-11` (no silenciosos)

- **La ventana de lectura es finita.** La reconstrucción lee las últimas `N` evaluaciones
  (`ADAPTIVE_STATE_WINDOW_DEFAULT`). Con menos filas que la ventana, `insufficient_history` está
  **declarado**: la racha es un suelo, no una promesa.
- **`capped` no es el número exacto.** El contador se satura en `min_pause_cycles + 1`; el plan no
  necesita más, y la lectura se lo dice al consumidor.
- **El pasado no se reescribe.** Si el journal no tiene evidencia de una pausa (porque se decidió
  antes de esta fase), el contador arranca **vacío y declarado**: `AUTO-11` no inventa historia.
- **`confidence` y la ventana recent/long/decay siguen fuera**: son `AUTO-12`/`AUTO-13`.
- **La UI sigue sin exponer `AUTO-7`…`AUTO-10`** (deuda ya declarada en `V2.50`/`V2.51`); esta fase
  no la toca.
- **`governor.json` sigue sin trackear**: se mantiene tal cual.
- **La tabla de estado dedicada no existe todavía**: el cooldown vive derivado del journal. Si el
  volumen lo pide, la decisión es una tabla (o un índice), no cambiar la semántica del contador.

## 6. Freeze / no tocar

- **No** se reabre el sello de `V2.51` (tag `v2.51-beta` quieto en `dba3d4f8`).
- **No** se toca `auto_adaptive.py` (umbrales, política, `ADAPTIVE_POLICY_VERSION`),
  `portfolio_decision_engine.py`, `RiskAllocator`, el gobernador ni su evidencia.
- **No** se toca la tabla `decision_journal_entries` ni su índice (sin migración; Alembic head sigue
  en `044_auto_cycle_trace`).
- **No** se cambia la autoridad de ejecución: Adaptive sigue recomendando con multiplicador en
  `[0, 1]` y el motor determinista sigue decidiendo.
- **No** se reescribe la política de planes ya emitidos (`auto9-v1` y anteriores).
- Sin SHORT. Sin migración. Sin backfill. Sin UI nueva. Sin `prettier` para `*.md`.
