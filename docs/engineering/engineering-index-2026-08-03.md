# Engineering Index — índice maestro de docs

> **AsOf:** 2026-08-03  
> **Propósito:** un **padre único** para la documentación de ingeniería (respuesta a auditoría externa A0 H1).  
> **Regla:** todo doc nuevo de ingeniería declara exactamente **un padre** (este índice o un hijo directo). No añadir más raíces en paralelo.  
> **Repo:** https://github.com/jvelasca/Bolsa_V1

---

## 0. Cómo leer (cuatro públicos)

| Público                    | Empieza aquí                                                                                        | No necesita          |
| -------------------------- | --------------------------------------------------------------------------------------------------- | -------------------- |
| **Usuario**                | [HELP.md](../HELP.md) · Ayuda (?) en app                                                            | ADRs / RFCs          |
| **Desarrollador**          | [ONBOARDING.md](../ONBOARDING.md) · [DEV_STARTUP.md](../DEV_STARTUP.md) · este índice §1–2          | RFCs completos       |
| **Arquitecto**             | [ARCHITECTURE.md](../ARCHITECTURE.md) · [adr/](../adr/) · [rfc/](../rfc/) · §3                      | Notebooks de campaña |
| **Investigador / auditor** | [audit-pack-post-audits-2026-08-03.md](./audit-pack-post-audits-2026-08-03.md) · freeze · lifecycle | Detalle UI de charts |

Índice general de todos los docs: [README.md](../README.md) (catálogo). **Este Engineering Index es el mapa de navegación**, no duplica el catálogo.

---

## 1. Árbol canónico (un padre)

```text
Engineering Index  (este doc)
├── Architecture
│   ├── ARCHITECTURE.md
│   ├── PROJECT_PREMISES.md
│   ├── adr/*  (decisiones)  — incl. ADR-001 (Prisma) · ADR-003 (Python backend) · ADR-025 (fuente verdad modelo, M4)
│   ├── rfc/*  (constitución)
│   └── bounded-contexts-2026-08-03.md
├── Research
│   ├── research-lifecycle.md
│   ├── backtesting-dia-d-premises-*.md
│   ├── improvement-roadmap-*.md
│   └── belief-coach-brief-draft-*.md  (futuro)
├── Product / Ops
│   ├── HELP.md  (sync Ayuda)
│   ├── stage-audit-*.md
│   ├── post-audit-decision-freeze-*.md
│   ├── dual-universes / mandato / reconciliación ADRs
│   ├── demo-operating-modes-brief-*.md   (MANUAL/SEMI/AUTO)
│   ├── semi-demo-book-impl-slice1-*.md   (GO SEMI)
│   ├── trading-operativa-panel-2026-08-04.md  (Operativa · IO · modos en barra)
│   ├── estudio-supervision-model-2026-08-06.md  (ADR-024 · Supervisión ON · 3 cadencias)
│   ├── estudio-process-status-ui-2026-08-06.md  (iconos · Actualizar/Redescubrir · OPERATIVA)
│   ├── session-handoff-2026-08-06-estudio-process-ui.md
│   ├── visualizados-list-ux-2026-08-06.md
│   ├── session-handoff-2026-08-06-visualizados-list-ux.md
│   ├── dev-continuation-plan-2026-08-09.md   ← continuación (estado + próximos pasos)
│   ├── audit-resume-premises-2026-08-09.md   ← premisas nuevo hilo auditoría
│   ├── general-audit-plan-2026-08-10.md       ← auditoría general + plan por módulos
│   ├── traspaso-m1-reproducibilidad-backend-2026-08-10.md  ← M1 reproducibilidad backend (uv.lock)
│   ├── traspaso-m2-versiones-frontend-2026-08-10.md        ← M2 versiones frontend (@types react) CERRADO 08-10
│   ├── traspaso-m3-dominio-2026-08-10.md                   ← M3 capa de dominio (py/domain + application) · entrada original (punto de entrada del hilo)
│   ├── traspaso-m3-dominio-cierre-2026-08-11.md            ← M3 CIERRE real: 4 lotes (fix ADR-024 `ce0cdab` · código muerto 5 Protocols `f13b09d` · docstrings 33 módulos `03472dc` · coherencia MIN_SCAN_BARS+KnowledgeStage `2c41b41`) · HEAD `2c41b41` · pytest domain+application 222 passed · deuda remanente: timeframes y mypy
│   ├── traspaso-m4-infraestructura-datos-2026-08-10.md     ← M4 infraestructura/modelo datos (Prisma vs SQLAlchemy + Alembic + repos) CERRADO 08-10 · ADR-025
│   ├── traspaso-m6-ai-analytics-2026-08-10.md              ← M6 AI/analytics (py/ai + py/analytics) CERRADO 08-10
│   ├── traspaso-m5-frontend-2026-08-10.md                  ← M5 Frontend web por features (apps/web): CERRADO-08-10 como feature-slicing Diseño B agotado (ver §7 nota de cierre) / entrada
│   ├── traspaso-m5-f4-8-coach-lab-2026-08-10.md            ← M5 hilo F4.8 siguiente: Coach + Lab (feature-slicing backtests-page)
│   ├── traspaso-m5-frente-coach-cierre-2026-08-10.md      ← M5 cierre frente: Lab extraído (paso 9) · Coach extraído (paso 10) · frentes alternativos evaluados
│   ├── traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md ← M5 frente trading-dia-d: B.1+B.2+B.3 extraídos (DiaDTradesPanel, DiaDPendingTradeBanner, DiaDSessionReportPanel) · frente CERRADO
│   ├── traspaso-m5-frente-backtest-explore-cierre-2026-08-10.md ← M5 frente backtest-explore (área Coach/TOP): E.1+E.2+E.3+E.4+E.5 extraídos (BH, Header, BatteryTable, AtOutlook, StarsGrid) · frente CERRADO · M5 en pausa
│   ├── traspaso-m5-continuacion-orquestacion-2026-08-10.md      ← M5 continuación: FASE 1 orquestación list-values-panel (1.395) / instruments-page (1.222) · punto de entrada del siguiente hilo
│   ├── traspaso-m5-frente-list-values-instruments-cierre-2026-08-10.md ← M5 frentes list-values/instruments: FASE 1 + I.1+I.2 extraídos (ListSearchBox, ListSelectionToolbar) · list-values 1.395→1.242 · instruments CERRADO como ya feature-sliced · M5 en pausa
│   ├── traspaso-m5-frente-create-account-wizard-cierre-2026-08-10.md ← M5 frente create-account-wizard: C.1–C.5 extraídos (IdentityStep, CapitalStep, CommissionsStep, TaxStep, ReviewStep) · 791→632 · profile excluido por alto acoplamiento · M5 en pausa
│   ├── traspaso-m5-frente-optimize-panel-entrada-2026-08-10.md ← M5 frente backtest-optimize-panel (2.168): ENTRADA con FASE 1 hecha (7 islas data-only bajo riesgo) · primera ola sugerida C-OPT.1–C-OPT.4
│   ├── traspaso-m5-frente-optimize-panel-cierre-2026-08-10.md ← M5 frente backtest-optimize-panel: CIERRE PARCIAL bajo+medio riesgo (C-OPT.4 cardheader + C-OPT.1 summarystrip/emptytip + C-OPT.2 WF/Edge/CPCV cards + C-OPT.5 seedbanner) · 2168→1880
│   ├── traspaso-higiene-formato-legacy-entrada-2026-08-10.md ← M0/§6.2 higiene de formato Prettier legacy por lotes aislados: ENTRADA · CRLF no es deuda (git normaliza LF) · real = 643 archivos desincronizados · lote 1 (components/ui+layout) `d39bbbb` · lote 2 (backtests/optimize) `0ceeb5b` · lote 3 (backtests/explore) `7c174c7` · lote 4 (backtests/result) `d96123d` · lote 5 (backtests/wizard) `9fa403a` · lote 6 (backtests/library+strategy-matrix) `68c9dac` · lote 7 (backtests/core-r) `f241872` · lote 8 (backtests/dia-d) `0a96220` · lote 9 (backtests/assistant) `1cb6ee7` · lote 10 (backtests/optimize restantes) `9853e79` · lote 11 (backtests/strategy-matrix restantes) `ee381d7` · lote 12 (backtests/list-auto+mass-compare) `9975cd3` · lote 13 (backtests/finalists+top) `f011918` · lote 14 (backtests/coach+lab) `6f8c668` · lote 15 (backtests/hub) `6c32b06` · lote 16 (backtests/chart) `a42587e` · lote 17 (backtests/misc motores) `da2f7d9` · lote 18 (cierre misc: library/estudio/ibex) `5bec6ed` · **`features/backtests` COMPLETO** · siguiente: resto `apps/web/src`
│   ├── traspaso-higiene-formato-legacy-salida-2026-08-11.md ← M0/§6.2 higiene Prettier legacy: SALIDA/RELEVO · protocolo 8 pasos + EOL check · **COMPLETO: `apps/web/src` (fuera de `features/backtests`, ya COMPLETO) 512 files con diff real en 36 commits · HEAD `5b47f60` (línea 1-31: backtests + accounts/workspace/config+platform/research/settings/instruments/stores/lib/screeners; líneas 32-36: trading 4 sub-lotes + auxiliares+root)** · `features/backtests` COMPLETO (lotes 2-18) · **`trading` 32-35 (CIERRE) · auxiliares+root 36 (CIERRE resto `apps/web/src`) · prettier --check amplio = 0 files desincronizados** · siguiente: sin pendientes (iniciar nuevo dominio o deuda si chat saturado) · ver §7.6.i
│   ├── relevo-higiene-formato-lotes-24-27-2026-08-11.md ← M0/§6.2 relevo del hilo (lotes 19-27): estado verificado HEAD `e498c68` · protocolo 8 pasos + encodificación ASCII + aviso auto-review · dominios pendientes (screeners/charts/trading/auxiliares) · 250 files pendientes · docs a actualizar (3)
│   ├── relevo-higiene-formato-cierre-2026-08-11.md ← M0/§6.2 CIERRE del hilo de higiene Prettier: `apps/web/src` (fuera de `features/backtests`, ya COMPLETO) COMPLETO · 512 files / 36 commits · HEAD `6112fb2` · 0 files por `prettier --check` amplio · sin pendientes · ancla de cierre para futuros frentes
│   ├── chart-top1-indicator-switch-*.md
│   └── operativa-test-plan-*.md
├── Audit (entrada externa)
│   ├── audit-pack-post-audits-*.md     ← START externos
│   ├── audit1-response-*.md
│   ├── audit2-response-*.md
│   └── audit-ext-round2-triage-*.md    ← round 2 (A0 / N4 / deep)
└── Historical
    ├── session-handoff-*.md
    ├── backups/
    └── research/observations/*
```

**Anti-patrón:** un doc con tres “padres” (p. ej. enlazado como raíz desde README + HELP + lifecycle sin declarar jerarquía). Enlazar **sí**; ser raíz **no**.

**Protocolo recurrente (norma permanente, 2026-08-11):** al **cerrar cualquier hilo de chat** (fin de módulo/fase/frente o saturación de contexto), el agente DEBE preparar el siguiente: crear/actualizar su `traspaso-*` con estado + decisiones + deuda residual, añadir su entrada aquí, y **entregar al usuario en el chat el texto exacto para pegar en el siguiente hilo**. Este índice es el punto de enrutamiento de esas continuaciones.

---

## 2. Producto vs docs (no confundir)

| Capa                  | Qué es                       | Riesgo si diverge                             |
| --------------------- | ---------------------------- | --------------------------------------------- |
| **Producto (código)** | FastAPI + React + motor BT   | Fuente de verdad de comportamiento            |
| **Docs**              | Premisas, ADRs, freeze, HELP | Explican y **congelan política**; no ejecutan |

Si código y ADR divergen: **ADR o freeze gana en política**; el código se alinea o se abre enmienda. No “arreglar” en silencio.

---

## 3. CORE — taxonomía única (A0 H5)

| Código     | Nombre canónico        | Dominio      | Depende de                      | No puede depender de                |
| ---------- | ---------------------- | ------------ | ------------------------------- | ----------------------------------- |
| **CORE-P** | Profile / Policy       | Trading      | InvestorProfile, TradingPolicy  | Coach LLM, Belief                   |
| **CORE-R** | Recommendation monitor | Trading ops  | Finalistas, BD `core_r_*`       | Research Belief, Lab re-opt en vivo |
| **CORE-A** | Assistant / Coach soft | Research UX  | Ranking determinista, narración | Reordenar TOP, Belief (freeze)      |
| **CORE-B** | Behaviour / Lab board  | Research Lab | Jobs hold-out/WF                | DEMO ledger, paper_auto             |

Crecer en vertical bajo **CORE**, no inventar CORE-X sin fila aquí + issue.

---

## 4. Dependencias entre bounded contexts

Ver [bounded-contexts-2026-08-03.md](./bounded-contexts-2026-08-03.md).

**Regla de oro (A0 conclusión):** toda dependencia **nueva** entre módulos se justifica en PR (una frase) o se rechaza.

---

## 5. Auditorías externas

1.  Entrada: [audit-pack-post-audits-2026-08-03.md](./audit-pack-post-audits-2026-08-03.md)
2.  Round 2 triage: [audit-ext-round2-triage-2026-08-03.md](./audit-ext-round2-triage-2026-08-03.md)
3.  Freeze: [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md)
4.  **Round 3 (pausa motor Estudio):** [audit-brief-estudio-motor-operativo-2026-08-04.md](./audit-brief-estudio-motor-operativo-2026-08-04.md)
5.  **Round 3 triage (ratificado O3-C · D1–Canales cerrados):** [audit-ext-round3-triage-estudio-motor-2026-08-04.md](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) §11 · [ADR-022](../adr/022-estudio-daily-opinion-motor.md)
6.  Diseño interno: [estudio-daily-opinion-alarms-design-2026-08-04.md](./estudio-daily-opinion-alarms-design-2026-08-04.md)
7.  **Asesor UI:** [asesor-ui-2026-08-04.md](./asesor-ui-2026-08-04.md) (ex-Research · tab Opiniones)
8.  **Pack cierre Estudio/Asesor/Canales:** [audit-pack-estudio-asesor-canales-2026-08-04.md](./audit-pack-estudio-asesor-canales-2026-08-04.md)
9.  **Thaw AUTO (prep, flag off):** [camino-d-auto-thaw-checklist-2026-08-04.md](./camino-d-auto-thaw-checklist-2026-08-04.md)
10. **Triage institucional pre-AUTO (Aud 1+2):** [audit-ext-institutional-pre-auto-triage-2026-08-04.md](./audit-ext-institutional-pre-auto-triage-2026-08-04.md)
11. **Risk Engine OR-RE v0:** [risk-engine-or-re-2026-08-04.md](./risk-engine-or-re-2026-08-04.md)
12. **OR-lite + Repro+ + Obs/CI:** [or-lite-repro-obs-2026-08-04.md](./or-lite-repro-obs-2026-08-04.md)
13. **Prep A2–A5 (flag off):** [camino-d-a2-a5-prep-2026-08-04.md](./camino-d-a2-a5-prep-2026-08-04.md) · [ADR-023](../adr/023-camino-d-thaw.md) Proposed
14. **Pack auditoría prep AUTO:** [audit-pack-pre-auto-a0-a5-2026-08-04.md](./audit-pack-pre-auto-a0-a5-2026-08-04.md) — SEMI OK · execute AUTO **no**
15. **Resumen operativo diario (R1–R4):** [daily-ops-report-brief-2026-08-04.md](./daily-ops-report-brief-2026-08-04.md) — Diario · HTML email · PDF opt-in
16. **Auditoría consolidada interna+externas + plan hardening (2026-08-11):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) — 4 fuentes cruzadas (interna · externa 1 · externa 2 · externa 3) · mapa P0/P1/P2 · plan F1–F5 · decisiones D0–D5 pactadas · checkpoint git `audit-checkpoint-2026-08-11` · NO tocar código
    >     └── **Plan F1 (integridad financiera):** [plan-f1-integridad-financiera-2026-08-11.md](./plan-f1-integridad-financiera-2026-08-11.md) — micro-cambios M1–M5 (`with_for_update`, `deduct_cash`, `ExecuteTrade`, idempotencia, invariantes) · batería+riesgos+orden commits · pendiente de aprobación
    >         └── **F1 — traspaso de hilo:** [traspaso-f1-integridad-financiera-2026-08-11.md](./traspaso-f1-integridad-financiera-2026-08-11.md) — documento de trabajo F1 (integridad financiera) **CERRADO 2026-08-11** ✅ · rama `stage/f1-integridad-financiera-2026-08-11` creada desde `7edb3d1` · M1 `3d093cb` (with_for_update) · M2 `113e27a` (deduct_cash allow_partial, Opción B) · M3 `5128cf4` (ExecuteTrade saldo real) · M4 `986399d` (idempotencia+contrato estricto, migración Prisma `20260811010000_trade_idempotency`) · M5 `3c59dc8` (suite invariantes contables) · **verificación final**: web 707 ✓ · infra M2+M5 8+8 ✓ · api M4 3 ✓ · ruff 0 nuevos · mypy 0 nuevos (71 pre-existentes base) · **cero regresiones** · commits M1→M5 · ver §9 del traspaso
    >         └── **F2 — traspaso de hilo:** [traspaso-f2-backtest-next-open-2026-08-11.md](./traspaso-f2-backtest-next-open-2026-08-11.md) — documento de trabajo F2 (Rigor científico del backtest, fill `next_open`) **COMPLETADO 2026-08-11** · A `backtest.py` `execution_model` next_open · B grids H0 SMA/RSI/MACD + `optimize.py` · C `vectorbt_sma`/`optuna_sma` shift+open · D fingerprint OHLCV completo + bump manifest 1.1 / engine 0.4.0 · E `test_no_lookahead.py` · F `scripts/research/recalc_trials_next_open.py` · pytest analytics 323✓ + application 222✓ + api offline 9✓ = **554✓ · 0 fallos** · **PR #30 MERGED** (fast-forward en `stage/f1-*`, 6 commits C1–C6, rama `stage/f2-*` eliminada) · **recálculo de trials ejecutado 20/20 (`next_open`, engine 0.4.0)** · fix `distinct` SQLAlchemy 2.0 (`a3573ae`) · deuda: `--mark-legacy` no-op (sin columna, → F3b) · ver §9
    >         └── **F3b — traspaso de hilo:** [traspaso-f3b-alembic-data-epoch-2026-08-11.md](./traspaso-f3b-alembic-data-epoch-2026-08-11.md) — documento de trabajo F3b (Alembic autoridad BD + columna `data_epoch`) **COMMITEADO + PR #31 ABIERTO** · A `env.py` real · B alembic.ini `prepend_sys_path`/`path_separator` · C baseline `001` tolerante a TimescaleDB ausente · D migración `002_research_data_epoch` (DDL `data_epoch` en `backtest_runs`/`research_trials`) · E `database/migrations.ensure_migrated()` (upgrade head idempotente) · F llamada en lifespan (P1.2, fuera del path) · G columna en `tables.py` · H `--mark-legacy` deja de ser no-op (`_mark_legacy` legacy/next_open) · I `test_f3b_alembic_data_epoch.py` · pytest infra 46✓ + app 222✓ + analytics 323✓ + api offline 11✓ = **602✓ · 0 fallos** · `alembic_version=002` aplicado en local · **PR #31 MERGED 2026-08-11** (merge commit `014a207` en `stage/f1-*`) · deuda: portar DDL Prisma→Alembic (→F3a/F4), `account_repository.ensure_migrated` por-request (→F3a) · ver §9
    >         └── **F5a — traspaso de hilo:** [traspaso-f5a-contratos-fe-be-2026-08-11.md](./traspaso-f5a-contratos-fe-be-2026-08-11.md) — documento de trabajo F5a (Contratos FE/BE: OpenAPI fuente de verdad + drift gate, hallazgo P1.5) **COMMITEADO + PR #32 ABIERTO (6 commits C1–C6, HEAD `dde9c32`)** · rama `stage/f5a-contratos-fe-be-2026-08-11` desde `stage/f1-*` (tras merge PR #31) · A `apps/api-python/scripts/dump_openapi.py` (offline, sin servir/BD) · B `apps/web/api/openapi.json` versionado (**180 paths / 367 schemas**, fuente de verdad) · C `apps/web/src/api/schema.d.ts` generado (`openapi-typescript@7.13.0`) · D `apps/web/scripts/sync-contract.mjs` (`contract:gen` + `contract:check` gate de spec) · E scripts en `apps/web/package.json` + devDep · F `apps/web/src/api/contract-check.ts` gate de tipos (claves FE ⊆ contrato, sentinelas BacktestRunDto/PortfolioSummaryDto/InvestmentAccountDto) · **G (corrección C5–C6)** `.prettierignore` (excluye artefactos generados) + LF en dump + norm. CRLF en `--check` → contrato reproducible byte-a-byte, tree limpio tras `contract:gen` · batería: ruff✓ mypy✓ pytest api-python **27✓** · web typecheck✓ lint✓ test **707✓** · contract:check✓ (verificado falla ante drift) · **drift medido P1.5**: `manifest` FE ⊆ BE roto, normalizaciones number↔integer / ?↔null · deuda: sustituir DTOs manuales fidelidad campo-a-campo + `openapi-fetch` como cliente (no en esta fase) · ver §9
    >         └── **F3a — traspaso de hilo:** [traspaso-f3a-procesos-db-2026-08-11.md](./traspaso-f3a-procesos-db-2026-08-11.md) — documento de trabajo F3a (Arquitectura de procesos y DB) **COMPLETADO 2026-08-11** · rama `stage/f3a-procesos-db-2026-08-11` desde `stage/f1-*` (tras merge PR #32) · **P0.4/D3** `scheduler_worker.py` (proceso dedicado; workers fuera del `lifespan`) + `main.py` limpio + `pyproject` script + `run-dev.mjs` + tests · **P1.2** `run_account_data_migration` idempotente una-vez (lifespan + scheduler); retirada `ensure_migrated` del path de petición · **P0.5/D2** `003_prisma_schema_baseline` (takeover: schema completo 53 tablas + 8 enums, no-op en BD Prisma / fresh-build sin Prisma) + guards idempotencia en `002` + generador `dump_alembic_prisma_baseline.py --check` (reproducible) · **fix borrado de cuentas FK** en `delete_simulated_account` · batería: ruff 0 en fase (25→13→7 heredados → F4) · mypy✓ nuevos · pytest infra **48✓** + api **30✓** + domain/market/application/analytics/ai **676✓** · `--check`✓ · deuda: P1.6 mypy gate, ruff gates infra restantes (7), P1.9 API thin → F4 · ver §9
    >         └── **F4 — traspaso de hilo:** [traspaso-f4-arquitectura-python-2026-08-11.md](./traspaso-f4-arquitectura-python-2026-08-11.md) — documento de trabajo F4 (Arquitectura Python) **COMPLETADO 2026-08-12** · rama `stage/f4-arquitectura-python-2026-08-11` desde `stage/f1-*` (tras merge PR #33) · **P0.6** ciclo `analytics↔market` ROTO: `MarketEvent`/`MarketEventCalendar`/`EventBlackoutContext`/`build_market_event`/`event_decay_weight` → `bolsa_domain/entities/market_event.py` y `prefer_summary_excerpt` → `bolsa_domain/value_objects/excerpt.py`; `analytics` y `market` quedan como pares solo con `domain` (0 imports cruzados src↔src; re-export de compatibilidad en `bolsa_analytics.cognitive`) + 2 fixes mypy preexistentes en `news_snapshot.py` · **7 ruff gates CERRADOS** (I001 ×6 + B007): `ruff check packages/py apps/api-python` → **0 errores** · **P1.6** mypy gate POR FASES (files_only): paso CI bloqueante `Mypy — gate scoped F4` sobre 13 ficheros (exit 0); paso global sigue `continue-on-error` (~451 preexistentes) · batería: ruff 0 · mypy gate 13 files ✓ · pytest market+analytics **431✓** + application **222✓** + infra+domain **57✓** + api-python **30✓** (bolsa_v1) + ai+analytics **337✓** · deuda: P1.9 API thin (hilo propio), mypy resto del árbol por fases, D4 auth → F5b · ver §9
    >         └── **F5b — traspaso de hilo:** [traspaso-f5b-backend-seguridad-2026-08-12.md](./traspaso-f5b-backend-seguridad-2026-08-12.md) — documento de trabajo F5b (Backend/Seguridad) **COMPLETADO 2026-08-12** · rama `stage/f5b-backend-seguridad-2026-08-12` desde `stage/f1-*` (tras merge PR #34/F4) · **P1.8** rate-limit **distribuido** entre workers: `rate_limit.py` con `RedisStore` (INCR+PEXPIRE en Lua) + `MemoryStore` fallback + circuit-breaker; prefijos `SENSITIVE_PREFIXES` deterministas (específico→genérico) y `/api/instruments/{id}/fundamentals` por segmento · **P2.3** `upsert_bars` en **bulk INSERT...ON CONFLICT DO UPDATE** (una sentencia multi-fila; antes loop N+1), validado contra BD real en rollback · **P2.5** `/health` sin filtrar internos: Redis sin `url_host`/`{exc}`, auth sin `APP_PASSWORD`/`OR-S1`, xtb sin URL real, smtp sin `port`/`hasUser`/`missing`, worker_arq sin key interna, DB mensaje genérico; + `test_health_redacts_internal_details` · **P2.7** `Deposit/Withdraw.amount` → `gt=0`+`allow_inf_nan=False` (TradeRequestDto ya estricto F1/M4) · **CI (defecto preexistente)** `quality` Pytest sin Postgres corría `test_health/auth/ai_authoring` (lifespan→DB → `Connection refused`): se excluyen (ig. `test_lists`/`test_workspaces`) → **quality UNBLOCK**; mypy gate → `F4+F5b` (16 files, exit 0) · batería: ruff 0 · mypy gate 16 ✓ · pytest offline **451✓** + api 27✓ (bolsa_v1) + application 222✓ + infra+domain 57✓ + ai+analytics+digest **340✓** · deuda: P1.9 API thin (hilo propio), P1.3 auth full D4 diferido, P2.1 god-components frontend, F5a §6 fidelidad DTOs/openapi-fetch, mypy preexistente por fases · ver §9
    >         └── **F5c — traspaso de hilo:** [traspaso-f5c-frontend-cleanup-2026-08-12.md](./traspaso-f5c-frontend-cleanup-2026-08-12.md) — documento de trabajo F5c (Frontend clean-up de la parte frontend de F5) **COMPLETADO 2026-08-12** · rama `stage/f5c-frontend-cleanup-2026-08-12` desde `stage/f1-*` (tras merge PR #35/F5b) · **P2.8** formato: nuevo `apps/web/src/lib/format.ts` (punto único local "es-ES", helpers preservan semántica exacta) + `format.test.ts` (7) · migrados **29 call sites/helpers locales** `toLocaleString("es-ES")` (dispersos en ~30 ficheros) · **P2.8 timers**: 11 llamadas bare → `window.setTimeout/setInterval` + handles `number` (antes `ReturnType<typeof setTimeout>`) · **P2.6** `packages/shared`: script `test` (vitest) + `vitest.config.ts` (alias a src) + `policy-gate.test.ts` (8, paridad TS↔Py RFC-008) + pasos CI `Frontend` "Typecheck shared"/"Test shared" (el único test era huérfano) · batería: shared test **10✓** typecheck✓ lint✓ + web typecheck✓ lint 0 test **714✓** (141 f) · commits `e72650d`/`d908ac2`/`d9ae632` · **P2.1 god-components DIFERIDO a hilo propio** (decisión usuario; mapa listo) · residue: `as unknown as` (8) bridges intencionales→fidelidad F5a §6; duplicación TS↔Py restante (ai-indicator-series/execution-policies/position-policies) exige acuerdo de diseño · ver §8
