# Roadmap de mejoras — post-auditorías (laboratorio + producto)

> **AsOf:** 2026-08-02  
> **Fuente:** síntesis de 3 auditorías externas (lab C1–C3.5 · FIE/docs · observability/TOP) + estado real Bolsa_V1 (ADR-019/020/021, Lab WF/CPCV, FIE F1 parcial, stage-audit LAB/DÍA D/Mandato).  
> **Canvas vivo:** abrir junto al chat `improvement-roadmap-post-audits.canvas.tsx`  
> **No sustituye ADRs:** decide *orden de ejecución*; las decisiones de producto siguen en `docs/adr/`.

---

## 0. Principios (congelados por las auditorías)

1. **No C4** sin hipótesis científica nueva (no “toca otra familia”).  
2. **No Fase 2 Belief / Knowledge Nodes / Discovery Score** hasta que el laboratorio sea reproducible y temporalmente estable.  
3. **Calidad > cantidad de experimentos.** Primero sanidad, trazabilidad, estabilidad temporal.  
4. **IA solo narra / resume**; nunca decide ni inventa números (FIE §0).  
5. **Una pregunta → una campaña.** El ledger responde; no reescribe histórico.  
6. **Ya existe producto operativo** (Play, Finalistas, DÍA D, Mandato): el roadmap *no* lo deshace; lo endurece.

---

## 1. Mapa: qué dijo cada auditoría vs qué ya tienes

| Tema auditoría | Estado real Bolsa_V1 | Acción |
|----------------|----------------------|--------|
| Parar antes de C4 | Documentado en lifecycle + notebooks | **Mantener** |
| Informe C3.5 / ledger | `research_trials` + Observatory | Explotar + **lab health** |
| Warm-up MACD | En ISSUES; no reescribir K | **Auditar warm-up todas las familias** |
| Un solo periodo IS / 500 barras | Lab ya tiene hold-out/WF/CPCV en producto | **Metadatos dataset + campañas multi-ventana** |
| Versionado motor/campaña | Parcial (manifests, dataVersion backtests) | **Campaign manifest formal** |
| FIE F1 incompleto | `score_fund.py` existe (confidence/display); UI/API FA avanzados | Cerrar **gaps** (warnings, stale, chips) no “empezar de cero” |
| Observabilidad solo logs | Health API existe; sin OTel/redact formal | **Higiene** gradual |
| Walk-forward / robustez | Código Lab + tests | **Productizar** (mapas, multi-ventana) antes Monte Carlo |
| TOP: Strategy Studio / SOR / DuckDB | Horizonte | Solo tras gates Q0–Q2 |

---

## 2. Tracks paralelos (no secuencias ciegas)

```text
T1 Lab científico     ──► salud · manifiestos · estabilidad temporal · (¿C4?)
T2 FIE / Valor        ──► cerrar gaps F1 · no reabrir Belief
T3 Higiene plataforma ──► redact · health · rate limit · warm-up
T4 Producto LAB/TRAD  ──► pulir DÍA D · Mandato · CORE-R BD (ya avanzado)
T5 Horizonte TOP      ──► robustez UX · studio · risk 3 capas · (gated)
```

Trabajar **poco a poco**: cada slice = 1 PR con criterio de hecho + test/smoke.

---

## 3. Fases ejecutables

### Fase Q0 — Sanidad del laboratorio (1–2 semanas) ★ ahora

**Objetivo:** poder responder *¿está sano el laboratorio?* sin abrir C4 ni Belief.

| # | Entrega | Criterio de hecho | Esfuerzo |
|---|---------|-------------------|----------|
| Q0.1 | **Lab Health** panel/script | Cobertura Sharpe/Sortino/Calmar; % `tradeCount=0`; campañas; instrumentos con/sin cobertura | S |
| Q0.2 | **Campaign manifest v0** | Por campaña: `git commit`, engine/indicadores version, universo, TF, costes, `dataset_start/end`, `bar_count` | S |
| Q0.3 | **Warm-up audit** | Matriz SMA/EMA/RSI/MACD/Bollinger/ADX/ATR: barras mínimas; doc en ISSUES; tests smoke | S |
| Q0.4 | Doc limitación ranking | Cross-family: Sharpe mediano ≠ verdad; tradeCount/Calmar como *caveat* en C3.5 / HELP | XS |

**No hacer en Q0:** nuevas familias, Belief, OTel completo, DuckDB.

---

### Fase Q1 — Reproducibilidad + estabilidad temporal (2–4 semanas)

**Objetivo:** dejar de extrapolar desde *un* experimento temporal.

| # | Entrega | Criterio de hecho | Esfuerzo |
|---|---------|-------------------|----------|
| Q1.1 | Metadatos en cada trial/campaña | `dataset_start`, `dataset_end`, `bars`, `market_regime?` (heurística simple o null) en blocks/manifest | M |
| Q1.2 | **Campañas de estabilidad** | Repetir protocolo C3-like en ≥2 ventanas (p. ej. 2022–23 vs 2024–25) *sin* nueva familia | M |
| Q1.3 | Informe estabilidad | ¿Mismos “fuertes/débiles” por activo? Δ ranking documentado (notebook + Observatory) | M |
| Q1.4 | `family.yaml` formal | SMA/RSI/MACD: hipótesis, pregunta, presets, grid, variables, espacio explorado vs teórico | S |
| Q1.5 | Separar **K científico** vs **CPU cost** | Campo opcional `cpu_cost_units` (no cambia ledger K) | S |
| Q1.6 | Gate cierre campaña | Checklist automática: métricas mínimas, warm-up OK, manifest completo, % zero-trades bajo umbral | M |

**Gate C4:** solo si Q1.3 + hipótesis escrita (ej. Bollinger rompe patrón de fortaleza por activo).

---

### Fase Q2 — Cerrar FIE F1 + higiene seguridad (en paralelo a Q1)

**Objetivo:** diseño FIE ya congelado → ejecución coherente; labs seguros.

| # | Entrega | Criterio de hecho | Esfuerzo |
|---|---------|-------------------|----------|
| Q2.1 | Warnings + confidence + freshness | `ScoreFundResult` warnings; confidence = f(coverage, stale, provider) | S |
| Q2.2 | Validación OHLCV frontera | `high≥low`, OHLC coherente, volume≥0; rechazar/quarantine | S |
| Q2.3 | Health components | `/api/health` detalla DB + (best-effort) Yahoo/XTB degradado | S |
| Q2.4 | Redact logs | Pino/Python: authorization, apiKey, password; no loguear payloads broker | S |
| Q2.5 | Rate limit API sensibles | fundamentals / AI / sync; 429 documentado | S |
| Q2.6 | Guardrails copiloto FA | sanitize query; validar que no inventa ROE vs facts | M |
| Q2.7 | UI Tarjeta/chip FA gaps | Solo lo que falte vs fa-status (no rehacer FIE) | M |

**No hacer en Q2:** sector thresholds (F2), feature store, sentiment multi-source.

---

### Fase Q3 — Robustez de producto (investigación usable)

**Objetivo:** lo que el Lab ya calcula, hacerlo **visible y comparable**.

| # | Entrega | Criterio de hecho | Esfuerzo |
|---|---------|-------------------|----------|
| Q3.1 | Robustness map UI | Heatmap vecindario params (no solo best point) | M |
| Q3.2 | Multi-ventana en embudo | DÍA D + WF ya existen; unificar copy + informe “estabilidad” en Coach/Finalistas | M |
| Q3.3 | Comparación masiva v1 | Lista × estrategias × TF (límites soft-cap) → ranking + heatmap | M |
| Q3.4 | CORE-R cola en BD | Multi-dispositivo (pendiente ISSUES) | M |
| Q3.5 | Costes realistas v2 | Slippage volumen / spread tip (config); paper hiperrealista gate | M |

---

### Fase H — Horizonte TOP (solo con gates)

Abrir **solo** si Q0–Q1 hechos y hay demanda explícita:

| Capacidad | Gate | Notas |
|-----------|------|-------|
| Monte Carlo trades | Q1.3 | No antes de estabilidad temporal |
| Strategy blocks (regime→setup→exit) | ADR dedicado | Diferenciador; no mezclar con presets actuales |
| Strategy Studio visual | Tras blocks | Unreal-like; alto coste |
| DuckDB / feature store | Universo > umbral | Acelerar, no cambiar ciencia |
| Risk 3 capas + kill-switch | Antes de live broker | Obligatorio pre-live |
| SOR / venues | Live multi-broker | Después paper realista |
| OTel + Prometheus + Grafana | Volumen logs | Tras redact + sampling market-data |
| Marketplace interno estrategias | Madurez biblioteca | Git-like versions |
| Sentiment pipeline | FIE gobernanza | Tras guardrails |

---

## 4. Orden recomendado de PRs (poco a poco)

1. `lab-health-v0` — script + panel mínimo Observatory  
2. `campaign-manifest-v0` — schema + escritura en cierre campaña  
3. `warmup-audit` — matriz + tests  
4. `ohlcv-validate` + `log-redact` — higiene  
5. `fund-confidence-freshness` — FIE gap  
6. `stability-campaign-protocol` — doc + 1 corrida notebook  
7. `family-yaml` — SMA/RSI/MACD  
8. `robustness-map-ui` — Lab  
9. (opcional) hipótesis C4 Bollinger **solo** si Q1.3 lo pide  

---

## 5. Anti-objetivos (explícitos)

- No añadir ADX/ATR/Stoch/Ichimoku “porque faltan”.  
- No reescribir K de C1–C3.  
- No auto-adoptar Finalistas / auto-paper.  
- No LLM que proponga campañas sin Gate humano.  
- No confundir score de grid interno con ranking científico cross-family.

---

## 6. Métricas de éxito del roadmap

| Señal | Verde |
|-------|--------|
| Lab health | % zero-trades y cobertura Sortino/Calmar visibles y estables |
| Reproducibilidad | Cualquier campaña C* se re-ejecuta con manifest → mismos hashes |
| Temporal | Ranking activos C3.5 vs ventana-B documentado (acuerdo o drift) |
| FIE | Confidence refleja stale; sin score “neutro” silencioso sin warning |
| Seguridad | Secrets no aparecen en logs de smoke |
| Producto | DÍA D / Mandato / Finalistas no regresan (test:operativa) |

---

## 7. Relación con docs vivos

- Auditoría etapa reciente: [stage-audit-lab-dia-d-mandate-2026-08-02.md](./stage-audit-lab-dia-d-mandate-2026-08-02.md)  
- Lifecycle / C4 gate: [research-lifecycle.md](./research-lifecycle.md)  
- Deuda lab: [research/observations/ISSUES.md](../../research/observations/ISSUES.md)  
- FIE: [fundamental-intelligence-engine-2026-07-30.md](./fundamental-intelligence-engine-2026-07-30.md)  
- FA status: [fa-status-and-test-plan-2026-07-31.md](./fa-status-and-test-plan-2026-07-31.md)

---

*Siguiente paso operativo sugerido: empezar Q0.1 (Lab Health) en un PR pequeño.*

---

## 8. Estado de ejecución (2026-08-02 · “vamos con todo”)

| Ítem | Estado |
|------|--------|
| Q0.1 Lab Health API/UI/script | Hecho — `GET /api/research/lab-health`, Observatory, `lab_health_report.py` |
| Q0.2 Campaign manifest v0 | Hecho — `campaign_manifest.py` + plantilla `research/campaigns/` |
| Q0.3 Warm-up audit | Hecho — `warmup_matrix` + tests + script |
| Q0.4 Caveat Sharpe | Hecho — C3.5 notebook + Lab Health caveat + HELP |
| Q1.1 Dataset metadata | Hecho (trials human) — `dataset_metadata` en `RunAndSaveBacktest` |
| Q1.2–Q1.3 Estabilidad multi-ventana | Protocolo + filter + Δ + `stability_windows_smoke.py` (limit pequeño) |
| Q1.4 family.yaml | Hecho — SMA/RSI/MACD |
| Q1.5 cpu_cost_units | Hecho (campo opcional en manifest; no altera K) |
| Q1.6 Gate cierre campaña | Hecho — `campaign_close_gate.py` · RSI campaign wire manifest/fechas |
| Q2.1 Confidence/stale/warnings | Hecho (card + provider) |
| Q2.2 OHLCV intradía | Hecho (quarantine barras incoherentes) |
| Q2.3 Health components | Hecho |
| Q2.4 Log redact | Hecho |
| Q2.5 Rate limit | Hecho (middleware in-memory) |
| Q2.6 FA guardrails ROE | Hecho (fallback heurístico si inventa) |
| Q2.7 UI chips FA | Parcial — ya existían; sin rehacer FIE |
| Q3.1 Robustness map | Label Lab heatmap (mapa ya existía) |
| Q3.3 Comparación masiva | Hecho — UI panel + `mass_compare_list.py` (soft-cap 40×8 / 120 celdas) |
| Q3.4 CORE-R BD | Hecho — blob + sync + **cron servidor** (`CORE_R_CRON_ENABLED`, off-by-default) |
| Q3.5 Costes v2 | Hecho (gated) — `COST_MODEL_V2_ENABLED=false` por defecto; wire en `run_backtest` |
| Fase H | No abierta |

**No hecho a propósito:** C4, Belief Fase 2, OTel, DuckDB, Monte Carlo, Strategy Studio.