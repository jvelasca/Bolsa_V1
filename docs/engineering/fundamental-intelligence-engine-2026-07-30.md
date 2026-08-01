# Fundamental Intelligence Engine (FIE) — diseño canónico (2026-07-30)

> Consolida **auditorías externas (ronda 1 + ronda 2 sobre este doc)** + arquitectura Bolsa V1.  
> Complementa [`fundamental-analysis-readiness-2026-07-30.md`](./fundamental-analysis-readiness-2026-07-30.md).

**Objetivo:** evaluación objetiva, reproducible y explicable de la calidad fundamental de una empresa, **desacoplando** el cálculo financiero de la interpretación mediante IA.

---

## 0. Principios arquitectónicos (bloqueados)

1. Toda métrica financiera debe poder reproducirse **únicamente con Python**.
2. Toda interpretación (LLM) debe poder **eliminarse** sin alterar el resultado numérico.
3. Ningún LLM modifica datos de mercado.
4. Ningún LLM escribe en la base de datos operacional.
5. Toda puntuación es **trazable** hasta sus variables originales (`refs` / facts).
6. **Gobernanza:** ninguna decisión de inversión automática puede depender exclusivamente de un componente generativo; solo de cálculos deterministas.

---

## 1. Tesis de producto

| Rol | Qué hace | Qué **no** hace |
|-----|----------|-----------------|
| **Filtro Fundamental** («qué») | Salud / calidad / valoración determinista → lista blanca o score | Señales de timing |
| **Disparo Técnico** («cuándo») | Embudo Coach / Lista AUTO / Finalistas | Sustituir FA |
| **LLM copiloto** | Explicar ratios, riesgos, Q&A sobre docs | Calcular ROE, DCF, Piotroski, Altman |

**Flujo UX (sin segundo Coach):**

```text
Universo → [Gate / Score FA] → Embudo técnico (Coach) → Finalistas
         → Composite Investment Score → Paper D (cuando F3)
```

**Regla de oro:** *nunca* dejar que un LLM haga aritmética financiera si Python puede hacerlo.

---

## 2. Qué ya existe (no reinventar)

| Pieza | Dónde |
|-------|--------|
| Cliente HTTP Primary Provider (Yahoo quoteSummary hoy) | `bolsa_market.yahoo_client` |
| Snapshot v3 (PE, mcap, ROE, márgenes, D/E, Altman Z, FCF, fcfYield…) | `bolsa_market.instrument_fundamentals` → `profile_snapshot.fundamentals` |
| Refresh single/batch + stale ~30d | `bolsa_application.refresh_instrument_fundamentals` |
| Gate scanner PE/cap/sector | `fundamentals-gate.ts` + `bolsa_analytics.signals.fundamental_gate` |
| Score_FUND ∈ [-1,1] + FundamentalAssessment | `bolsa_analytics.knowledge.*` (RFC-008 D5) |
| Ollama local | `bolsa_ai` — **no** puntuación FA |
| Universos listas/índices | Listas v1.0 cerradas |

**Ausente a propósito (v1):** yfinance, OpenBB, LangChain/CrewAI, Chroma/FAISS, SEC RAG, tabla SQL tipada de ratios.

---

## 3. Decisiones bloqueadas

| # | Decisión | Elección |
|---|---------|----------|
| 1 | FA vs Coach | **Capa** de scoring + filtro; **no** embudo Coach paralelo |
| 2 | Métricas v1 | Pack value snapshot v3 |
| 3 | Provider día 1 | **Primary Provider** = Yahoo quoteSummary (httpx). SEC / OpenBB / otros = swap de adaptador, no de arquitectura |
| 4 | UI primero | Panel **Valor** + chip Lista Backtesting |
| 5 | LLM | Solo explicación Ollama; F2b resumen/ask filing (no ratios); RAG = TF-IDF local F2b++ |
| 6 | Storage F0–F1 | JSONB versionado; tabla tipada = F2 si hace falta |
| 7 | Multi-agente | **No** en v1 |
| 8 | Piotroski | **Completo en F2** (YoY). No score parcial inventado en F1 (rigor > badge incompleto) |
| 9 | DCF / Graham | **F2.3** Graham · **F2.4** WACC sector · **F2.5** escenarios · **F2.6** CAPM (beta Yahoo) + ADV liquidez |
| 10 | Jerarquía de scores | Pilares → `Score_FUND` (ver §5); UI 0–100 vía `fundScoreToDisplay100` |
| 11 | Versionado | `sourceVersion` (datos) + `scoreVersion` (pesos/agregación) |
| 12 | Confidence | `HIGH` / `MEDIUM` / `LOW` según cobertura de inputs del score |
| 13 | Moat / Management | **Hueco conceptual** reservado; sin implementación hasta datos/modelo |

---

## 4. Arquitectura FIE (capas lógicas)

```text
Ticker / Lista
      │
      ▼
┌─────────────────────────────────────────┐
│  market · Primary Provider (ingesta)    │
│  Adaptador actual: Yahoo quoteSummary   │
│  (futuro: SEC, OpenBB, …)               │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  facts (lógico / Feature Store)         │
│  JSONB hoy · tipado mañana              │
│  Facts crudos + derived (Altman, …)     │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  analytics · scores                     │
│  Pilares → Score_FUND + scoreVersion    │
│  + confidence · Gate · Assessment       │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  application · Refresh / sync / API     │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  web · Panel FA + chip + Monitor        │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  ai · Copiloto (Ollama) — solo lee      │
│  facts/scores; NUNCA escribe BD         │
└─────────────────────────────────────────┘
```

`ai` **nunca** escribe ratios ni scores. Interpretación eliminable sin cambiar números.

---

## 5. Facts → Derived → Pilares → Score_FUND

Separación explícita (auditoría ronda 2):

```text
Facts (provider)
  ROE, ROA, márgenes, D/E, cash, growth, PE, FCF, sector, …
        │
        ▼
Derived metrics (Python)
  Altman Z (classic public), fcfYield, Piotroski, Graham Number, DCF FCF 2-stage
        │
        ▼
Pillar scores (deterministas, versionados)
  Value | Quality | Growth | Risk / Financial Strength
  (+ Management / Economic Moat — reservados)
        │
        ▼
Score_FUND  ∈ [-1, +1]     scoreVersion: fund_score_v1
        │
        ▼
UI display 0–100
```

**Hoy (F0/F1):** el Assessment/facts `fund.valuation|quality|growth|solvency|size` ya es el embrión de pilares; F1 expone el agregado + facts visibles. F2 formaliza pilares nombrados + pesos documentados + `scoreVersion`.

**Composite Investment Score (F3)** — no solo «TA+FA+perfil»:

```text
Composite Investment Score
  ├── Technical Score
  ├── Fundamental Score (Score_FUND)
  ├── Risk Profile
  ├── Liquidity
  ├── Market Regime
  └── Portfolio Constraints
```

Paper D solo tras F3 documentado y auditable.

---

## 6. Versionado y confidence

| Campo | Quién | Ejemplo |
|-------|--------|---------|
| `sourceVersion` | market / snapshot | `yahoo_quote_summary_v3` |
| `scoreVersion` | analytics | `fund_score_v1` |
| `confidence` | analytics al puntuar | `HIGH` / `MEDIUM` / `LOW` |

**Confidence (datos, no IA):** baja si faltan inputs clave del pilar (p. ej. sin FCF ni currentRatio, o Altman incompleto). La UI muestra badge; el gate puede exigir `confidence ≠ LOW`.

---

## 7. Catálogo de métricas (snapshot v3+)

### Valoración
`trailingPe`, `forwardPe`, `priceToBook`, `fcfYield`

- **`fcfYield`** = `freeCashflow / marketCap` (ratio, no %). Fuente Yahoo: FCF suele ser **TTM** vía `financialData.freeCashflow`; `marketCap` del summaryDetail en el mismo fetch. Si el precio se mueve fuerte y el snapshot es stale (~30d), un refresh recalcula yield con mcap actual del fetch — no usar precio intradía aislado sin re-fetch del pack.

### Calidad / rentabilidad
`roe`, `roa`, `operatingMargin`, `profitMargin`

### Crecimiento
`revenueGrowth`, `earningsGrowth`

### Solvencia / liquidez
`debtToEquity`, `currentRatio`, `quickRatio`, `totalCash`, `totalDebt`

### Derived
- **`altmanZ`:** fórmula **Altman Z-Score clásica (empresas públicas)**.  
  Método: `altman_z_classic_v1`. EBIT preferente de income statement; fallback documentado `financial_ebitda_proxy` (no es EBIT puro — UI/copiloto deben etiquetarlo).
- **`piotroski`:** F-Score 0–9 solo si los **9** criterios son computables (`piotroski_f_annual_v1`); si falta YoY/cashflow → `null` + `piotroskiMethod=null`. Sin scores parciales.
- **`grahamNumber` / `grahamUpside`:** Graham Number clásico `sqrt(22.5·EPS·BVPS)` (`graham_number_v1`). Upside = (Graham − price)/price; price = mcap/shares o PE×EPS. Null si EPS/BVPS ≤0.
- **`dcfEquityValue` / `dcfUpside`:** DCF FCF 2 etapas (`dcf_fcf_2stage_wacc_v1`): 5 años FCF×(1+g), g = revenueGrowth acotado [−5%, +15%] (default 5%), **r = WACC proxy sector** (`fund_wacc_sector_v1`; default 10% si sector desconocido), g_term=2.5% Gordon. Trata FCF como cash a equity (simplificación; no FCFF−net debt). Null si FCF≤0. = escenario **base**.
- **`dcfScenarios`:** F2.5 bear/base/bull (`dcf_scenarios_v1`); g±3pp · WACC±1pp.
- **`wacc` / `waccMethod`:** tasa descuento DCF: CAPM (`fund_capm_v1`) si hay beta Yahoo; si no, WACC sector.
- **`capmRf` / `capmErp`:** supuestos CAPM versionados (persistidos en snapshot/Tarjeta cuando `waccMethod=fund_capm_v1`); **no** son tasas live.
- **`beta` / `averageVolume` / `advUsd`:** F2.6 — inputs CAPM y liquidez Composite.
- **`roic` / `roicMethod`:** F2.7 — NOPAT/IC (`roic_nopat_ic_v1`); null si falta EBIT income o IC≤0.
- **`beneishM` / `beneishMethod`:** F2.8 — M-Score anual (`beneish_m_annual_v1`); null-if-incomplete.
- **Moat / Management:** reservados (sin campos hasta fase dedicada).

### Meta
`sector`, `marketCap`, `fetchedAt`, `sourceVersion` (+ en Assessment: `scoreVersion`, `confidence`)

### Aplazado
Sector bands ✅ F2.2. Graham ✅ F2.3. WACC ✅ F2.4. DCF escenarios ✅ F2.5. CAPM+ADV ✅ F2.6. ROIC ✅ F2.7. Beneish ✅ F2.8.

---

## 8. Fases de entrega

| Fase | Objetivo | Entregable |
|------|----------|------------|
| **F0** | Contrato & catálogo | ✅ Shared/Python v3 + fcfYield + este doc (principios ronda 2) |
| **F1** | Panel Valor | Tarjeta FA (facts + Score_FUND 0–100 + frescura + confidence); chip lista Backtesting |
| **F1b** | Copiloto | Prompt Ollama §10; solo facts/scores precalculados |
| **F2** | Gate rico + Piotroski + sector + valoración | **F2.0–F2.3** ✅ · **F2.4** ✅ WACC sector → DCF |
| **F2b** | Docs USA | ✅ Lite · ✅ EDGAR · ✅ **F2b++** RAG TF-IDF local (`filing_rag_tfidf_v1`; sin Chroma/FAISS) |
| **F3** | Composite Investment Score | ✅ Monitor `composite_score_v1` · desbloquea ingeniería Paper D |
| **F4** | Screener FA | ✅ `fund_screener_v1` · universo × gate → hits (+ lista snapshot opcional) |

**Notas F1 (auditoría ronda 2/3):**
- Stale 30d no oculta revalorizaciones bruscas: botón/refresh + `fetchedAt` visible; fcfYield del último fetch.
- Chip boceto: `[SYM] FUND 82 · ROE · D/E · Z · FCF% · conf.`

**Rechazado en F1:** Piotroski parcial (X/9) sin contrato de criterios — evita badge engañoso. Criterios sueltos visibles como facts sí; score Piotroski no.

---

## 9. Relación con auditorías (mapa)

| Idea | En Bolsa |
|------|----------|
| yfinance | Primary Provider HTTP propio |
| Ollama | Solo copiloto |
| CrewAI / multi-agente | No v1 |
| Feature store | Capa lógica facts (JSONB hoy) |
| Jerarquía pilares | §5; formalizar F2 |
| scoreVersion + confidence | §6; cablear en F1/F2 |
| Sector-normalized gate | F2 |
| PDF 10-K manual | F2b lite antes de RAG |
| OpenBB | Adaptador futuro |

---

## 10. Prompt base copiloto (F1b) — borrador bloqueado

```text
Eres un analista financiero. NO inventes ni recalcules números.
Usa SOLO el bloque [DATO REAL] siguiente.

[DATO REAL CALCULADO POR PYTHON - NO MODIFICAR NI RECALCULAR]
Empresa: {ticker} | Sector: {sector}
PE: {pe} | ROE: {roe} | Margen op.: {operatingMargin}
D/E: {debtToEquity} | Altman Z: {altmanZ} ({altmanLabel})
FCF Yield: {fcfYield} | DCF upside: {dcfUpside} | Graham upside: {grahamUpside}
Score_FUND: {scoreFund} [-1..+1]
Display: {score100}/100 | confidence: {confidence}
scoreVersion: {scoreVersion} | datos: {fetchedAt} ({sourceVersion})

[INSTRUCCIÓN]
En 3 párrafos cortos:
1) Puntos fuertes según esos datos.
2) Riesgos principales (endeudamiento / solvencia / valoración).
3) Qué mirar del sector ({sector}) sin inventar peers numéricos.
Si confidence es LOW, dilo en la primera frase.
Si DCF/Graham son "—", no inventes valor intrínseco.
```

---

## 11. Criterios F0 (cerrado)

- [x] Diseño FIE + principios §0.  
- [x] `sourceVersion` shared = `yahoo_quote_summary_v3`.  
- [x] `InstrumentFundamentalsV1` + `fcfYield` + tests.  
- [x] Ayuda / handoff track FA activo.  
- [x] Este doc actualizado con auditorías ronda 2 (jerarquía, confidence, provider, gobernanza, prompt).

**Pendiente pre-F1 (opcional spike):** fixture/doc de `fcfYield` con 1–2 tickers conocidos (discrepancia vs web externa documentada, no bloqueante).

---

## 12. F1 Contract Freeze (bloqueado al iniciar código)

Una vez iniciada F1:

- No se añaden nuevos ratios al snapshot.
- No se modifican pesos de `Score_FUND` (`fund_score_v1`).
- No se añaden pilares nuevos (solo mapear valuation→value, solvency→risk).
- No se cambian DTOs públicos `FundamentalCardDto` sin bump de fase.
- Solo bugs / wiring.

Toda mejora arquitectónica → RFC / F2.

### Entrega por PRs

| PR | Scope | Estado |
|----|-------|--------|
| **PR1** | Backend card + API + tests | ✅ |
| **PR2** | Tarjeta Valor + franja compacta wizard | ✅ `FundamentalCardPanel` |
| **PR3** | Chip lista Backtesting | ✅ `POST /instruments/fundamentals/query` + chip en Universo Lista |
| **PR4 / F1b** | Copiloto Ollama | ✅ `POST /api/ai/fundamentals/explain` + botón Copiloto |

### DTO público F1 (`FundamentalCardDto`)

```text
instrumentId, ticker
scoreFund [-1..1], scoreDisplay100 [0..100], distress
pillars: { value, quality, growth, risk }   // = ScoreFundResult.components
facts: todas las keys siempre presentes (null explícito)
derived: altmanZ (+method/source), fcfYield, piotroski (+method),
         grahamNumber/Upside (+method), dcfEquityValue/Upside (+method)
metadata: {
  provider, sourceVersion, scoreVersion,
  fetchedAt, staleDays, isStale,
  confidence: HIGH|MEDIUM|LOW,   // Python (inputs ∩ coverage; stale→LOW)
  coverage                     // 0..1 pesos pilares
}
narrativeFacts[]  // = claims / evidencias Score_FUND
warnings[]
```

**Fuera del DTO card:** `bias` (stance FUND sigue en Assessment cognitivo; no en UI card — evita confusión con sesgo técnico).

**Congelado post-refino auditorías:** `scoreDisplay100`, pilares value/risk, confidence en Python, facts con nulls.

---

## 13. Siguiente paso de ingeniería

1. ~~F1 completo (PR1–PR4).~~  
2. ~~**F2.0** gate rico (ROE, D/E, Altman Z, FCF yield, current, márgenes/growth) en scanner híbrido.~~  
3. ~~**F2.1** Piotroski completo (cashflow history + YoY; null si incompleto).~~  
4. ~~**F2.2** umbrales por sector (`fund_sector_bands_v1` + checkbox scanner).~~  
5. ~~**F2.3** Graham Number + DCF FCF 2 etapas (`valuation.py`; gate `dcfUpside`/`grahamUpside`).~~  
6. ~~**F2b lite** filings PDF/TXT en disco + resumen (`filing_store` / `prompt_filing_summary_v1`).~~  
7. ~~**F2b+** SEC EDGAR fetch (`sec_edgar.py` → mismo almacén; dedupe por accession).~~  
8. ~~**F2b++** indexación/RAG TF-IDF (`filing_rag.py` + `POST …/filings/ask`).~~  
9. ~~**F2.4** WACC proxy por sector (`fund_wacc_sector_v1` → `dcf_fcf_2stage_wacc_v1`).~~  
10. ~~**F3** Composite Investment Score (`composite_score_v1` · Monitor · Paper D unblocked).~~  
11. ~~**F4** Screener FA (`fund_screener_v1` · gate-only · whitelist opcional).~~  
12. ~~**Paper D** propose + execute (`paper_d_propose_v2` · Router paper_auto).~~  
13. ~~**Cron** semanal FA→D (`fa_weekly_pipeline_v1` · worker off-by-default).~~  
14. ~~**F2.5** DCF multi-escenario (`dcf_scenarios_v1` bear/base/bull).~~  
15. ~~**F2.6** CAPM (`fund_capm_v1`) + ADV liquidez (`adv_usd_v1`).~~  
16. ~~**F2.7** ROIC (`roic_nopat_ic_v1`).~~  
17. ~~**F2.8** Beneish M (`beneish_m_annual_v1`).~~  
18. ~~Verificar `pnpm test:fa`.~~  
19. **Fase actual (2026-07-31):** prueba APP + optimización — ver  
    [`fa-status-and-test-plan-2026-07-31.md`](./fa-status-and-test-plan-2026-07-31.md).

### Paper D — contrato propose/execute

```text
proposeVersion: paper_d_propose_v2
API: POST /api/paper-d/propose
Body: { universe, minScoreDisplay100?, execute?, executionPolicyId? }
Result: candidates[] + executeStatus + execution?{actions[]}
Execute:
  default dry_run
  execute=true sin PAPER_D_EXECUTE=1 → blocked_env
  execute=true + env + policy mode=paper_auto + entry_long
    → hits sintéticos (last_close) → ExecutionRouter (Gate cognitivo)
≠ Camino B radar · ≠ Camino C Supervisado
UI: Screeners → «Paper D (propose)»
```

### Cron FA→D — pipeline semanal

```text
pipelineVersion: fa_weekly_pipeline_v1
API manual: POST /api/paper-d/weekly-run
Worker: FA_WEEKLY_CRON_ENABLED=1 (default off)
  + FA_WEEKLY_UNIVERSE_LIST_ID
  ventana: viernes ≥ FA_WEEKLY_HOUR (Madrid; default 18)
  1× por weekKey (UTC ISO)
Flujo: Screener FA → whitelist snapshot → ProposePaperDPlan
Execute cron: FA_WEEKLY_EXECUTE=1 + PAPER_D_EXECUTE=1 + FA_WEEKLY_EXECUTION_POLICY_ID
UI: Screeners → «FA→D semanal»
```


### F4 — contrato Screener FA

```text
screenerVersion: fund_screener_v1
API: POST /api/instruments/fundamentals/screener
Body: { universe: {listId|instrumentIds}, fundamentalGate, refreshStale?, maxResults?, persist? }
Result: hits[] (pass gate) + skipped[] + weekKey (YYYY-Www)
Persist opcional: InstrumentList kind=snapshot (nombre «FA whitelist {week}»)
Reglas:
  - Solo gate FA (sin OHLCV / technical_rating / ruleGate)
  - Refresh stale Yahoo opcional (RefreshFundamentalsBatch)
  - UI: Screeners → panel «Screener FA (F4)»
  - Distinto del rastreador híbrido (timing)
```

### F3 — contrato Composite

```text
scoreVersion: composite_score_v1 · schemaVersion: composite_card_v1
API: GET /api/instruments/{id}/composite?horizon=&regime=
Piernas (scores [-1,+1] o null):
  technical     ← Score_TA (inputs) o technical_rating_v1 mapeado desde OHLCV
  fundamental   ← Score_FUND (snapshot Yahoo)
  riskProfile   ← stub (size_hint + veto + tolerancia)
  liquidity     ← ADV USD si hay (`adv_usd_v1`); si no, proxy marketCap
  marketRegime  ← WeightRules regime → score
  portfolioConstraints ← not_evaluated (stub)
Fusión: pesos WeightRules (TA/FUND/MACRO) + liquidez/perfil; renormaliza piernas presentes
metadata.paperDUnlocked=true → ranking auditable; no despliega paper automáticamente
UI: bloque Composite en Tarjeta Valor (Monitor)
Reglas: Python calcula; LLM no recalcula
```

### F2.4 — contrato WACC

```text
Catálogo: fund_wacc_sector_v1 (TS shared + Python wacc.py)
  Default 10% · overlays Yahoo sector (Tech 9.5%, Utils 6.5%, …)
  No CAPM (sin beta/rf/ERP vivos); cambiar tasas ⇒ bump versión
Snapshot/card derived: wacc, waccMethod
DCF method: dcf_fcf_2stage_wacc_v1 (r = wacc; g_term=2.5%)
Reglas: LLM no calcula WACC/DCF; null DCF si FCF≤0
```

### F2.5 — contrato DCF escenarios

```text
method: dcf_scenarios_v1
Snapshot/card derived.dcfScenarios: { method, bear, base, bull }
  cada pierna: { equityValue, upside, growth, wacc }
Deltas (versionados): growth ±3pp · WACC ±1pp (floor g_term+2pp)
dcfEquityValue / dcfUpside = escenario base (gate sin cambio)
UI: Tarjeta Valor — fila DCF bear/base/bull
Refresh Yahoo regenera escenarios (derived en snapshot)
```

### F2.6 — contrato CAPM + ADV

```text
CAPM: fund_capm_v1
  ke = rf + beta×ERP · rf=4% · ERP=5% (versionados)
  beta: Yahoo defaultKeyStatistics.beta (clamp [0.3, 2.5])
  Si beta OK → wacc/waccMethod = ke / fund_capm_v1 (descuento DCF)
  Si no → fund_wacc_sector_v1 (F2.4)
ADV: averageVolume × price → advUsd
  Composite liquidity v1.1: ADV buckets (mega ≥1B · very_high ≥100M · high ≥20M …) > mcap proxy
  Calibrado 2026-08-01 (US mega ≠ IBEX large; ACS ~51M → adv_high, no mega)
UI: Tarjeta Valor — Beta · ADV$ · r=CAPM|WACC · footnote `ke = rf + β×ERP` (rf/ERP versionados)
```

### F2.7 — contrato ROIC

```text
method: roic_nopat_ic_v1
ROIC = NOPAT / IC · NOPAT = EBIT×(1−t) · IC = equity + debt − cash
EBIT: solo income_statement (sin proxy EBITDA)
t: tax/pretax si usable; si no statutory 21% (roicTaxSource)
Null si falta input o IC≤0
Gate: minRoic (opcional) · Score_FUND quality ya consume roic
```

### F2.8 — contrato Beneish M

```text
method: beneish_m_annual_v1
8 índices YoY (DSRI…LVGI); TATA = (NI−CFO)/TA simplificado
Null-if-incomplete (como Piotroski)
Gate: maxBeneishM (típicamente −1.78; lte)
UI: Tarjeta Valor — Beneish M
```

### F2b / F2b+ / F2b++ — contrato

```text
Disco: BOLSA_FILINGS_DIR o ./data/filings/{instrumentId}/
  index.json + {filingId}.* + {filingId}.txt (extract)
  {filingId}.chunks.json   # F2b++ indexVersion=filing_rag_tfidf_v1
API:
  GET/POST/DELETE /api/instruments/{id}/filings
  POST /api/instruments/{id}/filings/sec-fetch?kind=10-K|10-Q
  POST /api/ai/fundamentals/filings/summarize
  POST /api/ai/fundamentals/filings/ask   # question → top-k chunks → LLM/heurística
EDGAR:
  ticker US (yahoo sin sufijo .MC/.PA/…) → company_tickers.json → CIK
  submissions → latest form → Archives primaryDocument
  User-Agent: BOLSA_SEC_USER_AGENT (requerido por SEC; 403 si falta contacto)
RAG:
  Chunks ~900c solape 120; TF-IDF coseno stdlib; sin Chroma/FAISS/embeddings
Reglas:
  - No escribe profile_snapshot.fundamentals
  - No altera Score_FUND / gate
  - LLM solo narra contexto recuperado; no inventa ratios
  - HTML SEC → texto stdlib; PDF: pypdf opcional; TXT siempre
  - Dedup por accessionNumber
```
