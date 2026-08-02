# Informe estabilidad temporal (Q1.3)

- **Ventana A:** `ibex35-rsi-win-a` (trials=3)
- **Ventana B:** `ibex35-rsi-win-b` (trials=3)
- **Celdas same / changed / missing:** 0 / 3 / 0

## Caveat

Sharpe mediano cross-family ≠ verdad; mirar tradeCount/Calmar (Q0.4).
Solo human IS; grid no entra en tercios.

## Δ ranking (solo celdas changed/missing)

| Activo | Familia | A | B | Δ |
|--------|---------|---|---|---|
| BBVA | RSI | ▼ | ▲ | ▼→▲ |
| IBE | RSI | ▲ | ○ | ▲→○ |
| SAN | RSI | ○ | ▼ | ○→▼ |

## Gate C4

Abrir C4 solo si hay hipótesis escrita **y** este Δ lo justifica (p.ej. patrón de fortaleza por activo se rompe con volatilidad).
