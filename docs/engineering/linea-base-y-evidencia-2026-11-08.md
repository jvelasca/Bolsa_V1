# Línea base y evidencia monetaria — 2026-11-08

Cierre de la **Fase 1** del plan de remediación de la auditoría externa. Responde a la
pregunta que la evidencia DÍA-D sola no podía responder: *¿algún brazo razonable gana dinero
en 2021-2026 con estos costes?* La respuesta medida es **no**, y por eso AUTO sigue OFF.

## Umbrales fijados ANTES de medir

Los cinco, literales en `baseline_arms.BASELINE_THRESHOLDS` (con test que los clava):

| Umbral | Límite |
|---|---|
| Retorno neto | ≥ 0 % |
| Drawdown máximo | ≤ 15 % |
| Ventanas positivas | ≥ 60 % |
| Exceso vs comprar y mantener | ≥ 0 % |
| Coste de ida y vuelta | ≥ 22 bps |

Ventana: 2021-01-01 → 2026-12-31 (barras disponibles 2021-10-29 → 2026-11-06, 1.299 días),
holdout 30 % por días. Costes 10/5/2 bps ⇒ **32 bps** de round-trip.

## Brazos y resultados

Artefacto: `operability_runs/baseline/baseline-arms-2021-10-29_2026-11-06.json`.
Brazo AUTO: `operability_runs/dia-d-auto/multi-2021_2026-evidence.json`.

| Brazo | Neto | DD | Ventanas+ | Exceso vs B&H | Coste RT | Veredicto |
|---|---:|---:|---:|---:|---:|---|
| Buy & hold equiponderado (cesta del catálogo, 20) | +54,472 % | 23,59 % | 52,47 % | 0,000 % | 32 bps | REFUTED (DD, ventanas) |
| Tendencia `close > SMA200`, ejecución al open siguiente | +36,992 % | 16,73 % | 52,11 % | −17,480 % | 32 bps | REFUTED (DD, ventanas, exceso) |
| AUTO V2 (DÍA-D real, edge declarado 11,4) | −169,734 % | 292,21 % | 57,58 % | −230,875 % | 45,41 bps | REFUTED (4 de 5) |

**Ningún brazo pasa los cinco umbrales ⇒ AUTO se queda OFF** y no se añade gobernanza nueva.
El cuello de botella es la **señal**, no el coste (el coste medido supera el suelo en los
tres brazos que operan).

Declaraciones honestas de la comparación:

- El brazo AUTO usa el watch **PIT por año** de `v2_93`; los pasivos usan el **catálogo**
  actual (20 instrumentos, mismos símbolos deterministas). No es el mismo universo exacto:
  el benchmark del brazo AUTO es el suyo (`equityEvidence.buyHold`, 20/20 símbolos).
- El edge del seam es un escalar declarado. Se usó **11,4** (`EdgeReport` persistido
  `EDGE-bef2fc0e63f1`, `sma_crossover`, 2026-11-08), nunca el `0.9` de fábrica.
- El fuera de muestra del brazo AUTO queda **n/d**: su tramo OOS empieza con equity de caja
  negativa y el retorno no es medible sin marca a mercado. Se declara, no se inventa.

## Edge declarado, no fabricado

`v2_93_dia_d_multi.py` ya no tiene `_DEFAULT_EDGE = 0.9`:

- `--edge` es **obligatorio** (sin él, `main` devuelve 1 con un mensaje explícito).
- El valor queda sellado en `meta.declaredEdge` del artefacto.
- El runner de líneas base comprueba que el edge pedido coincide con el del artefacto
  (`edgeMismatch` si no).

Esto elimina la circularidad: el artefacto histórico se había generado con señal fabricada.

## Hueco de `created_at` en fills (1.045 → 0)

- `persist_fill_finance_context` acepta `created_at`; `apply_simulated_order_once` y
  `submit_simulated_order` lo propagan.
- El worker sella `created_at=self._time` (reloj del tick, determinista en replay).
- El store PG respeta el instante declarado (`context.created_at or _now()`).
- El grabador hermético deduplica por `execution_id` y la evidencia filtra a los fills
  **confirmados por el applier** (un contexto persistido antes del apply no prueba caja).
- Resultado: `flowsUnmeasured` **1045 → 0**; curva **123 → 516 puntos**; el artefacto lo
  declara con `unmeasuredReasons {}`.
- El pasado no se rellena: los artefactos anteriores conservan su hueco declarado.

Tests: `packages/py/application/tests/test_sim_fill_created_at.py` (con instante y sin él).

## Curva declarada: caja realizada, NO cartera

`build_equity_evidence` ahora publica `curveBasis: "realized_cash"` y `curveBasisNote`.
La curva acumula solo flujos de caja: una posición viva no se marca a mercado,
así que `maxDrawdownPct` es pico-valle de **caja** y no de cartera (puede sobreestimar la
caída al comprar o subestimarla al no marcar posiciones vivas). El DD de 292,21 % del brazo
AUTO se lee con esa lente y se declara en el artefacto; la marca a mercado queda como
trabajo pendiente explícito, no como un número inventado.

## Reproducir

```bash
uv run --no-sync python apps/api-python/scripts/v2_93_dia_d_multi.py \
  --from-year 2021 --to-year 2026 --universe pit --edge 11.4 \
  --equity-evidence --cycle-detail --json \
  --out operability_runs/dia-d-auto/multi-2021_2026-evidence.json

uv run --no-sync python apps/api-python/scripts/v2_101_baseline_arms.py \
  --from-year 2021 --to-year 2026 --watch-size 20 --edge 11.4 \
  --auto-artifact operability_runs/dia-d-auto/multi-2021_2026-evidence.json \
  --out operability_runs/baseline/baseline-arms-2021-10-29_2026-11-06.json
```

## Decisión de producto

`AUTO_STAYS_OFF`. No se toca AUTO, no se cambian defaults y no se añade gobernanza: con
señal sin edge demostrado, más gobernanza solo hace perder menos despacio. Si en el futuro
algún brazo pasa los cinco, se promueve con ventana PAPER, nunca por cambio de default.
