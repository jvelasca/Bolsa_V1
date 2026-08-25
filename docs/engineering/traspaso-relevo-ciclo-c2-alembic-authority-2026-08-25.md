# RELEVO — Ciclo C2 Alembic única autoridad (v1.8.1) · 2026-08-25

> **Padre:** [`plan-ciclo-c2-alembic-authority-2026-08-25.md`](./plan-ciclo-c2-alembic-authority-2026-08-25.md) · C1 [`traspaso-relevo-ciclo-c1-hoy-honesty-help-2026-08-25.md`](./traspaso-relevo-ciclo-c1-hoy-honesty-help-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO** (commit ola 1). E1 = C3 ActionQueue.
> **Arranque:** este fichero + `CURRENT_SYSTEM.md` + ADR-025 enmienda C2.

---

## 0. Qué quedó hecho

| Pieza                                                   | Estado                                                      |
| ------------------------------------------------------- | ----------------------------------------------------------- |
| Públicos `db:push` / `db:migrate` / `db:migrate:deploy` | fail-closed · `scripts/prisma-not-authoritative.mjs`        |
| Bootstrap setup / db-ensure / db-check                  | `runAlembicUpgrade` → `ensure_migrated`                     |
| Prisma                                                  | seed + `db:generate`; `legacy:prisma:*` no públicos         |
| ADR-025                                                 | enmendado: Alembic dueño DDL                                |
| Test D6                                                 | `node scripts/research/verify_prisma_not_authoritative.mjs` |

## 1. Freeze / siguiente

- **C3** ActionQueue. **No** reescribir Alembic `010`. **No** dual-schema.
- `PAPER_D_EXECUTE` off · broker **no** · thin 5.x/8.x parked.

## 2. E1

1. Ciclo **C3** `buildActionQueue` + Hoy slice top-8.
2. No C4/C5 hasta cerrar C3.
