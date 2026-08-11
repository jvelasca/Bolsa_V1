# Traspaso — F3b Alembic como autoridad BD + columna `data_epoch` para `--mark-legacy` (2026-08-11)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §16 (sub-entrada de la Auditoría consolidada, junto a F1/F2).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (P0.5/P1.2 + D0–D5) · [traspaso-f2-backtest-next-open-2026-08-11.md](./traspaso-f2-backtest-next-open-2026-08-11.md) (§6 deuda: `--mark-legacy` no-op → F3b).
> **Rama de ejecución:** `stage/f3b-alembic-data-epoch-2026-08-11` (desgajada desde `stage/f1-*`), **PR #31 ABIERTO** → base `stage/f1-integridad-financiera-2026-08-11` (aún sin mergear).
> **Regla del hilo:** NO tocar código fuera del alcance F3b. Cambios validados con la batería (ruff+mypy+pytest) antes del commit.
> **Estado:** F3b **COMMITEADO (7 commits C1–C7, HEAD `b9e9b6c`)** y **PR #31 ABIERTO** (sin mergear). Batería **602✓ · 0 fallos**. Working tree limpio. Pendiente de **merge** del PR #31 (fast-forward) para consolidar en `stage/f1-*`. Ver §7/§8.

---

## 1. Objetivo de F3b

Hacer **Alembic la única autoridad de esquema PostgreSQL** (D2) para el DDL nuevo, aportar la vía **`ensure_migrated`** programática e idempotente al arranque (fuera del path de petición, P1.2), y **resolver la deuda de F2 §6**: la columna de época/legacy en `research_trials`/`backtest_runs` para que `--mark-legacy` del recalc deje de ser no-op. Cero features (D5). **Alcance acordado incremental** (decisión del usuario): NO portar todo el DDL Prisma existente a Alembic en esta fase (queda como deuda F3/F4).

## 2. Diagnóstico confirmado en código (fase previa + este hilo)

- **Alembic era un stub:** `env.py` vacío (solo un salto de línea) y una única migración `001_timescaledb_extension` que hacía `CREATE EXTENSION IF NOT EXISTS timescaledb`. La tabla `alembic_version` **no existía**: Alembic nunca se había ejecutado contra la BD.
- **`alembic_version` ausente + extensión TimescaleDB ausente:** el docker-compose usa `postgres:16-alpine` plano; el `CREATE EXTENSION` de la baseline `001` lanzaba `FeatureNotSupported` → imposible delivrar `upgrade head`.
- **`data_epoch` inexistente** en `backtest_runs` y `research_trials` (deuda F2 §6): `--mark-legacy` era no-op.
- **Esquema real** creado por Prisma (`packages/database/prisma/migrations/*`); el runtime consulta con SQLAlchemy (`Base`).

## 3. Decisiones pactadas (no renegociar)

- **D0** orden F1 → F2 → F3b → F5a → (F3a+F4+F5b); F3b es la fase ejecutada.
- **D2** Alembic = única autoridad PostgreSQL; Prisma degradado a lector/legacy.
- **D5** solo F1–F5, cero features.
- **F3b alcance incremental (usuario):** Alembic operativo + `ensure_migrated` + columna `data_epoch` + cable `--mark-legacy`; NO portar todo el DDL Prisma a Alembic (deuda).

## 4. Implementación

| #     | Fichero(s)                                                | Qué                                                                                                                                                                                                                                                                                             |
| ----- | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **A** | `packages/py/infrastructure/alembic/env.py`               | `env.py` real: resuelve el URL desde `DATABASE_URL`/ini (normaliza a `+psycopg`), soporta offline (`--sql`) y una conexión inyectada (`config.attributes["connection"]`); `target_metadata = Base.metadata` para autogenerate.                                                                  |
| **B** | `packages/py/infrastructure/alembic.ini`                  | `prepend_sys_path = .:src` + `path_separator = os` (sin silenciar el deprecation de separador de path).                                                                                                                                                                                         |
| **C** | `alembic/versions/001_timescaledb_extension.py`           | Baseline tolerante: consulta `pg_available_extensions` y solo crea `timescaledb` si está disponible; no rompe `upgrade head` en Postgres plano.                                                                                                                                                 |
| **D** | `alembic/versions/002_research_data_epoch.py` (nuevo)     | Primera migración de DDL real vía Alembic: `ALTER TABLE backtest_runs ADD COLUMN data_epoch TEXT` + `research_trials` (nullable). `down_revision = "001_timescaledb_extension"`.                                                                                                                |
| **E** | `src/bolsa_infrastructure/database/migrations.py` (nuevo) | `ensure_migrated()`: aplica `alembic upgrade head` de forma programática (config con `script_location` absoluto, conexión inyectada), idempotente por `alembic_version`. Lanza si falla.                                                                                                        |
| **F** | `apps/api-python/src/bolsa_api/main.py`                   | Lifespan: `await asyncio.to_thread(ensure_migrated)` al arranque (una vez, fuera del path de petición).                                                                                                                                                                                         |
| **G** | `src/bolsa_infrastructure/database/models/tables.py`      | `data_epoch: Mapped[str                                                                                                                                                                                                                                                                         | None]`en`BacktestRunRow`y`ResearchTrialRow` (SQLAlchemy). |
| **H** | `scripts/research/recalc_trials_next_open.py`             | `--mark-legacy` deja de ser no-op: `_mark_legacy()` etiqueta runs old-theme (`manifest.engine.version != actual`) como `data_epoch='legacy'` y los new-theme como `'next_open'`, propagando a los trials; idempotente; requiere `ensure_migrated()` antes (columna). `DATA_EPOCH_*` constantes. |
| **I** | `tests/test_f3b_alembic_data_epoch.py` (nuevo)            | 3 tests: (1) cadena Alembic llega a head `002`, (2) `ensure_migrated` idempotente + columna `data_epoch` en ambas tablas + versión `alembic_version`, (3) `_mark_legacy` marca old→`legacy` y new→`next_open` propagando a trials.                                                              |

## 5. Batería (aplicada)

- **ruff check** sobre los ficheros tocados: **0 errores** (los del paquete tests/infra pre-existentes quedan fuera del scope).
- **mypy** sobre los ficheros nuevos/editados: **0 errores** (`migrations.py`, `env.py`, `001`/`002`, `test_f3b...`). `tables.py` y `main.py` conservan **solo errores pre-existentes** (verificado: las líneas añadidas no generan errores nuevos).
- **pytest:**
  - infrastructure **46✓** (incluye 3 nuevos F3b) · application **222✓** · analytics **323✓** · api-python offline **11✓** → **602✓ · 0 fallos**.
- **Migración aplicada en local:** `ensure_migrated()` → `alembic_version = ['002_research_data_epoch']`, columnas `data_epoch` presentes (verificado por query e idempotencia). Idempotente (2ª llamada ok).

## 6. Deuda / fuera de alcance (registrado, NO resuelto)

- **Portar TODO el DDL Prisma a Alembic** (P0.5 completo): fuera del alcance incremental; se consolida en F3a/F4. El runtime sigue sin `create_all`; Prisma sigue siendo el autor del esquema base ya existente (Alembic aporta DDL nuevo).
- **account_repository.ensure_migrated** (seeding/backfill destructivo por request, P1.2): NO retirado en F3b (escope conservador; es data-seed distinto del DDL). El esquema-Alembic ya se aplica al arranque; la consolidación por-request queda para F3a/workers.
- **Workers schedulers en lifespan** (P0.4): F3a, fuera de alcance.
- **MOC / execution_model** (F3+/F5+), **auth** (F5b), **ciclo analytics↔market** (F4), **contratos FE/BE** (F5a): no tocados.
- **recalc idempotencia vs datos:** el dry-run del recalc mostró `would_recalc` en lugar de `already_new` (18 targets) — refleja el estado live de `data_version` (datos OHLCV re-ingestionados tras F2), NO una regresión de F3b (no se tocó `_new_theme_run_exists`).

## 7. Registro

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                       |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Traspaso F3b creado sobre `stage/f1-*` (HEAD `9859d62`). Alcance incremental (Alembic op + `ensure_migrated` + columna + `--mark-legacy`).                                                                                                                                                                                   |
| 2026-08-11 | A–B: `env.py` real + ini (`prepend_sys_path`/`path_separator`).                                                                                                                                                                                                                                                              |
| 2026-08-11 | C–D: baseline `001` tolerante a TimescaleDB ausente; migración `002` (DDL `data_epoch`).                                                                                                                                                                                                                                     |
| 2026-08-11 | E–F: `migrations.ensure_migrated()` + llamada en lifespan. `ensure_migrated` aplicado en local: `alembic_version=002`, columnas presentes, idempotente.                                                                                                                                                                      |
| 2026-08-11 | G–H: columna en `tables.py` + cable `--mark-legacy` (deja de ser no-op).                                                                                                                                                                                                                                                     |
| 2026-08-11 | I: tests F3b (3). Batería: ruff✓ · mypy✓ · pytest infra 46✓ + app 222✓ + analytics 323✓ + api offline 11✓ = **602✓ · 0 fallos**.                                                                                                                                                                                             |
| 2026-08-11 | **COMMITS + PR**: 7 commits atómicos C1–C7 en `stage/f3b-alembic-data-epoch-2026-08-11` (C7 `b9e9b6c`). **PR #31 ABIERTO** → base `stage/f1-*`. Working tree limpio. `origin/stage/f1-*` sigue en `9859d62` (F2); base local `stage/f1-*` quedó adelantada a `b9e9b6c` (se reconcilia por fast-forward tras mergear PR #31). |

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto (traspasos F1 §8 / F2 §8). Al cerrar: preparar el siguiente con su `traspaso-*`, entrada única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 9. Texto exacto de traspaso — siguiente hilo (F5a / continuación)

```text
Texto de traspaso → nuevo chat (F3b completado — siguiente fase tras F3b)

CONTEXTO INMEDIATO: F3b (Alembic como autoridad BD + columna data_epoch para --mark-legacy)
está COMPLETADO con 7 commits en rama stage/f3b-alembic-data-epoch-2026-08-11 y PR #31 ABIERTO:
  - 7 commits atómicos C1..C7 (doc cierre C7 `b9e9b6c`) en stage/f3b-alembic-data-epoch-2026-08-11.
  - PR #31 (https://github.com/jvelasca/Bolsa_V1/pull/31) → base stage/f1-integridad-financiera-2026-08-11, AÚN SIN MERGEAR.
  - Alembic operativo: env.py real, baseline 001 tolerante a TimescaleDB ausente, migración 002
    (data_epoch en backtest_runs/research_trials). alembic_version=002 aplicado en local.
  - bolsa_infrastructure.database.migrations.ensure_migrated(): upgrade head programático e idempotente,
    invocado 1 vez al arranque (lifespan), fuera del path de petición (P1.2).
  - --mark-legacy (recalc_trials_next_open.py) deja de ser no-op: etiqueta data_epoch legacy/next_open.
  - Batería: ruff✓ · mypy✓ · pytest infra 46✓ + app 222✓ + analytics 323✓ + api offline 11✓ = 602✓.

ESTADO GIT (VERIFICADO, OJO): origin/main = eb31a7d · origin/stage/f1-* = 9859d62 (F2) · origin NO ha
avanzado con F3b. PR #31 PENDIENTE DE MERGE. IMPORTANTE: la rama LOCAL stage/f1-* quedó ADELANTADA a
`b9e9b6c` (no 9859d62) porque F3b se commiteó y desgajó a una rama propia; NO es un reset destructivo y
NO afecta al PR. Tras mergear PR #31 (fast-forward) origin/stage/f1-* alcanza esos mismos commits y la
rama local se reconcilia sin conflictos. NO hacer reset --hard salvo aprobación explícita. Checkpoint
de retroceso global: tag audit-checkpoint-2026-08-11 (2683c49).

Lee PRIMERO: docs/engineering/traspaso-f3b-alembic-data-epoch-2026-08-11.md (§4 implementación A–I,
§5 batería 602✓, §6 deuda) y su fuente: audit-consolidado-internas-externas-2026-08-11.md (D0–D5).
Para la fase siguiente usa engineering-index-2026-08-03.md y el plan de la fase declarada.
NO toques código fuera del alcance de la fase que se declare.

SIGUIENTE FASE (orden pactado D0, NO renegociar): F3b → F5a → (F3a+F4+F5b). Tras F3b, la siguiente es
F5a = CONTRATOS FE/BE (hallazgo P1.5, drift openapi-typescript):
  - Problema (P1.5): DTOs/TypeScript a mano en packages/shared (manual) + api.ts vs Pydantic (FastAPI);
    sin cliente generado desde OpenAPI → drift silencioso FE/BE.
  - Objetivo: generar tipos/contrato TS del OpenAPI de FastAPI con openapi-typescript; eliminar la
    duplicación manual y el drift. Cero features (D5). P1.5 confirmado en código.
  - ARRANQUE RECOMENDADO: (1) mergear PR #31 y ponerte en la punta stage/f1-*; (2) leer el hallazgo P1.5
    completo y revisar cómo FastAPI expone el schema OpenAPI (apps/api-python) y cómo el FE consume
    endpoints (apps/web: api.ts / packages/shared); (3) pactar alcance incremental con el usuario
    antes de implementar (mismo patrón que F3b). Preparar traspaso F5a + entrada única en
    engineering-index + texto exacto al cerrar (norma permanente).

Decisiones pactadas (NO renegociar): D0 orden F1→F2→F3b→F5a→(F3a+F4+F5b); D1 next_open inmutable 1D
(MOC fuera); D2 Alembic única autoridad BD; D3 extraer workers de FastAPI (F3a); D4 auth local diferida
(F5b); D5 Solo F1–F5, CERO FEATURES. Deuda registrada en F3b §6: portar TODO el DDL Prisma a Alembic
(→F3a/F4), account_repository.ensure_migrated por-request no retirado (→F3a), workers en lifespan (F3a),
MOC/auth/ciclo analytics↔market (→F4), contratos FE/BE = PRECISAMENTE F5a.

NOTA OPERATIVA: al tocar scripts que imprimen caracteres Unicode ('→') en Windows, ejecutar con
$env:PYTHONIOENCODING="utf-8"; (consola cp1252 lanza UnicodeEncodeError).

BATERÍA OBLIGATORIA: ruff check + mypy (ficheros tocados) + pytest (analytics/application/api-python,
+ infraestructura si se tocan DB/repos) + pnpm test / CI si toca web. Al cerrar cualquiera: preparar el
siguiente traspaso-* + entrada única en engineering-index + texto exacto en el chat (norma permanente).

FLUJO DE COMMITS (patrón proyecto): trabajo en rama stage/fX-*-fecha; commits atómicos por cambio; push +
PR hacia la base activa (stage/f1-* actualmente); merge fast-forward tras aprobación del usuario.
```
