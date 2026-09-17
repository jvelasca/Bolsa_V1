# Arranque del auditor — V2.42 / AUTO-2 · Position Lifecycle FSM & Real Protection (slice 2a) (`1.67.0-beta`)

> **Para quién es esto:** la persona (o el agente) que audita `v2.42-beta` sin acceso al entorno de
> desarrollo. Orden de lectura, afirmaciones verificables, mapa de código, comandos y preguntas abiertas.
> **Pack completo:** [`audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md`](./audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md).
> **Base sobre la que se asienta:** [`audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md`](./audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md)
> (`AUTO-1`, capital reservado con identidad; tag `v2.41-beta`) y
> [`audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md`](./audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md)
> (`POSITION = Σ APPLIED`).
> **Hoja de ruta:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §4.
> **Estado de la evidencia:** implementado, medido **en local** y **sellado**. Commit de fase `6e53294f`
> (17 ficheros, `+2914/−99`), commit de arreglo de test `35e38c24` (1 fichero, `+59/−1`) y tag anotado
> **`v2.42-beta` → `35e38c24`**; los runs de CI (con el rojo del commit de fase declarado) están en §8.1
> del pack.

**Bump:** `1.66.0-beta` → `1.67.0-beta`. **Migración: NINGUNA** (Alembic head sigue en
`042_portfolio_reservations`; el estado vive en el JSONB `sim_auto_positions.position_state`).

**Alcance del slice:** escribe **2a** (FSM + `PROTECT`/trailing real + retirada de `ProtectionConfig`
como motor + unificación T1/T2). **Fuera (2b):** `TIME_EXIT`, `THESIS_EXIT`, ATR real, horizonte de
tiempo. Es importante para auditar: el **criterio de salida completo** de `AUTO-2` **no** se declara
cerrado.

---

## 1. Qué afirma esta versión (y qué no)

**Afirma**

1. Existe un **FSM de posición explícito** (`position_lifecycle.py`): 13 estados, 14 eventos y una tabla
   de transiciones **explícita**; una transición no listada **no avanza** y devuelve motivo.
2. El estado se **persiste** en el JSONB `position_state` (`lifecycleState`) y **sobrevive** al proceso
   (medido en PostgreSQL real). Un estado desconocido o inconsistente con el hecho de cantidad se
   rehidrata como `RECONCILIATION_REQUIRED` + `PROTECTION_MISSING`, **nunca** como "sin protección".
3. El `stop_update` que propone la gestión **deja de descartarse**: el stop sube (H2: nunca empeora) y se
   **persiste aunque el tick no venda**. El trailing se mide **en R** (`highWatermark − r ×
initial_risk`) y sólo se arma **tras T1**.
4. **Ningún `PROTECT` queda mudo**: ratchet aplicado, rechazado por empeorar y petición sin stop se
   journalizan (y también la transición rechazada).
5. La **política T1/T2 es única** (MODERATE 0.3/0.3) en los dos caminos AUTO: `template_id=None` ya no
   cae al fallback 0.5/1.0.
6. Hay **un solo motor** de decisión de protección (`protection_compat.py`) con dos modos declarados
   (`pct` para compat flag-off reproduciendo `v2.39.x`, `r` para V2); `ProtectionConfig` es un value
   object que delega.
7. Las posiciones **adoptadas** sin estado verificable se **declaran degradadas** con atención alta y
   conservan el mejor stop conocido (o declaran la ausencia de protección sin inventar un número).
8. **Ninguna salida protectora se veta** por reconciliación degradada; el límite está declarado: tomar
   beneficio sí espera.

**NO afirma**

- Que existan `TIME_EXIT`/`THESIS_EXIT` ni ATR real (deuda de **2b**).
- Que la dualidad de superficies de estado de posición esté resuelta: `sim_auto_positions` (autoridad del
  camino AUTO) y `position_states` (ADR-033) siguen coexistiendo.
- Que `ProtectionConfig` haya desaparecido del código (sigue exportada como value object).
- Que exista un `ProtectionPlan` por estrategia end-to-end: se unificó el **valor** y el **dueño** de la
  política T1/T2, no el contrato completo del roadmap.
- **Nada sobre runs anteriores a `35e38c24`**: el rojo del commit de fase en `auto-v2-durable-pg` está
  declarado (lotería de la cola SIM del test durable V2, no regresión; el mismo commit pasó `5/5` en
  `main`), y `Release tag CI` del tag re-apuntado es **GREEN** (§8.1 del pack).

---

## 2. Qué cierra exactamente (y de dónde venía)

| Deuda / agujero declarado antes                                                                                | Cómo lo cierra este slice                                                                                                          |
| -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `position_manager_package` **descartaba** el `stop_update`: `current_stop` congelado en el valor de nacimiento | `position_manager_stop_update` + ratchet aplicado (H2) y persistido en `_v2_apply_stop_update`, **haya o no orden**                |
| Un `PROTECT` colapsaba a `hold → hold_no_op` mudo                                                              | Journal de los tres desenlaces + `POSITION_LIFECYCLE_REASONS`                                                                      |
| Ciclo de vida **derivado** de cuatro valores, sin `ENTRY_PENDING` ni T1 como transición ni degradación         | `position_lifecycle.py` (estados, eventos, tabla explícita, `advance_lifecycle` fail-closed)                                       |
| Adopción de posición sin plan durable **sin declarar** la incertidumbre de protección                          | `_v2_degrade_adoption` (`RECONCILIATION_REQUIRED` + `PROTECTION_MISSING` + `source`, atención alta, stop de emergencia conservado) |
| **Dos motores** de protección incomunicados                                                                    | `protection_compat.py` (modos `pct`/`r`) + traducción de motivos al FSM                                                            |
| `template_id=None ⇒ 0.5/1.0` (dos fracciones distintas para el mismo T1)                                       | `position_decision` resuelve **siempre** `resolve_exit_policy(template_id)`                                                        |
| `CRITICAL` degradaba a `REVIEW` incluso las salidas protectoras                                                | `_PROTECTIVE_EXIT_REASONS` manda sobre `CRITICAL` (sólo las protectoras)                                                           |

---

## 3. Dónde mirar el código (mapa mínimo)

| Qué                                                                        | Dónde                                                                                                                                                                                                                            |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FSM: estados, eventos, tabla, transición fail-closed, trailing en R        | `packages/py/analytics/src/bolsa_analytics/cognitive/position_lifecycle.py`                                                                                                                                                      |
| `PositionState` + `lifecycleState`, tipados, rehidratación, high watermark | `packages/py/analytics/src/bolsa_analytics/cognitive/position_state.py`                                                                                                                                                          |
| Política única + exención de salidas protectoras                           | `packages/py/analytics/src/bolsa_analytics/cognitive/position_decision.py`                                                                                                                                                       |
| Anchura del trailing en R + `resolve_exit_policy`                          | `packages/py/analytics/src/bolsa_analytics/cognitive/exit_policy.py`                                                                                                                                                             |
| Surface del stop y journal de gestión                                      | `packages/py/application/src/bolsa_application/auto_v2_entry.py` (`position_manager_stop_update`, `plan_v2_position_outcome`, `build_position_management_journal_entry`)                                                         |
| `template_id` en el ciclo AUTO                                             | `packages/py/application/src/bolsa_application/auto_investment_system.py` (~L424)                                                                                                                                                |
| Motor único de protección legacy + traducción al FSM                       | `packages/py/application/src/bolsa_application/protection_compat.py`                                                                                                                                                             |
| Reason codes de lifecycle/ratchet/protección                               | `packages/py/application/src/bolsa_application/auto_reason_codes.py` (`POSITION_LIFECYCLE_REASONS`)                                                                                                                              |
| Worker: ratchet, FSM del ciclo, adopción degradada, persistencia           | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (`_v2_position_package`, `_v2_apply_stop_update`, `_v2_track_entry`, `_v2_track_reduce`, `_v2_adopt_position`, `_v2_degrade_adoption`, `_v2_durable_state`) |
| Tests herméticos (FSM / aplicación)                                        | `packages/py/analytics/tests/test_position_lifecycle.py`, `packages/py/application/tests/test_auto_v2_lifecycle_stop.py`                                                                                                         |
| Test PG (FSM durable)                                                      | `apps/api-python/tests/test_auto_v2_lifecycle_pg.py`                                                                                                                                                                             |
| Tests de worker (ratchet / reinicio / PROTECT nunca mudo)                  | `apps/api-python/tests/test_auto_v2_worker_integration.py`                                                                                                                                                                       |
| Cobertura legacy del shim flag-off (9 tests, sin borrar)                   | `apps/api-python/tests/test_auto_simulation_worker.py`, `apps/api-python/tests/test_a9_1_durability_integrity.py`                                                                                                                |

---

## 4. Cómo verificar (comandos listos)

```bash
# 1) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_lifecycle.py \
               packages/py/application/tests/test_auto_v2_lifecycle_stop.py \
               apps/api-python/tests/test_auto_v2_worker_integration.py -q

# 2) Los 9 tests legacy que siguen cubriendo el shim flag-off (deben seguir verdes)
uv run pytest apps/api-python/tests/test_auto_simulation_worker.py \
               apps/api-python/tests/test_a9_1_durability_integrity.py -q

# 3) PG real (FSM durable). Un skip es FALLO.
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q -rs
AUTO_V2_DURABLE_PG_REQUIRED=1 AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest \
    apps/api-python/tests/test_auto_v2_durable_pg.py apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q

# 4) Estático con la invocación EXACTA de CI
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
           packages/py/application/src apps/api-python/src --follow-imports=silent
```

Cifras medidas en el árbol del slice: **46 herméticos** (29 + 17), **35** de worker, **9** legacy,
**3 PG** de lifecycle, **36** de la batería durable PG, **141** del bloque PG del job `lifecycle-pg`,
**2825** de `pytest packages/py` (1 skipped de Ollama, 1 xfailed). Las del job `quality` dependen del
**entorno**: en CI (limpio) da **1869 passed, 38 skipped** (run `35214904914`); las **1903 passed** que
aparecen en otros documentos se midieron con `DATABASE_URL` y los seis `*_PG_REQUIRED` exportados, así
que incluían suites gated que en CI se skipean (§8.1 del pack).

### Mutaciones sugeridas (deben poner suites en rojo)

| Mutación                                                  | Rojo esperado |
| --------------------------------------------------------- | ------------- |
| `apply_lifecycle_event` acepta transiciones no listadas   | **3**         |
| La rehidratación no degrada un estado inconsistente       | **2**         |
| `compute_trail_stop` pierde el clamp nunca-empeorar       | **1**         |
| El worker descarta el `stop_update`                       | **3**         |
| La reconciliación `CRITICAL` veta las salidas protectoras | **2**         |
| `_v2_track_reduce` no arma el trailing con el T1          | **1**         |
| La adopción sin estado verificable no se degrada          | **1**         |
| Vuelve el fallback 0.5/1.0 sin `template_id`              | **3**         |
| El shim legacy evalúa T1 antes que el trailing            | **2**         |
| Un `PROTECT` sin stop utilizable queda mudo               | **1**         |
| El trailing se considera armado antes de T1               | **3**         |

(Las once están **medidas** en el §4 del pack, con el rojo exacto y el fichero que lo delata.)

---

## 5. Preguntas abiertas que el auditor debería intentar romper

1. **`lifecycleState` vs el hecho de cantidad**: la rehidratación degrada `CLOSED` con posición viva
   ¿pero qué pasa con `PARTIAL_EXIT` cuando la cantidad **sube** (una compra de reentrada en el mismo
   instrumento)? ¿Debería degradar también?
2. **Doble superficie**: `position_states` (ADR-033) y el JSONB `position_state` pueden **divergir**.
   ¿Existe algún consumidor que lea la primera para decidir gestión? (El pack afirma que el camino AUTO
   usa la segunda; no que nadie más mire la primera.)
3. **Trailing sin marks**: una posición sin ticks no tiene `highWatermark` y no ratchea. ¿Es aceptable
   "proteger solo si hay mercado", o debería el pico inferirse de otra evidencia (fill, close)?
4. **`RECONCILED`**: la salida de la degradación exige un estado resuelto verificado; hoy el worker no
   emite `RECONCILED` (sólo lo hacen los hechos observables). ¿Quién debería resolver explícitamente?
5. **La exención protectora** se define por motivo (`STRUCTURAL_STOP`, `TRAIL`, `PORTFOLIO_RISK`) y vive
   en `position_decision`. ¿Puede un motivo nuevo (2b: `TIME_STOP`) quedar **vetado** por olvido al
   añadirlo a `ExitReason` sin añadirlo aquí?
6. **`ProtectionConfig` como value object**: ¿queda alguna ruta en el camino `AUTO_ENGINE_SIM_V2=1` que
   siga leyendo sus umbrales? (El pack dice que su lógica vive en `protection_compat`; el auditor debería
   buscar lecturas residuales.)
