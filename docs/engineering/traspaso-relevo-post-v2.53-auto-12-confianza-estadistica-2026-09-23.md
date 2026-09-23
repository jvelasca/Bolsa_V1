# Traspaso de relevo — post `V2.53` (`AUTO-12` Confidence + calidad estadística)

**Fase:** `AUTO-12` (`V2.53` / `1.78.0-beta`) · **Fecha:** 2026-09-23 · **Fase anterior:** `V2.52`
(`AUTO-11` Estado Adaptive durable y recuperación).
**Documentos de la fase:** [audit-pack](./audit-pack-v2-53-auto-12-confianza-estadistica-2026-09-23.md)
· [plan](./plan-v2-53-auto-12-confianza-estadistica-2026-09-23.md).
**Rótulo ratificado por el propietario:** `AUTO-12` sobre `V2.53` / `1.78.0-beta`, con **alcance core
backend** (`sample_size`, `measurement_completeness`, `confidence`, `recent`/`long`, `decay` y
multiplicador ajustado por confianza; **sin UI**, **sin migración**, **sin Data Gate** y **sin recovery
gradual**) y con **dos decisiones explícitas**: **eje de recencia por instante real** (no por posición de
lista) y **shrinkage por muestra** (redistribuye, no ensancha, y solo actúa sobre edges decisorios).

---

## 0. Posición en la línea AUTO

`v2.48` = `AUTO-8` (Adaptive AUTO) · `v2.49` = `AUTO-8.1` (Adaptive correcto, explícito y reproducible) ·
`v2.50` = `AUTO-9` (Strategy × Regime y net expectancy_R) · `v2.51` = `AUTO-10` (Journal durable por
ciclo) · `v2.52` = `AUTO-11` (Estado Adaptive durable y recuperación) · **`v2.53` = `AUTO-12`
(Confidence + calidad estadística)**: el reparto deja de tratar igual una muestra de 12 que una de 180, y
el sistema **distingue** el histórico del presente declarando `decay`.
**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`).

La línea de preguntas del epic queda así: `AUTO-9` *"¿cuánto vale?"* · `AUTO-10` *"¿de qué ciclo es?"* ·
`AUTO-11` *"¿dónde vive su memoria?"* · **`AUTO-12` *"¿cuánto puedo creérmelo?"***.

---

## 1. Qué quedó HECHO y medido en esta fase

1. **Módulo puro nuevo** `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_confidence.py`
   (sin I/O, sin estado, orden-invariante): `StrategyConfidence` (con `by_regime`), `AdaptiveConfidence`
   (el sobre con `recent_window`/`long_window`/`recent_available`/`notes`) y `build_adaptive_confidence(...)`.
   Reutiliza `aggregate_by_regime` (AUTO-9) sobre **dos rebanadas**, `sample_quality_from_n` como base de
   banda y `combine_measurements` para la completitud **compuesta**.
2. **Eje de recencia aditivo**: `SimFillFinanceContext.created_at` (**sin migración**; la columna PG ya
   existía), proyectado por el store PG; `cycles_from_fills` emite `closedAt` = **último** fill del ciclo
   (un ciclo anónimo **no** reclama instante; un fill sin fecha **no** borra el cierre medible); orden por
   **instante parseado** con el no-parseable al final y **declarado**. `test_auto_self_evaluation_feed.py`
   fija que **AUTO-7 es byte-idéntico** sin fechas.
3. **Costura del feed** `build_adaptive_confidence_from_fills(fills, cycle_risk, ...)`: la confianza y el
   informe se construyen del **mismo** material, sin segundo productor.
4. **Integración en `auto_adaptive.py`**: `StrategyHealth` gana `confidence`, `recent_expectancy_r`,
   `long_expectancy_r` y `decay`; `evidence_for` los publica; `recommend_allocation`/`build_adaptive_plan`
   aceptan `confidence=None` (byte-idéntico sin él) y aplican el **shrinkage** `w·n/(n+k)` **solo** a
   edges decisorios positivos, con normalización de siempre y **suelo > 0**; `AdaptivePolicy` gana
   `confidence_prior = 20.0` y `severe_decay_factor = 0.5`; `ADAPTIVE_POLICY_VERSION` sube a
   **`auto12-v1`**.
5. **Cableado en el worker**: la confianza se construye **una vez** por tick desde los fills ya leídos
   (**cero I/O nuevo**, medido con un store que cuenta llamadas) y el hueco de la ventana reciente se
   registra como `warning` en vez de fingirse.
6. **Evidencia durable sin tocar el contrato**: la confianza viaja **dentro de `healthByStrategy`** del
   journal de `AUTO-11` (`readOnly` conservado). `auto_adaptive_journal.py` y
   `auto_adaptive_recovery.py` quedan **byte a byte iguales**.
7. **Verificación**: **+50 tests** medidos **fichero a fichero contra `HEAD`** (+21 nuevo puro, +9 costura
   nueva, +11 `test_auto_adaptive.py`, +9 `test_auto_self_evaluation_feed.py`); las dos suites modificadas
   en su versión de `HEAD` contra el código de la fase dan **56 pasan / 1 rojo nombrado** (el sello de
   versión, actualizado con nombre); **12/12** mutaciones nuevas (`M60…M71`) muerden; la matriz completa
   (`71/71` medidas, **`0`** en `NADA`, árbol intacto) no deja **ninguna** etiqueta en `NADA`. `AUTO-12`
   **realineó** la sonda heredada `M33` (apuntaba a una llamada *inline* que la fase sustituyó por una
   lectura única del riesgo por ciclo) y vuelve a morder: se declara porque una sonda desalineada
   **afirma** cobertura que no tiene.
8. **Los dos hallazgos de diseño de la fase**, ambos medidos y no opinados:
   (a) **`effective_n` no es `trades`** — 40 ciclos con 4 R medidos son una muestra de **4**
   (`M60` lo prueba); y (b) **`UNKNOWN` no premia** — sin instantes legibles, 120 ciclos medidos dan
   `MEDIUM` y no `HIGH` (`M62` lo prueba).

## 2. Las dos decisiones ratificadas, y qué las sostiene

**Eje de recencia por instante real.** La alternativa (recortar la ventana por posición de lista) es más
barata pero **repite el defecto que la Auditoría 2 midió en `cycle_risk`**: la "ventana reciente" pasa a
ser la última que el llamante puso, no la más nueva en el tiempo. Sostienen la decisión: `M66` (orden por
llegada) rompe **dos** tests, `M67` (recencia inventada) rompe **dos**, y `M70` (cierre por el primer
fill) rompe **dos**. El coste asumido es explícito: `created_at` entra al dominio de fills (aditivo) y sin
fechas legibles **no hay decay** — se declara el hueco.

**Shrinkage por muestra.** La alternativa (un *cap* duro por banda de confianza) es más simple pero
introduce **saltos** y reacciona de más al cruzar una banda. El encogimiento `w·n/(n+k)`:
redistribuye (no ensancha), mantiene `[0, 1]`, nunca deja a nadie en **0**, conserva la normalización
histórica (`(w'/Σw')·count`) y **solo** toca los edges **medidos** — la ausencia de dato sigue siendo
neutral. Sostienen la decisión: `M68` (prior a 0) rompe **tres** tests, `M69` (sin descuento por
deterioro) rompe el suyo, y el test de rotación fija que la confianza **no** crea pausas.

## 3. Lo que esta fase NO toca (y por qué es importante que no lo toque)

- **El gobernador y su evidencia**: `exit 0`, byte a byte iguales.
- **La rotación**: el `decay` **no** añade motivo de pausa. La reacción gradual es `AUTO-13`; el audit
  pedía explícitamente no crear un "sistema nervioso".
- **El contrato del journal** (`auto_adaptive_journal.py`) y la recuperación (`auto_adaptive_recovery.py`).
- **El esquema**: sin migración; head sigue en `044_auto_cycle_trace`. **Sin backfill.**
- **Los umbrales de rotación** y `ADAPTIVE_ADVERSE_REGIMES`.

## 4. Riesgos y deudas declaradas (las que el siguiente chat debe conocer)

1. **`AUTO-13` es el siguiente tramo natural y ya está definido en el audit**: Data Gate
   (`OK/DEGRADED/STALE/BLOCKED`) antes de decidir con evidencia, y **recovery gradual**
   (`RECOVERING` + multiplicadores `0.25→1.0`) en vez del descuento fijo actual.
2. **El `decay` se mide sobre `R` bruto:** el neto sigue siendo el eje **alternativo** de `AUTO-9` y
   exige `net_r_measurement == COMPLETE`, que un coste **estimado** no garantiza. Quien decida con neto
   debe seguir exigiendo eso.
3. **Instrumentación pendiente:** `confidence`, `recent`/`long` y `decay` **ya son durables** (viajan en
   `healthByStrategy`) y **no se ven** en ninguna UI. La deuda de UI de `AUTO-7`…`AUTO-12` sigue viva y ya
   tiene datos que mostrar.
4. **El `bounded` de `AUTO-11` sigue existiendo** para el cooldown (ventana finita, saturación declarada);
   `AUTO-12` no lo cambia.
5. **`governor.json` sigue sin trackear.**
6. **La verificación offline completa del bloque `quality`/`python` del tag no se pudo reproducir en esta
   máquina** por `asyncpg` ausente y por el teardown PG del conftest de `apps/api-python`; los totales de
   CI del tag quedan **a CI** y el audit-pack **no** afirma cifras no medidas.

## 5. Punto de entrada para el siguiente chat

1. Leer [`PROJECT_STATE.md`](./PROJECT_STATE.md) (este bloque) y este relevo.
2. El **plan** de la fase (`plan-v2-53-auto-12-confianza-estadistica-2026-09-23.md`) con sus pasos y
   gates, y el **audit-pack** con las matrices afirmación→código→test.
3. Si el siguiente tramo es **`AUTO-13`**: el audit §22 (Adaptive Data Gate) y §24 (recovery gradual) son
   el punto de partida; el `decay` y la `confidence` que esta fase deja son **el insumo exacto** de los
   dos (un Data Gate decide con `confidence`; el recovery gradual decide con `decay`).
4. Si el siguiente tramo es **UI**: `healthByStrategy` ya lleva `confidence`, `recent`/`long` y `decay`
   en cada recomendación publicada, así que la pantalla tiene datos reales sin tocar el esquema.
