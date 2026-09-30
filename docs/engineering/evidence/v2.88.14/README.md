# Evidencia del sello `v2.88.14-beta` — `GRANULARIDAD-OPERATIVA` · **W1** (modelo puro + capability gate, **seam inerte**)

> **Objeto:** tag anotado **`v2.88.14-beta`** · **Versión:** `2.11.14-beta` · **Alembic head:**
> `046_fill_reference_mid` (**sin migración**).
> **Naturaleza:** **primer incremento con `src`** de la serie de granularidad operativa, y el único
> diseñado para ser **demostrablemente neutro** (`Δ = 0`, golden **byte-idéntico**).
> **Base del diff:** `v2.88.13-beta`.
> **AsOf:** 2026-09-30 · **HEAD del árbol sellado:** `a73edd01`.

---

## 1. Qué es este sello

`W1` del [plan de trabajos](../../plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md). Introduce
el **vocabulario** (`OperativeGranularity` con relojes separados) y el **gate de capacidad fail-closed**
**sin ningún efecto observable**: el worker sigue operando con `1d` exactamente como antes.

**Sí** toca `src` (a diferencia de `v2.88.12`/`v2.88.13`), pero **sólo** para derivar lo que antes se leía
suelto:

- `self._v2_tunables.signal_timeframe` (`:1936`, `:3034` **previos**) → `self._v2_granularity.decision.timeframe`.

Con el default `1d` ambos son la misma cadena ⇒ **golden byte-idéntico** (§4). **NO** enmienda el ADR 010 y
**NO** toca `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B.

---

## 2. Ficheros del sello

| Fichero | Δ | Rol |
| --- | --- | --- |
| `packages/py/domain/src/bolsa_domain/operative_granularity.py` | **nuevo**, 209 líneas | VO frozen: `OperativeGranularity` = `DecisionClock` + `ProtectionClock` + `ExecutionModel` + `EvidenceBucket`; enums `ProtectionModel`/`ExecutionTiming`/`EvidenceBucketUnit`/`GranularityRejection`; `DAILY_GRANULARITY`/`WEEKLY_GRANULARITY`; gate `require_supported()` |
| `packages/py/application/src/bolsa_application/operative_granularity_policy.py` | **nuevo**, 75 líneas | `resolve_operative_granularity(fallback_timeframe)`: env `AUTO_ENGINE_OPERATIVE_GRANULARITY` → VO → `.require_supported()` |
| `packages/py/domain/src/bolsa_domain/errors.py` | `+25/−1` | `UnsupportedGranularityError(reason, detail)` (subclase de `ValueError`) |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `+10/−2` | **seam inerte**: `self._v2_granularity` en `__init__` (`:740`); `signal_timeframe` → `self._v2_granularity.decision.timeframe` (`:1936`, `:3034`) |
| `packages/py/domain/tests/test_operative_granularity.py` | **nuevo**, 104 líneas, **11 tests** | matriz de capacidad, invariantes frozen, rechazos tipados |
| `packages/py/application/tests/test_operative_granularity_policy.py` | **nuevo**, 65 líneas, **8 tests** | precedencia de resolución, fallback, override, fail-closed |
| `apps/api-python/tests/test_simulated_finance_pg.py` | `+24/−1` | **`OBS-23`**: `_sell_seed_with_fill` determinista |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `+48` | **`M270`…`M274`** |
| `.github/workflows/python-ci.yml` | `+11` | alta explícita en el job `quality` (**`OBS-19`**) |
| `.github/workflows/release-tag-ci.yml` | `+8` | alta explícita en el job `python` (**`OBS-19`**) |

---

## 3. El gate fail-closed (lo que se rechaza)

`require_supported()` no degrada **nunca** en silencio; lanza `UnsupportedGranularityError` con un
`GranularityRejection` **tipado**:

| Configuración | Motivo | Estado |
| --- | --- | --- |
| `1d` (default) | — | **soportada** |
| `1wk` | gap del lunes sin pruebas temporales | **declarada, NO habilitada** |
| protección intradía (`ProtectionModel.INTRADAY_FEED`) | sin ingesta intradía | **rechazada** |
| `ExecutionTiming.NEXT_BAR_OPEN` | Fase B (`W3`), aún no implementada | **rechazada** |
| `EvidenceBucketUnit.WEEK` | cubo semanal no formalizado | **rechazada** |
| valor **desconocido** de entorno | error de configuración | **rechazado** (no cae a `1d`) |

El **heartbeat de infraestructura** (60 s) **no** es campo del VO: hay un test que lo fija.

---

## 4. Neutralidad demostrada (`Δ = 0`)

El default `1d` hace que el VO derive **exactamente** el `signal_timeframe` previo. La neutralidad se
verifica con el golden del día AUTO:

```
uv run pytest apps/api-python/tests/test_auto_v2_golden_day_evidence.py -q   # 5 passed
```

No se introduce golden nuevo: **el artefacto no cambia** (el plan `W1` lo exige y `W3` —`OPEN(D+1)`— es el
primer incremento que **sí** cambia resultados).

---

## 5. `OBS-23` — el flake del test PG de `OBS-21` (CERRADA)

`test_permanent_rejection_materializes_failed_not_retry` emparejaba `seed = 7` (fijo) con un `instrument_id`
**aleatorio** (`uuid4`); el terminal del fill (`draw_queue_noise(seed, side, instrument_id)`) puede caer en una
cola **sin fill** con probabilidad no despreciable.

**Medido sobre 400 `uuid` aleatorios (`seed = 7`, pata `sell`, `qty = 60`):**

```
OLD (seed = 7 fijo): 56/400 sin fill = 14.00 %
NEW (seed elegido) :  0/400 sin fill =  0.00 %
```

El fix sustituye el seed fijo por **`_sell_seed_with_fill(instrument_id, quantity)`**, que elige el primer
seed determinista cuya pata `sell` produce al menos un chunk (`_fill_chunks` es el espejo exacto del schedule
del settlement, y el corte no depende del `venue_order_id`). El escenario de `OBS-21` **no** depende del seed.

**Corrida real contra PG (local), 25 veces:** `PASS 25/25`.

---

## 6. `OBS-19` — alta explícita en AMBOS workflows (caso cerrado)

`packages/py/application/tests` **no** tiene pase de directorio en ninguno de los dos jobs de pytest, así que
el nuevo `test_operative_granularity_policy.py` se registra **a mano** en:

- `python-ci.yml` → job `quality` (bloque `Pytest offline`).
- `release-tag-ci.yml` → job `python` (bloque `Pytest offline`).

Cada alta lleva su comentario de procedencia. El test de dominio **no** se registra: entra por el pase de
directorio de `packages/py/domain/tests`, que ambos jobs ya recolectan enteros.

**`OBS-19` sigue ABIERTA como causa estructural** (las listas son manuales): este sello cierra **el caso**, no
la clase.

---

## 7. Mutaciones (`M269` → `M274`)

| Id | Defecto inyectado | Mata |
| --- | --- | --- |
| `M270` | `require_supported` deja de rechazar lo no habilitado (gate **fail-OPEN**) | `test_operative_granularity.py` (2) |
| `M271` | la matriz de decisión admite `1wk` | `test_operative_granularity.py` (2) |
| `M272` | `next_bar_open` declarado implementado | `test_operative_granularity.py` (1) |
| `M273` | la política resuelve pero **no exige** el gate | `test_operative_granularity_policy.py` (2) |
| `M274` | granularidad **desconocida** cae a `1d` en vez de rechazarse | `test_operative_granularity_policy.py` (1) |

**Resultado:** `5/5` muerden; la sonda restaura el árbol **byte a byte** (`medidas: 5/5`).

---

## 8. Verificación local (números exactos)

| Gate | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `mypy` (targets de CI, `--follow-imports=silent`) | `no issues found in 510 source files` |
| `lint-imports --config packages/py/.importlinter` | `4 kept, 0 broken` |
| `pytest` golden día AUTO | `5 passed` |
| `pytest` tests nuevos | `19 passed` (11 dominio + 8 aplicación) |
| `pytest` `OBS-23` contra PG real | `1 passed` · **25/25** corridas |
| mutación `M270…M274` | `5/5` |

---

## 9. Firma de estado (verificable)

```
git cat-file -t v2.88.14-beta                                     # tag (anotado)
git show v2.88.14-beta:package.json                               # 2.11.14-beta
git diff --stat v2.88.13-beta v2.88.14-beta -- packages/py apps/api-python/src \
  apps/api-python/scripts apps/api-python/tests .github
# Alembic: sin migración nueva (head sigue 046_fill_reference_mid)
```

---

## 10. Deuda que este sello NO cierra

`P3-2`/`P3-3` (ventana PAPER real ≥4 días con material), `OBS-19` (**causa estructural**), `OBS-22`,
`OBS-15`, `OBS-16`, `OBS-14.b`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`. `OBS-21` sigue
**CERRADA** (desde `v2.88.11-beta`). `OBS-23` **CERRADA** por este sello.

---

## 11. Cita del CI (POST-TAG) — `(pendiente)`

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado no
puede vivir dentro del propio tag; se cita en `main` como commit **POST-TAG**. Esperado del job `python`: los
**mismos `37` skips** + los **19** tests nuevos — **se cita el run, no se hereda**.

---

## 12. Revisión

- **Implementa** `W1` del [plan](../../plan-granularidad-operativa-auto-post-auditoria-2026-09-30.md), que
  ordena la serie del [diseño v2](../../rethink-granularidad-operativa-auto-v2-2026-09-30.md).
- **No** cambia la semántica (§4) ni la ventana PAPER.
- **Siguiente incremento:** **`W2`** (`v2.88.15-beta`) — short-circuit **Fase A** con `Δ = 0` estricto.
