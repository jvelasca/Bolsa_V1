# Arranque del auditor — `v2.58-beta` (AUTO-17 · Integridad de la población de medida)

**Qué se te pide:** revisar el delta de `V2.58`/`AUTO-17` **contra su invariante**, no contra el estilo.
Todo lo que sigue está **medido sobre el árbol sellado**; lo que **no** se pudo medir aquí está declarado
como tal (y se dice qué lo cierra). Superficie de revisión: el PR draft **#67**
(`auto-17-integridad-poblacion-medida` → `audit-base-v2.57-beta`).

Antes de empezar: `git status`, `git log --oneline -5`, la head de Alembic
(`046_fill_reference_mid`) y la guardia de head
(`apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43`).

---

## 0. Si solo tienes una hora

1. **El invariante** (§1) y las **cinco reglas duras**: round-trip **cuantitativo**, cierre por la
   autoridad FIFO, series por base, pooled **ausente** si `MIXED`, reparto solo con base comparable.
2. **Sin migración** (§2): la base es **recomputable**; `_ALEMBIC_HEAD` **no** se movió.
3. **La costura con CONTROL** (§5): con base homogénea el pooled es **el número de `v2.57` byte a byte**;
   con `MIXED`/`TRANSITION` el reparto **no** cambia de composición.
4. **El delta simétrico** (pack §7) y el **CI del sello** (pack §11): el delta lleva sus rojos
   **declarados de antemano** — el **sello** (`auto17-v1`) y la guardia de head **no** cambian —, y
   **ningún** rojo residual; el CI del sello se **mide después de sellar** (§8, no es un hallazgo).

---

## 1. El invariante (ataca contra él, no contra el estilo)

> **Ningún número con el que Adaptive decide promedia dos bases de coste distintas: la base del R neto
> viaja con la evidencia, y una población mixta se declara y se abstiene, nunca se interpreta como mejora
> o deterioro.**

Cinco corolarios, con test y con mutación que los mata:

1. **El round-trip se prueba con las cantidades.** `COMPLETE` exige `Σ buy qty == Σ sell qty` (tolerancia
   declarada) **además** de la presencia de lados; el balance usa cantidades **aunque falte
   `reference_mid`** (cierre y medición son ejes independientes).
2. **El cierre lo declara `cycles_from_fills`.** El mapa aplicado se restringe a los `closed_cycle_ids`
   que ya produce el FIFO: un ciclo **reabierto** (recomprado) no recibe fricción.
3. **Dos series, nunca una media.** Con base homogénea el pooled sale **byte a byte** como hoy; con
   `MIXED` el pooled **no se publica** (`None`) y el número viaja en `net_r_series`.
4. **Un salto de base no es señal.** `decay` devuelve `UNKNOWN` si `basis_transition` es `TRANSITION` o
   `MIXED`.
5. **El eje del R neto exige base comparable.** `_allocation_weights` solo adopta `net_expectancy_r` si
   **todas** las versiones que compiten comparten una base **estable**; si no, cae al eje histórico con
   `ADAPTIVE_CELL_NOTE_BASIS_UNSTABLE`.

**La compatibilidad es parte del invariante:** con base homogénea todo es byte a byte como `v2.57`; el
camino sin `reference_mid` publica el número de `v2.56`; los campos nuevos tienen **defecto seguro**
(`net_r_series=()`, `basis_transition=UNKNOWN`).

---

## 2. Sin migración: qué se declara

- **`_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`**: la base del R neto es **recomputable** de
  `reference_mid` presente/ausente + la comisión del modelo. **No** se persiste por ciclo.
- **Sin backfill:** el histórico pre-2.57 queda `STABLE_ESTIMATED`, el post-2.57 `STABLE_APPLIED`; el
  periodo con ambos `TRANSITION`/`MIXED`. El salto de base **no** se interpreta como señal.
- **`downgrade` de `046` = DESTRUCTIVE DATA DOWNGRADE** (simetría de esquema ≠ reversibilidad de datos):
  declarado en el docstring de la migración y en el pack.

---

## 3. El punto único del round-trip y el cierre

| Punto | `ruta:línea` |
| --- | --- |
| `AppliedLeg.quantity` (la cantidad sobrevive aunque falte el mid) | `applied_cost.py:121` |
| `applied_leg` (signo, magnitud, favorable, cantidad) | `applied_cost.py:175` |
| `_quantity_balanced` (tolerancia `_QTY`) | `applied_cost.py:222` |
| Notas nuevas | `applied_cost.py:75` / `:79` |
| Agregado por ciclo (balance + cierre) | `applied_cost.py:266` / `:267` |
| Autoridad de cierre en el mapa | `applied_cost.py:340` |
| **Único** pegador + cierre una sola vez | `auto_self_evaluation_feed.py:214` → `_cycles_with_risk` `:246` |

- **Sin I/O nuevo.** `_cycles_with_risk` calcula `cycles_from_fills` **una sola vez** y reusa su
  `closed_cycle_ids`; no hay segundo FIFO ni lectura nueva.
- **Pregunta incómoda:** ¿puede un ciclo con **tres** patas declararse `COMPLETE`? Sí, si compra y vende
  cuadran: la regla suma las patas, y `legs` es el rastro. Lo mide el unit.

---

## 4. Las series y el reparto

| Punto | `ruta:línea` |
| --- | --- |
| `NetRBasisSeries` | `auto_self_evaluation.py:689` |
| Campo `net_r_series` en las dos filas | `auto_self_evaluation.py:755` / `:853` |
| `_net_r_series` (agrupa por base, determinista) | `auto_self_evaluation.py:1156` |
| `_basis_of` (declara `MIXED` si hay más de una serie) | `auto_self_evaluation.py:1180` |
| `_pooled_net_expectancy` (ausente si `MIXED`) | `auto_self_evaluation.py:1192` |
| `_basis_transition` (detector puro) | `auto_adaptive_confidence.py:268` |
| `_decay` gated por la transición | `auto_adaptive_confidence.py:290` / `:313` |
| `net_r_basis`/`basis_transition` en confianza | `auto_adaptive_confidence.py:355`/`:358`, `:403`/`:407` |
| `_net_basis_comparable` | `auto_adaptive.py:967` |
| Nota `ADAPTIVE_CELL_NOTE_BASIS_UNSTABLE` | `auto_adaptive.py:281` (uso `:1080`) |
| `StrategyHealth.net_r_basis` / `basis_transition` | `auto_adaptive.py:422` / `:423` |
| Sello del reparto | `auto_adaptive.py:188` |

- **El sello sube a `auto17-v1`**: aquí **sí** cambia la **regla** (la condición del eje del R neto), a
  diferencia de `AUTO-16`, donde solo cambiaba la procedencia de un input. `DATA_GATE_POLICY_VERSION`
  sigue `auto15-v1`.
- **La decisión de producto:** las celdas decisivas **no se parten** por base (para no romper
  `min_trades`); la dimensión `strategy × regime × basis` se representa como las dos series.
- **El pooled ausente no es un permiso:** quien decida con el neto debe leer `net_r_series` y exigir una
  base común.

---

## 5. La costura (con CONTROL)

- **Costura hermética** (`test_auto_v57_auto16_applied_cost_seam.py`, por el camino **real** del worker):
  un grupo con una pata `estimated` y otra `applied` **no** mueve pesos por el delta de base
  (`test_a_group_that_mixes_cost_bases_does_not_move_weights_by_the_net_axis`); el eje cae a
  `ALLOCATION_AXIS_CURRENCY` y los multiplicadores **no** cambian.
- **Control positivo** (el grupo con **base única** sí mueve pesos por el neto) y **control** del
  histórico con salto de base (`test_the_historical_basis_jump_does_not_change_who_competes`).
- **Lo que NO se pudo medir aquí:** los runs de CI (no existen hasta empujar el tag) y la batería
  offline **completa** de los jobs del tag (recolectan suites PG que importan `asyncpg`, ausente en esta
  máquina). Ese límite lo cierra la CI del tag.

---

## 6. Mutaciones que YA se midieron (no las redisculpas)

`M129…M138` muerden **todas** (pack §6) y la matriz **completa** `M1…M138` está corrida con **0**
etiquetas en `NADA`, **0** fragmentos ausentes y restauración **byte a byte**. **Tres realineos
declarados** de la sonda (`M122`, `M125`, `M128`) porque su ancla cambió con esta fase. Si crees que una
mutación **no** muerde, reproduce su corrida antes de reportarlo: la sonda imprime, para cada etiqueta,
los tests que se pusieron rojos **por nombre**.

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
uv run --no-sync python -m pytest packages/py/application/tests/test_applied_cost.py packages/py/analytics/tests/test_auto_self_evaluation.py packages/py/analytics/tests/test_auto_adaptive_confidence.py packages/py/analytics/tests/test_auto_adaptive.py apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py -q

# La matriz de mutaciones (mide, restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
```

---

## 8. Qué NO es un hallazgo (declarado de antemano)

- **El aplicado se completa con la comisión del MODELO.** No existe comisión realizada en SIM; la base lo
  **nombra**, así que no finge un coste completo.
- **No hay backfill.** El histórico anterior a `2.57` no tiene referencia y se mide con el estimado
  **declarado**.
- **El CI del sello se mide DESPUÉS de sellar, no antes.** El run del tag **no existe** hasta empujar el
  tag, así que las cifras viven en el `audit-pack` **§11** —añadido en el **commit de docs posterior al
  sello**, el mismo patrón declarado que `AUTO-13`…`AUTO-16`—: `Release tag CI`
  [`35976693458`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35976693458) **verde a la primera**
  (`10 success` + `1 skipped`), `2668 passed / 35 skipped` y `37` `check-runs`. **No hubo re-sello.**
- **`/commits/{sha}/status` en `pending` con `0` statuses NO es un rojo.** Es la API **legacy de Commit
  Status**; el repo publica **check-runs** —los `37` de `72f6084a` están `completed`—. Medido **en vivo
  sobre el propio sello**: es el **cruce de API**, no un check ausente (es el P0 del acta de `v2.57`,
  cerrado documentalmente en esta fase; no lo reabras sin una medición nueva).
- **La base no se persiste por ciclo**: se recomputa. No hay migración.
- **El flag Adaptive sigue OFF.** Sin él no hay plan ni lectura.
- **Sin UI, sin SHORT, sin backfill.**

---

## 9. Preguntas abiertas que el autor NO cierra

1. Con **base mixta** el pooled del agregado es `None`: ¿basta para que un consumidor futuro no improvise
   una media, o debería ser un **error de tipo** en la firma?
2. La tolerancia del balance de cantidades (`_QTY`) es **declarada**; ¿debe publicarse en el payload del
   informe para que el auditor la vea sin leer el módulo?
3. Un ciclo con **tres o más patas** cuenta su balance, pero **no** publica la composición (qué pata
   aportó qué). ¿Es suficiente para auditar la resta?
4. La **caducidad** de una racha durable vieja (cola de `AUTO-15`) sigue sin existir.

---

## 10. Lo que **no** debes asumir

- Que el flag está ON: **está OFF**, y con él nada de esto corre en producción.
- Que `basis_transition = STABLE_*` implica una base única *para siempre*: implica que las dos ventanas
  comparadas comparten base, no que la población entera la comparta.
- Que el pooled ausente es un `0`: es **`None`**, «no se publica», no «vale cero».
- Que los tests verdes locales cubren los jobs PG: los jobs PG necesitan PostgreSQL real.

---

## 11. Formato del hallazgo

Para cada hallazgo: **(a)** el invariante que se rompe, **(b)** el fichero y la línea, **(c)** el caso
mínimo que lo reproduce, **(d)** si hay un test que debería haberlo cazado y no lo hizo (y por qué),
**(e)** la mutación (`M…`) que debería cubrirlo si es del alcance de la sonda. Un hallazgo sin caso
mínimo es una opinión.
