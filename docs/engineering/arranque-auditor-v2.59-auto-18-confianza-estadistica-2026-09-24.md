# Arranque del auditor — `v2.59-beta` (AUTO-18 · Confianza estadística)

**Qué se te pide:** revisar el delta de `V2.59`/`AUTO-18` **contra su invariante**, no contra el estilo.
Todo lo que sigue está **medido sobre el árbol sellado**; lo que **no** se pudo medir aquí está declarado
como tal (y se dice qué lo cierra). Superficie de revisión: el PR de auditoría (rama
`auto-18-confianza-estadistica` → la base de `v2.58-beta`).

Antes de empezar: `git status`, `git log --oneline -5`, la head de Alembic
(`046_fill_reference_mid`) y la guardia de head
(`apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43`).

---

## 0. Si solo tienes una hora

1. **El invariante** (§1) y las **seis reglas duras**: `effective_N` **estadístico**, cobertura por
   régimen (eje propio), calibración **descriptiva**, expectancy encogida por la `n` **nueva**, series
   por `(basis, cost_model_version)`, `DATA_DEGRADED` ≠ `UNKNOWN`.
2. **Sin migración** (§2): `costModelVersion` es **aditivo**; `_ALEMBIC_HEAD` **no** se movió.
3. **La costura con CONTROL** (§5): sin `confidence` el plan es **byte-idéntico**; con `confidence`, el
   factor publicado es el de la `n` **estadística**, no la bruta.
4. **El delta simétrico** (pack §7) y el **CI del sello** (pack §11): el delta lleva sus rojos
   **declarados de antemano** — el **sello** (`auto18-v1`) y la guardia de head **no** cambian —, y
   **ningún** rojo residual; el CI del sello se **mide después de sellar** (§8, no es un hallazgo).

---

## 1. El invariante (ataca contra él, no contra el estilo)

> **Ninguna recomendación Adaptive puede pesar más de lo que su población independiente, homogénea,
> comparable y calibrada sostiene.** La evidencia se mide con `effective_N` **estadístico** (no con el
> bruto), se publica con su **cobertura por régimen** y su **fiabilidad por banda**, y solo compite en un
> eje cuando comparte `(net_r_basis, cost_model_version)`. Adaptive sigue siendo **read-only**.

Seis corolarios, con test y con mutación que los mata:

1. **La independencia acota la muestra.** `effective_n = min(measured_n, episodes)`; 100 ciclos de una
   sola fase de mercado encogen como **1** porque eso es lo que la independencia permite afirmar. Los
   ciclos `UNKNOWN` forman/extienden su **propia** racha (declarado).
2. **La cobertura es un eje propio.** `HIGH`/`MEDIUM`/`LOW`/`UNCOVERED` por celda, desde la muestra
   efectiva; **no** mueve la banda de confianza.
3. **La calibración no decide.** `ConfidenceCalibration` publica banda→`n`/`mean_r`/`win_rate`/rango
   prometido/fiabilidad observada. Es **descriptiva**: no cambia banda ni reparto.
4. **La expectancy se encoge con la `n` nueva.** `shrunk_expectancy_r` en cada fila/celda; el reparto usa
   `effective_n`, no `measured_n`.
5. **Dos metros ⇒ dos series.** Un cambio de `costModelVersion` **separa** series; `COST_MODEL_TRANSITION`
   bloquea `decay` y el eje del R neto. Población homogénea = `(basis, cost_model_version)`.
6. **`DATA_DEGRADED` no es `UNKNOWN`.** Un neto **sin** base declarada baja la banda y añade nota
   (`ADAPTIVE_CONFIDENCE_BASIS_UNDECLARED`); **no** hay neto es el `UNKNOWN` **inocuo** que no bloquea.

**La compatibilidad es parte del invariante:** sin `confidence` el plan es byte a byte; los campos nuevos
tienen **defecto seguro** (`measured_n = effective_n` histórico, `cost_model_version=None`,
`episodes=0`).

---

## 2. Sin migración: qué se declara

- **`_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`**: `costModelVersion` entra como clave **aditiva**
  en el JSON de `TradingCost.to_dict()` (ya persistido en reservas), recomputable de
  `commissionPresetId + bps`.
- **Sin backfill:** las filas históricas quedan `None`/`undeclared`. El metro **no** se reconstruye hacia
  atrás y se publica tal cual (declarado, nunca afirmado).
- **La confianza viaja en `healthByStrategy`/`evidence_for`** con campos nuevos `null` por defecto: sin
  clave nueva en el journal durable.

---

## 3. La muestra estadística y su cobertura

| Punto | `ruta:línea` |
| --- | --- |
| `_episodes` (rachas de régimen por versión) | `auto_adaptive_confidence.py:391` |
| `_coverage_band` (eje de cobertura por celda) | `auto_adaptive_confidence.py:416` |
| `_shrunk` (expectancy encogida `n/(n+k)`) | `auto_adaptive_confidence.py:434` |
| `_band` (banda **bajada** si `DATA_DEGRADED`) | `auto_adaptive_confidence.py:464` / `:494` |
| `_regime_calibration` (tabla descriptiva) | `auto_adaptive_confidence.py:1026` |
| `RegimeConfidence` (`measured_n`/`episodes`/`coverage`/`shrunk_expectancy_r`) | `auto_adaptive_confidence.py:634` |
| `StrategyConfidence` | `auto_adaptive_confidence.py:700` |
| `ConfidenceCalibration` | `auto_adaptive_confidence.py:767` |
| `AdaptiveConfidence` (con `calibration`) | `auto_adaptive_confidence.py:813` |
| Descuento declarado | `auto_adaptive_confidence.py:267` |

- **`effective_n ≤ measured_n` siempre** (es un `min`). El descuento se declara
  (`ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT`) para que una muestra que se encoge por falta de independencia
  **no** parezca un dato perdido.
- **Sin fechas legibles** la cobertura/calibración se declaran, no se inventan: una ventana sin `closedAt`
  ordenable no fabrica rachas.

---

## 4. El metro del coste y el reparto

| Punto | `ruta:línea` |
| --- | --- |
| `NetRBasis` (enum cerrado) | `auto_self_evaluation.py:131` |
| `NetRBasisSeries` | `auto_self_evaluation.py:746` |
| `_net_r_series` (agrupa por `(basis, model)`) | `auto_self_evaluation.py:1233` |
| `_cost_model_key` / `_cost_model_of` | `auto_self_evaluation.py:1270` / `:1275` |
| `_basis_of` / `_pooled_net_expectancy` | `auto_self_evaluation.py:1289` / `:1331` |
| `affirms_declared_net_r_basis` + guarda en `_strategy_row` | `auto_self_evaluation.py:1307` / `:1424` |
| `BasisTransition` (enum cerrado) | `auto_adaptive_confidence.py:210` |
| `_basis_transition` (con `DATA_DEGRADED`) | `auto_adaptive_confidence.py:514` / `:555` |
| `_decay` gated por transición | `auto_adaptive_confidence.py:577` |
| `cost_model_signature` (firma del modelo) | `portfolio_reservation.py:205` |
| `cost_model_version` en `TradingCost` + JSON | `portfolio_reservation.py:263` / `:283` |
| `_net_basis_comparable` (población homogénea) | `auto_adaptive.py:1030` |
| `_confidence_factor` (usa `effective_n`) | `auto_adaptive.py:1188` |
| `shrink_factors` publicado | `auto_adaptive.py:615` / `:1308` |
| `evidence_for` (los seis campos) | `auto_adaptive.py:830` |
| Sello del reparto | `auto_adaptive.py:198` |

- **El sello sube a `auto18-v1`**: aquí **sí** cambia la **regla** del reparto (la `n` del encogimiento),
  a diferencia de `AUTO-17`, donde cambiaba la condición del eje. `DATA_GATE_POLICY_VERSION` sigue
  `auto15-v1`.
- **`MIXED` vs `TRANSITION`:** `MIXED` es heterogeneidad **interna** (dos bases conviviendo en la MISMA
  ventana); `TRANSITION` es un cambio **temporal** de base entre ventanas. Son **dos ejes distintos** y
  ambos se declaran.

---

## 5. La costura (con CONTROL)

- **Costura hermética** (`test_auto_v59_auto18_confidence_seam.py`, por el camino **real** del worker):
  la evidencia publicada lleva `measuredN`/`episodes`/`effectiveN`/`coverage`/`shrunkExpectancyR`/
  `shrinkFactor`, y el factor **es** el de la `n` **estadística** (`1/(1+prior)`), no el de la bruta.
- **Control positivo** (la confianza sin lector de régimen declara `episodes=1`/`coverage=LOW` en vez de
  inventar independencia) y **control** del sello (`auto18-v1`).
- **Freeze byte a byte**: `auto_adaptive_journal.py` y `v2_43_governor_evidence.py` con diff **vacío**.
- **Batería pre-tag medida con la selección EXACTA del CI** (la lista literal de `python-ci.yml`, que
  incluye `apps/api-python/tests` con sus `--ignore`): **`2728 passed`**, `0` rojos, **`94.07 s`**.
- **CI del sello ya medido** (pack §11): `Release tag CI` **`success`**, job `python` del tag
  **`2701 passed / 35 skipped`**, `Python CI` per-commit del tag y de `main` **`5/5`**, `check-runs` del
  sello `45` = `44` success + `1` skipped, PR [#68](https://github.com/jvelasca/Bolsa_V1/pull/68)
  `29` checks `SUCCESS`.
- **Lo que sigue sin poder medirse aquí:** las suites que exigen **PostgreSQL real** en local (las PG
  `--ignore`adas, `apps/api-python/tests/integration` y `chaos/live_a7`; importan `asyncpg`, ausente en
  esta máquina). Las **cierra** la CI del tag, que ya las corrió en verde.

---

## 6. Mutaciones que YA se midieron (no las redisculpas)

`M139…M148` muerden **todas** (pack §6) y la matriz **completa** `M1…M148` está corrida con **0**
etiquetas en `NADA`, **0** fragmentos ausentes y restauración **byte a byte**. **Cinco realineos
declarados** de la sonda (`M60`, `M125`, `M128`, `M131`, `M134`) porque su ancla cambió con esta fase
(`M131` dejó de morder al añadir `AUTO-18` una segunda guarda a `_pooled_net_expectancy`; la mutación
desactiva ahora **las dos**). Si crees que una mutación **no** muerde, reproduce su corrida antes de
reportarlo: la sonda imprime, para cada etiqueta, los tests que se pusieron rojos **por nombre**.

---

## 7. Comandos exactos (no los reinventes)

```bash
# Estático (los de CI, no rutas sueltas)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió: diff VACÍO
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py

# El contrato durable NO se movió: diff VACÍO
git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py

# La guardia de head NO cambió (la head sigue en 046)
rg -n "_ALEMBIC_HEAD" apps/api-python/tests/test_discovery_evidence_snapshot_pg.py

# El tramo de la fase (unit + costura hermética)
uv run --no-sync python -m pytest packages/py/analytics/tests/test_auto_adaptive_confidence.py packages/py/analytics/tests/test_auto_adaptive.py packages/py/analytics/tests/test_auto_self_evaluation.py packages/py/application/tests/test_cycle_risk.py packages/py/application/tests/test_auto_self_evaluation_feed.py apps/api-python/tests/test_auto_v59_auto18_confidence_seam.py apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py apps/api-python/tests/test_auto_v54_auto13_data_gate_wiring_seam.py apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py -q

# La matriz de mutaciones (mide, restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
```

- **Batería pre-tag completa, con la selección EXACTA del CI** (`2728 passed`, `0` rojos): copia la línea
  `pytest` literal del job `quality` de `.github/workflows/python-ci.yml` y cámbiale el prefijo
  `uv run pytest` por `uv run --no-sync python -m pytest` (en esta máquina `uv run pytest` lo bloquea el
  Control de aplicaciones). Lo único que queda fuera es lo que exige **PostgreSQL real**.

---

## 8. Qué NO es un hallazgo (declarado de antemano)

- **La calibración es descriptiva.** No mueve banda ni reparto; un `mean_r` observado bajo **no** es un
  bug: es información publicada para el operador.
- **El `effective_N` por episodios es una cota, no una varianza.** Que 180 ciclos de un solo régimen
  cuenten como **1** es exactamente el diseño conservador ratificado.
- **`cost_model_version` no se reconstruye hacia atrás.** El histórico queda `None`/`undeclared`
  **declarado**; no es un hueco silencioso.
- **El CI del sello se mide DESPUÉS de sellar, no antes.** El run del tag **no existe** hasta empujar el
  tag, así que las cifras viven en el `audit-pack` **§11** —añadido en el **commit de docs posterior al
  sello**, el mismo patrón declarado que `AUTO-13`…`AUTO-17`.
- **El flake `test_finance_auto_day_materializes_executetrade_exactly_once` NO es un hallazgo de la fase.**
  Su primer intento en el `Release tag CI` cayó en `RETRY` (estado de **lease** de `execution_events`), se
  cerró con el **re-run declarado** y su camino (`simulated_finance`/`simulated_settlement`/`execution_event`)
  **no importa** ninguno de los cuatro ficheros que `AUTO-18` toca. El detalle medido está en pack §11.6.
- **`/commits/{sha}/status` en `pending` con `0` statuses NO es un rojo.** Es la API **legacy de Commit
  Status**; el repo publica **check-runs**. No lo reabras sin una medición nueva.
- **El flag Adaptive sigue OFF.** Sin él no hay plan ni lectura.
- **Sin UI, sin SHORT, sin backfill.**

---

## 9. Preguntas abiertas que el autor NO cierra

1. Con dos modelos dentro de la MISMA base el pooled del agregado es `None`: ¿basta para que un
   consumidor futuro no improvise una media, o debería ser un **error de tipo** en la firma?
2. Los `episodes` se cuentan sobre el orden de llegada de las ventanas: ¿debería publicarse también el
   **número de régimen distinto** como cota superior de independencia, para auditar el `min`?
3. La calibración descriptiva publica la fiabilidad observada por banda, pero **no** su error: con `n`
   pequeño, ¿debería declararse un intervalo en vez de un punto?
4. La **caducidad** de una racha durable vieja (cola de `AUTO-15`) sigue sin existir.

---

## 10. Lo que **no** debes asumir

- Que el flag está ON: **está OFF**, y con él nada de esto corre en producción.
- Que `coverage = HIGH` implica confianza alta: son **dos ejes distintos** (independencia vs deterioro);
  una celda con `coverage=HIGH` puede tener `decay=SEVERE`.
- Que un `basis_transition = DATA_DEGRADED` es "sin datos": es "hay un neto y **no** declara su base", que
  es un estado **peor** que `UNKNOWN` (baja la banda).
- Que los tests verdes locales cubren los jobs PG: los jobs PG necesitan PostgreSQL real.

---

## 11. Formato del hallazgo

Para cada hallazgo: **(a)** el invariante que se rompe, **(b)** el fichero y la línea, **(c)** el caso
mínimo que lo reproduce, **(d)** si hay un test que debería haberlo cazado y no lo hizo (y por qué),
**(e)** la mutación (`M…`) que debería cubrirlo si es del alcance de la sonda. Un hallazgo sin caso
mínimo es una opinión.
