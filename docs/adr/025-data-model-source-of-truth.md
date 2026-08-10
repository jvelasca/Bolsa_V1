# ADR-025 — Fuente de verdad única del modelo de datos (Prisma dueño del DDL · SQLAlchemy mapeo runtime)

- **Estado:** Accepted — 2026-08-10 (registro del estado verificado, módulo M4 del plan 08-10)
- **Tipo:** decisión de arquitectura / modelo de datos
- **Padres:** [ADR-001](./001-database-choice.md) (PostgreSQL + Prisma) · [ADR-003](./003-python-backend-ai-platform.md) §9 (strangler TS→Python) · [DATA_MODEL.md](../DATA_MODEL.md)
- **Contexto de auditoría:** [traspaso-m4-infraestructura-datos-2026-08-10.md](../engineering/traspaso-m4-infraestructura-datos-2026-08-10.md) · [general-audit-plan-2026-08-10.md](../engineering/general-audit-plan-2026-08-10.md) §5 fila **M4**

---

## 1. Contexto

El monorepo persiste en PostgreSQL 16 + TimescaleDB. Dos capas ORM conviven:

- **Prisma** — `packages/database/prisma/schema.prisma` (53 models → 53 tablas PostgreSQL) + `prisma/migrations/*` (~55 migraciones). Paquete TS **exclusivamente de tooling** (migraciones SQL, seed IBEX, inspección).
- **SQLAlchemy 2.0** — `packages/py/infrastructure/.../database/models/tables.py` (53 tablas con `__tablename__`) + repos `SqlAlchemy*` + `database/session.py`. Es la capa ORM **runtime** de la API FastAPI.

Existe una aparente tensión entre decisiones históricas:
- **ADR-001** (Sprint 0) eligió **Prisma** como ORM con migraciones versionadas.
- **ADR-003** §9 (estrategia strangler hacia Python) planea **retirar Prisma** (`@bolsa/database`) y pasar a **SQLAlchemy + Alembic** (§1 decisión 1: "Migraciones: Alembic").

Auditado el estado real en 2026-08-10 (M4), se detectó una **desconexión doc↔estado**:

- `packages/database/README.md` declara: *«Este paquete **no es runtime**… se usa únicamente para Migraciones SQL (`prisma migrate`), Seed del catálogo IBEX, Inspección. La API FastAPI accede a PostgreSQL vía SQLAlchemy, no vía Prisma Client.»*
- `alembic/env.py` está **vacío (0 líneas)**; la única migración `alembic/versions/001_timescaledb_extension.py` dice textualmente *«tablas existentes vía Prisma (baseline sin recreate)»*.
- Verificado: **los 53 tables de SQLAlchemy y los 53 models de Prisma son el mismo conjunto de tablas** (sin tablas en uno que falten en el otro).

→ En **el estado actual**, quien crea/esquematiza la BD (dueño del DDL) es **Prisma migrate**. SQLAlchemy es la capa de lectura/escritura en runtime, **no** el dueño del esquema. Alembic es hoy un **placeholder no funcional como migrador**.

## 2. Decisión

Se declara de forma explícita la **fuente de verdad del esquema y su evolución**, anclada al estado verificado:

1. **Prisma es el dueño del DDL (esquema/migraciones) hoy.** `packages/database/prisma/schema.prisma` es la fuente de verdad canónica del modelo; las tablas se crean/alteran con `prisma migrate` + `prisma db seed`.
2. **SQLAlchemy es la capa de mapeo runtime.** `bolsa_infrastructure` mapea 1:1 el mismo esquema (`tables.py`) y lo usa la API FastAPI; **debe permanecer coherente con el schema Prisma** (mismo conjunto de tablas y columnas compatibles). No genera el DDL por sí sola; sus modelos no deben divergir de Prisma sin migración previa.
3. **Alembic no es el migrador activo.** `env.py` vacío + única migración de la extensión TimescaleDB ≠ gestión de tablas. Un **baseline Alembic real** (autogenerar desde SQLAlchemy para igualar Prisma) es el camino que prevé ADR-003 §9, pero **se difiere explícitamente** (riesgo Alto: DDL paralelo que debe coincidir exactamente; hoy generaría drift con el dueño real). No se ejecuta ahora.
4. **Coherencia = contrato.** Todo cambio de esquema se declara en Prisma (migración) y se refleja en SQLAlchemy (`tables.py` + repos); sin batería completa (ruff + mypy + pytest) no se cambia modelo.

### 2.1 Resolución de la tensión ADR-001 vs ADR-003

No hay contradicción activa: **ADR-003 fija el destino (Alembic), el presente está gobernado por ADR-001 + el estado real (Prisma)**. La migración a Alembic es un **hito futuro diferido**, no la práctica actual. Este ADR congela el estado intermedio legítimo del strangler.

## 3. Consecuencias

### Positivas

- Fuente de verdad única y verificable (Prisma → DDL; SQLAlchemy → runtime), sin ambigüedad de "quién es el dueño del esquema".
- El futuro baseline Alembic queda **deliberado** (no sorpresa) y con riesgo documentado.
- Base para consolidar repos (frente M4 futuro, sin tocar semántica de use-cases).

### Negativas / costes

- Dos definiciones que hay que mantener alineadas (Prisma + SQLAlchemy); cualquier drift futuro requiere revisión a mano.
- Alembic configurado pero no operativo puede inducir a error si alguien intenta migrar con él.
- El plan de simplificación final (retirar `@bolsa/database`) sigue pendiente de un baseline Alembic fiable, aún sin trazar en detalle.

## 4. Verificación (2026-08-10, M4 FASE 1)

- Conjunto de tablas idéntico: Prisma 53 models == SQLAlchemy 53 `__tablename__`.
- `alembic/env.py` vacío; única migración `001_timescaledb_extension.py` (extension TimescaleDB).
- `packages/database/README.md` y `package.json` (`db:migrate`/`db:migrate:deploy`) confirman que Prisma migrate es el mecanismo.
- Batería base intacta (solo docs en este módulo): ruff solo `B007` conocido, pytest 663/2 pre-existentes, mypy deuda continue-on-error.

## 5. Pendiente (fuera de alcance atómico M4, frentes futuros)

- Trazar e implementar un **baseline Alembic** que iguale Prisma (hito ADR-003 §9) — riesgo Alto, requiere plan atómico + batería y **no** tocar la semántica de use-cases.
- Consolidar repos: adoptar explícitamente los ~16 Protocol de `bolsa_domain.repositories` (~22 repos no tienen interfaz de dominio hoy) — frente de infra, sin tocar application en el cuerpo.
- Reducir el acoplamiento `application → infrastructure` (mayoritariamente en `apps/api-python/src/bolsa_api/api/dependencies.py`).
