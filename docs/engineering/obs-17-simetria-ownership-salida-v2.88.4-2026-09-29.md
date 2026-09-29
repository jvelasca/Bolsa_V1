# `OBS-17` — Simetría del ownership de SALIDA: la reserva de `_v2_reserve_exit` también es de su sesión (`v2.88.4-beta`, `AUTO-MATERIAL-17`, 2026-09-29)

> **Tipo de entrega:** test de costura (hermético) + mutación **`M253`** + informe + evidencia + registros.
> **Objeto:** tag anotado **`v2.88.4-beta`** · **Versión:** `2.11.3-beta` → **`2.11.4-beta`** ·
> **Alembic head:** `046_fill_reference_mid` (**sin migración**) · **Base del diff:** `0038adfc` (= `v2.88.3-beta`).
> **Origen:** **hallazgo de la auditoría externa de `v2.88.3-beta`** (`APROBADO`, 0 bloqueantes), que lo
> señala como **«la siguiente mejora técnica prioritaria»** (§14-§17 del
> [informe de auditoría](./auditoria-v2-88-3-auto-material-16c-2026-09-29.md)).
> **NO se toca el motor.**

---

## 0. Qué es y qué NO es esta entrega

**Es** el cierre de **`OBS-17`**: la pata de **SALIDA** del alta de reservas
(`_v2_reserve_exit`, `auto_simulation_worker.py`) **registra propiedad** (`_v2_owned_reservations`) como
la de entrada, pero **no tenía test ni mutación dedicados**. Se añade **la prueba que faltaba** —la
simetría de ownership— y **la mutación `M253`** que la muerde.

**NO es** un cambio de motor: el diff es **un test + el arnés de mutaciones + docs**. `auto_simulation_worker.py`
queda **idéntico** a `v2.88.3-beta`. **NO** cierra `OBS-14.b`, `OBS-15`, `OBS-16` ni `P3-2`/`P3-3`.

---

## 1. El hueco que cierra (simetría rota del contrato)

El contrato del ciclo de reservas acota el **cierre de turno** por **propiedad**:

```python
await self._v2_reconcile_reservations(
    startup=False,
    attribute_fills=False,
    only_ids=frozenset(self._v2_owned_reservations),   # ← solo lo que ESTA sesión dio de alta
)
```

`_v2_owned_reservations` se alimenta en los **dos** puntos de alta:

| Pata | Punto de alta | Cobertura de prueba |
| --- | --- | --- |
| **ENTRADA** | `_v2_persist_tick_reservations` (línea ~2335) | 🟢 **`M252`** (muerde **6** tests) |
| **SALIDA** | `_v2_reserve_exit` (línea ~2541) | 🔴 **sin test ni mutación** (solo un docstring la mencionaba) |

⇒ El contrato **no estaba simétricamente demostrado**: un defecto de ownership en la **salida** (retirar la
reserva de salida **viva** de otra sesión) es el **mismo fail-OPEN de carrera** que motivó `v2.88.1`/`v2.88.2`,
pero por la pata que **ninguna prueba** guardaba.

---

## 2. El test que faltaba (hermético, sin PostgreSQL)

`apps/api-python/tests/test_auto_v2_durable_cycle.py` — **2 tests nuevos** (14 → **16**):

### `test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it`

Demuestra las **dos caras** de la simetría:

1. **Sesión A** llama `_v2_reserve_exit(...)` → la reserva se persiste (`exit:<ULID>`) **y A registra su
   propiedad** (`res_id in session_a._v2_owned_reservations`); la reserva queda **viva** y es `side="sell"`.
2. **Sesión B** (proceso distinto, sin memoria de A) cierra su turno con
   `only_ids=frozenset(B._v2_owned_reservations)` = ∅ → **B NO puede liberar la reserva de SALIDA de A**:
   sigue `is_live` con `released_qty == 0.0`.
3. **Sesión A** cierra **su** turno con su propia propiedad → **A SÍ la retira** como
   `RELEASED_BY_CANCEL` / `cancel`, y su propiedad se **poda**.

### `test_reserve_exit_without_a_durable_intent_does_not_claim_ownership` (CONTROL)

Con el store de reservas **ausente**, `_v2_reserve_exit` devuelve `None` sin comprometer nada: **no** queda
reserva viva **ni** propiedad huérfana que el cierre pudiera usar contra capital ajeno (fail-closed del libro).

---

## 3. La mutación que la muerde (`M253`)

En `apps/api-python/scripts/v2_44_mutation_audit.py`, matriz **252 → `253`**:

```text
M253 (salida sin propiedad): la reserva de SALIDA se persiste pero NO registra quién es su dueño
  muta:   elimina `self._v2_owned_reservations.add(reservation.reservation_id)` en `_v2_reserve_exit`
  caza:   test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it
```

Simetría de la matriz: **`M252`** acota la pata de **ENTRADA** (6 tests) y **`M253`** la de **SALIDA** (1 test).

---

## 4. Verificación (números exactos)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Costura del ciclo durable | `pytest apps/api-python/tests/test_auto_v2_durable_cycle.py` | **16 passed** (14 + 2 nuevos) |
| `M252` (entrada) | `v2_44_mutation_audit.py --only M252 M253` | **1/1** detectada · **6** tests en rojo |
| `M253` (salida) | ídem | **1/1** detectada · **1** test en rojo (el nuevo) |
| Árbol tras la sonda | ídem (`huella del árbol`) | **intacto**, restauración **byte a byte**, `exit 0` |
| Estilo (comando EXACTO del CI) | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| Matriz COMPLETA | `v2_44_mutation_audit.py` | **`253/253`** medidas, árbol **intacto**, `exit 0` |
| Diff del motor | `git diff v2.88.3-beta..HEAD -- packages/py apps/api-python/src` | **vacío** |

---

## 5. Límites declarados

- **NO** se toca el motor: el cambio es **test + arnés + docs**. La propiedad de la salida **ya existía** en
  código desde `v2.88.2`; lo que faltaba era su **prueba adversarial**.
- El test es **hermético** (sin PostgreSQL): ejercita la costura de reconciliación con stores **en memoria**.
  La corrida **real** de concurrencia/recovery (3 sesiones, crash) la acredita el job `lifecycle-pg` del CI
  del tag, **no** este test.
- **NO** cierra `OBS-14.b` (barrido de arranque sin ventana de gracia), **`OBS-15`** (techo de 1000
  `APPLIED`), **`OBS-16`** (costuras manuales) ni `P3-2`/`P3-3`. Sigue **vigente** el orden de prioridad del
  auditor: tras `OBS-17`, **`OBS-14.b`** y **volver a PAPER real**.

---

## 6. CI del tag (POST-TAG por construcción)

`Release tag CI` **solo corre al empujar**, así que la cita **no puede** vivir dentro del tag (patrón
`OBS-3`/`OBS-4`): se registra **después**, en `main`. Esperado sobre este objeto (motor idéntico a
`v2.88.3-beta` + 2 tests puros nuevos): job `python` **`3042 passed, 37 skipped`** (los `3077` recogidos de
`v2.88.3` + **2**), con los **mismos `37` skips**. **Se cita el run, no se hereda.**

---

## 7. Evidencia y registros

- **Evidencia cruda:** [`evidence/v2.88.4/README.md`](./evidence/v2.88.4/README.md).
- **Registros:** `PROJECT_STATE.md` · `engineering-index-2026-08-03.md` (entrada 187) ·
  [`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) (`OBS-17` → **CERRADA**).
- **Origen:** [`auditoria-v2-88-3-auto-material-16c-2026-09-29.md`](./auditoria-v2-88-3-auto-material-16c-2026-09-29.md).
- **Relevo anterior:** [`obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md`](./obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md).
