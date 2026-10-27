# ADR-048 — Estado `gated`: una sola fuente de estado y una sola semántica de salida

**Estado:** **Accepted — implementado en `v2.88.167-beta`.** `gated` responde a *«¿qué tiene el libro
ahora?»* y `raw` a *«¿hubo transición en la ventana?»*; la salida se evalúa **sólo** sobre la última
barra con **OHLCV real**. **`Δ motor = 0`** · **`Δ decisión ≠ 0` sólo** en la ruta de política para
presets de volumen/rango y en el caso de libro ilegible · `Δ contrato HTTP = 0` · SIN migración.
**Fecha:** 2026-10-27
**Contexto:** [auditoría de detección](../engineering/auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md)
(§5 y §7: dos evaluadores de salida y dos formas de dato) · evidencia
[`v2.88.167`](../engineering/evidence/v2.88.167/README.md).
**Depende de:** [ADR-031](./031-operational-model-tesis-plan-permiso.md) (posición como estado
operativo) · [ADR-032](./032-operational-core-tradeplan-positionstate-execution.md)
(`PositionState` y ejecución) · [ADR-029](./029-order-proposal-decision-journal.md) (journal
append-only).
**Afecta a:** [`rules_engine.evaluate_exit_last_bar_gated`](../../packages/py/analytics/src/bolsa_analytics/signals/rules_engine.py),
[`position_exit_evaluator`](../../packages/py/application/src/bolsa_application/position_exit_evaluator.py),
[`active_strategy_signal_evaluator`](../../packages/py/application/src/bolsa_application/active_strategy_signal_evaluator.py)
y el journal de [`auto_v2_entry`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py).

---

## 1. El problema, medido (no supuesto)

La palabra `gated` se usaba para **dos preguntas distintas** y con **dos formas de dato**:

| Ruta | Pregunta que responde | Dato con el que se respondía |
| --- | --- | --- |
| Decisor ACTIVE (`mode="gated"`) | ¿qué tiene el **libro** ahora, y qué acción tiene sentido en la última barra? | barras OHLCV reales de la ventana; el estado arranca en `holds_long` (libro) |
| Ruta de política (`position_exit_evaluator`) | ¿la regla de salida se cumple en la última barra? | `evaluate_exit_last_bar_gated`, que **reconstruía** barras `open = high = low = close`, `volume = 0` |

Consecuencias medidas por el banco de contrato (`test_scan_decider_contract`): en presets de
**volumen o rango** la ruta de política evaluaba una serie que **no es la que el scan publica** ni la
que el decisor ACTIVE usa. La misma posición podía recibir una salida distinta según quién
preguntara. Y el estado del libro **no viajaba** en el artefacto de decisión: solo se podía inferir
desde el journal de posiciones.

## 2. Decisión

### 2.1 Una sola fuente de estado: el libro

El estado `gated` **es** el libro real (`_open`, readoptado del espejo canónico en el arranque).
**No** se persiste un segundo estado `gated` en el journal ni en `PositionState`: dos verdades del
mismo hecho divergen el día que una de las dos no se actualiza.

| Hecho | Fuente | Cómo se declara |
| --- | --- | --- |
| ¿Hay posición larga? | `holds_long(symbol)` sobre `_open` | `gatedState.holdsLong: true/false`, `source: "book"` |
| Libro ilegible | el lector lanza | `gatedState.holdsLong: null`, `source: "unavailable"` |
| Ventana que no alcanza | `evaluability_reason` | HOLD `warmup_insufficient` / `warmup_unmeasurable` |

`holdsLong = true` **no** significa «la señal quiere comprar»: significa que la pregunta de la última
barra es **de nivel** (¿procede cerrar?), no de transición. Un `BUY` con el libro largo está prohibido
por construcción (no se promedia a ciegas).

### 2.2 Una sola semántica de salida: última barra con OHLCV real

`evaluate_exit_last_bar_gated(definition, timestamps, closes, *, bars=...)` acepta el **OHLCV real** de
la ventana y construye el `indicator_context` con él. El **wrapper close-only** se conserva para
llamantes históricos y se declara como tal: no es la ruta de producto.

La ruta de política (`position_exit_evaluator`) pasa las barras reales que ya carga. La ruta ACTIVE ya
usaba el contexto real (`_exit_rule_holds`); el ADR fija que **ambas** preguntan lo mismo sobre el
mismo dato.

### 2.3 El estado viaja (aditivo, sin migración)

```json
"gatedState": { "holdsLong": true, "source": "book", "exitEvaluated": "last_bar" }
```

- Campo aditivo de `DecisionPackage` → `V2Signal` → `payload` de `auto_entry_decision` **y** de
  `auto_active_strategy_hold`.
- Se **omite** cuando el productor no declara libro (no se inventa `false`).
- Libro ilegible ⇒ **sin BUY** y HOLD con `gated_unavailable`; nunca un replay silencioso de la
  ventana como si el libro estuviera vacío.

### 2.4 Qué **no** certifica cada uno

| | `gated` | `raw` |
| --- | --- | --- |
| Responde | estado del libro y acción de la última barra | transición dentro de la ventana |
| No responde | cuándo entrar, ni si la operación es rentable | qué tiene el libro ahora |
| Consumidor | decisor ACTIVE y política de salida | scan y alertas |
| Efecto de un error | operar contra el libro (doble compra / no cerrar) | hit/aviso perdido en la ventana |

## 3. Consecuencias

- **Paridad:** ACTIVE y política deben devolver la misma salida sobre el mismo OHLCV
  (`test_active_and_policy_paths_agree_on_real_ohlcv`). El wrapper close-only conserva el
  comportamiento histórico (`test_the_close_only_wrapper_keeps_the_historical_signal`).
- **Libro no readoptado:** si `readopt_positions()` no llegó a ejecutarse, `_open` está vacío y
  `holdsLong` sería `false`. Eso **no** lo arregla este ADR: el worker declara la posición no
  gestionada (`position_unmanaged`, ADR-045/S-5) y la ventana sigue declarando sus propios límites.
  Es un límite conocido, no una segunda verdad.
- **Coste:** el contexto se construye sobre las mismas barras que ya se cargaban; no hay llamada
  nueva a repositorio. El wrapper close-only sigue disponible y no cuesta más que antes.
- **Contrato HTTP:** sin delta. **Migración:** sin delta (`head` sigue `058_estudio_daily_proposals`).
