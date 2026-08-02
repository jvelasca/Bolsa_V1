# Informe estabilidad temporal (Q1.3)

> **AsOf:** 2026-08-03 · corrida `stability_windows_smoke.py --full` (IBEX 35 × 2 ventanas, human RSI).  
> `trials=38` por ventana = 35 IBEX + residuos del smoke `--limit 3` previo con el mismo `campaign_id` (no se purgó ledger).

- **Ventana A:** `ibex35-rsi-win-a` (trials=38)
- **Ventana B:** `ibex35-rsi-win-b` (trials=38)
- **Celdas same / changed / missing:** 13 / 22 / 0
- **Lectura:** ~58% de celdas cambian de tercil entre ventanas → fortaleza por activo **no** es estable en RSI human; Gate C4 sigue cerrado.

## Caveat

Sharpe mediano cross-family ≠ verdad; mirar tradeCount/Calmar (Q0.4).
Solo human IS; grid no entra en tercios.

## Δ ranking (solo celdas changed/missing)

| Activo | Familia | A | B | Δ |
|--------|---------|---|---|---|
| ACX | RSI | ▲ | ○ | ▲→○ |
| ALM | RSI | ▼ | ▲ | ▼→▲ |
| AMS | RSI | ○ | ▼ | ○→▼ |
| BBVA | RSI | ○ | ▲ | ○→▲ |
| CAF | RSI | ▼ | ▲ | ▼→▲ |
| CLNX | RSI | ▼ | ○ | ▼→○ |
| COL | RSI | ▼ | ○ | ▼→○ |
| ELE | RSI | ○ | ▼ | ○→▼ |
| ENG | RSI | ○ | ▼ | ○→▼ |
| FDR | RSI | ▼ | ▲ | ▼→▲ |
| FER | RSI | ○ | ▲ | ○→▲ |
| GRF | RSI | ▼ | ○ | ▼→○ |
| IBE | RSI | ▲ | ○ | ▲→○ |
| IDR | RSI | ○ | ▲ | ○→▲ |
| ITX | RSI | ○ | ▼ | ○→▼ |
| MEL | RSI | ▼ | ○ | ▼→○ |
| NTGY | RSI | ▲ | ▼ | ▲→▼ |
| RED | RSI | ○ | ▼ | ○→▼ |
| REP | RSI | ▲ | ○ | ▲→○ |
| SAN | RSI | ○ | ▼ | ○→▼ |
| SCYR | RSI | ▲ | ○ | ▲→○ |
| TEF | RSI | ▲ | ○ | ▲→○ |

## Gate C4

Abrir C4 solo si hay hipótesis escrita **y** este Δ lo justifica (p.ej. patrón de fortaleza por activo se rompe con volatilidad).
