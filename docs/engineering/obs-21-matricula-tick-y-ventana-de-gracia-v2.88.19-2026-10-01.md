# `OBS-21` — Matrícula del tick + ventana de gracia de reservas (`v2.88.19-beta`)

> **Clase:** informe/relevo de un sello de **producto** (`Δ src ≠ 0`) · **fecha:** 2026-10-01 · **objeto:** tag anotado **`v2.88.19-beta`** · package **`2.11.19-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**).
> **Evidencia cruda:** [`evidence/v2.88.19/README.md`](./evidence/v2.88.19/README.md).
> **Padres:** [`evidence/v2.88.18/README.md`](./evidence/v2.88.18/README.md) (la compuerta `G2`, el sello que este supersede) · [`evidence/v2.88.17.1/README.md`](./evidence/v2.88.17.1/README.md) · [`obs-20-atribucion-por-ciclo-v2.88.7-2026-09-29.md`](./obs-20-atribucion-por-ciclo-v2.88.7-2026-09-29.md) (de dónde viene el invariante de procedencia) · [`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).

---

## 1. De dónde sale este sello

El sello **`v2.88.18-beta`** estaba cerrado (compuerta `G2`: los tests invisibles **205 → 53**, instrumento `scripts/ci/test_selection.py` + guarda de censo). Su `Release tag CI` (run [`36886166182`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36886166182)) dejó **11 de 12 jobs verdes** — `python` y `replay-repro` entre ellos — y **`lifecycle-pg` ROJO en una sola prueba**:

```
test_concurrent_auto_n_sessions_claim_one_signal_pg[5]
apps/api-python/tests/test_concurrent_auto_pg.py:346
E   AssertionError: la retirada debe DECLARAR que había cola de fill parcial:
    motivo='cancel' status='RELEASED_BY_CANCEL'
```

`test_concurrent_auto_pg.py` es **el único fichero del repo** que ejerce a la vez (a) el alta **concurrente** del tick del motor AUTO y (b) el barrido de reservas **entre sesiones**. Investigar ese rojo destapó **dos defectos de producto** distintos, no uno:

| | Defecto | Cómo apareció |
|---|---|---|
| **A** | La **matrícula del tick** podía reventar con `UniqueViolation` del **PK** | **Sonda pura** (2/300 intentos) + soak local del fichero (2 de los 3 fallos previos) |
| **B** | La **ventana de gracia** envejecía una reserva recién nacida ⇒ un par **ajeno** la retiraba con `cancel` | **El CI** (el assert de la línea 346) + sonda instrumentada |

Los dos son de **producto** (motor/infraestructura del motor), no de arnés. Esto importa: la serie `W`/`G2` venía de sellos `docs-only`/`test-only`, y este es el primer sello que **toca código de motor** desde `W4`.

---

## 2. Defecto A — el árbitro del `ON CONFLICT` era una apuesta

`record_tick` matriculaba el tick con:

```python
.on_conflict_do_nothing(constraint="auto_engine_ticks_engine_seq_uidx")
if inserted.rowcount == 0:   # guardián de no-doble
```

Dos fallos, los dos **medidos**:

1. **El árbitro nombrado no cubre el PK.** La tabla tiene **dos** índices únicos sobre la **misma** clave funcional: `…_engine_seq_uidx` sobre `(engine_id, seq)` y `…_pkey` sobre `tick_id = f"tick-{engine_id}-{seq}"`. `ON CONFLICT ON CONSTRAINT c` resuelve **solo** contra `c`; el otro índice queda armado. Resultado medido en sonda pura (5 insertadores concurrentes por intento, 300 intentos): **2/300** con `psycopg.errors.UniqueViolation` sobre **`auto_engine_ticks_pkey`**.
2. **El guardián de no-doble era código muerto.** El driver devuelve **−1** en `rowcount` para `INSERT … ON CONFLICT` (medido: **−1** en las **125** inserciones de la sonda, ganadas y omitidas). `rowcount == 0` **nunca** era cierto ⇒ la omisión no se detectaba por ahí.

**Arreglo (el mínimo que quita la apuesta, no el que la mitiga):**

```python
.on_conflict_do_nothing()                       # sin árbitro: TODOS los índices únicos
.returning(AutoEngineTickRow.tick_id)           # la omisión se lee de DATOS
...
if inserted.scalar_one_or_none() is None:       # sin fila devuelta ⇒ ya estaba matriculado
    await _sp.rollback()
    return
```

**Después:** **0/300**, **300** `tick_id` (una matrícula por intento), **1200** omisiones declaradas (4 por intento × 300).

---

## 3. Defecto B — la ventana de gracia medía ruido de cuantización como si fuera edad

El sello de alta de una reserva (`_v2_instant`) es **ISO-UTC a segundos**. La edad se calcula contra ese sello, así que la edad **aparente** = edad **real** + `δ`, con `δ ∈ [0, 1)` y **siempre positiva**. La ventana era de **1 turno**, y en la cadencia de la certificación el turno es de **1.000 s exactos**:

```
ventana = 1 × 1.000 s = 1.000 s
```

**Trace medido** (instrumentación temporal, retirada; árbol sin residuos):

| Sesión | Reloj | `created` | Edad aparente | Decisión |
|---|---|---|---|---|
| A (**dueño**) | `16:08:10.999037` | `16:08:09` | 0.999 s | **CONSERVA** |
| B (**ajena**, `mine=False`) | `16:08:10.009331` | `16:08:09` | **1.009 s** | **RETIRA (`cancel`)** |

La reserva tenía **milisegundos** de vida y la orden de su dueño **aún no se había emitido** (`in_flight = []`). El libro quedó así:

```
released  = 200.000000  (cancel)
Σ APPLIED = 147.000000  (2 tranchas, 100 + 47, MISMO cycle_id)
```

Dos consecuencias, y la segunda es la grave:

- **capital de una orden en vuelo devuelto al mercado** (el notional que la orden seguía reclamando se declara libre);
- **procedencia falsa**: se declara `cancel` («nunca se materializó») sobre una reserva que **sí** se materializó. Es exactamente la clase de mentira que `OBS-14` y `OBS-20` existen para impedir, y la razón por la que el assert de la línea 346 la caza.

**Arreglo:** la ventana **suma** la resolución del sello.

```python
V2_RESERVATION_GRACE_STAMP_RESOLUTION = timedelta(seconds=1)

def reservation_grace_window(interval_seconds: float | None = None) -> timedelta:
    seconds = _sim_interval_seconds() if interval_seconds is None else interval_seconds
    return (
        timedelta(seconds=V2_RESERVATION_GRACE_TURNS * seconds)
        + V2_RESERVATION_GRACE_STAMP_RESOLUTION
    )
```

`aged` pasa a implicar edad **REAL** > ventana. El cambio es de **1 s** (el error de medida del sello), **no** de un turno: la política de gracia no se relaja.

---

## 4. Lo que se probó y se **descartó** (declarado)

Se sospechó también el **orden de lectura** de la evidencia durable en `_v2_reconcile_reservations` (libro de reservas antes o después de las trazas de fill). Se aplicó el cambio y el fallo **persistió idéntico** (misma firma `cancel`). Se **revirtió**: **Δ `src` = 0** por ese concepto. Se deja escrito para que un auditor comparando el árbol con las hipótesis del relevo sepa que esa vía **se midió y se abandonó**, no que se ignoró.

---

## 5. Estado tras el sello

| Cosa | Estado |
|---|---|
| Defecto **A** (matrícula del tick) | **Corregido** (sonda 2/300 → 0/300) |
| Defecto **B** (ventana de gracia) | **Corregido** (60/60 + 10/10 soak) |
| Guarda hermética + mutante de **B** | Añadida; el mutante muere |
| `test_concurrent_auto_pg.py` | Añade volcado de diagnóstico (`cycle_id`/procedencia) al mensaje del assert ⇒ el **próximo** rojo llega **con causa** |
| `ruff` / `mypy` (gate exacto de CI) | `All checks passed!` · `no issues found in 512 source files` |
| `v2.88.18-beta` | **Rojo citado** (run `36886166182`), **no** borrado |
| CI del tag `v2.88.19-beta` | **TODO VERDE** — run [`36895471323`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36895471323): **11 `success` + 1 `skipped`**, `certify` `success`, `python` **`4158 passed, 42 skipped`** (**+1** sobre el run rojo = la guarda nueva; **mismos `42` skips**) y `lifecycle-pg` —el job del rojo— **verde** |
| `replay-repro` | **`REPRODUCIDO`** ⇒ los dos arreglos son **INERTES** para el artefacto del instrumento OOS (ver §9.2) |

---

## 6. Lo que este sello **NO** cierra (importante para el auditor)

1. **`OBS-14.b` sigue ABIERTA.** Su objeto es el **alcance** del barrido de arranque (global: no distingue una huérfana de una reserva **viva** de otra sesión en un reinicio rodante). Aquí se corrige la **precisión del instrumento** con el que decide «¿es huérfana?»; el alcance queda **como estaba**. Decirlo al revés sería el tipo de sobreventa que este repo prohíbe.
2. **`OBS-19`/`G2` sigue ABIERTA.** Los **53** ficheros declarados con motivo y tanda siguen sin correr en ningún job.
3. **`P3-2`/`P3-3` siguen ABIERTAS.** Un soak de concurrencia con reloj de pared **no** acredita la ventana PAPER real (≥4 días / ≥32 ciclos / A-B real). Este sello **no** mueve esa aguja.
4. **Umbrales intactos**: `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B sin tocar. Sin backdating.
5. **Sin migración**: los dos arreglos son de código.

---

## 7. Siguiente paso (lo que queda para la auditoría externa y la APP)

El orden que el propietario fijó — **elevar versión → auditar desde GitHub → probar la operativa en la APP** — queda así:

1. **Sellar `v2.88.19-beta`** — **HECHO**: commit `c712f2a5`, tag anotado **`v2.88.19-beta`** empujado junto a `main`.
2. **Citar el CI del tag** (POST-TAG) — **HECHO**: run [`36895471323`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36895471323) **TODO VERDE** (`python` **4158/42** = **+1** sobre el run rojo, **mismos `42` skips**; **`lifecycle-pg` —el job que dio el rojo— verde** con `AUTO_CONCURRENT_PG_REQUIRED=1`; `replay-repro` **`REPRODUCIDO`** ⇒ el arreglo es **INERTE** para el instrumento OOS).
3. **Auditoría externa**: el paquete de handover vigente es [`entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md`](./entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md) (+ [audit-pack](./audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md) + [arranque](./arranque-auditor-v2-88-17-1-w4-2026-10-01.md)). El auditor que entre por ahí debe **añadir** a su lista: `OBS-21` (este sello) y el criterio de salida de `-beta` ([`criterio-salida-beta-2026-10-01.md`](./criterio-salida-beta-2026-10-01.md), compuertas `G1`–`G7`).
4. **Probar la operativa en la APP**: es el paso que **ninguna** de estas correcciones sustituye. Todo lo anterior mide «¿el motor puede sobrevivir sin mentir?»; la prueba en la APP mide «¿qué hace la operativa de verdad, durante días?». `P3-2`/`P3-3` (cubos de calendario real, A-B real) **sólo** se acreditan ahí.

> **Regla de la casa que este documento respeta:** ninguna cifra sin comando, un hueco se declara **NO MEDIDO**, y jamás un `0` fingido.
