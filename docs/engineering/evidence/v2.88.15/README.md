# Evidencia del sello `v2.88.15-beta` — `GRANULARIDAD-OPERATIVA` · **W2** (short-circuit de barra, Fase A, `Δ = 0` estricto)

> **Objeto:** tag anotado **`v2.88.15-beta`** · **Versión:** `2.11.15-beta` · **Alembic head:**
> `046_fill_reference_mid` (**sin migración**).
> **Naturaleza:** segunda fase **demostrablemente neutra** de la serie. No se salta la decisión **ni** la
> protección: se deja de **releer**, dentro de la MISMA barra D1, el I/O de DATO que la barra ya decidió.
> **Base del diff:** `v2.88.14-beta` (HEAD padre del árbol sellado: `2c723bb3`; el HEAD del sello lo fija el
> commit del propietario).
> **AsOf:** 2026-09-30.

---

## 1. Qué es este sello

`W2` del [plan de trabajos](../../plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md). El
diagnóstico del diseño v2 es que el **dato es diario** (D1) y el **bucle late cada 60 s**
(`auto_simulation_worker.py:6155`, `_sim_interval_seconds(default: float = 60.0)`) ⇒ ~**1.440 ticks/día**
para ~**1 decisión real** por barra.

`W2` cobra ese trabajo redundante **sin cambiar un solo resultado**:

- El turno **durable** cuyo dato de barra ya está cargado en RAM **reutiliza** ese dato y deja de pagar
  el I/O de DATO del tick: `_v2_refresh_regime` (`:3028`), `_v2_load_consumed_signals` (`:3111`),
  `_v2_refresh_trade_context` (`:2101`), `_v2_refresh_open_orders` (`:2125`),
  `_v2_build_adaptive_plan` (`:3356`) y `_v2_prune_consumed_signals` (`:3134`).
- **Lo que NO se omite** es la **decisión**: `_v2_plan_tick(reuse_bar_datum=…)` (`:3184`) sigue llamando a
  la función **pura** `plan_v2_tick` con el estado corriente del turno. Por eso `Δ evidence = 0` **sin
  replicar contabilidad**: la única fuente de verdad del embudo, el journal y la procedencia del ATR
  sigue siendo la matemática de decisión, que se ejecuta en **todos** los turnos.
- El **heartbeat** durable (`record_tick`, `auto_engine_state_store.py:107`/`:125`) sigue en **todos** los
  turnos ⇒ **`Δ record_tick = 0`** y el contrato del store **no se toca** (`AutoEngineTickInput.seq` `:84`).

**NO** enmienda el ADR 010 y **NO** toca `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B.

---

## 2. Ficheros del sello

| Fichero | Δ | Rol |
| --- | --- | --- |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `+131/−20` | estado de barra en `__init__` (`:753`–`:764`); helpers `_v2_bar_short_circuit_applies` (`:3072`), `_v2_bar_note_plan` (`:3090`), `_v2_bar_note_settlement` (`:3095`); `_v2_plan_tick(*, reuse_bar_datum=False)` (`:3184`); seam en `auto_turn` (`:4741`); nota de liquidación (`:5068`); alcance en `real_turn` (`:5180`, `:5182`, `:5321`) |
| `apps/api-python/tests/test_auto_v2_bar_short_circuit.py` | **nuevo**, 414 líneas, **5 tests** | A/B de equivalencia estricta (`Δ = 0`) + bordes fail-closed |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `+40` | **`M275`→`M278`** (la matriz llega a **`M278`**, `:3030`) |

**Sin migración.** El head sigue en `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py`.

---

## 3. El estado de barra (lo que se reutiliza)

`__init__` (`:753`–`:764`):

| Campo | Para qué |
| --- | --- |
| `_v2_bar_short_circuit` | ¿el turno es **durable**? Lo enciende `real_turn`, no el arnés hermético |
| `_v2_bar_plan_bar` | barra cuyo dato de decisión ya se cargó **en este proceso** (`""` = ninguna) |
| `_v2_bar_adaptive` | el plan Adaptive viaja **con** el dato de barra (si no, se releería) |
| `_v2_bar_pending` | **fail-closed**: la barra dejó aprobaciones **sin consumir** |
| `_v2_bar_short_circuit_ticks` | instrumentación: turnos que reutilizaron el dato |

El seam se decide por turno (`auto_turn`, `:4741`):

```
same_bar_datum = self._v2_bar_short_circuit_applies()
```

y `_v2_bar_short_circuit_applies` (`:3072`) sólo afirma cuando las **tres** cosas se sostienen: turno
durable, dato de barra cargado, y **ninguna** aprobación pendiente. Si el plan del turno **falla**, la
barra **no** queda acreditada (`self._v2_bar_plan_bar = ""`, `:4753`) y el turno siguiente **vuelve a
releer**: un hueco no se hereda.

---

## 4. `Δ = 0` estricto, **medido** (`test_auto_v2_bar_short_circuit.py`, **5/5**)

El control (`OLD`) es el **mismo** turno durable con el seam apagado (`_control` monkeypatchea
`_v2_bar_short_circuit_applies → False`), así que la comparación es A/B sobre idéntico config/cuenta/
señales/precios: no se compara contra un mock, se compara contra **el propio camino previo**.

### 4.1 Informe del día idéntico y ahorro real de I/O

`test_same_bar_turns_reuse_the_datum_without_changing_the_daily_report` — 4 turnos D1 en la **misma**
barra (señal re-emitida en cada uno: el caso que infla embudo y journal):

| Magnitud medida | `OLD` (seam OFF) | `NEW` (seam ON) |
| --- | --- | --- |
| I/O `refresh_regime` | `4` | `1` |
| I/O `trade_context` | `4` | `1` |
| I/O `open_orders` | `4` | `1` |
| `_v2_bar_short_circuit_ticks` | `0` | `3` (= `_TURNS − 1`) |
| `auto_store.ticks_written` (**heartbeat**) | `4` | `4` |
| `_report(...)` (informe diario: embudo, ATR, journal, atribución) | — | **idéntico** (`==`) |
| `Δ fills` / `Δ cycles` / `Δ settlements` / `Δ PnL` / `Δ reservas` | — | **`0`** |

El test **no** se conforma con «el informe coincide»: cuenta el I/O por turno y exige que el turno
reutilizado **no** lo haga. Un short-circuit inerte (que nunca se activara) fallaría este test.

### 4.2 La PROTECCIÓN no se cortocircuita

`test_an_exit_inside_the_bar_is_never_short_circuited` — el precio rompe el stop estructural (**97**,
derivado de `ATR = 2`, `100 − 1.5×2`) en un turno **intermedio** de la misma barra: la salida se
materializa en los **dos** caminos, con `dict(day.exit_reasons) == {"structural_stop": 1}` y los mismos
motivos de gestión journalizados. La gestión de posición corre en el bucle por símbolo de `auto_turn`,
**fuera** del seam de I/O: el short-circuit ahorra **I/O de decisión, jamás protección**.

### 4.3 Bordes fail-closed

| Test | Qué fija |
| --- | --- |
| `test_a_bar_with_an_unconsumed_approval_keeps_re_reading` | la barra con una aprobación **sin consumir** **no** reutiliza (`_v2_bar_pending`) |
| `test_the_approval_that_never_filled_is_what_blocks_the_reuse` | el **settlement sin fill** es lo que **activa** la guarda (la señal sigue sin marcar en `_v2_consumed_signals`); el reintento intra-barra es observable porque el fill se ancla al minuto (`:1355`, `seed=self._minute * 100_003 + …`) |
| `test_changing_the_bar_re_reads_the_datum` | el **cambio de barra** vuelve a releer (`_v2_current_bar_start() != _v2_bar_plan_bar`, `:3050`) |

---

## 5. Alcance del seam (el arnés hermético **no** cambia)

`self._v2_bar_short_circuit = True` se enciende **sólo** dentro de `real_turn` (`:5182`) y se restaura en
su `finally` (`:5321`), con la misma disciplina que los demás seams de store de ese método. Consecuencia
medible: el camino **hermético** (tests y replay que llaman `auto_turn` suelto) sigue midiendo el plan
completo byte a byte, y el **default** sigue siendo el comportamiento previo.

---

## 6. Mutaciones (`M275` → `M278`, +4)

| Id | Defecto inyectado | Mata |
| --- | --- | --- |
| `M275` | la guarda de pendiente se ignora (**fail-open**): una barra con aprobación sin consumir vuelve a reutilizar | `test_a_bar_with_an_unconsumed_approval_keeps_re_reading`, `test_the_approval_that_never_filled_is_what_blocks_the_reuse` |
| `M276` | la reutilización **sobrevive al cambio de barra** (el motor deja de decidir el día siguiente) | `test_changing_the_bar_re_reads_the_datum` |
| `M277` | **la DECISIÓN sí se omite**: el turno reutilizado deja el plan a `None` ⇒ embudo, journal y procedencia del ATR desaparecen del informe | `test_an_exit_inside_the_bar_is_never_short_circuited`, `test_same_bar_turns_reuse_the_datum_without_changing_the_daily_report` |
| `M278` | **ahorro vacío**: el short-circuit cuenta turnos pero sigue releyendo régimen/contexto/órdenes (optimización narrada, no medida) | `test_changing_the_bar_re_reads_the_datum`, `test_same_bar_turns_reuse_the_datum_without_changing_the_daily_report` |

**Resultado:** `4/4` muerden; la sonda restaura el árbol **byte a byte** (`medidas: 4/4`; salida literal:

```
### M275 ... rojo en: test_a_bar_with_an_unconsumed_approval_keeps_re_reading, test_the_approval_that_never_filled_is_what_blocks_the_reuse
### M276 ... rojo en: test_changing_the_bar_re_reads_the_datum
### M277 ... rojo en: test_an_exit_inside_the_bar_is_never_short_circuited, test_same_bar_turns_reuse_the_datum_without_changing_the_daily_report
### M278 ... rojo en: test_changing_the_bar_re_reads_the_datum, test_same_bar_turns_reuse_the_datum_without_changing_the_daily_report
estado git de esos ficheros (despues): M apps/api-python/src/bolsa_api/background/auto_simulation_worker.py
  intacto: la sonda no altero el arbol
  medidas: 4/4 (ninguna se quedo sin fragmento)
```)

`M277` y `M278` son las dos trampas que este sello teme: **saltarse la decisión** (cambia el informe) y
**no ahorrar nada** (optimización de relato). Las dos rompen.

---

## 7. Trabajo transversal de `W2`: `OBS-15` / `OBS-16` (vigilados, **no** cerrados)

El plan asigna a `W2` vigilar el **techo de `1000 APPLIED`** (`OBS-15`) y la **cobertura local-vs-CI**
(`OBS-16`) «al tocar el bucle».

**(a) `OBS-15` — no se agrava (medido, no supuesto).** El short-circuit **no** toca el camino de
liquidación: `_persist_position`, la liquidación, los settlements y `_v2_note_settlement` siguen
ejecutándose en **todos** los turnos; lo que se omite es I/O de **lectura** de DATO de decisión. El techo
de `1000` filas `APPLIED` (`applied_fills.py`, `DEFAULT_APPLIED_LIMIT`) no cambia de magnitud por este
sello ⇒ **sigue ABIERTA como estaba**.

**(b) `OBS-16` — esta vez la cobertura local-vs-CI se **midió** con las **dos** listas, no con «suites
vecinas».** Recuentos locales de las dos listas de pytest (verbatim de las corridas de este sello):

| Lista | Recogidos local | Corrida local | Identidad |
| --- | --- | --- | --- |
| `python-ci.yml` (job `quality`) | `3172` | corrida **A/B** con el mismo listado menos `packages/py/domain/tests` (`110` tests, `3172 − 110 = 3062` recogidos) ⇒ `3061 passed + 1 failed` | — |
| `release-tag-ci.yml` (job `python`) | **`3180`** | **`1 failed, 3179 passed`** | `3142` (esperado CI `passed`) + `38` (esperado CI `skipped`) = `3180` ✔ |

El único rojo local es el **PG-local pre-existente** `test_auto_v70_auto23_evidence_validation.py::
test_the_validation_reads_real_postgres_material_and_seals_it` (`assert 17 == 26`), que **CI salta** (el job
`python` no tiene PostgreSQL) y que en local corre porque hay PG ⇒ es **1 de los 38 skips del CI**. Queda
**verificado que es ajeno a este sello**: con el cambio de `W2` **descartado** (`git stash` del worker) el
mismo test falla **idéntico** (`assert 17 == 26`). **`OBS-16` sigue ABIERTA** (la vigilancia no es un
cierre): lo que este sello aporta es la **medición de las dos listas** en lugar de la validación por
suites vecinas.

**Recuento de la batería (medido, Δ contra `v2.88.14-beta` con el **mismo** listado):**

| Listado | `W1` (seam apagado) | `W2` | Δ |
| --- | --- | --- | --- |
| `python-ci.yml` menos `packages/py/domain/tests` (recorte usado para el A/B) | `3056 passed + 1 failed` | `3061 passed + 1 failed` | **`+5`** |
| `release-tag-ci.yml` entero (recogidos) | `3175` (= CI `3137 + 38`) | **`3180`** | **`+5`** |

El `+5` es **exactamente** la suite nueva: el sello **no** añade ni retira tests en ningún otro sitio.

**Instrumentación de CPU / ticks por día: NO MEDIDO.** No se instrumentó reloj de pared ni CPU en este
sello (medirlo exige un banco que este sello no trae y **no se inventa cifra**). Lo que **sí** está medido
es el I/O por turno (§4.1: `4 → 1` lecturas de régimen, contexto y órdenes en una barra de 4 turnos) y el
contador `_v2_bar_short_circuit_ticks`. La extrapolación a ticks/día **no** se publica como medida.

---

## 8. Verificación local (números exactos)

| Gate | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `mypy` (targets de CI, `--follow-imports=silent`) | `no issues found in 510 source files` |
| `lint-imports --config packages/py/.importlinter` | `4 kept, 0 broken` |
| `pytest` suite nueva `test_auto_v2_bar_short_circuit.py` | **`5 passed`** |
| `pytest` golden día AUTO `test_auto_v2_golden_day_evidence.py` | **`5 passed`** |
| mutación `M275`→`M278` | **`4/4`** (árbol intacto) |
| batería offline `release-tag-ci` (listado completo, local con PG) | **`3179 passed, 1 failed`** (el rojo PG-local pre-existente, ajeno al sello: verificado con el cambio descartado) |

**El test nuevo entra en AMBOS workflows sin registro manual** (regla 6 del plan): vive bajo
`apps/api-python/tests`, que tiene **pase de directorio** en los dos jobs
(`python-ci.yml:361`, `release-tag-ci.yml:564`). `OBS-19` (listas manuales de
`packages/py/application/tests`) **no** se ve afectada por este sello.

---

## 9. Firma de estado (verificable)

```
git cat-file -t v2.88.15-beta                                     # tag (anotado)
git show v2.88.15-beta:package.json                               # 2.11.15-beta
git diff --stat v2.88.14-beta v2.88.15-beta -- packages/py apps/api-python/src \
  apps/api-python/scripts apps/api-python/tests .github
# Alembic: sin migración nueva (head sigue 046_fill_reference_mid)
```

---

## 10. Deuda que este sello NO cierra

`P3-2`/`P3-3` (ventana PAPER real ≥4 días con material), `OBS-19` (**causa estructural**), `OBS-16`
(cobertura local-vs-CI, **medida** aquí), `OBS-15` (techo de `1000 APPLIED`), `OBS-22`, `OBS-14.b`,
`OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`. `OBS-21` y `OBS-23` siguen **CERRADAS**.

---

## 11. Cita del CI (POST-TAG, 2026-09-30)

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado no
puede vivir dentro del propio tag; se cita en `main` como commit **POST-TAG**.

**Predicción declarada (Encaje `ESPERADO = OBSERVADO`):** job `python` **`3142 passed, 38 skipped`** =
los **`3137`** del CI de `v2.88.14-beta` + **`5`** del bundle `W2`, con los **mismos `38` skips** y
`ruff`/`import-linter`/`mypy` con los mismos veredictos. **Se cita el run, no se hereda.**

> **PENDIENTE DE CITA.** Este documento se sella con la **predicción** y el **encaje que cierra** (los
> `3180` recogidos local = `3142 + 38`); la cita verbatim del run se añade en `main` como commit
> **POST-TAG** cuando el propietario publique `v2.88.15-beta` (mismo patrón que `v2.88.14`).

---

## 12. Revisión

- **Implementa** `W2` del [plan](../../plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md), con
  **una precisión fechada** que el plan anota en su §3: el guard NO salta *decisión* ni *protección* — se
  reutiliza el **dato** de barra y la **decisión pura se recalcula** en cada turno (es lo que hace
  verificable `Δ = 0` sin replicar contabilidad).
- **No** cambia resultados: informe del día idéntico en el A/B (§4) y golden del día intacto.
- **Siguiente incremento:** **`W3`** (`v2.88.16-beta`) — Fase B, anclaje temporal `OPEN(D+1)`: el **primer**
  incremento que **sí** cambia resultados y por eso exige **golden nuevo**.
