# Documentación — Bolsa V1

Índice central. **Empieza por [ONBOARDING.md](./ONBOARDING.md)** si eres nuevo.

## Fuente de verdad (estado actual)

| Documento | Contenido |
|-----------|-----------|
| [AI_PLATFORM_SOLUTION.md](./AI_PLATFORM_SOLUTION.md) | Dictamen IA + estado F1/F2 · UI: Ayuda → Plataforma IA |
| [HELP.md](./HELP.md) | Mapa Ayuda ↔ trackers ↔ docs (`HELP_CONTENT_AS_OF`) |
| [rfc/README.md](./rfc/README.md) | Constitución RFC-000…007 · fases código |
| [API_REFERENCE.md](./API_REFERENCE.md) | Endpoints HTTP |
| [ONBOARDING.md](./ONBOARDING.md) | Setup primer día |
| [domain-language.md](./domain-language.md) | **Diccionario QROS** (Scientific / Trading / Infra) |

## Operación y producto

| Documento | Contenido |
|-----------|-----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Capas, monorepo |
| [DATA_MODEL.md](./DATA_MODEL.md) | Esquema BD |
| [MARKET_DATA.md](./MARKET_DATA.md) | Yahoo / XTB |
| [docker.md](./docker.md) | PostgreSQL (+ Ollama opcional aparte) |
| [UI_PLATFORM.md](./UI_PLATFORM.md) | Shell / barra superior |
| [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md) | **Premisa:** UI configurable → `localStorage` (por dispositivo/navegador) |
| [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md) | Espacios: chip, gestor, arranque, capas |
| [CHART_DATA_BAR.md](./CHART_DATA_BAR.md) | Barra de datos del gráfico |
| [CHART_DRAWING_TAXONOMY.md](./CHART_DRAWING_TAXONOMY.md) | Barra de dibujos |
| [CHART_INDICATORS.md](./CHART_INDICATORS.md) | Indicadores / paneles · catálogo unificado `IND-*` |
| [CHART_RESPONSIVE.md](./CHART_RESPONSIVE.md) | Responsive del gráfico |
| [BACKTESTING_DATA_ARCHITECTURE.md](./BACKTESTING_DATA_ARCHITECTURE.md) | Datos BT → IA |
| [adr/011-quantitative-research-platform.md](./adr/011-quantitative-research-platform.md) | **QROS** — arquitectura (congelado v1.1) |
| [adr/012-scientific-validation-knowledge-evolution.md](./adr/012-scientific-validation-knowledge-evolution.md) | **Leyes** científicas Evidence→Belief→Knowledge |
| [adr/013-research-mathematics-statistical-foundations.md](./adr/013-research-mathematics-statistical-foundations.md) | **Matemáticas** research (Discovery Vector, \(V_r\), EIG) — v1.1 |
| [adr/015-scientific-domain-vs-trading-domain.md](./adr/015-scientific-domain-vs-trading-domain.md) | **Scientific Domain ≠ Trading Domain** |
| [adr/016-research-persistence-model.md](./adr/016-research-persistence-model.md) | **Persistencia** científica (tablas, \(K\), Fase 1) |
| [adr/017-baseline-v1-5-research-observatory.md](./adr/017-baseline-v1-5-research-observatory.md) | **Baseline v1.5** — laboratorio observable (congelado) |
| [engineering/research-lifecycle.md](./engineering/research-lifecycle.md) | **Flujo** operativo BT → trials → Observatory · embudo · paper |
| [engineering/session-handoff-2026-08-01.md](./engineering/session-handoff-2026-08-01.md) | **Handoff** frescura v1.3 · FA · Composite v1.1 |
| [engineering/session-handoff-2026-07-31.md](./engineering/session-handoff-2026-07-31.md) | Handoff cierre DÍA D v0.11 + CORE-R v1.8 |
| [engineering/operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md) | Plan smoke UI DÍA D + CORE-R |
| [engineering/backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) | **Backtesting DÍA D** — as-of + replay (premisas bloqueadas) |
| [engineering/backtesting-funnel-handoff-2026-07-29.md](./engineering/backtesting-funnel-handoff-2026-07-29.md) | Handoff embudo→Finalistas A/C + Monitor MVP (retomar) |
| [HYBRID_TRACKERS.md](./HYBRID_TRACKERS.md) | Rastreadores híbridos |
| [PERFORMANCE.md](./PERFORMANCE.md) | Rendimiento frontend |
| [CONFIGURATION_MODEL.md](./CONFIGURATION_MODEL.md) | Modelo de configuración |
| [LEGACY.md](./LEGACY.md) | TS legacy (stub → archive) |

## ADRs y arquitectura

| Documento | Tema |
|-----------|------|
| [adr/](./adr/) | Architecture Decision Records |
| [architecture/investment-platform.md](./architecture/investment-platform.md) | Spec inversión |
| [architecture/_snapshots/](./architecture/_snapshots/) | Snapshots pre-fase |

## Arranque rápido

```bash
pnpm test:py:install
pnpm db:ensure
pnpm dev
# Web → http://localhost:5173
# API → http://localhost:8000/api/health
```

## Convenciones

- Código/commits: identificadores en inglés; UI y docs en español.
- Decisiones relevantes → ADR en `docs/adr/`.
- BD = fuente de verdad; Yahoo/XTB solo actualizan.
- API por defecto: **Python :8000**.
