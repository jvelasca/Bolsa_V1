# Audit-pack `AUTO-14` Reparto por CELDA de régimen — `1.80.0-beta` (2026-09-23)

**Fase:** `V2.55` · **Rótulo:** `AUTO-14` · **Bump:** `1.79.0-beta` → **`1.80.0-beta`** · **Tag:**
`v2.55-beta` (cifras de CI en §12) · **Fase anterior:** `V2.54` / `AUTO-13` (tag `v2.54-beta` →
`54a3b86a`, `Release tag CI` `35857892968` **GREEN**: `10 success` + `1 skipped`, `check-runs`
`38 success` + `1 skipped`, job `python` del tag **`2568 passed / 35 skipped`**).

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva,
sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal durable** (la entrada
`adaptive_recommendation` proyecta por lista blanca `riskMultipliers` + `evidenceAxis`:
`auto_adaptive_journal.py:58`, **byte a byte igual**). El gobernador y su evidencia quedan **intactos**.
Adaptive **sigue siendo recomendador read-only** y con el flag **OFF** el camino de producción es
**byte-idéntico** a `v2.54`: esta fase no se ejecuta en producción hasta un flag explícito.

---

## 0. Resumen: qué instala esta pasada

`AUTO-9` dejó el cruce `strategy × regime` **medido** y lo usó para la **rotación** y la **salud**, pero el
**reparto** seguía pesando con la evidencia **global** de la estrategia. El §20 del audit de `AUTO-13`
declaró esa mitad —la *matriz avanzada*— para esta fase.

Esta pasada deja que la **celda** afine el **peso**, con dos reglas que la hacen honesta:

1. **La celda afina el peso, nunca la composición.** Quién entra al numerador lo decide la **fila**
   (`decisive` + expectancy positiva), igual que en `v2.50`–`v2.54`: la celda solo cambia **el número**
   con el que compite una versión **ya admitida**. Ni añade ni quita competidores.
2. **El hueco se declara.** Sin celda, sin muestra suficiente, sin R neto medido o sin régimen legible,
   esa versión conserva su número **global** y el motivo viaja en el plan.

Superficie nueva: `regime_cell_for(...)` (helper puro) y la costura
`apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py`.
Superficie tocada: `auto_adaptive.py` (sello, motivos, `AllocationPlan`, `_allocation_weights`,
`recommend_allocation`, `build_adaptive_plan`) y el worker (`auto_simulation_worker.py`, **solo** la
declaración del tick en el log: **sin cambio de firma**).

---

## 1. El invariante: **el reparto no puede mejorar su peso con una celda que no se ha medido**

> Una celda sin muestra suficiente, una celda ausente, un R **neto** no medido, una celda medida **no
> positiva** o un régimen **ilegible** **no mueven el peso**. Esa versión cae al **global** de su fila y
> el hueco se **declara**. La celda solo **afina** lo que ya estaba medido.

Es la extensión del invariante de `AUTO-13` del **material** al **reparto**: `AUTO-9` cerró *«¿cuánto
vale?»*, `AUTO-10` *«¿de qué ciclo es?»*, `AUTO-11` *«¿dónde vive su memoria?»*, `AUTO-12` *«¿cuánto puedo
creérmelo?»*, `AUTO-13` *«¿están sanos los datos con los que me lo creo, y cómo vuelvo?»* y `AUTO-14`
cierra *«¿el peso que reparto se midió en el régimen en el que voy a operar?»*.

**Cuatro corolarios, todos con test y con mutación que los mata:**

- **La celda no cambia quién compite.** El numerador se decide por la **fila**; la celda solo puede
  cambiar pesos **relativos** de quien ya competía.
- **Sin muestra no hay celda.** `decisive = false`, `net_r_measurement != COMPLETE`, `None` o `<= 0`:
  hueco declarado, **nunca** un cero disfrazado de medida.
- **Sin régimen legible no hay juicio de régimen.** `None`, `""` y `UNKNOWN` no eligen celda (la lección
  del §20/`M81`): se declara `cell_regime_absent`.
- **La moneda no se inventa por celda.** La celda mide **R**; con el eje histórico
  (`expectancy_currency`) el reparto es **global** y se declara `cell_axis_without_cell`. No se deriva un
  cociente paralelo para fabricar una moneda por régimen.

---

## 2. La selección de celda: un helper puro y declarativo

`regime_cell_for(cells, strategy_version, regime) -> (celda | None, motivo | None)`
(`auto_adaptive.py:871`) es el **único** sitio donde se elige celda, y devuelve **siempre** el par
`(celda, motivo)`: el hueco nunca se silencia.

| Punto | `ruta:línea` |
| --- | --- |
| Normalización **declarada** (`strip().upper()`, un solo mapa) | `auto_adaptive.py:860` (`_cell_key`) |
| Régimen ilegible ⇒ `cell_regime_absent` | `auto_adaptive.py:888` |
| Sin celda para `(versión, régimen)` ⇒ `cell_not_found` | `auto_adaptive.py:899` |
| Celda no `decisive` ⇒ `cell_not_decisive` | `auto_adaptive.py:900` |
| R neto no `COMPLETE` ⇒ `cell_net_unmeasured` | `auto_adaptive.py:901` |
| Celda medida no positiva ⇒ `cell_not_positive` | `auto_adaptive.py:903` |
| Vocabulario de motivos (propio del reparto) | `auto_adaptive.py:242-256` |

**Decisiones finas, medidas:**

- **No se traduce otra vez.** El plan recibe el régimen **canónico** del tick (el worker ya lo traduce con
  `to_market_regime`); un segundo mapa de alias podría **divergir** del que usó la rotación, así que aquí
  solo se normaliza la **forma** (caja y espacios).
- **Solo afina una celda medida Y positiva.** Un R neto medido pero negativo no "penaliza" por celda: la
  versión conserva su global y se declara. La celda se usa para **afinar**, no para castigar.
- **Nunca se hereda.** No se elige otra celda, ni la de otra versión, ni la de otro ciclo.

**Preguntas incómodas.**

- ¿Puede `regime_cell_for` devolver una celda **y** un motivo a la vez (o ninguno de los dos)? Si puedes
  construirlo, el consumidor tiene un camino no probado: **mídelo**.
- `truncate`: `_cell_key(" trend_up ")` y `_cell_key("TREND_UP")` coinciden, pero `RANGE` y `RANGE_MARKET`
  **no**. ¿Está declarado que la normalización es **solo** de forma? (Sí: docstring del helper.)
- La celda es **del tick**: un régimen que el worker traduzca distinto de como lo guardó el agregador
  produce `cell_not_found` (hueco declarado), **nunca** una celda de otro régimen.

---

## 3. El reparto: la celda afina el PESO, nunca la composición

`_allocation_weights(...)` (`auto_adaptive.py:923`) sigue eligiendo **eje** y **grupo** con la **fila**
(`decisive` + expectancy positiva, R neto `COMPLETE`), y devuelve ahora `_AllocationSources`
(`:910`) con `axis`, `positive`, `cell_axis`, `cell_used` y `cell_fallback`.

- **El eje es del GRUPO, nunca de la fila** (la regla de `AUTO-9`): el R neto solo se adopta si cubre a
  **todo** el grupo que compite (`net_r.keys() == currency.keys()`, `:979`). Mezclar moneda y R dentro
  del grupo sería aritmética sin sentido (**M102**).
- **La celda se consulta solo para quien YA competía** (`:965-976`): se toma el número de su celda y se
  sustituye; si la celda no es utilizable, el número **global** se queda y nace el motivo
  (`cell_fallback`). Una versión **no** puede entrar o salir del numerador por una celda.
- **Con el eje de moneda no se toca el reparto** y **todas** las que compiten declaran
  `cell_axis_without_cell` (`:986-993`).
- Sigue **suma-preservado**, acotado a `[0, 1]` y **sin ceros** (`:1126-1141`), y la **rampa `AUTO-13`
  sigue siendo el techo** (`min`, `:1141-1148`), aplicada **después** del reparto.
- **Sin `by_regime`/`regime` el reparto es byte-idéntico** al de `v2.54` (keyword-only opcionales): el
  mismo patrón de `AUTO-12` con `confidence=None`.

---

## 4. El encogimiento (`AUTO-12`) se mide con la banda de la **celda**

`_cell_confidence(...)` (`auto_adaptive.py:999`) busca el `RegimeConfidence` de la celda en
`StrategyConfidence.by_regime` (que `AUTO-12` **ya** publica). Cuando el peso de una versión salió de su
celda, el factor de encogimiento usa la **muestra efectiva** y el **deterioro** de **esa** celda; si el
peso salió del global, usa la banda de la estrategia (`:1113-1119`). Sin lectura de confianza, el
comportamiento es el histórico (`_confidence_factor`, `:1016`).

Es la decisión que evita el error sutil: encoger el peso de una celda con la muestra **agregada** de la
estrategia (que mezcla regímenes que no se parecen) volvería a introducir el *winner chasing* que
`AUTO-12` cerró, esta vez por la puerta de la celda (**M106**).

---

## 5. La declaración: `allocationCells` en el plan, sin tocar nada sellado

`AllocationPlan` (`auto_adaptive.py:504`) gana tres campos declarativos —`cell_axis`, `cell_used`,
`cell_fallback` (`:525-534`)— con lecturas propias (`cell_for` `:539`, `cell_note_for` `:542`).

**Su `as_dict()` NO cambia** (`:544-552`): sigue publicando exactamente
`{"riskMultipliers", "evidenceAxis"}`, el frame que selló `AUTO-13`. La base de celda se declara en el
**nivel del plan**, en campo propio (`AdaptivePlan.as_dict()['allocationCells']`, `:750-754`), junto al
hueco de régimen (`regimeUndetermined`) y a `shrinkage`. Con eso:

- El **contrato durable** de `AUTO-11` queda **byte a byte igual**: `_ALLOCATION_KEYS` (`auto_adaptive_journal.py:58`)
  proyecta solo las dos claves selladas, así que `allocationCells` **nunca** llega al journal
  (test `test_the_journal_projection_is_byte_identical_with_a_cell_present`).
- `evidenceAxis` conserva sus **dos literales** (el eje es el mismo): lo que se declara aparte es **de
  dónde salió el número**, no con qué se pesó.
- El **tick lo declara** en el log (`auto_simulation_worker.py:3167`), como `AUTO-13` hace con la rampa y
  el hueco de régimen: un multiplicador no dice por sí solo si su número se midió en el régimen del tick
  o en el agregado global.

> **Delta declarado respecto al plan de fase.** El plan preveía que los tres campos viajaran en
> `AllocationPlan.as_dict()`. La implementación los declara en el **nivel del plan** para que el frame
> sellado de `allocation` quede **byte-idéntico** a `AUTO-13`: es **más** estricto que el plan, no menos,
> y permite que el test de `AUTO-13` que fija el frame siga valiendo **sin tocarlo**.

---

## 6. El sello `auto14-v1` y su consecuencia declarada

`ADAPTIVE_POLICY_VERSION` → **`auto14-v1`** (`auto_adaptive.py:168`), con el test del sello renombrado
**con nombre** (`test_the_policy_version_seals_the_auto14_evidence_contract`). Cambia la **regla de
asignación** (los pesos relativos), así que el sello **debe** subir: dos planes iguales con la misma
evidencia y el mismo régimen no son idénticos si uno se midió por celda y el otro no.

**Consecuencia medida y declarada.** El mismatch de política (`auto_adaptive_recovery.py:380-385`)
marcará las filas históricas `auto13-v1` hasta que se escriba la primera fila `auto14-v1`, de modo que el
gate puede declarar `STALE` **un tick**. Se **cura con la primera escritura**, **no** resetea el contador
(continuidad de política, docstring `:41-45`) y **no se ejecuta con el flag OFF**. Se relaja **nada** del
contrato de `AUTO-11`: el test de la consecuencia
(`test_the_seal_bump_declares_a_stale_gate_and_never_resets_the_failure_counter`) lo fija, y su **control**
(`test_without_a_reading_the_gate_never_invents_a_mismatch`) demuestra que sin lectura **no** se inventa
un mismatch.

---

## 7. Matriz de mutaciones (`M99…M107`): 9/9 muerden

| # | Mutación | Invariante que ataca |
| --- | --- | --- |
| `M99` | el guard de decisividad de la celda se cae (`if not found.decisive:` → `if False:`) | una celda **fina** movería el peso |
| `M100` | el fallback deja de publicarse | el hueco quedaría **silenciado** |
| `M101` | la versión sin celda cae a `0.0` | el hueco se leería como **cero**, no como «global» |
| `M102` | el R neto se adopta sin cubrir a todo el grupo | **ejes mezclados** dentro del grupo |
| `M103` | la búsqueda deja de casar la **versión** | celda de **otra versión** |
| `M104` | con régimen ilegible toma la primera celda | régimen ilegible **eligiendo** celda |
| `M105` | el R neto `PARTIAL` habilita decidir | celda **no medida** tratada como medida |
| `M106` | el shrink usa la banda de la **fila** | encogimiento con la base que la celda **no** tiene |
| `M107` | la rampa `AUTO-13` se esquiva si el peso vino de una celda | la rampa dejaría de **topar** el peso de celda |

La corrida **completa** de la matriz está en §8.

---

## 8. Verificación (lo medido, y lo que no se pudo medir aquí)

- **Compuertas §5 del relevo, con el comando de CI** (no rutas sueltas):
  `ruff check packages/py apps/api-python --config pyproject.toml` **`All checks passed!`**;
  `mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent`
  **`0` errores en `497` ficheros**;   `lint-imports --config packages/py/.importlinter` ⇒ **`4 kept, 0 broken`**. *(El primer `ruff` de la
  fase mordió un `UP035` de la costura nueva —`typing.Sequence`— y se corrigió importando de
  `collections.abc`: la matriz de §7 se corrió **después** de ese arreglo, así que sus cifras describen el
  árbol que se sella, no uno anterior.)*
- **Unit de la fase:** `test_auto_adaptive.py` **90 tests** (HEAD **78**: **+12**), con la sección
  `AUTO-14` completa: celda decisiva **mueve** el multiplicador, celda fina / ausente / net no medido /
  no positiva **no** lo mueven y **declaran**, régimen ilegible, eje de moneda, composición intacta, ejes
  sin mezclar, shrink con la banda de la celda, rampa como techo, `allocationCells` en campo propio y
  reproducibilidad sin celdas.
- **Costura nueva** `test_auto_v55_auto14_regime_cell_allocation_seam.py` (**6 tests**) por el **camino
  real del worker** y **con control**: una celda **sin muestra** no mueve el peso y una **decisiva** sí
  (el mismo par medido en el reparto, con el tick y su lector de régimen de verdad), la composición no
  cambia y la rampa sigue topando, el tick **declara** la base de celda, la proyección del journal es
  **byte-idéntica** con una celda presente y el sello declara `STALE` **sin resetear** el contador.
- **Tramo de la fase:** `test_auto_adaptive.py` (90) + `test_auto_v53_auto12_confidence_seam.py` (9) +
  `test_auto_v54_auto13_recovery_seam.py` (14) + `test_auto_v55_auto14_regime_cell_allocation_seam.py`
  (6) ⇒ **`119 passed`**, `0` rojos.
- **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales), corriendo la versión de
  `HEAD` de cada fichero de test modificado **contra el código de la fase**:

  | Fichero | HEAD vs fase | Rojos | Causa declarada |
  | --- | --- | --- | --- |
  | `packages/py/analytics/tests/test_auto_adaptive.py` | **3 failed, 75 passed** (HEAD 78) | `test_regime_cells_alone_do_not_move_rotation_or_allocation` · `test_the_policy_version_seals_the_auto13_evidence_contract` · `test_the_operational_states_travel_in_their_own_field_without_mixing_axes` | el **contrato de celdas** que la fase cambia y el **sello** `auto13-v1` → `auto14-v1` (una de ellas lo afirmaba dentro del test del §29) |
  | `apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py` | **1 failed, 8 passed** (HEAD 9) | `test_the_policy_used_by_the_worker_seals_the_auto13_rule` | el **sello** |
  | `apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py` | **1 failed, 13 passed** (HEAD 14) | `test_the_published_evidence_keeps_its_declared_frame` | el **sello** dentro del payload |
  | `apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py` | **no existe en `HEAD`** (0) | — | costura **nueva** de la fase |

  Los **5 rojos** de `HEAD` son **dos causas declaradas** (el contrato de celdas y el sello) y **ninguno**
  es una regresión de comportamiento: el delta del plan decía «2 rojos declarados» y la medida dice **5
  nodos con 2 causas** —el sello aparecía también dentro de otros dos tests—; se declara la cifra medida,
  no la prevista. Los tres ficheros se restauraron **byte a byte** tras la corrida.
- **Matriz de mutaciones COMPLETA** (`M1…M107`): **`107/107` muerden**, **`0`** etiquetas en `NADA`,
  **`0`** fragmentos ausentes, restauración **byte a byte** y huella `git status` **idéntica** antes y
  después (`intacto: la sonda no altero el arbol`).
- **Lo que no se pudo medir aquí:** la batería offline **completa** de los jobs `quality`/`python` del
  tag (su recolección incluye suites PG que importan `asyncpg`, ausente en esta máquina, y el teardown de
  sesión del conftest de `apps/api-python` exige PostgreSQL). **Ese límite lo cierra la CI del tag**
  (§12), medida.

---

## 9. Límites declarados (no silenciosos)

- El reparto por celda **solo actúa sobre el eje del R neto medido**. Con el eje de moneda el reparto es
  global y lo **declara** (`cell_axis_without_cell`): no hay moneda medida por régimen y **no se
  inventa**.
- La celda **nunca** cambia quién compite: solo el peso relativo de quien ya competía.
- El **shrink de celda** solo puede **estrechar** (redistribuye y sigue sin ceros): un `RegimeConfidence`
  con `effective_n = 0` se **declara** por el hueco, no se convierte en un peso fabricado.
- La celda es **del tick**: dos turnos con el mismo régimen y la misma celda dan el mismo reparto
  (reproducibilidad), pero un régimen **no** legible no elige celda.
- **El flag Adaptive sigue OFF**: sin él, esta fase **no se ejecuta**.
- **Fuera de alcance, sin tocar:** Data Gate **persistido** y la **UI** de `AUTO-7`…`AUTO-14`.

---

## 10. Freeze respetado

No se toca el sello de `V2.53`/`V2.54`, `auto_adaptive_journal.py` (**byte a byte igual**),
`yahoo_circuit_breaker.py`, `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación, el gobernador
(`v2_43_governor_evidence.py`: **diff vacío** y script `exit 0`), la tabla `decision_journal_entries` ni
el esquema. **Sin migración** (Alembic head `044_auto_cycle_trace`), sin SHORT, sin backfill, sin UI.
`*.md` **sin `prettier`**. La versión `v2.53`/`v2.54` sellada no se reabre: esta fase **añade** sobre ella.

---

## 11. Sellado

El paquete de cierre (este pack, el [relevo](./traspaso-relevo-post-v2.55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md),
el [arranque del auditor](./arranque-auditor-v2.55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md) y el
[del agente siguiente](./arranque-agente-post-v2.55-auto-14-2026-09-23.md), `CHANGELOG.md`,
`PROJECT_STATE.md` y el índice) viaja **dentro** del tag. La tabla de runs de CI se escribe en §12 con las
cifras **medidas**.
