# Handoff 061 — Ventana BD: diagnóstico read-only y verdad de esquema (2026-10-29)

Rama: `fix/059-060-proveedores` (sobre `393c45fe`, con 059+060 ya commiteadas).

## Qué se entrega

### 1. Diagnóstico read-only (`Configuración → BD`)

`GET /api/database/maintenance` → `GetDatabaseMaintenance` (aplicación) con dos puertos:

| Puerto | Adaptador | Fuente |
|--------|-----------|--------|
| `SchemaContract` | `SchemaContractAdapter` | `Base.metadata` + allowlist |
| `BackupInventory` | `BackupInventoryAdapter` | `db-backups/backups-manifest.json` + FS |

Bloques publicados: `schema`, `capacity`, `maintenance`, `connections`, `backups`, `integrity`.
Consultas de solo lectura sobre `alembic_version`, `information_schema`, `pg_constraint`,
`pg_database_size`, `pg_stat_user_tables`, `pg_stat_activity`, `pg_settings` y conteos acotados
de integridad.

Doctrina aplicada:

- **Sin medición no hay verde**: la métrica no disponible se publica `unknown` con motivo.
- `error > warning > ok > unknown` al agregar.
- **200 con la BD caída** (`connected=false`), para que la UI explique el fallo.
- Cero acciones de escritura: ni VACUUM/ANALYZE, ni migraciones, ni copias, ni purgas.

### 2. Verdad de esquema (`alembic check` como gate)

- `SyncSettingsRow` declara el `CHECK` `sync_settings_provider_check_interval_check` (15..3600)
  que creó la migración 060. Solo metadatos: no hay migración nueva.
- `packages/py/infrastructure/src/bolsa_infrastructure/database/schema_contract.py`:
  `KNOWN_SCHEMA_DIVERGENCES` con **motivo por entrada** (custody_obligation, índices históricos,
  pares índice-único/constraint, CHECK de `live_orders`, `alembic_version`).
- `alembic/env.py` aplica `include_object` en offline y online (también con conexión inyectada).
- Tests: `packages/py/infrastructure/tests/test_schema_contract.py` (metadatos + allowlist) y
  `apps/api-python/tests/test_schema_drift_gate_pg.py` (`compare_metadata` == []).

`alembic check` → `No new upgrade operations detected.`

### 3. Intervalo de servidores de vuelta a 60 s

`PATCH /api/sync/settings {"providerCheckIntervalSeconds": 60}` y verificación SQL:

```
provider_check_enabled = True, provider_check_interval_seconds = 60
```

## Verificación ejecutada

| Gate | Resultado |
|------|-----------|
| `alembic check` | Sin operaciones pendientes |
| `pytest tests/test_schema_drift_gate_pg.py tests/test_database_maintenance_api.py tests/test_database_maintenance_pg.py` | 6 passed |
| `pytest packages/py/infrastructure/tests/test_schema_contract.py` | 4 passed |
| `vitest run src/features/config/database-maintenance-panel.test.tsx` | 3 passed |
| `pnpm --filter @bolsa/shared build` · `pnpm --filter @bolsa/web typecheck` | OK |
| `GET /api/database/maintenance` (instancia temporal :8010) | 200, `connected=true`, `schema=ok`, `integrity=ok` |

Los tres tests PG nuevos quedan cableados en el job `lifecycle-pg` de
`.github/workflows/python-ci.yml` con gates fail-if-skipped
(`SCHEMA_DRIFT_PG_REQUIRED`, `DATABASE_MAINTENANCE_PG_REQUIRED`, `MARKET_PROVIDERS_PG_REQUIRED`):
un skip silencioso es un fallo duro, igual que una divergencia nueva de esquema.

Salida real del endpoint (resumen): esquema en `060_provider_check_policy`, 87 tablas del
contrato presentes, 21 divergencias históricas declaradas, 49.1 MB, autovacuum activo,
13 conexiones, copia más reciente de 52.3 h tomada en `035_paper_forward_evidence` → `warning`
honesto (no hay copia reciente ni espejo).

## Límites

- No se ejecutan acciones de escritura sobre la BD.
- No se aplican migraciones desde la UI.
- No se crea ni restaura ninguna copia; solo se reporta su estado.
- La allowlist de drift es **deuda declarada**: cada entrada lleva motivo y el gate falla ante
  una divergencia nueva. No se amplía sin justificarla en la PR.
