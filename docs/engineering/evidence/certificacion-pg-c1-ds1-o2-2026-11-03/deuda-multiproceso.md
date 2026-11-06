# Deuda multiproceso: `test_auto_v46_multiprocess_pg.py` (AUTO-6)

**Fecha:** 2026-11-03
**Fichero:** `apps/api-python/tests/test_auto_v46_multiprocess_pg.py`
**Test:** `test_n_real_processes_claim_one_signal_exactly_once_pg`
**Veredicto:** **defecto de sincronización del test** (H1). No es una limitación de Windows y no
se toca producto.

## 1. Qué hace el test

Lanza **3 procesos** `bolsa_api.workers.scheduler_worker` reales (`subprocess.Popen`), cada uno
con su RAM, su reloj y sus stores `psycopg` async, sobre la **misma** cuenta/engine/instrumento/
barra/señal, contra PostgreSQL real. Los invariantes se leen **solo de lo durable**:

1. `count(distinct venue_order_id)` de BUY == 1;
2. una única fila de `portfolio_reservations` para la cuenta;
3. `Σ APPLIED BUY == released_qty` de esa reserva;
4. tras matar uno de los procesos y reiniciarlo, los invariantes siguen en pie.

Gobierno de honestidad: sin PG el test hace `pytest.skip`; con
`AUTO_MULTIPROCESS_PG_REQUIRED=1` el skip es fallo duro.

## 2. Las dos formas en que el bucle de espera mentía

El bucle de la FASE 1 rompía con `positions >= 1` **y** «alguna reserva `OPEN` con
`remaining_qty > 0`», y **acto seguido** assertaba `released_qty > 0`. Ese proxy no es el hecho
que el test mide, y falla en las dos direcciones:

### 2.1 Rompe demasiado pronto → el fallo de CI

El camino caliente escribe en **dos transacciones distintas**:

| Paso | Código | Transacción |
| --- | --- | --- |
| 1 | `_persist_position(...)` → `PostgresSimAutoPositionStore.upsert` (`autocommit=True`) | **COMMIT** de `sim_auto_positions` |
| 2 | `_v2_release_reservations_for_fill(...)` → `store.release(...)` | COMMIT de `portfolio_reservations` |

Entre los dos commits existe un estado **durable y legítimo**: hay posición, y la reserva sigue
`OPEN` con `released_qty = 0` y `remaining_qty = quantity`. Justo el estado que el proxy tomaba
por «la carrera se ha resuelto». Medido en CI:

- run [`41594625695`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41594625695) — **failed**
  en 5,68 s en `test_auto_v46_multiprocess_pg.py:194`:
  `assert Decimal('0') > 0` (materialización). Es decir: el bucle rompió en la ventana entre las
  dos transacciones y la aserción se ejecutó **antes** de que la liberación fuese durable.
- run [`41597599762`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41597599762) — **passed**
  (~115 s). Mismo código, otra intercalación: el segundo commit llegó antes de la lectura.

El mismo fichero se colgaba/gastaba el presupuesto en local. **No era Windows**: era la misma
condición de carrera del bucle.

### 2.2 Rompe nunca → los 115 s locales

Un fill **completo** deja la reserva en `RELEASED_BY_FILL` con `remaining_qty = 0`. Como el
proxy exigía una reserva `OPEN` **con cola**, con fill completo el bucle no rompía jamás: agotaba
los `160 × 0,5 s = 80 s` de presupuesto y solo entonces pasaba las aserciones (que sí se cumplían).
Medido en Windows con `127.0.0.1`: **115,5 s** por corrida — `80 s` (FASE 1 agotada) + `30 s`
(dwell deliberado de FASE 2) + arranque/migración.

## 3. Clasificación de las hipótesis

| Hipótesis | Criterio | Veredicto |
| --- | --- | --- |
| **H1** defecto de sincronización del test | rompe con un estado intermedio y/o agota el presupuesto sin exigir `released_qty > 0` | **CONFIRMADA** |
| H2 limitación de Windows / `localhost` | el cuelgue se explicaría por resolución de nombre/conexión | **DESCARTADA**: `localhost` = **36,5 s**, `127.0.0.1` = 35,6–39,6 s; sin delta de ~30 s. Los ~30 s de la corrida son el dwell de FASE 2, no conexiones |
| H3 carrera real / lock | el padre esperaría locks de los hijos | **DESCARTADA**: las lecturas del padre son `SELECT` simples, sin esperas de lock; el log del scheduler avanza |
| H4 fallo de arranque de hijos | `poll()` los vería muertos o el log no avanzaría | **DESCARTADA**: los 3 hijos arrancan y su log avanza (705 peticiones `httpx` al puente XTB local en una corrida) |

## 4. Arreglo aplicado (solo test)

Se sustituye el proxy por **el hecho que el test asserta**, con una condición estable en
cualquier punto intermedio:

```python
def _materialized(positions: int, rows: Sequence[Any]) -> bool:
    if positions < 1 or not rows:
        return False
    for row in rows:
        requested = Decimal(str(row.quantity or 0))
        released = Decimal(str(row.released_qty or 0))
        remaining = Decimal(str(row.remaining_qty or 0))
        if released > 0 and released + remaining == requested:
            return True
    return False
```

- `released > 0` ⇒ ya hay al menos una trancha materializada (lo que se asserta).
- `released + remaining == requested` ⇒ la contabilidad está cerrada, que el libro mantiene en
  **cada** liberación (también con `released = 0`), así que no se espera un estado que el
  producto no prometa.
- El bucle lee posiciones y reservas de una sola instantánea (`_materialization_snapshot`) y, si
  agota el presupuesto, el fallo incluye el **volcado durable** (`_materialization_dump`):
  `reservation_id`, `status`, `qty`, `released`, `remaining`.
- No se toca `_live_reservations`/`_MAX_POLLS`/`_CONVERGE_POLLS`: el presupuesto sigue siendo
  80 s + 30 s, solo que ahora se sale en cuanto el hecho es durable.

Además se añade una prueba **pura** (sin PG) que fija la regresión:
`test_la_materializacion_no_se_da_por_hecha_entre_las_dos_transacciones` — rechaza
`(positions=1, OPEN, released=0, remaining=qty)` y acepta liberación total o parcial.

**Por qué no se toca producto.** La ventana entre los dos commits es deliberada: el espejo de
posición es reconstruible y su commit propio nunca tumba el turno, y un crash en medio lo
reconcilia el arranque (adopción + `OBS-20`, que completa `materialized` desde `cycle_fills`
durables). Exigir atomicidad en el test obligaría a prometer algo que el diseño no promete.

## 5. Verificación

Windows 10.0.26200 · `.venv` Python 3.12.13 · `psycopg` 3.3.4 · PostgreSQL 16.14 en
`127.0.0.1:5432` · `AUTO_MULTIPROCESS_PG_REQUIRED=1`.

| Corrida | Antes del arreglo | Después del arreglo |
| --- | --- | --- |
| 1 | 115,5 s — passed | **36,1 s** — passed |
| 2 | — | **35,7 s** — passed |
| 3 | — | **39,6 s** — passed |
| 4 | — | **36,8 s** — passed |
| 5 | — | **37,0 s** — passed |
| `localhost` (1 corrida) | — | **36,5 s** — passed |

**5/5 verdes** con el arreglo, y el tiempo cae de 115 s a ~36 s: los ~30 s restantes son el
**dwell intencional** de la FASE 2 (dar ventana a una convergencia defectuosa), no espera de
sincronización. Ruff: **All checks passed**.

## 6. Riesgo residual

1. El test **ya no** distingue «aún no liberado» de «liberado»: espera al asentamiento. Si una
   regresión hiciese que la liberación no llega nunca, falla por presupuesto con el volcado
   durable, que es exactamente el diagnóstico que faltaba.
2. El dwell de FASE 2 sigue siendo fijo (30 s). No se cambia: es la ventana en la que un
   reemplazo defectuoso apilaría una segunda reserva/orden, y acortarlo debilitaría el invariante.
3. En local, el ciclo del scheduler tarda ~4–5 s en materializar porque el puente XTB de
   `localhost:3002` sirve cotizaciones de todo el universo (~705 peticiones por corrida). Infla el
   tiempo, no el resultado; en CI ese puente no existe.
