# ADR-025 — Fuente de verdad única del modelo de datos (Alembic dueño del DDL · Prisma tooling)

- **Estado:** Accepted — 2026-08-10 (M4) · **enmendado 2026-08-25 Ciclo C2**
- **Tipo:** decisión de arquitectura / modelo de datos
- **Padres:** [ADR-001](./001-database-choice.md) (PostgreSQL + Prisma histórico) · [ADR-003](./003-python-backend-ai-platform.md) §9 (strangler TS→Python · migraciones Alembic) · [DATA_MODEL.md](../DATA_MODEL.md)
- **Contexto de auditoría:** [traspaso-m4-infraestructura-datos-2026-08-10.md](../engineering/traspaso-m4-infraestructura-datos-2026-08-10.md) · [plan-ciclo-c2-alembic-authority-2026-08-25.md](../engineering/plan-ciclo-c2-alembic-authority-2026-08-25.md)

---

## Enmienda C2 (2026-08-25) — vigente

**Alembic es el único dueño del DDL hoy.** Schema se aplica con `alembic upgrade head` / `bolsa_infrastructure.database.migrations.ensure_migrated` (head actual `010` en `bolsa_v1`). SQLAlchemy (`tables.py`) mapea ese esquema en runtime.

**Prisma no es autoridad de schema.** `@bolsa/database` queda como **tooling**: `db:generate` (Prisma Client) y `db:seed` (catálogo IBEX). Los comandos públicos `pnpm db:push`, `pnpm db:migrate` y `db:migrate:deploy` **fail-closed**. No hay dual-schema Prisma+Alembic: un cambio de tablas se declara en Alembic + SQLAlchemy; Prisma no gobierna DDL.

Los §§1–5 siguientes son el **registro histórico M4 (2026-08-10)** (Prisma era el DDL entonces; Alembic placeholder). Quedan superseded por esta enmienda.

---

## 1. Contexto (histórico M4, 2026-08-10)

El monorepo persiste en PostgreSQL 16 + TimescaleDB. Dos capas ORM conviven:

- **Prisma** — `packages/database/prisma/schema.prisma` (53 models → 53 tablas PostgreSQL) + `prisma/migrations/*` (~55 migraciones). Paquete TS **exclusivamente de tooling** (migraciones SQL, seed IBEX, inspección).
- **SQLAlchemy 2.0** — `packages/py/infrastructure/.../database/models/tables.py` (53 tablas con `__tablename__`) + repos `SqlAlchemy*` + `database/session.py`. Es la capa ORM **runtime** de la API FastAPI.

Existe una aparente tensión entre decisiones históricas:

- **ADR-001** (Sprint 0) eligió **Prisma** como ORM con migraciones versionadas.
- **ADR-003** §9 (estrategia strangler hacia Python) planea **retirar Prisma** (`@bolsa/database`) y pasar a **SQLAlchemy + Alembic** (§1 decisión 1: "Migraciones: Alembic").

Auditado el estado real en 2026-08-10 (M4), se detectó una **desconexión doc↔estado**:

- `packages/database/README.md` declara: _«Este paquete **no es runtime**… se usa únicamente para Migraciones SQL (`prisma migrate`), Seed del catálogo IBEX, Inspección. La API FastAPI accede a PostgreSQL vía SQLAlchemy, no vía Prisma Client.»_
- `alembic/env.py` está **vacío (0 líneas)**; la única migración `alembic/versions/001_timescaledb_extension.py` dice textualmente _«tablas existentes vía Prisma (baseline sin recreate)»_.
- Verificado: **los 53 tables de SQLAlchemy y los 53 models de Prisma son el mismo conjunto de tablas** (sin tablas en uno que falten en el otro).

→ En **el estado de 2026-08-10**, quien creaba/esquematizaba la BD (dueño del DDL) era **Prisma migrate**. SQLAlchemy era la capa de lectura/escritura en runtime, **no** el dueño del esquema. Alembic era entonces un **placeholder no funcional como migrador**.

## 2. Decisión (histórico M4; superseded C2)

Se declara de forma explícita la **fuente de verdad del esquema y su evolución**, anclada al estado verificado **en 2026-08-10**:

1. **Prisma era el dueño del DDL (esquema/migraciones) entonces.** `packages/database/prisma/schema.prisma` era la fuente de verdad canónica del modelo; las tablas se creaban/alteraban con `prisma migrate` + `prisma db seed`.
2. **SQLAlchemy es la capa de mapeo runtime.** `bolsa_infrastructure` mapea 1:1 el mismo esquema (`tables.py`) y lo usa la API FastAPI.
3. **Alembic no era el migrador activo** en M4. `env.py` vacío + única migración de la extensión TimescaleDB ≠ gestión de tablas. Un **baseline Alembic real** es el camino que prevé ADR-003 §9 (cumplido después: F3b/F3a + árbol hasta `010`).
4. **Coherencia = contrato.** En M4 el cambio se declaraba en Prisma y se reflejaba en SQLAlchemy.

### 2.1 Resolución de la tensión ADR-001 vs ADR-003 (histórico)

En M4 no había contradicción activa: **ADR-003 fijaba el destino (Alembic), el presente estaba gobernado por ADR-001 + el estado real (Prisma)**. C2 cierra ese intermedio: el destino de ADR-003 §9 es la práctica actual.

## 3. Consecuencias (histórico M4)

### Positivas

- Fuente de verdad única y verificable en M4 (Prisma → DDL; SQLAlchemy → runtime).
- El futuro baseline Alembic quedaba **deliberado** (no sorpresa).

### Negativas / costes

- Dos definiciones que había que mantener alineadas (Prisma + SQLAlchemy).
- Alembic configurado pero no operativo podía inducir a error.
- El plan de simplificación (retirar `@bolsa/database` como DDL) quedó pendiente hasta C2.

## 4. Verificación (2026-08-10, M4 FASE 1)

- Conjunto de tablas idéntico: Prisma 53 models == SQLAlchemy 53 `__tablename__`.
- `alembic/env.py` vacío; única migración `001_timescaledb_extension.py` (extension TimescaleDB).
- `packages/database/README.md` y `package.json` (`db:migrate`/`db:migrate:deploy`) confirmaban Prisma migrate como mecanismo **entonces**.
- Batería base intacta (solo docs en este módulo): ruff solo `B007` conocido, pytest 663/2 pre-existentes, mypy deuda continue-on-error.

## 5. Pendiente (histórico M4; C2 cierra el DDL)

- ~~Trazar e implementar un **baseline Alembic** que iguale Prisma (hito ADR-003 §9)~~ — hecho en F3b/F3a (`003` takeover) + revisiones hasta `010`. **C2** retira Prisma como camino público de schema.
- Consolidar repos: adoptar explícitamente los ~16 Protocol de `bolsa_domain.repositories` (~22 repos no tienen interfaz de dominio hoy) — frente de infra, sin tocar application en el cuerpo.
- Reducir el acoplamiento `application → infrastructure` (mayoritariamente en `apps/api-python/src/bolsa_api/api/dependencies.py`).
