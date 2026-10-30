# Cierre de los expedientes A y B (2026-10-30)

**Dictamen: los dos gates que bloqueaban la integración quedan cerrados y medidos en
verde. No se publica nada: sin push, sin PR, sin tag y sin Release.**

Rama de integración: `integracion/cuentas-perfil-2026-10-30`. Los tres commits
materializados (`31f23a6b`, `9fb39d12`, `06653971`) siguen intactos: `06653971` es
ancestro de la cabeza, la `061` no cambia ni un byte y la fusión entra como commits
nuevos.

## Expediente A — integridad del esquema

**Defecto 1 (CHECK de `sync_settings`).** La `060` creaba
`sync_settings_provider_check_interval_check` dentro del bloque de la columna. En una base
nueva la baseline ya trae la columna desde los metadatos, así que el `CHECK` nunca se
creaba. Reproducido con el árbol anterior sobre una BD desechable (`CHECK tras árbol
viejo: None`) y reparado por dos vías:

- `060` corregida: decide el `CHECK` por su propia existencia, no por la columna;
- `062_sync_settings_check_backfill`: idempotente, fail-closed si el constraint existe
  con otra definición, y única vía para bases ya estampadas en `060`/`061`.

**Defecto 2 (acciones de FK invisibles).** Alembic 1.19.1 no compara `onupdate`/`ondelete`.
La BD tiene `investment_accounts_active_profile_id_fkey` con `RESTRICT` + `ON UPDATE
CASCADE`; la metadata declaraba `SET NULL` sin `onupdate`. Ahora la metadata declara
`onupdate="CASCADE"` (sin DDL nuevo) y el gate de drift compara **todas** las FK contra
`pg_constraint` (con la allowlist de `custody_obligation` como única deuda tolerada).

Evidencia: [`evidence/integridad-esquema-2026-10-30/`](evidence/integridad-esquema-2026-10-30/README.md)
(`probe.py`, salida completa y `gates-final.txt`).

## Expediente B — Ruff reproducible

El rojo masivo no era deriva de versión: era el `Makefile` invocando Ruff **sin
`--config`**. Medido con `ruff 0.16.2`: con `--config` el árbol base da **0** errores y el
integrado **2** (`I001` reales); sin `--config` da **824/828** falsos positivos.

- `ruff==0.16.2` en `pyproject.toml` (raíz) y `apps/api-python/pyproject.toml`; `uv.lock`
  regenerado (solo cambia el specifier, la versión resuelta sigue en 0.16.2).
- `Makefile`: `lint` y `format` con `--config pyproject.toml`.
- CI (`quality`): `uv sync --frozen` y guardia que falla si el binario no es
  exactamente `ruff 0.16.2`.
- Los **2 únicos** `I001` reales (`test_accounts.py`, `test_tax_report.py`) se corrigieron
  con `--fix` acotado a esos dos ficheros en la fusión (en la base común están limpios).

Evidencia: [`evidence/ruff-reproducible-2026-10-30/`](evidence/ruff-reproducible-2026-10-30/README.md)
y `ruff.txt` regenerado en la evidencia de integración.

## Gates medidos (cabeza de integración)

| Gate | Comando | Resultado |
|---|---|---|
| Drift + acciones de FK + 061/062 | pytest con `SCHEMA_DRIFT_PG_REQUIRED=1` y `SYNC_SETTINGS_CHECK_PG_REQUIRED=1` | **27 passed** |
| Área perfiles / guard / asignación | pytest | **17 passed** |
| Ruff (CI exacto) | `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| Import-linter | `lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| mypy | dominio, mercado, infraestructura, API | **308 ficheros, sin issues** |
| TypeScript | `pnpm typecheck` | **4/4** |
| ESLint | `pnpm lint` | **4/4** (0 errores; 23 warnings preexistentes) |
| Contrato OpenAPI | `pnpm contract:check` | **OK** |
| Vitest web | `pnpm test` | **355 ficheros / 2659 tests** |
| Sonda A, BD heredada | árbol viejo -> 061 sin CHECK -> árbol corregido | **CHECK recreado, sin drift, FK `('r','c')`** |
| Sonda A, BD nueva | árbol corregido -> head | **CHECK presente, sin drift** |

Salida completa en [`evidence/integridad-esquema-2026-10-30/gates-final.txt`](evidence/integridad-esquema-2026-10-30/gates-final.txt).

## Commits de la fusión

```
582f6f4b style(tests): ordena imports de test_accounts y test_tax_report (I001 real)
fb4e32c6 merge: expediente B (Ruff reproducible 0.16.2)
6038def0 merge: expediente A (integridad de esquema)
1b263b5d chore(lint): fija ruff 0.16.2 y alinea la invocacion con --config      (rama B)
1bd34bb8 fix(esquema): cierra el drift del CHECK de 060 y de las acciones de FK  (rama A)
06653971 docs(integracion): nota y evidencia medida ...                          (intacto)
```

## Estado de las bases

- `bolsa_v1` (compartida): sigue en **060**, no se tocó.
- `bolsa_v1_integracion`: sigue en **061**; sigue documentada como *scratch* de
  integración, no operativa. No se le aplicó ninguna migración nueva.
- `bolsa_ev_a_legacy` / `bolsa_ev_a_new`: BDs desechables de la sonda, se conservan para
  inspección; `probe.py --drop` las elimina. Ninguna es la BD operativa.

## Lo que NO se re-ejecutó y por qué

- **Smoke E2E 12/12**: la superficie UI no la tocan ni A ni B (los gates de UI —typecheck,
  ESLint, contrato y 2659 tests de Vitest— están verdes) y re-ejecutarlo exigiría arrancar
  la API contra `bolsa_v1_integracion`, lo que aplicaría la `062` y mutaría la BD de
  evidencia, prohibido por el propio plan. El smoke previo sigue siendo válido para la UI
  sin cambios.

## Confirmación expresa

**Sin push. Sin PR. Sin tag. Sin Release.** Todo el trabajo vive en las ramas locales
`fix/schema-integridad-2026-10-30`, `chore/ruff-reproducible-2026-10-30` e
`integracion/cuentas-perfil-2026-10-30`.
