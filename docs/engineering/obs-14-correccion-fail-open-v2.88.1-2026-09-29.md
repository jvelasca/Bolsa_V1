# Corrección fail-OPEN del cierre de turno — `AUTO-MATERIAL-16` / `v2.88.1` (RE-SELLO)

> **AsOf:** 2026-09-29 · **Fase:** corrección de motor (`real_turn` + costura del replay) sobre el sello `v2.88`.
> **Tipo de entrega:** código de motor (`apps/api-python/src/`) + módulo puro (`bolsa_application`) + tests + mutaciones + informe + evidencia.
> **Bump:** `2.11.0-beta` → `2.11.1-beta` · **SIN migración** (Alembic head sigue en `046_fill_reference_mid`).
> **Sello:** tag anotado **`v2.88.1-beta`** · **tag SUPERADO:** `v2.88-beta` (público y **rojo**, ver §1) · **base del diff:** `3483b6b5`.
> **Padre:** [obs-14-cierre-por-turno-v2.88-2026-09-29.md](./obs-14-cierre-por-turno-v2.88-2026-09-29.md) · **Evidencia:** [evidence/v2.88.1/README.md](./evidence/v2.88.1/README.md) · **Índice:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) · **Deuda:** [deuda-p3-post-auditoria-v2.70-2026-09-26.md](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)

---

## 1. Por qué existe este RE-SELLO

El tag `v2.88-beta` se publicó y su **`Release tag CI` quedó ROJO**. El fallo no era de entorno:

```
lifecycle-pg (Alembic + auth + golden restart)
  Pytest Crash/Recovery Day (proceso scheduler matado en sucio + PG, fail if skipped)
E AssertionError: la muerte debe ocurrir con el fill PARCIAL durable (cola de reserva viva);
                  reservas vivas: []
```

Los **cinco** workflows de `main` del mismo commit quedaron en **verde** — y entre ellos
`python (ruff/imports/mypy/pytest offline)`, de modo que el `mypy` que no se pudo medir en el entorno
local (Windows Application Control bloquea `mypy.main` y `uvx`) queda **medido por CI**: verde.

El objeto `v2.88-beta` **no es válido como objeto de auditoría**. Este documento y el tag `v2.88.1-beta`
lo sustituyen; la evidencia del rojo se conserva en `evidence/v2.88.1/README.md` sin borrarse, porque el
auditor tiene derecho a ver el fallo y su corrección, no solo el estado final.

## 2. Causa raíz (fail-OPEN, no cosmética)

La **regla 1** de `_v2_reconcile_reservations` reparte el histórico **COMPLETO** de fills
`applied_at >= created_at` de cada reserva: `consumed` se reinicializa en cada llamada, así que la
atribución **no es idempotente**, mientras que `_release` aplica `released_qty` como **delta** sobre la
fila durable (`ReservationLedger.release`).

Mientras la reconciliación solo corría al **arrancar** el proceso, ese reparto se ejecutaba una vez (y
sobre un libro vacío en el caso medido). Al invocarla además **al cerrar cada turno** (el cierre de
`OBS-14`), cada turno **volvía a liberar fills que el camino caliente ya había liberado**
(`_v2_release_reservations_for_fill`) y **drenaba el `remaining_qty` de una orden parcialmente
llenada**: la cola VIVA del fill parcial, que es capital realmente comprometido.

El resultado no era un veto conservador sino lo contrario: **devolver al mercado un capital que la orden
seguía reclamando**. El test de crash/recovery lo detecta precisamente porque exige que la muerte sucia
ocurra con esa cola viva.

## 3. Prueba de causalidad (y corrección de un diagnóstico previo)

1. **Revertir SOLO** `auto_simulation_worker.py` a `HEAD~1` (sin tocar nada más):
   `test_crash_recovery_day_real_process_survives_dirty_kill_pg` → **pasa en 8,87 s**.
2. Con el cierre de turno activo → **falla** (mismo aserto que CI).
3. En CI, sobre **Postgres 16 nuevo con `alembic upgrade head`**, falla **idéntico** ⇒ no es estado de
   la base de datos de desarrollo.

**Corrección de un diagnóstico previo de esta misma sesión:** en la corrida local completa fallaron 7
tests y se atribuyeron todos a "estado obsoleto de la BD de desarrollo". **Uno de ellos era esta
regresión real**; los otros seis sí eran estado local (contenido sembrado `17 != 26`, `403` de auth, y
`test_workspaces_crud` dependiente de orden, que pasa en aislado).

## 4. Corrección aplicada

La reconciliación gana un parámetro explícito y el cierre de turno deja de repartir fills:

```python
async def _v2_reconcile_reservations(
    self, *, startup: bool, attribute_fills: bool = True
) -> None:
```

- `attribute_fills=True` (por defecto) → **arranque**: conserva la semántica previa, sin cambios.
- `attribute_fills=False` → **cierre de turno**: corre solo la **regla 2** (la reserva que NUNCA se
  materializó, `filled == 0.0`), que es exactamente el huérfano que `OBS-14` persigue. Una orden
  parcialmente llenada (`filled > 0`) queda **intacta**.

La **costura del instrumento `v2.87`** (`close_tick` en `bolsa_application/replay_oos.py`) se alinea con
el motor y cierra también con `attribute_fills=False`.

## 5. Qué NO cambia

- **No** se degrada ninguna compuerta, **no** se fuerza régimen, **no** se baja ningún umbral.
- La reconciliación de **arranque** mantiene su comportamiento exacto (el parámetro tiene por defecto el
  valor histórico).
- **SIN migración**: Alembic head sigue en `046_fill_reference_mid`.

## 6. Validación en el árbol (antes del RE-SELLO)

| Medición | Resultado |
| --- | --- |
| Crash/recovery PG (`test_crash_recovery_day_process_pg.py`) | **1 passed** (8,32 s) |
| Batería motor + instrumento (7 ficheros) | **105 passed** |
| `ruff check --config pyproject.toml` | limpio |
| Mutaciones `M245`–`M248` (arnés real, filtrado) | **4/4 detectadas**, matriz `248` |

Mutaciones nuevas: **`M247`** (el cierre de turno vuelve a repartir el histórico ⇒ el test nuevo
`test_closing_reconcile_keeps_the_live_tail_of_a_partially_filled_order` lo caza:
`assert 6.0 == 10.0`) y **`M248`** (la costura del replay vuelve a repartir ⇒ lo caza
`test_close_tick_does_not_re_attribute_fills`). `M246` se re-ancló al texto nuevo del cierre: su
fragmento anterior ya no existía, y el arnés falla (a propósito) cuando un fragmento desaparece.

## 7. Límite declarado — el artefacto de `v2.87` exige RE-EJECUCIÓN

El artefacto multianual del instrumento `v2.87` (`operability_runs/replay-oos-durable-cycle-*.json`, no
versionado) se midió con la costura **ANTES** de esta guarda, es decir, con un libro que drenaba la cola
viva de las órdenes parcialmente llenadas en cada tick. **Sus cifras siguen siendo evidencia de
INVESTIGACIÓN de cómo se comportaba aquel modelo, pero NO son reproducibles con el código sellado.**
Se declara aquí y en la evidencia de `v2.87`; la re-ejecución queda como trabajo pendiente y **no** se
usa como evidencia de estrategia ni para mover `P3-2`/`P3-3`.

Lo que el RE-SELLO **sí** certifica es el comportamiento del **motor**: la costura, la guarda y la
reconciliación de cierre están cubiertas por tests herméticos y por el test PG de crash/recovery que
delató la regresión.

## 8. Relevo

- **Estado:** `OBS-14` sigue **cerrada** (con la guarda correcta); `OBS-15` sigue **abierta**.
- **Deuda nueva (instrumento):** re-ejecutar `v2.87` con la costura alineada antes de citar su R.
- **Objeto de auditoría vigente:** tag `v2.88.1-beta` (versión `2.11.1-beta`). El tag `v2.88-beta` queda
  superado y su CI rojo documentado en `evidence/v2.88.1/README.md`.
