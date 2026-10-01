# Evidencia cruda — `v2.88.21.1-beta` (AUTO Operational Monitor · hotfix de `M2`)

> **Objeto:** tag anotado **`v2.88.21.1-beta`** · package **`2.11.21.1-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**) · fecha **2026-10-01**.
> **Clase:** sello de **producto** (`Δ src ≠ 0`), **hotfix** del sello `M2`. Supersede el tag **rojo** [`v2.88.21-beta`](../v2.88.21/README.md).
> **Madre:** [`evidence/v2.88.21/README.md`](../v2.88.21/README.md) — el sello `M2` completo (auditoría, ownership, concurrencia) es **este mismo incremento**; aquí sólo se documenta el defecto que destapó su CI y su arreglo.
> **Padres:** [`evidence/v2.88.20/README.md`](../v2.88.20/README.md) (`M1`, **verde** en su tag).

---

## 0. El hecho medido

`v2.88.20-beta` (`M1`) quedó **VERDE** en `Release tag CI` run `36903850807`. `v2.88.21-beta` (`M2`) quedó **ROJO**:

| Run | Job | Veredicto |
|---|---|---|
| `36903850433` (`Release tag CI`, `v2.88.21-beta`) | `lifecycle-pg` | **success** (5m15s) — la certificación **PG** del monitor corrió **de verdad** y pasó |
| `36903850433` | `python (ruff/imports/mypy/pytest offline)` | **FAILURE** — `6 failed, 4182 passed, 42 skipped` en `Pytest offline` |
| `36903850433` | `certify` | FAILURE (agrega, como debe) |
| `36903850433` | `frontend` / `replay-repro` / `shared` / `decision-spine` / `security` / `dr-verify` / `a7-gate` / `playwright (mock)` | success |
| `36903850316` (`Python CI`, `v2.88.21-beta`) | — | **FAILURE** (mismo defecto) |
| `36903825051` (`Python CI`, `main`) | — | **FAILURE** (mismo defecto) |

Los **6** fallos, todos con la **misma** firma, en `apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py`:

```
E   AttributeError: 'AutoSimulationWorker' object has no attribute '_operational_audit_sink'
apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:2735
```

---

## 1. Causa raíz (medida, no interpretada)

El rojo **no** es de la auditoría: es de **robustez de la costura**. La costura inerte leía
`self._operational_audit_sink` **a pelo** en `_v2_journal_reservation_claims`,
`_v2_journal_entry_decisions` y `_v2_journal_reconciliation_decisions`. El atributo sólo se
declaraba en `__init__`.

Pero en este repo hay un patrón **legítimo y extendido** de test de un solo método que monta el
worker **sin pasar por `__init__`**:

```python
worker = object.__new__(AutoSimulationWorker)
worker._account_id = ...
worker._time = ...
```

`test_auto_v51_auto10_cycle_journal_seam.py` (precedente a este incremento, `v2.51/AUTO-10`) hace
exactamente eso y ejercita `_v2_persist_tick_reservations` → `_v2_journal_reservation_claims`.
Sin el atributo, esa lectura revienta **en medio de un turno**: no es un fallo de test, es un
`AttributeError` **en código de producción** para cualquier instancia que no haya pasado por
`__init__`.

**Por qué mi verificación local no lo cazó (honestidad):** corrí `packages/py/application/tests`
completo y **mis** tres ficheros de test, pero **no** el pase de directorio completo de
`apps/api-python/tests` —donde vive el test que mordió—. El gate de CI sí lo hace. Defecto de
**método de verificación**, declarado aquí.

---

## 2. Arreglo

`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` — la costura se declara a
nivel de **CLASE**, no en `__init__`:

```python
    # AUTO Operational Monitor (M2): la costura inerte se declara a nivel de CLASE para que
    # cualquier instancia la vea —incluidas las que los tests construyen con ``object.__new__``
    # sin pasar por ``__init__`` (patrón común para probar un solo método)—. Sin el default,
    # leerla revienta con ``AttributeError`` en medio de un turno; con él, la ausencia de sink
    # es exactamente el ``Δ = 0`` que promete el flag OFF.
    _operational_audit_sink: Callable[[Any], Awaitable[None]] | None = None
    _audit_session_id: str | None = None
```

`__init__` sigue asignándolos (el sink inyectado y la identidad de sesión acuñada); el default de
clase sólo garantiza que **la ausencia** de sink sea `None` — es decir, **Δ = 0**, también por la
vía de construcción que no pasa por `__init__`.

---

## 3. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **H1** | Un worker montado con `object.__new__` (sin `__init__`) **no** revienta en ninguna de las tres costuras: son **no-ops declarados**. | Quitar el default de clase ⇒ `AttributeError: 'AutoSimulationWorker' object has no attribute '_operational_audit_sink'` en las tres. | `uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` → **8 passed** (incluye `test_a_worker_without_the_seam_attribute_is_a_declared_noop`) |
| **H2** | El test preexistente que mordió queda verde **sin tocarlo** (el arreglo es de producción, no de test). | Revertir el default ⇒ `test_auto_v51_auto10_cycle_journal_seam.py` vuelve a fallar (6 fallos, misma firma). | `uv run python -m pytest apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py -q` → **8 passed** |
| **H3** | El árbol offline completo del job `python` queda verde (el rojo era el único defecto). | Cualquier otro choque de la costura caería en el pase de directorio. | `uv run python -m pytest <pase de directorio del offline> -q` → **4229 passed, 1 skipped** |
| **H4** | La certificación **PG** de `M1`+`M2` ya había pasado **en el run rojo**. | El job `lifecycle-pg` del run `36903850433` es `success` con `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1` ⇒ si el defecto hubiera afectado al PG, ese job habría caído. | run `36903850433`, job `lifecycle-pg` = **success** |

---

## 4. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 515 source files` |
| `uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` | **8 passed** |
| `uv run python -m pytest apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py -q` | **8 passed** |
| `uv run python -m pytest <pase de directorio offline idéntico al CI> -q` | **4229 passed, 1 skipped** in 212.30 s |

> Nota de honestidad: la cifra **4229/1** es **local** (con PostgreSQL disponible, muchos tests que en CI se saltan aquí **sí** corren). El encaje con el CI se hace en §6 con las cifras del run verde del tag.

---

## 5. Límites declarados

1. **No cambia ninguna decisión del motor**: el arreglo es un **default de clase**; con `AUTO_OPERATIONAL_AUDIT` OFF el camino es el mismo (Δ = 0).
2. **No toca la certificación PG** (ya verde en el run rojo).
3. **No cierra `P3-2`/`P3-3`** ni las compuertas `G1`–`G7`.
4. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.
5. El tag **`v2.88.21-beta` NO se borra**: queda como **rojo citado** (run `36903850433`).
6. **El hueco de método queda declarado**: en sellos posteriores, la verificación previa debe incluir el **pase de directorio completo** del job offline, no sólo los ficheros nuevos. Es exactamente la clase de error que `OBS-19` persigue.

---

## 6. Cita del CI

### 6.1 CI del tag **rojo** — citado, verificado

`Release tag CI` run **`36903850433`** (`refs/tags/v2.88.21-beta`, HEAD `e58877ef`, `2026-10-01T18:02:25Z`) → **`FAILURE`**: `python` rojo (`6 failed, 4182 passed, 42 skipped`), `lifecycle-pg` **verde**, `certify` rojo por agregación.

### 6.2 CI del tag **`v2.88.21.1-beta`** — POST-TAG · **TODO VERDE**

`Release tag CI` run **[`36928967231`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36928967231)** (`ref=refs/tags/v2.88.21.1-beta`, HEAD `be388124`, `2026-10-01T21:28Z`) → **`SUCCESS`**: **11 jobs `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño, con **`certify` `success`**.

| Job | Conclusión | Cifra citada |
|---|---|---|
| `python (ruff/imports/mypy/pytest offline)` — **el job del rojo** | **success** | `All checks passed!` · **`4189 passed, 42 skipped`** in 128.66 s |
| `lifecycle-pg (…)` | **success** | con `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED: 1` y **`apps/api-python/tests/test_auto_operational_monitor_pg.py`** en la lista ⇒ la certificación **PG** del monitor corrió con gate fail-if-skipped |
| `replay-repro` | **success** | **`VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)`** ⇒ pese a `Δ src ≠ 0`, el artefacto OOS **no se mueve**: `M1`+`M2` son **INERTES** para el instrumento |
| `shared` | **success** | `src/cognitive/auto-operational-monitor.test.ts` · **8 tests** |
| `frontend` | **success** | **234 ficheros / 1352 tests** + `contract:check` |
| `decision-spine` / `security` / `dr-verify` / `a7-gate` / `playwright (mock E2E)` | **success** | — |

**Encaje de cuentas (el dato que cierra el sello):** el job `python` del run **rojo** de §6.1 dio **`4182 passed, 42 skipped` + 6 failed** (es decir **4188** veredictos) y el del tag **`4189 passed, 42 skipped`** ⇒ **+1** = **exactamente** la guarda de regresión nueva (`test_a_worker_without_the_seam_attribute_is_a_declared_noop`), con los **mismos `42` skips**. Esto **además demuestra** que la guarda **corre** en el job offline: no cae en la clase de `OBS-19`.
