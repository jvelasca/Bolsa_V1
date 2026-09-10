# Cierre V2.30 — Higiene auditable en GitHub (2026-09-10)

Version: `v2.30-beta`. Alcance: **solo deuda de higiene técnica**. Las deudas de
producto (`StrategyDiscoveryEngine`, shadow automático con evidencia ejecutada,
atribución tras crash) **no** entran aquí y siguen diferidas (ver §5).

Objetivo: dejar una entrega auditable en GitHub donde el CI del tag ejecuta de verdad
todo lo que dice certificar, sin drift silencioso ni guardias obsoletas.

---

## 1. Motivo: guardias de head de Alembic obsoletas

Al cerrar V2.29 se detectó que el tag apuntaba a un commit previo al arreglo de
imports, y al re-ejecutar el CI apareció un fallo real: cinco tests PG asertaban que
la head de Alembic era `030_strategy_lifecycle`, pero la migración **031**
(`031_sim_fill_strategy_attr`, V2.28) pasó a ser la head.

```
RuntimeError: alembic_version is {'031_sim_fill_strategy_attr'};
expected 030_strategy_lifecycle (V2.25 head)
```

El patrón ya se había corregido dos veces a mano en commits anteriores
(`fix 029 -> 030`, `fix 028 -> 029`): cada migración rompía las guardias. Esta versión
elimina la causa raíz.

### Hallazgo mayor: drift de 27 migraciones invisible

Dos tests que **se creían** auto-derivados seguían anclados a `004_ledger_reference_unique`:

- `packages/py/infrastructure/tests/test_f3b_alembic_data_epoch.py` (assert a `004`)
- `packages/py/infrastructure/tests/test_ledger_entries_reference_unique.py` (`_HEAD = "004_..."`)

Llevaban **27 migraciones** desactualizados sin que nadie lo notara, porque
**no se ejecutaban en ningún job de CI**. El CI decía "verde" sobre tests que no
corrían: exactamente el tipo de falsa garantía que invalida una auditoría.

---

## 2. Cambios

### 2.1 Helper `alembic_head()` (causa raíz)

`packages/py/infrastructure/src/bolsa_infrastructure/database/migrations.py`:

```python
def alembic_head() -> str:
    from alembic.script import ScriptDirectory

    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"se esperaba una única head lineal, encontradas {len(heads)}: {heads}")
    return heads[0]
```

Deriva la head del filesystem de migraciones (no de la BD) y exige una única head
lineal. Reutiliza `_alembic_config()` con rutas absolutas, así que resuelve igual
invocado desde `packages/py/*` o desde `apps/api-python`.

### 2.2 Guardias derivadas, no hardcodeadas

Sustituidas por `alembic_head()` en:

- `packages/py/infrastructure/tests/test_f3b_alembic_data_epoch.py`
- `packages/py/infrastructure/tests/test_ledger_entries_reference_unique.py`
- `packages/py/infrastructure/tests/test_lifecycle_event_store_pg.py`
- `apps/api-python/tests/test_financial_integrity_pg.py`
- `apps/api-python/tests/test_lifecycle_outbox_worker_pg.py`
- `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py`
- `apps/api-python/tests/test_e2_v2_14_incident_dedup_pg.py`

Los asserts que fijan revisiones **concretas** en el texto de una migración
(p.ej. `test_live_order_store_pg.py` sobre `020`/`021`) se dejan intactos: verifican
esa migración, no la head.

### 2.3 Test de concurrencia PG hermético

`apps/api-python/tests/test_live_order_recovery_concurrency_pg.py` era **no hermético**:
`_seed_unknown` hace `commit` y ningún teardown limpiaba, así que el primer test dejaba
una fila UNKNOWN persistida y el segundo fallaba deterministamente
(`lote no cubierto: ... extra {'lo-conc-...'}`) incluso partiendo de BD limpia.

Añadido helper `_purge_account()` (borra por `account_id`, no `TRUNCATE`, respetando el
aislamiento multi-cuenta) e invocado en `finally` en ambos tests.

Nota: **no** se añade filtro por cuenta a `claim_unknown_batch`; es global por diseño
(recovery cross-PID). El defecto era del test, no de producción.

### 2.4 Cierre del hueco de CI

`.github/workflows/release-tag-ci.yml`:

- Job `lifecycle-pg`: incorporados los 7 tests PG que estaban fuera de todos los jobs
  (`test_f3b_alembic_data_epoch`, `test_ledger_entries_reference_unique`,
  `test_execution_event_fence_pg`, `test_live_order_store_pg`,
  `test_submit_intent_store_pg`, `test_e2_v2_14_incident_dedup_pg`,
  `test_live_order_recovery_concurrency_pg`).
- Gates fail-if-skipped nuevos: `LIVE_PG_REQUIRED=1`, `E2_PG_REQUIRED=1`,
  `EXECUTION_FENCE_PG_REQUIRED=1`. Además, `test_f3b` y `test_ledger` pasan a respetar
  `LIFECYCLE_PG_REQUIRED=1` (antes hacían skip incondicional).
- Job `python`: `--ignore` explícito de los `*_pg.py` que ahora corren en `lifecycle-pg`,
  para que no se recoleten sin PG (hoy se colaban por el directorio `apps/api-python/tests`).

### 2.5 Marcador shadow documentado

`packages/py/application/src/bolsa_application/strategy_lifecycle_store.py`
(`save_active`): `shadow_validated=True` **no se cambia** — es un marcador de
materialización que `get_active` usa como localizador (busca por `finalist_id` +
`promoted`). Se añade comentario explícito de que **no** es evidencia de validación
shadow (esa vive en el Promotion Gate). `ActiveStrategy` no expone `shadow_validated`,
así que no es posible propagar el valor real sin tocar el dominio; cambiar la semántica
es parte del trabajo de shadow real (V2.31+).

---

## 3. Verificación

- `uv run ruff check packages/py apps/api-python --config pyproject.toml` → limpio.
- `uv run lint-imports --config packages/py/.importlinter` → 4 contratos KEPT.
- Batería PG ampliada del job `lifecycle-pg`, **dos pasadas consecutivas** con los gates
  activos contra `bolsa-postgres` → **58 passed** en ambas (prueba de hermeticidad).
- `Release tag CI` del tag `v2.30-beta` en GitHub → verde, incluido `certify`.

---

## 4. Deuda de higiene residual (no bloqueante)

- Comentarios/etiquetas con head obsoleta en algún docstring de chaos y en el propio
  workflow (`hoy 025`): cosmético, no afecta a ninguna aserción.
- Los tests PG que se commitean y no limpian en otros ficheros (`test_strategy_lifecycle_pg`,
  `test_lifecycle_outbox_worker_pg`, ...) comparten el riesgo de residuo, pero al usar
  cuentas/ids únicos no se ha observado envenenamiento entre tests. Candidatos a un
  barrido de hermeticidad futuro.

---

## 5. Fuera de alcance (deuda de producto, diferida)

Sin cambios en V2.30; siguen pendientes y documentadas:

- **`StrategyDiscoveryEngine`**: no existe selector sobre los 30+ indicadores de
  `bolsa_analytics.indicators.compute`; se optimizan 3 familias (`SUPPORTED_FAMILIES`).
- **Shadow automático**: `AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1` certifica sin ejecutar;
  falta entidad/store de evidencia (`ShadowValidation`; `StrategyValidation` solo lleva gates).
- **Atribución tras crash**: los cierres de posiciones readoptadas quedan sin versión
  (la proyección durable no la guarda) — límite documentado en V2.28.

---

## 6. Por qué esto deja el repo auditable

Antes: el CI podía estar verde sin ejecutar 7 tests PG, dos de los cuales llevaban 27
migraciones esperando una head inexistente, y las guardias se parcheaban a mano en cada
migración. Ahora: la head se deriva de una única fuente (`alembic_head()`), los tests PG
que antes no corrían se ejecutan con gate fail-if-skipped, y el test no hermético dejó
de envenenar la suite. Un skip silencioso ya no pasa por verde.
