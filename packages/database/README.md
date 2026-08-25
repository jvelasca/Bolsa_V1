# packages/database — Prisma (tooling seed/generate)

Este paquete **no es runtime** y **no es autoridad de schema**. Se usa únicamente para:

- **Generate** del Prisma Client (`pnpm db:generate`)
- **Seed** del catálogo IBEX (`pnpm db:seed`)
- **Inspección** ocasional (`pnpm db:studio`)

El DDL lo aplica **Alembic** (`bolsa_infrastructure.database.migrations.ensure_migrated` / `alembic upgrade head`). Comandos públicos `db:push` / `db:migrate` / `db:migrate:deploy` **fail-closed**.

La API FastAPI (`apps/api-python`) accede a PostgreSQL vía **SQLAlchemy** en `packages/py/infrastructure`, no vía Prisma Client.

## Comandos habituales

```bash
pnpm db:ensure          # Docker + Alembic upgrade + seed (desde raíz)
pnpm db:generate        # Prisma Client (seed)
pnpm db:seed            # Catálogo IBEX
```

Emergencia (no públicos): `legacy:prisma:*` en este `package.json`.
