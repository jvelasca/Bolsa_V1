# FA / FIE — estado general y plan de prueba (2026-07-31)

> Resumen operativo tras cerrar el track de valoración FIE (F0–F2.8 + F3/F4 + Paper D + cron).  
> Canónico: [`fundamental-intelligence-engine-2026-07-30.md`](./fundamental-intelligence-engine-2026-07-30.md).  
> Ayuda UI: **Ayuda → Análisis del valor** (`HELP_CONTENT_AS_OF`).

---

## 1. Estado en una frase

**Python calcula** ratios, scores y gates; **LLM solo explica**. El embudo FA («qué») alimenta whitelist/Composite/Paper D; el timing técnico («cuándo») sigue en Coach/Screeners.

---

## 2. Inventario entregado

| Área | Versión / contrato | Dónde se ve / se usa |
|------|--------------------|----------------------|
| Snapshot Yahoo v3+ | `yahoo_quote_summary_v3` | `profile_snapshot.fundamentals` |
| Score_FUND | `fund_score_v1` · pilares value/quality/growth/risk | Tarjeta Valor · Assessment |
| Card UI | `fund_card_v1` · `scoreDisplay100` | Monitor / Valor |
| Gate FA | métricas + sector bands `fund_sector_bands_v1` | Scanner híbrido · Screener FA |
| Piotroski | `piotroski_f_annual_v1` (null si incompleto) | Snapshot · gate |
| Graham / DCF | `graham_number_v1` · `dcf_fcf_2stage_wacc_v1` | Snapshot · gate upside |
| WACC sector | `fund_wacc_sector_v1` | Descuento DCF (fallback) |
| DCF escenarios | `dcf_scenarios_v1` bear/base/bull | Tarjeta Valor |
| CAPM | `fund_capm_v1` (beta Yahoo; rf/ERP versionados · `capmRf`/`capmErp` en Tarjeta) | Preferido sobre WACC si hay beta |
| ADV liquidez | `adv_usd_v1` | Pierna Composite liquidity |
| ROIC | `roic_nopat_ic_v1` | Snapshot · quality Score_FUND · gate |
| Beneish M | `beneish_m_annual_v1` · hard-limit Score_FUND si M > −1.78 | Snapshot · gate `maxBeneishM` · distress |
| Filings | disco + SEC EDGAR + TF-IDF ask | Tarjeta Valor · **no** Score_FUND |
| Composite | `composite_score_v1_1` · etiquetas liquidez UI | Tarjeta Valor · ranking Paper D |
| Screener FA | `fund_screener_v1` | Screeners → whitelist snapshot |
| Paper D | `paper_d_propose_v2` | Propose + execute Router (`PAPER_D_EXECUTE`) |
| Cron FA→D | `fa_weekly_pipeline_v1` | Worker off (`FA_WEEKLY_CRON_ENABLED`) |

---

## 3. Mapa UX (APP)

```text
Backtesting → Valor / Monitor
  · Tarjeta FA (facts + derived + Composite + filings + copiloto)
Screeners
  · Screener FA (F4) → whitelist
  · Paper D (propose ± execute)
  · FA→D semanal (manual; cron opcional)
Ayuda → Análisis del valor
  · Estado · capas cognitivas · Replay · pesos · BD · checklist prueba
```

---

## 4. Env / gates operativos

| Variable | Default | Efecto |
|----------|---------|--------|
| `PAPER_D_EXECUTE` | off | Permite execute paper vía Router |
| `FA_WEEKLY_CRON_ENABLED` | false | Worker viernes Madrid |
| `FA_WEEKLY_UNIVERSE_LIST_ID` | — | Universo fuente del cron |
| `FA_WEEKLY_EXECUTE` | false | Cron pide execute (sigue necesitando `PAPER_D_EXECUTE`) |
| `BOLSA_SEC_USER_AGENT` | — | Fetch SEC EDGAR |
| `python-multipart` | dep API | Upload filings |

---

## 5. Verificación automatizada

```bash
pnpm test:fa          # battery: units + operativa + bench + boot + smoke API
pnpm test:fa:ops      # operativa offline + micro-bench eficiencia
pnpm test:fa:boot     # import API + rutas FA; health live (SKIP si down)
pnpm doctor / pnpm health
pnpm --filter @bolsa/shared build
```

### Presupuestos bench (`verify_fa_pipeline_bench.py`)

| Paso | Budget avg |
|------|------------|
| snapshot Yahoo sintético | ≤ 25 ms |
| fundamental card | ≤ 15 ms |
| composite | ≤ 20 ms |
| screener ×50 | ≤ 80 ms |
| weekly pipeline (fakes) | ≤ 50 ms |

### Prep datos live (antes de checklist manual)

```bash
pnpm audit:fa:coverage   # refresh Yahoo 8 tickers + % cobertura FA
```

Notas (2026-07-31): Yahoo `balanceSheetHistory` llega vacío → se rellena vía `fundamentals-timeseries`. Bancos (SAN/BBVA) suelen quedar sin Piotroski/Beneish/Altman (null-if-incomplete). Handshake crumb: `fc.yahoo.com` → getcrumb.

Arranque APP: `pnpm dev` → `scripts/run-dev.mjs` (DB → free ports → shared build → API :8000 → web :5173). F5: **Bolsa: F5 Dev (recomendado)**.

API debe arrancar con `python-multipart` instalado (filings `UploadFile`).

Obsoleto / cleanup: [`pending-delete/README.md`](./pending-delete/README.md).

---

## 6. Checklist prueba manual (fase actual)

### Datos / refresh
- [ ] Refresh Yahoo en 3–5 tickers US + 2–3 ES/EU; revisar cobertura nulls (Piotroski, Beneish, ROIC, beta).
- [ ] Confirmar `fetchedAt` / stale y chip en lista Backtesting.
- [ ] CAPM vs WACC: ticker con beta → `waccMethod=fund_capm_v1` + footnote Tarjeta `ke = rf + β×ERP`; sin beta → sector.
- [ ] Composite live `ver=composite_score_v1_1` + etiquetas liquidez (adv_mega / …).

### Tarjeta Valor
- [ ] Facts + derived (Altman, Piotroski, Graham, DCF bear/base/bull, ROIC, Beneish distress, ADV$).
- [ ] Más métricas: footnote CAPM si `fund_capm_v1`.
- [ ] Composite piernas · etiquetas liquidez · `scoreDisplay100`.
- [ ] Copiloto: solo explica números ya calculados (sin aritmética inventada).
- [ ] Filings: upload TXT · Traer SEC (US) · Preguntar RAG.

### Gates / Screeners
- [ ] Gate rico + sector bands en scanner híbrido.
- [ ] Screener FA → persist whitelist `kind=snapshot`.
- [ ] Gate `minRoic` / `maxBeneishM` (opcional) en estrategia.

### Paper D / cron
- [ ] Propose dry-run sobre whitelist.
- [ ] Execute con `PAPER_D_EXECUTE=1` + política `paper_auto` (cuenta paper).
- [ ] Manual FA→D semanal; cron solo si env configurado.

### Regresiones conocidas (ya corregidas)
- [ ] Backtesting no crashea (`accounts` array en React Query).
- [ ] API arranca (multipart).

### Optimización (siguiente)
- [x] Hit-rate Yahoo (2026-08-01 audit 8 tickers): Piotroski 75% · ROIC 87.5% · Beneish 50% · beta 87.5% · ADV/WACC/Graham 100%. Bancos SAN/BBVA null Piotroski/Beneish/Altman (diseño).
- [x] Timeseries: income vacío → replace completo; ROIC lee debt/cash del balance.
- [ ] Latencia refresh batch + screener FA en universos grandes.
- [x] UI: densidad Tarjeta Valor + nota nulls bancos.
- [x] Composite: calibrar buckets ADV vs mcap (`composite_score_v1_1` · AAPL≠ACS).
- [x] Beneish: hard-limit distress en Score_FUND si M > −1.78.

---

## 7. Decisiones bloqueadas (no reabrir en prueba)

1. LLM **nunca** calcula ratios ni escribe BD operacional.
2. Filings **nunca** alimentan Score_FUND / gate numérico.
3. Piotroski / Beneish: **null si incompleto** (no parcial).
4. Card sin `bias`; UI usa `scoreDisplay100`.
5. Paper D ≠ radar B ≠ Supervisado C.
6. Execute paper off-by-default.

---

## 8. Enlaces código

| Pieza | Path |
|-------|------|
| Snapshot | `packages/py/market/src/bolsa_market/instrument_fundamentals.py` |
| Card / Score | `packages/py/analytics/.../fundamental_card.py` · `score_fund.py` |
| Gate TS/Py | `packages/shared/src/fundamentals-gate.ts` · `bolsa_analytics/signals/fundamental_gate.py` |
| Screener / Paper D / Weekly | `bolsa_application/run_fundamental_screener.py` · `paper_d_propose.py` · `fa_weekly_pipeline.py` |
| Ayuda tracker | `apps/web/src/features/settings/value-analysis-tracker.ts` |
| Battery | `scripts/research/verify_fa_battery.mjs` |
