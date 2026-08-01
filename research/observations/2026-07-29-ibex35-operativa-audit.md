# Auditoría operativa IBEX 35 — 2026-07-29

- Lista: **IBEX 35** (`2b2fcc55c4de44e88e2cca65a`)
- Valores: 35 (catálogo esperado 35)
- sticky TOP #1: 25.0%
- Resultado: **PASS** (critical=0, warn=0)

## Findings

- **[info]** `no_top` — BKT: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — CABK: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — IAG: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — IBE: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — IDR: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — ITX: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — LOG: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — MAP: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — MEL: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — NTGY: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — PHM: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — RED: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — REP: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — ROVI: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — SAB: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — SAN: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — SCYR: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — UNI: sin InstrumentStrategyTop (1d)
- **[info]** `no_top` — VIS: sin InstrumentStrategyTop (1d)
- **[info]** `summary_partial_tops` — 19/35 sin TOP; 16 con TOP
- **[ok]** `live_healthy` — Lista IBEX 35: datos+TOP coherentes a primera vista

## TOP #1 frequency

```json
{
  "supertrend_follow": 1,
  "bollinger_lower_bounce": 1,
  "macd_signal_cross": 1,
  "death_cross": 1,
  "pullback_in_uptrend": 4,
  "adx_di_trend": 2,
  "price_above_sma200": 2,
  "rsi_mean_reversion": 1,
  "sma_crossover": 1,
  "donchian_breakout": 1,
  "stoch_oversold": 1
}
```

## Por valor

| Symbol | Bars | TOP status | Evidence | #1 | miss runId |
|---|---:|---|---|---|---:|
| ACS | 1302 | semifinal | in_sample_only | supertrend_follow | 0 |
| ACX | 1303 | semifinal | in_sample_only | bollinger_lower_bounce | 0 |
| AENA | 1300 | active | lab_validated | macd_signal_cross | 0 |
| ALM | 1299 | semifinal | in_sample_only | death_cross | 0 |
| AMS | 1299 | active | lab_validated | pullback_in_uptrend | 0 |
| ANA | 1299 | semifinal | in_sample_only | adx_di_trend | 0 |
| BBVA | 1301 | semifinal | in_sample_only | price_above_sma200 | 0 |
| BKT | 1299 | — | — | — | 0 |
| CABK | 1299 | — | — | — | 0 |
| CAF | 1299 | active | lab_validated | price_above_sma200 | 0 |
| CLNX | 1300 | active | lab_validated | adx_di_trend | 0 |
| COL | 1299 | active | lab_validated | rsi_mean_reversion | 0 |
| ELE | 1299 | active | lab_validated | sma_crossover | 0 |
| ENG | 1299 | semifinal | in_sample_only | donchian_breakout | 0 |
| FDR | 1299 | active | lab_validated | pullback_in_uptrend | 0 |
| FER | 1299 | semifinal | in_sample_only | stoch_oversold | 0 |
| GRF | 1299 | active | lab_validated | pullback_in_uptrend | 0 |
| IAG | 1299 | — | — | — | 0 |
| IBE | 1299 | — | — | — | 0 |
| IDR | 1299 | — | — | — | 0 |
| ITX | 1298 | — | — | — | 0 |
| LOG | 1298 | — | — | — | 0 |
| MAP | 1298 | — | — | — | 0 |
| MEL | 1298 | — | — | — | 0 |
| NTGY | 1298 | — | — | — | 0 |
| PHM | 1298 | — | — | — | 0 |
| RED | 1298 | — | — | — | 0 |
| REP | 1298 | — | — | — | 0 |
| ROVI | 1298 | — | — | — | 0 |
| SAB | 1298 | — | — | — | 0 |
| SAN | 1298 | — | — | — | 0 |
| SCYR | 1298 | — | — | — | 0 |
| TEF | 1298 | active | lab_validated | pullback_in_uptrend | 0 |
| UNI | 1298 | — | — | — | 0 |
| VIS | 1298 | — | — | — | 0 |

## Notas

- Offline coach/Lista AUTO: `pnpm test:coach` (incluye `ibex35-operativa-audit.test.ts`).
- Batería de backtests: `python scripts/research/run_ibex35_battery.py`.
