# Lab Notebook — IBEX35 Cross-Family Consolidation (Campaña 3.5)

## Fecha

2026-07-24

## Objetivo

Explotar el ledger existente (\(K=2893\)) **antes** de abrir una cuarta familia. Comprobar si el laboratorio responde preguntas cross-family con solo lectura de `research_trials`.

**No es Fase 2.** Cero entidades nuevas, cero Discovery Score, cero Belief, cero semántica nueva.

## Método

| Campo | Valor |
|-------|--------|
| Fuente | `research_trials` (solo lectura) |
| Script | `scripts/research/cross_family_consolidation.py` |
| Universo | IBEX 35 · 3 familias cerradas (SMA, RSI, MACD) |
| Ranking | Tercios **dentro de cada familia** sobre mediana de Sharpe **human** |
| Marcas | ▲ tercio superior · ○ medio · ▼ inferior · — sin human Sharpe |
| Sin | puntuaciones nuevas, \(C_{score}\), filtros de universo implementados |

Familias ← presets:

- **SMA** ← `sma_crossover`
- **RSI** ← `rsi_mean_reversion`, `rsi_momentum`, `rsi_oversold_bounce`
- **MACD** ← `macd_signal_cross`, `macd_zero_line`

## Ledger (estado al consolidar)

| Métrica | Valor |
|---------|--------|
| Trials / K | 2893 |
| human / grid | 218 / 2675 |
| Sharpe nulo | 2685 (92.8%) — **casi todo grid** (2675/2675 sin `sharpeRatio` en `is_metrics`); human 10/218 |
| tradeCount=0 | 214 (7.4%) — human 10 · grid 204 |

Interpretación: el % de Sharpe nulo **no** mide “experimentos vacíos”; mide hueco de métrica en el payload del grid. Vacío operativo ≈ `tradeCount=0`.

## Matriz Activo × Familia

| Activo | SMA | RSI | MACD | Trials | K | Observación |
|--------|-----|-----|------|--------|---|-------------|
| ACS | ▲ | ▲ | ▲ | 107 | 107 | fuerte en 3 familias |
| ANA | ▲ | ▲ | ▲ | 82 | 82 | fuerte en 3 familias |
| BBVA | ▲ | ▲ | ▲ | 82 | 82 | fuerte en 3 familias |
| CABK | ▲ | ▲ | ▲ | 81 | 81 | fuerte en 3 familias |
| ELE | ▲ | ▲ | ▲ | 81 | 81 | fuerte en 3 familias |
| IDR | ▲ | ▲ | ▲ | 81 | 81 | fuerte en 3 familias |
| MAP | ▲ | ▲ | ▲ | 81 | 81 | fuerte en 3 familias |
| REP | ▲ | ▲ | ▲ | 81 | 81 | fuerte en 3 familias |
| UNI | ▲ | ▲ | ▲ | 81 | 81 | fuerte en 3 familias |
| MEL | ▲ | ▼ | ▲ | 81 | 81 | depende de familia |
| ACX | ○ | ▲ | ○ | 107 | 107 | mixto / no extremo |
| IAG | ○ | ○ | ▲ | 81 | 81 | mixto / no extremo |
| IBE | ▲ | ○ | ○ | 81 | 81 | mixto / no extremo |
| SAN | ▲ | ○ | ○ | 81 | 81 | mixto / no extremo |
| ALM | ▼ | ▲ | ○ | 82 | 82 | depende de familia |
| CAF | ○ | ▼ | ▲ | 81 | 81 | depende de familia |
| NTGY | ○ | ▲ | ▼ | 81 | 81 | depende de familia |
| AENA | ○ | ○ | ○ | 82 | 82 | zona media en todas |
| BKT | ○ | ○ | ○ | 82 | 82 | zona media en todas |
| ENG | ○ | ○ | ○ | 81 | 81 | zona media en todas |
| FER | ○ | ○ | ○ | 81 | 81 | zona media en todas |
| SAB | ○ | ○ | ○ | 81 | 81 | zona media en todas |
| SCYR | ○ | ○ | ○ | 81 | 81 | zona media en todas |
| GRF | ▼ | ○ | ○ | 81 | 81 | mixto / no extremo |
| LOG | ○ | ○ | ▼ | 81 | 81 | mixto / no extremo |
| PHM | ▼ | ○ | ○ | 81 | 81 | mixto / no extremo |
| VIS | ○ | ▼ | ▼ | 81 | 81 | débil mayoritario |
| AMS | ▼ | ▼ | ▼ | 82 | 82 | débil consistente |
| CLNX | ▼ | ▼ | ▼ | 81 | 81 | débil consistente |
| COL | ▼ | ▼ | ▼ | 81 | 81 | débil consistente |
| FDR | ▼ | ▼ | ▼ | 81 | 81 | débil consistente |
| ITX | ▼ | ▼ | ▼ | 81 | 81 | débil consistente |
| RED | ▼ | ▼ | ▼ | 81 | 81 | débil consistente |
| ROVI | ▼ | ▼ | ▼ | 81 | 81 | débil consistente |
| TEF | ▼ | ▼ | ▼ | 81 | 81 | débil consistente |

## Respuestas del laboratorio

| Pregunta | Respuesta (ledger) |
|----------|-------------------|
| ¿Activos sistemáticamente fuertes? | **ACS, ANA, BBVA, CABK, ELE, IDR, MAP, REP, UNI** (▲ en 3) |
| ¿Activos sistemáticamente débiles? | **AMS, CLNX, COL, FDR, ITX, RED, ROVI, TEF** (+ VIS débil mayoritario) |
| ¿Dependen de familia? | **MEL, ALM, CAF, NTGY** (▲ y ▼ mezclados) |
| ¿Mayor dispersión entre activos? | **MACD** (pstdev medianas 0.76) > SMA (0.66) > RSI (0.58) |
| ¿Quién recibe más K? | ACS / ACX (107); resto ~81–82 — sesgo residual C1, no diseño |
| ¿Presets con más vacíos (`tradeCount=0`)? | `rsi_mean_reversion` 21.4% · `rsi_oversold_bounce` 14.3% · resto ≤1.4% |
| ¿% Sharpe nulo? | 92.8% global; **human ~4.6%**; grid 100% sin campo — hueco de instrumentación, no de trades |

## Caveat ranking (Q0.4 · 2026-08-02)

**Sharpe mediano cross-family ≠ verdad científica.** El ranking ▲/○/▼ es un *mapa exploratorio* anclado en human Sharpe dentro de cada familia. Antes de decidir producto u hipótesis C4:

1. Mirar **tradeCount** (vacíos operativos) y **Calmar**/maxDD, no solo Sharpe.
2. Usar Lab Health (`GET /api/research/lab-health` · `scripts/research/lab_health_report.py`) para cobertura Sortino/Calmar.
3. No comparar score de grid interno con ranking human cross-family.

Ver [improvement-roadmap-post-audits-2026-08-02.md](../../docs/engineering/improvement-roadmap-post-audits-2026-08-02.md) Q0.4.

## Observaciones

1. **El factor dominante IS es el activo, no la familia.** 9 fuertes y 8 débiles atraviesan SMA/RSI/MACD. Coincide con la intuición de C1–C3 y ahora está tabulado.
2. **Dependencia de familia es minoritaria** (4/35). La mayoría no “cambia de tercio” al cambiar de indicador.
3. **Asimetría K grid/human** se confirma otra vez (~92% grid), pero aquí no se corrige — solo se constata.
4. **Hueco métrico del grid:** sin `sharpeRatio` en `is_metrics` del grid, cualquier ranking cross-family fiable debe anclarse en **human** (como este informe) o enriquecer el payload del grid en una pasada futura de instrumentación (no es Belief).
5. **Nota motor MACD:** `_macd_signal_line` siembra `None→0.0` antes de la EMA de señal — distorsión de calentamiento. Anotado en código (`macd_grid.py`); revisar antes de tratar `macd_grid_h0` como referencia definitiva.

## Implicación para Campaña 4

El ledger **sí responde** a las preguntas de explotación. Abrir Bollinger/Stoch sobre los 35 ahora añadiría ~900 K sin cambiar el diagnóstico principal.

**Criterio (post-auditoría C3.5):** una nueva familia solo se ejecuta si responde una pregunta que SMA/RSI/MACD no pueden responder.

| Opción | Idea |
|--------|------|
| **A — Pausar familias** | No C4 hasta que haya una pregunta nueva que el ledger no conteste |
| **B — C4 con hipótesis de universo** | Bollinger solo sobre subconjuntos (p.ej. fuertes vs débiles) como contraste — sigue siendo explotación, no Belief |
| **C — C4 universo completo** | Solo si se quiere una cuarta filosofía (volatilidad) para stress-test del ranking de activo |

**Decisión actual:** pausa evaluativa (**A**). **B** si aparece pregunta de volatilidad explícita. **C** desaconsejada a ciegas.

### Instrumentación cerrada (forward)

Hueco grid sin `sharpeRatio` corregido en motores SMA/RSI/MACD + hook optimize (`finalize_grid_is_metrics`). Trials C1–C3 **no** se re-ejecutan. Issue MACD warm-up: [ISSUES.md](./ISSUES.md#macd-signal-ema-warmup).

## Relación

- Índice: [index.md](./index.md)
- C1 SMA: [2026-07-24-ibex35-battery.md](./2026-07-24-ibex35-battery.md)
- C2 RSI: [2026-07-24-ibex35-rsi.md](./2026-07-24-ibex35-rsi.md)
- C3 MACD: [2026-07-24-ibex35-macd.md](./2026-07-24-ibex35-macd.md)
