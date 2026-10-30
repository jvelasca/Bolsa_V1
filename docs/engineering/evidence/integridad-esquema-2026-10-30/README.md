# Expediente A — integridad del esquema (2026-10-30)

Cierra los dos defectos que dejaban rojo el gate `SCHEMA_DRIFT_PG_REQUIRED` en la rama
de integración, **sin tocar la 061** ni la fusión de los tres commits ya materializados.

## Los dos defectos, medidos

### 1. `CHECK` de `sync_settings` ausente en bases nuevas

La `060` creaba `sync_settings_provider_check_interval_check` **dentro** de
`if not _column_exists(provider_check_interval_seconds)`. En una base nueva la baseline
(`003_prisma_schema_baseline`) crea esa columna **desde los metadatos**, así que la rama
nunca se ejecutaba y el `CHECK` quedaba ausente.

Reproducido con el árbol anterior (`06653971`) sobre una base desechable:

```
[1/2] BD heredada: árbol ANTERIOR -> 061_profile_delete_restrict
revisión tras árbol viejo: 061_profile_delete_restrict
CHECK tras árbol viejo   : None   <-- defecto reproducido
```

En una base **heredada** ya estampada en `060`/`061` la revisión no se vuelve a ejecutar,
así que corregir la `060` no basta: hace falta una revisión nueva.

### 2. Acciones de FK invisibles para Alembic

`investment_accounts_active_profile_id_fkey` está en la BD con
`ON DELETE RESTRICT` + `ON UPDATE CASCADE` (catálogo ART-PROFILE y la `061` lo conserva),
mientras la metadata declaraba `SET NULL` sin `onupdate`.

Alembic 1.19.1 **no compara acciones de FK**: `compare_metadata` no lo veía. Medido contra
la BD compartida en `060` (FK todavía `SET NULL`), el gate nuevo sí lo detecta:

```
FK drift bolsa_v1 (060, FK SET NULL):
  ('investment_accounts', 'active_profile_id', "ON DELETE metadata='RESTRICT'", "BD='n'")
```

## Qué se cambió

| Pieza | Fichero | Cambio |
|---|---|---|
| Migración 060 | `packages/py/infrastructure/alembic/versions/060_provider_check_policy.py` | El `CHECK` se decide por su propia existencia, fuera del bloque de la columna |
| Migración 062 | `packages/py/infrastructure/alembic/versions/062_sync_settings_check_backfill.py` | Repara bases heredadas; idempotente y fail-closed si el `CHECK` existe con otra definición |
| Metadata | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` | `onupdate="CASCADE"` en la FK de `active_profile_id` (declara lo que la BD ya tiene; sin DDL) |
| Contrato | `packages/py/infrastructure/tests/test_schema_contract.py` | Exige `ondelete=RESTRICT` **y** `onupdate=CASCADE` |
| Gate de drift | `apps/api-python/tests/test_schema_drift_gate_pg.py` | Nueva aserción PG de acciones de FK contra `pg_constraint` |
| Ciclo de la 062 | `packages/py/infrastructure/tests/test_062_sync_settings_check_pg.py` | Base nueva, heredada, idempotencia, fail-closed y downgrade |
| CI | `.github/workflows/python-ci.yml` | `SYNC_SETTINGS_CHECK_PG_REQUIRED=1` y el test nuevo en `lifecycle-pg` |

La 061 quedó **intacta** (`git diff 06653971 -- .../061_profile_delete_restrict.py` vacío).

## Verificación (medida)

Sonda: [`probe.py`](./probe.py) — crea `bolsa_ev_a_legacy` y `bolsa_ev_a_new`, nunca toca
`bolsa_v1` ni `bolsa_v1_integracion`.

```
$ uv run python docs/engineering/evidence/integridad-esquema-2026-10-30/probe.py
head del árbol corregido : 062_sync_settings_check_backfill

[1/2] BD heredada: árbol ANTERIOR -> 061_profile_delete_restrict
revisión tras árbol viejo: 061_profile_delete_restrict
CHECK tras árbol viejo   : None   <-- defecto reproducido

=== BD heredada tras aplicar el árbol corregido ===
alembic_version        : 062_sync_settings_check_backfill
check definición        : CHECK (((provider_check_interval_seconds >= 15) AND (provider_check_interval_seconds <= 3600)))
FK confdeltype/updtype  : ('r', 'c')
compare_metadata        : SIN DIFERENCIAS
acciones de FK          : SIN DIFERENCIAS

[2/2] BD nueva: árbol corregido -> head

=== BD nueva tras el árbol corregido ===
alembic_version        : 062_sync_settings_check_backfill
check definición        : CHECK (((provider_check_interval_seconds >= 15) AND (provider_check_interval_seconds <= 3600)))
FK confdeltype/updtype  : ('r', 'c')
compare_metadata        : SIN DIFERENCIAS
acciones de FK          : SIN DIFERENCIAS
```

| Gate | Resultado |
|---|---|
| `test_062_sync_settings_check_pg.py` (PG, gate `SYNC_SETTINGS_CHECK_PG_REQUIRED=1`) | **4 passed** |
| `test_schema_drift_gate_pg.py` (PG, gate `SCHEMA_DRIFT_PG_REQUIRED=1`) | **3 passed** |
| `test_schema_contract.py` + `test_061_profile_delete_restrict.py` | **16 passed** |
| `alembic_head()` | `062_sync_settings_check_backfill` (única head lineal) |
| `ruff` (ficheros tocados, `--config pyproject.toml`) | sin errores |

## Límites y estado de las bases

- `bolsa_v1` (compartida) sigue en **060** y no se tocó; su FK está en `SET NULL` a
  propósito: la 061 solo se aplica cuando el árbol fiscal adopte la cadena completa.
- `bolsa_v1_integracion` sigue en **061** (scratch de integración, no operativa).
- Las bases de la sonda se conservan para inspección; `probe.py --drop` las elimina.
- La `062` es la única vía de reparación de bases ya estampadas; la corrección de la
  `060` solo protege a las bases nuevas.
- La `062` **no sobrescribe** un `CHECK` homónimo con otra definición: aborta y deja la
  revisión sin marcar para que el operador decida.
