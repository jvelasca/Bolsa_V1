# Auditoría General + Plan de Refactorización por Módulos — 2026-08-10

> Documento de arranque de una **pausa de auditoría general** (estructura + documentación)
> tras un crecimiento grande del monorepo. Da origen a un **plan de refactorización
> ejecutado por módulos en hilos separados**, validando todo con la batería de tests y
> sin romper nada.
>
> Enlaza con: [audit-resume-premises-2026-08-09.md](./audit-resume-premises-2026-08-09.md)
> y [dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md).

---

## 1. Objetivo

Revisar la **estructura general** y la **documentación** del monorepo para detectar lo
**obsoleto, desconectado o con errores**, y trazar un **plan de refactorización por
módulos**. Cada módulo se trabaja en un **hilo/chat propio** (para no sobrecargar) y se
valida **completamente con los tests** antes de darlo por bueno.

Premisas firmes del hilo:

- **No romper nada.** Cada cambio se decide, se propone y se valida con la batería
  completa antes de commitear.
- **Sin tocar código a la ligera.** Los módulos que tocan código van acompañados de su
  batería de verificación y, con aprobación, commit + push.
- **GitHub siempre sincronizado** y recuperable.

## 2. Estado del repositorio (referencia de partida)

- Rama de trabajo: `stage/estudio-membership-operativa-2026-08-04`.
- Árbol limpio y sincronizado con `origin/<rama>` (0/0).
- Último commit confirmado: `5d39e7a` (fix 500 FK en `instrument-daily-opinions/query`).
- Batería web en verde: **707 tests (140 archivos)** · pytest: **654 passed**.

## 3. Inventario de la estructura (confirmado)

```
Bolsa_V1                                pnpm + Turborepo + uv/Python + Prisma
├── apps/
│   ├── api-python/                     FastAPI (Python) · "capa HTTP fina"
│   └── web/                            React 19 + Vite 6 + Vitest (TS)
├── packages/
│   ├── database/                       Prisma 6 (PostgreSQL)
│   ├── shared/                         utilidades/contratos compartidos TS (~85 src)
│   └── py/                             uv workspace (7 paquetes)
│       └── ai, application, analytics, domain, infrastructure, market
├── scripts/                            run-dev.mjs, lib/*, research/*
├── tests/  research/  docs/(adr, engineering, rfc, architecture, backups)
└── .github/workflows/                  frontend-ci, python-ci, fase2-scientific,
                                        optimize-lab, gitleaks
    + .husky + lint-staged · turbo.json · pnpm-workspace.yaml · Makefile
```

Puntos fuertes: monorepo bien organizado, **un solo gestor por ecosistema**
(pnpm para JS/TS, uv para Python), un único `pnpm-lock.yaml`, sin duplicación de
dependencias.

## 4. Hallazgos (clasificados por criticidad)

### 🔴 Criticidad alta — enlaces de documentación rotos (doc que no existe)

Documentos referenciados pero **inexistentes** en el repo (muertos, no renombrados):

| Ruta rota                                   | Citado en                                                               |
| ------------------------------------------- | ----------------------------------------------------------------------- |
| `docs/CUTOVER_PYTHON.md`                    | `README.md` l.42 · `docs/ARCHITECTURE.md` l.64                          |
| `docs/BACKTESTING_AUDIT.md` (×4)            | `docs/BACKTESTING_DATA_ARCHITECTURE.md` l.5,650 · `docs/adr/009` l.9,95 |
| `docs/SCREENERS_SIGNALS_ALIGNMENT.md`       | `docs/adr/010` l.197                                                    |
| `docs/PROJECT_STATE.md`                     | `docs/adr/008` l.6                                                      |
| `docs/AI_TRACKER_STRATEGY.md`               | `docs/HYBRID_TRACKERS.md` l.4                                           |
| `docs/DISK_AND_CLEANUP.md`                  | `docs/docker.md` l.183                                                  |
| `docs/sessions/*` (×2; carpeta inexistente) | `docs/API_REFERENCE.md` l.299 · `docs/PERFORMANCE.md` l.108             |

### 🟡 Criticidad media — documentación desconectada de los índices centrales

- Los docs vivientes de continuidad (`dev-continuation-plan-2026-08-09.md` y
  `audit-resume-premises-2026-08-09.md`) **no están** en `docs/README.md` ni en
  `engineering-index` (solo se enlazan entre sí y desde el roadmap).
- `engineering-index-2026-08-03.md` quedó en 08-03 y solo añadió 08-06; **no cubre**
  los docs de 08-09.
- 3 ficheros de `research/observations/` (07-29, 08-02-smoke, 08-03) **no indexados**
  en `research/observations/index.md`.
- `docs/README.md` dice "RFC-000…007"; ya existe y está aprobado **RFC-008**.
- Enlace relativo `./` roto (vs `../`) en `docs/engineering/pending-delete/NEXT-IA-BUTTON.md`.

### 🟢 Criticidad baja — coherencia de versiones de dependencias

- **JS/TS**: coherente (1 `pnpm-lock.yaml`, rangos `^` matchean, sin duplicados).
  Menor: `@types/react` (19.2.17) vs `@types/react-dom` (19.2.3) desalineados.
- **Python**: coherente (todo `hatchling`, `requires-python >=3.12`, un gestor).
  Señales razonables de desactualización: `vectorbt>=0.26` (mantenimiento parado),
  `arq>=0.26`, `fastapi>=0.115`, `ruff>=0.9`.
- ⚠️ **Falta `uv.lock` commiteado** pese a usar `[tool.uv.workspace]` → riesgo de
  instalaciones no reproducibles en el backend (a diferencia del `pnpm-lock.yaml`).

### Otros señales

- `packages/py/README.md` marca `py/ai` como **"Placeholder fase 6+"**, pero el paquete
  **ya está implementado** (AI Governance · RFC-007). Documentación desactualizada.
- `github-v1-release.md` es una checklist de release **ya completada** (v1.0.0) →
  candidato a histórico.
- `.secrets/` y `logs/` (generados) — verificar tracking y cobertura de gitleaks.

## 5. Plan de refactorización por módulos (hilos separados)

Estructura de hilos. Cada módulo = 1 hilo/chat nuevo, con su documento de trabajo vivo y
su batería completa de verificación.

**Batería base por módulo:**

- Web (si toca frontend): `pnpm --filter @bolsa/web typecheck` + `lint` (0 errores) +
  `test` + `build`.
- Py (si toca backend): `ruff` + `mypy` + `pytest`.
- Global: `pnpm test` (turbo) y confirmación de CI en GitHub.

| Módulo                                                            | Alcance                                                                                      | Riesgo           | Prioridad       |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------------- | --------------- |
| **M0 — Higiene de documentación**                                 | Enlaces rotos, índices (docs 08-09, research, RFC-008), `py/README` ai, histórico v1-release | Nulo (solo docs) | ★★★ Alto/barato |
| **M1 — Reproducibilidad backend**                                 | Commitear `uv.lock`; evaluar subir `fastapi`/`ruff`/`arq` con tests                          | Bajo             | ★★★             |
| **M2 — Versiones frontend**                                       | Reconciliar `@types/react`/`react-dom`; revisar rangos `^` amplios                           | Bajo             | ★★              |
| **M3 — Capa de dominio** (`py/domain` + `application`)            | Coherencia de negocio, docstrings, código muerto                                             | Medio            | ★★★             |
| **M4 — Infraestructura / modelo de datos** (Prisma vs SQLAlchemy) | Fuente de verdad única del modelo, Alembic, repos                                            | **Alto**         | ★★★             |
| **M5 — Frontend web (por features)**                              | Feature-slicing: hub, listas, accounts, alertas, charts                                      | Medio            | ★★              |
| **M6 — AI / analytics**                                           | `py/ai` (doc vs código), motores backtest/indicadores                                        | Medio            | ★★              |
| **M7 — Dev-stack residual F3.7**                                  | Crash "puro" de Vite (code-splitting / subir Vite)                                           | Medio            | ★★              |

### Orden sugerido de ejecución

1. **M0** (docs) — barato, riesgo nulo, deja la documentación fiable como base.
2. **M1 + M2** (reproducibilidad/versiones) — atacan la premisa de "revisar versiones
   tras el crecimiento".
3. **M3 / M4 / M6** (backend por capas) — el corazón de la lógica de negocio.
4. **M5** (frontend por features) — lo más grande, dividido para no sobrecargar.
5. **M7** (dev-stack) — ya tiene su plan documentado en el plan de continuación 08-09.

## 6. Próximo hilo: M0 — Higiene de documentación

**Alcance concreto (con aprobación paso a paso):**

1. Enlaces rotos críticos: decidir por cada uno _crear_ el doc o _quitar/redirigir_ la
   referencia. Candidatos a quitar (referencias históricas muertas): `docs/sessions/*`,
   `PROJECT_STATE`, `AI_TRACKER_STRATEGY`, `DISK_AND_CLEANUP`,
   `SCREENERS_SIGNALS_ALIGNMENT`. Candidatos a _crear/renombrar_: `CUTOVER_PYTHON.md`
   (el contenido real del cutover puede migrarse o apuntarse a un doc equivalente),
   `BACKTESTING_AUDIT.md` (comprobar si `BACKTESTING_DATA_ARCHITECTURE.md` cumple el rol).
2. Conectar los docs 08-09 a `docs/README.md` y `engineering-index`.
3. Indexar los 3 ficheros de research en `research/observations/index.md`.
4. Corregir "RFC-007"→"RFC-008" y el enlace `./` roto en `NEXT-IA-BUTTON.md`.
5. Actualizar `packages/py/README.md` (marcar `ai` como implementado).
6. Verificación final de enlaces y registro en el plan de continuación.

---

## 7. Registro M0 — enlaces rotos resueltos (decisión A: redirigir + dejar indicado para eliminación)

**Decisión (usuario, 2026-08-10):** cada doc roto se **redirige a un documento existente**
que cumple su rol, y se deja una **nota inline** señalándolo como _histórico: pendiente de
borrar definitivamente cuando se confirme libre de uso_. Esta lista es el registro oficial
para proceder a su **eliminación definitiva** cuando se verifique que no queda ningún uso.

| Doc original (roto)                          | Redirigido a                             | Enlaces corregidos en                                                   |
| -------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------- |
| `docs/CUTOVER_PYTHON.md`                     | `docs/DEV_STARTUP.md` + `docs/README.md` | `README.md` l.42 · `docs/ARCHITECTURE.md` l.64                          |
| `docs/BACKTESTING_AUDIT.md`                  | `docs/BACKTESTING_DATA_ARCHITECTURE.md`  | `docs/BACKTESTING_DATA_ARCHITECTURE.md` l.5,650 · `docs/adr/009` l.9,95 |
| `docs/SCREENERS_SIGNALS_ALIGNMENT.md`        | `docs/adr/011`                           | `docs/adr/010` l.197                                                    |
| `docs/PROJECT_STATE.md`                      | `docs/PORTFOLIO_AND_CASH.md`             | `docs/adr/008` l.6                                                      |
| `docs/AI_TRACKER_STRATEGY.md`                | — (marca histórica)                      | `docs/HYBRID_TRACKERS.md` l.4                                           |
| `docs/DISK_AND_CLEANUP.md`                   | `docs/DATA_MODEL.md`                     | `docs/docker.md` l.183                                                  |
| `docs/sessions/2026-07-11-rd2-arq-worker.md` | — (marca histórica)                      | `docs/API_REFERENCE.md` l.299                                           |
| `docs/sessions/2026-07-12-audit-close.md`    | — (marca histórica)                      | `docs/PERFORMANCE.md` l.108                                             |

> **Pendiente de confirmación:** eliminar definitivamente cada doc de la columna izquierda
> una vez verificado que no hay ninguna otra referencia ni uso en el repo (código, CI o docs).

---

_Documento de auditoría general y plan de refactorización por módulos. 2026-08-10._
