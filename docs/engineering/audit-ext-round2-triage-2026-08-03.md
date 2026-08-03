# Triage — Auditorías externas round 2 (A0 · N4 · Deep) — 2026-08-03

> **Propósito:** contrastar tres informes externos del 2026-08-03 con el **código y docs reales** de Bolsa_V1; decidir qué se adopta, qué ya existe, qué se aparca y qué **no aplica** (stack inventado).  
> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md).  
> **Entrada auditoría:** [audit-pack-post-audits-2026-08-03.md](./audit-pack-post-audits-2026-08-03.md).  
> **Freeze:** [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md) — **sin reabrir** C4 / Belief / flags ops.  
> **Stack real:** FastAPI (`apps/api-python`) + `packages/py/*` + React Vite (`apps/web`). **No** tRPC · Drizzle · Next.js · `packages/core` · `packages/engine` · `packages/market-data`.

---

## 0. Resumen ejecutivo

| Informe | Valoración nuestra | Acción inmediata |
|---------|-------------------|------------------|
| **A0 — Arquitectura global** | Muy alineado; riesgo = complejidad documental + ecosistema | **Hecho:** Engineering Index + bounded contexts + taxonomía CORE |
| **N4 — Código/datos/mecánica** | Útil como radiografía del freeze; algunos diagramas **sobre-inventan** (Redis Pub/Sub SSE, vault, Kendall formal) | **Aceptar espíritu**; errata abajo; sin código nuevo |
| **Deep — Código/seguridad** | Contamina con **otro monorepo** (paths/deps inexistentes) | **Errata fuerte**; no implementar checklist 48h tal cual; mapear solo gaps reales |

**Veredicto producto:** seguir **probando el Lab entregado**. No abrir Belief, C4, Risk 3 capas, microservicios, streaming BT, Alpaca, OTel.

---

## 1. Auditoría A0 — Arquitectura global

### Notas del auditor (10/10 arquitectura) — **de acuerdo**

El riesgo principal ya no es “mal diseño”, sino **complejidad acumulada** (docs + módulos). Correcto.

### Hallazgos

| # | Pri | Hallazgo | Veredicto Bolsa | Acción |
|---|-----|----------|-----------------|--------|
| H1 | ALTA | Segunda arquitectura documental | **Aceptado** | [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) — un padre; 4 públicos |
| H2 | ALTA | Ecosistema / dependencias cruzadas | **Aceptado** | [bounded-contexts-2026-08-03.md](./bounded-contexts-2026-08-03.md) |
| H3 | ALTA | Research Ledger → ADR propio | **Parcial** | Contratos repartidos en ADR-016/018 + `research_trials`; **ADR “Research Ledger”** → backlog futuro (no ahora) |
| H4 | MEDIA | Versionado científico completo | **Parcial** | `CampaignManifestV0` ya trae `git_commit`, engine, indicators, dataset window, costs ([campaign_manifest.py](../../packages/py/application/src/bolsa_application/campaign_manifest.py)). Falta **dataset hash** formal → backlog |
| H5 | MEDIA | Taxonomía CORE | **Aceptado** | Tabla CORE-P/R/A/B en Engineering Index §3 |
| H6 | MEDIA | Lab Health History 30d | **Aparcado** | Lab Health puntual OK; historial = horizonte (no Fase H) |
| H7 | MEDIA | Trazabilidad ADR↔código↔tests | **Forward-only** | Premisa docstrings; no reescribir histórico entero |
| H8 | MEDIA | ISSUES con impacto/prob/coste | **Aparcado** | ISSUES ya listan severidad; matriz formal = higiene futura |
| H9 | BAJA | CLI `research campaign …` | **Aparcado** | Scripts OK para research; orquestación unificada más adelante |
| H10 | BAJA | Docs por público | **Hecho** | Engineering Index §0 |

**Freeze C4:** el auditor lo celebra — **mantener**.

**Regla adoptada:** *toda dependencia nueva entre módulos se justifica en el PR* (bounded-contexts §4).

---

## 2. Auditoría N4 — Invariantes / CORE-R / FIE / smoke

### Lo que cuadra con el repo

| Tema | Estado real |
|------|-------------|
| Warm-up grid Q1.6 | `warmup_matrix.py` · `assert_grid_warmup` · gate de campaña |
| Estabilidad IBEX 13 same / 22 changed → C4 cerrado | Observation + freeze |
| CORE-R BD + LS cache · cron off | `core_r_account_state` · sync · `CORE_R_CRON_ENABLED=false` |
| Toast multi-dispositivo | Poll/hydrate + toast (v1.12), **no** Redis Pub/Sub SSE obligatorio |
| Yahoo CB + OHLCV quarantine + health | audit1-response · `yahoo_circuit_breaker` · quarantine |
| Score_FUND warnings/confidence | Ya F1; test cobertura parcial |
| Smoke `pnpm test:operativa` / coach / ibex 35/35 | audit-pack |

### Errata (sobre-especificación del informe)

| Afirmación N4 | Realidad |
|---------------|----------|
| Diagrama Redis Pub/Sub → SSE/WebSockets para CORE-R | Sync HTTP + toast remoto; Redis es best-effort health/cache, no bus de eventos CORE-R documentado así |
| `SELECT … FOR UPDATE` como garantía narrada | Upsert/estado en BD; no asumir locking de novela sin citar código |
| “Quarantine Vault” / FA ROE como etapa fija del mismo pipeline Yahoo | Cuarentena OHLCV ≠ vault; FA es pipeline fundamentals aparte |
| Fórmula Kendall_Tau formal en observation | Observation reporta same/changed; no exigir esa fórmula como verdad de repo |
| “Inmutable y sin ítems bloqueantes” | Estable para auditoría externa **con freeze**; deuda y Belief siguen aparcados a conciencia |

**Acción código:** ninguna en esta pasada (ya respondido en audit1/2 + freeze).

---

## 3. Auditoría Deep — Código / seguridad / rendimiento

### Errata de stack (crítica)

El informe cita artefactos **que no existen** en Bolsa_V1:

| Citado | ¿Existe? | Equivalente real (si aplica) |
|--------|----------|------------------------------|
| `packages/core/src/money.ts` | **No** | Dinero/precios en shared/DTOs + motor Python |
| `packages/market-data/.../yahoo-provider.ts` | **No** | `packages/py/market/.../yahoo_client.py` |
| `packages/engine/src/backtest-engine.ts` | **No** | `bolsa_analytics` / application backtests |
| `packages/risk/src/risk-engine.ts` | **No** | Policy Gate / risk en Python + TradingPolicy |
| `packages/api` tRPC + Drizzle | **No** | FastAPI + SQLAlchemy |
| Next.js 15 / tRPC 11 / Drizzle | **No** | Vite React + FastAPI |
| `yahoo-finance2` npm | **No** | Cliente HTTP Yahoo Python |
| Coberturas % inventadas (core 95%, api 45%…) | **No verificable** | No usar como KPI |

Tratar el Deep como **checklist genérico de plataforma cuant**, no como lectura de este árbol.

### Mapeo de “inmediatas 48h” al stack real

| # Deep | Pedido | En Bolsa_V1 |
|--------|--------|-------------|
| 1 | Validar HTML Yahoo | Parcial: status retryables + CB; endurecer parse HTML → **backlog bajo** si se ve en prod |
| 2 | Rate limit tRPC | **Ya existe** FastAPI `RateLimitMiddleware` (Q2.5) |
| 3–4 | Sanitize / validate LLM FA | Copiloto FA: guardrails parciales en roadmap; no reabrir Belief/Coach soft |
| 5 | Dev PIN middleware | App password / env ya; no copiar tRPC PIN |
| 6–10 | Split engine, cache RSI, DuckDB… | Horizonte / freeze — **no** |
| 11–20 | Alpaca, Risk 3 capas, OTel, microservicios… | Fase H / fuera — **no** |

### Riesgos Deep que **sí** guardamos (reformulados)

1. **Yahoo sigue siendo SPOF de mercado** — CB + quarantine mitigan; fallback Alpaca = futuro.  
2. **LLM prompt injection / alucinación** — Proxy + heurísticas; validación estricta de números = mejora incremental cuando se toque FA copiloto.  
3. **Resultados BT grandes en memoria** — monitorizar en uso real; sampling = backlog si duele.  
4. **toNumber / precisión** — solo si aparece tipo money branded; hoy no aplica el patch citado.

---

## 4. Priorización unificada (post round 2)

| Prioridad | Ítem | Estado |
|-----------|------|--------|
| P0 | Seguir operativa / pruebas humanas del Lab | **En curso (usuario)** |
| P0 | Mantener freeze C4 / Belief / flags | **Vigente** |
| P1 | Engineering Index + bounded contexts + CORE taxonomy | **Hecho (este PR)** |
| P2 | Dataset hash en campaign manifest | Backlog research |
| P2 | ADR “Research Ledger” unificado | Backlog (tras uso real) |
| P3 | Lab Health history 30d | Horizonte |
| P3 | CLI research unificado | Horizonte |
| — | Checklist Deep tRPC/Next | **Descartado** |

---

## 5. Mensaje para las 3 auditorías externas

1. Empezar por el [audit-pack](./audit-pack-post-audits-2026-08-03.md).  
2. Leer este triage si el informe menciona tRPC / `packages/engine` / Next — **errata de stack**.  
3. Arquitectura documental: navegar desde el [Engineering Index](./engineering-index-2026-08-03.md).  
4. No pedir Belief/C4/Risk-3/microservicios como “bloqueantes”: están **congelados a propósito**.

---

## 6. Ratificación

- [x] A0 H1/H2/H5/H10 documentados  
- [x] N4 espíritu aceptado + errata  
- [x] Deep marcado como parcial/N/A stack  
- [ ] Dataset hash / Research Ledger ADR — solo con brief futuro  
- [ ] Belief — [belief-coach-brief-draft](./belief-coach-brief-draft-2026-08-03.md) sin implementar
