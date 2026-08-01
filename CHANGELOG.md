# Changelog

All notable releases of Bolsa V1.

## [1.0.0] — 2026-08-01

Primera release empaquetada (**BETA1 → GitHub V1**). DEMO / paper; sin broker live.

### Producto
- Embudo Backtesting: Coach ★ local · Lab AT · Lista AUTO (frescura v1.3) · Finalistas
- **CORE-P** perfil ↔ Coach/Lab (gate, techo DD, soft-bias espacio, E2E smoke/ASGI)
- **CORE-B** v0.2 memoria Lab (meseta → espacio · `resolveDefaultLabFamily`)
- **CORE-R** v1.8 reevaluación (Monitor, cola, narración; cron local)
- **DÍA D** v0.11 simulación as-of + Evidence (fullBleed no se persiste)
- Análisis del valor / FA·FIE · Tarjeta CAPM footnote · Composite liquidez v1.1
- Trading supervisado F3 (Decision Engine); paper auto dry-run (execute off-by-default)
- Ayuda / trackers sincronizados (`HELP_CONTENT_AS_OF` 2026-08-01)

### Calidad
- `pnpm test:coach` · `test:coach:smoke` · `test:coach:api`
- `pnpm test:operativa` · `test:operativa:smoke`
- `pnpm test:fa`

### Congelado (no en V1)
- Belief UI · Lab Discovery P3–P9 · `PAPER_D_EXECUTE` · CORE-R multi-dispositivo · broker live

### Notas
- Stack: React/Vite + FastAPI + PostgreSQL
- Requiere Node ≥20, pnpm ≥10, Python ≥3.11, Docker Desktop
