# Evidencia — auditoría 2 (D-1–D-4)

> **AsOf:** 2026-10-29 · **Rama:** `fix/auditoria-2-d1-d4` · **HEAD:** `393c45fe` (commit del tag
> `v2.88.171-beta`) · **Cambios:** **sin commit**, en el árbol de trabajo.
> **Naturaleza:** registro de ejecución de la batería de cierre de la auditoría 2. No certifica el sello, no
> modifica el estado operativo y no sustituye a la re-auditoría independiente del diff.

---

## 0. Qué se cierra en este registro

| Tarea | Contrato cerrado | Prueba que lo fija |
| --- | --- | --- |
| `d1-seam` | El contraste de la geometría del parte se hace contra el precio de **FILL** (`open(B)`), no solo contra el de **decisión** (`close(B-1)`). Un fill en/por debajo del stop publicado no abre posición ni emite paquete. | `test_auto_v2_real_price_fail_closed.py::test_the_proposal_veto_measures_the_fill_price_not_the_decision_price` (+ contraprueba `..._a_fill_inside_the_published_geometry_still_opens`) |
| `d1-boundaries` | El borde del 2 % es **inclusivo** (`divergence == 0.02` NO veta) y un `structuralStop`/`target1` no finito se veta como `geometry_not_finite` (y el detalle del veto sigue siendo JSON estricto: el nivel no representable viaja como `null`). | `test_estudio_daily_proposal_handoff.py::test_the_two_percent_boundary_is_inclusive`, `::test_a_non_finite_stop_or_target_is_vetoed_as_incomplete_geometry`, `::test_a_non_finite_level_never_reaches_the_journal_payload` |
| `d3-retry` | Un discovery `failed` se reintenta **también dentro del mismo proceso** (no solo tras reinicio), el dedupe durable serializa los reintentos y el aviso `scan_daily_failed_today` solo se emite si el reintento va a ocurrir. La concurrencia multi-scheduler queda **declarada** como límite. | `test_opportunity_daily_scan_worker.py::test_a_failed_discovery_is_retried_within_the_same_process`, `::test_no_retry_and_no_warning_when_the_slot_is_already_covered` |
| `d4-race` | La carrera del índice único parcial se recupera con reintento acotado: si el ganador terminó antes de la relectura se reintenta el `INSERT`; nunca se devuelve un 500. `created` sigue significando «esta llamada insertó». | `test_auto_ops_job_enqueue_race.py` (3 casos herméticos) · `test_auto_ops_jobs_enqueue_outcome_pg.py` (2 casos PG reales) |

### Cambios de código de esta pasada

- `packages/py/application/src/bolsa_application/estudio_daily_proposals.py` — `_DIVERGENCE_EPSILON` (borde
  inclusivo), `PROPOSAL_PRICE_GEOMETRY_NOT_FINITE` y veto explícito de stop/objetivo no finitos.
- `packages/py/application/src/bolsa_application/auto_v2_entry.py` — `V2Signal.execution_price` (aditiva) y
  contraste del parte contra el precio de ejecución cuando el productor lo declara; `executionPrice` solo viaja
  en el detalle del veto cuando **difiere** de la decisión (Δ = 0 en el camino hermético).
- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` — la señal declara
  `_v2_price_exec(...)` como precio de fill del tick.
- `apps/api-python/src/bolsa_api/background/opportunity_daily_scan_worker.py` — reintento intra-proceso,
  filtro de fallidos ya cubiertos y límite de concurrencia declarado en el docstring.
- `packages/py/infrastructure/src/.../auto_ops_job_repository.py` — reintento acotado tras `IntegrityError`
  (sin `raise` ciego cuando el ganador ya no está activo).

---

## 1. Verificación estática

| Verificación | Comando | Resultado |
| --- | --- | --- |
| Ruff (config de CI) | `python -m ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** (árbol completo) |
| Mypy (strict) | `python -m mypy` sobre `auto_v2_entry.py`, `estudio_daily_proposals.py`, `auto_ops_job_repository.py`, `opportunity_daily_scan_worker.py`, `auto_simulation_worker.py` | **0 errores** |
| `lint-imports` | `python -m importlinter.cli lint-imports` | **NO EJECUTADO**: el entorno bloquea el DLL de `grimp` (`ImportError: DLL load failed while importing _rustgrimp`), no el contrato. Limitación de la máquina, no del árbol |

---

## 2. Suites

| Suite | Resultado |
| --- | --- |
| `packages/py/application/tests` | **2 988 passed** |
| `packages/py/infrastructure/tests` | **225 passed** |
| `apps/api-python/tests` (completa) — ejecución A | **1 431 passed, 3 failed** (solo P&L, §3.1) |
| `apps/api-python/tests` (completa) — ejecución B | **1 430 passed, 4 failed** (los 3 P&L + `c3b` de chaos, §3.2) |
| `apps/web` (los 2 ficheros afectados) | **43 passed** |

Las dos ejecuciones completas de la suite API se hicieron **después** de todos los cambios de código y con el
mismo árbol: la diferencia entre ambas es **un test de chaos distinto** (`c3a` en la primera pasada histórica,
`c3b` en la segunda de hoy, ambos verdes en las demás). Los 3 fallos de P&L aparecen **idénticos** en las dos.
Ninguno de los 4 es de esta rama: se reproducen sobre el árbol limpio del tag (§3).

---

## 3. Clasificación de los 4 fallos de la suite API

### 3.1 P&L — PREEXISTENTES (no atribuibles a D-1–D-4)

Reproducidos en el árbol de trabajo **y** en el árbol limpio del tag (`393c45fe`, con `git stash` temporal y
restauración verificada por hash del diff):

| Test | Rama (`fix/auditoria-2-d1-d4`) | Tag `393c45fe` (árbol limpio) |
| --- | --- | --- |
| `test_auto_dia_d_trace_pg.py::test_dia_d_chain_is_fully_traced_and_pnl_reconciled_pg` | FAIL — `monitor=-27.255746` vs `libro=-27.255745` | **FAIL idéntico** — `monitor=-27.255746` vs `libro=-27.255745` |
| `test_auto_dia_d_trace_pg.py::test_dia_d_trace_reconciles_per_value_and_cycle_pg` | FAIL — `ciclos=-66.705234` vs `libro=-66.705233` | **FAIL idéntico** — `ciclos=-66.705234` vs `libro=-66.705233` |
| `test_auto_estudio_chain_evidence_pg.py::test_estudio_chain_evidence_covers_nine_steps_per_value_pg` | FAIL — `ciclos=-66.705234` vs `libro=-66.705233` | **FAIL idéntico** — `ciclos=-66.705234` vs `libro=-66.705233` |

**Causa:** la reconstrucción del P&L desde el journal (ciclo a ciclo, redondeo a quantum de 1e-6 por ciclo) no
coincide con el realizado agregado del libro aplicado; la diferencia es **un quantum** (`0.000001`), es decir
orden de suma/redondeo, no un descuadre económico. Ninguno de los tres tests toca las rutas modificadas por
D-1–D-4 (traza Día D / evidencia de cadena ESTUDIO).
**Clasificación:** defecto de precisión **preexistente**; fuera del alcance de esta auditoría, declarado como
deuda abierta.

### 3.2 Chaos — INESTABLE (flaky), no atribuible a los parches

Familia `apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py`. Medición propia:

- **`::test_c3a_crash_after_recovery_claim_then_second_is_exact_once`**, sobre el **árbol limpio del tag**:
  6 ejecuciones aisladas ⇒ **4 passed / 2 failed** (y en una tanda previa de 3: 2 passed / 1 failed).
  Mensaje:

  ```
  AssertionError: el segundo proceso no resolvió exactamente una vez: 'drained=0 resolved=0'
  assert 'resolved=1' in 'drained=0 resolved=0'
  ```

  En la ejecución completa A de hoy **pasó**; en la del informe previo **falló**.
- **`::test_c3b_crash_after_resolve_put_no_double_on_relaunch`**, en la ejecución completa B de hoy:
  `AssertionError: primer resolve no reclamó la fila: 'drained=0 resolved=0'`. En la ejecución A (20 min antes,
  mismo árbol) **pasó**.

Ambos fallos son el MISMO síntoma (`drained=0 resolved=0`: el segundo proceso no encuentra la fila reclamable en
el instante en que el arnés la busca) y no tocan las rutas de D-1–D-4. La carrera está en el arnés
(timing de arranque del proceso vs. visibilidad del claim), no en el motor.
**Clasificación:** **flaky** preexistente, reproducido en el tag y en la rama, con dos tests distintos de la
misma familia cayendo en pasadas distintas.

---

## 4. Reproducción

```powershell
# Suite completa API (árbol de trabajo)
python -m pytest apps/api-python/tests -q

# Los 3 fallos de P&L, en el árbol limpio del tag
git stash push -u -m "aud2-evidence-baseline"
python -m pytest `
  "apps/api-python/tests/test_auto_dia_d_trace_pg.py::test_dia_d_chain_is_fully_traced_and_pnl_reconciled_pg" `
  "apps/api-python/tests/test_auto_dia_d_trace_pg.py::test_dia_d_trace_reconciles_per_value_and_cycle_pg" `
  "apps/api-python/tests/test_auto_estudio_chain_evidence_pg.py::test_estudio_chain_evidence_covers_nine_steps_per_value_pg" -q
git stash apply "stash@{0}"   # restaurar (verificar con git diff)

# Chaos, repetido en el árbol limpio
1..6 | ForEach-Object {
  python -m pytest "apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py::test_c3a_crash_after_recovery_claim_then_second_is_exact_once" -q
}
```

> Nota de estado: el stash `aud2-evidence-baseline` usado para la comparación **sigue en la lista local** de
> stashes (el árbol de trabajo ya está restaurado y verificado por hash de diff). No se ha hecho commit, push,
> tag ni merge: la rama permanece sin certificar a la espera de la re-auditoría del diff.

---

## 5. Límites declarados

1. `lint-imports` no se pudo ejecutar en esta máquina (DLL de `grimp` bloqueado por la política de control de
   aplicaciones). No hay evidencia de contrato roto, pero **tampoco medición**: queda pendiente en un entorno
   que lo permita.
2. Los tests PG se ejecutaron contra el PostgreSQL local (disponible). En un entorno sin stack se saltarían por
   su gate habitual; los gates `fail-if-skipped` (`*_PG_REQUIRED`) no se activaron en esta pasada.
3. El `stash` de comparación permanece en la lista local; eliminarlo es una operación de estado de git que
   **no** se ha ejecutado en esta pasada.
