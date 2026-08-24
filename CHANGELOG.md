# Changelog

All notable releases of Bolsa V1.

## [Unreleased]

- **ADR-031 / Ciclo 4.2** (`a7eeaee`, en origin vía `4930344`): `EntrySetup` refina `entry_ready`; campo `entrySetup`. Spine **81**. Sin `ARMED` · sin `contract:gen`.
- **ADR-031 / Ciclo 4.1** (`97f4862` = origin/main): Golden G `NO_NEW_LONGS` — long + `risk_off`/`crisis` → `BLOCKED`/`regime`. Spine **79**. Sin EntrySetup · sin `contract:gen`.
- **ADR-031 / Ciclo 4.0** (`1cbd021`, en origin vía stamp `d99b1d1`): stop estructural ATR×1.5 + swing 10 barras (más lejano), `entry_ready` por bias TA, size con equity de cartera. Spine **75**. Sin familias EntrySetup · sin `contract:gen`.
- **ADR-031 / TradePlan en propose+confirm** (`17a386d`): `data.tradePlan` + `runtime.tradePlan`; confirm echo; Hoy prefiere plan vivo. Spine **67**. Sin `contract:gen`.
- **ADR-031 / TradePlan v0** (`818b0c7`): tesis ≠ plan ≠ permiso. Confirm SEMI: TTL, revalidación de precio, H3 orphan fail-closed. `pending_orders` fill vía `check_opening`. Strip **Hoy** en la mesa. Golden A/B/C/H.
- **Python CI pytest:** excluye tests DB-gated R12 isolation + F7b backfill del workflow offline (`386a959`) — **569 pass** sin Postgres.
- **Ruff I001:** import order hygiene en 49 ficheros Python (`a3dcc3f`) — desbloquea gate Import-linter en Python CI (post F9-A3 `f8c7e3f`).
- **F9-A3:** gate `lint-imports` en Python CI (4 contratos, `packages/py/.importlinter`).
- Post-`v1.7.0-beta` ya en `main`: OrderProposal/Journal F1–F3 + F9-A1/A2 (`8a1e64d`). Purge V2 sigue MONITOR. F9-B PARKED.

## [1.7.0-beta] — 2026-08-24

Ciclo post-`v1.6.0-beta` (Decision Spine + mesa U0–U6 + gates DS-05/DS-03 + ops + copy Research→Radar). Producto sigue **BETA**. Tag anotado **`v1.7.0-beta`** (pendiente de crear por coordinador sobre commit de stamp). Partida: **`c3964fc`**. Tags `v1.6.0-beta` / `v1.5.0-beta` / `v1.3.0` intactos.

### Track B — split backtests + nav Señales (heredado post-R-13)

- **F4′–F6′** (`240c846`): copy nav **Señales** (`/screeners`); tests href B0; herencia R-13 Track B desbloqueado.
- **B1–B12**: extracción incremental de `backtests-page.tsx` (~4698→321 LOC shell) — constantes/tipos, queries, mutations, derivados, URL sync, navegación, Lista AUTO, play cycle, Lab handlers, tabs run/jobs, `useBacktestPageModel`. Sin cambio de comportamiento; smoke manual backtests sigue recomendado.

### Fase 0 Decision Spine (código + docs)

- **F0.5b** (`3670a09`): PortfolioFit v1 — concentración cesta activo+sector, VETO fail-closed; `MaxSectorExposure` cableada.
- **F0.6b + F0.6-UI** (`8df8a65`, `672e88f`): Decision Board v1 backend + UI solo lectura (`/decision-board`).
- **D1/D2/D3**: risk cesta SEMI=AUTO (`7530556`); DecisionPackage contrato en confirm SEMI (`f7b1f6c`); Lab/Radar **fuera** del spine (`ea0c93f`, ADR-019).
- **Confirm SEMI deuda** (`2281903`): `wait` sin sesión ya no ejecuta sell default; side de `exit_hint`/`reduce` desde package.
- **Prove Spine** (`5e81350`): S0–S3, tests `pnpm test:decision-spine`, golden scenario.
- **H5** (`f56af2f`): perfil inversor SEMI → `check_opening` (mismo SoT AUTO).

### UX mesa U0–U6

- **U0–U4** (`6f26f9d`): tips Ayuda, presets S/R, Confirm drawer, chips Fit.
- **U5** (`04e441e`): proyección orden F3 en chart (post-SEMI preview).
- **U6** (`9e9a346`): preview ticket en Confirm/drawer — notional, comisión, margen (UI-only; sin bypass execute).

### Spine residual — gates en `check_opening`

- **DS-05** (`15e86a4`): Data Freshness Gate fail-closed (umbral 5×24h; SEMI ohlcv + AUTO `signal.timestamp`; exits fuera).
- **DS-03** (`41adb8e`): Account Mandate Gate fail-closed (tenure BD `mandate_tenures`; mismatch estrategia AUTO; exits fuera). Batería `pnpm test:decision-spine` **53**.

### Ops (ejecutable + propietario)

- **Ops residual** (`3c53f4e`…`7363ec6`): saneo símbolos `/` en import índices; fix 404 recurrente `BP.L`; re-sync `idx-ftse100` verificado; backup corrupt drop.
- **Ops propietario** (`5100d23`): secret scanning + push protection enabled vía API; runbook `TRUSTED_PROXIES` prod (valor real sigue en propietario).
- **Higiene dev** (`ea9a985`, dato local `bolsa_v1`): script `cleanup_dev_test_residues.py`; 3 cuentas huérfanas R8C eliminadas; `verify_ledger_balance_chain.py` **EXIT 0**.

### Research→Radar copy (UI)

- CTAs y cross-links **Asesor** (`/research`) vs **Señales** (`/screeners`); helpers `asesorHistoryHref`; sin fusión de páginas ni rutas API. Hereda F4′–F6′. Batería: `daily-nav.test.ts` 8/8.

## [1.6.0-beta] — 2026-08-22

Consolidación BETA post-R-12 (ciclo R-13). Producto sigue **BETA**. Tag anotado **`v1.6.0-beta` → `c3964fc`**. Tags `v1.5.0-beta` / `v1.3.0` intactos. Plan: `docs/engineering/plan-r13-consolidacion-beta-2026-08-22.md`.

### R-13 consolidación (docs + E8 micro)

- Cierre de R-12 como ciclo de reparación. Firma de partida R-13: `origin/main` **`5edbcb5`** (histórica) → **`c3964fc`** (A0–A3). README alineado a **v1.6.0-beta**. Track B producto (god-page / Research→Radar) **bloqueado**.
- A2: tests de contrato/ausencia en `chart-new-tab-setup.test.ts`; **purge** de `normalizeChartNewTabSeed` (0 callers). `extractChartNewTabSeed` / `applyChartNewTabSeed` intactos. Pending-delete alto **sin purge**.

### Auth D4 / JWT (incluido en release; commits post-`v1.5.0-beta`, ya en `main`)

- **R12-ACCOUNTS** (`3c958f1`) paquete `bolsa_application/accounts/`
- **R12-AUTH F1–F3** stamp owner + 404 cuenta ajena + cash/trade scoped
- **F4** ADR-027 Opción C **Aceptado** · **F5–F7a** tabla `users` + JWT + list/get scoped · **F8–F8e** perfiles, trackers, policies, events, workspaces, list-for-list
- **F9** FE login campo `login` opcional · **F10** `session_version` + `/auth/refresh` + rate-limit user
- **F7b** script + apply **local** (103→0 NULL; no prod) · **JWT-only** (`tokens.py` eliminado; SHA-256/HMAC → 401)
- **F7c** match estricto `user_id == principal` · `scan.completed` `ownerUserId` · cron stamp `tracker.user_id`
- Pending-delete E8 tests (`851b545`) · purge V2 métricas T+0 19/19 (**E8 N, sin purge**)

## [1.5.0-beta] — 2026-08-22

R-12 Track C (mesa SEMI frontend) + copy E8 residual + leftover CORE-R + tres gates de contrato/ejecución/workers. Producto sigue **BETA**. Tag anotado **`v1.5.0-beta` → `5e52bd6`**. Tag `v1.3.0` → `b778292` intacto. Plan: `docs/engineering/plan-r12-auditoria-ux-2026-08-21.md`.

### Track C + higiene copy

- Track C **C1** (`5bc51ff`): ruta `/confirm`, nav Confirmar con badge de cola, `openHelpAiPlatform({ panel: "supervised-f3" })` navega SPA (no Ayuda)
- Track C **C2** (`01af9ff`): nav diaria Trading · Señales · Confirmar vs Laboratorio / Asesor; hub Señales; copy Universo en vigilancia
- Track C **C3** (`97e20ab`): AUTO de cuenta «No disponible (BETA)»; copy de mesa sin `PAPER_D_EXECUTE`; execute sigue congelado
- Track C **C4** (`154fcd1`): nav **Libro** (Operaciones + Historial); cabeceras «Libro · …»; sin fusionar páginas
- Track C **C5** (`0eb8976`): HELP + Ayuda sync Confirm `/confirm` · Señales/Libro · AUTO BETA · frase SEMI
- Copy E8 residual (`ce601c9`) + leftover CORE-R (`8dd3caf`): CTAs de firma → `/confirm` dejan de decir Ayuda; atajos list-hub `/screeners` = Señales (Laboratorio); leftover CORE-R Proponer F3 ya en Confirmar

### Gates cerrados

- **R12-409 B1** (`eb24608`): declarar HTTP 409 en OpenAPI para conflictos de `idempotency_key` en deposit/withdraw/trade (`{detail: str}`); regen acotada `openapi.json` + `schema.d.ts`; runtime handler sin cambio
- **EXEC-B-CONC** (`ca60d0a`): `ExecuteTrade` deriva `balance_after` trade/fee desde cash post-lock (`result.summary.portfolio.cash`); elimina lectura pre-lock `get_summary`; chaos refuerza invariante B estricta bajo concurrencia
- **R12-SCHED / R-8C.2** (`5e52bd6`): scheduler = crons only; poll no-ARQ → `bolsa-queue-poll-worker`; ARQ → `bolsa-arq-worker` (queue_poll no-op); `run-dev.mjs` spawnea el proceso correcto según `SCAN_QUEUE_BACKEND`

### Contexto R-12 previo (Track A+B)

- Firma de estado: **GitHub `origin/main`**; implementación Track A+B `48cc255`; partida R-12 `f7a86cc`; premisas esenciales del ciclo R-12
- Alineación documental: README `v1.3.0 BETA`; tag `v1.3.0` → **`b778292`**
- Tests/scripts de verificación residuales (DEFAULT_PORTFOLIO, invariantes C–E, retry HTTP)
- Inventario `pending-delete` (sin purge) + higiene E8 + estudio UX comparativo (Track B **aprobado**, mesa 5 puertas)

## [1.3.0] — 2026-08-21

Endurecimiento del núcleo financiero y del gate CI apuntado por la **auditoría externa sobre v1.2.1** (R-11: C1–C5, C6, D1, D2 — todas cerradas) + deuda de datos/código residual cerrada tras el cierre de R-11. Documenta la política de cargo de custodia (C6) y deja `verify_ledger_balance_chain.py` en **EXIT 0 global**. Tag: `v1.3.0` sobre **`b778292`** (cierre documental; padre `deafa27` = fix test + verify EXIT 0). DEMO / paper; sin broker live.

### Post-R-11 (deuda §3 del traspaso, cierre de release)

- **Test** (`deafa27`) `test_execute_trade_con_fees_reconcilia` corregido: `ExecuteTrade.execute(...)` pide `idempotency_key` (R-10 F1 / R-11 C2); se añade `f"trade-{uuid4().hex[:8]}"` (deuda ajena a R-11, no regresión de gate). Batería coordinador: `test_m2` 7 passed 1 xfailed
- **Dato dev** (fuera de repo) cuenta de simulación huérfana `acc_broken_72ab7c2aa881` ("R8C broken", única de 111 que fallaba la cadena `balance_after` por +0.01 float legacy) **eliminada por path canónico** `close_account`→`delete_simulated_account` (coherente con R-10 F3-sim; **D6 prohíbe backfill** por eso no se reescribió `balance_after`) → `verify_ledger_balance_chain.py` **EXIT 0**

### R-11 — Endurecimiento post-v1.2.1 (C1–C6 + D1 + D2 cerradas a `main`)

- **C1** (`c3327c1`) Custodia **multi-periodo** (R-10.6): tabla `custody_obligations` PK `id` autoincremento + `UNIQUE(account_id, period)` + `created_at`/`updated_at`; migración Alembic `006_custody_obligations_period` (encadena sobre `005`); `upsert` reparado para **no sobrescribir** + `get_pending_by_account`/`get_by_account_period`; `ApplyCustodyFees`/`RunCustodyJob` liquidan primero el PENDING más antiguo antes del periodo nuevo
- **C2** (`17a1107`) **Idempotency_key end-to-end** (R-10.7): DTOs `DepositCashDto`/`WithdrawCashDto`/`TradeRequestDto` con `str_strip_whitespace=True`, `min_length=16`, `max_length=128`; repo `execute_trade` con `idempotency_key: str` obligatoria + rechazo de `""`/whitespace; guard en `ConfirmRecommendationIntent` (uuid4 fallback)
- **C3** (`cda26e9`) **Precisión Decimal end-to-end** (R-10.8): en `ExecuteTrade.execute` `notional`/`cash_before`/`amount`/`trade_balance`/`fee_balance` en `Decimal`, `float` solo en el borde al invocar repo/ledger; invariante secuencial exacta
- **C4** (`157bb45`) `contract:check` **EXIT 0** (R-10.9, Opción A): regen acotada de `apps/web/api/openapi.json` — `idempotencyKey` con `minLength/maxLength` + `TaxProfileDto` con `minimum:0.0`; `schema.d.ts` sin cambio; el 409 sigue solo en runtime (handler global), no en OpenAPI (decisión Opción A)
- **C5** (`6762614`) **`mypy` == 0 en gate CI** (R-10.9): añadida `packages/py/application/src` al step Mypy de `.github/workflows/python-ci.yml`; limpiados **105 errores en 33 ficheros** de la capa application; semántica mínima en `ledger_repository` (`limit: int|None=50`), `market_indices`, `fetch_core_r_pnl_extra_rows` (guard numérico) y `scans.py` (fix de `TypeError` latente: `expected_last_daily_bar()` sin el `exchange` obligatorio; ahora por instrumento)
- **C6** (docs, 2026-08-21) Política de cargo de custodia **`custody_charge_source = DEFAULT_PORTFOLIO`** documentada en ADR 026: la custodia es obligación de cuenta (importe sobre **equity agregado**) pero se cobra **exclusivamente desde la cartera seleccionada/default** (`scope.portfolio`, fallback `is_default`); sin transferencia implícita entre carteras — **solo documenta la regla, sin cambio de comportamiento**
- **Batería global R-11** (verificada por el coordinador): mypy gate `344 files` EXIT 0 · mypy application `95 files` EXIT 0 · ruff 0 · pytest application+market `388` · pytest api-python offline `84`
- **D2** (`db95709`, con C6) **Cierre documental**: docstrings aditivos en `ApplyCustodyFees.execute`/`ExecuteTrade.execute` (accounts.py, 14 ins, 0 lógica) · estado documental en PROJECT_STATE/backlog/index/plan/ADR 026/CHANGELOG
- **D1** (`870fb21`) **Limpieza transversal E8**: `custody_obligation_repository.get_by_account` + `get_by_account_period` (0 callers producción; el segundo nunca se cableó a `ApplyCustodyFees`/`RunCustodyJob`) quitados del repo y de fakes de test · se mantienen `get_pending_by_account`/`upsert` · **sin tocar ítems RIESGO ALTO** · batería D1: ruff 0 · mypy repo gate 0 · pytest custodia 7 · pytest application 279

## [1.2.1] — 2026-08-21

Correcciones de la **auditoría externa post‑v1.2.0** (R-10, F1–F5). Refuerza el núcleo financiero detectado en la pasada: `balance_after` secuencial, custodia con obligación pendiente y fuera del GET, DTOs estrictos, idempotencia exacta y `idempotency_key` obligatoria. DEMO / paper; sin broker live.

### R-10 — Correcciones de la auditoría externa (cerrada, F1–F5)

- **F1** `idempotency_key` **obligatoria** en deposit/withdraw/trade (422 si falta) + contrato/regen OpenAPI y ajuste de consumidores web
- **F2a** `TaxProfileDto` estricto (Pydantic fail-fast 422): `ge=0`, `allow_inf_nan=False`, `fiscal_year_start_month ∈ [1,12]`
- **F2b** Comparación idempotente **exacta normalizada a `Numeric(18,6)`** (eliminada la tolerancia de `0.01`)
- **F3** `balance_after` de trade+fee **secuencial por fila** (cash FINAL ya no en ambas), sin backfill (forward-only)
- **F4a** Custodia **Opción B con obligación pendiente** (tabla `custody_obligation`, `PENDING`/`APPLIED`, ADR 026, migración `005`): si `cash < fee` no descuenta ni marca DONE — registra `PENDING` y cobra el total cuando haya saldo
- **F4b** Custodia **fuera del GET** → job periódico `RunCustodyJob` (scheduler/worker); `GetAccountSummary`/`GetTaxReport` quedan **100% de solo lectura** (desfase de saldo pre‑custodia aceptado mientras corre el job). **Reabre `M-4/T-M4`** (job de custodia dedicado)
- **F5** Cierre: docs de estado (backlog, PROJECT_STATE, engineering-index, plan-r10) + CHANGELOG `[1.2.1]` + limpieza E8 inventariada

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · **R-8C.2 scheduler-vs-worker** · gobernanza IA
- **`M-4/T-M4` REACTIVADO y CERRADO por R-10 F4b** (`e12a125`) — la custodia ya es un job dedicado, no muta en GET

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

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
