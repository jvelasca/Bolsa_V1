# Traspaso de relevo — post `V2.49` (`AUTO-8.1` Adaptive correcto, explícito y reproducible)

**Fecha:** 2026-09-21 · **Tag:** `v2.49-beta` (`1.74.0-beta`) · **Migración:** **NO** (Alembic head
`044_auto_cycle_trace`).
**Commit de fase:** `2f541fc7` · **Tag anotado:** `v2.49-beta` → `3d0a139b` → `2f541fc7` · **CI real:**
**10/10 `success`**, `Release tag CI` [`35694148660`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148660)
(2026-09-22).
**Pack de evidencia:** [`audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md`](./audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md)
**Plan de la fase:** [`plan-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md`](./plan-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md)

---

## 0. Posición en la línea AUTO

```
AUTO-6   Crash / Concurrent          ✅
AUTO-7   Self-Evaluation             ✅
AUTO-8   Adaptive Recommendation     ✅ (v2.48)
AUTO-8.1 Adaptive correcto/estable   ✅ (v2.49 — esta fase)
AUTO-9   Strategy × Regime           ⏭️ siguiente (gated por productor)
AUTO-10  Adaptive production         ⏭️
```

La regla de la línea sigue intacta: **la recomendación Adaptive solo estrecha; el motor determinista decide y el
gobernador manda.**

---

## 1. Qué quedó HECHO y medido en esta fase

1. **Gate de decisividad POR FILA** en `recommend_allocation`: solo las estrategias `decisive` con
   `expectancy_currency > 0` entran al reparto proporcional. Una muestra fina favorable ya no mueve el
   presupuesto de las validadas.
2. **Política explícita de "sin evidencia"** (`AdaptivePolicy.unknown_multiplier = 1.0`): una parte del mapa,
   configurable y declarada. `recommend_allocation` **nunca** emite `0.0`.
3. **`0.0` es techo CERO explícito** en `RiskAllocator.compute_allocation` (antes quitaba el techo y cedía todo
   el `risk_budget`: el multiplicador Adaptive `0.0` **ensanchaba** el riesgo). `None` = "sin techo" es ahora el
   único camino de ausencia de techo.
4. **Hysteresis + cooldown** en la rotación: umbrales de pausa ≠ reactivación (PF `1.0`→`1.10`, WR `0.35`→`0.45`)
   y `min_pause_cycles = 3`. El estado previo entra como **dato** (`paused_cycles`), no como estado interno.
5. **`adaptivePolicyVersion` (`auto8-v2`)** sellado en `AdaptivePlan`, `as_dict()` y journal.
6. **Evidencia en el journal**: `decisive`, `trades`, `expectancyCurrency`, `expectancyR`, `netExpectancyR`,
   `profitFactor`, `winRate`, `regime` en el estrechamiento y en la pausa.
7. **Goldens nuevos**: reproducibilidad (orden de filas indiferente), **ON neutral ≡ OFF byte a byte** e
   invariante "Adaptive solo cambia candidatas y techo de riesgo".
8. **M19–M27**: 9 de 9 mutaciones nuevas muerden; árbol intacto.

---

## 2. Límites declarados (no silenciosos)

- **`net expectancy_R` no medido**: `StrategyHealth.net_expectancy_r` es siempre `None` hoy. El `expectancy_currency`
  que alimenta la asignación es **BRUTO** (los fills se realizan `(sell − buy) × qty`, sin comisión ni slippage), y
  el `expectancy_r` de la self-evaluation es `None` porque ningún productor emite `r_multiple` por ciclo.
- **`strategy × regime` no medido**: `StrategyHealth.regime` es siempre `UNKNOWN` (los fills no llevan régimen).
  La rotación usa el régimen **del tick**, no el régimen por estrategia; la política ignora `UNKNOWN` (no se
  inventa el cruce). Es el gate real de `AUTO-9`.
- **Cooldown en memoria**: `self._v2_adaptive_paused_cycles` se reinicia con el proceso; tras un crash una pausa
  puede levantarse antes de su ventana mínima. No añade tabla ni migración (decisión de esta fase).
- **Sin UI**: la recomendación, la política y la evidencia solo son observables vía el detalle del journal.

---

## 3. La siguiente fase (`AUTO-9`, `V2.50`) — recomendación, no orden

El siguiente salto NO es "más IA": es hacer la adaptación **estratificación × régimen** y **económicamente
válida**. Todo pasa por **construir el productor de datos por ciclo**, que hoy no existe:

1. **Productor por ciclo** (**adaptador read-only, SIN migración**: el head sigue en `044`): los tres insumos
   ya son durables y están atados por `cycle_id` — `risk_amount` en `portfolio_reservations.reserved_risk`
   (con `entry`/`stop`/`quantity`/`side`/`cost`), PnL en `sim_fill_finance_context`, y régimen en el
   `marketRegime` del payload del journal. De ahí salen `r_multiple`, `net expectancy_R` (coste **estimado**,
   etiquetado como tal) y `strategy × regime health` **medidos**, con `UNKNOWN` declarado para lo previo y
   `cycles_without_risk` publicado para que el R no se calcule sobre un subconjunto silencioso. Plan de la
   fase: [`plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md`](./plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md).
2. **`strategy × regime health`**: tabla por estrategia y régimen, manteniendo que Adaptive **solo estrecha**
   (un régimen favorable puede devolver a `1.0`, nunca subir por encima).
3. **Hysteresis sobre la nueva señal**: extender la zona muerta a la confianza de muestra (intervalo/bootstrap),
   no solo a PF/WR.
4. **Cooldown durable**: derivar `paused_cycles` del journal durable (`adaptive_strategy_paused` + `cycle_id`) en
   vez de memoria de proceso.
5. **`Fill → incremental evaluator → StrategyHealthCache`**: dejar de reconstruir la self-evaluation histórica
   completa en cada tick.
6. **Crash durante la evaluación Adaptive**: extender la certificación de `AUTO-6` al tramo
   `fills → self-evaluation → adaptive → plan`, comprobando que un reinicio no produce recomendación distinta ni
   orden duplicada (la trazabilidad `cycle_id` ya está).

---

## 4. Invariantes que NO deben romperse

- **Adaptive recomienda, el motor decide.** Ninguna ruta nueva `Adaptive → BUY` ni `Adaptive → LIVE`.
- **Solo estrecha.** El multiplicador vive en `[0, 1]`; `0.0` veta (techo cero explícito), nunca "sin techo".
- **Sin evidencia = desconocido = neutral.** Ni pausa a ciegas ni riesgo cero por omisión.
- **Flag OFF ⇒ byte-identidad** con `AUTO-7`; **ON neutral ≡ OFF**.
- **Gobernador, kill switch, `RiskGate`/`Simulation Gate` y gobernador de drawdown intactos.**
- **Sin SHORT, sin backfill inventado, sin migración no declarada.**
