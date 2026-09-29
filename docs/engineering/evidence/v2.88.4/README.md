# Evidencia cruda — simetría del ownership de SALIDA (`v2.88.4`, `AUTO-MATERIAL-17`, 2026-09-29)

Resumen **verificable** del cierre de `OBS-17`: la pata de **SALIDA** del alta de reservas
(`_v2_reserve_exit`) pasa a tener **test + mutación** como la de ENTRADA. Las cifras están transcritas de
las corridas, sin edición.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-17` (`v2.88.4`) — simetría del ownership de SALIDA (`OBS-17`) + arnés + docs |
| Versión de paquete | `2.11.3-beta` → **`2.11.4-beta`** |
| Tag (lo crea el propietario) | **`v2.88.4-beta`** (anotado) |
| Base del diff | **`0038adfc`** (= `v2.88.3-beta`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Diff del motor | **vacío** (`packages/py` + `apps/api-python/src` idénticos a `v2.88.3-beta`) |
| Contenido del sello | 1 test de costura (2 tests nuevos) + 1 mutación (`M253`) + `CHANGELOG` + `package.json` + docs |

## 1. El hueco que se cierra

El cierre de turno acota la retirada por **propiedad**:
`only_ids=frozenset(self._v2_owned_reservations)`. `_v2_owned_reservations` se alimenta en los **dos** puntos
de alta:

| Pata | Punto de alta | Prueba adversarial |
| --- | --- | --- |
| ENTRADA | `_v2_persist_tick_reservations` | 🟢 `M252` (6 tests) |
| **SALIDA** | `_v2_reserve_exit` | 🔴 **ninguna** → **cerrado aquí** |

Es el **tipo** de defecto que motivó `v2.88.1`/`v2.88.2` (fail-OPEN de carrera): la evidencia durable no
distingue "orden muerta" de "orden que OTRA sesión aún no ha emitido"; el único discriminador es la
**propiedad**.

## 2. Tests nuevos (`test_auto_v2_durable_cycle.py`, 14 → 16)

```
### test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it
  - A: _v2_reserve_exit -> reserva viva (exit:<ULID>, side=sell) + A registra su PROPIEDAD
  - B (sin memoria de A) cierra su turno -> NO puede liberar la reserva de SALIDA de A
        (sigue is_live, released_qty == 0.0)
  - A cierra SU turno con su propiedad -> SÍ la retira (RELEASED_BY_CANCEL / cancel) y su propiedad se poda

### test_reserve_exit_without_a_durable_intent_does_not_claim_ownership  (CONTROL)
  - sin store de reservas: _v2_reserve_exit -> None, sin reserva viva y sin propiedad huérfana (fail-closed)
```

Corrida del fichero completo:

```
$ uv run --no-sync python -m pytest apps/api-python/tests/test_auto_v2_durable_cycle.py -q -p no:cacheprovider
................                                                         [100%]
16 passed in 1.03s
```

## 3. Mutación `M253` (matriz `252` → `253`)

```
M253 (salida sin propiedad): la reserva de SALIDA se persiste pero NO registra quién es su dueño
  muta: elimina `self._v2_owned_reservations.add(reservation.reservation_id)` en `_v2_reserve_exit`
  caza: test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it
```

Filtrada (`--only M252 M253`), con la huella del árbol:

```
filtro de rotulos: --ONLY, M252, M253 (2/253)

### M252 (alta sin propiedad): el tick persiste la reserva pero NO registra quien es su dueno
  rojo en: test_book_does_not_drip_over_n_ticks_when_the_cycle_is_durable,
           test_closing_reconcile_does_not_touch_another_sessions_reservation,
           test_closing_reconcile_keeps_captured_unapplied_capital_in_flight,
           test_orphan_reservation_is_released_as_cancel_at_tick_close,
           test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn,
           test_two_real_turns_do_not_drip_the_book_between_them
  restaurado byte a byte: si

### M253 (salida sin propiedad): la reserva de SALIDA se persiste pero NO registra quien es su dueno
  rojo en: test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it
  restaurado byte a byte: si

=== huella del arbol ===
  intacto: la sonda no altero el arbol
  medidas: 2/2 (ninguna se quedo sin fragmento)
```

Matriz **COMPLETA** (rotulada por el run; cifra transcrita de `logs/mutation-harness-obs17-253.log`):

| Mutación | Detectada | Test(s) que la cazan |
| --- | --- | --- |
| `M252` (entrada sin propiedad) | ✅ | 6 (ciclo durable) |
| **`M253` (salida sin propiedad)** | ✅ | **1** (el nuevo, de simetría) |
| **Matriz COMPLETA** | **`253/253`** medidas · árbol **intacto** · `exit 0` | — |

## 4. Compuertas

```
$ uv run ruff check packages/py apps/api-python --config pyproject.toml
All checks passed!

$ git diff v2.88.3-beta..HEAD -- packages/py apps/api-python/src      # vacío (motor intacto)
```

## 5. Límites declarados

- **NO** se toca el motor: el diff es un test + el arnés + docs. La propiedad de la salida **ya existía** en
  código desde `v2.88.2`; lo que faltaba era su **prueba adversarial**.
- El test es **hermético** (sin PostgreSQL): la corrida **real** de concurrencia/recovery (3 sesiones,
  crash real, golden day) la acredita el job `lifecycle-pg` del CI del tag, **no** este test.
- **NO** cierra `OBS-14.b`, `OBS-15`, `OBS-16` ni `P3-2`/`P3-3`.

## 6. CI del tag — POST-TAG (patrón `OBS-3`/`OBS-4`)

`Release tag CI` solo corre **al empujar**, así que su cita **no puede** vivir dentro del tag: **pendiente
de medir y citar en `main`** tras el push. Esperado sobre este objeto (motor idéntico a `v2.88.3-beta` +
**2** tests puros nuevos): job `python` **`3042 passed, 37 skipped`** (los `3077` recogidos de `v2.88.3` +
**2**) y los **mismos `37` skips**. **Se cita el run, no se hereda.**
