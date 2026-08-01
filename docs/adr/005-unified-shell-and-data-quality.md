# ADR 005: Shell unificado, gráfico propio y calidad de datos

## Estado

Aceptado — jun 2026. Sustituye parcialmente la barra dual de ADR-004 (fase shell).

## Contexto

La UI actual tiene **MenuBar + Toolbar** (~68 px de chrome) y rutas secundarias (Overview, Cartera…) renderizadas **dentro del panel Gráficos**, lo que reduce espacio útil y confunde la navegación.

Objetivos acordados:

- Aspecto **moderno y profesional** (referencia: XTB xStation, ProRealTime web, TradingView layout).
- **Gráfico como protagonista** en la vista Trading.
- Datos de mercado **100 % de confianza** con seguimiento explícito de calidad y coherencia.
- Modelo **cliente-servidor** completo (persistencia en BD, no solo localStorage).
- Alcance **global** (horarios de mercado, divisas, tarifas).

## Decisiones

### 1. Barra superior única (eliminar MenuBar)

Una sola barra (~48 px):

```
┌────────────────────────────────────────────────────────────────────────┐
│ Bolsa │ Overview │ Trading │ Cartera │ Alertas │ … │ paneles │ guardar │
└────────────────────────────────────────────────────────────────────────┘
```

- **Eliminar** `MenuBar` (menús Espacio de trabajo / Gráficos / Listas / Ver).
- Acciones hoy en menús → **barra contextual del gráfico** (solo en Trading), menú **⋯** (workspace) o atajos en paneles.
- Toggles de panel (listas, operaciones) → iconos en la barra o bordes del dock (patrón VS Code).

### 2. Rutas y layouts

| Ruta | Vista | Layout |
|------|-------|--------|
| `/overview` | Resumen global (antes Dashboard) | **Pantalla completa** bajo barra superior |
| `/trading` | Terminal de análisis y operación | **Dock**: watchlist (izq) + gráfico + operaciones |
| `/portfolio`, `/alerts`, `/instruments`, … | Gestión | Pantalla completa |
| `/` | — | Redirige a `/trading` |

El dock de trading **no envuelve** Overview ni Cartera.

### 3. Watchlist (listas)

- Panel izquierdo **fijo por defecto**, **colapsable** (icono o arrastre a 0 px).
- Conserva carrusel, hub de listas, columnas y lista Visualización (sesión).

### 4. Operaciones

- **Panel inferior** persistente (posiciones, órdenes pendientes) — ya existe `TradingStatusBar` + `OperationsPanel`.
- **Diálogo modal** para nueva orden / detalle (ya existe `OrderDialog`).
- **Fase posterior:** líneas de compra/venta/stop **sobre el gráfico** (manual y auto). Tipos reservados en `shared` (`TradingLine`) sin implementar aún.

### 5. Gráficos: sin licencias de TradingView

| Modo | Tecnología | Uso |
|------|------------|-----|
| **Propio (core)** | `lightweight-charts` + API Bolsa | Histórico BD, indicadores, dibujos, backtest, calidad de datos |
| **Referencia externa** | Enlace a `tradingview.com/chart` (sin widget de pago) | Exploración rápida; no persiste en Bolsa |

**No** se integrará el Charting Library / widget comercial de TradingView (coste/licencia).

Evolución del modo propio:

1. Timeframes (1D primero; intradía cuando el pipeline lo soporte).
2. Indicadores en gráfico + paneles inferiores reubicables.
3. Dibujos avanzados (líneas, reglas, Fib, canales, texto).
4. Líneas de trading sobre precio.

### 6. Espacios de trabajo: varios layouts guardados

- Varios **workspaces nombrados** por usuario (servidor).
- Cada uno: tabs de gráfico, dibujos, layout de paneles, listas activas, plantillas de columnas.
- Migración desde `bolsa-workspace` (localStorage) → API `GET/PUT /api/workspaces`.

### 7. Persistencia servidor (cliente-servidor)

Todo lo que hoy vive en localStorage debe migrar a API + PostgreSQL:

| Recurso | Estado actual | Destino |
|---------|---------------|---------|
| Workspace (charts, drawings, layout) | localStorage | `workspaces` + `workspace_charts` |
| Dibujos chartistas | localStorage | JSON en workspace o tabla `chart_drawings` |
| Órdenes pendientes | localStorage | `pending_orders` |
| Layout dock (tamaños paneles) | localStorage | campo en workspace o preferencias usuario |
| Listas custom | API ✅ | — |

La app puede seguir ejecutándose en un solo PC; el modelo es el mismo que en producción.

### 8. Calidad y coherencia de datos por instrumento

Cada instrumento lleva **metadatos de calidad** (tabla o extensión de `instruments`), actualizados en cada sync y en chequeos programados.

Campos propuestos (`InstrumentDataQuality` o columnas en `instruments`):

| Campo | Descripción |
|-------|-------------|
| `lastBarDate` | Última vela en BD por timeframe principal |
| `expectedLastBarDate` | Último día/sesión de mercado esperado (calendario) |
| `freshnessStatus` | `current` \| `stale` \| `syncing` \| `error` \| `gap_detected` |
| `lastSyncAt` | Último sync Yahoo exitoso |
| `lastSyncStatus` | success / partial / failed |
| `lastXtBQuoteAt` | Última cotización XTB (si bridge activo) |
| `xtbVsCloseDeviationPct` | Desviación último XTB vs cierre BD |
| `gapCount` | Huecos detectados en ventana reciente |
| `sanityWarnings` | JSON: splits, volumen cero, OHLC incoherente |
| `primarySource` | yahoo \| xtb (para intradía futuro) |
| `qualityScore` | 0–100 agregado (opcional, calculado) |

**UI:** badge en gráfico (color + texto) + sección completa en diálogo **(i)** / propiedades del instrumento.

**Pipeline:**

1. Al abrir gráfico → si `stale` → sync incremental en background (cola final + solape 7 días).
2. Tras sync → `run_sanity_checks` (ya existe, cablear).
3. Si XTB disponible → comparar last vs cierre; registrar desviación.
4. Job post-cierre por **calendario de mercado** (global).

### 9. Alcance global

Nuevas entidades (fase datos, no bloquea shell):

- **`MarketCalendar`**: exchange, timezone, sesiones, festivos, early close.
- **`Exchange`**: MIC, país, moneda de cotización, horario referencia.
- **`FxRate`**: pares, fuente, timestamp (Yahoo FX ya usado en órdenes).
- **`Instrument`**: ampliar con `marketCalendarId`, `quoteCurrency`, `tradingCurrency`.

Las apps pro (IBKR, Bloomberg, XTB) resuelven esto con **calendario por bolsa** + **FX en tiempo de operación** + **normalización a moneda de cartera**. Bolsa V1 adopta el mismo patrón de forma incremental.

### 10. Overview (antes Dashboard)

- Ruta `/overview`; etiqueta **Overview** en la barra (más representativo que “Dashboard”).
- Vista separada del dock Trading: widgets de cartera, alertas recientes, estado de sync global.

## Roadmap de implementación

```
P1  Shell unificado + rutas (/trading vs full-page) + rename Overview
P2  GET /instruments/{id}/data-status + auto-sync + badge gráfico + (i)
P3  Persistencia workspace/dibujos en servidor
P4  Gráfico propio: timeframes UI, paneles indicadores, toolbar contextual
P5  MarketCalendar + freshness global multi-bolsa
P6  Intradía (schema timestamptz + ingest)
P7  TradingLine sobre gráfico (manual → auto)
```

## Consecuencias

- Menos altura de chrome; más espacio al gráfico.
- ADR-004 shell “doble barra” queda obsoleto en fase 1; docking y workspace siguen válidos.
- Sin dependencia de licencias TradingView; el producto diferenciador es **datos propios + calidad visible**.
- Requiere migraciones Prisma y endpoints nuevos antes de quitar localStorage.

## Referencias

- [UI_PLATFORM.md](../UI_PLATFORM.md)
- [MARKET_DATA.md](../MARKET_DATA.md)
- [ADR 002](./002-yahoo-primary-xtb-secondary.md)
- [ADR 004](./004-prorealtime-ui-platform.md)
