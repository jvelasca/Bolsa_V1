# Audit-pack `AUTO-16` Coste REAL por ciclo — `1.82.0-beta` (2026-09-24)

**Fase:** `V2.57` · **Rótulo:** `AUTO-16` · **Bump:** `1.81.0-beta` → **`1.82.0-beta`** · **Tag:**
`v2.57-beta` (cifras de CI en §11, añadidas en el commit de docs **posterior** al sello) · **Fase
anterior:** `V2.56` / `AUTO-15` (tag `v2.56-beta` → `8ad54416`, `Release tag CI` `35928080874`
**GREEN**: `10 success` + `1 skipped`, job `python` del tag **`2608 passed / 35 skipped`**, PR de
auditoría [#65](https://github.com/jvelasca/Bolsa_V1/pull/65)).

**SÍ hay migración:** Alembic head `045_adaptive_gate_state` → **`046_fill_reference_mid`** (aditiva,
**una columna `NULL`able, sin backfill**, `upgrade`/`downgrade` **simétricos e idempotentes**). Sin
SHORT, sin UI nueva, sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal
durable** (la proyección por lista blanca `_ALLOCATION_KEYS = ("riskMultipliers", "evidenceAxis")`,
`auto_adaptive_journal.py`, queda **byte a byte igual**). El gobernador y su evidencia quedan
**intactos**. Adaptive **sigue siendo recomendador read-only**.

**Ruta con el flag OFF:** el camino Adaptive **no se recorre** (ni lectura ni plan), así que el plan,
el journal y la API quedan **byte a byte iguales** a `v2.56`. La única diferencia medible es **el
valor de una columna nueva** que el settlement **ya escribía** (la fila del contexto del fill es la
misma: no hay fila nueva, ni escritura nueva, ni lectura nueva) y que **con el flag OFF nadie lee**.

---

## 0. Resumen: qué instala esta pasada

`AUTO-9` midió el R de cada ciclo con el coste que el **decisor supuso** en la reserva
(`TradingCost`). Ese R neto es el eje con el que `AUTO-12`/`AUTO-13`/`AUTO-14` encogen, rampean y
reparten… pero el coste que **de verdad se pagó** nunca entraba en la cuenta:

```
reserva (coste ESTIMADO 25.0) ─┐
fills SIM (fricción APLICADA 2.5, con su mid de referencia) ─┴─► R neto = pnl − 25.0   ← se decide con el supuesto
```

El simulador **construye** el precio de cada fill sobre un mid con una fricción determinista y
adversa (`simulated_broker.simulated_fill_schedule`). Esa fricción es **medible**
(`|price − reference_mid| × qty`), no es reconstruible desde el precio (el precio ya la lleva dentro)
y **no se persistía en ningún sitio**: el mid vivía en la memoria del tick que construyó el schedule
y se tiraba. La pata de **entrada** de un ciclo se liquida en otro tick, así que un cálculo en
memoria tampoco bastaba: cubriría media fricción y perdería la otra al reiniciar.

Esta pasada la **persiste** y la usa **declarando la base**:

1. **Columna nueva** `sim_fill_finance_context.reference_mid` (`Numeric(18,6)`, `NULL`able, sin
   backfill) — migración `046_fill_reference_mid`.
2. **Módulo puro nuevo** `applied_cost.py`: la fricción aplicada por **pata** y su agregado por
   **ciclo** (ida y vuelta), con la medición declarada (`COMPLETE`/`PARTIAL`/`UNKNOWN`) y sin
   fabricar jamás un `0`.
3. **El settlement** persiste el mid con el que construyó el precio (misma escritura de siempre).
4. **`CycleRisk.cost_applied`** + el pegador puro `attach_applied_cost`, cableado **en un solo
   punto** de la alimentación (informe `AUTO-7`, confianza `AUTO-12` y rampa `AUTO-13` cuelgan de
   él) **sin I/O nuevo**: los fills que ya se leían llevan su referencia.
5. **El R neto declara su BASE** (`CycleR.cost_basis` / `netRBasis` en el agregado): el coste que
   entra al cociente es la fricción **aplicada + la comisión del modelo** cuando está medida, o el
   **estimado** de siempre cuando no — y **cuál de los dos** viaja en el número. El sello del
   reparto sube a **`auto16-v1`** (cambia la **procedencia de un input**, no la regla).

Superficie nueva: `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py`,
`packages/py/application/src/bolsa_application/applied_cost.py`, las costuras
`apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py` (**9** tests) y
`apps/api-python/tests/test_auto_v57_auto16_applied_cost_pg.py` (**5** tests), más los unit
`packages/py/application/tests/test_applied_cost.py` (**9**) y
`packages/py/application/tests/test_sim_fill_reference.py` (**9**).
Superficie tocada: `auto_self_evaluation.py` (base declarada, `CycleR`, la comisión del modelo),
`cycle_risk.py` (`cost_applied` + pegador), `auto_self_evaluation_feed.py` (el punto único),
`sim_durable_store.py` (`reference_mid` + lector por ciclo), `sim_finance_context.py`,
`simulated_settlement.py`, `tables.py` (columna ORM), `auto_adaptive.py` (sello), los dos workflows
de CI y la sonda de mutaciones.

---

## 1. El invariante: **el neto declara su BASE, nunca se adivina cuál de los dos costes es**

> El R neto es un cociente contra un coste, y ese coste puede venir de **dos modelos distintos**: el
> que el **decisor supuso** y el que el **simulador aplicó**. Dos netos con el mismo aspecto pero
> distinta base **no son comparables**: si la base no viaja con el número, un cambio de procedencia
> se lee como un cambio de rendimiento.

De ahí las cinco reglas duras, todas con test y con mutación que las mata:

- **La base se publica con el número, siempre** (`costBasis` por ciclo, `netRBasis` por agregado):
  `applied_friction+modelled_commission` / `estimated`, y `mixed`/`undeclared` cuando un agregado
  promedia bases distintas o ninguna fila declara. Nunca se promedian dos bases en silencio.
- **El aplicado se completa con la comisión del MODELO, y la base lo nombra.** El schedule del
  simulador **no cobra comisión** (en SIM es `0` en los fills con `fill_id`): un neto que restara
  solo la fricción saldría **más alto** por un motivo que no es una mejor ejecución, sino una parte
  del coste que se dejó fuera. Y sin comisión cuantificada **no se compone a medias**: el neto vuelve
  al estimado completo y lo declara.
- **Un `PARTIAL` no entra al neto.** Media ida y vuelta (o una pata sin referencia) es un **SUELO**:
  restarlo sobrestimaría el R del ciclo. Se publica la medición y el ciclo queda con el estimado.
- **Sin referencia no hay fricción, y jamás es `0`.** Una fila anterior a `2.57` o un mid que no es
  un precio deja la pata **sin medir**: publicar `0` diría «fricción gratis», que es regalar R.
- **La fricción es un COSTE, nunca una rebaja.** El monto es la **magnitud** del desvío contra el
  mid; una pata favorable (imposible en el schedule adverso) se mide pero se **declara**
  (`applied_cost_favourable_leg`) en vez de restar.

**Corolario de compatibilidad:** la lectura vieja **sigue leyéndose**. `costEstimate` se publica
igual que en `v2.56`, `costApplied`/`costBasis` se **añaden**, y el camino sin referencia produce
**el mismo número de `v2.56` byte a byte** (medido en la costura, §5).

---

## 2. La migración: una columna, sin backfill, con `downgrade` simétrico

| Punto | `ruta:línea` |
| --- | --- |
| `revision` / `down_revision` | `046_fill_reference_mid.py:38` / `:39` |
| `op.add_column(reference_mid, Numeric(18,6), nullable=True)` | `046_fill_reference_mid.py:71` |
| `downgrade` (drop de la MISMA columna) | `046_fill_reference_mid.py:85` |
| Columna ORM (espejo del esquema) | `tables.py:2248` |
| Guardia de head del repo (`_ALEMBIC_HEAD`) | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |

**Decisiones finas, medidas.**

- **Aditiva y `NULL`able, sin backfill.** No hay valor que inventar para las filas anteriores: la
  ausencia de referencia **es** el hecho (el mid no se midió). Un `0` de relleno sería «fricción
  gratis» en todo el histórico.
- **Idempotente** (el patrón de las `028`–`045`: la columna se comprueba antes de crearse) y con
  `downgrade` **simétrico**: `upgrade`/`downgrade`/`upgrade` se corre en el test PG (§5).
- **La guardia de head se bumpea en el MISMO paso 1** —`045` → `046`—, que es exactamente el rojo
  que obligó a re-sellar `v2.56` (pack `v2.56`, §11.1). Aquí se corrige **antes** de empujar el tag.

**Preguntas incómodas.**

- ¿Puede quedar una fila con `reference_mid` a `0` (que diría «fricción gratis»)? El contexto
  **normaliza y valida** al construirse (`usable_reference_mid`, `sim_durable_store.py:64`): un
  valor que no describe un precio (`None`, `NaN`, `≤ 0`) se guarda como **ausencia**. Lo mide `M126`
  y `M123`.
- ¿Y si el `downgrade` deja la columna y el `upgrade` la vuelve a crear con otro tipo? El roundtrip
  del test PG lo mide contra PostgreSQL real.

---

## 3. El punto único: la fricción aplicada se recompone **sin I/O nuevo**

| Punto | `ruta:línea` |
| --- | --- |
| Fricción de UNA pata (signo, magnitud, favorable) | `applied_cost.py:157` (`signed` en `:187`) |
| Agregado por ciclo (ida y vuelta, `PARTIAL` no es total) | `applied_cost.py:200` (`round_trip` en `:220`) |
| Una entrada por ciclo pedido, con sus huecos | `applied_cost.py:244` |
| Predicado del `COMPLETE` | `applied_cost.py:274` |
| Vocabulario de notas (`without_reference`, `favourable_leg`, `without_round_trip`) | `applied_cost.py:58`/`:67` |
| El **único** pegador (informe + confianza + rampa cuelgan de él) | `auto_self_evaluation_feed.py:214` → `:232` |
| `CycleRisk.cost_applied` + su medición | `cycle_risk.py:145` / `:157` |
| `to_cycle_fields` (publica `costApplied` CON su medición) | `cycle_risk.py:161` |
| `attach_applied_cost` (puro) | `cycle_risk.py:348` |
| Escritura del mid en el settlement (misma escritura de siempre) | `simulated_settlement.py:331` |
| Normalización + persistencia en el contexto | `sim_finance_context.py:61` / `:78` |
| Lector por ciclo (verificación, NO en el tick) | `sim_durable_store.py:300` (memoria) / `:581` (PG) |

**Decisiones finas, medidas.**

- **Un solo productor.** El aplicado se pega en **un** punto (`_risk_with_applied_cost`) por el que
  pasan las tres lecturas que lo consumen: dos productores podrían medir un coste distinto en
  silencio.
- **Cero I/O nuevo.** Los fills que el tick **ya** leía para reconstruir los ciclos llevan su
  `reference_mid`; el agregado por ciclo es aritmética pura. Medido en el test de la costura: **una**
  lectura de fills por versión (la de siempre) y **cero** lecturas por ciclo
  (`list_by_cycle_ids` existe como **lector de verificación** del reinicio, no como I/O del turno).
- **Persistir la referencia NO está gateado por el flag, y se declara.** El plan decía «gateado por
  el flag»; la medida dice que la columna viaja en la escritura del settlement **que ya existía**
  (misma fila, sin I/O nuevo) y lo que el flag gatea es su **uso**. Gatear la **escritura** por el
  flag dejaría un hueco **permanente** en el histórico el día que se encienda la lectura: el dato que
  falta no se puede recuperar después. Es la misma decisión que `AUTO-9` tomó con `cycle_id` (`044`).
- **El lector por ciclo acota por cuenta en SQL.** Un fill de otra cuenta **no** aporta la fricción
  de este ciclo (lo mide `M124` y lo certifica el test PG).

**Preguntas incómodas.**

- ¿Puede un ciclo agregar **tres** patas (una entrada partida en dos fills) y declararse `COMPLETE`
  con la ida y la vuelta cubiertas? Sí: la regla exige **las dos direcciones**, y suma las patas
  medidas; el número de patas queda en `legs`, que es el rastro de la suma.
- ¿Se puede colar una pata **favorable** como descuento? No: se mide en magnitud y se declara
  (`applied_cost_favourable_leg`); lo mide el unit del módulo.

---

## 4. La declaración: base por ciclo, base por agregado y sello `auto16-v1`

| Punto | `ruta:línea` |
| --- | --- |
| Bases del ciclo (`applied_friction+modelled_commission` / `estimated`) | `auto_self_evaluation.py:130` |
| `mixed` / `undeclared` del agregado | `auto_self_evaluation.py:132` |
| Comisión del MODELO (o `None` ⇒ no se compone) | `auto_self_evaluation.py:195` |
| `cycle_r` (el cociente y su base) | `auto_self_evaluation.py:435` |
| `CycleR.cost_applied` / `cost_basis` | `auto_self_evaluation.py:416`/`:420` |
| Base del agregado (`_net_r_basis`) | `auto_self_evaluation.py:1124` |
| `netRBasis` en las dos filas del informe | `auto_self_evaluation.py:768`/`:839` |
| Sello del reparto | `auto_adaptive.py:175` |

- **`ADAPTIVE_POLICY_VERSION` → `auto16-v1`** (`auto_adaptive.py:175`). **No** cambia la regla
  —ninguna condición de `_allocation_weights` se toca— pero **sí la procedencia de un input** del eje
  del R neto: dos planes con la misma evidencia pueden diferir en los pesos porque el neto se midió
  contra otro modelo de coste. Sin subir el sello, esa diferencia sería invisible. Es el mismo
  criterio con el que `AUTO-15` subió el del gate; **`DATA_GATE_POLICY_VERSION` NO se toca**
  (sigue `auto15-v1`).
- **El sello SÍ se compara** (a diferencia del sello del gate en `AUTO-15`): vive en el journal del
  reparto y marca las filas históricas como de otra política —declarado, medido en la costura—.
- **`netRBasis` es aditivo y con defecto seguro.** El campo nuevo de las dos filas del informe tiene
  defecto `None` (= «no declarada»): una fila construida por un consumidor viejo **no afirma** una
  base, igual que `sinkFailuresDurable` no afirma durabilidad. Medido: los tres ficheros de test que
  construían `StrategySelfEvaluation` sin el campo **siguen pasando sin tocarlos** (delta §7).
- **La declaración NO se convierte en permiso.** `decisive` sigue exigiendo el R **bruto** medido; el
  neto se lee con `netRMeasurement == COMPLETE` **y** su base. El `as_dict` del informe publica los
  dos hechos por separado (§6.3 de `AUTO-9` sigue intacto).

---

## 5. La costura (con CONTROL) y la certificación contra PostgreSQL real

- **Costura hermética** (`test_auto_v57_auto16_applied_cost_seam.py`, **9** tests, por el camino real
  del worker): la fricción de las **dos** patas del ciclo llega al neto que lee el plan
  (`(297.5 − 2.5 − 5.0)/250 = 1.16`, no el `1.09` del estimado); la base viaja en la lectura; el
  aplicado **mueve los pesos** del reparto (la consecuencia que justifica el sello); **control
  negativo**: con el MISMO material y solo sin `reference_mid`, el ciclo declara el hueco y el neto es
  el estimado de `v2.56` **byte a byte**; y **control de la composición**: sin comisión cuantificada,
  el neto **no** se compone a medias (vuelve al estimado y la medición se sigue publicando); y la
  **pata de entrada liquidada en otro tick** se lee con la de salida.
- **Cero I/O nuevo, medido**: `version_reads == 2` (una por versión, lo que ya hacía `AUTO-9`) y
  `cycle_reads == 0`. Con el flag **OFF**, el constructor del plan no se invoca.
- **PG real** (`test_auto_v57_auto16_applied_cost_pg.py`, **5** tests, job `auto-v2-durable-pg` con
  `APPLIED_COST_PG_REQUIRED=1`): roundtrip de la `046` (`upgrade`/`downgrade`/`upgrade`), la
  `reference_mid` **sobrevive a una sesión nueva** y la fricción se **recompone fuera del proceso**
  que la midió (las dos patas), una fila sin referencia se declara sin fricción (jamás `0`), y la
  lectura por ciclo **no cruza cuentas**.

---

## 6. Matriz de mutaciones (`M119…M128`): 10/10 muerden

| # | Mutación | Invariante que ataca |
| --- | --- | --- |
| `M119` | el pegador devuelve la evidencia **intacta** | el aplicado **no llega** al neto |
| `M120` | el neto **suma** el coste en vez de restarlo | la fricción leída como **rebaja** |
| `M121` | el neto aplicado **no** lleva la comisión del modelo | coste adjudicado **de más** en cada ciclo |
| `M122` | el agregado no exige **ida y vuelta** | un **suelo** leído como el total |
| `M123` | un fill sin mid se mide **contra su precio** | fricción **`0`** inventada |
| `M124` | el lector por ciclo no casa la **cuenta** | fricción **ajena** en el neto |
| `M125` | la procedencia cambia y el **sello no** | dos modelos de coste sin declararlo |
| `M126` | el contexto del fill **pierde** su mid | persistencia **aparente** |
| `M127` | la base `applied` se declara **sin medición** | etiqueta del medido con el supuesto dentro |
| `M128` | el agregado **no declara** la mezcla de bases | dos modelos promediados como uno |

La corrida **completa** de la matriz está en §7.

---

## 7. Verificación (lo medido, y lo que no se pudo medir aquí)

- **Compuertas §3 del relevo, con el comando de CI** (no rutas sueltas):
  `ruff check packages/py apps/api-python --config pyproject.toml` **`All checks passed!`**;
  `mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent`
  **`0` errores en `499` ficheros** (`498` → `499`: el módulo puro nuevo);
  `lint-imports --config packages/py/.importlinter` ⇒ **`4 kept, 0 broken`**.
- **Unit de la fase:** `test_applied_cost.py` (**9** tests, nuevo: signo por dirección, ida y vuelta,
  media ida declarada, sin referencia jamás `0`, pata favorable declarada, patas inutilizables,
  ciclos no pedidos ignorados, rastro de patas medidas) y `test_sim_fill_reference.py` (**9** tests,
  nuevo: la referencia sobrevive al store y se lee por ciclo, la pata de otro tick se recompone,
  ciclos sin fill y fills sin ciclo no fabrican ceros, la cuenta ajena no casa, un mid inutilizable
  se guarda como ausencia y uno usable se normaliza a `Decimal`).
- **Costura nueva** `test_auto_v57_auto16_applied_cost_seam.py` (**9** tests) con **dos controles**
  (sin referencia ⇒ el número de `v2.56`; sin comisión ⇒ no se compone a medias).
- **PG real** `test_auto_v57_auto16_applied_cost_pg.py` (**5** tests) contra el PostgreSQL del
  compose: **`5 passed`** — roundtrip de la `046`, reinicio real, fila legacy declarada, cuenta ajena
  fuera.
- **Tramo de la fase:** `test_applied_cost.py` (9) + `test_sim_fill_reference.py` (9) +
  `test_auto_v57_auto16_applied_cost_seam.py` (9) + `test_auto_self_evaluation.py` (45) +
  `test_cycle_risk.py` (33) ⇒ **`105 passed`** (`+ PG 5` ⇒ **`110`**), `0` rojos.
- **Delta simétrico FICHERO A FICHERO contra `HEAD`** (nunca restando totales). Se corrió **la
  versión de `HEAD` de cada fichero de test modificado** contra el árbol de la fase; los rojos que
  salen son los **declarados de antemano** (el sello del reparto y la guardia de head de Alembic), y
  **solo ésos**:

  | Fichero | `HEAD` vs fase | Rojos | Causa declarada |
  | --- | --- | --- | --- |
  | `packages/py/analytics/tests/test_auto_adaptive.py` | `2 failed, 88 passed` (`65225` B → `65314` B) | **2** | el **sello** (`auto14-v1` → `auto16-v1`) |
  | `packages/py/analytics/tests/test_auto_self_evaluation.py` | `38 passed` (`29684` B → `35175` B) | **0** | — (los tests nuevos son aditivos) |
  | `packages/py/application/tests/test_cycle_risk.py` | `26 passed` (`18685` B → `24103` B) | **0** | — |
  | `packages/py/application/tests/test_auto_adaptive_entry.py` | `9 passed` (`12117` B, **idéntico**) | **0** | — (campo nuevo con defecto) |
  | `packages/py/application/tests/test_auto_adaptive_journal.py` | `13 passed` (`9528` B, **idéntico**) | **0** | — |
  | `apps/api-python/tests/test_auto_v52_auto11_adaptive_state_seam.py` | `21 passed` (`22044` B, **idéntico**) | **0** | — |
  | `apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py` | `1 failed, 8 passed` (`11226` B → `11263` B) | **1** | el **sello** |
  | `apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py` | `1 failed, 13 passed` (`15482` B) | **1** | el **sello** |
  | `apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py` | `6 passed` (`15898` B → `15950` B) | **0** | — |
  | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py` | `5 failed, 14 passed` (`38306` B → `38305` B) | **5** | la **guardia de head** (`045` → `046`), solo en los jobs PG |
  | `test_applied_cost.py`, `test_sim_fill_reference.py`, `test_auto_v57_auto16_*` | **no existen en `HEAD`** | — | superficie **nueva** de la fase |

  **Rojo declarado y corregido en el propio delta (no silenciado):** la primera medición mostró **76
  rojos** más en `test_auto_adaptive.py` (y `TypeError` en tres ficheros más) porque el campo
  `netRBasis` se había añadido **sin defecto**. Se midió, se corrigió **en la fase** (§4: defecto
  `None` = «no declarada», el trato de `sinkFailuresDurable`) y el delta quedó en los **9** rojos
  declarados. **Se publica la cifra medida, no la que habría sido cómoda.**
- **Matriz de mutaciones COMPLETA** (`M1…M128`): **`128/128` muerden**, **`0`** etiquetas en `NADA`,
  **`0`** fragmentos ausentes, restauración **byte a byte** y huella `git status` **idéntica** antes y
  después (`intacto: la sonda no altero el arbol`). **Un realineo declarado y medido:** la primera
  corrida de la matriz encontró **`M32`** con el **fragmento ausente** (la llamada de `AUTO-9`
  `apply_cycle_risk(..., cycle_risk)` dejó de existir tal cual al entrar la fricción aplicada en el
  **mismo** sitio; la sonda apuntaba ahí). Un fragmento ausente **afirma cobertura que no tiene**, así
  que la sonda se **realineó a la llamada del informe** —que es donde su invariante vive— y vuelve a
  morder en **5** tests (dos de ellos de `AUTO-16`). Se publica la corrida **anterior** en rojo y la
  **posterior** en verde, no una sola cifra.
- **Gobernador y contrato durable intactos** (medido): `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py`
  y `git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py` ⇒ **vacíos**.
- **Lo que no se pudo medir aquí:** la batería offline **completa** de los jobs `quality`/`python` del
  tag (su recolección incluye suites PG que importan `asyncpg`, ausente en esta máquina) y los runs de
  CI (no existen hasta empujar). **Ese límite lo cierra la CI del tag** (§11), medida — y además, con el
  PostgreSQL del **compose** levantado, la batería entera se re-corrió en local: **`4024 passed / 1
  xfailed / 0` rojos** (§11.4).

---

## 8. Límites declarados (no silenciosos)

- **La comisión aplicada NO existe en SIM.** El neto aplicado se completa con la comisión **del
  modelo** y la base lo nombra (`applied_friction+modelled_commission`): no se finge un coste
  realizado completo. Un broker real cobraría una comisión distinta (o ninguna), y eso exigiría otra
  fase y otra fuente.
- **Solo se persiste la referencia**, no la fricción: una sola fuente de verdad, y la aritmética es
  pura y auditable (`|price − reference_mid| × qty`). Persistir la fricción además daría **dos**
  fuentes que pueden divergir.
- **No hay backfill.** El histórico anterior a `2.57` no tiene referencia: esos ciclos se miden con el
  estimado **y lo declaran**. Es un hueco honesto, no un cero.
- **La referencia se mide contra el mid del simulador**, no contra un precio de mercado: lo que se
  mide es la fricción que **este** simulador aplicó.
- **El flag Adaptive sigue OFF**: sin él no hay plan, ni lectura de la referencia, ni encogimiento.
- **Fuera de alcance, sin tocar:** UI, SHORT, `gap` del modelo dentro del neto aplicado y el resto de
  preguntas abiertas del §9 del arranque del auditor.

---

## 9. Freeze respetado

No se toca el sello de `V2.53`/`V2.54`/`V2.55`/`V2.56`, `auto_adaptive_journal.py` (**byte a byte
igual**), el contrato de `decision_journal_entries`, `yahoo_circuit_breaker.py`,
`ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación, el **gobernador**
(`v2_43_governor_evidence.py`: **diff vacío**) ni la tabla estado→efecto del gate. **Sin UI**, sin
SHORT, sin backfill; `*.md` **sin `prettier`**; `governor.json` sigue **sin trackear**.

---

## 10. Sellado

El paquete de cierre (este pack, el [relevo](./traspaso-relevo-post-v2.57-auto-16-coste-real-por-ciclo-2026-09-24.md),
el [arranque del auditor](./arranque-auditor-v2.57-auto-16-coste-real-por-ciclo-2026-09-24.md) y el
[del agente siguiente](./arranque-agente-post-v2.57-auto-16-2026-09-24.md), `CHANGELOG.md`,
`PROJECT_STATE.md`, el índice y el bump `1.82.0-beta`) viaja **dentro** del tag. **Excepción
declarada:** esta §11 con los runs de CI **medidos** se añade en el commit de docs **posterior** al
sello (mismo patrón que `AUTO-13`/`AUTO-14`/`AUTO-15`): el run del tag no existe hasta que el tag se
empuja, así que la tabla se **mide** en lugar de predecirse.

**Superficie de auditoría (post-sello, declarada):** el **PR draft #66** (`auto-16-coste-real-por-ciclo`
→ `audit-base-v2.56-beta`) se abre **después** del sello para que el auditor externo revise el delta
con comentarios en línea. Su diff medido es el de la fase y **no** es vehículo de merge: `main` ya la
recibió en **fast-forward**.

---

## 11. CI del sello `v2.57-beta` (medida, no predicha)

**Se mide, no se predice:** el run del tag no existe hasta que el tag se empuja, así que estas cifras se
añaden en el **commit de docs posterior al sello** (mismo patrón que `AUTO-13`/`AUTO-14`/`AUTO-15`),
citando cada una el run que la produjo.

### 11.1 El CI del tag salió VERDE **a la primera** (la guardia se bumpeó en el paso 1)

**Contraste medido con el sello anterior:** el tag `v2.56-beta` obligó a un **fix + re-sello** porque la
guardia `_ALEMBIC_HEAD` (`apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43`, **5**
aserciones) no se bumpeó con la migración `045`, y esos 5 rojos **solo** aparecen en los jobs PG, que la
matriz offline ignora. En `AUTO-16` la guardia se bumpeó `045` → `046` **en el MISMO paso 1**, su delta
simétrico se midió **antes** de empujar (`HEAD` ⇒ `5 failed, 14 passed`; fase ⇒ `19 passed`, §7) y el
primer —y único— empuje del tag salió **verde**: los **tres** jobs PG (`auto-v2-durable-pg`,
`grammar-discovery-pg`, `lifecycle-pg`) cerraron en `success`. **No hubo re-sello.**

### 11.2 Cifras medidas del sello

| Corte | Run | Resultado |
| --- | --- | --- |
| `Release tag CI` (`c5e14ae1`) | [`35968175990`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35968175990) | **GREEN a la primera**: **`10 success` + `1 skipped`** (`playwright (integrated E2E, opt-in)`) y `certify (aggregate + artifact)` en `success` |
| `python` del tag | job del run anterior | ruff **`All checks passed!`** · mypy **`Success: no issues found in 499 source files`** · pytest **`2649 passed / 35 skipped`** (**+41** passed y **0** skips nuevos sobre los `2608 / 35` de `v2.56`) |
| `Python CI` del tag (per-commit) | [`35968176009`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35968176009) | **`5/5` jobs `success`**: `quality` (**`2638 passed / 38 skipped`**), `auto-v2-durable-pg` (la `046` + la guardia + el test PG nuevo de la fase), `grammar-discovery-pg`, `paper-forward-pg` y `lifecycle-pg` |
| `Python CI` de `main` (per-commit) | [`35968177267`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35968177267) | **`5/5` jobs `success`** |
| `check-runs` del commit sellado `c5e14ae1` | API de checks | **`27 success` + `1 skipped`** |

### 11.3 El límite declarado del §7, cerrado por la CI del tag

El §7 declaró dos cosas que **no** se podían medir en esta máquina: (a) los runs de CI —«no existen hasta
empujar»— y (b) la batería offline **completa** de los jobs `quality`/`python` del tag, cuya recolección
incluye suites PG que importan `asyncpg` (ausente aquí). **El tag las cierra las dos**: `2649 passed / 35
skipped` en el job `python` del tag y `2638 passed / 38 skipped` en `quality` del per-commit, con **`5/5`**
jobs verdes en los dos `Python CI` (los cuatro de PG incluidos, que son justo los que la matriz offline
**no** puede correr). **Cero rojos y cero skips nuevos** respecto de `v2.56`.

### 11.4 Cierre local del límite del §7 (medido, no CI)

El §7 declaró que la **batería offline completa** no se podía medir aquí porque su recolección incluye
suites PG que importan `asyncpg`. Con el **PostgreSQL del compose levantado** (verificado: `localhost:5432`
aceptando conexiones) se re-corrió la batería **entera** con el entorno de CI (`DB_HOST=localhost`,
`DB_PASSWORD=bolsa_dev`, sin `DATABASE_URL`) y **todas las suites PG corrieron de verdad** (no se
saltaron):

```
4024 passed, 1 xfailed, 29 warnings in 574.20s (0:09:34)   ·   0 FAILED · 0 ERROR · 0 collection errors
```

Es un dato **local**, no de CI: el job `python` del tag mide **`2649 passed / 35 skipped`** porque allí las
suites PG de este job van por otros jobs dedicados (§11.2). Se publica porque **cierra el límite del §7**
con una corrida real: **cero rojos y cero errores de colección** sobre el árbol sellado, con la `046`
aplicada y el PG de verdad detrás.

### 11.5 Los tres rojos de una corrida local ANTERIOR: causa declarada, no regresión

La primera corrida local de la batería (pre-sello, `06:48`) dio **`3 failed, 3859 passed, 1 xfailed`**, con
los tres rojos **en el mismo fichero y por la misma causa**:

```
test_database_url_se_compone_desde_db_vars_vacio
test_database_url_incluye_password_si_se_provee
test_repr_redacta_credenciales_db
AssertionError: assert 'postgresql+psycopg://bolsa@127.0.0.1:5432/bolsa_v1'
                     == 'postgresql+psycopg://bolsa@localhost:5432/bolsa_v1'
```

**Causa medida:** el shell de esa corrida tenía **`DB_HOST=127.0.0.1`** exportado (residuo de las
certificaciones PG contra el compose) y el test espera el **defecto** `localhost`. **No es una regresión
de la fase:** (a) el fichero pasa **`17 passed`** en aislamiento, (b) `test_config.py` **no** está en el
diff de `AUTO-16`, y (c) la CI fija **`DB_HOST: localhost`** y sale verde (`2649 passed / 35 skipped` con
**0** rojos). La corrida limpia de §11.6, con el mismo entorno que la CI, da **`0` rojos**. Se publica la
cifra medida y su causa, en vez de la que habría sido cómoda.

### 11.6 El intermitente conocido **no** se reprodujo en este sello (declarado)

`AUTO-15` dejó declarado un **test PG intermitente preexistente y ajeno a la fase**
(`apps/api-python/tests/test_concurrent_auto_pg.py`, `UniqueViolation` en `auto_engine_ticks_pkey`; medido
entonces **`1` rojo en `5`** corridas locales) y un teardown de vitest que envenenaba el exit code con los
tests en verde. **En este sello ninguno de los dos apareció**: los dos `Python CI` y el `Release tag CI`
cerraron sin rojos. Se deja **declarado** el hueco por si el auditor lo reproduce: ninguno de los dos
ficheros está en el diff de esta fase, así que la existencia del intermitente **no** cambia con ella.
