# `OBS-14.b` — Ventana de gracia por EDAD: el barrido de reservas deja de ser fail-OPEN en un reinicio rodante (`v2.88.5-beta`, `AUTO-MATERIAL-18`, 2026-09-29)

> **Tipo de entrega:** cambio de **motor** (acotado) + 8 funciones de test (**7 netas**) + 4 mutaciones + informe + evidencia + registros.
> **Objeto:** tag anotado **`v2.88.5-beta`** · **Versión:** `2.11.4-beta` → **`2.11.5-beta`** ·
> **Alembic head:** `046_fill_reference_mid` (**sin migración**) · **Base del diff:** `a4d32c0d`
> (= `v2.88.4-beta` + cita POST-TAG de su CI).
> **Origen:** **hallazgo de la auditoría externa de `v2.88.3-beta`** (`APROBADO`, 0 bloqueantes), que lo
> fija como **paso 2** del orden de prioridad (`OBS-17` ✅ → **`OBS-14.b` ← este sello** → volver a PAPER
> real) en el [informe de auditoría](./auditoria-v2-88-3-auto-material-16c-2026-09-29.md) y en la
> [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).

---

## 0. Qué es y qué NO es esta entrega

**Es** el cierre de **`OBS-14.b`**: la reconciliación de reservas deja de retirar una reserva **ajena**
por el único hecho de no ser de esta sesión. La regla pasa a retirar si **es de esta sesión**
(`only_ids`) **o** si la reserva **ya envejeció** una ventana (`V2_RESERVATION_GRACE_TURNS = 1` turno de
la cadencia real del loop). Una reserva **ajena y joven** se **conserva** (fail-**closed**): es el
discriminador que faltaba frente a un **reinicio rodante**.

**NO es** un cambio de comportamiento de trading: no se toca `TOP_N`, `REGIME`, `RISK`, `SIGNALS`, `A/B`
ni ningún umbral. **NO** cierra `OBS-15` (techo de 1000 `APPLIED`), `OBS-16` (costuras manuales de
`object.__new__`) ni `P3-2`/`P3-3`.

---

## 1. El hueco que cierra (fail-OPEN de reinicio rodante)

`v2.88.2` acotó el **cierre de turno** por **propiedad** (`only_ids = _v2_owned_reservations`) y dejó el
**barrido de ARRANQUE** global (`only_ids=None`). Pero la regla 2 decide "esta orden murió sin llenarse"
con **la misma evidencia durable** (sin `APPLIED`, sin traza en vuelo, lecturas medibles), y esa evidencia
**no puede distinguir**:

| Caso | Qué es | Qué debe hacer la reconciliación |
| --- | --- | --- |
| **Huérfana** | reserva que dejó un proceso **muerto** | retirarla (liberar el capital) |
| **Viva ajena** | reserva que **otra sesión** acaba de dar de alta y **aún no ha emitido/ liquidado** | **no tocarla** |

Sin discriminador, el barrido de arranque de **B** retiraba la reserva **viva de A** y devolvía al
mercado un capital que **A sí materializa** después: capital reservado ≠ capital materializado. Es el
**mismo fail-OPEN** que tumbo `v2.88.1-beta` (`test_concurrent_auto_pg.py`), pero por la pata que el CI
**no** ejercitaba (en el arranque **simultáneo** de varias sesiones la ventana es nula: todas barren antes
de que ninguna reserve). **Ya existía en `v2.85.2`**: no es una regresión de la serie `v2.88`.

---

## 2. El mecanismo: PROPIEDAD **o** EDAD

### 2.1 La fuente de verdad de la ventana

```python
V2_RESERVATION_GRACE_TURNS = 1

def reservation_grace_window(interval_seconds: float | None = None) -> timedelta:
    seconds = _sim_interval_seconds() if interval_seconds is None else interval_seconds
    return timedelta(seconds=V2_RESERVATION_GRACE_TURNS * seconds)
```

La ventana **no** es un número mágico: se declara en **turnos** y se deriva de
`AUTO_ENGINE_SIM_INTERVAL_SECONDS` (**default `60 s`**), que es la cadencia **real** del loop
(`auto_sim_loop` hace `run_tick()` y luego `sleep(interval)`). Con la cadencia nominal la ventana son
**60 s**.

**Por qué 1 turno es correcto en este motor.** El motor AUTO opera **solo** `paper`/`simulated` (sin
bridge LIVE): la orden **liquida dentro del tick**. Por tanto una reserva que ha superado **un turno
completo** sin fill y sin traza en vuelo está muerta **por construcción** — su dueño, sea quien sea, ya
cerró su turno. La EDAD es el discriminador, y **no** requiere identidad de sesión (que el esquema no
tiene).

### 2.2 La regla 2 (`_v2_reconcile_reservations`)

```python
mine = only_ids is not None and reservation.reservation_id in only_ids
if not mine and not self._v2_reservation_is_aged(created):
    resolved.append(reservation)
    continue
```

### 2.3 El predicado de edad (fail-closed por construcción)

```python
def _v2_reservation_is_aged(self, created: datetime | None) -> bool:
    if created is None:
        return False
    return (self._time - created) > self._v2_reservation_grace
```

- **Estricto (`>`):** en el borde exacto (`age == grace`, i.e. `== 1 turno`) la reserva **no** está
  caducada ⇒ se **conserva**. El borde cae del lado conservador.
- **Sin fecha legible ⇒ conserva.** Un `created_at` ilegable no es prueba de muerte.
- **Fecha FUTURA ⇒ conserva.** `self._time - created < 0` (dos procesos con **relojes no comparables**)
  ⇒ `False` ⇒ fail-closed. No se afirma una edad que no se puede medir.
- **Reloj de referencia:** `self._time`, la **misma** autoridad temporal con la que esta sesión fecha sus
  propias altas (no `datetime.now()`), para que la comparación sea intra-proceso.

### 2.4 Consecuencia declarada (retirada DIFERIDA, no indefinida)

La huérfana de un crash que **aún no envejeció** sobrevive al barrido de arranque y se retira en el
**primer cierre de turno posterior a la ventana** (etiqueta `RELEASED_BY_CANCEL`), **a lo sumo un turno
más tarde**; si el proceso no vuelve a arrancar, el arranque siguiente (ya con la reserva envejecida) la
retira como `RELEASED_BY_RESTART`. La retención está **acotada**, no es una fuga: el techo es
`V2_RESERVATION_GRACE_TURNS` turnos.

### 2.5 Simetría con la pata de SALIDA (`OBS-17`)

Una reserva ajena y joven **conservada** **no** se publica en `outcomes`, así que
`_v2_sync_exit_orders` la lee como `(0.0, None)` y **no** actúa sobre la identidad ajena: el `ExitOrder`
de la otra sesión **no** se marca `ABANDONED`. Es la misma dirección que el test de simetría de `OBS-17`
(la reserva de salida es de su sesión), ahora también frente al **tiempo**.

---

## 3. Los tests (`+8` funciones nuevas ⇒ **`+7` netos**)

`apps/api-python/tests/test_auto_v2_durable_cycle.py` — **16 → 22** (7 nuevas, **1 sustituida** ⇒ +6 netos):

| Test | Qué demuestra |
| --- | --- |
| `test_closing_reconcile_does_not_touch_a_young_foreign_reservation` | cierre de turno: la ajena **joven** se conserva (sigue `is_live`, `released_qty == 0`) |
| `test_closing_reconcile_retires_a_foreign_reservation_once_it_aged` | cierre de turno: la ajena **envejecida** se retira (`RELEASED_BY_CANCEL`) y su capital se libera |
| `test_startup_sweep_retains_a_young_foreign_reservation` | **arranque**: la ajena **joven** **sobrevive** al barrido (el fail-OPEN de `OBS-14.b`) |
| `test_startup_sweep_retires_an_aged_foreign_reservation` | **arranque**: la ajena **envejecida** se retira (`RELEASED_BY_RESTART`) |
| `test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future` | **relojes no comparables** (fecha futura): no se afirma edad ⇒ se conserva |
| `test_grace_window_boundary_is_strict_at_exactly_one_turn` | **borde estricto**: `age == 1 turno` ⇒ conserva; `age == 1 turno + ε` ⇒ retira |
| `test_closing_reconcile_does_not_abandon_a_young_foreign_exit_intent` | la ajena joven conservada **no** deja el `ExitOrder` del dueño en `ABANDONED` |

`apps/api-python/tests/test_auto_v44_exit_crash_matrix.py` — **8 → 9** (1 nueva ⇒ +1 neto):

- **`test_c2b_restart_inside_the_grace_window_retains_and_then_converges`** (nuevo): crash tras reservar
  y **reinicio DENTRO** de la ventana ⇒ la reserva **se conserva**; el **reinicio siguiente, ya
  envejecida**, la retira y el libro **converge** a plano ⇒ la retención es **acotada**, no una fuga.

**Re-anclados a la semántica de EDAD explícita** (sin tests nuevos):

- `test_auto_v44_exit_crash_matrix.py`: `test_c2_*` y `test_c4_*` pasan a reiniciar **más allá** de la
  ventana (minuto +2) — la huérfana del crash está muerta **por construcción** y el barrido debe retirarla.
- `test_auto_v44_exit_governance.py` (9 tests) y `test_auto_v46_crash_recovery.py` (2 tests): el reinicio
  se mueve **fuera** de la ventana, con el motivo escrito en el test (un reinicio **dentro** de la ventana
  **conserva**, y eso lo certifican los `test_startup_sweep_*`).

---

## 4. Las mutaciones (matriz `253` → `256`)

En `apps/api-python/scripts/v2_44_mutation_audit.py`:

| Mutación | Qué muta | Qué la caza (verbatim del run) |
| --- | --- | --- |
| **`M250`** (re-anclada) | `_v2_reservation_is_aged` → `return True` (ventana **nula**: toda reserva "envejece" al instante) | **6** tests: `test_closing_reconcile_does_not_touch_a_young_foreign_reservation`, `test_closing_reconcile_does_not_abandon_a_young_foreign_exit_intent`, `test_startup_sweep_retains_a_young_foreign_reservation`, `test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future`, `test_grace_window_boundary_is_strict_at_exactly_one_turn`, `test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it` |
| **`M254`** (nueva) | `_v2_reservation_is_aged` → `return False` (ventana **infinita**: nada caduca nunca) | **6** tests: `test_startup_sweep_retires_an_aged_foreign_reservation`, `test_closing_reconcile_retires_a_foreign_reservation_once_it_aged`, `test_grace_window_boundary_is_strict_at_exactly_one_turn`, `test_c2_crash_after_reserving_before_emit_releases_dead_and_exits_once`, `test_c2b_restart_inside_the_grace_window_retains_and_then_converges`, `test_c4_crash_after_partial_fill_carries_the_intent_and_converges` |
| **`M255`** (nueva) | edad **sin signo** (`abs(...)`): la distancia **absoluta** cuenta como edad ⇒ un reloj **futuro** se retira | **1** test: `test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future` |
| **`M256`** (nueva) | borde **no estricto** (`>=`): `age == 1 turno` ya autoriza a retirar | **2** tests: `test_grace_window_boundary_is_strict_at_exactly_one_turn`, `test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it` |

**Direcciones cubiertas:** `M250`/`M255` atacan el **fail-closed** (retirar de más = fail-OPEN) y
`M254`/`M256` atacan la **terminación** (conservar de más = fuga). Las cuatro direcciones de la ventana
(propiedad, edad, borde, relojes no comparables) tienen su mutación.

---

## 5. Verificación (números exactos)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Ciclo durable | `pytest apps/api-python/tests/test_auto_v2_durable_cycle.py` | **22 passed** (16 + 7 − 1 reemplazado) |
| Matriz de crash (exit) | `pytest apps/api-python/tests/test_auto_v44_exit_crash_matrix.py` | **9 passed** (8 + 1 nuevo) |
| Gobernanza de salida | `pytest apps/api-python/tests/test_auto_v44_exit_governance.py` | **9 passed** (re-anclados) |
| Crash/recovery `v46` | `pytest apps/api-python/tests/test_auto_v46_crash_recovery.py` | **2 passed** (re-anclados) |
| Estilo (comando EXACTO del CI) | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| Batería offline COMPLETA (mismo comando del CI, **extraído del workflow**) | `python -m pytest <115 args del job `Pytest offline`>` | **`1 failed, 3085 passed, 4 warnings in 73.77s`** (**`3086` recogidos**) |
| Matriz COMPLETA de mutaciones | `v2_44_mutation_audit.py` | **`256/256`** medidas (`exit 0`, ~12m50s) · árbol **intacto** · roturas **byte a byte** restauradas |
| Diff del motor | `git diff --stat` | **+91 / −20** en `auto_simulation_worker.py` (5 hunks: 2 de declaración de la ventana, 2 de la regla 2/predicado, 1 de comentario en el cierre de turno) |

El único `failed` local es **pre-existente y ajeno**:
`test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it`
(`AssertionError: assert 17 == 26`: necesita **material `paper_real` real** sembrado en PostgreSQL local y
la BD de desarrollo tiene **17** de los **26** ciclos que exige; en el job `python` del CI ese test **se
salta** y forma parte de los `37` skips — es el **mismo** fallo de entorno declarado en la evidencia de
`v2.88.3`). Los recuentos **cuadran**: `3085 + 1 = 3086` recogidos = los **`3079`** que recogía el job
`python` de `v2.88.4` (`3042 passed + 37 skipped`) **+ 7** tests netos ⇒ el esperado del CI es
**`3049 passed, 37 skipped`** (§7).

Cita cruda y detalle línea a línea: [`evidence/v2.88.5/README.md`](./evidence/v2.88.5/README.md).

---

## 6. Límites declarados

- **SÍ** se toca el motor (a diferencia de `v2.88.4`): la ventana de gracia **es** lógica de producción.
  Los 5 hunks están **enunciados** arriba y el cierre de turno solo **comenta** el cambio.
- **La ventana es 1 turno con la cadencia nominal (60 s).** Es una decisión **declarada**, no medida en
  producción: el techo de retención de una huérfana es esa ventana. El turno SIM real es trabajo en
  proceso + BD sin esperas de red, con lo que la ventana deja un margen de **dos órdenes de magnitud**
  sobre la duración medida del turno; aun así, si la cadencia configurada
  (`AUTO_ENGINE_SIM_INTERVAL_SECONDS`) fuese muy superior al turno real, la ventana sería más laxa (nunca
  menos laxa: la propiedad sigue acotando el cierre).
- **NO** sustituye la prueba real de concurrencia: eso es el job `lifecycle-pg` (crash/recovery + **3
  sesiones concurrentes** + golden day + aislamiento de cuenta) del CI del tag.
- **NO** cierra `OBS-15` (techo de 1000 `APPLIED`) ni `OBS-16` (costuras manuales de `object.__new__`).
- El fallo `1 failed` de la batería local es **pre-existente y ajeno a esta fase** (§5): el test que en el
  job `python` del CI **se salta** (necesita material real en PostgreSQL) y que en local corre contra la
  BD de desarrollo. Los recuentos **cuadran**: `3085 passed + 1 failed = 3086` recogidos = los **`3079`**
  de `v2.88.4` **+ 7** tests netos ⇒ el job `python` del CI debe dar **`3049 passed, 37 skipped`** (§7).

---

## 7. CI del tag (POST-TAG por construcción)

`Release tag CI` **solo corre al empujar**, así que la cita **no puede** vivir dentro del tag (patrón
`OBS-3`/`OBS-4`): se registra **después**. Esperado sobre este objeto (**+7 tests netos**, motor con
cambio acotado): job `python` **`3049 passed, 37 skipped`** (los `3042` passed de `v2.88.4` + **7**;
`3086` recogidos), con los **mismos `37` skips**. **Se cita el run, no se hereda.**

### 7.1 Cita REAL del run (POST-TAG, este commit)

_Pendiente de push: se rellena en el commit de cita POST-TAG, sin tocar el objeto sellado._

---

## 8. Evidencia y registros

- **Evidencia cruda:** [`evidence/v2.88.5/README.md`](./evidence/v2.88.5/README.md).
- **Registros:** `PROJECT_STATE.md` · `engineering-index-2026-08-03.md` (entrada 188) ·
  [`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
  (`OBS-14.b` → **CERRADA**).
- **Origen:** [`auditoria-v2-88-3-auto-material-16c-2026-09-29.md`](./auditoria-v2-88-3-auto-material-16c-2026-09-29.md)
  (paso 2 del orden de prioridad del auditor).
- **Relevos:** [`obs-17-simetria-ownership-salida-v2.88.4-2026-09-29.md`](./obs-17-simetria-ownership-salida-v2.88.4-2026-09-29.md)
  (paso 1) · [`obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md`](./obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md)
  (el `OBS-14.b` primigenio: el cierre de turno) ·
  [`obs-14-cierre-por-turno-v2.88-2026-09-29.md`](./obs-14-cierre-por-turno-v2.88-2026-09-29.md).
