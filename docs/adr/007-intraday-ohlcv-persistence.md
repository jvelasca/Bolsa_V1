# ADR 007: Persistencia OHLCV intradía

## Estado

Aceptado — jul 2026

## Contexto

La fase P4b expuso timeframes intradía vía **Yahoo en vivo** sin guardar en PostgreSQL. Eso sirve para visualizar el gráfico, pero **no cumple el horizonte del proyecto**:

- Backtesting multi-timeframe (replay sobre barras históricas)
- Estudios automáticos e indicadores custom en servidor
- IA / feature engineering sobre series temporales
- Triggers de objetos gráficos evaluados en histórico (ADR-006)

ADR-002 ya establece el flujo objetivo:

```
Yahoo ──sync/cache──► PostgreSQL ◄──read── Gráficos / Backtests / Analytics / IA
```

El atajo «solo Yahoo, sin BD» era **v1 de visualización**, no el diseño final.

## Decisión

### 1. Un solo almacén: `ohlcv_bars`

Todas las temporalidades viven en la misma tabla, clave `(instrument_id, timeframe, timestamp)`:

| Campo | Diario (1D) | Intradía / semanal / mensual |
|-------|-------------|------------------------------|
| `timeframe` | `1d` | `1m` … `4h`, `1wk`, `1mo` |
| `timestamp` | `timestamptz` (medianoche UTC del día) | `timestamptz` (apertura de vela UTC) |

**Migración:** `timestamp` pasa de `DATE` a `TIMESTAMPTZ`; enum `Timeframe` se amplía.

### 2. Estrategia de ingesta

| Timeframe | Ingesta principal | Política |
|-----------|-------------------|----------|
| **1D** | Sync manual + auto-sync (existente) | Incremental con overlap 7 días |
| **Intradía / 1wk / 1mo** | **Cache-on-read** al pedir OHLCV | Si vacío o TTL expirado → Yahoo → upsert → leer BD |

La auto-sync programada sigue centrada en **1D** (watchlists completas). El intradía se acumula al usar el gráfico y queda disponible para backtests sin repetir llamadas a Yahoo.

**Fase siguiente (no bloqueante):** cola de sync intradía por instrumentos favoritos / activos en workspace.

### 3. Consumidores unificados

Todo lee de PostgreSQL vía `GetOhlcvBars`:

- API `/ohlcv` e `/indicators`
- Backtests (cuando acepten timeframe)
- Evaluación server-side de reglas sobre dibujos
- Pipelines IA (export batch desde `ohlcv_bars`)

### 4. Retención (orientativa)

| Timeframe | Ventana Yahoo típica | Retención BD inicial |
|-----------|----------------------|----------------------|
| 1m | ~7 días | Lo que se cachee |
| 5m–30m | ~30 días | Idem |
| 1h–4h | ~1 año | Idem |
| 1wk / 1mo | años | Idem |
| 1D | 5–30 años sync | Completo |

Política de purga por antigüedad: fase posterior (`OhlcvRetentionJob`).

## Consecuencias

- Los datos intradía **sí quedan en BD** tras la primera visualización o refresh.
- Backtesting e IA pueden apoyarse en la misma fuente que el gráfico.
- Rate limit Yahoo se mitiga con cache + TTL por timeframe.
- Requiere migración de schema y redeploy API.

### Migración desde `db push` (instalaciones existentes)

La BD se creó originalmente con `prisma db push` sin historial de migraciones. Por eso `migrate dev` fallaba en la shadow DB (`type "Timeframe" does not exist`).

1. Baseline `20250101000000_baseline` — schema completo actual (solo para shadow / nuevos entornos).
2. Delta `20260701120000_intraday_ohlcv_persistence` — enum + `timestamptz`.

En una BD ya poblada:

```powershell
cd packages\database
pnpm db:migrate:resolve-baseline
pnpm db:migrate:deploy
pnpm db:generate
```

No ejecutes el SQL del baseline contra una BD que ya tiene tablas.

## Referencias

- [ADR-002](./002-yahoo-primary-xtb-secondary.md)
- [ADR-006](./006-chart-platform-and-settings.md) — Fase 2 «cache por (instrument, timeframe)»
