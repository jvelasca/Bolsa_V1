# Audit-pack `AUTO-11` Estado Adaptive durable y recuperación — `1.77.0-beta` (2026-09-23)

**Fase:** `V2.52` · **Rótulo:** `AUTO-11` · **Bump:** `1.76.0-beta` → **`1.77.0-beta`** · **Fase
anterior:** `V2.51` / `AUTO-10` (tag `v2.51-beta` → `dba3d4f8`, `Release tag CI` `35787648126`
**GREEN**).

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI
nueva, sin cambio de contrato de API ni de DTO. El gobernador y su evidencia quedan **intactos**.
Adaptive **sigue siendo recomendador read-only**: lo único que cambia es **dónde vive su memoria**.

---

## 0. Resumen: qué instala esta pasada

`AUTO-8`/`AUTO-8.1`/`AUTO-9` dejaron el **cooldown** (`min_pause_cycles`) vivo en una lista del
proceso (`self._v2_adaptive_paused_cycles`). La semántica era correcta, pero la memoria no
sobrevivía al proceso: **un reinicio levantaba una pausa antes de su ventana mínima** (P1 de la
auditoría de `v2.51-beta`) y la evidencia de cada evaluación Adaptive se perdía al volver del
turno. Esta pasada cierra las dos cosas sin tocar el esquema:

1. **La recomendación Adaptive se publica durable** (`adaptive_recommendation`), con el contador de
   pausa que **entró** a decidir.
2. **El cooldown se reconstruye del journal** al arrancar (`rebuild_paused_cycles`: racha trailing
   por versión, saturada, con política en curso declarada).
3. **El rastro de ciclo se reconcilia** al arrancar: capital reservado sin traza de régimen (la
   ventana `RESERVATION COMMITTED → CRASH → NO JOURNAL` que `AUTO-10` aceptó y declaró, pero nadie
   comprobaba) y el caso inverso.
4. **Tres hallazgos de higiene** de la auditoría de `v2.51-beta`, más **un cuarto hallazgo de
   cobertura** que apareció al medir la propia sonda de mutaciones (§5).

Superficie nueva (`packages/py/application/src/bolsa_application/`):
`auto_adaptive_journal.py`, `auto_adaptive_recovery.py`, `auto_cycle_reconciliation.py`. Superficie
tocada: `reservation_store.py` (método aditivo `list_recent_with_cycle`), `auto_cycle_regime_reader.py`
y `cycle_risk.py` (higiene), y el worker (`auto_simulation_worker.py`).

## 1. El invariante: **el estado Adaptive, o es durable, o se declara**

> El cooldown no vive en la lista del proceso: se **reconstruye** del journal durable al arrancar,
> se **publica** la evidencia de cada recomendación (con el contador que entró a decidir) y, si la
> historia no alcanza o no se puede leer, el contador arranca **vacío y declarado** — nunca se finge
> «no hay pausas».

Es la extensión del invariante de `AUTO-9`/`AUTO-10` (*medir o declarar, nunca inventar*) al
estado **de cartera**: no a un dato de mercado, sino al recuerdo de una decisión propia.

**El orden replica el precedente de `AUTO-10`**: primero el dinero, después la traza. La
recomendación se persiste **después** de que el motor determinista la consumió y después de
commitear la reserva (`await self._v2_persist_tick_reservations(plan)` →
`await self._v2_journal_adaptive_recommendation(adaptive)`). Así el journal **nunca** registra una
recomendación que no llegó a aplicarse; y un crash **antes** del sink deja, como mucho, una
evaluación sin evidencia, que la lectura declara como hueco.

## 2. La reconstrucción del cooldown, y sus cuatro límites declarados

`auto_adaptive_recovery.py` es puro sobre las filas y **no escribe nada**. Reproduce la regla del
proceso vivo (`_v2_next_paused_cycles`): una versión que no está pausada en un turno **desaparece**
del mapa (cuenta a 0) y una que sí lo está suma uno. Recorrer las evaluaciones de **nueva a vieja**
y contar la **racha inicial** por versión reproduce eso exactamente.

**Saturación declarada.** El valor publicado se limita a `min_pause_cycles + 1`. No es pérdida: el
único consumo del contador es `count < min_pause_cycles` y `count <= 0` (las ramas de cooldown e
hysteresis), así que cualquier valor por encima del umbral significa lo mismo; y saturar evita que
el número crezca sin límite en la historia. La lectura lo declara (`bounded`, y `saturated` como
propiedad).

**Una evaluación por TURNO.** La identidad de la recomendación es determinista por turno
(`dec-adap-<hash>`), así que dos filas con el mismo `decision_id` son **la misma evaluación escrita
dos veces** (reintento del sink), no dos turnos. Se colapsan antes de contar (`collapsed` lo
declara): contarlas dos veces inflaría la racha y **alargaría** el cooldown, afirmando un turno que
no ocurrió.

**Cuatro huecos declarados y distintos** (la disciplina de `cycle_risk`/`AUTO-10`):

| Declarado | Significa | Por qué no puede ser un `0` |
| --- | --- | --- |
| `read_ok = False` | la fuente durable **no se pudo leer** | `0` y «no leí» llegarían con la misma forma: el contador se reiniciaría por la puerta de atrás |
| `insufficient_history` | se leyeron **menos filas que la ventana** | la racha es un **suelo**, no el número real |
| `unreadable` | filas sin el contrato de rotación usable | una pausa que no se puede leer **no se afirma**; la fila corta la racha y se cuenta |
| `policy_version_mismatch` | la historia mezcla versiones de política | la historia **no se reescribe**: se declara la mezcla |

**Continuidad de política.** El contador **se conserva** a través de un cambio de `policyVersion`
—resetearlo sería exactamente el bug que esta fase cierra— y desde el turno siguiente mandan los
umbrales de la política en curso. La política entra al lector **por parámetro**
(`build_adaptive_state_reader(session, *, policy=...)`), no por copia: derivarla de una segunda
construcción permitiría que plan y lector divergieran en silencio.

**Invariante al orden.** `_ordered` ordena por **instante** de forma defensiva (el puerto real ya
sirve `created_at DESC`), con el instante ilegible **al final** —nunca se le supone «lo más nuevo»—
y desempate por identidad. La lectura es la misma con las filas en cualquier orden.

## 3. La identidad del turno y el payload durable

`auto_adaptive_journal.py` fija el contrato de la fila (`adaptive_recommendation`). Cuatro reglas
duras, cada una con test:

- **Sin plan no hay entrada** (`None`): un no-op que el llamante declara, nunca una fila con un plan
  vacío —una fila vacía afirmaría «Adaptive evaluó y no recomendó nada», que es un hecho distinto de
  «Adaptive no evaluó»—.
- **La identidad es del turno**: `dec-adap-<sha256(cuenta \x1f asOf)[:12]>`. Un reintento del mismo
  turno **no duplica** evidencia; dos cuentas del mismo instante no colisionan; y **sin sello de
  turno** se conserva el fallback aleatorio (una identidad **única**, nunca una compartida por
  accidente).
- **Aislamiento de `AUTO-10`**: `cycle_decision_id()` devuelve `None` sobre una identidad
  `dec-adap-*`, así que ninguna de las dos derivaciones alcanza la historia de la otra. Son dos
  lectores con contratos distintos y no pueden compartir fila.
- **Lo no medido se declara**: `regime = None` viaja como `None` (nunca un `UNKNOWN` de relleno) y
  `healthByStrategy` va vacío cuando ninguna estrategia trae fila. El payload **se proyecta** con
  lista blanca de claves (`rotation` → `paused`/`byStrategy`; `allocation` →
  `riskMultipliers`/`evidenceAxis`): una clave nueva del plan **no** puede colarse en la historia
  sin decidirlo aquí. `readOnly: true` viaja en la fila como constancia durable del reparto de
  autoridad.

`pausedCycles` publica el contador que **entró** a decidir, normalizado (`> 0`, sin `bool`s, sin
claves en blanco, ordenado). El worker lo copia **antes** de `build_adaptive_plan`
(`_v2_adaptive_paused_cycles_entered`) precisamente para que la evidencia explique la decisión y no
el estado posterior.

## 4. Reconciliación del rastro de ciclo

`auto_cycle_reconciliation.py` es read-only y puro sobre lo que le pasan. Cruza los ciclos con
**reserva durable** (`list_recent_with_cycle`, por la columna `cycle_id` con índice desde `044`)
con los que el lector de `AUTO-10` **confirma**, y declara **cuatro desajustes que no son el mismo
hecho**:

| Motivo | Qué pasó | Por qué tiene nombre propio |
| --- | --- | --- |
| `missing` | hay capital y **no** hay régimen confirmado | es el hueco del crash; `missing_reasons` dice si la fila **no estaba** (`regime_absent`) o **no se creyó** (`regime_unconfirmed`) |
| `unrequested` | hay capital y **ni se preguntó** por ese ciclo | es un hueco **operativo** (la ventana no lo cubría), no un journal roto |
| `not_derivable` | hay capital y el `cycle_id` no es alcanzable por el índice | la ausencia es **estructural**, no un fallo de escritura |
| `orphan` | hay traza confirmada y **ninguna** reserva | o sobra la traza o falta la reserva; ninguna de las dos es normal |

Los cuatro se publican por nombre en `as_dict()` y el worker los registra al arrancar (`warning` con
recuento e ids; `info` si el cruce está limpio). Fail-open declarado: sin libro de reservas o sin
lector no hay nada que cruzar (camino hermético, **sin log**), y una lectura rota se registra sin
afirmar que todo está limpio.

## 5. Higiene, y un hallazgo de cobertura que obliga a cambiar el código

**Los tres hallazgos de la auditoría de `v2.51-beta`:**

1. **`duplicates` vs `extra_rows` en el lector de régimen.** La traza de régimen y la entrada de
   decisión del ciclo **comparten `decision_id` por diseño**, así que en el camino durable el grupo
   tiene dos filas en **todo** ciclo normal. Contar todas como «duplicado» daba un **baseline
   distinto de cero** y ahogaba la única señal que interesa vigilar. Ahora `duplicates` cuenta
   **solo trazas confirmantes de más** (con `collapsed_rows` como suma) y `extra_rows` cuenta
   **todas** las filas de más, incluidas las no confirmantes (`discarded_rows` como suma).
2. **Orden de `created_at` en `cycle_risk`.** El denominador de `R` se elegía ordenando `created_at`
   **como texto**: correcto solo mientras todo origen usara el mismo ancho fijo —lo garantiza el
   repositorio, no el contrato—. Ahora se parsea a **instante** y se ordena por `(instante,
   reservation_id)`, con el no-parseable **al final** y **declarado**
   (`CYCLE_RISK_UNDATED_RESERVATION`, y solo cuando hubo que **desempatar**: con una sola candidata
   la fecha de la otra no cambia nada, y una nota que no cambia nada es ruido). El camino de
   escritura no se toca.
3. **Régimen releído por ciclo en el worker.** `_v2_regime()` y `_v2_instant()` se llamaban **dentro**
   del bucle de reservas de `_v2_journal_cycle_regime`, así que un turno con varios ciclos podía
   publicar regímenes distintos —o uno distinto del que decidió—. Se **hojean fuera** del bucle:
   todos los ciclos del turno publican el régimen que decidió y el mismo `asOf`.

**El cuarto hallazgo, y es el interesante: la sonda de mutaciones puede mentir por una guarda
duplicada.** Al correr la matriz filtrada se midió que **`M39` (`sin confirmar`) había dejado de
morder**. La causa no era el test: al separar `duplicates` de `extra_rows`, el camino de lectura
pasó a filtrar las filas por identidad (`traces`) **antes** de pedirles el régimen, así que la
comprobación de `payload['cycleId']` que `_confirmed_regime` hacía **después** era **inobservable**:
duplicada, inalcanzable, y la sonda no podía morderla. Es exactamente la lección del `33/33` de
`V2.51`, en su forma más pura: la matriz no mentía en lo que medía, pero **afirmaba cobertura que no
tenía**, y esta vez lo dijo en voz alta.

**El cierre.** La identidad de la traza pasa a vivir en **un solo sitio** —`_is_trace`, que exige el
`event_type` de la traza **y** el `cycleId` exacto— y lo usan las dos cosas que antes lo comprobaban
por separado: el recuento de trazas (`duplicates`) y la lectura del régimen (`_confirmed_regime`).
`M39` muta ahora esa guarda **compartida** y vuelve a morder (**3** rojos, incluido
`test_a_row_of_another_cycle_is_not_believed`). El código queda con **una** puerta de identidad, que
es además la lectura honesta: una fila es traza de **este** ciclo o no lo es, y "qué régimen aporta"
es una pregunta distinta que se hace después.

## 6. La matriz de mutaciones

Sonda `apps/api-python/scripts/v2_44_mutation_audit.py` (**59** mutaciones). Corrida **completa**, sin
filtro:

```text
=== huella del arbol ===
  intacto: la sonda no altero el arbol
  medidas: 59/59 (ninguna se quedo sin fragmento)
```

- **`59/59` muerden**, **0** `NADA (la mutacion NO se detecta)`, 59 restauraciones byte a byte,
  huella `git status` de los ficheros tocados **idéntica** antes y después.
- **Las 18 nuevas (`M42…M59`)** y su recuento de rojos:

| Etiqueta | Qué rompe | Rojos |
| --- | --- | --- |
| `M42` | identidad sin cuenta (dos cuentas colisionan) | 1 |
| `M43` | sin plan se escribe una fila vacía | 1 |
| `M44` | el régimen ausente se publica `UNKNOWN` | 1 |
| `M45` | un `0` entra al mapa de pausas como pausa | 1 |
| `M46` | la versión sigue contando después de reactivarse | **7** |
| `M47` | el contador deja de recortarse al umbral | 1 |
| `M48` | un reintento del sink cuenta dos veces el turno | 1 |
| `M49` | no se declara que la racha es un suelo | 3 |
| `M50` | un ciclo **con** traza se declara además `missing` | 4 |
| `M51` | el ciclo nunca consultado pasa a ser un hueco | 2 |
| `M52` | el duplicado cuenta la entrada de decisión del ciclo | 1 |
| `M53` | la lectura deja de declarar `extra_rows` | 4 |
| `M54` | el denominador de `R` se elige comparando `created_at` como texto | 2 |
| `M55` | el desempate sin fecha legible deja de declararse | 1 |
| `M56` | la evidencia publica el contador **posterior** a decidir | 1 |
| `M57` | el journal se lee y el contador se descarta | 2 |
| `M58` | los huecos del rastro de ciclo se declaran limpios | 1 |
| `M59` | con Adaptive apagado el arranque paga la lectura igual | 1 |

- **Tres fragmentos derivados por la propia fase**, reescritos contra el código real: `M38` (el sink
  Adaptive es calcado del de la traza del ciclo, así que el fragmento pasó a aparecer **dos** veces y
  la sonda **abortaba** —que es lo correcto: la sonda prefiere abortar a mentir—), `M40` y `M41`
  (citaban un nombre intermedio que la higiene renombró). Los tres **muerden** otra vez.

## 7. Evidencia medida

**Bloques offline, con la MISMA extracción que CI** (la lista de targets se lee del propio YAML y se
corre sin PostgreSQL, igual que el job, para que los `skipped` sean los mismos):

| Bloque (targets del YAML)                   | Base `v2.51` (CI) | Con la fase (local, sin PG) | Rojos | Delta |
| ------------------------------------------- | ----------------- | --------------------------- | ----- | ----- |
| `quality` (`python-ci.yml`)                 | 2334 / 38 sk.     | **2398 / 38 sk.**           | **0** | **+64** |
| job `python` del tag (`release-tag-ci.yml`) | —                 | **2409 / 35 sk.**           | **0** | **+64** |

El delta es la cuenta exacta de la fase, medida **fichero a fichero** contra `HEAD`:

- **+13** `test_auto_adaptive_journal.py` (nuevo) · **+16** `test_auto_adaptive_recovery.py`
  (nuevo) · **+10** `test_auto_cycle_reconciliation.py` (nuevo) · **+21**
  `test_auto_v52_auto11_adaptive_state_seam.py` (nuevo) = **+60**.
- **+3** en `test_cycle_risk.py` (`HEAD` **23** → **26**) y **+1** en
  `test_auto_cycle_regime_reader.py` (`HEAD` **17** → **18**) = **+4**.

La coherencia se comprueba sola: los `skipped` del bloque `quality` son **38** en CI y **38** aquí
(la estructura de `--ignore` es idéntica), y `2334 + 64 = 2398`. Los dos ficheros de test
**modificados** se corrieron además en su versión de `HEAD` contra el código de la fase: las **23**
de `test_cycle_risk.py` pasan (**el orden por instante es retrocompatible**) y en
`test_auto_cycle_regime_reader.py` falla **exactamente 1**
(`test_the_newest_CONFIRMING_row_wins_over_a_newer_window_entry`), que es la expectativa que la
propia fase actualiza al separar `duplicates` de `extra_rows`: el rojo está **nombrado y
justificado**, no es una regresión oculta.

**Registro en CI (simétrico).** Los tres módulos puros nuevos viven en
`packages/py/application/tests`, que **no tiene pase de directorio** en ninguno de los dos jobs, así
que van **explícitos** en `python-ci.yml` (`quality`) y en `release-tag-ci.yml` (job `python`), con
un comentario que declara el porqué. La costura
(`apps/api-python/tests/test_auto_v52_auto11_adaptive_state_seam.py`) entra por el **pase de
directorio** de `apps/api-python/tests`. Se comprobó con la lista leída del YAML que los dos jobs
contienen los mismos tres ficheros nuevos y que la diferencia entre ambos es la estructural de
siempre (el job del tag lista 9 targets más).

**Compuertas:** `ruff check packages/py apps/api-python --config pyproject.toml` **limpio** (`I001`
de un import desordenado en la costura, corregido con `--fix` **solo sobre ese fichero**; `ruff
format` **no** se corre en masa: el repo tiene *drift* de formato respecto a la config y la lección
de `V2.50` sigue vigente) · `mypy` (gate real de CI, `--follow-imports=silent`) **0 errores / 497
ficheros** · `import-linter` **4/4** contratos `KEPT` (`Domain no importa…`, `SDKs LLM…`,
`bolsa_ai no entra en domain`, `analytics y market no se importan entre sí`) · mutaciones
**`59/59`** con el árbol intacto.

## 8. Sello y CI

**Este §8 se escribe antes del tag**, y por eso **no** afirma una CI que todavía no existe: declara
la evidencia local medida (§6–§7) y qué se va a observar. La tabla de runs —con los `workflow runs`
y los `check-runs` del commit del tag— se añade en el **commit de enmienda inmediatamente posterior**
al tag (precedente: el §7 de `v2.51` y la enmienda del sello movido de `v2.50`), porque necesita
runs **reales**.

Lo que el sello debe cumplir, declarado de antemano:

1. **Tag anotado `v2.52-beta`** → commit de **documentos de fase** (este pack, el plan, el relevo y
   el índice), para que los cuatro viajen **dentro** del tag; el commit de **código** va antes.
2. **Push a `main` en fast-forward** y el tag **empujado de uno en uno** (lección de `v2.49`: **no**
   usar `--follow-tags` con tags locales antiguos; más de tres tags en un push **no** disparan los
   workflows de tag).
3. **`Release tag CI` GREEN** con los diez jobs de decisión + `certify`, y el E2E integrado
   **opt-in** omitido como está diseñado.
4. **`quality` con `2398 + k` passed y 0 fallos** (`k` = lo que añada la CI respecto a esta
   extracción local; el `38 skipped` debe cuadrar, porque son las suites PG que ese job ignora por
   diseño).
5. **Sin migración**: Alembic head sigue en `044_auto_cycle_trace`.

## 9. Freeze (no tocar sin motivo)

- `AUTO_ENGINE_SIM_V2=0` ⇒ sigue comportándose como `v2.39.x`; el gobernador y su evidencia ⇒ **byte
  a byte iguales**, `"bump"` conservado, `exit 0`.
- `auto_adaptive.py` (umbrales, política, `ADAPTIVE_POLICY_VERSION`), `portfolio_decision_engine.py`
  y `RiskAllocator` ⇒ **no** se tocan. Adaptive **no** gana autoridad: su multiplicador sigue en
  `[0, 1]` y el motor determinista sigue decidiendo.
- La tabla `decision_journal_entries` y su índice `decision_journal_entries_decision_id_idx` ⇒ **no**
  se tocan (sin migración; sin tabla de estado dedicada).
- La política de planes ya emitidos (`auto9-v1` y anteriores) ⇒ **no** se reescribe.
- `v2.51-beta` y anteriores ⇒ **no** se mueven (sus sellos siguen siendo auditables con lo que
  declararon).
- Sin SHORT. Sin migración. Sin backfill. Sin UI nueva.
