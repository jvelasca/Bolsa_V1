# Triage — Auditorías institucionales (pre-AUTO) — 2026-08-04

> **Propósito:** contrastar las **Auditorías 1 y 2** (base + ampliaciones 1–4) con el **código/docs reales** de Bolsa_V1; decidir qué se adopta **antes de Camino D**, qué es **backlog institucional**, qué **ya existe**, y qué es **sobre-especificación / no aplica**.  
> **AsOf:** 2026-08-04 · branch `stage/estudio-membership-operativa-2026-08-04` · PR [#29](https://github.com/jvelasca/Bolsa_V1/pull/29)  
> **Padres:** [engineering-index](./engineering-index-2026-08-03.md) · [freeze](./post-audit-decision-freeze-2026-08-03.md) · [pack Canales](./audit-pack-estudio-asesor-canales-2026-08-04.md) · [thaw AUTO](./camino-d-auto-thaw-checklist-2026-08-04.md) · [ADR-022](../adr/022-estudio-daily-opinion-motor.md)  
> **Premisa:** no implementar 60+ ítems; **priorizar Operational Readiness** antes de execute AUTO. Sin reabrir Belief / C4 / `CORE_R_CRON` / Strategy Studio / `COST_MODEL_V2` on-by-default.

---

## 0. Resumen ejecutivo

| Fuente | Naturaleza | Veredicto |
|--------|------------|-----------|
| **Aud 1** (CTO / institutional) | Reproducibilidad, ledger hash, OR, entropía | **Espíritu ACEPTADO** · mucho ya parcial · resto = roadmap años |
| **Aud 2** (seguridad / finanzas / IA / ops) | Auth, RCE, race, Decimal, ErrorBoundary, IA sanitize | **Verificar en código** · varias hipótesis **falsas o parciales** |
| **Ampliaciones 1–4** | 67+ capacidades institutional-grade | **Catálogo de valor** · **no** checklist de sprint |

**Veredicto producto (2026-08-04):**

1. Canales / SEMI / pack pre-AUTO siguen **PASS condicional** ([pack §8](./audit-pack-estudio-asesor-canales-2026-08-04.md)).  
2. Camino D **sigue freeze**.  
3. Siguiente código: **A0 telemetría dictamen** + arranque **Operational Readiness (OR-*)** del thaw checklist — **no** blockchain ledger ni Monte Carlo ni OTel ahora.  
4. Abrir **backlog institucional** (este doc §5) sin contaminar el freeze.

---

## 1. Evidencia rápida vs claims críticos (Aud 2)

| Claim auditor | Evidencia repo | Veredicto |
|---------------|----------------|-----------|
| Auth JWT con expiración por ruta | Token = SHA256 estático (`auth/tokens.py`); middleware global; **no** JWT con TTL | **Parcial** — endurecer auth = multiusuario futuro; no inventar Depends JWT ahora |
| RCE vía `eval`/`exec` en indicadores | **0 matches** `eval(`/`exec(` en `packages/py` | **No aplica hoy** — no refactor AST “contra un fantasma” |
| Race en paper / portfolio sin locks | Paper D gated `PAPER_D_EXECUTE`; `FOR UPDATE` en jobs índice, no ledger cash genérico | **Aceptar riesgo** pre-AUTO · OR-idempotencia + transacciones = **OR-T4/T6** thaw |
| Float vs Decimal en dinero | `paper_d_propose.py` usa `float(...)` en precios | **Aceptado backlog OR** (pri Media-Alta antes de live; no bloquea SEMI DEMO) |
| Error Boundaries React | **No** `ErrorBoundary` / `errorElement` en web | **Aceptado** — P2 UI (no bloquea AUTO prep) |
| Campaign fingerprint / git / costs | `CampaignManifestV0`: git_commit, engine, indicators_version, costs, dataset window (`campaign_manifest.py`) | **Parcial** — falta hash chain trial, pip freeze, dataset SHA formal |
| Fingerprint barras | `fingerprint_bars` / `compute_data_version` en analytics + backtests | **Ya existe** base |
| Kill switch / shadow / reconcile broker | Congelado Camino D; checklist thaw P7/T* | **Aceptado** como **OR pre-execute** |
| LLM → sizing directo | RFC-008 + Coach “no corona TOP”; Belief freeze | **Alineado** — no reabrir Belief; sanitize prompt = P2 cuando LLM toque dinero |

---

## 2. Mapa Aud 1 — qué adoptar / aparcar

### 2.1 Adoptar *espíritu* → anclar en thaw / A0 (ahora–próximo)

| # Aud | Tema | Acción Bolsa |
|-------|------|--------------|
| OR / §prep AUTO | Kill switch, límites, idempotencia, shadow, reconcile | Ya en [camino-d-auto-thaw-checklist](./camino-d-auto-thaw-checklist-2026-08-04.md) P7–T8 · **no flip** hasta ✅ |
| Fingerprint / reproducibilidad | Manifest + versiones | Extender **CampaignManifest** (dataset SHA, feature_flags snapshot) = **A0-adjunto / Q0+** |
| Invariantes runtime | cash≥0, Sharpe finite… | Ampliar gates existentes (warm-up, campaign close) · no “cientos” de golpe |
| Explainability decisión | Dictamen → reasons → Confirm | **Parcial:** `InstrumentDailyOpinion.reasons` + cola F3 origen · Decision Replay = backlog |
| Complejidad arquitectónica | Bounded contexts / Index | **Ya:** [bounded-contexts](./bounded-contexts-2026-08-03.md) · Index · medir entropía = P3 |

### 2.2 Backlog institucional (valioso · **no** sprint AUTO)

Hash-chain ledger · Confidence decay · Research Domain isolation · Canary Research · Golden Master / mutation testing · Chaos / disaster sim · Monte Carlo infra · OTel · ADR ejecutables · Trust Score · Decision Diff · Safety Case · Supply-chain CI (gitleaks) · Capacity model · Cross-provider validate · Hexagonal audit automática · …

Catálogo completo: §5.

### 2.3 Errata / sobre-alcance

| Afirmación | Realidad |
|------------|----------|
| “auth/tokens.py cifrado JWT por ruta” | Token = SHA256(password+secret) sin TTL; middleware global; sin `APP_PASSWORD` = API abierta |
| “workers evalúan scripts de usuario con eval” | Indicadores versionados en código; sin eval dinámico hallado |
| “WebSocket/SSE obligatorio en dock” | Mucho es HTTP poll / toast (CORE-R, Alarmas); no inventar bus |
| “Redis cache bleed multi-tenant” | App mono-operador hoy; prefs localStorage; Redis best-effort |
| Blockchain ligero trial **antes** de SEMI estable | Deseable a 12–24m; **no** gate de A0 |

---

## 3. Mapa Aud 2 — capas

| Capa | Hallazgos útiles | Acción |
|------|------------------|--------|
| Seguridad API | Auth off-by-default en dev | Doc ONBOARDING + ops: exigir `APP_PASSWORD` en cualquier demo compartida (**OR-S1**) |
| Concurrencia paper | Transacciones / idempotencia execute | Thaw T4/T6 |
| RCE indicadores | — | Cerrado (no eval) |
| Slippage / look-ahead | COST_MODEL_V2 flag-off; warm-up gate | Mantener freeze costes; Lab A/B solo con brief |
| IA governance | Sanitize + tope sizing | Forward-only al tocar LLM money paths |
| Workers silent fail | Heartbeat / failed-job notify | P2 ops (email admin / toast) |
| Decimal money | Migrar paper path a Decimal | OR-P2 antes de live broker |
| Frontend leaks / ErrorBoundary | Cleanup charts + boundary shell | P2 |
| Secrets CI | gitleaks en Actions | P2 supply-chain |
| Data quality score | Quarantine + Lab Health ya | Extender score A–D = P3 |

---

## 4. Prioridad de implementación (orden producto)

> Alineado con la recomendación final de Aud 1 ampl.4 — **sin** abrir execute.

| Orden | Épico | Incluye | No incluye |
|-------|-------|---------|------------|
| **0** | Cierre Canales (hecho) | Toast, prefs email, pack §8 | — |
| **1** | **A0 telemetría dictamen** | Precisión/recall proxy, conteos días | Flip `PAPER_D_EXECUTE` |
| **2** | **OR-lite + OR-RE** | Kill switch, Decimal paper, idempotencia, **Risk Engine façade** (Gate/mandato/maxOpen unificados) | Broker live directo |
| **3** | **Repro+** | dataset SHA + feature_flags + trial payload_hash | Blockchain ledger |
| **4** | Observabilidad / CI | Heartbeat, gitleaks, ErrorBoundary | OTel/Prometheus full |
| **5** | Institutional + stats avanzadas | Hash-chain, SPA/WFO, Monte Carlo, Safety Case… | Hasta demanda explícita |

**Regla:** cualquier ítem §5 que no esté en 1–4 requiere frase de producto («implementa X»).

---

## 5. Catálogo institucional (referencia · aparcado)

Agrupado para no perder valor de las ampliaciones. **No** es TODO de ingeniería inmediata.

| Familia | Ítems Aud (aprox.) | Notas |
|---------|-------------------|-------|
| **Integridad científica** | Hash chain trials, fingerprint absoluto, pip freeze, golden master, mutation, anti-lookahead auto, bias detector, research domains, confidence half-life | Extiende CampaignManifest / ledger |
| **OR / AUTO** | Kill switch, circuit breakers, shadow, reconcile, black box, disaster sim, latency budget, capacity | Gate thaw |
| **Observabilidad** | OTel, heartbeats, LAB REPORT PDF, project observatory, perf budget CI | Tras OR-lite |
| **Arquitectura** | Contratos capas, hexagonal audit, anti-entropía PR, ADR coverage, semantic versions científicas | Bounded contexts ya |
| **Dinero / precisión** | Decimal, portfolio domain, broker simulator, Monte Carlo robustez | Pre-live |
| **Datos** | Provenance ETL, quality A–D, calendar engine, cross-provider | Yahoo SPOF conocido |
| **IA** | Sanitize prompts, no raw series, Pydantic caps | RFC-008 |
| **Frontend** | ErrorBoundary, chart destroy, no compute en UI | P2 |
| **Supply chain / DevOps** | gitleaks, pin deps, migration metadata, failover modes | P2–P3 |

---

## 6. Respuestas a las preguntas de los auditores

| Pregunta | Respuesta Bolsa |
|----------|-----------------|
| ¿Profundizar seguridad rutas API? | Middleware global OK; endurecer **APP_PASSWORD** en demos; multiusuario después |
| ¿AST indicators / Decimal / chart cleanup ahora? | **Decimal + ErrorBoundary** en OR-lite/P2; AST **no** (no hay eval) |
| ¿Blockchain ledger / Decision Replay antes de AUTO? | **No** — A0 + OR-lite primero |
| ¿Fases A–H institutional audit full? | Sí como **programa**; este triage es la puerta; no una pasada de 300 hallazgos en un PR |

---

## 7. Actualizaciones de docs hechas con este triage

| Doc | Cambio |
|-----|--------|
| Este triage | **Creado** |
| [camino-d-auto-thaw-checklist](./camino-d-auto-thaw-checklist-2026-08-04.md) | + enlace OR-lite / este triage |
| [audit-pack-estudio-asesor-canales](./audit-pack-estudio-asesor-canales-2026-08-04.md) | + §9 enlace |
| [freeze](./post-audit-decision-freeze-2026-08-03.md) | + nota auditorías institucionales |
| [engineering-index](./engineering-index-2026-08-03.md) | + entrada §5 |
| [docs/README](../README.md) | + fila triage |

---

## 8. Mensaje a las auditorías

Gracias. El nivel CTO / institutional es el correcto **como horizonte**. Contrastado con el monorepo:

- Varias amenazas (RCE eval, Depends-por-ruta, Redis multi-tenant) **no se sostienen** en el código actual.  
- La línea de valor real coincide con la vuestra: **Operational Readiness + reproducibilidad + trazabilidad de decisión** antes de dinero real.  
- Bolsa_V1 **no** abrirá Camino D por presión de checklist; A0 métricas + OR-lite + freeze amend siguen siendo el camino.

---

## 9. Cierre Aud 1 — 15 riesgos + Risk Engine + 4 pilares (2026-08-04)

> Valoración **antes** de A0. No diluye el PASS Canales; **reordena** lo imprescindible pre-€ real.

### 9.1 Los 15 riesgos → prioridad Bolsa

| # | Tema auditor | Estado repo | Acción |
|---|--------------|-------------|--------|
| 1 | Versionado algoritmo (hashes en trial) | Manifest parcial (git/engine/costs) | **Repro+** (épico 3) — hashes formales |
| 2 | Dataset fingerprint 100% | Metadata + bar fingerprint parcial | **Repro+** · no bloquea A0 |
| 3 | Trazabilidad git/python/lock en ledger | `git_commit` en manifest | Extender dirty/py/lock en Repro+ |
| 4 | Execution simulator (delay/partial) | Paper paths básicos | **Backlog OR** pre-broker live |
| 5 | Motor órdenes estados | Pending orders parcial | Diseño Camino D · no inventar OMS completo ahora |
| 6 | Portfolio Engine correlaciones | maxOpen + mandato; sin correlaciones | **Risk Engine** (ver 9.2) · portfolio domain P3 |
| 7 | Market regime id | No | Backlog científico |
| 8 | Drift PSI/KL | No | Post-meses DEMO |
| 9 | Tests estadísticos (SPA/WFO) | Warm-up + stability IBEX | Lab; **no** gate Camino D DEMO |
| 10 | Stress test botón | No | OR / disaster sim backlog |
| 11 | Decision Trace | reasons + Confirm origen | Ampliar en DecisionSession (OR-T6) |
| 12 | Lab quality indices | Lab Health | Extender P3 |
| 13 | Prometheus | No | Épico 4 |
| 14 | Secrets Vault / JWT TTL | Auth SHA256 demo | Multiusuario + OR-S1; Vault pre-prod |
| 15 | Capa AUTO desacoplada Lab→Risk→Broker | SEMI Confirm; Camino D freeze | **Obligatorio** antes execute · = Risk Engine + checklist |

### 9.2 Risk Engine independiente — **imprescindible pre-€**

El auditor eleva esto por encima del resto. **De acuerdo**, con matiz:

| Ya existe (disperso) | Falta |
|----------------------|-------|
| `TradingPolicy` / Gate long-only | Fachada única **Risk Engine** que Camino D **debe** llamar |
| Libro DEMO maxOpen / size% | Max pérdida diaria / DD / horario / liquidez / broker up |
| Mandato tenure | Duplicidad orden + stop obligatorio |
| SEMI Confirm humano | Kill switch &lt;1s + shadow mode |

**Decisión:** no construir el Risk Engine completo **antes** de A0 (necesitamos métricas). Sí:

1. A0 telemetría (medir dictamen). **Hecho.**  
2. **OR-RE v0:** `bolsa_application.risk_engine.check_opening` → ALLOW|DENY; envuelve Gate; kill switch + book maxOpen; **ExecutionRouter** ya llama.  
3. Ampliar checks (DD diario UI, mandato pre-trade, stop obligatorio) en OR-lite / A3.  
4. **Prohibido:** Research/dictamen → Broker sin Risk Engine.

### 9.3 Cuatro pilares → mapeo épicos

| Pilar auditor | Épico Bolsa |
|---------------|-------------|
| Reproducibilidad absoluta | **3 Repro+** |
| Validación estadística avanzada | Lab backlog (9, 10) · **no** bloquea DEMO AUTO |
| Motor riesgo + ejecución desacoplado | **2 OR-lite + OR-RE** · checklist thaw |
| Observabilidad continua | **4** Prometheus/heartbeats |

### 9.4 Orden actualizado (producto)

| # | Épico | Nota |
|---|-------|------|
| 1 | **A0** telemetría dictamen | Ahora |
| 2 | **OR-lite + OR-RE** (Risk Engine façade) | Antes de A2 execute |
| 3 | **Repro+** hashes/fingerprint | Paralelo OK tras A0 |
| 4 | Observabilidad CI | |
| 5 | Catálogo §5 + stats avanzadas | Demanda explícita |

*Fin §9.*
