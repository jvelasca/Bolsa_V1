# packages/database — Prisma (tooling)

Este paquete **no es runtime** de la aplicación. Se usa únicamente para:

- **Migraciones** SQL (`prisma migrate`)
- **Seed** del catálogo IBEX (`prisma db seed`)
- **Inspección** ocasional del esquema (`scripts/inspect_db.py`)

La API FastAPI (`apps/api-python`) accede a PostgreSQL vía **SQLAlchemy** en `packages/py/infrastructure`, no vía Prisma Client.

## Comandos habituales

```bash
pnpm db:ensure          # Docker + migrate + seed (desde raíz)
pnpm --filter @bolsa/database exec prisma migrate deploy
```

Tras cambiar `prisma/schema.prisma`, genera migración y aplica desde la raíz del monorepo.
