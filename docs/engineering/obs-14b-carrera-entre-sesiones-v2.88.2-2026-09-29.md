# Corrección fail-OPEN de CARRERA en el cierre de turno — `AUTO-MATERIAL-16b` / `v2.88.2` (RE-SELLO)

> **AsOf:** 2026-09-29 · **Fase:** corrección de motor (`real_turn` + `_v2_reconcile_reservations` + costura del replay) sobre el sello `v2.88.1`.
> **Tipo de entrega:** código de motor (`apps/api-python/src/`) + módulo puro (`bolsa_application`) + tests + mutaciones + informe + evidencia.
> **Bump:** `2.11.1-beta` → `2.11.2-beta` · **SIN migración** (Alembic head sigue en `046_fill_reference_mid`).
> **Sello:** tag anotado **`v2.88.2-beta`** · **tags SUPERADOS:** `v2.88-beta` y `v2.88.1-beta` (ver §1) · **base del diff:** `dd8a16a5` (= `v2.88.1-beta`).
> **Padre:** [obs-14-correccion-fail-open-v2.88.1-2026-09-29.md](./obs-14-correccion-fail-open-v2.88.1-2026-09-29.md) · **Evidencia:** [evidence/v2.88.2/README.md](./evidence/v2.88.2/README.md) · **Índice:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) · **Deuda:** [deuda-p3-post-auditoria-v2.70-2026-09-26.md](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)

---

## 1. Por qué existe este RE-SELLO

El tag `v2.88.1-beta` (`dd8a16a5`) se publicó y su **`Release tag CI` quedó ROJO** (run `36548125321`):
el job `lifecycle-pg` tumbó el paso **`Pytest Concurrent AUTO`** (`test_concurrent_auto_pg.py`, `FFF`:

```
apps/api-python/tests/test_concurrent_auto_pg.py:326: in test_concurrent_auto_n_sessions_claim_one_signal_pg
    assert released == held, (
E   AssertionError: lo liberado por fill debe ser exactamente lo materializado:
                   released=200.000000 materializado=147.000000
```

**Corrección de un diagnóstico previo (importante para el auditor):** en el CI de `v2.88-beta`
(`36544461660`) **ese paso nunca se ejecutó**. Al fallar antes el paso de crash/recovery, GitHub **saltó**
los pasos siguientes y el job terminó en rojo por las guardas de *"no dejó log de la corrida"*
(`HardKill recovery`, `crash injection matrix`, `multiprocess AUTO`). Es decir: **el defecto existía ya en
`v2.88-beta` y estaba enmascarado**, no ausente. En `v2.88.1-beta` la guarda `attribute_fills` retiró el
primer fallo y dejó a la vista el segundo, que es el que este RE-SELLO corrige.

Además, los tres pasos **saltados** de `v2.88-beta` (`HardKill`, `crash injection matrix`,
`multiprocess AUTO`) se ejecutaron **por primera vez** en este RE-SELLO, en local: **5 passed**.

## 2. Causa raíz: una carrera entre SESIONES (fail-OPEN, no cosmética)

`_v2_reconcile_reservations` decide la **regla 2** («la reserva murió sin llenarse») con evidencia
**durable**: ninguna lectura APPLIED posterior al alta, ninguna traza sin aplicar (no `in_flight`) y las
dos lecturas MEDIBLES. Esa evidencia era suficiente mientras la reconciliación corría **solo al
arrancar**. Al correrla también al **cerrar cada turno** (el cierre de `OBS-14`), aparece un hueco que la
evidencia durable **no puede** cerrar:

> Una reserva recién dada de alta por **otra sesión** —cuya orden todavía no se ha emitido ni
> liquidado— es **indistinguible** de una orden muerta sin llenar.

Traza real del fallo (instrumentación temporal retirada; árbol restaurado byte a byte):

```
[RECON]  worker=…354656 (PERDEDOR) startup=False attr=False measurable=True in_flight=[] facts=[]
         live=[('RES-dec-…','inst-v46conc-…','buy','200.0', <created>)]
[RULE]   filled=0.0 available=0.0 fill_qty=0.0 remain=200.0 measurable=True
[RELEASE] status=RELEASED_BY_CANCEL delta=None remain_before=200.0  ← desde real_turn (cierre de turno)
[HOTFILL] worker=…575904 (GANADOR) qty=147.000000 → store.release devuelve None (fila ya liberada)
```

La sesión **perdedora** cierra su turno, ve la reserva **viva del ganador** y la declara muerta: libera
**200 completos**. El ganador materializa **147** después, y su liberación por fill ya no encuentra fila
viva (`released is None`): el resultado es `released=200` con `materializado=147`, es decir **capital
comprometido devuelto al mercado** — el mismo modo de fallo (fail-**OPEN**) que el RE-SELLO anterior, por
una puerta distinta.

**Nota de segundo hallazgo (misma familia):** el cierre de turno también podía retirar la **cola viva** de
un fill **propio del tick** si el hecho APPLIED aún no era durable en ese instante. El acotado por
propiedad **no** lo cubre por sí solo; lo cubre la combinación ya sellada (`attribute_fills=False`) más la
guarda `filled == 0.0`. Se deja dicho porque es el mismo patrón y el auditor debe poder buscarlo.

## 3. Prueba de causalidad

| Experimento (mismo árbol, mismo PG) | Resultado |
| --- | --- |
| Cierre con `attribute_fills=False` (el sello `v2.88.1`) | `FAILED` — `released=200.000000` vs `materializado=147.000000` |
| Worker revertido a `HEAD~1` (cierre `v2.88-beta`, regla 1 activa) | `FAILED` — **idéntico** (`200` vs `147`) |
| Tras el acotado por propiedad | `PASSED` (7/7 de la familia, 3/3 de los parámetros de la carrera) |

El segundo experimento es el decisivo: **el fallo no lo causaba la guarda `attribute_fills`** (con y sin
ella los números son idénticos), sino el **alcance** del cierre de turno. La instrumentación del punto
único de liberación (`_release`) mostró **una sola** liberación —`CANCEL` total, `remain_before=200.0`,
desde `real_turn`— y el camino caliente del ganador llegando **después**.

## 4. Corrección aplicada (alcance por PROPIEDAD)

La reconciliación gana un parámetro de alcance y el cierre de turno deja de mirar reservas ajenas:

```python
async def _v2_reconcile_reservations(
    self,
    *,
    startup: bool,
    attribute_fills: bool = True,
    only_ids: frozenset[str] | None = None,
) -> None:
```

- **`only_ids=None`** → **arranque**: barre el libro COMPLETO, como siempre (el proceso nace sin memoria
  y la huérfana ajena es exactamente lo que hay que retirar).
- **`only_ids={…}`** → **cierre de turno**: solo las reservas que **esta sesión** dio de alta
  (`_v2_owned_reservations`, alimentado en los dos únicos puntos de alta: `save_claim` ganado en
  `_v2_persist_tick_reservations` y `_v2_reserve_exit`). Las ajenas se **conservan vivas** en el libro
  (su capital sigue comprometido para esta sesión) y **no** se tocan sus `INTENT` de salida.

La **costura del instrumento `v2.87`** (`close_tick`) pasa el mismo conjunto, de modo que instrumento y
motor no divergen.

**Por qué es la corrección correcta y no un parche:** la propiedad es el **único** discriminador
disponible. La evidencia durable no puede separar «orden muerta» de «orden que otra sesión aún no ha
emitido», y para las reservas propias el orden de turno garantiza que ya se emitió y liquidó (SIM) antes
del cierre. El acotado **solo puede retirar menos**, nunca más: es fail-**CLOSED**.

## 5. Qué NO cambia

- **No** se degrada ninguna compuerta, **no** se fuerza régimen, **no** se baja ningún umbral.
- La reconciliación de **arranque** mantiene su comportamiento exacto (por defecto, alcance total).
- **SIN migración**: Alembic head sigue en `046_fill_reference_mid`.
- **Los números del artefacto `v2.87` no cambian por este acotado**: en un proceso ÚNICO el huérfano del
  tick es del propio turno, así que el conjunto acota sin quitar nada. (La declaración de RE-EJECUCIÓN de
  `v2.86`/`v2.87` **se mantiene** por la guarda anterior `attribute_fills`.)

## 6. Validación en el árbol (antes del RE-SELLO)

| Medición | Comando (resumen) | Resultado |
| --- | --- | --- |
| Carrera entre sesiones (la que rompió) | `pytest apps/api-python/tests/test_concurrent_auto_pg.py` | **7 passed** (antes: 3 failed) |
| Ciclo durable + costura | `pytest apps/api-python/tests/test_auto_v2_durable_cycle.py` | **14 passed** |
| Instrumento | `pytest packages/py/application/tests/test_replay_oos.py` | **14 passed** |
| Vecinos del motor | crash/recovery PG + partial fills + worker integration + lifecycle PG | **49 passed** |
| Pasos SALTADOS en CI (1ª vez) | HardKill + crash injection matrix + multiprocess PG | **5 passed** |
| Estilo | `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| Mutaciones nuevas `M249`–`M251` | arnés real, filtrado | **3/3 detectadas** |

Mutaciones nuevas:

- **`M249`** (el cierre pierde el acotado y vuelve a liberar reservas de otra sesión) → lo caza
  `test_closing_reconcile_does_not_touch_another_sessions_reservation`.
- **`M250`** (el barrido de ARRANQUE se acota por propiedad y deja de retirar la huérfana ajena) → lo caza
  el mismo test, por su contraste con un **proceso nuevo** (ruta de producción de `real_turn`).
- **`M251`** (la costura del replay deja de acotar) → lo caza `test_close_tick_does_not_re_attribute_fills`.

**Re-anclaje obligado de 4 mutaciones previas:** el sello cambió el texto que anclaban `M240`, `M246`,
`M247` y `M248` (el cierre de turno pasó a llamada multilínea con `only_ids`, en motor y en costura). La
primera corrida de la matriz completa lo declaró **en ROJO** (`mutaciones SIN medir`), que es el
comportamiento correcto del arnés: **no finge cobertura sobre una etiqueta que ya no casa**. Se
re-anclaron al código nuevo **sin cambiarles la semántica** y se certificaron con
`--only M240 M246 M247 M248` → **4/4 detectadas**, árbol restaurado byte a byte. Detalle y trazas en
[`evidence/v2.88.2/README.md`](./evidence/v2.88.2/README.md) §4.b.

## 7. Límite declarado (no se maquilla)

- **Deuda nueva `OBS-14.b` (residual, MEDIUM):** el barrido de **ARRANQUE** sigue siendo global y, por
  tanto, **tampoco** distingue una huérfana de una reserva **viva de otra sesión a mitad de turno** (en un
  reinicio rodante con otro motor operando). Ya era así en `v2.85.2` y el arreglo acordado es de
  **alcance**: aquí se cierra el camino del **cierre de turno**. Discriminador posible y no implementado:
  **ventana de gracia por EDAD** de la reserva. Queda registrado en la deuda P3 y **no** se finge
  cubierto.
- El artefacto multianual de `v2.86`/`v2.87` sigue **exigiendo RE-EJECUCIÓN** (medido con la costura
  previa a `attribute_fills=False`); no se usa como evidencia de estrategia ni para mover `P3-2`/`P3-3`.
- `mypy` **NO MEDIDO en local** (Windows Application Control bloquea `mypy.main` y `uvx`): lo mide el job
  `python (ruff/imports/mypy/pytest offline)` del CI del tag (verde en `v2.88.1-beta`, sin cambios en esos
  ficheros).

## 8. Relevo

- **Estado:** `OBS-14` sigue **cerrada** (ahora con el alcance correcto); `OBS-14.b` **abierta** (nueva,
  residual de arranque); `OBS-15` sigue **abierta**.
- **Objeto de auditoría vigente:** tag `v2.88.2-beta` (versión `2.11.2-beta`). Los tags `v2.88-beta` y
  `v2.88.1-beta` quedan superados y sus CI rojos **documentados** en `evidence/v2.88.1/README.md` y
  `evidence/v2.88.2/README.md`, conservados como evidencia.
