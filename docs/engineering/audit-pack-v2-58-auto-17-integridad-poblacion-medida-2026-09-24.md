# Audit-pack `AUTO-17` Integridad de la población de medida — `1.83.0-beta` (2026-09-24)

**Fase:** `V2.58` · **Rótulo:** `AUTO-17` · **Bump:** `1.82.0-beta` → **`1.83.0-beta`** · **Tag:**
`v2.58-beta` (cifras de CI en §11, añadidas en el commit de docs **posterior** al sello) · **Fase
anterior:** `V2.57` / `AUTO-16` (tag `v2.57-beta` → `c5e14ae1`, `Release tag CI` `35968175990`
**GREEN a la primera**, `1.82.0-beta`, PR de auditoría
[#66](https://github.com/jvelasca/Bolsa_V1/pull/66)).

**NO hay migración:** Alembic head sigue en **`046_fill_reference_mid`**. La base del R neto es
**recomputable** de `reference_mid` presente/ausente + la comisión del modelo, así que **no** se persiste
por ciclo y **no** hay backfill. Sin SHORT, sin UI nueva, sin cambio de contrato de API ni de DTO y **sin
clave nueva en el journal durable** (la proyección por lista blanca `_ALLOCATION_KEYS = ("riskMultipliers",
"evidenceAxis")`, `auto_adaptive_journal.py`, queda **byte a byte igual**). El gobernador y su evidencia
quedan **intactos**. Adaptive **sigue siendo recomendador read-only**.

**Ruta con el flag OFF:** el camino Adaptive **no se recorre** (ni lectura ni plan), así que el plan, el
journal y la API quedan **byte a byte iguales** a `v2.57`.

---

## 0. Resumen: qué instala esta pasada

`AUTO-16` hizo que el R neto **declarara su base** (`estimated` / `applied_friction+modelled_commission`),
pero dejó **dos huecos** que se midieron contra el árbol sellado:

1. **El round-trip del coste aplicado no era CUANTITATIVO.** `applied_cost.py` declaraba `COMPLETE` un
   ciclo con solo ver los dos lados, y se alimentaba de todos los `cycle_risk.keys()` (incluidos ciclos
   **abiertos**). Un `BUY 100 / SELL 10` medía la fricción de una ida y vuelta que **no terminó**: el
   SUELO entraba al neto como si fuera el total.
2. **La base del neto no viajaba de extremo a extremo.** El agregado **declaraba** `mixed` pero seguía
   **promediando** poblaciones de base distinta, y ni la confianza (`AUTO-12`) ni el reparto (`AUTO-8`
   Adaptive) veían la base. El número con el que se decide podía mezclar dos modelos de coste sin que
   nada lo dijera.

Esta pasada cierra los dos, sin migración y sin I/O nuevo:

1. **Round-trip cuantitativo** (`applied_cost.py`): `COMPLETE` exige **balance de cantidades**
   (`Σ buy qty == Σ sell qty`, tolerancia declarada) **además** de la presencia de lados; el balance usa
   cantidades **aunque falte `reference_mid`** (cierre y medición son ejes independientes). El mapa
   aplicado se restringe a los **`closed_cycle_ids`** que `cycles_from_fills` ya produce (autoridad de
   cierre FIFO), sin un segundo FIFO ni I/O nuevo.
2. **La base viaja con dos SERIES** (`auto_self_evaluation.py`): el agregado publica `NetRBasisSeries`
   por base; con base homogénea el `net_expectancy_r` pooled sale **byte a byte** como hoy, y con `MIXED`
   el pooled **no se publica** (`None`). La confianza gana `net_r_basis` + `basis_transition`, el `decay`
   devuelve `UNKNOWN` si la base cambia, y el **reparto solo adopta el eje del R neto si todas las
   versiones que compiten comparten una base estable**.

Superficie tocada: `applied_cost.py`, `auto_self_evaluation_feed.py`, `auto_self_evaluation.py`,
`auto_adaptive_confidence.py`, `auto_adaptive.py`, el docstring de `046_fill_reference_mid.py` (sin
cambio de esquema) y la sonda de mutaciones. **Sin ficheros de test nuevos** (los tests van en ficheros
ya registrados en los dos workflows; `packages/py/analytics/tests` entra por pase de directorio y los de
`packages/py/application/tests` ya están listados explícitamente).

---

## 1. El invariante: **ningún número con el que Adaptive decide promedia dos bases distintas**

> La base del R neto es una **dimensión estadística**: dos netos con el mismo aspecto y distinta base
> **no son comparables**. Si la base no viaja con el número, un cambio de medida se lee como un cambio de
> rendimiento. Un agregado que promedia dos bases mide una mezcla que no existe en el mercado.

De ahí las cinco reglas duras, todas con test y con mutación que las mata:

- **El round-trip se prueba con las cantidades.** `COMPLETE` exige lados **y** balance
  (`applied_cost_unbalanced_round_trip` si no cuadra); media ida y vuelta (`applied_cost_without_round_trip`)
  y las patas sin referencia (`applied_cost_without_reference`) son **SUELO**, no total.
- **El cierre lo declara `cycles_from_fills`.** Un ciclo fuera del conjunto cerrado declara su hueco
  (`applied_cost_without_cycle_closure`) y **jamás** publica fricción.
- **Dos series, nunca una media.** Con base homogénea el pooled es **byte a byte** el de `v2.57`; con
  `MIXED` el pooled es **`None`** y el número viaja en `net_r_series`.
- **Un salto de base no es señal.** `decay` devuelve `UNKNOWN` si `basis_transition` es `TRANSITION` o
  `MIXED`.
- **El eje del R neto exige base comparable.** `_allocation_weights` solo adopta `net_expectancy_r` si
  **todas** las versiones que compiten comparten una base **estable**; si no, cae al eje histórico con
  `ADAPTIVE_CELL_NOTE_BASIS_UNSTABLE`.

**La compatibilidad es parte del invariante:** `net_r_series=()` y `basis_transition=UNKNOWN` son
defectos seguros, así que el código viejo que no los declara conserva el comportamiento histórico (un
`UNKNOWN` **no** bloquea).

---

## 2. Sin migración: qué se declara y qué **no**

| Punto | `ruta:línea` |
| --- | --- |
| Alembic head (sin cambio) | `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py:38` |
| Guardia de head del repo (`_ALEMBIC_HEAD`) | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Docstring de `downgrade` (**DESTRUCTIVE DATA DOWNGRADE**) | `046_fill_reference_mid.py:85` |

- **La base no se persiste por ciclo**: se recomputa. Persistirla daría **dos** fuentes de verdad que
  pueden divergir, y `reference_mid` presente/ausente + comisión ya la determinan.
- **`downgrade` de `046` = DESTRUCTIVE DATA DOWNGRADE** (simetría de esquema ≠ reversibilidad de datos):
  bajar la migración **pierde** las referencias. Declarado en el docstring y aquí.
- **La guardia `_ALEMBIC_HEAD` NO cambió** (`046_fill_reference_mid`): al no haber migración, no hay
  riesgo del rojo que obligó a re-sellar `v2.56`.

---

## 3. El punto único del round-trip y el cierre

| Punto | `ruta:línea` |
| --- | --- |
| `AppliedLeg.quantity` (la cantidad sobrevive aunque falte el mid) | `applied_cost.py:121` |
| `applied_leg` (signo, magnitud, favorable, cantidad) | `applied_cost.py:175` |
| `_quantity_balanced` (tolerancia `_QTY`) | `applied_cost.py:222` |
| Notas nuevas (`unbalanced_round_trip`, `without_cycle_closure`) | `applied_cost.py:75` / `:79` |
| Agregado por ciclo (lados + balance) | `applied_cost.py:266` / `:267` |
| Autoridad de cierre en el mapa | `applied_cost.py:340` |
| **Único** pegador + cierre una sola vez | `auto_self_evaluation_feed.py:214` → `_cycles_with_risk` `:246` |

**Decisiones finas, medidas.**

- **Un solo FIFO.** `_cycles_with_risk` calcula `cycles_from_fills` **una vez** y reusa su
  `closed_cycle_ids`; el informe, la confianza y la rampa cuelgan del **mismo** material, sin un segundo
  FIFO que pueda divergir. **Cero I/O nuevo.**
- **Cierre y medición son ejes independientes.** Un BUY sin `reference_mid` **sí** cierra contra su SELL
  (aporta su cantidad al balance) pero el ciclo queda `PARTIAL`/suelo por la pata sin medir.
- **La cantidad ilegible no prueba el balance.** Un fill con cantidad no numérica hace que
  `_quantity_balanced` devuelva `False` → **no** `COMPLETE` (jamás se fabrica un `0`).

**Preguntas incómodas.**

- ¿Puede un ciclo con **tres** patas declararse `COMPLETE`? Sí, si compra y vende cuadran: la regla suma
  las patas y `legs` es el rastro. Lo mide
  `test_a_round_trip_that_balances_with_several_legs_is_complete`.
- ¿Se cuela un `0` por un ciclo no pedido? No: una ausencia se declara como hueco, nunca como coste.

---

## 4. Las series por base, la confianza y el reparto

| Punto | `ruta:línea` |
| --- | --- |
| `NetRBasisSeries` | `auto_self_evaluation.py:689` |
| Campo `net_r_series` en las dos filas | `auto_self_evaluation.py:755` / `:853` |
| `_net_r_series` (agrupa por base, determinista) | `auto_self_evaluation.py:1156` |
| `_basis_of` (declara `MIXED` si hay más de una serie) | `auto_self_evaluation.py:1180` |
| `_pooled_net_expectancy` (ausente si `MIXED`) | `auto_self_evaluation.py:1192` |
| `_basis_transition` (detector puro) | `auto_adaptive_confidence.py:268` |
| `_decay` gated por la transición | `auto_adaptive_confidence.py:290` / `:313` |
| `net_r_basis`/`basis_transition` + series en confianza | `auto_adaptive_confidence.py:355`/`:358`, `:403`/`:407` |
| `_net_basis_comparable` | `auto_adaptive.py:967` |
| Nota `ADAPTIVE_CELL_NOTE_BASIS_UNSTABLE` | `auto_adaptive.py:281` (uso `:1080`) |
| `StrategyHealth.net_r_basis` / `basis_transition` | `auto_adaptive.py:422` / `:423` |
| `evidence_for` publicando `netRBasis`/`basisTransition` | `auto_adaptive.py` (`evidence_for`) |
| Sello del reparto | `auto_adaptive.py:188` |

- **`ADAPTIVE_POLICY_VERSION` → `auto17-v1`**. **Aquí SÍ cambia la REGLA** (la condición que decide
  adoptar el eje del R neto), a diferencia de `AUTO-16`, donde solo cambiaba la **procedencia de un
  input**. Dos planes con la misma evidencia pueden diferir en los pesos según la base del grupo; sin
  subir el sello, esa diferencia sería invisible. **`DATA_GATE_POLICY_VERSION` NO se toca**
  (`auto15-v1`, `auto_adaptive_data_gate.py:76`).
- **La dimensión `strategy × regime × basis` se representa como las dos series**, no partiendo las
  celdas decisivas: así **no** se rompe `min_trades` (una celda no se fragmenta en dos muestras delgadas).
  Es la **decisión de producto** de la Opción A.
- **El pooled ausente no es un permiso**: quien decida con el neto debe leer `net_r_series` y exigir una
  base común. El `as_dict` publica `netRBasis`, `net_r_series` y (en el plan) `basisTransition`.

---

## 5. La costura (con CONTROL) y la compatibilidad

- **Costura hermética** (`test_auto_v57_auto16_applied_cost_seam.py`, **10** tests, por el camino real del
  worker): un grupo con una pata `estimated` y otra `applied` **no** mueve pesos por el delta de base
  (`test_a_group_that_mixes_cost_bases_does_not_move_weights_by_the_net_axis`); el eje cae a
  `ALLOCATION_AXIS_CURRENCY` y los multiplicadores **no** cambian.
- **Controles:** el grupo con **base única** sí mueve pesos por el neto, y el **histórico con salto de
  base** no cambia quién compite (`test_the_historical_basis_jump_does_not_change_who_competes`).
- **Compatibilidad byte a byte:** con base homogénea el pooled y el resto salen idénticos a `v2.57`; el
  camino sin `reference_mid` sigue publicando el número de `v2.56` y lo declara; los campos nuevos tienen
  defecto seguro.
- **Lo que NO se pudo medir aquí:** los runs de CI (no existen hasta empujar el tag) y la batería offline
  **completa** de los jobs del tag (recolectan suites PG que importan `asyncpg`, ausente en esta máquina).
  Ese límite lo cierra la CI del tag (§11).

---

## 6. Matriz de mutaciones (`M129…M138`): 10/10 muerden

| # | Mutación | Invariante que ataca | Detectada (tests en rojo) |
| --- | --- | --- | --- |
| `M129` | el agregado no exige **balance** de cantidades | ciclo abierto leído como ida y vuelta | `test_a_cycle_with_a_partial_exit_never_gets_an_applied_cost`, `test_a_reopened_cycle_is_not_complete_even_with_a_prior_round_trip`, `test_a_round_trip_with_unbalanced_quantities_is_not_complete` |
| `M130` | se ignora el **conjunto de cierre** | fricción de un ciclo no cerrado | `test_a_cycle_outside_the_closed_set_declares_its_gap_and_never_a_friction` |
| `M131` | con dos bases se **publica el pooled** | media de dos modelos de coste | `test_a_mixed_basis_is_declared_and_never_silently_averaged`, `test_a_historical_transition_is_declared_by_regime_without_splitting_the_cell` |
| `M132` | el desglose **colapsa** todas las bases en una | mezcla fundida antes de declararse | `test_a_mixed_basis_is_declared_and_never_silently_averaged`, `test_a_historical_transition_is_declared_by_regime_without_splitting_the_cell`, `test_a_row_without_a_declared_base_is_undeclared_not_completed` |
| `M133` | el detector nunca marca **TRANSITION** | salto de base leído como señal | `test_the_basis_transition_states_are_declared` |
| `M134` | el **decay** se calcula cruzando bases | deterioro sobre metros distintos | `test_a_window_that_spans_two_bases_declares_mixed_and_refuses_to_decay` |
| `M135` | el reparto adopta el eje **sin base comparable** | versiones compitiendo en ejes distintos | `test_allocation_refuses_to_mix_two_cost_bases_in_the_net_axis`, `test_allocation_refuses_a_group_with_an_explicitly_mixed_basis`, `test_the_historical_basis_jump_does_not_change_who_competes` |
| `M136` | una base **MIXED** no bloquea | población mixta entrando al eje del neto | `test_allocation_refuses_a_group_with_an_explicitly_mixed_basis` |
| `M137` | la **salud pierde la base** del neto | evidencia sin declarar la base | `test_strategy_health_publishes_the_net_basis_and_its_transition` |
| `M138` | la confianza **no lee** la base de la fila | transición invisible | `test_a_homogeneous_window_is_stable_and_keeps_the_historic_decay`, `test_a_stable_applied_window_is_declared_and_keeps_the_historic_decay`, `test_a_window_that_spans_two_bases_declares_mixed_and_refuses_to_decay` |

**Esperada / detectada / corregida / residual (punto #27 del auditor):**

| Etiqueta | Esperada | Detectada | Corregida | Residual |
| --- | --- | --- | --- | --- |
| `M129…M138` | 10 | **10** (0 en `NADA`) | la producción es correcta (la mutación se restaura byte a byte) | **0** |
| `M122`/`M125`/`M128` (realineadas) | 3 | **3** | ancla nueva, invariante intacto | **0** |
| `M32` (realineada) | 1 | **1** (5 tests) | ancla nueva (`_cycles_with_risk`) | **0** |

La corrida **completa** `M1…M138` está en §7. **Cuatro realineos declarados** (`M32`, `M122`, `M125`,
`M128`) porque su ancla cambió con esta fase: una sonda desalineada **afirma** cobertura que no tiene, así
que se realinea, no se borra.

---

## 7. Verificación (lo medido, y lo que no se pudo medir aquí)

- **Compuertas con el comando de CI** (no rutas sueltas):
  - `ruff check packages/py apps/api-python --config pyproject.toml` ⇒ **`All checks passed!`**
  - `mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent`
    ⇒ **`Success: no issues found in 499 source files`** (`0` errores; el contador **no** sube porque la
    fase no añade módulos nuevos).
  - `lint-imports --config packages/py/.importlinter` ⇒ **`4 kept, 0 broken`**.
- **Tramo de la fase: `245 passed`, `0` rojos** (ocho suites):

  | Fichero | Fase | `HEAD` |
  | --- | --- | --- |
  | `packages/py/application/tests/test_applied_cost.py` | **16** | 9 |
  | `packages/py/application/tests/test_auto_self_evaluation_feed.py` | **29** | 29 (sin cambios) |
  | `packages/py/analytics/tests/test_auto_self_evaluation.py` | **47** | 45 |
  | `packages/py/analytics/tests/test_auto_adaptive_confidence.py` | **25** | 21 |
  | `packages/py/analytics/tests/test_auto_adaptive.py` | **95** | 90 |
  | `apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py` | **10** | 9 |
  | `apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py` | **9** | 9 |
  | `apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py` | **14** | 14 |

  **19 tests nuevos** (7 + 2 + 4 + 5 + 1).
- **Delta simétrico FICHERO A FICHERO contra `HEAD`** (nunca restando totales). Se corrió **la versión de
  `HEAD` de cada fichero de test modificado** contra el árbol de la fase; los rojos que salen son los
  **declarados de antemano**, y **solo ésos**: **6** rojos.

  | Fichero | `HEAD` vs fase | Rojos | Causa declarada |
  | --- | --- | --- | --- |
  | `packages/py/analytics/tests/test_auto_adaptive.py` | `2 failed, 88 passed` (`65314` B → `71252` B) | **2** | el **sello** (`auto16-v1` → `auto17-v1`) |
  | `packages/py/analytics/tests/test_auto_self_evaluation.py` | `1 failed, 44 passed` (`35175` B → `38553` B) | **1** | el pooled **mixto** ya no se promedia (`None`) |
  | `packages/py/analytics/tests/test_auto_adaptive_confidence.py` | `21 passed` (`15987` B → `21099` B) | **0** | — (campos nuevos con defecto seguro) |
  | `packages/py/application/tests/test_applied_cost.py` | `9 passed` (`7162` B → `11103` B) | **0** | — (tests nuevos **aditivos**) |
  | `apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py` | `1 failed, 8 passed` (`11263` B → `11314` B) | **1** | el **sello** |
  | `apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py` | `1 failed, 13 passed` (`15482` B, **idéntico**) | **1** | el **sello** (`auto16-v1` → `auto17-v1`, mismo ancho) |
  | `apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py` | `1 failed, 8 passed` (`19153` B → `20950` B) | **1** | el reparto **mixto** ya no mueve pesos por el neto |
  | Controles **sin cambios** `test_auto_self_evaluation_feed.py` / `test_cycle_risk.py` / `test_auto_adaptive_entry.py` / `test_auto_adaptive_journal.py` / `test_auto_v52_auto11_adaptive_state_seam.py` | `29` / `33` / `9` / `13` / `21` passed | **0** | — |

  **No hay rojo residual ni rojo corregido dentro de la fase:** los 6 rojos son **esperados** (el sello y
  el cambio de comportamiento de la población mixta) y **no** se «arreglan» en el código de producción
  porque son exactamente lo que la fase promete.
- **Matriz de mutaciones COMPLETA** (`M1…M138`): **`138/138` muerden**, **`0`** etiquetas en `NADA`,
  **`0`** fragmentos ausentes, restauración **byte a byte** y huella `git status` **idéntica** antes y
  después (`intacto: la sonda no altero el arbol`). **Cuatro realineos declarados** (§6).
- **Batería de CI `quality` (selección exacta del YAML, sin PG):**
  `2695 passed, 0 skipped, 0 failed` en `94.15s`. Es el mismo conjunto que el job `quality` del tag,
  corrido en local con `uv run --no-sync python -m pytest` (en esta máquina `uv run pytest` lo bloquea
  Control de aplicaciones). **Cero rojos y cero skips.**
- **Gobernador y contrato durable intactos** (medido): `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py`
  y `git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py` ⇒ **vacíos**.
- **Lo que no se pudo medir aquí:** los runs de CI y la batería **completa con PG real** del tag (las
  suites PG necesitan PostgreSQL y, en el job `python` del tag, van en jobs dedicados). **Ese límite lo
  cierra la CI del tag** (§11).

---

## 8. Límites declarados (no silenciosos)

- **La comisión aplicada NO existe en SIM.** El neto aplicado se completa con la comisión **del modelo** y
  la base lo nombra (`applied_friction+modelled_commission`): no se finge un coste realizado completo.
- **Las cantidades se comparan con tolerancia declarada** (`_QTY`); un fill con cantidad ilegible hace que
  el ciclo **no** se declare `COMPLETE` (nunca un `0` fabricado).
- **No hay backfill.** El histórico pre-2.57 no tiene referencia: esos ciclos se miden con el estimado
  **y lo declaran** (`STABLE_ESTIMATED`).
- **La base no se persiste por ciclo** (se recomputa): no hay migración ni dos fuentes de verdad.
- **El flag Adaptive sigue OFF**: sin él no hay plan, ni lectura, ni encogimiento.
- **Fuera de alcance, sin tocar:** UI, SHORT, el `gap` del modelo dentro del neto aplicado y el resto de
  preguntas abiertas del §9 del arranque del auditor.

---

## 9. Freeze respetado

No se toca el sello de `V2.53`…`V2.57` (`auto13-v1`…`auto16-v1`), `auto_adaptive_journal.py` (**byte a
byte igual**), el contrato de `decision_journal_entries`, `yahoo_circuit_breaker.py`,
`ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación, el **gobernador**
(`v2_43_governor_evidence.py`: **diff vacío**) ni la tabla estado→efecto del gate
(`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`). **Sin UI**, sin SHORT, sin backfill; `*.md` **sin
`prettier`**; `governor.json` sigue **sin trackear**.

---

## 10. Sellado

El paquete de cierre (este pack, el [relevo](./traspaso-relevo-post-v2.58-auto-17-integridad-poblacion-medida-2026-09-24.md),
el [arranque del auditor](./arranque-auditor-v2.58-auto-17-integridad-poblacion-medida-2026-09-24.md) y el
[del agente siguiente](./arranque-agente-post-v2.58-auto-17-2026-09-24.md), `CHANGELOG.md`,
`PROJECT_STATE.md`, el índice y el bump `1.83.0-beta`) viaja **dentro** del tag. **Excepción declarada:**
esta §11 con los runs de CI **medidos** se añade en el commit de docs **posterior** al sello (mismo patrón
que `AUTO-13`…`AUTO-16`): el run del tag no existe hasta que el tag se empuja, así que la tabla se
**mide** en lugar de predecirse.

**Superficie de auditoría (post-sello, declarada):** el **PR draft #67**
(`auto-17-integridad-poblacion-medida` → `audit-base-v2.57-beta`) se abre **después** del sello para que
el auditor externo revise el delta con comentarios en línea. Su diff medido es el de la fase y **no** es
vehículo de merge: `main` ya la recibió en **fast-forward**.

---

## 11. CI del sello `v2.58-beta` (medida, no predicha)

**Se mide, no se predice:** el run del tag no existe hasta que el tag se empuja, así que estas cifras se
añaden en el **commit de docs posterior al sello** (mismo patrón que `AUTO-13`…`AUTO-16`), citando cada
una el run que la produjo.
