# Evidencia cruda — `v2.88.19-beta` (`OBS-21`: matrícula del tick + ventana de gracia)

> **Objeto:** tag anotado **`v2.88.19-beta`** · package **`2.11.19-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**) · fecha **2026-10-01**.
> **Clase:** sello de **producto** (`Δ src ≠ 0`), a diferencia de los sellos `docs-only`/`test-only` de la serie `W`/`G2`. **Umbrales `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B: INTACTOS.** Sin backdating.
> **Origen:** el `lifecycle-pg` del tag **`v2.88.18-beta`** quedó **ROJO** en `Release tag CI` run **`36886166182`** (`2026-10-01T15:40:54Z`, la **única** prueba que cayó en todo el run — **11 de 12** jobs verdes, `certify` rojo por agregación como debe): el step `Pytest Concurrent AUTO (3 sesiones concurrentes + PG, fail if skipped)` murió en **una** prueba, `test_concurrent_auto_n_sessions_claim_one_signal_pg[5]` (`apps/api-python/tests/test_concurrent_auto_pg.py:346`):

```
E   AssertionError: la retirada debe DECLARAR que había cola de fill parcial:
    motivo='cancel' status='RELEASED_BY_CANCEL'
```

> Investigar **esa** prueba (la única del repo que ejerce el alta concurrente del tick **y** el barrido de reservas **entre sesiones** a la vez) destapó **dos defectos de producto** que ningún otro job podía ver: el **A** no había llegado al CI todavía y el **B** es el que firma el rojo de arriba.
> **Padres:** [`evidence/v2.88.18/README.md`](../v2.88.18/README.md) · [`evidence/v2.88.17.1/README.md`](../v2.88.17.1/README.md) · informe/relevo: [`obs-21-matricula-tick-y-ventana-de-gracia-v2.88.19-2026-10-01.md`](../../obs-21-matricula-tick-y-ventana-de-gracia-v2.88.19-2026-10-01.md).

---

## 0. Resumen de una línea por defecto

| # | Defecto | Síntoma medido | Causa raíz | Arreglo | Después |
|---|---------|----------------|------------|---------|---------|
| **A** | Matrícula del tick (`auto_engine_ticks`) | `psycopg.errors.UniqueViolation` sobre **`auto_engine_ticks_pkey`** en **2/300** intentos de la sonda pura (5 sesiones, mismo `engine_id`/`seq`) | `ON CONFLICT ON CONSTRAINT auto_engine_ticks_engine_seq_uidx` **no cubre** el PK, que es **otro** índice sobre la **misma** clave funcional; y el guardián de no-doble (`rowcount == 0`) era **código muerto** | `ON CONFLICT DO NOTHING` **sin árbitro** (cubre *todos* los índices únicos) + omisión leída por **`RETURNING`** | **0/300** errores, **una única** matrícula por intento (ganador devuelve el `tick_id`, omitido devuelve `None`) |
| **B** | Ventana de gracia de reservas | Un par **AJENO** (`mine=False`) retiraba con `cancel` una reserva **de milisegundos** justo antes de que su dueño emitiera: `released=200` frente a `Σ APPLIED=147` (2 tranchas, **mismo `cycle_id`**) | El sello de alta (`_v2_instant`) tiene resolución de **1 s** y la ventana era de **1 turno = 1.000 s exactos** ⇒ la edad **aparente** puede superar a la **real** en hasta 1 s | `reservation_grace_window` **SUMA** `V2_RESERVATION_GRACE_STAMP_RESOLUTION = 1 s` ⇒ `aged` implica edad **REAL** > ventana | Reserva conservada; el fill del dueño se materializa y la liberación por fill la encuentra viva |

---

## 1. Defecto A — la matrícula del tick podía reventar

### 1.1 Síntoma (medido con sonda, **NO** con el CI)

**Aviso para el auditor:** este defecto **no** aparece en el log del run `36886166182` — su evidencia es una **sonda pura** (5 insertadores `AsyncSession` concurrentes por intento, `record_tick` para el **mismo** `(engine_id, seq)`, **300** intentos) y el **soak local** del fichero (§4). No lo busque en el CI: no llegó a dispararse ahí.

```
ANTES:  intentos=300  IntegrityError=2  (psycopg.errors.UniqueViolation: duplicate key value
        violates unique constraint "auto_engine_ticks_pkey")
        detalle: Key (tick_id)=(tick-<engine>-<seq>) already exists.
```

Los supervivientes de esas corridas quedaban con **la misma** `(engine_id, seq)` que la clave del árbitro ⇒ el conflicto **no** era de la clave natural que el `ON CONFLICT` declaraba, sino del **PK**. Tasa: **2/300 intentos** (en la sonda de `rowcount` se midieron **125** inserciones: 25 intentos × 5 insertadores).

### 1.2 Causa raíz (medida, no interpretada)

La tabla lleva **dos** índices únicos sobre la **misma** clave funcional:

| Índice | Definición | ¿Cubierto por `ON CONFLICT ON CONSTRAINT …_uidx`? |
|---|---|---|
| `auto_engine_ticks_pkey` | `PRIMARY KEY (tick_id)`, con `tick_id = f"tick-{engine_id}-{seq}"` | **NO** |
| `auto_engine_ticks_engine_seq_uidx` | `UNIQUE (engine_id, seq)` | **sí** (era la clave explícita) |

`ON CONFLICT (…)` / `ON CONFLICT ON CONSTRAINT c` usa **solo el índice nombrado como árbitro**. Dos insertadores concurrentes con distinto `tick_id` textual son imposibles aquí (el `tick_id` es función determinista de `(engine_id, seq)`), pero la elección del **árbitro** decide *qué* violación se absorbe: al nombrar solo el `uidx`, PostgreSQL resolvía el conflicto contra un índice y el otro seguía armado ⇒ `UniqueViolation` del **PK** subía como excepción.

**El guardián de no-doble era código muerto:** `inserted.rowcount == 0` para detectar «ya existía» nunca era cierto, porque el driver devuelve **−1** para sentencias `INSERT … ON CONFLICT` sin `RETURNING` (medido: **−1** en las **125** inserciones de la sonda, **ganadas y omitidas**). Es decir, la rama que debía detectar la omisión **no se ejecutaba nunca**; el efecto observable era que la omisión se colaba como «inserción correcta».

### 1.3 Arreglo

`packages/py/application/src/bolsa_application/auto_engine_state_store.py` — `PostgresAutoEngineStore.record_tick`:

```python
async with self._session.begin_nested() as _sp:
    inserted = await self._session.execute(
        pg_insert(AutoEngineTickRow)
        .values(
            tick_id=f"tick-{tick.engine_id}-{tick.seq}",
            engine_id=tick.engine_id,
            seq=tick.seq,
            state=tick.state,
            proposals=int(tick.proposals),
            vetoes=int(tick.vetoes),
            pending_plans=int(tick.pending_plans),
            reason=_reason_text(tick.last_reason),
            tick_at=occurred,
            created_at=now,
        )
        .on_conflict_do_nothing()
        .returning(AutoEngineTickRow.tick_id)
    )
    if inserted.scalar_one_or_none() is None:
        await _sp.rollback()
        return
```

Dos cambios, cada uno con su porqué:

1. **`on_conflict_do_nothing()` sin árbitro** ⇒ cubre **todos** los índices únicos utilizables de la tabla (`pkey` **y** `uidx`). Nombrar un árbitro era una **apuesta**: cualquiera de las dos claves podía ser la que chocara.
2. **`RETURNING tick_id` + `scalar_one_or_none() is None`** ⇒ la omisión se lee de **datos**, no de un `rowcount` que el driver no rellena (`-1`). Si la fila entró, devuelve su id; si se omitió, `None` y **`ROLLBACK` del savepoint**.

### 1.4 Después

```
DESPUÉS: intentos=300  IntegrityError=0
          300 filas con tick_id (una por intento, ganador)
          1200 None            (los 4 perdedores por intento, omitidos)
          filas por (engine_id, seq) = exactamente 1
```

**4** perdedores × **300** intentos = **1200** omisiones declaradas ⇒ no hay «ganadores duplicados» ni omisiones silenciosas.

---

## 2. Defecto B — la ventana de gracia envejecía una reserva recién nacida

### 2.1 Síntoma

**Esta es la firma que mató el CI** (run `36886166182`), en `test_concurrent_auto_pg.py:346`:

```
E   AssertionError: la retirada debe DECLARAR que había cola de fill parcial:
    motivo='cancel' status='RELEASED_BY_CANCEL'
```

Es decir: se declaró «nunca se materializó» (`cancel`) sobre una reserva que **sí** tenía cola de fill. Reproducido en local con instrumentación temporal, y ahí el libro completo quedó a la vista:

```
released  = 200.000000   (retirada total, release_reason = "cancel", sesión con mine = False)
Σ APPLIED = 147.000000   (2 tranchas: 100 + 47, MISMO cycle_id)
in_flight = []           (la orden no estaba en vuelo: nadie la había emitido todavía)
```

`released != materializado` es exactamente la firma que `OBS-14`/`OBS-20` existen para **no** volver a producir: además de devolver al mercado capital de una orden en vuelo, **falsea la procedencia** (declara «nunca se materializó» sobre una reserva que **sí** se materializó).

### 2.2 Traza de la decisión (la que aísla la causa)

Instrumentación temporal (retirada; el árbol queda **sin residuos**) sobre el discriminador `_v2_reservation_is_aged`:

| Sesión | Reloj de evaluación | `created` (según sello) | Edad **aparente** | Ventana | Decisión |
|---|---|---|---|---|---|
| A (dueño) | `16:08:10.999037` | `16:08:09` | 0.999 s | 1.000 s | **CONSERVA** |
| B (ajena) | `16:08:10.009331` | `16:08:09` | **1.009 s** | 1.000 s | **RETIRA (`cancel`)** |

La reserva se creó en `16:08:09`; su edad **real** al ser evaluada por B era de **~10 ms**. La edad **aparente** (reloj − sello) era **1.009 s**.

### 2.3 Causa raíz

El sello de alta (`_v2_instant`, `YYYY-MM-DDTHH:MM:SSZ`) tiene resolución de **1 segundo**: la edad calculada desde el sello es `edad_real + δ`, con `δ ∈ [0, 1)` y **siempre positiva**. La ventana de gracia era de **1 turno**, y en el entorno de la certificación el turno es de **1.000 s exactos**:

```
ventana = V2_RESERVATION_GRACE_TURNS (1) × interval (1.000 s) = 1.000 s
```

Con `δ` hasta 1 s, una reserva de **milisegundos** puede superar el umbral ⇒ el barrido de otra sesión la declara muerta **antes de que su dueño emita**. La ventana medía, en realidad, «edad + ruido de cuantización», no «edad».

### 2.4 Arreglo

`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`:

```python
V2_RESERVATION_GRACE_STAMP_RESOLUTION = timedelta(seconds=1)

def reservation_grace_window(interval_seconds: float | None = None) -> timedelta:
    seconds = _sim_interval_seconds() if interval_seconds is None else interval_seconds
    return (
        timedelta(seconds=V2_RESERVATION_GRACE_TURNS * seconds)
        + V2_RESERVATION_GRACE_STAMP_RESOLUTION
    )
```

La resolución del sello se **suma** a la ventana (no se resta del cálculo de la edad): `aged` pasa a implicar edad **REAL** > ventana. El orden de magnitud del cambio es **1 s**, no un turno: no relaja la política de gracia (`OBS-14.b`), solo deja de contar el ruido de cuantización como edad.

### 2.5 Después

`test_concurrent_auto_pg.py`: la reserva **viva** de la sesión A sobrevive al barrido del par ajeno, el fill del dueño se materializa y la liberación por fill la encuentra **viva** (libera, no `cancel`) ⇒ `released == materializado`. Reproducible **60/60** (ver §4).

---

## 3. Hipótesis propia, medida y **descartada** (declarada por honestidad)

Se sospechó **también** el **orden de lectura** de la evidencia durable en `_v2_reconcile_reservations` (leer el libro de reservas antes o después de las trazas de fill). Se aplicó el cambio de orden y **el fallo persistió idéntico** (misma tasa, misma firma `cancel`). Se **revirtió** ⇒ **Δ `src` = 0** por ese concepto.

Se deja escrito porque un auditor que compare el árbol con las hipótesis del relevo encontrará que esa idea **se probó y se abandonó con medida**, no que se ignoró.

---

## 4. Soak (certificación de concurrencia)

Fichero: `apps/api-python/tests/test_concurrent_auto_pg.py` (PG real, **3** sesiones).

| Momento | Corridas | Fallos | Firma de los fallos |
|---|---|---|---|
| **Antes** | ~**66** | **3** | 2 × `IntegrityError` (`auto_engine_ticks_pkey`) + 1 × `released=200` / `materializado=147` con `cancel` |
| **Después** | **60** | **0** | — |

Los **3** fallos previos no son de la misma familia (uno es integridad, otro es procedencia) — y **por eso** el mismo fichero destapó los dos defectos: es la única prueba del repo que ejerce el alta concurrente del tick **y** el barrido de reservas **entre sesiones** a la vez.

---

## 5. Guardas y mutación

**Guarda hermética nueva** (`apps/api-python/tests/test_auto_v2_durable_cycle.py`):

- `test_reservation_grace_window_sums_the_stamp_resolution` — propiedad determinista: la ventana **debe** ser `turns × interval + 1 s` para varias combinaciones de `interval_seconds`; **no** depende del reloj ni de PG.

**Mutación:** eliminando el término `+ V2_RESERVATION_GRACE_STAMP_RESOLUTION` de `reservation_grace_window`, la guarda **falla** (muere el mutante). Aplicada y revertida con el árbol **restaurado byte a byte**.

Guardia de la **misma propiedad** para el defecto A: la sonda pura (§1.4) es el instrumento; su versión **en árbol** es la que hace que un `ON CONFLICT` con árbitro nombrado vuelva a producir `IntegrityError` de forma **determinista** en la sonda (2/300 con árbitro vs 0/300 sin él) — se declara como **medida**, no como test de CI (la sonda se ejecuta a mano y su salida está arriba).

---

## 6. Verificación

### 6.1 Re-ejecutada en el momento del sello

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` (**el gate exacto de CI**) | `Success: no issues found in **512** source files` |
| `uv run python -m pytest apps/api-python/tests/test_auto_v2_durable_cycle.py -q` | **28 passed** in 1.03 s |
| `uv run python -m pytest apps/api-python/tests/test_concurrent_auto_pg.py -q` × **10** iteraciones | **3 passed** en las 10 (**0 fallos**), ~2.2 s por iteración |

### 6.2 Verificación del sello (soak + baterías)

| Suite | Resultado |
|---|---|
| `test_concurrent_auto_pg.py` (PG real, 3 sesiones) — **soak del sello** | **3 passed** × **60** iteraciones = **0 fallos** |
| Sonda pura de la matrícula (defecto A) | **0/300** fallos · **300** `tick_id` · **1200** `None` |
| Batería enfocada motor+instrumento (hermética) | **130 passed** |
| Soak mixto hermético | **45 passed** |

> Nota de honestidad: la fila `mypy` de §6.1 se ejecutó con el **comando exacto** extraído del workflow (`python-ci.yml` / `release-tag-ci.yml`, step `Mypy`). Un `uv run mypy` **sin argumentos** (o sobre `apps/api-python` entero) **no** es el gate: recorre tests y scripts y devuelve **2 690** errores **preexistentes** que el gate acota fuera con su lista de rutas — declarado aquí para que nadie lo lea como una regresión de este sello.

---

## 7. Límites declarados (lo que este sello **NO** hace)

1. **No cierra `OBS-14.b`.** `OBS-14.b` es el **alcance** del barrido de arranque (global, no distingue una huérfana de una reserva **viva** de otra sesión). Este sello corrige la **precisión de la medida** con la que se decide «es huérfana»; el alcance queda **como estaba**.
2. **No cierra `OBS-19`/`G2`.** La compuerta `G2` sigue con sus **53** ficheros declarados y sin correr en ningún job.
3. **No acredita `P3-2`/`P3-3`.** Un soak de **~60** corridas con reloj de pared **no** sustituye la ventana PAPER real (≥4 días / ≥32 ciclos / A-B real).
4. **No toca umbrales** (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) ni backdatea nada.
5. **Sin migración**: Alembic head sigue en `046_fill_reference_mid` (los dos arreglos son de **código**).
6. **La cita del CI es POST-TAG** (patrón `OBS-3`/`OBS-4`): se cita el run del tag **después** del push, no se hereda de otra versión.
7. El tag **`v2.88.18-beta` NO se borra**: queda como **rojo citado** (`lifecycle-pg`, run **`36886166182`**).

---

## 8. Comandos (reproducir)

```bash
# 1) sonda pura de la matrícula (A): 5 sesiones, mismo (engine_id, seq)
uv run pytest apps/api-python/tests -q -k "concurrent_auto" -p no:randomly
#    (la sonda instrumentada del alta concurrente del tick se corre a mano; su salida está en §1.1/§1.4)

# 2) certificación de concurrencia (A + B) contra PG real
uv run pytest apps/api-python/tests/test_concurrent_auto_pg.py -q

# 3) guarda hermética de la ventana (B) + su mutante
uv run pytest apps/api-python/tests/test_auto_v2_durable_cycle.py -q -k "grace_window"

# 4) estilo y tipos como en CI
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py apps/api-python
```

---

## 9. Cita del CI

### 9.1 CI de **origen** (el rojo que destapó `OBS-21`) — citado, verificado

`Release tag CI` run **`36886166182`** (`ref=refs/tags/v2.88.18-beta`, `2026-10-01T15:40:54Z`) → **`FAILURE`**, con la forma **exacta**:

| Job | Conclusión |
|---|---|
| `python (ruff/imports/mypy/pytest offline)` | **success** |
| `replay-repro` | **success** |
| `shared` / `frontend` / `decision-spine` / `security` / `dr-verify` / `a7-gate` / `playwright (mock E2E)` | **success** |
| `lifecycle-pg (Alembic + auth + golden restart)` | **FAILURE** |
| `playwright (integrated E2E, opt-in)` | skipped (por diseño) |
| `certify (aggregate + artifact)` | **FAILURE** (agrega, como debe) |

El único step rojo: `Pytest Concurrent AUTO (3 sesiones concurrentes + PG, fail if skipped)`, en `test_concurrent_auto_n_sessions_claim_one_signal_pg[5]`, `apps/api-python/tests/test_concurrent_auto_pg.py:346`. **`lifecycle-pg` es, además, el job donde el fichero de concurrencia corre en serio** — de ahí que el defecto **B** sólo pudiera verse ahí (y el **A** ni siquiera ahí: ver §1.1).

### 9.2 CI del tag **`v2.88.19-beta`** — **CITADO (POST-TAG) · TODO VERDE**

`Release tag CI` run **[`36895471323`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36895471323)** (`ref=refs/tags/v2.88.19-beta`, HEAD `c712f2a5`, `2026-10-01T16:54:27Z` → `~17:01Z`) → **`SUCCESS`**: **11 jobs `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño, con **`certify` `success`**.

| Job | Conclusión | Cifra citada |
|---|---|---|
| `python (ruff/imports/mypy/pytest offline)` | **success** | `All checks passed!` · `no issues found in **512** source files` · **`4158 passed, 42 skipped`** |
| `lifecycle-pg (…)` — **el job del rojo de §9.1** | **success** | con **todos** los gates `*_PG_REQUIRED: 1` (incl. `AUTO_CONCURRENT_PG_REQUIRED`, `AUTO_V2_DURABLE_PG_REQUIRED`) ⇒ el fichero de concurrencia corrió **de verdad** y pasó |
| `replay-repro` | **success** | **`VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)`** — render **LF** `3 340 728` B / `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`, **2ª corrida IDÉNTICA**, artefacto `11178993346` |
| `shared` / `frontend` / `decision-spine` / `security` / `dr-verify` / `a7-gate` / `playwright (mock E2E)` | **success** | — |

**Encaje de cuentas (el dato que cierra el sello):** el job `python` del run **rojo** de §9.1 dio **`4157 passed, 42 skipped`** y el del tag **`4158 passed, 42 skipped`** ⇒ **+1** = **exactamente** la guarda hermética nueva de §5, con los **mismos `42` skips** (ningún `skip` se movió). Esto **además demuestra** que la guarda **sí corre** en el job offline: no cae en la clase de `OBS-19`.

**Hallazgo derivado, medido (y contrario a lo que §9.2 anticipaba antes del run):** el sello tiene **`Δ src ≠ 0`** en `packages/py/application` (la matrícula del tick es del **store** del motor AUTO) y **aun así** `replay-repro` reproduce el artefacto **byte a byte** ⇒ los dos arreglos son **INERTES para el artefacto del replay**: el replay **no** ejerce ni el alta concurrente del tick (su motor es de un solo proceso, sin carrera) ni la ventana de gracia (que solo cambia **+1 s** de margen ⇒ ninguna decisión se mueve). Es la mejor forma posible de decir que el cambio **no toca la semántica** del instrumento OOS.
