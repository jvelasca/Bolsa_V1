# Engineering Index — índice maestro de docs

> **AsOf:** 2026-08-03  
> **Propósito:** un **padre único** para la documentación de ingeniería (respuesta a auditoría externa A0 H1).  
> **Regla:** todo doc nuevo de ingeniería declara exactamente **un padre** (este índice o un hijo directo). No añadir más raíces en paralelo.  
> **Repo:** https://github.com/jvelasca/Bolsa_V1

---

## 0. Cómo leer (cuatro públicos)

| Público | Empieza aquí | No necesita |
|---------|--------------|-------------|
| **Usuario** | [HELP.md](../HELP.md) · Ayuda (?) en app | ADRs / RFCs |
| **Desarrollador** | [ONBOARDING.md](../ONBOARDING.md) · [DEV_STARTUP.md](../DEV_STARTUP.md) · este índice §1–2 | RFCs completos |
| **Arquitecto** | [ARCHITECTURE.md](../ARCHITECTURE.md) · [adr/](../adr/) · [rfc/](../rfc/) · §3 | Notebooks de campaña |
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
│   ├── traspaso-m3-dominio-2026-08-10.md                   ← M3 capa de dominio (py/domain + application) CERRADO 08-10
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
│   ├── traspaso-higiene-formato-legacy-entrada-2026-08-10.md ← M0/§6.2 higiene de formato Prettier legacy por lotes aislados: ENTRADA · CRLF no es deuda (git normaliza LF) · real = 643 archivos desincronizados · lote 1 (components/ui+layout) `d39bbbb` · lote 2 (backtests/optimize) `0ceeb5b` · lote 3 (backtests/explore) `7c174c7` · lote 4 (backtests/result) `d96123d` · lote 5 (backtests/wizard) `9fa403a` · lote 6 (backtests/library+strategy-matrix) `68c9dac` · lote 7 (backtests/core-r) `f241872` · lote 8 (backtests/dia-d) `0a96220` · lote 9 (backtests/assistant) `1cb6ee7` · lote 10 (backtests/optimize restantes) `9853e79` · lote 11 (backtests/strategy-matrix restantes) `ee381d7` · lote 12 (backtests/list-auto+mass-compare) `9975cd3` · lote 13 (backtests/finalists+top) `f011918` · lote 14 (backtests/coach+lab) `6f8c668` · lote 15 (backtests/hub) `6c32b06` · restante por dominios (`chart`/`misc`…)
│   ├── traspaso-higiene-formato-legacy-salida-2026-08-11.md ← M0/§6.2 higiene Prettier legacy: SALIDA/RELEVO (punto de entrada del siguiente hilo) · protocolo 8 pasos + EOL check · avance 1-15 (160 files) HEAD `6c32b06` · `coach`/`lab` HECHO lote 14 · `hub` HECHO lote 15 · próximos dominios `chart`/`misc` · ver §7.6.i
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

---

## 2. Producto vs docs (no confundir)

| Capa | Qué es | Riesgo si diverge |
|------|--------|-------------------|
| **Producto (código)** | FastAPI + React + motor BT | Fuente de verdad de comportamiento |
| **Docs** | Premisas, ADRs, freeze, HELP | Explican y **congelan política**; no ejecutan |

Si código y ADR divergen: **ADR o freeze gana en política**; el código se alinea o se abre enmienda. No “arreglar” en silencio.

---

## 3. CORE — taxonomía única (A0 H5)

| Código | Nombre canónico | Dominio | Depende de | No puede depender de |
|--------|-----------------|---------|------------|----------------------|
| **CORE-P** | Profile / Policy | Trading | InvestorProfile, TradingPolicy | Coach LLM, Belief |
| **CORE-R** | Recommendation monitor | Trading ops | Finalistas, BD `core_r_*` | Research Belief, Lab re-opt en vivo |
| **CORE-A** | Assistant / Coach soft | Research UX | Ranking determinista, narración | Reordenar TOP, Belief (freeze) |
| **CORE-B** | Behaviour / Lab board | Research Lab | Jobs hold-out/WF | DEMO ledger, paper_auto |

Crecer en vertical bajo **CORE**, no inventar CORE-X sin fila aquí + issue.

---

## 4. Dependencias entre bounded contexts

Ver [bounded-contexts-2026-08-03.md](./bounded-contexts-2026-08-03.md).

**Regla de oro (A0 conclusión):** toda dependencia **nueva** entre módulos se justifica en PR (una frase) o se rechaza.

---

## 5. Auditorías externas

1. Entrada: [audit-pack-post-audits-2026-08-03.md](./audit-pack-post-audits-2026-08-03.md)  
2. Round 2 triage: [audit-ext-round2-triage-2026-08-03.md](./audit-ext-round2-triage-2026-08-03.md)  
3. Freeze: [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md)  
4. **Round 3 (pausa motor Estudio):** [audit-brief-estudio-motor-operativo-2026-08-04.md](./audit-brief-estudio-motor-operativo-2026-08-04.md)  
5. **Round 3 triage (ratificado O3-C · D1–Canales cerrados):** [audit-ext-round3-triage-estudio-motor-2026-08-04.md](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) §11 · [ADR-022](../adr/022-estudio-daily-opinion-motor.md)  
6. Diseño interno: [estudio-daily-opinion-alarms-design-2026-08-04.md](./estudio-daily-opinion-alarms-design-2026-08-04.md)  
7. **Asesor UI:** [asesor-ui-2026-08-04.md](./asesor-ui-2026-08-04.md) (ex-Research · tab Opiniones)  
8. **Pack cierre Estudio/Asesor/Canales:** [audit-pack-estudio-asesor-canales-2026-08-04.md](./audit-pack-estudio-asesor-canales-2026-08-04.md)  
9. **Thaw AUTO (prep, flag off):** [camino-d-auto-thaw-checklist-2026-08-04.md](./camino-d-auto-thaw-checklist-2026-08-04.md)  
10. **Triage institucional pre-AUTO (Aud 1+2):** [audit-ext-institutional-pre-auto-triage-2026-08-04.md](./audit-ext-institutional-pre-auto-triage-2026-08-04.md)  
11. **Risk Engine OR-RE v0:** [risk-engine-or-re-2026-08-04.md](./risk-engine-or-re-2026-08-04.md)  
12. **OR-lite + Repro+ + Obs/CI:** [or-lite-repro-obs-2026-08-04.md](./or-lite-repro-obs-2026-08-04.md)  
13. **Prep A2–A5 (flag off):** [camino-d-a2-a5-prep-2026-08-04.md](./camino-d-a2-a5-prep-2026-08-04.md) · [ADR-023](../adr/023-camino-d-thaw.md) Proposed  
14. **Pack auditoría prep AUTO:** [audit-pack-pre-auto-a0-a5-2026-08-04.md](./audit-pack-pre-auto-a0-a5-2026-08-04.md) — SEMI OK · execute AUTO **no**  
15. **Resumen operativo diario (R1–R4):** [daily-ops-report-brief-2026-08-04.md](./daily-ops-report-brief-2026-08-04.md) — Diario · HTML email · PDF opt-in
