# Integración Cuentas / Perfil inversor sobre el árbol fiscal (2026-10-30)

- **Base**: `c9e572cb` (`Bolsa_V1`, `fix/059-060-proveedores`, `.173` publicado).
- **Origen del primer bloque**: `a5f6f1c6` + el WIP auditado de
  `feat/cuentas-perfil-2026-10-30`.
- **Rama de integración**: `integracion/cuentas-perfil-2026-10-30`, worktree propio en
  `.cursor/worktrees/integracion-cuentas-perfil-2026-10-30`, **BD propia**
  (`bolsa_v1_integracion`).
- **Sin push, sin PR, sin tag y sin Release.** `Bolsa_V1` intacto (mismo HEAD, mismos
  hashes en los 65 paths de su working tree).

## 1. Los commits

| # | Hash | Mensaje | Tamaño |
|---|---|---|---|
| 1 | `31f23a6b` | `feat(cuentas): perfil inversor en la ficha, desasignación explícita y FK RESTRICT (061)` | 84 ficheros, +6.906 / −388 |
| 2 | `9fb39d12` | `chore(integracion): snapshot del WIP fiscal-comisiones 2026-10-30 (fusionado)` | 65 ficheros, +4.049 / −411 |
| 3 | (este) | `docs(integracion): nota y evidencia medida` | nota + evidencia |

El commit 1 es **el candidato auditado, sin cambios**: su árbol difiere del commit
`66d76d26` del worktree candidato solo en los dos ficheros que aporta `c9e572cb`
(`CHANGELOG.md` y su README de evidencia). Ese commit se creó en el worktree candidato con
la rama `feat/cuentas-perfil-2026-10-30` ya commiteada, y se cherry-pickeó aquí.

El commit 2 **no es el sello del bloque fiscal**: es una copia para integrar y revisar. El
día que el bloque fiscal se selle, su commit tendrá que reconciliarse con este (mismo
contenido, distinto autor y orden).

El commit 3 solo añade documentación y evidencia; los commits 1 y 2 quedan exactamente
como se especificó.

## 2. Cómo se materializó

1. **59 paths fiscales no solapados** copiados byte a byte (`Copy-Item`), verificados con
   SHA-256 fichero a fichero: **0 discrepancias**.
2. **6 paths solapados** resueltos por fusión, nunca por sobrescritura:

| Fichero | Resolución |
|---|---|
| `account-settings-panel.tsx` | Base fiscal completa (presets, `initialTab`, `validateAccountSettings`, `describeCommissionPreset`) y se retira el import, la prop `activeProfileId` y el bloque `<AccountInvestorProfileSelect>` del render |
| `account-settings-dialog.tsx` | `initialTab` fiscal + título/descripción del candidato («Comisiones y fiscal de la cuenta») y sin `activeProfileId` hacia el panel |
| `account-detail-panel.tsx` | Base candidato (perfil en cabecera, `focus=perfil`, `profilesQuery`, P&L realizado, `profileRef`) + resumen fiscal con `describeCommissionPreset`/`describeCommissionProfile`/`describeTaxProfile`, deep-link `focus=fiscal` e `initialTab` al diálogo; el botón usa el copy del candidato |
| `create-account-wizard-dialog.tsx` | Base fiscal (tipos, `currency`, `tax`, `COST_BASIS_LABELS`) + `accountsQuery`, `profileUsage` y `usedByAccounts` del candidato con su aviso de asignación |
| `account-settings-panel.test.tsx` | Un fichero con **9 casos**: los 8 fiscales + el del candidato (sin selector de perfil, botón «Guardar comisiones y fiscal»). Se retira el mock de `AccountInvestorProfileSelect` (el panel ya no lo renderiza) y se conserva el de `AccountVenuePreference` |
| `python-ci.yml` | Job `lifecycle-pg` fiscal (`MARKET_PROVIDERS_PG_REQUIRED`, `SCHEMA_DRIFT_PG_REQUIRED`, `DATABASE_MAINTENANCE_PG_REQUIRED` + paths nuevos) + step del candidato `Pytest integridad 061 PG (fail if skipped)` justo después de `Alembic upgrade head` y antes de `Pytest A12 PG` |

`platform-config-dialog.tsx` lo toca solo el candidato (quita la exigencia de cuenta activa
y las props `activeProfileId`), así que no colisiona.

## 3. La 061 por la ruta real de despliegue

Detalle completo en
[`evidence/integracion-cuentas-perfil-fiscal-2026-10-30/certificacion-061.txt`](evidence/integracion-cuentas-perfil-fiscal-2026-10-30/certificacion-061.txt).

Resumen: `db-restore --target-db bolsa_v1_integracion` (que llama a
`runDbMigrateDeploy` → `ensure_migrated`, la misma ruta que `database_bootstrap`) llevó la
copia heredada de 060 a **061** con la asignación viva intacta (1 cuenta, 1 perfil, 0
huérfanos); `ensure_migrated` repetido dos veces **no cambia el `oid`** de la FK (613733);
`downgrade_to('060…')` → `'n'` y `migrate_to('head')` → `'r'` sin perder datos; y el API
arrancó contra esa BD (`/api/health` 200, `schema_revision = 061`).

Ventana de bloqueo declarada: `DROP + ADD CONSTRAINT` viaja en la transacción de Alembic y
toma `ACCESS EXCLUSIVE` sobre `investment_accounts` (milisegundos; un lector concurrente
nunca ve la FK ausente).

## 4. El incidente que impedía arrancar la APP

La BD de desarrollo `bolsa_v1` quedó estampada en `061_profile_delete_restrict` por el stack
del worktree candidato, mientras `Bolsa_V1` solo conoce hasta `060`:
`CommandError: Can't locate revision identified by '061_profile_delete_restrict'` en
`ensure_migrated` y caída del lifespan.

- **Reparado** con `downgrade_to("060_provider_check_policy")` desde el worktree candidato:
  `alembic_version = 060`, FK de vuelta a `SET NULL` (`confdeltype='n'`), datos intactos
  (la cuenta conserva su perfil) y 0 huérfanos.
- **Verificado**: `ensure_migrated` del árbol fiscal devuelve `True` y su API arranca
  (`/api/health` 200 con `schema_revision = 060_provider_check_policy`).
- **Prevención**: este worktree tiene su propia BD (`bolsa_v1_integracion`). La 061 solo se
  volverá a aplicar sobre `bolsa_v1` cuando la integración se adopte de forma expresa
  (entonces la 061 ya existirá en el árbol que la ejecute).

## 5. Gates medidos

Tabla completa en
[`evidence/integracion-cuentas-perfil-fiscal-2026-10-30/README.md`](evidence/integracion-cuentas-perfil-fiscal-2026-10-30/README.md).

Lo relevante: TypeScript raíz 4/4, ESLint 0 errores, `contract:check` OK, Vitest web
**355 ficheros / 2.659 tests ×2**, shared 878+1 `todo`, pytest dirigido **63 passed**,
integración accounts/tax 7 passed, mypy **582 ficheros**, YAML del CI válido y smoke E2E
**12/12** con capturas.

## 6. Lo que NO queda verde, y por qué

1. **`alembic check` / gate de drift** (`SCHEMA_DRIFT_PG_REQUIRED`): falla por **dos causas
   preexistentes** del bloque fiscal, reproducidas también en `Bolsa_V1`:
   - la FK tiene `ON UPDATE CASCADE` en la BD y la metadata no lo declara (aparece ya en 060);
   - en BD nuevas falta el `CHECK` de `sync_settings`, porque la 060 lo crea solo dentro de
     `if not _column_exists(provider_check_interval_seconds)` y la baseline ya trae la columna.

   No se tocó: cambiar la 061 alteraría el candidato auditado, y tocar la 060 es del dueño
   del bloque fiscal. **Este es el único punto que deja rojo el CI fusionado.**
2. **`ruff`**: `pyproject` pide `ruff>=0.9` y `uv.lock` no lo fija → hoy resuelve 0.16.2, que
   marca **827 I001** aquí y **824** en `Bolsa_V1` (deriva de herramienta sobre ~800
   ficheros, no del cambio). Los ficheros del diff no aportan errores del gate.

## 7. Deuda abierta (sin cambios respecto a los bloques)

- **AUD-02**: la UI de `409` no enumera las cuentas afectadas (el payload sí).
- **AUD-04 / AUD-05 / AUD-06 / AUD-08 / AUD-09**: ver el seguimiento del bloque Cuentas.
- **Sello fiscal pendiente**: este commit 2 es copia, no sello.
- **Drift de esquema** (punto 6.1) y **`ruff` sin fijar** (punto 6.2).

## 8. Rollback

```powershell
git worktree remove .cursor/worktrees/integracion-cuentas-perfil-2026-10-30
git branch -D integracion/cuentas-perfil-2026-10-30
# y, si se quiere limpiar la scratch:
# DROP DATABASE bolsa_v1_integracion WITH (FORCE);
```

`bolsa_v1` queda en **060**, consistente con el árbol fiscal. Los commits 1 y 2 son
autocontenidos: no hay nada publicado.
