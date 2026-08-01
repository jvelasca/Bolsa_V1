# ADR 006: Configuración global y plataforma gráfica profesional

## Estado

Aceptado (diseño) — jun 2026.  
**Nota jul 2026:** la implementación gráfica ha avanzado respecto a las fases P4 de este ADR.
La fuente de verdad del estado actual en UI es **Ayuda → Estado gráficos**
(`chart-platform-tracker.ts`, sync `HELP_CONTENT_AS_OF` — ver [HELP.md](../HELP.md)).
Este ADR sigue siendo el diseño de referencia; no uses las tablas de fases inferiores como backlog literal.

## Contexto

Bolsa V1 necesita dos capas de configuración claramente separadas, como en ProRealTime, TradingView o XTB xStation:

1. **Configuración global de la aplicación** — captura de datos, proveedores, sincronización programada, preferencias de workspace, cuenta.
2. **Configuración por gráfico / instrumento** — timeframe, zoom, indicadores instanciados, objetos gráficos, reglas de trading asociadas.

Hoy la auto-sync vive en Overview; las propiedades del gráfico son un diálogo modal básico; los indicadores son toggles fijos (SMA/EMA/RSI). No hay catálogo de indicadores ni motor de objetos con eventos.

## Decisiones

### 1. Centro de configuración (`/settings`)

Una ruta única con navegación lateral por secciones:

| Sección | Alcance | Persistencia |
|---------|---------|--------------|
| General | Workspace, autoguardado, tema (futuro) | Servidor + local |
| Captura de datos | Proveedores, flujo manual, calidad | Informativo + API status |
| Sincronización automática | Cola, intervalos, rate limit | `SyncSettings` (BD) |
| Plataforma gráfica | Roadmap, enlaces a doc | Solo UI |
| Cuenta y seguridad | Auth (futuro multi-user) | `.env` / BD |

Overview muestra **resumen** y enlaza a Settings; no duplica formularios completos.

### 2. Modelo de datos de mercado (recordatorio ADR-002)

```
Yahoo (histórico OHLCV) ──sync──► PostgreSQL ◄──read── Gráficos / Backtests
XTB Bridge (cotización live) ──► API quote (no persiste barras)
```

- **Manual**: `POST /api/instruments/{id}/sync` desde UI o badge de frescura.
- **Automática**: worker en background escanea instrumentos `stale|empty`, encola con delay y backoff; fallos reencolan.
- **Criterio de frescura**: calendario de mercado por bolsa (`expected_last_daily_bar`).

### 3. Arquitectura del entorno gráfico (por pestaña de chart)

Cada `ChartTabState` evoluciona hacia un documento autocontenido:

```typescript
interface ChartTabState {
  id: string;
  instrumentId: string;
  label: string;
  // ── Timeframe & viewport ──
  timeframe: ChartTimeframe;      // 1D hoy; 1H, 4H, 1W en fases
  viewport?: ChartViewportState;  // zoom, scroll, escala log (futuro)
  // ── Apariencia base ──
  chart: ChartInstanceConfig;     // grid, colores, cursor (existente)
  // ── Indicadores instanciados ──
  indicators: ChartIndicatorInstance[];
  // ── Objetos gráficos ──
  drawings: ChartDrawing[];     // existente; ampliar tipos y props
  // ── Reglas (futuro) ──
  rules?: ChartRuleBinding[];
}
```

**Separación clave (patrón ProRealTime / TV):**

| Concepto | Qué es | Dónde se configura |
|----------|--------|-------------------|
| **Catálogo de indicadores** | Definición: SMA, RSI, MACD, script custom, IA | Menú Indicadores (global) |
| **Instancia en gráfico** | Aplicación con parámetros (periodo 14, color, panel) | Propiedades del gráfico / panel derecho |
| **Objeto gráfico** | Línea, fibo, canal, triángulo, regla | Toolbar dibujo + inspector |
| **Regla / alerta gráfica** | Cruce de línea → orden, alerta, webhook | Inspector del objeto o panel Reglas |

### 4. Timeframes y zoom (fases)

| Fase | Entregable |
|------|------------|
| P4a ✅ | 1D, gráfico adaptativo al panel, volumen integrado, RSI en sub-panel |
| P4b | Selector multi-timeframe; persistir `timeframe` por pestaña; API OHLCV por intervalo |
| P4c | Zoom scroll/pinch; botones +/-; reset vista; sincronizar eje tiempo entre paneles |
| P4d | Escalas: lineal/log, % , ajuste automático del rango visible |

`lightweight-charts` soporta time scale sync entre charts vinculados (RSI ↔ precio).

### 5. Catálogo de indicadores

Tres orígenes, un modelo común:

```typescript
type IndicatorSource = 'builtin' | 'custom' | 'ai';

interface IndicatorDefinition {
  id: string;
  name: string;
  source: IndicatorSource;
  category: 'trend' | 'momentum' | 'volatility' | 'volume' | 'custom';
  parameters: IndicatorParamSchema[];  // period, source field, etc.
  outputs: IndicatorOutputSchema[];    // línea, histograma, banda, panel separado
  compute: 'server' | 'client' | 'wasm';  // builtin → server hoy
}

interface ChartIndicatorInstance {
  instanceId: string;
  definitionId: string;
  parameters: Record<string, number | string | boolean>;
  display: { visible: boolean; color: string; panel: 'overlay' | 'sub' };
  zIndex: number;
}
```

**Menú Indicadores** (nuevo, barra superior en Trading):

- Pestañas: Estándar | Mis indicadores | IA (futuro)
- Buscar + favoritos
- Doble clic o «Añadir al gráfico activo» crea `ChartIndicatorInstance`
- Propiedades por instancia en panel lateral (no solo toggles globales)

Indicadores builtin iniciales: SMA, EMA, RSI, MACD, Bollinger, ATR, Volumen (ya parcial).

### 6. Objetos gráficos y eventos

Ampliar `ChartDrawing` existente:

```typescript
interface ChartDrawing {
  id: string;
  type: 'line' | 'ray' | 'rectangle' | 'fibonacci' | 'channel' | 'triangle' | 'ruler' | 'hline';
  vertices: ChartPoint[];
  style: DrawingStyle;           // color, grosor, estilo línea, relleno
  locked: boolean;
  visible: boolean;
  // ── Fase eventos ──
  triggers?: DrawingTrigger[];
}

interface DrawingTrigger {
  id: string;
  event: 'price_cross' | 'touch' | 'breakout' | 'time_reached';
  direction?: 'up' | 'down' | 'both';
  action: 'alert' | 'pending_order' | 'market_order' | 'webhook' | 'backtest_marker';
  params: Record<string, unknown>;  // side, qty, message, etc.
  enabled: boolean;
}
```

Evaluación de triggers:

1. **En cliente** (tiempo real): monitor como `PendingOrdersMonitor` — precio live vs geometría.
2. **En servidor** (histórico / backtest): replay sobre barras para validar estrategias dibujadas.
3. **Cola** para acciones que requieran API (órdenes).

Inspiración: ProRealTime «ProOrder from line», TradingView alerts on drawing, MT5 object events.

### 7. UI profesional — layout objetivo en Trading

```
┌─ Top bar: nav + workspace + [Indicadores▼] [Objetos▼] [Propiedades gráfico] ─┐
├─ Watchlist ─┬─ Chart tabs ────────────────────────────────────────────────────┤
│             │ Toolbar timeframe │ indicadores activos │ badge datos            │
│             │ ┌─ Panel precio + volumen (flex) ─────────────────────────────┐ │
│             │ └─ Sub-paneles indicadores (RSI, MACD, …) ─────────────────────┘ │
│             │ Status: última vela │ escala │ crosshair OHLC                    │
├─────────────┴─ Operaciones ─────────────────────────────────────────────────────┤
└─ Status bar cartera ────────────────────────────────────────────────────────────┘
```

Panel **derecho contextual** (futuro): inspector del objeto o indicador seleccionado — paridad con ProRealTime «Propiedades».

### 8. Persistencia

| Dato | Dónde |
|------|-------|
| SyncSettings, cola | PostgreSQL (global) |
| Workspace + charts + drawings + indicators | PostgreSQL `Workspace` JSON |
| Layout dock trading | localStorage (por dispositivo) |
| Catálogo indicadores custom | PostgreSQL (fase posterior) |
| Scripts IA generados | PostgreSQL + revisión usuario |

## Fases de implementación

```
Fase 0  ✅ Settings /settings + ADR + Overview resumen
Fase 1  Menú Indicadores + instancias en workspace JSON + panel sub-chart genérico
Fase 2  Multi-timeframe API + selector + cache por (instrument, timeframe)
Fase 3  Zoom avanzado + sync time scale entre paneles
Fase 4  Inspector objetos (estilo, lock) + tipos triángulo, ray, hline
Fase 5  Triggers en objetos → alertas y órdenes pendientes
Fase 6  Indicadores custom (DSL / Pine subset) + IA asistente
```

## Consecuencias

- La configuración global queda desacoplada de la per-chart; el usuario entiende «App vs Gráfico de SAN».
- El modelo `ChartIndicatorInstance` reemplaza progresivamente toggles fijos en `ChartDisplayConfig`.
- Los objetos gráficos con eventos requieren motor de evaluación y tests de regresión geométricos.
- Multi-timeframe implica ampliar schema OHLCV y sync Yahoo (intervalos intradía con límites de rate).

## Referencias

- [ADR-002](./002-yahoo-primary-xtb-secondary.md) — proveedores
- [ADR-004](./004-prorealtime-ui-platform.md) — shell y workspaces
- [ADR-005](./005-unified-shell-and-data-quality.md) — calidad de datos
- ProRealTime: indicadores, dibujos, ProOrder
- TradingView: studies, drawings, alerts
- lightweight-charts: multi-pane, time scale sync
