# Changelog

All notable releases of Bolsa V1.

## [1.2.0] — 2026-08-20

Refactorización y corrección R-7 / R-8 / R-9 completadas (hardening financiero + limpieza + contrato). DEMO / paper; sin broker live.

### R-9 — Núcleo financiero determinista (cerrada, F1–F8)

- **F1** Idempotencia deposit/withdraw aislada por cuenta + `type` (align lookup ↔ UNIQUE por-cuenta)
- **F2** 409 `IDEMPOTENCY_KEY_REUSED` ante `idempotency_key` reutilizada con payload distinto (sin migración)
- **F3** Carrera de custodia idempotente → nunca 500 en contienda (UNIQUE + savepoint + detección de violación)
- **F4** DTOs financieros estrictos (Pydantic fail-fast 422): `ge/gt` + `allow_inf_nan=False` en `CommissionProfileDto` / `CreateInvestmentAccountDto`
- **F5** Sesión con **epoch UTC** (`time.time()`) en vez de `time.monotonic()` (portable multi-host)
- **F6** `balance_after` documentado como **postcondición de app** (no constraint DB) + corrección de docs
- **F7** Suite de **concurrencia/invariantes** en PG real (`test_concurrency_scenarios.py`) + verifiers `scripts/verify/`
- **F8** Limpieza transversal E8: código/aliases muertos en Python + web + shared (pending-delete riesgo alto intacto)
- **F9 (V2)** — arquitectura Python + puente `legacy_portfolio_id`: **DIFERIDA** (requiere ADR + decisión explícita)

### R-7 — Deuda de dinero real (cerrada)

- Doble cargo de custodia en GET concurrentes · deposit/withdraw idempotentes · claim AUTO no quemado
- Ledger con UNIQUE `(account_id, reference_type, reference_id, type)` · reconciliación cash↔ledger · cost-basis FIFO/avg con fee · margen real · max drawdown high-water-mark · `transfer_cash` muerto eliminado · trade+fee idempotente en AUTO execute/confirm · guard FIFO qty==0 + observabilidad PnL CORE-R · `total_unrealized_gain` fail-closed

### R-8 — Prevención de riesgo + contrato (cerrada; incluida en v1.1.0)

- Sesión HttpOnly firmada + logout · rate-limit login/status · invariante `balance_after` por grupo atómico · limpieza transversal baja (R-8D) · fidelidad wire DTOs shared (R-8B.3) · CONTRACT-STALE resuelto (`openapi.json`+`schema.d.ts` regenerados)

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · R-8C.2 scheduler-vs-worker · M-4/T-M4 (job dedicado custodia) · gobernanza IA

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

## [1.1.0] — 2026-08-20

Integridad R-7/R-8 y fidelidad de contrato. DEMO / paper; sin broker live.

### Seguridad / sesión (R-8B)

- Cookie de sesión **HttpOnly firmada** + logout + endpoint `authenticated`
- Rate-limit en login/status (R-8B.1)
- Sesión vulnerable a reutilización multi-host corregida (preludio de epoch en R-9.5)

### Robustez financiera (R-7)

- `A-1/A-3` custodia: mutex `claim_custody_charge` + release · `A-2` deposit/withdraw idempotentes por `idempotency_key`
- `L-M3/M-5` ledger UNIQUE por-cuenta+type · `M-1` fallback mark-to-cost · `M-2` `sum_cash_amounts` rest con ledger · `M-3` cost-basis con fee · `M-6` margen real · `M-4/T-M5` fees de custodia fuera de `fees_paid_total` · `M-7` dedup verificación por UNIQUE · `B-1` max drawdown high-water-mark · `B-3` `transfer_cash` eliminado · `B-4` trade+fee idempotente AUTO/confirm · `B-5` guard FIFO qty==0 + obs. PnL CORE-R · `B-2` `total_unrealized_gain` fail-closed
- Invariante `balance_after` por grupo atómico (R-8C) · bootstrap advisory-lock · fidelidad wire DTOs (R-8B.3, fases A–D) · CONTRACT-STALE resuelto

## [Unreleased] — stage 2026-08-06

### Listas / Visualizados

- **Visualizados** = espejo de pestañas abiertas (separado de **Estudio** API)
- Quitar selección cierra tabs (sin resucitar por autosave) · **Por IO** ordena por Índice Operativo
- Columnas opcionales IO/TA/FA/★/Postura · sort por columna (tabs siguen el orden)
- Foco buscar/pestaña: lista **Cartera → Estudio → resto** + scroll bajo cabecera sticky
- Docs: `visualizados-list-ux-2026-08-06.md` · handoff `session-handoff-2026-08-06-visualizados-list-ux.md`

### Arranque (perf)

- Windows: liberar puertos con `netstat` (sin PowerShell Get-NetTCPConnection)
- `GET /api/lists/memberships` batch · sync catálogo con TTL 60s en `GET /lists`
- Monitor / CORE-R: batch `instrument-strategy-tops/query` (menos N+1 al pintar Trading)
- CORE-R shell: primer tick + hydrate diferidos (~1.5–4 s / idle) tras el paint

### Estudio / Operativa (ADR-024 + UI procesos)

- Universo **Estudio** API · Supervisión ON · cadencias Vigilia / Frescura / Redescubrimiento
- UI: subtítulo procesos bajo el nombre · botones **Actualizar** / **Redescubrir** (barra inferior) · chips cadencia V·F·R en banner · sellos locales
- Manual/SEMI/AUTO en barra de estado (`OPERATIVA: …`) → Cuentas · Config (fuera del panel por valor)
- Docs: `docs/engineering/estudio-process-status-ui-2026-08-06.md` · handoff `session-handoff-2026-08-06-estudio-process-ui.md` · HELP sync
- GitHub: [jvelasca/Bolsa_V1](https://github.com/jvelasca/Bolsa_V1) · PR stage [#29](https://github.com/jvelasca/Bolsa_V1/pull/29)

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
