# Lab Notebook — IBEX35 battery (SMA / RSI)

## Fecha

2026-07-24

## Objetivo

Primera explotación empírica del laboratorio (Baseline v1.5): poblar `research_trials` con la lista IBEX 35, costes reales y presets H0; observar gasto de \(K\) y lectura del Observatory.

## Dataset

| Campo | Valor |
|-------|--------|
| Lista | IBEX 35 (`ibex35`) |
| Timeframe | 1d |
| Bar limit | 500 |
| Capital | 10 000 |
| Costes | commission 10 bps · slippage 5 bps · spread 2 bps |
| Motor | H0 event-driven (barra a barra, sin peek al futuro) |

## Familia evaluada

1. Presets human: `sma_crossover`, `rsi_mean_reversion` (todos los 35).
2. Grid SMA (`proposed_by=grid`) en un subconjunto (ACS…BKT y posteriores).

## Ledger (tras primera tanda + ampliaciones)

Estado al cierre de la campaña SMA grid (resto IBEX):

| Métrica | Valor |
|---------|--------|
| Trials / K | **1003** |
| Instrumentos | 35 |
| human | 78 |
| grid | 925 |

Ver estado vivo: UI `/research` o `python scripts/research/lab_observation_report.py`.

## Observaciones

1. **\(K\) ya es magnitud útil** — la pregunta “¿dónde gastamos investigación?” se responde sin Belief: grid vs human.
2. **Experimentos vacíos son información** — `PnL=0` / `Sharpe=null` (p. ej. RSI sin trades en ANA, ELE, IBE, MAP, SAN) ≠ pérdida; la hipótesis no se activó.
3. **Redundancia** — re-lanzar el mismo preset+costes+instrumento suma \(K\) sin nueva información. Anotado; no se implementa anti-duplicado todavía.
4. **IS fuerte (human)** — UNI, ACS, SAN (cuando hay actividad).
5. **IS débil (human)** — AMS, FDR, ITX, CLNX, RED.
6. **Friction UI/API** — ordenar por Sharpe mezclaba nulls arriba → corregido con **NULLS LAST** en métricas IS del repo (ADR-017, solo lectura).

## Preguntas abiertas

- ¿Por qué UNI / ACS / SAN muestran edge IS relativo y AMS / FDR / ITX no?
- ¿El gasto de \(K\) del grid se justifica o hay que acotar `maxTrials` / universo?
- ¿Cuándo la redundancia deja de ser anecdota y pasa a ser un problema medible?

## Próximo experimento

- Completar **grids SMA** en el resto del IBEX (skip si ya hay grid).
- Mantener metodología: familia → batería → notebook → siguiente familia (p. ej. RSI/MACD más adelante).
- No abrir Evidence / Belief hasta madurez empírica (ADR-017).

## Scripts

```bash
python scripts/research/run_ibex35_battery.py
python scripts/research/run_ibex35_battery.py --optimize-only --skip-if-grid --optimize-max-trials 25
python scripts/research/lab_observation_report.py
```
