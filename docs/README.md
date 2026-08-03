# Documentación — Bolsa V1

Índice central. **Empieza por [ONBOARDING.md](./ONBOARDING.md)** si eres nuevo.

## Fuente de verdad (estado actual)

| Documento | Contenido |
|-----------|-----------|
| [PROJECT_PREMISES.md](./PROJECT_PREMISES.md) | **Premisas de proyecto** (documentar todo · índice de premisas · repo público) |
| [AI_PLATFORM_SOLUTION.md](./AI_PLATFORM_SOLUTION.md) | Dictamen IA + estado F1/F2 · UI: Ayuda → Plataforma IA |
| [HELP.md](./HELP.md) | Mapa Ayuda ↔ trackers ↔ docs (`HELP_CONTENT_AS_OF`) |
| [rfc/README.md](./rfc/README.md) | Constitución RFC-000…007 · fases código |
| [API_REFERENCE.md](./API_REFERENCE.md) | Endpoints HTTP |
| [ONBOARDING.md](./ONBOARDING.md) | Setup primer día |
| [domain-language.md](./domain-language.md) | **Diccionario QROS** (Scientific / Trading / Infra · universos LAB/TRADING) |

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
| [adr/019-dual-universes-lab-vs-trading.md](./adr/019-dual-universes-lab-vs-trading.md) | **LAB ≠ TRADING** (universos UI; Cartera LAB) |
| [adr/020-operating-mandate-tenure.md](./adr/020-operating-mandate-tenure.md) | **Mandato operativo** — tenure estrategia×instrumento (TRADING · M1b BD) |
| [adr/021-dia-d-reconciliation.md](./adr/021-dia-d-reconciliation.md) | **Reconciliación DÍA D** — F-hoy · F-D · V (SAME/DRIFT · contrafactual) |
| [engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md](./engineering/stage-audit-lab-dia-d-mandate-2026-08-02.md) | **Auditoría cierre etapa** LAB/DÍA D/Mandato (checklist externa) |
| [engineering/audit-pack-post-audits-2026-08-03.md](./engineering/audit-pack-post-audits-2026-08-03.md) | **Paquete auditoría** post-Q0–Q3 + freeze + evidencia smoke |
| [engineering/audit1-response-ingest-fie-2026-08-03.md](./engineering/audit1-response-ingest-fie-2026-08-03.md) | **Respuesta auditoría 1** — gaps reales A/B (ingesta + FIE) vs stack Bolsa_V1 |
| [engineering/improvement-roadmap-post-audits-2026-08-02.md](./engineering/improvement-roadmap-post-audits-2026-08-02.md) | **Roadmap mejoras** post-auditorías (Q0–Q3 · horizonte TOP) |
| [engineering/post-audit-decision-freeze-2026-08-03.md](./engineering/post-audit-decision-freeze-2026-08-03.md) | **Freeze** post-Q3: C4 no · Belief no · flags ops off |
| [engineering/dev-logs.md](./engineering/dev-logs.md) | Logs locales `logs/` (no producto; sin README en carpeta) |
| [engineering/code-documentation-standard-2026-08-03.md](./engineering/code-documentation-standard-2026-08-03.md) | **Docstrings** — política forward-only + lotes de cobertura |
| [DEV_STARTUP.md](./DEV_STARTUP.md) | F5 / `pnpm dev` · puertos · doctor |
| [engineering/stability-campaign-protocol-2026-08-02.md](./engineering/stability-campaign-protocol-2026-08-02.md) | Protocolo estabilidad multi-ventana (Q1.2/Q1.3) |
| [adr/016-research-persistence-model.md](./adr/016-research-persistence-model.md) | **Persistencia** científica (tablas, \(K\), Fase 1) |
| [adr/017-baseline-v1-5-research-observatory.md](./adr/017-baseline-v1-5-research-observatory.md) | **Baseline v1.5** — laboratorio observable (congelado) |
| [engineering/research-lifecycle.md](./engineering/research-lifecycle.md) | **Flujo** operativo BT → trials → Observatory · embudo · paper |
| [engineering/session-handoff-2026-08-01.md](./engineering/session-handoff-2026-08-01.md) | **Handoff** frescura v1.3 · FA · Composite v1.1 |
| [engineering/session-handoff-2026-07-31.md](./engineering/session-handoff-2026-07-31.md) | Handoff cierre DÍA D v0.11 + CORE-R v1.8 |
| [engineering/operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md) | Plan smoke UI DÍA D + CORE-R |
| [engineering/backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) | **Backtesting DÍA D** — as-of + replay (premisas; Modo A 2026-08-02) |
| [engineering/dual-universes-lab-trading-design-2026-08-02.md](./engineering/dual-universes-lab-trading-design-2026-08-02.md) | **Dos universos** LAB vs TRADING — diseño UI/carteras/puente |
| [adr/019-dual-universes-lab-vs-trading.md](./adr/019-dual-universes-lab-vs-trading.md) | **ADR-019** — LAB ≠ TRADING (producto) |
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
- **Documentar todo** (producto en `docs/` + docstrings/JSDoc forward-only) — [PROJECT_PREMISES.md](./PROJECT_PREMISES.md) §1 · [code-documentation-standard](./engineering/code-documentation-standard-2026-08-03.md).
- Decisiones relevantes → ADR en `docs/adr/`.
- BD = fuente de verdad; Yahoo/XTB solo actualizan.
- API por defecto: **Python :8000**.
- Repo GitHub: **público** (`jvelasca/Bolsa_V1`) para auditorías.
