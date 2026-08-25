# Plan — Ciclo C2 Alembic única autoridad (v1.8.1)

> **Padre:** [`roadmap-v181-operational-consolidation-2026-08-25.md`](./roadmap-v181-operational-consolidation-2026-08-25.md) · [`traspaso-relevo-ciclo-c1-hoy-honesty-help-2026-08-25.md`](./traspaso-relevo-ciclo-c1-hoy-honesty-help-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **ABIERTA**.
> **Método:** P1 arquitectura; Ranking ≠ BUY; **no** reescribir Alembic `010`; sin `contract:gen`; sin LLM; **no** tocar spine/Hoy/TradePlan.

---

## 0. Objetivo

`CURRENT_SYSTEM` declara Alembic = autoridad de schema. Prisma sigue en comandos públicos (`db:push` / `db:migrate`) y en bootstrap (`setup.mjs` `runDbPush`, `db-ensure` Prisma deploy). C2 cierra esa doble autoridad.

### Qué entra vs qué queda fuera

| Incluye (C2)                                                               | Excluye                        |
| -------------------------------------------------------------------------- | ------------------------------ |
| `pnpm db:push` / `db:migrate` / `db:migrate:deploy` públicos fallan        | Reescribir árbol Alembic `010` |
| Bootstrap `setup` / `db-ensure` / `db-check` → Alembic (`ensure_migrated`) | Dual-schema Prisma+Alembic     |
| Prisma queda seed + `db:generate`                                          | Spine / Hoy / TradePlan        |
| Enmendar ADR-025                                                           | `contract:gen` · thaw · broker |

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                                               |
| --- | -------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Alembic (`ensure_migrated` / `alembic upgrade head`) es el único camino de schema. Prisma = seed + `db:generate`.                      |
| D2  | Públicos `db:push` / `db:migrate` / `db:migrate:deploy` **fail-closed** con mensaje `Prisma schema is not authoritative. Use Alembic.` |
| D3  | `runDbMigrateDeploy` / `runDbPush` dejan de llamar Prisma; bootstrap usa Alembic. `db:seed` y `db:generate` intactos.                  |
| D4  | Enmendar ADR-025 (ya no «Prisma dueño del DDL hoy»). Sin dual-schema.                                                                  |
| D5  | No tocar spine / Hoy / TradePlan / check_opening.                                                                                      |
| D6  | Test o script: `pnpm db:push` exit ≠ 0 + substring del mensaje.                                                                        |
| D7  | Stamp CURRENT_SYSTEM + README / ONBOARDING / docker.md / packages/database/README si mencionan `db:push`.                              |
| D8  | Relevo C2. E1 = C3 ActionQueue.                                                                                                        |

Si D2 deja `db:push` operativo, D3 sigue llamando Prisma, o se recrea schema: **parar**.

---

## 2. Ficheros

- `package.json` · `packages/database/package.json`
- `scripts/lib/db.mjs` · `scripts/db-ensure.mjs` · `scripts/db-check.mjs` · `scripts/setup.mjs`
- `docs/adr/025-data-model-source-of-truth.md` · `docs/ONBOARDING.md` · `docs/docker.md` · `packages/database/README.md` · `README.md`
- `bolsa_infrastructure.database.migrations.ensure_migrated` (reusar, no reescribir `010`)

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · C1 intacto · 5.x/8.x parked · `PAPER_D_EXECUTE` off · broker no.
