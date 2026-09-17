# Audit pack — V2.42 / AUTO-2 · Position Lifecycle FSM & Real Protection (slice 2a) (`1.67.0-beta`)

> **Ámbito:** la gestión de posición deja de ser un **derivado implícito** (`PositionStatus` de cuatro
> valores + `exitStatus` + estados de leg sueltos) y pasa a ser una **máquina de estados explícita y
> persistida** en `sim_auto_positions.position_state` (JSONB). Además, el **stop que la gestión proponía
> deja de descartarse**: `position_manager_package` sólo leía `order_action`/`order_qty`, así que
> `current_stop` quedaba **congelado en el valor de nacimiento** (ni break-even ni trailing existían en
> AUTO) y un `PROTECT` colapsaba a `hold → hold_no_op` **mudo**. El slice instala ratchet de stop real
> (trailing **en R**), degradación fail-closed de las adopciones sin estado verificable, política T1/T2
> **única** (MODERATE 0.3/0.3) y un **motor único** de decisión de protección (`pct` legacy / `r` V2).
> **Bump:** `1.66.0-beta` → `1.67.0-beta`. **Migración: NINGUNA** (head sigue en
> `042_portfolio_reservations`).
> **Estado:** implementado, verificado y **sellado**. Commit de fase `6e53294f` (17 ficheros,
> `+2914/−99`), commit de arreglo de test `35e38c24` (1 fichero, `+59/−1`) y tag anotado **`v2.42-beta`
> → `35e38c24`**, con los runs de CI de §8.1 (incluido el rojo declarado del commit de fase).
> **Auditoría externa post-sellado (2026-09-17):** ningún P0; el sello se confirma y 5 mutaciones se
> reproducen con los rojos exactos. **7 hallazgos de código** (afirmaciones del §1 más absolutas que el
> código) quedan declarados en **§9** como criterio de aceptación de **2b**, junto con la **errata** de
> las cifras de este documento.
>
> **Especificación de la fase:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §4
> (`AUTO-2` — Position Manager 2.0: objetivo, invariante, estados, gate y criterio de salida).
> **Alcance real de este slice (2a):** FSM + `PROTECT`/trailing real + retirada de `ProtectionConfig`
> como motor + unificación T1/T2. **Fuera (2b):** `TIME_EXIT`, `THESIS_EXIT`, ATR real, horizonte de
> tiempo.
> Punto de partida: [`audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md`](./audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md)
> (`AUTO-1`, tag `v2.41-beta`).

---

## 1. Qué afirma esta versión (y qué no)

**Afirma**

1. **Una posición siempre tiene un estado persistido y verificable.** El FSM (`PositionLifecycleState`)
   vive en el JSONB `position_state` (`lifecycleState`) y viaja con la posición a través del espejo
   durable; `status` sigue siendo el **hecho de cantidad/break-even** y el FSM es **aditivo** (se
   proyecta sobre `derive_position_status` sin tocar a los ~30 lectores de `.status`).
2. **Un estado no verificable degrada, nunca se interpreta como "sin protección".** Un valor
   desconocido, o uno inconsistente con el hecho de cantidad (p. ej. `CLOSED` con posición viva), se
   rehidrata como `RECONCILIATION_REQUIRED` + `PROTECTION_MISSING`, y se journaliza con atención alta.
3. **Las transiciones no listadas se rechazan.** `ALLOWED_TRANSITIONS` es una tabla explícita;
   `apply_lifecycle_event` es fail-closed: no avanza, devuelve motivo (`lifecycle_transition_rejected`)
   y el llamante debe journalizarlo. La familia degradada **no es terminal**: un hecho observable (fill,
   T1, ratchet, salida) la re-verifica por la misma tabla. **Corregido por la auditoría externa:** la
   afirmación de que `RECONCILED` "exige un estado resuelto **verificado**" es **falsa** hoy —
   `apply_lifecycle_event` lo acepta desde **cualquier** estado sin comprobar coherencia con la cantidad
   (hallazgo **H-1** del §9). El pack afirma la intención, no el hecho; el candado es deuda de 2b.
4. **El stop propuesto deja de descartarse y sube de verdad.** `position_manager_stop_update` surface el
   `stop_update` de un `PROTECT`; el worker lo aplica con `apply_position_current_stop` (**H2:
   nunca-empeorar**) y lo **persiste aunque no haya orden** (un ratchet no vende). Sin esa persistencia el
   tick siguiente parte del stop viejo.
5. **Ningún `PROTECT` mudo.** Se journaliza el ratchet aplicado, el rechazado por empeorar y la petición
   sin stop utilizable (`protect_requested`), y también la transición rechazada. **Corregido por la
   auditoría externa:** el absoluto es falso en el estado estacionario del trailing (mismo stop, mismo
   estado ⇒ ni ratchet ni `protect_requested`; solo el `hold_no_op` genérico) — hallazgo **H-2** del §9.
   Lo que sí se sostiene: **todo `PROTECT` con efecto deja traza**.
6. **Trailing en R.** `compute_trail_stop = highWatermark − trail_distance_r ×
initial_risk` (long), con anchura por plantilla (tight 0.75 / medium 1.0 / wide 1.25: la tabla
   `TRAIL_DISTANCE_R_BY_WIDTH` **preexistía** en `exit_policy.py`; lo nuevo es `compute_trail_stop` y su
   anclaje al pico persistido). Sin `initial_risk` **no se inventa** un porcentaje del precio.
   **Corregido por la auditoría externa:** (a) "sólo tras T1" no es exacto —`PARTIAL_EXIT` también lo
   arma, así que una reducción **sólo de T2** lo activa sin T1 (**H-3**)— y (b) "sin pico ⇒ `None`" es
   falso: sin `trailing.highWatermark` cae al precio de entrada y devuelve un trailing sintético
   (**H-4**).
7. **El pico tiene memoria propia y durable.** `apply_position_mark` es el único writer de
   `trailing.highWatermark`; el ratchet se calcula sobre la posición **marcada** y el reinicio continúa
   desde el `highWatermark` persistido (medido en PostgreSQL real).
8. **Una sola política T1/T2 en los dos caminos AUTO**: `resolve_exit_policy(template_id)` (MODERATE
   0.3/0.3) sustituye al fallback silencioso 0.5/1.0 que se activaba cuando no había `template_id`.
9. **Un solo motor de protección.** `protection_compat.py` decide con dos modos declarados (`pct` para
   compat flag-off reproduciendo `v2.39.x`, `r` para V2 delegando en analytics) y traduce el vocabulario
   legacy al del FSM. `ProtectionConfig` queda como **value object** que delega; el worker deja de usar
   su `exit_reason`/`exit_fraction` como motor.
10. **Ninguna salida protectora se veta** por reconciliación degradada o medición incompleta (stop
    rebasado, trailing alcanzado, riesgo de cartera siguen vendiendo con el libro sin cuadrar). El
    límite queda declarado: **tomar beneficio sí espera** al veredicto.

**NO afirma**

- Que `TIME_EXIT`/`THESIS_EXIT` existan: siguen fuera del FSM (asignados a **2b**), así que el
  **criterio de salida completo** de `AUTO-2` (§4 del roadmap) **no** se cierra en este slice.
- Que exista **ATR real**: el camino de adopción y el fallback legacy siguen usando el ATR aproximado
  (`precio × 2 %` × multiplicador) — deuda declarada de 2b.
- Que la política T1/T2 se pueda **configurar por estrategia** end-to-end (`Strategy → TradePlan →
ProtectionPlan → PositionState → PositionManager`): se unifica el **valor** (MODERATE) y el dueño
  (`resolve_exit_policy`), no se instala el `ProtectionPlan` del roadmap.
- Que la dualidad `sim_auto_positions` vs `position_states` (ADR-033) esté resuelta: está **declarada**
  (§5.2).
- Nada sobre runs **anteriores** a `35e38c24`: el rojo del commit de fase en `auto-v2-durable-pg` está
  declarado en §8.1, no escondido (loteria de la cola SIM; el mismo commit había pasado 5/5 en `main`).

---

## 2. Punto de partida verificado (lo que este slice cierra)

| Deuda / agujero medido antes del slice                                                                                                                 | Cómo lo cierra AUTO-2 (2a)                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `position_manager_package` **descartaba** `result.stop_update`: `current_stop` quedaba en el valor de nacimiento                                       | `position_manager_stop_update` (surface) + ratchet aplicado con H2 y persistido por `_v2_apply_stop_update` **aunque no haya orden**            |
| Un `PROTECT` colapsaba a `hold → hold_no_op` **mudo** (ni traza ni stop)                                                                               | Journal de los tres desenlaces (`stop_ratchet_applied`, `stop_ratchet_rejected`, `protect_requested`) + transición rechazada declarada          |
| El ciclo de vida era un **derivado** (`OPEN`/`PARTIAL`/`PROTECTED`/`CLOSED`): sin `ENTRY_PENDING`, sin T1 como transición y sin estados de degradación | `position_lifecycle.py`: 13 estados, 14 eventos, tabla explícita y `advance_lifecycle` fail-closed                                              |
| La **posición adoptada** sin plan durable no declaraba que su protección era incierta                                                                  | `_v2_degrade_adoption`: `RECONCILIATION_REQUIRED` + `PROTECTION_MISSING` (+ `source`), journal con atención alta, stop de emergencia conservado |
| **Dos motores** de protección que no hablaban entre sí (`ProtectionConfig` en % y el `ExitPlan`/`current_stop` en geometría)                           | `protection_compat.py` (dueño único, modos `pct`/`r`) + traducción de motivos al FSM; `ProtectionConfig` pasa a value object                    |
| `template_id=None ⇒ policy=None ⇒ fallback 0.5/1.0`: los dos caminos AUTO cerraban T1 con fracciones **distintas**                                     | `position_decision` resuelve **siempre** `resolve_exit_policy(template_id)` (MODERATE 0.3/0.3)                                                  |
| Reconciliación `CRITICAL` degradaba **cualquier** decisión a `REVIEW`, incluidas las salidas protectoras                                               | `_PROTECTIVE_EXIT_REASONS` (`STRUCTURAL_STOP`, `TRAIL`, `PORTFOLIO_RISK`) mandan sobre `CRITICAL`; el resto sigue esperando                     |

Invariantes que **no** se tocan: `AUTO ⇒ SIMULATED` (cero caminos LIVE nuevos), `POSITION = Σ APPLIED`,
`exit_qty <= materialized_qty`, fail-closed de reservas y libros, migraciones aditivas (aquí
**ninguna**), long-only y `PAPER_D_EXECUTE` off.

---

## 3. Matriz afirmación → código → test

### a) El FSM (analytics puro)

| Afirmación                                                                             | Código                                                              | Test                                                                                           |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Estados, eventos y tabla de transiciones son contrato público y **explícito**          | `position_lifecycle.py` (`LIFECYCLE_EVENTS`, `ALLOWED_TRANSITIONS`) | `packages/py/analytics/tests/test_position_lifecycle.py`                                       |
| Una transición no listada **no avanza** y devuelve `lifecycle_transition_rejected`     | `apply_lifecycle_event`                                             | idem (`test_invalid_transitions_are_rejected_without_advancing`)                               |
| El **producto cartesiano** estado × evento es total y fail-closed                      | `_TRANSITIONS` (mapa total)                                         | idem (`test_cartesian_product_is_total_and_fail_closed`)                                       |
| Un evento **desconocido** no degrada el estado: se rechaza y el estado se conserva     | `_coerce_event` + rechazo con estado válido                         | idem (`test_unknown_event_is_rejected_and_keeps_state`)                                        |
| Un **estado desconocido** degrada a `RECONCILIATION_REQUIRED` (nunca "sin protección") | rama `current is None`                                              | idem (`test_unknown_state_degrades_to_reconciliation_required`)                                |
| `RECONCILED` sólo sale de la degradación con estado resuelto **verificado**            | rama `RECONCILED`                                                   | idem (`test_reconciled_requires_a_resolved_state`)                                             |
| Los degradados **re-verifican** con un hecho observable (fill, T1, ratchet, salida)    | `_MANAGEMENT_EVENTS` en los estados degradados                      | idem (`test_degraded_states_reverify_with_observable_facts`)                                   |
| `advance_lifecycle` rechazado deja la posición **intacta**                             | `advance_lifecycle` (early return)                                  | idem (`test_advance_lifecycle_rejected_leaves_position_untouched`)                             |
| La proyección legacy no inventa estados y respeta la precedencia declarada             | `derive_lifecycle_state`                                            | idem (`test_derive_lifecycle_t1_and_partial`, `test_persisted_lifecycle_wins_over_projection`) |

### b) `PositionState`: estado tipado, rehidratación y pico

| Afirmación                                                                                            | Código                                                                     | Test                                                                                                                                                                                            |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lifecycleState` se emite **sólo** si no es `None` (canario de igualdad exacta preservado)            | `PositionState.to_dict`                                                    | `packages/py/application/tests/test_sim_durable_v2_state.py` (pins `47`, `92`) sin cambios                                                                                                      |
| El blob round-trip conserva `lifecycleState`, `trailing` y `protection_state` **tipados**             | `position_state_from_dict` + `trailing_state_dict`/`protection_state_dict` | `test_position_lifecycle.py` (`test_lifecycle_state_survives_roundtrip`)                                                                                                                        |
| Un estado **inconsistente con la cantidad** (p. ej. `CLOSED` con posición viva) degrada al rehidratar | `lifecycle_state_is_consistent` + `forced_degradation`                     | idem (`test_inconsistent_lifecycle_degrades_on_rehydration`) — **salvedad H-6 del §9**: con la clave `lifecycleState` **ausente o `null`** (y `status=CLOSED` con cantidad viva) **no** degrada |
| Un estado degradado **persistido** conserva su `protection_state` rico (auditoría, no stub genérico)  | `forced_degradation` sólo cuando lo impone la rehidratación                | idem                                                                                                                                                                                            |
| `status` sigue siendo el hecho de cantidad/break-even y el FSM se **proyecta** encima                 | `derive_position_status`                                                   | `packages/py/analytics/tests/test_position_state.py` (sin cambios)                                                                                                                              |
| `apply_position_mark` es el único writer del extremo favorable (`trailing.highWatermark`)             | `apply_position_mark`                                                      | `test_position_lifecycle.py` (`test_trail_stop_in_r_after_t1`)                                                                                                                                  |

### c) Trailing en R y política única (analytics puro)

| Afirmación                                                                          | Código                                                     | Test                                                                                                                                              |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| La anchura del trailing está **declarada** por plantilla (0.75/1.0/1.25 R)          | `TRAIL_DISTANCE_R_BY_WIDTH`, `trail_distance_r_from_width` | `packages/py/analytics/tests/test_position_lifecycle.py`                                                                                          |
| `compute_trail_stop = highWatermark − r × initial_risk` (long) y simétrico en corto | `compute_trail_stop`                                       | idem (`test_trail_stop_in_r_after_t1`)                                                                                                            |
| El trailing **nunca empeora** el stop vigente (H2)                                  | `stop_worsens` ⇒ devuelve el stop vigente                  | idem (`test_trail_stop_never_worsens`)                                                                                                            |
| Sin `initial_risk` ⇒ `None` (no se inventa distancia)                               | guardas de `compute_trail_stop`                            | idem (`test_trail_stop_not_armed_before_t1`) — **con la salvedad H-3/H-4 del §9**: `PARTIAL_EXIT` arma sin T1 y sin pico cae al precio de entrada |
| `template_id=None` ⇒ MODERATE 0.3/0.3 (no 0.5/1.0)                                  | `position_decision` (`resolve_exit_policy` siempre)        | `packages/py/application/tests/test_auto_v2_lifecycle_stop.py` (`test_t1_reduce_is_moderate_without_template`)                                    |
| Sólo las salidas **protectoras** mandan sobre la reconciliación `CRITICAL`          | `_PROTECTIVE_EXIT_REASONS` + `_action_from_plan`           | idem (`test_stop_hit_still_sells_with_recon_drift`, `test_take_profit_still_waits_for_recon`)                                                     |

### d) El stop deja de descartarse y el shim legacy (application)

| Afirmación                                                                             | Código                                                      | Test                                                                                                                                                                                                          |
| -------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Un `PROTECT` no emite orden (spine intacto) pero **surface** su stop                   | `plan_v2_position_outcome` + `position_manager_stop_update` | `test_auto_v2_lifecycle_stop.py` (`test_position_manager_stop_update_surfaces_protect`)                                                                                                                       |
| `None`/NaN/0/negativos **no** son un stop utilizable (fail-closed)                     | `position_manager_stop_update`                              | idem (`test_position_manager_stop_update_rejects_garbage`) — **salvedad H-5 del §9**: `+inf` **sí** pasa y revienta con `OverflowError` (los `_finite*` no usan `math.isfinite`)                              |
| El shim `pct` reproduce los cuatro motivos legacy `v2.39.x` con sus umbrales exactos   | `protection_compat.protection_exit_reason`                  | idem (`test_legacy_policy_reproduces_v239_thresholds`)                                                                                                                                                        |
| El shim es **fail-closed** (sin activar / sin posición / precios inválidos ⇒ `None`)   | idem                                                        | idem (`test_legacy_policy_fail_closed`)                                                                                                                                                                       |
| `ProtectionConfig` **no decide**: su lógica vive en el módulo y delega                 | `ProtectionPolicy.exit_reason`/`exit_fraction`              | idem (`test_legacy_policy_methods_delegate_to_module`)                                                                                                                                                        |
| El motivo legacy se **traduce** al evento del FSM sin volver a decidir                 | `lifecycle_event_for_protection_reason`                     | idem (`test_legacy_reason_translates_to_fsm_event`)                                                                                                                                                           |
| Los 5 tests de `A9.1` portados a **V2=1** (R, high-watermark, T1 que deja de competir) | FSM + `ExitPlan`                                            | idem (`test_v2_trail_in_r_replaces_legacy_pct_and_wins_over_t1`, `test_v2_t1_reduces_when_no_retracement`, `test_v2_t1_partial_fraction_matches_legacy_shim`, `test_v2_t1_partial_leaves_residual_lifecycle`) |
| Los 9 tests legacy siguen **verdes** cubriendo el camino flag-off (shim `pct`)         | `ProtectionConfig` (alias del shim en el worker)            | `apps/api-python/tests/test_auto_simulation_worker.py` (4) + `test_a9_1_durability_integrity.py` (5)                                                                                                          |

### e) Worker: ratchet, FSM en el ciclo y adopción degradada

| Afirmación                                                                                | Código                                                     | Test                                                                                                                   |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| El ratchet del trailing se **aplica, persiste y journaliza**; un ratchet no vende         | `_v2_position_package` + `_v2_apply_stop_update`           | `apps/api-python/tests/test_auto_v2_worker_integration.py` (`test_v2_stop_ratchet_is_applied_persisted_and_journaled`) |
| T1 **arma** el trailing y el estado lo declara (`armed` → `active`)                       | `_v2_track_reduce` (`mark_trailing`) + `advance_lifecycle` | idem                                                                                                                   |
| Tras reiniciar, el trailing **continúa** desde el estado persistido (no se re-deriva)     | `_v2_restore_durable_position` + `_persist_position`       | idem (`test_v2_restart_rehydrates_trailing_and_keeps_ratcheting`)                                                      |
| Ni el stop que empeora ni el `PROTECT` sin stop quedan mudos                              | journal de `stop_ratchet_rejected` / `protect_requested`   | idem (`test_v2_protect_is_never_silent`)                                                                               |
| Una adopción sin estado verificable se **declara** degradada, con stop de emergencia vivo | `_v2_degrade_adoption` + `_v2_adopt_position`              | idem (`test_v2_adopts_with_reconstructed_geometry_without_durable_plan`)                                               |
| El FSM emitido por el worker no rompe el ciclo existente                                  | `_v2_track_entry` / `_v2_track_reduce`                     | los 35 tests de `test_auto_v2_worker_integration.py` (todos en verde)                                                  |

### f) Durabilidad real (PostgreSQL)

| Afirmación                                                                                                                               | Código                                          | Test                                                                                          |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Cada estado intermedio (`PROTECTED`, `T1_REACHED`, `TRAILING`, `EXIT_PENDING`, `RECONCILIATION_REQUIRED`) sobrevive al round-trip por PG | JSONB `position_state` (`lifecycleState`)       | `apps/api-python/tests/test_auto_v2_lifecycle_pg.py`                                          |
| El ratchet **continúa** después de reiniciar con el `highWatermark` persistido                                                           | `trailing.highWatermark` + `compute_trail_stop` | idem (`test_v2_trailing_continues_from_persisted_watermark_after_restart`)                    |
| Un estado **no verificable** se degrada al rehidratar desde PG (no se confía en él)                                                      | `position_state_from_dict`                      | idem (`test_v2_unverifiable_state_degrades_on_rehydration`)                                   |
| Sin migración nueva: el head sigue siendo `042_portfolio_reservations`                                                                   | (ninguna revisión nueva)                        | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py` (`_ALEMBIC_HEAD`, sin cambios) |

### g) Red de seguridad de CI

| Afirmación                                                                                                                                                           | Dónde                                                                                                                | Verificación                                                                                                                                                      |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Los herméticos nuevos se ejecutan: **`test_auto_v2_lifecycle_stop.py` por nombre** y `test_position_lifecycle.py` **por directorio** (`packages/py/analytics/tests`) | `quality` (`python-ci.yml`) y `python` (`release-tag-ci.yml`)                                                        | §8.1 (ambas listas, extraídas del YAML). **Corregido por la auditoría externa**: el fichero de analytics **no** se nombra en los workflows (entra por directorio) |
| El FSM durable se certifica contra **PostgreSQL real** con gate fail-if-skipped                                                                                      | `auto-v2-durable-pg` (`python-ci.yml`) y `lifecycle-pg` (`release-tag-ci.yml`) con `AUTO_V2_LIFECYCLE_PG_REQUIRED=1` | §8.1 (36 passed, 0 skipped; el fichero aparece en el comando del job y la batería recolecta exactamente 36 tests ⇒ no es skip mudo)                               |
| El fichero PG nuevo **no** queda como skip mudo en los jobs offline                                                                                                  | `--ignore` en ambos jobs offline                                                                                     | §8.1                                                                                                                                                              |

---

## 4. Matriz de mutaciones **medida**

Cada mutación se aplicó sobre el árbol de trabajo, se corrió la suite del slice y se revirtió (ninguna se
declara sin medir):

| #   | Mutación                                                          | Efecto medido                                                                                                                                                                           |
| --- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | `apply_lifecycle_event` acepta transiciones no listadas           | **3 rojos** (`test_invalid_transitions_are_rejected_without_advancing`, `test_cartesian_product_is_total_and_fail_closed`, `test_advance_lifecycle_rejected_leaves_position_untouched`) |
| M2  | La rehidratación **no** degrada un estado inconsistente           | **2 rojos**: hermético de analytics **y** PG real `test_v2_unverifiable_state_degrades_on_rehydration` (`CLOSED` en vez de `RECONCILIATION_REQUIRED`)                                   |
| M3  | `compute_trail_stop` pierde el clamp nunca-empeorar (H2)          | **1 rojo**: `test_trail_stop_never_worsens` (103 ≠ 107)                                                                                                                                 |
| M4  | El worker descarta el `stop_update`                               | **3 rojos**: ratchet aplicado/persistido, reinicio que sigue ratcheando y `PROTECT` nunca mudo                                                                                          |
| M5  | La reconciliación `CRITICAL` veta también las salidas protectoras | **2 rojos**: `test_stop_hit_still_sells_with_recon_drift`, `test_ratchet_still_applies_with_recon_drift`                                                                                |
| M6  | `_v2_track_reduce` no arma el trailing con el T1                  | **1 rojo**: `trailing_status == "armed"` en el ratchet real                                                                                                                             |
| M7  | La adopción sin estado verificable no se degrada                  | **1 rojo**: `test_v2_adopts_with_reconstructed_geometry_without_durable_plan`                                                                                                           |
| M8  | Vuelve el fallback 0.5/1.0 sin `template_id`                      | **3 rojos**: `test_t1_reduce_is_moderate_without_template`, `test_v2_t1_reduces_when_no_retracement`, `test_v2_t1_partial_fraction_matches_legacy_shim` (5.0 ≠ 3.0)                     |
| M9  | El shim legacy evalúa T1 antes que el trailing                    | **2 rojos**: `test_exit_reason_trailing_wins_over_t1` y `test_restart_with_open_position_trailing_uses_persisted_watermark` (`t1_exit` ≠ `trailing_stop`)                               |
| M10 | Un `PROTECT` sin stop utilizable queda mudo                       | **1 rojo**: `protect_requested` ausente del journal                                                                                                                                     |
| M11 | El trailing se considera armado antes de T1                       | **3 rojos**: `test_trail_stop_not_armed_before_t1`, `test_trailing_status_of_birth_stub_is_inactive` y `sin T1 no hay trailing`                                                         |

**Sin mutación**: la batería del §8.1/§8.2 es la referencia (todo verde).

> **Nota de la auditoría externa (2026-09-17):** se reprodujeron **M1, M3, M4, M5 y M7** con los rojos
> exactos publicados. **M11 tiene un hueco de cobertura**: dice probar "trailing sólo tras T1", pero el
> test que lo respalda usa una posición **sin parcial**, y el código arma el trailing también con
> `PARTIAL_EXIT` (una reducción **sólo de T2** lo activa sin T1) ⇒ ver hallazgo **H-3** del §9.
> M2, M6, M8, M9 y M10 quedaron **no reproducidas** (no refutadas) en esa pasada.

---

## 5. Cambios observables y breaking declarado (beta)

1. **Journal / reason codes nuevos**: `stop_ratchet_applied`, `stop_ratchet_rejected`,
   `protect_requested`, `protection_missing`, `reconciliation_required`,
   `lifecycle_transition_rejected` (+ los motivos del FSM re-exportados desde analytics), agrupados en
   `POSITION_LIFECYCLE_REASONS` de `auto_reason_codes.py`.
2. **Un campo nuevo en el JSONB `position_state`**: `lifecycleState` (aditivo; se emite sólo si no es
   `None`) y `trailing.highWatermark` pasa a tener writer real. Un consumidor que lea el blob con una
   versión anterior **ignora** el campo; el round-trip exacto de los canarios está preservado.
3. **`ProtectionConfig` deja de ser motor**: se conserva exportada desde el worker como **value object**
   (flag-off), pero su lógica vive en `protection_compat`. Un consumidor que instanciara
   `ProtectionConfig` y esperara que el worker la usara como autoridad **ya no la usa**.
4. **La política T1/T2 es única (MODERATE 0.3/0.3)**: un consumidor que no pasara `template_id` y
   contara con la reducción del 50 % en T1 verá 30 % (es la unificación declarada).
5. **Un `PROTECT` puede mover el stop sin emitir orden**: el `PositionManagerResult` ya contenía
   `stop_update`, pero nadie lo leía; ahora el stop persistido **sube** en esos ticks. El spine de
   órdenes (sólo SELL) no cambia.
6. **Sin migración**: `sim_auto_positions` sigue siendo la autoridad de estado de posición AUTO;
   `position_states` (ADR-033) **no se toca** (dualidad declarada, §6.2).

---

## 6. Límites declarados (lo que este slice NO resuelve)

1. **`TIME_EXIT` y `THESIS_EXIT` no existen** en el FSM: el roadmap los pide para `AUTO-2`, pero este
   slice es **2a** y los deja asignados a **2b** (junto con el horizonte de tiempo). El criterio de
   salida completo de `AUTO-2` **no** se declara cerrado.
2. **Dualidad de superficies de estado de posición**: `sim_auto_positions` (JSONB `position_state`) es
   la autoridad del camino AUTO y `position_states` (ADR-033) sigue existiendo para otros consumidores.
   Este slice **no** unifica ambas; se declara explícitamente que no hay una única tabla de ciclo de
   vida de posición en la plataforma.
3. **ATR real**: la adopción degradada y el camino legacy siguen con el ATR aproximado
   (`precio × 2 %` × multiplicador). Sin ATR medido no hay stop ⇒ esto sigue siendo deuda de 2b.
4. **`ProtectionConfig` no desaparece**: se mantiene como value object exportado por el worker para no
   romper el freeze flag-off. La limpieza total (eliminar la dataclass del camino AUTO) es 2b.
5. **El trailing necesita marks**: sin ticks (sin `apply_position_mark`) no hay pico, y sin pico no hay
   ratchet de trailing. Una posición que no se marca no protege al alza. **Matiz de la auditoría
   externa (H-4, §9):** sin pico persistido el cálculo **no** devuelve `None`: cae al precio de entrada y
   produce un trailing sintético, así que "no protege al alza" es cierto pero "no calcula nada" no.
6. **El FSM declara, no repara**: la rehidratación degrada un estado no verificable, pero resolverlo es
   responsabilidad de la reconciliación. **Corregido por la auditoría externa:** "`RECONCILED` exige la
   resolución explícita" describe la **intención**, no el código de hoy (véase **H-1** en §9): el evento
   se acepta desde cualquier estado y sin comprobar la cantidad.
7. **Lo que este pack NO afirma**: ningún run **anterior** a `35e38c24` (el rojo del commit de fase está
   declarado en §8.1, no escondido) y ningún comportamiento fuera del camino `AUTO_ENGINE_SIM_V2=1`
   salvo el shim flag-off, que se certifica con los tests legacy. **Y desde la auditoría externa:** no
   afirma que las afirmaciones absolutas del §1 se cumplan en los bordes — H-1…H-7 son precisamente esa
   lista de excepciones (§9).
8. **Lo que este pack NO afirma**: ningún run **anterior** al arreglo `35e38c24` (el rojo del commit de
   fase está declarado en §8.1, no escondido) y ningún comportamiento fuera del camino
   `AUTO_ENGINE_SIM_V2=1` salvo el shim flag-off, que se certifica con los tests legacy.

---

## 7. Cómo reproducir la verificación

```bash
# 1) Estático (invocación EXACTA de CI: NO añadas `packages/py/analytics/src` — CI no lo compila
#    y da exit 2 por hallazgos preexistentes ajenos a la fase; ver §9.2)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_lifecycle.py \
               packages/py/application/tests/test_auto_v2_lifecycle_stop.py \
               apps/api-python/tests/test_auto_v2_worker_integration.py -q

# 3) Cobertura legacy que sigue cubriendo el shim flag-off (9 tests)
uv run pytest apps/api-python/tests/test_auto_simulation_worker.py \
               apps/api-python/tests/test_a9_1_durability_integrity.py -q

# 4) Offline del job `quality` (usa EXACTAMENTE su lista y sus --ignore, extraída del YAML)
uv run python -c "import yaml;print(yaml.safe_load(open('.github/workflows/python-ci.yml',encoding='utf-8'))['jobs']['quality']['steps'][-1]['run'])"
# (ídem para el job `python` de release-tag-ci.yml)

# 5) PG real (certificación). Un skip es FALLO.
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q
AUTO_V2_DURABLE_PG_REQUIRED=1 AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest \
    apps/api-python/tests/test_auto_v2_durable_pg.py \
    apps/api-python/tests/test_auto_v2_lifecycle_pg.py \
    apps/api-python/tests/test_instrument_trade_context_pg.py \
    apps/api-python/tests/test_unique_natural_keys_pg.py \
    apps/api-python/tests/test_portfolio_reservation_pg.py \
    apps/api-python/tests/test_discovery_evidence_snapshot_pg.py -q

# 6) Batería completa de paquetes
uv run pytest packages/py -q
```

---

## 8. Evidencia de verificación

### 8.1 CI real de GitHub

| Gate                                                      | Run                                                                            | Resultado                                                                                                                                                                                                                                                                                                                                             |
| --------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Python CI` en `main` @ `35e38c24`                        | [`35214904914`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35214904914) | **GREEN** (`5/5`: `quality`, `auto-v2-durable-pg`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`)                                                                                                                                                                                                                                        |
| `Python CI` en la ref `v2.42-beta` @ `35e38c24`           | [`35214985401`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35214985401) | **GREEN** (`5/5`)                                                                                                                                                                                                                                                                                                                                     |
| `Release tag CI` en `v2.42-beta` @ `35e38c24`             | [`35214985392`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35214985392) | **GREEN** (**9 jobs requeridos + `certify`**; el opt-in `playwright (integrated E2E)` queda `skipped` por diseño ⇒ 10 ejecutados de 11). Corregido por la auditoría externa                                                                                                                                                                           |
| `Python CI` en `main` @ `6e53294f` (commit de fase)       | [`35213904170`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35213904170) | **GREEN** (`5/5`)                                                                                                                                                                                                                                                                                                                                     |
| `Python CI` en la ref `v2.42-beta` @ `6e53294f` (1.º tag) | [`35213906948`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35213906948) | **ROJO** en `auto-v2-durable-pg` (los otros 4 verdes): el test durable V2 **sorteaba** instrumento (lotería de la cola SIM). El **mismo commit** había pasado `5/5` minutos antes en `main` ⇒ **flaky preexistente, no regresión** de 2a. Arreglado en `35e38c24` (test-only, identidad determinista que llena) y el tag **re-apuntado** a ese commit |

**Evidencia del fichero nuevo de este slice dentro de esos jobs** (extraída de los logs de los runs
verdes):

- `auto-v2-durable-pg` (`python-ci.yml`, run `35214904914`): `36 passed` en 5,4 s con
  `AUTO_V2_DURABLE_PG_REQUIRED=1` + `AUTO_V2_LIFECYCLE_PG_REQUIRED=1`; el fichero
  `test_auto_v2_lifecycle_pg.py` **figura en el comando del job** y el `--collect-only` de sus seis
  ficheros devuelve **36 tests** (= los 36 passed) con gate fail-if-skipped ⇒ **no es skip mudo**.
- `lifecycle-pg` (`release-tag-ci.yml`, run `35214985392`): `141 passed` en 85,5 s con
  `AUTO_V2_LIFECYCLE_PG_REQUIRED=1` (el `--collect-only` de sus **30** ficheros devuelve **141 tests**)
  - el gate de aislamiento por cuenta `45 passed`.
- `quality` (`python-ci.yml`, run `35214904914`): `1869 passed, 38 skipped` en 114,4 s.
- `python` (`release-tag-ci.yml`, run `35214985392`, offline): `1880 passed, 35 skipped` en 60,7 s.

**Corrección de procedencia (honestidad):** las cifras de §8.2 se midieron **en local** con
`DATABASE_URL` y los seis `*_PG_REQUIRED` exportados en la sesión, de modo que las suites gated
**corrieron dentro** del job en vez de skipear (`1903 passed, 0 skipped` en `quality`; `1915 passed` en
el bloque offline del tag). En CI, con el entorno limpio, el mismo comando da `1869`/`1880` con
`38`/`35` skips: **la cifra que manda es la de CI** y el delta (`34` y `35`) **es** exactamente la
batería gated que corrió de propina en local. Ninguna afirmación de este pack se apoya ya en una
medición contaminada por el entorno.

**Nota de artefacto (declarada, no escondida):** la **anotación del tag** (`git tag -n5 v2.42-beta`)
enumera los estados **en prosa** y nombra `REDUCED`, que **no existe** en el FSM: los 13 estados reales
son los de `position_lifecycle.py` (§1). La prosa del tag **no** es la fuente y se declara aquí en vez
de re-escribir un tag ya publicado (mover el tag invalidaría el mapeo run ↔ commit de la tabla de
arriba).

### 8.2 Baterías locales (medidas en el árbol final del slice, antes de publicar)

| Batería                                                                                                                            | Resultado                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (invocación de CI)                                                | `All checks passed!`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `mypy … --follow-imports=silent`                                                                                                   | **487 ficheros, 0 issues**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `lint-imports --config packages/py/.importlinter`                                                                                  | **4 kept / 0 broken**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Suites herméticas nuevas                                                                                                           | **46 passed** (`test_position_lifecycle.py` 29 + `test_auto_v2_lifecycle_stop.py` 17)                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Suite de integración del worker                                                                                                    | **35 passed** (`test_auto_v2_worker_integration.py`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Los 9 tests legacy de protección (flag-off vía shim)                                                                               | **9 passed** (4 de `test_auto_simulation_worker.py` + 5 de `test_a9_1_durability_integrity.py`)                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Job `quality` completo** (comando **extraído del YAML**, con la lista y los `--ignore` nuevos)                                   | **exit 0**. En CI (run `35214904914`, job `quality`): `1869 passed, 38 skipped`, 114,4 s. En local, con `DATABASE_URL` + los seis `*_PG_REQUIRED` exportados: `1903 passed, 0 skipped`, 85,7 s ⇒ el delta (34) **es** la batería gated que en CI skipea (corre en sus jobs dedicados, §8.1)                                                                                                                                                                                                                                                       |
| Bloque offline del job **`python`** de `release-tag-ci.yml` (extraído del YAML)                                                    | **exit 0**. En CI (run `35214985392`): `1880 passed, 35 skipped`, 60,7 s. En local con los flags exportados: `1915 passed`, 61,1 s                                                                                                                                                                                                                                                                                                                                                                                                                |
| `pytest packages/py` (batería completa de paquetes)                                                                                | **2825 passed**, 1 skipped (Ollama ausente: entorno) y 1 xfailed ⇒ **0 rojos**                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `AUTO_V2_LIFECYCLE_PG_REQUIRED=1 … test_auto_v2_lifecycle_pg.py`                                                                   | **3 passed** (0 skipped): round-trip de los cinco estados intermedios, continuación del ratchet desde el watermark persistido y degradación de estado no verificable. **Confirmado en CI** (§8.1: job `lifecycle-pg` del tag y job `auto-v2-durable-pg`, donde el fichero figura en el comando del job y la batería recolecta exactamente 36 tests)                                                                                                                                                                                               |
| `AUTO_V2_DURABLE_PG_REQUIRED=1 …` (durable + lifecycle + contexto + claves + reservas + snapshot)                                  | **36 passed** (0 skipped). **Reproducido en CI**: run `35214904914`, job `auto-v2-durable-pg`, `36 passed`                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Bloque PG del job **`lifecycle-pg`** de `release-tag-ci.yml` (**30** ficheros en el step, comando y `env:` **extraídos del YAML**) | **exit 0** (`141 passed`, 96,2 s): golden V1.88–V1.96, auth, outbox worker, integridad financiera, estado del motor AUTO, finanzas simuladas, **bucle real del scheduler con cero intervención humana** (`test_auto_scheduler_real_pg_zero_human_intervention.py`) y **proceso** del scheduler, estrategia, discovery→AUTO, durabilidad V2, lifecycle, reservas y fencing de ejecución. **Reproducido en CI**: run `35214985392`, job `lifecycle-pg`, `141 passed` (85,5 s) + gate de aislamiento `45 passed` (**corregido**: 30, no 36 ficheros) |

**Lo que este pack afirma:** las cifras de §8.2 (con la salvedad de procedencia declarada en §8.1), la
matriz de mutaciones del §4 (cada mutación aplicada, medida y revertida) y los runs de CI de §8.1.
**Lo que NO afirma:** ningún run **anterior** a `35e38c24` (el rojo de `6e53294f` está declarado en
§8.1, no escondido) ni ningún comportamiento fuera del camino `AUTO_ENGINE_SIM_V2=1` salvo el shim
flag-off, que se certifica con los tests legacy.

---

## 9. Auditoría externa del 2026-09-17 (post-sellado): hallazgos y deuda declarada

Tres auditorías independientes de **solo lectura** sobre `da93cd20` (código idéntico al tag
`35e38c24`: `git diff 35e38c24..HEAD -- packages apps` **vacío**), con encargo explícito de **refutar**.
Resultado: **ningún P0** (sin agujero de dinero ni de seguridad; el commit no toca barreras LIVE) y el
sello confirmado (los cinco runs, el mapeo tag↔commit, la ausencia de migración y **5 mutaciones
reproducidas con los rojos exactos**: M1, M3, M4, M5, M7). Lo que sigue es lo que **sí** se rompió.

**Decisión del owner tras el informe: NO se toca código en 2a** (el slice queda como está y estos
hallazgos pasan a ser criterio de aceptación de **2b**). Se corrigen las afirmaciones del documento y se
declara la deuda; el código se arreglará con su propio gate y su propia matriz de mutación.

### 9.1 Hallazgos de código (7) — deuda de 2b, con evidencia medida

| #   | Afirmación que cae                                  | Realidad medida                                                                                                                                                               | Alcanzable hoy                                      |
| --- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| H-1 | `RECONCILED` exige estado resuelto **verificado**   | `apply_lifecycle_event` lo acepta desde **13/13 estados** y **no** comprueba coherencia con la cantidad (`OPEN→RECONCILED(CLOSED)` aceptado). `position_lifecycle.py:359-377` | No: nadie emite `RECONCILED` (el worker no lo hace) |
| H-2 | **Ningún** `PROTECT` mudo                           | Trailing estable (`changed=False` **y** mismo `lifecycle_state`) ⇒ **cero journal**; solo el `hold_no_op` genérico. `auto_simulation_worker.py:2283-2293`                     | Sí, es el estado normal del trailing                |
| H-3 | Trailing **sólo tras T1**                           | `is_trail_armed` incluye `PARTIAL_EXIT` (`position_lifecycle.py:530`): una reducción **sólo de T2** arma el trailing sin T1                                                   | Sí (vía `manage_position_outcome`)                  |
| H-4 | Sin pico ⇒ `None`                                   | Sin `trailing.highWatermark` **cae al precio de entrada** y devuelve un trailing sintético (`position_lifecycle.py:559-561`)                                                  | Sí                                                  |
| H-5 | `None`/NaN/0/negativos no son stop utilizable       | `+inf` **pasa** los filtros (`_finite`/`_finite_positive` no usan `math.isfinite`) y revienta en `round()` con `OverflowError`                                                | Latente (exigiría un `+inf` aguas arriba)           |
| H-6 | Un estado inconsistente con la cantidad **degrada** | Con `lifecycleState` **ausente o `null`** y `status=CLOSED` + cantidad viva: **no** degrada (`position_state.py:421-443`). Con `""`/`123`/`[...]` sí degrada                  | Sí (JSONB escrito por terceros)                     |
| H-7 | La tabla de transiciones es el contrato             | **7 transiciones aceptadas retroceden** en el ciclo (p. ej. `TRAILING+T1_HIT→T1_REACHED`, `PARTIAL_EXIT+PROTECT_APPLIED→PROTECTED`)                                           | Poco (los eventos del worker son forward-only)      |

Además, dos fragilidades P2 que **no** son afirmación falsa pero tampoco estaban declaradas: el worker
mantiene **dos picos** (columna `_high_price` para ratchetear vs `trailing.highWatermark` del JSONB, que
no es la entrada de `compute_trail_stop`; latente porque `run_auto_cycle` solo lo llaman tests) y el
motor legacy sigue **presente aunque muerto**, con su propio orden T1-vs-trailing.

**Criterio de aceptación para 2b (derivado):** H-1 (exigir estado degradado de origen + coherencia con
la cantidad), H-2 (journalizar el no-op o declarar la prosa), H-3 (quitar `PARTIAL_EXIT` de
`is_trail_armed`), H-4 (devolver `None` sin watermark explícito), H-5 (`math.isfinite` en los tres
filtros), H-6 (`null` presente = no verificable; validar `status`↔cantidad), H-7 (mapas forward-only),
más un solo pico y la retirada del legacy. **Ninguno** cambia el veredicto de dinero/seguridad del
sello.

### 9.2 Correcciones de evidencia de este pack (errata)

Cifras y anclas **mías** que la auditoría refutó y que quedan corregidas en el texto:

1. "el log cita **7 veces** `test_auto_v2_lifecycle_pg`" (y "**28** citas" en el tag): **falso**. La
   medición contaba líneas que contenían `lifecycle_pg`, y 6 eran el eco de la variable de entorno
   `AUTO_V2_LIFECYCLE_PG_REQUIRED: 1`; el fichero aparece **1** vez, en el comando. La sustancia se
   sostiene por otra vía: el fichero está en el comando del job y `--collect-only` da **36 tests** = los
   `36 passed`, con gate fail-if-skipped.
2. "bloque PG de **36 ficheros**" ⇒ **30** (contado en el YAML).
3. "**10 jobs requeridos** + `certify`" ⇒ **9 requeridos + `certify`** (10 ejecutados de 11; uno es el
   opt-in `playwright (integrated E2E)`, `skipped` por diseño).
4. Ancla muerta **`§7.2`** (4 referencias) ⇒ `§8.1`/`§8.2`.
5. "Los herméticos nuevos se ejecutan **con nombre propio**" ⇒ solo el de `application`
   (`test_auto_v2_lifecycle_stop.py`) está nombrado; el de analytics entra **por directorio**.
6. **`TRAIL_DISTANCE_R_BY_WIDTH` preexistía** en `exit_policy.py` (presente en `15618c0c`, fichero
   **intacto** en la fase): no es novedad de A3; lo nuevo es `compute_trail_stop` y su anclaje al pico.
7. "97 referencias comprobadas" ⇒ **98** (`a9_doc_refs_probe`, 0 muertas). La sonda valida rutas, **no**
   anclas de sección (por eso `§7.2` pasaba).
8. El `mypy` del relevo estaba rotulado "invocación **EXACTA** de CI" **sin serlo**: añadía
   `packages/py/analytics/src`, que CI **no** compila (sale `exit 2` con errores preexistentes ajenos a
   la fase). La invocación de CI es limpia y da **487 ficheros, 0 issues**.

### 9.3 Nota de método (para futuras auditorías)

La auditoría C ejecutó las mutaciones **en el árbol vivo** mientras B auditaba el mismo árbol: B vio la
M4 aplicada y midió una suite contaminada (`1 failed` frente a `82 passed` en limpio — verificado
después por quien escribe, en árbol limpio). B lo detectó y se ancló a `HEAD` con `git show HEAD:`, que
es lo correcto. **Regla para la próxima pasada: mutar en `git worktree add` aislado, nunca sobre el
árbol que otro auditor está leyendo.**
