# ADR 003: Backend Python + plataforma de análisis e IA

## Estado

Aceptado — migración en curso (2026)

## Contexto

Bolsa V1 empezó como monorepo TypeScript (Fastify + Prisma + React). El objetivo evoluciona hacia **análisis bursátil profundo, backtesting avanzado e IA**, donde Python aporta ecosistema numérico, ML y tipado estricto con Pydantic/mypy.

Tres auditorías externas convergen en:

- Separación headless: React solo UI; Python solo cerebro.
- Clean Architecture / hexagonal: dominio independiente de FastAPI y de librerías.
- OpenAPI como contrato único con el frontend.
- Calidad de datos antes de indicadores, backtests e IA.
- Fases: clásico → backtest → optimización → ML → LLM → DL.

El frontend React + Vite + TanStack Query + Lightweight Charts **se mantiene**.

## Decisiones

### 1. Stack backend

| Componente | Elección |
|------------|----------|
| Lenguaje | Python 3.12+ |
| API | FastAPI + Uvicorn |
| Validación / DTOs | Pydantic v2 (`strict=True` en ingesta) |
| Tipado estático | mypy `--strict` + Ruff |
| ORM | SQLAlchemy 2.0 |
| Migraciones | Alembic |
| Tests | pytest + httpx |
| Gestión deps | uv (preferido) o Poetry |

### 2. Stack frontend (sin cambio sustancial)

React 19, Vite, TypeScript `strict`, TanStack Query, Zustand, Lightweight Charts.

Contrato con backend:

```
FastAPI → openapi.json → openapi-typescript + openapi-fetch → apps/web
```

No duplicar modelos a mano. CI debe fallar si OpenAPI y cliente TS divergen.

### 3. Organización del monorepo

El **dominio no vive dentro de FastAPI**. Estructura objetivo:

```
apps/
  web/              # React (actual)
  api-python/       # FastAPI — capa HTTP fina
  api/              # Fastify TS — retirar tras cutover

packages/py/
  domain/           # entidades, value objects, reglas puras
  market/           # ingesta, validación OHLCV, sanity checks
  infrastructure/   # SQLAlchemy, Redis, Yahoo, XTB bridge
  analytics/        # análisis determinista (patrones, S/R) — futuro
  ai/               # LLM, ML, RAG — futuro

packages/           # TS legacy hasta cutover (@bolsa/shared para web)
```

La API es una **puerta de entrada**. El mismo dominio debe usarse desde workers, CLI, notebooks y jobs de entrenamiento.

### 4. Separación analytics vs ai

- **`packages/py/analytics/`**: determinista (indicadores, patrones chartistas, estructura de mercado).
- **`packages/py/ai/`**: probabilística (LLM, embeddings, forecast, ML).

No mezclar ambos en un solo módulo.

### 5. Base de datos

- **PostgreSQL 16 + TimescaleDB** desde fase 1 (imagen Docker Timescale; `CREATE EXTENSION IF NOT EXISTS timescaledb`).
- Hypertable en `ohlcv_bars` cuando se migre schema desde Prisma (Alembic baseline).
- Datos relacionales (portfolio, backtests, usuarios futuros) en las mismas tablas PostgreSQL.
- **No** InfluxDB/QuestDB separadas en fase inicial.

### 6. Redis

- Introducir **Redis en fase 2** (caché de indicadores y resultados de backtest).
- Colas asíncronas: **Arq** o **Dramatiq** (no Celery) en fase 4+ para optimización e IA.
- MinIO (modelos, datasets) en fase 5+.

### 7. Indicadores y backtesting

| Fase | Indicadores | Backtesting |
|------|-------------|-------------|
| 1–2 | Portar SMA/EMA/RSI propios + **pandas-ta** puente | Motor propio simple (paridad con TS actual) |
| 3–4 | **`packages/py/domain/indicators`** propio (~30 indicadores) | **VectorBT** para optimización masiva |
| 5+ | GPU/vectorización si hace falta | Motor propio para reglas complejas (comisiones, slippage) |

No casarse con VectorBT; no reescribir motor desde cero antes de validar con VectorBT.

### 8. Capa de validación de datos (prioridad temprana)

Antes de pandas-ta o backtests:

1. **Pydantic v2** en ingesta (`OhlcvBarIngest`, splits, rangos OHLC).
2. **Data sanity checks** en `packages/py/market/` (nulos, `high >= low`, volumen, gaps, duplicados).
3. Solo datos validados entran al pipeline analítico.

Un split mal ajustado o un cierre nulo invalida backtests e IA.

### 9. Migración desde TypeScript (estrategia strangler)

1. Scaffold Python + paridad endpoint a endpoint.
2. Tests golden JSON (respuesta TS == respuesta Python).
3. Cutover frontend (`VITE_API_URL` → puerto Python).
4. Retirar `apps/api`, `@bolsa/core`, `@bolsa/market-data`, `@bolsa/database` (Prisma).

Preservar paths y shapes JSON actuales (`{ data: ... }`, camelCase vía Pydantic `alias` o serialización).

### 10. IA — orden obligatorio

```
Análisis clásico → Backtest fiable → Optimización (Optuna/VectorBT)
→ ML tabular (LightGBM/XGBoost) → LLM/RAG → DL experimental (PyTorch)
```

No saltar etapas.

## Consecuencias

### Positivas

- Dominio reutilizable fuera de HTTP (workers, notebooks, CLI).
- OpenAPI evita desincronización front/back.
- TimescaleDB escala histórico sin cambiar de motor SQL.
- Validación temprana reduce basura en backtests e IA.

### Negativas / costes

- Monorepo mixto TS + Python (dos toolchains, CI duplicado temporalmente).
- Periodo de convivencia TS/Python durante strangler migration.
- mypy estricto con pandas requiere stubs y `# type: ignore` acotados en bordes.

### Pendiente de ADR futuro

- ADR 004: Timescale hypertables + continuous aggregates.
- ADR 005: Estrategia IA (RAG vs fine-tuning, modelos permitidos).
- ADR 006: Autenticación multi-usuario.

## Fases de implementación

| Fase | Entregable |
|------|------------|
| 0 | ADR-003 + scaffold FastAPI + validación ingesta + health |
| 1 | Paridad 14 endpoints REST + Alembic baseline |
| 2 | Cutover frontend + OpenAPI client + Redis caché indicadores |
| 3 | Dominio analítico (pandas-ta → indicadores propios) |
| 4 | VectorBT + Arq workers + equity UI |
| 5 | Timescale continuous aggregates + MinIO modelos |
| 6 | analytics/ + ai/ (LLM, ML tabular) |

## Referencias

- Auditorías internas 2026 (3 informes consolidados).
- ADR 001 (PostgreSQL), ADR 002 (Yahoo/XTB).
- Contrato actual: `packages/shared/src/types.ts`, `apps/web/src/lib/api.ts`.
