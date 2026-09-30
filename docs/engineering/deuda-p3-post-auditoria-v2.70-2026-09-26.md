# Deuda P3 post-auditoría `v2.70` (y cierre en `v2.71`) — 2026-09-26

> **AsOf:** 2026-09-26 · **Origen:** auditoría profunda de `auto_adaptive_uncertainty.py` y
> `auto_adaptive_replay.py` (AUDITORIA 2 sobre `AUTO-23`).
> **Naturaleza:** hallazgos **P2/P3** sobre **la lectura** de la incertidumbre; ninguno publica un
> número falso nuevo, pero H1 **sí** mezcla dos funcionales en el mismo nombre.
> **Estado:** **H1 y H2/H3/H4 cerrados en `v2.71`**; **P3-4** (hallazgo de la auditoría de `v2.71`,
> preexistente y read-only) **cerrada en `v2.72`**; **P3-5** (`reserved_risk` sobrecargado: libro vivo
> vs evidencia histórica) **abierta y declarada** (2026-09-26, tras el E2E PostgreSQL de `v2.74`);
> **P3-6** (la contabilidad por familias no es de vetos puros: `approved`/`risk_exit` engordan `other`)
> y **P3-7** (`STATE_UNKNOWN` inalcanzable: un payload vacío se lee como `no_signal`) **CERRADAS en
> `v2.78`** (2026-09-27) — ambas de la auditoría externa de `v2.77-beta`, 2026-09-26; `P3-6` era
> MEDIUM y afectaba al caso de uso principal del instrumento. **La auditoría externa de `v2.78-beta`
> (2026-09-27) reabrió `P3-6` PARCIALMENTE (`H-1`: los motivos de gestión de posición seguían
> inflando `vetoCounted`) y añadió `H-2`/`H-3` (LOW, contrato del dueño y disjunción veto/no-veto):
> los tres se **CIERRAN en `v2.79`** (censo de ENTRADA + canal de posición aparte);
> **la auditoría externa de `v2.79-beta` (2026-09-27) emite `APROBADO CON OBSERVACIONES` (0
> bloqueantes) y añade `H-4` (LOW, el test de exhaustividad omite el vocabulario de rechazo
> pre-ranqueo de `auto_v2_entry`), que queda **ABIERTO y declarado**; la fase `v2.80` (`AUTO-MATERIAL-8`,
> 2026-09-27) **no lo cierra** (fuera de su alcance) pero lo hace **VISIBLE**: el nuevo `otherCount`/
> `contractViolation`/`reasonCatalogCoverage` de `market_operability.py` declaran en el journal los códigos
> que caen en `other` en vez de diluirlos; el cierre formal (familia declarada para los cinco `signal_*` y
> exhaustividad del test vía import) sigue **pendiente**;**
> P3-2 y P3-3 siguen **abiertas** (requieren material PAPER real con **diversidad de mercado**). **El
> bloqueante central es MATERIAL, no código** (y desde `v2.74` es de **muestra**, no de forma; `v2.75`
> cruza la **cantidad** —42 ciclos medibles ⇒ `EVIDENCE_READY`— pero **no** la **diversidad**: un solo
> bucket de calendario y un solo episodio de régimen; `v2.76` cablea **precio y régimen de MERCADO**
> por el único seam del motor congelado y **declara** por qué, medido, el material de mercado no se
> puede adelantar: la diversidad de cubos sale de `created_at = datetime.now(UTC)` y exige **tiempo
> real transcurrido**, no una corrida rápida). **La auditoría externa de `v2.83.1-beta` (2026-09-27,
> clon fresco de GitHub) emite `APROBADO CON OBSERVACIONES` (0 bloqueantes; 6/8 PASS, 2 PARTIAL —
> semántica del instrumento y compuertas PG no reproducibles en local) y levanta `OBS-6` (MEDIUM),
> `OBS-7`/`OBS-8` (LOW), que quedan **ABIERTOS** y se **CIERRAN en `v2.84`** (ver más abajo); el re-sello
> es docs-only ⇒ los tres hallazgos son del instrumento de `v2.83` (`operability_audit.py`), no de
> `v2.83.1`. `OBS-9` (nuevo, LOW doc-only) queda **ABIERTA y declarada**.**
> **La auditoría externa de `v2.84-beta` (2026-09-28, `AUTO-MATERIAL-12`, tag `e6d921a8` → `fd3859e3`)
> emite `APROBADO` (0 bloqueantes)** sobre una fase de instrumento read-only y levanta **`OBS-10` (LOW)**:
> `stateCounts` del `TOTAL` recorre todas las filas mientras el resto usa `measured_rows`. Queda
> **ABIERTA y APLAZADA** a la fase de código `v2.85`/`AUTO-MATERIAL-13` (no se toca `packages` con una
> ventana PAPER en curso); su semántica de cierre ya está **decidida** (`measured_rows`). **`v2.85`
> (2026-09-28) la CIERRA en `main`** (código + test + **`M233`**; sellada en `v2.85-beta` y re-sellada en
> `v2.85.1-beta`) y, al etiquetar `unresolvedRate`, registra la observación nueva **`OBS-11`
> (LOW)**: su aritmética es un **indicador** (`numerador == denominador`), no una proporción — **ABIERTA y
> declarada** (la etiqueta honesta se hizo; la semántica de la clave, no).
> **`OBS-12` (LOW, higiene documental, hallazgo del propietario al ir a auditar):** el tag `v2.85-beta`
> llevaba **dos sets documentales** de la misma fase y `PROJECT_STATE` llamaba «Relevo vivo» al
> **obsoleto** ⇒ un auditor podía emitir un hallazgo **falso** («los docs niegan el tag»).
> **CERRADA en el re-sello `v2.85.1`** (docs-only; ver más abajo).
> **Deuda de proceso declarada:** `v2.73-beta` quedó
> **sin auditoría externa** (ver más abajo).
> **`v2.86` (2026-09-29):** fase de **instrumento** (replay OOS de viabilidad, sin bump/migración/tag):
> **no cierra ni mueve** ninguna deuda de datos; añade la clase de evidencia **replay con reloj simulado**
> y declara la **causa raíz de instrumento** que truncaba el replay (libro de compromisos no retirado).
> **`v2.87` (2026-09-29):** fase de **instrumento** que **resuelve** esa causa (ciclo durable
> `reserva→fill→liberación` al cierre de tick; replay multi-anual **completo**, 62 ciclos en 4
> temporadas). Sigue **sin bump/migración/tag** y **NO cierra `P3-2`/`P3-3`** (reloj simulado). **Abre
> `OBS-14` (MEDIUM, alcance motor)**: el motor real retira reservas muertas **solo al arranque**, no
> entre reinicios (ver más abajo).
> **`v2.88` (2026-09-29):** **sello conjunto** `v2.88-beta` (`AUTO-MATERIAL-16`) de tres incrementos
> implementados y **sin commitear** (`v2.86` + `v2.87` + el cierre de `OBS-14`); bump
> `2.10.2-beta → 2.11.0-beta`, **sin migración** (Alembic head `046_fill_reference_mid`). **`OBS-14`
> CERRADA** por la **ruta (a)** de su criterio de cierre (reconciliación al **cierre de turno**, en
> `real_turn`; ver más abajo). **Abre `OBS-15` (MEDIUM, alcance motor):** el techo de lectura de **1000
> filas `APPLIED`** puede **parar el motor** (ver más abajo).
> **`v2.88.1` (2026-09-29):** **RE-SELLO** `v2.88.1-beta` (`AUTO-MATERIAL-16`) que corrige un defecto
> **fail-OPEN** introducido por el cierre de `OBS-14`: bump `2.11.0-beta → 2.11.1-beta`, **sin
> migración**. El tag `v2.88-beta` quedó **público con `Release tag CI` ROJO** (`lifecycle-pg`,
> `test_crash_recovery_day_real_process_survives_dirty_kill_pg`). **Causa raíz:** la regla 1 de
> `_v2_reconcile_reservations` reparte el histórico **COMPLETO** de fills (`consumed` se reinicia en cada
> llamada) y `_release` aplica `released_qty` como **delta** ⇒ **no idempotente**; invocada en cada turno
> **re-liberaba fills ya liberados** y **drenaba la cola viva** de las órdenes parcialmente llenadas
> (capital comprometido devuelto al mercado). **Corrección:** `attribute_fills` (por defecto `True` ⇒
> arranque intacto); el cierre de turno corre con `attribute_fills=False` y solo aplica la **regla 2**;
> `close_tick` del replay alineado. **`OBS-14` sigue CERRADA**, ahora con la guarda correcta.
> **Deuda nueva declarada (instrumento):** el artefacto multianual de `v2.87` se midió con la costura
> previa ⇒ **exige RE-EJECUCIÓN** antes de citar su R (ver informe `obs-14-correccion-fail-open-v2.88.1`).
> **`v2.88.2` (2026-09-29):** **RE-SELLO** `v2.88.2-beta` (`AUTO-MATERIAL-16b`) que corrige un **segundo**
> defecto **fail-OPEN** del mismo cierre, esta vez de **carrera entre sesiones**: bump `2.11.1-beta →
> 2.11.2-beta`, **sin migración**. El tag `v2.88.1-beta` quedó **público con `Release tag CI` ROJO**
> (`lifecycle-pg`, `test_concurrent_auto_pg.py`: `released=200.000000` vs `materializado=147.000000`).
> **Causa raíz:** la **regla 2** decide con evidencia **durable**, que **no** puede distinguir «orden
> muerta» de «orden que OTRA sesión aún no ha emitido en su turno»: la sesión perdedora liberaba la
> reserva **viva** de la ganadora y el fill que esta materializaba después se quedaba sin fila que
> liberar. **Corrección (alcance):** `only_ids` en `_v2_reconcile_reservations`; el cierre de turno solo
> retira las reservas que **esta sesión** dio de alta (`_v2_owned_reservations`), el barrido de
> **arranque** sigue global; `close_tick` del replay alineado. **`OBS-14` sigue CERRADA**, ahora con el
> alcance correcto. **Abre `OBS-14.b` (MEDIUM, residual):** el barrido de arranque tampoco distingue una
> huérfana de una reserva viva de otra sesión (reinicio rodante); discriminador posible, **no**
> implementado: ventana de gracia por **EDAD** (ver más abajo).
> **Nuevo dato de no-regresión:** los tres pasos que quedaron **saltados** en el CI de `v2.88-beta`
> (`HardKill recovery`, `crash injection matrix`, `multiprocess AUTO`) se ejecutaron por primera vez en
> este RE-SELLO: **5 passed** en local.
>
> **`v2.88.3` (2026-09-29):** **RE-SELLO 3** `v2.88.3-beta` (`AUTO-MATERIAL-16c`): bump `2.11.2-beta →
> 2.11.3-beta`, **sin migración**, **motor INTACTO** (el diff es un test + el arnés + docs). El tag
> `v2.88.2-beta` (`41e7e679`) quedó **público con el job `python (ruff/imports/mypy/pytest offline)` ROJO**
> (`Release tag CI` `36553839085`): `ruff`/`import-linter`/`mypy` verdes y `Pytest offline` con **6 fallos**
> (`AttributeError: 'AutoSimulationWorker' object has no attribute '_v2_owned_reservations'`,
> `auto_simulation_worker.py:2335`, los seis en `test_auto_v51_auto10_cycle_journal_seam.py`). **Lo que ese
> rojo CONFIRMA:** el job `lifecycle-pg` (crash/recovery + **3 sesiones concurrentes** + golden day +
> aislamiento de cuenta) quedó **GREEN**, junto con `a7-gate`, `dr-verify`, `shared`, `frontend`, `spine` y
> `security` ⇒ **la corrección de `v2.88.2` funciona y lo mide el CI del tag**. **Causa raíz: de la
> VALIDACIÓN, no del motor** — esa costura construye el worker con `object.__new__` (**sin `__init__`**) y
> declara a mano el libro de reservas; al añadir el libro de propiedad al `__init__` se quedó sin declararlo.
> **Arreglo:** 1 línea en la costura (`worker._v2_owned_reservations = set()`), sin relajar el motor con
> `getattr`. **Observación nueva `OBS-16`** (ver más abajo). **`OBS-14.b` y `OBS-15` siguen ABIERTAS**.
> **`v2.88.4` (2026-09-29):** `AUTO-MATERIAL-17`, bump `2.11.3-beta → 2.11.4-beta`, **sin migración** y
> **sin tocar el motor** (test + arnés + docs). **`OBS-17` CERRADA**: test de simetría del ownership de la
> pata de **SALIDA** (`_v2_reserve_exit`) + mutación `M253` (matriz `252 → 253`).
> **`v2.88.5` (2026-09-29):** `AUTO-MATERIAL-18`, bump `2.11.4-beta → 2.11.5-beta`, **motor +91/−20**.
> **`OBS-14.b` CERRADA**: ventana de gracia por **EDAD** (`V2_RESERVATION_GRACE_TURNS = 1`, derivada de la
> cadencia real del loop, 60 s) — el barrido de **arranque** deja de ser **fail-OPEN** en un reinicio
> rodante; mutaciones `M250`/`M254`/`M255`/`M256` (matriz `253 → 256`). CI del tag: `3049 passed, 37
> skipped` (**ESPERADO = OBSERVADO**).
> **`v2.88.6` (2026-09-29):** `AUTO-MATERIAL-19`, bump `2.11.5-beta → 2.11.6-beta`, **sin migración**.
> **`OBS-18` CERRADA** (ID nuevo, ver más abajo): la **regla 2** de `_v2_reconcile_reservations` decidía
> por el **AGREGADO de fills del instrumento+lado** en vez de por la **evidencia de la fila**
> (`released_qty`), así que una reserva que **nunca materializó** sobrevivía **para siempre** en cuanto una
> hermana suya llenaba, y la **cola** de un fill parcial **no la retiraba nadie**; medido en la
> **RE-EJECUCIÓN obligatoria** del replay multianual de `v2.87` (16 reservas vivas, `$5999.9998 / $6000`
> comprometidos, `risk_budget_exceeded` 1400, actividad congelada tras `2022-05-06`) — y el horizonte lo
> publicaba como **`completed: true`**. Se toca **motor + instrumento**: evidencia **por reserva** con la
> guardia de `in_flight` mandando (fail-closed), motivo nuevo `tail_dead` frente a `cancel`, **log de
> retiradas con causa** (el artefacto publicaba `byDeadTail: 0` sobre **64** retiradas: un cero
> silencioso) y **guardarraíl de estancamiento** (`stalled_book`, `STALL_OPERABLE_DAYS = 20` días
> operables sin actividad con capital comprometido — **declara**, no corta). Ciclo durable **limpio**
> (752 fills / 62 ciclos / 4 temporadas / riesgo final `0.0`) y **byte-reproducible**; la contraprueba A/B
> reproduce el estancamiento y lo **declara**. Matriz `256 → 265` (`M257`–`M265`, 9/9 muerden).
> **`OBS-15`/`OBS-16`/`P3-2`/`P3-3` siguen ABIERTAS**; el CI del tag es **POST-TAG** (esperado
> `3103 passed, 37 skipped`). Al medir la batería se **descubrió y cerró** un **hueco de cobertura del CI**
> (el test del instrumento no estaba en la lista de ningún workflow: se cablea en los dos) y quedó
> registrada su causa estructural como **`OBS-19`**.

## H1 — `P(R>0)` mezclaba dos funcionales (P2/P3) — 🟢 CERRADO en `v2.71`

**Observación.** En `auto_adaptive_uncertainty.py`, `probability_positive` era la fracción de
**medias bootstrap** `> 0` (≈ `P(edge>0)`). En `auto_adaptive_replay.py`, `oos_positive_share` era la
fracción de **ciclos** `> 0` (≈ `P(R>0)`). `_question_probability_positive`
(`auto_adaptive_calibration.py`) las comparaba **como si fueran lo mismo**: la "calibración" medía una
diferencia de **definición**, no de acierto.

**Cierre.** Se publican **ambas** con nombres distintos:

- `P(ciclo>0)` = `cyclePositiveShare` = fracción de ciclos medidos con `R>0` (estricto).
- `P(edge>0)` = `edgePositiveProbability` = fracción de medias bootstrap `> 0`.
- La calibración compara `P(ciclo>0)` **IS** vs frecuencia positiva **OOS** (magnitudes homogéneas).
- Sellos nuevos: `bootstrap_episodes_v3`, `walk_forward_calibration_v4`, `current_regime_evidence_v2`,
  `auto23_evidence_validation_v2`, `auto23_sample_size_sweep_v2`, `auto23_regime_stability_v2`.

**Criterio de reversión.** Si un consumidor necesitara `P(edge>0)` para calibrar, tendría que
justificar por qué mide la misma magnitud que el OOS (no lo es).

## H2 — La ausencia de medición contaba como no cubierta (P3) — 🟢 CERRADO en `v2.71`

**Observación.** `_question_coverage` metía `dominant_regime_coverage is None` (no medido) en el grupo
"no cubierta", convirtiendo **ausencia de evidencia** en **evidencia negativa**.

**Cierre.** Esas celdas salen de la comparación y se declaran en **`cellsUnmeasured`**; `sample` y
veredicto solo miran bandas **medidas**. Protegido por **M195**.

## H3 — `build_replay_report` publicaba un nivel sin clampar (P3) — 🟢 CERRADO en `v2.71`

**Observación.** El informe publicaba `interval_level` **crudo** (p. ej. `0.0`) aunque el bootstrap usó
el nivel **clampeado** `0.5`; su hermano `CalibrationReport` sí publicaba el clampeado.

**Cierre.** `build_replay_report` calcula `resolved_level = min(max(level, MIN), MAX)` y publica **ese**
nivel. Protegido por **M196**.

## H4 — Colisión de la clave `regimeCoverage` (P3) — 🟢 CERRADO en `v2.71`

**Observación.** `regimeCoverage` era un **`float`** en `StrategyConfidence.as_dict()` y una **banda**
(`"HIGH"`/`None`) en `ReplayCell.as_dict()`: mismo nombre, dos formas.

**Cierre.** La celda de replay usa **`dominantRegimeCoverage`**. Protegido por **M197** y por el
contrato `test_the_regime_coverage_key_is_a_float_in_confidence_and_a_band_in_replay`.

## P3-1 — Flake ajeno del test runner (`core-r-scheduler.test.ts`)

**Estado: 🟢 CERRADA en `v2.69`.** Presupuesto **por fichero**
(`vi.setConfig({ testTimeout: 20_000, hookTimeout: 20_000 })`); la suite completa queda verde **sin**
flag global.

## P3-2 — Validación empírica de la correlación por cubos temporales

**Estado: 🔴 ABIERTA** (requiere el primer dataset PAPER real). La herramienta está lista en
`auto_evidence_validate.py` (`sharedSingleCycleShare`, ciclos/cubos activos por estrategia). Criterio
de cierre: comparar la correlación por cubos contra un oráculo por pares de ciclos emparejados y
declarar, **antes** de tocar la métrica, si la frecuencia/exposición sesga el número.

**Actualización `v2.75` (2026-09-26):** el instrumento queda **ejercitado de punta a punta** con el
material acumulado (`activeBuckets=1`, `pairs=[]`, sin inventar celdas; `minBuckets=4` respetado), pero
**no se cierra**: la muestra del productor determinista cae en **un solo bucket** (timestamps de reloj
real del mismo día). Cerrarla exige material PAPER REAL de mercado en **≥4 cubos**.

**Actualización `v2.76` (2026-09-26):** la **fuente de mercado** queda cableada —`MarketPriceSnapshot`
(XTB viva + cierre durable, fail-closed) inyectada por el seam público `price_script`, y **sin** fijar
`AUTO_ENGINE_SIM_V2_REGIME` para que el régimen salga de las barras reales— y el **par real de
versiones** (A = spine estampado `auto-2.0:<vA>`, B = ACTIVE `active-strategy:<vB>`) queda listo para
que **ambas** midan los **mismos cubos** sobre **una** cuenta. Pero la deuda **no se cierra** y ahora el
bloqueante está **medido y nombrado**: (a) la diversidad de cubos sale del **reloj real**
(`sim_fill_finance_context.created_at = datetime.now(UTC)`) y **exige ≥4 días de calendario
transcurridos** —ninguna corrida rápida los fabrica—; (b) el agregado de régimen es el veredicto **más
conservador** presente, de modo que **un solo** `trend_down` en un watch amplio deja el eje en
`BEAR_TREND` y el motor long-only veta por `regime_invalid` **todas** las entradas del tick (medido el
2026-09-26: 12 símbolos → `{range: 5, trend_down: 6, trend_up: 1}` ⇒ `BEAR_TREND`; forward de 8 ticks
con **0 fills**). **No se fuerza** el régimen ni se elige un watch «que pase»: se **declara**. Cerrarla
sigue exigiendo la **ventana de acumulación operativa** (≥4 días) con el mercado dando **≥2 episodios**.

**Actualización `v2.77` (2026-09-26):** el bloqueo deja de ser **opaco**: el **journal de operabilidad**
(`market_operability.py` + `v2_77_market_operability.py`) traduce cada forward a una fila diaria y
reparte el veto por **familia** (`regime`/`governor`/`liquidity`/`risk`/`top_n`/`data`/`other`), con la
regla fail-closed `no_signal` **sólo** si no hubo ni propuestas ni vetos. Sobre el smoke real la fila es
`2026-09-26 · BEAR_TREND · Long=NO · SimbOper=4/8 · Veto=64 · Fills=0 · CAPAZ` con `regime=40` +
`top_n=24`. La deuda **no se cierra** (no hubo ventana), pero ahora la causa de cada día **se mide en
una línea** y `pairCapable`/`pairActive` separan «arquitectura lista» de «dos versiones operando».
Comandos en el [relevo de `v2.77`](./traspaso-relevo-post-v2-77-auto-material-5-2026-09-26.md).

**Actualización `v2.82` (2026-09-27):** `AUTO-MATERIAL-10` es una fase **docs-only**: formaliza la
**ventana ≥4 días** como **operación del propietario** (runbook) y **no** la corre. La deuda sigue
**ABIERTA**; el instrumento (funnel + `unresolved_age` + HTML) queda **intacto** y **no** se cierra con
fixtures: exige material PAPER real en **≥4 cubos**.

**Actualización `v2.83` (2026-09-27):** `AUTO-MATERIAL-11` entrega el instrumento de **lectura acumulada**
de la ventana (`operability_audit.py` puro + `v2_83_window_audit.py` **read-only**: fila `TOTAL` y las
**tasas** `topNExclusionRate`/`riskRejectionRate`/`reservationFailureRate`/`fillRate`/`cycleRate`/
`unresolvedRate`), pero la deuda sigue **ABIERTA**: el instrumento **no** corre la ventana ni fabrica
medición (`n/d` ≠ `0`; el gate sigue siendo `INCONCLUSIVE` sin ≥4 días/≥2 episodios/≥32 ciclos). La
lectura por **cubos** sigue exigiendo material PAPER real.

## P3-3 — `P(R>0)` frente al tamaño muestral

**Estado: 🔴 ABIERTA** (requiere el primer dataset PAPER real). Regla que se mantiene: `P(R>0)` es
**evidencia descriptiva**; nunca se traduce en `confidence` ni en sizing. El barrido publica
`P(R>0)`, `P(R>0)` OOS, WFE y `effective_n` sobre el prefijo cronológico para `N ∈ {16,32,64,128}`.

**Actualización `v2.75` (2026-09-26):** el barrido queda **ejercitado** (`16`/`32` medidos, `64`
`insufficient_measured_cycles`), pero **no se cierra**: con `R` casi constante y **un solo episodio**
(`episodes=1`), `P(R>0)=0.0000` con `Effective-N=1` es degenerado, no un edge. Cerrarla exige material
de mercado con diversidad real (`Effective-N > 1`).
**Nota `v2.71`:** el barrido ya publica la `P(R>0)` por **ciclos** (antes publicaba una mezcla por la
ambigüedad de H1).

**Actualización `v2.76` (2026-09-26):** el **precio real** ya entra por el seam y el **régimen** ya sale
de las barras (sin override), así que el material que produzca el forward dejará de ser «`R` casi
constante» y podrá tener `Effective-N > 1` **si** hay mercado que lo permita. Sigue **ABIERTA**: en la
medición del 2026-09-26 el universe no produjo **ningún** ciclo válido (agregado `BEAR_TREND` ⇒
`regime_invalid` veta las entradas LONG; 0 fills en 8 ticks), y la ventana ≥4 días **no se ha corrido**.
Cerrarla exige la **acumulación operativa real** con el watch pudiendo entrar (tendencia alcista/rango)
y, después, `AUTO-22`/`AUTO-23` sin bajar `folds`/`min_is`/`min_oos` ni `min_episodes`.

**Actualización `v2.77` (2026-09-26):** el **journal de operabilidad** deja el diagnóstico de cada día
en una fila y **declara la familia** del veto (`regime`, `governor`, `top_n`…). El smoke real da 0
fills con `regime=40` + `top_n=24` y **4/8** símbolos operables por sí mismos: el instrumento
**cuantifica** la tensión del agregado conservador sin concluir. El barrido (`P(R>0)` por ciclos,
`Effective-N`) sigue **sin poder cerrarse** porque no hay ciclos válidos: **ABIERTA** por falta de
ventana real de mercado.

**Actualización `v2.82` (2026-09-27):** `AUTO-MATERIAL-10` (docs-only) mantiene la deuda **ABIERTA**: la
ventana **≥4 días** con **≥2 episodios** sigue siendo **operación del propietario**, y la fase **no**
rebaja `folds`/`min_is`/`min_oos`/`min_episodes` para forzar una corrida.

**Actualización `v2.83` (2026-09-27):** `AUTO-MATERIAL-11` mantiene la deuda **ABIERTA**: añade la
**lectura** de la ventana (`TOTAL` + tasas, read-only) pero **no** la corre y **no** rebaja
`folds`/`min_is`/`min_oos`/`min_episodes`. El preflight de 2026-09-27 volvió a **vetar** las entradas
LONG (`exit 2`, `BEAR_TREND`: `{range:8, trend_down:9, trend_up:3}`), así que sigue sin haber ciclos
válidos que barrer.

## P3-4 — `build_current_regime_evidence` publica el `level` sin clampar (P3) — 🟢 CERRADA en `v2.72`

**Origen:** auditoría externa de `v2.71-beta` (2026-09-26). **Preexistente** (idéntico en `v2.70-beta`;
el diff `v2.70 → v2.71` **no** lo toca) y **ajena a las 15 tesis** de la fase.

**Observación.** `build_current_regime_evidence`
(`auto_adaptive_regime_evidence.py:177`) hace `resolved_level = level` **sin clampar** y lo emite en
`CurrentRegimeEvidence.level`, mientras el bootstrap aguas abajo (`build_adaptive_uncertainty`) **sí**
clampa (`MIN_INTERVAL_LEVEL`/`MAX_INTERVAL_LEVEL`). Medido con sonda: `level=0.0` se **publica** `0.0`
pero la incertidumbre **usa** `interval.level=0.5`. Es la **misma clase** que **H3**, que la fase cerró
**solo** en `build_replay_report`.

**Impacto.** **P3**: evidencia **read-only** (`AUTO-21`/`AUTO-23` no mueven reparto, sizing, plan ni
reserva); solo observable con un `level` **no default**.

**Criterio de cierre.** Clampar `resolved_level` en `build_current_regime_evidence` y publicar el nivel
**efectivo**, subir el sello `current_regime_evidence_v2` → **`v3`**, y añadir la mutación + test
correspondientes.

**Cierre (`v2.72`).** `resolved_level = min(max(float(level), ADAPTIVE_INTERVAL_LEVEL_MIN),
ADAPTIVE_INTERVAL_LEVEL_MAX)` **antes** de publicarlo, igual que `build_replay_report` (`H3`, `v2.71`) y
`CalibrationReport`; sello subido a **`current_regime_evidence_v3`**. Protegido por **`M198`** y por
`test_the_interval_level_is_clamped_and_published` (que además comprueba que la celda publicada es la
**misma** que con el nivel clampeado explícito: no hay segunda aritmética) y
`test_the_clamped_level_travels_even_without_cycles`. Con el `level` default (`0.90`) el payload es
**idéntico salvo el sello `method`** (`current_regime_evidence_v2` → `v3`, que sube por diseño).

**Confirmado por la auditoría externa de `v2.72-beta`** (2026-09-26): `APROBADO CON OBSERVACIONES`,
**0 bloqueantes**, 10/10 tesis PASS; `M198` muerde los dos tests del clamp y restaura **byte a byte**;
`P3-4` **CERRADA**. La única observación (H-1, LOW documental) fue precisamente el «payload
byte-idéntico» de este documento, ya corregido. **Doble pasada:** la segunda auditoría, hecha **desde un
clon fresco de GitHub** (tag `82b231d3` → `0f8cc888`), reproduce el mismo veredicto y **re-ejecuta el RUN
BLOQUEADO** contra PostgreSQL vivo con los mismos números.

**Nota INFO declarada (2026-09-26, no es deuda ni defecto).** En
`test_the_interval_level_is_clamped_and_published`, las aserciones de **identidad de celda**
(`evidence_for(v)` con `level` fuera de rango == con el nivel clampeado explícito) pasarían **también con
`M198`**, porque `build_adaptive_uncertainty` **clampa por su cuenta** aguas abajo; la **mordida** de
`M198` proviene de las aserciones del `level` **publicado**. El contrato **sí muerde** (2 rojos), pero la
propiedad «no hay segunda aritmética» la garantiza el clamp del bootstrap, **no** ese test. Se deja
anotado para no sobre-confiar en la cobertura de ese test; endurecerla requeriría un doble que **no**
clampe por su cuenta.

## P3-5 — `reserved_risk` sobrecargado: libro vivo vs evidencia histórica — 🟠 ABIERTA (2026-09-26)

> **`v2.82` (2026-09-27):** sigue **ABIERTA y declarada**; `AUTO-MATERIAL-10` **no** la aborda (fase
> operativa docs-only, cero cambios de código).
>
> **`v2.83` (2026-09-27):** sigue **ABIERTA y declarada**; `AUTO-MATERIAL-11` **no** la aborda (fase de
> INSTRUMENTO **read-only**: módulo puro + CLI de auditoría, **sin** tocar el store ni el motor
> congelado; requiere migración, que esta fase **no** añade).

**Origen.** Seguimiento del punto 12 de `v2.74`: ¿`AUTO-19` (`cycle_risk_from_reservations`) obtiene el
riesgo histórico de una evidencia **inmutable** del ciclo o del estado **mutable** del `ReservationLedger`?

**Observación.** Ninguna de las dos, exactamente. `cycle_risk_from_reservations` **no** lee el ledger vivo
(lee filas durables de `portfolio_reservations`, vivas y liberadas, y filtra `is_buy and reserved_risk > 0`),
pero **tampoco** existe una entidad `CycleEvidence`: lee la **misma** columna
`portfolio_reservations.reserved_risk`, cuya semántica depende del estado — vivo mientras `OPEN`; histórico
tras el cierre, porque `_release()` la sobrescribe con el riesgo comprometido en el alta
(`reserved_risk × quantity / remaining_qty`, `_committed_risk`). Es una **reconstrucción tardía en el
store**, no un snapshot inmutable de entrada.

**Riesgo.** Un lector que no conozca la convención puede leer "riesgo actual `0`" donde el productor quiso
decir "riesgo comprometido `X`". La reconstrucción es exacta para la liberación total intacta y para la
última liberación de una escalera (cubierto por `test_portfolio_reservation.py`), pero la garantía vive en
el store y no en el modelo.

**Criterio de cierre.** O una columna/entidad dedicada e inmutable (`reserved_risk_at_entry` / `CycleEvidence`)
o declarar la convención como contrato explícito del store. Requiere migración Alembic (hoy head
`046_fill_reference_mid`); **no** se aborda en `v2.74` (alcance acordado: solo E2E).

**Evidencia de que no bloquea `PRODUCER_READY` (2026-09-26).** El E2E PostgreSQL
`apps/api-python/tests/test_auto_v74_producer_pg_e2e.py` demuestra que la estructura del productor V2
sobrevive al COMMIT y el gate la reconstruye desde una conexión **nueva**: la fila durable de la reserva de
ENTRADA de un ciclo cerrado conserva `reserved_risk > 0` con `remaining_qty = 0`. La convención funciona;
lo que falta es modelarla explícitamente.

**Hallazgo declarado (no bloqueante).** En la misma corrida, el productor V2 deja VIVA una reserva de
SALIDA (`side='sell'`, `reserved_risk = 0`) de un intento de salida superado por otro, tras quedar la
posición plana. No puede ser denominador de R (solo una reserva de COMPRA con `reserved_risk > 0` lo es) y
no altera el veredicto, pero es una reserva viva después del cierre: queda declarada como observación del
productor, fuera del alcance de esta fase (`auto_simulation_worker.py` sigue congelado).

## P3-6 — La contabilidad por familias no es de vetos puros: `approved` y `risk_exit` engordan `other` — 🟢 CERRADA en `v2.79` (reabierta por `H-1`)

**Origen.** Auditoría externa de `v2.77-beta` (clon fresco del tag), **OBS-1 (MEDIUM)**. **No es
bloqueante** y **no** invalida el sello, pero es un defecto semántico real **en el caso de uso
principal** del instrumento que la fase entrega.

**Observación.** `build_operability_record` clasifica **todos** los `journalReasons`
(`market_operability.py:288-289`) y `_journal_reasons` agrega **todos** los `reasonCodes` del journal
(`v2_76_forward_market_material.py:449-451`). El journal V2 estampa `reasonCodes` con los motivos de la
**entrada y de la salida**: una decisión `approved` lleva `("approved",)` (`auto_v2_entry.py:2247`) y una
salida lleva `risk_exit` (`position_manager.py:71`). Ninguno de los dos está en `VETO_BUCKET_BY_REASON`
(`market_operability.py:93-128`), así que caen en `other` y **suman** en `veto_counted` (`:197-198`). En
un día que **sí opera**, por tanto, `vetoCounted > vetoes` y aparece una familia `other` que **no es un
veto**.

La aserción `test_record_veto_counted_matches_the_declared_vetoes` pasa **solo porque** el smoke sellado
tiene `proposals = 0` (0 propuestas ⇒ ningún `approved`): la igualdad de hoy es una **coincidencia del
fixture**, no una propiedad del instrumento. Es decir: **fallaría precisamente en los días que existe
para medir** —los que operan—, que es justo cuando el propietario lo va a leer.

**Criterio de cierre (dos vías; elegir una y justificarla).** 1) **Excluir el no-veto del histograma**
antes de clasificar (filtrar `approved` y los motivos de salida) y declararlo en el contrato del módulo;
o 2) **derivar `vetoCounted` de `turnTotals.vetoes`** —la fuente que publica el motor— y dejar el
histograma por familias como **desglose de causas**, no como suma de vetos. En ambos casos: un test que
ejercite un payload **con** `approved` y `risk_exit` (no solo el smoke de 0 propuestas) y una mutación
nueva en la matriz. **Sin** tocar el motor ni el gobernador: es la **lectura** del journal, no la
decisión.

**Reversión.** Vuelve a estar mal si un día operado vuelve a publicar `vetoCounted != vetoes` o una
familia `other` con códigos que no son vetos.

**Cierre (`v2.78`, 2026-09-27).** Se eligió la **vía 1**: `split_journal_reasons` separa los VETOS de
las ATRIBUCIONES (`approved` ∪ motivos de salida ∪ saltos de gestión, importados del dueño
`auto_reason_codes`) **antes** de clasificar; `build_operability_record` clasifica sólo los vetos y
**publica** las atribuciones aparte (`nonVetoByCode` / `nonVetoCounted`), de modo que no se pierde
ningún dato. El contrato del módulo se declaró en `NON_VETO_REASON_CODES`. Protegido por
`test_operated_day_accounts_only_pure_vetoes` (fixture `_OPERATED_DAY` con `approved=3` + `risk_exit=1`
y `proposals>0`: `vetoCounted == vetoes == 2` y `other` **vacía**), por el contrato exhaustivo del
dueño (`test_every_decision_reason_code_is_declared_exactly_once`) y por **`M211`** (el no-veto vuelve
a contar como veto) y **`M213`** (se filtra pero se descarta). **No** se tocó el motor ni el
gobernador: es la **lectura** del journal.

**Reabierta PARCIALMENTE por la auditoría externa de `v2.78-beta` (2026-09-27) — `H-1` (MEDIUM).** La
corrección cubrió `approved`, las salidas (`risk_exit`/`time_exit`/…) y los saltos de gestión, pero
**no** el resto de eventos de **gestión de posición** que el worker congelado
(`auto_simulation_worker._journal_position_event` → `auto_v2_entry.build_position_management_journal_entry`,
payload `event="auto_position_management"`) anexa al MISMO journal: `protect_requested`,
`stop_ratchet_applied`/`_rejected`, `protection_missing`, `atr_geometry`, `lifecycle_transition_rejected`,
`lifecycle_state_unverified`, `reconciliation_required`, `no_mark_data`, `fill_not_materialized`,
`reservation_created`, `reservation_released_fill`. Medido: `journalReasons=["regime_invalid:2","approved:3","risk_exit:1","protect_requested:1"]`
con `vetoes=2` ⇒ `vetoCounted=3` y `other={protect_requested:1}` — **exactamente** el criterio de
reversión declarado arriba, alcanzable en el caso de uso principal (un día con posiciones vivas). El
smoke sellado (`proposals=0`) no lo ejercita. **CERRADA en `v2.79`** (censo de ENTRADA + canal de
posición aparte, ver `H-1` más abajo).

## P3-7 — `STATE_UNKNOWN` es inalcanzable: un payload vacío se lee como `no_signal` — 🟢 CERRADA en `v2.78` (2026-09-27)

**Origen.** Auditoría externa de `v2.77-beta`, **OBS-2 (LOW)**.

**Observación.** `operability_state` (`market_operability.py:275-281`) resuelve primero la condición
`proposals == 0 and vetoes == 0` y **después** comprueba `if not record: return STATE_UNKNOWN`; con un
payload vacío ambas cifras son `0`, así que gana `no_signal` y **`STATE_UNKNOWN` nunca se publica**. Un
JSON de entrada vacío, truncado o malformado se lee como «**sin señal**» —la lectura más
tranquilizadora posible— en vez de «**no medido**». Es fail-**open** ante entrada basura, en un módulo
cuyo contrato declarado es fail-closed.

**Criterio de cierre.** Que lo ausente no se pueda leer como un hecho del mercado: comprobar **primero**
la ausencia de registro/evidencia medible y declararlo con un test que pase un payload vacío. **Sin**
tocar el motor.

**Cierre (`v2.78`, 2026-09-27).** `operability_state` comprueba **primero** la ausencia: `not record`,
`measured == False` (la fila no trae `turnTotals`) o la falta de `proposals`/`vetoes` ⇒
`STATE_UNKNOWN`; sólo después resuelve `operated`/`no_signal`/`vetoed`. `build_operability_record`
publica `measured = bool(turnTotals)`. Protegido por `test_state_unknown_when_the_record_is_empty`,
`test_state_unknown_when_the_row_was_not_measured`, `test_state_unknown_when_absence_cannot_be_measured`
y `test_a_truncated_payload_is_declared_unmeasured`, y por **`M212`** (sin la comprobación de ausencia,
un payload sin medición se lee `no_signal`). Se conserva la lectura de filas ya escritas (`measured`
ausente ⇒ `True`). **Sin** tocar el motor.

## H-1 — Los motivos de gestión de posición inflan `vetoCounted` y caen en `other` (P3) — 🟢 CERRADO en `v2.79` (2026-09-27)

**Origen.** Auditoría externa de `v2.78-beta` (clon fresco del tag), **H-1 (MEDIUM)**. **No es
bloqueante** y **no** invalida el sello, pero es el defecto semántico que **`P3-6` no terminó de
cerrar** (ver arriba).

**Observación.** `market_operability.NON_VETO_REASON_CODES` solo declara `approved`, las salidas
(`risk_exit`/`time_exit`/…) y los saltos de gestión (`mark_rejected`/`decision_unavailable`). El
runner agrega `journalReasons` sobre **todas** las entradas del journal, y el worker congelado anexa
los eventos de **gestión de posición** (`auto_position_management`) con su propio `reasonCodes`:
`protect_requested`, `stop_ratchet_applied`/`_rejected`, `protection_missing`, `atr_geometry`,
`lifecycle_transition_rejected`, `lifecycle_state_unverified`, `reconciliation_required`,
`no_mark_data`, `fill_not_materialized`, `reservation_created`, `reservation_released_fill`. Todos
ellos caían en `other` y sumaban a `vetoCounted` **en el caso de uso principal** (un día con
posiciones vivas). Medido: `vetoCounted=3` con `vetoes=2` y `other={protect_requested:1}`.

**Cierre (`v2.79`).** El censo pasa a ser de **decisiones de ENTRADA**: `collect_journal_reasons`
filtra por `ENTRY_DECISION_EVENT` (`auto_entry_decision`), y los motivos de gestión se publican por
un **canal propio** (`positionEventByCode`/`positionEventCounted`, del conjunto del dueño
`POSITION_ATTRIBUTION_REASONS`) que **nunca** engorda `vetoCounted` **ni se descarta**. El runner
separa `journalReasons` (entrada) de `positionEventReasons` (posición). Protegido por
`test_the_audit_reversal_example_is_caught`, `test_position_management_events_are_published_not_discarded`,
`test_legacy_merged_rows_still_read_their_position_codes_as_non_veto` y **`M214`**/**`M215`**.

## H-2 — El contrato del dueño no cubre todos los dueños (P3) — 🟢 CERRADO en `v2.79` (2026-09-27)

**Origen.** Auditoría externa de `v2.78-beta`, **H-2 (LOW)**. `test_every_decision_reason_code_is_declared_exactly_once`
solo recorría `DecisionReasonCode`; añadir un código en `OPTIMIZER_REASONS`, `ADAPTIVE_STRATEGY_PAUSED`,
`POSITION_LIFECYCLE_REASONS`, `MATERIALIZATION_REASONS`, `RESERVATION_REASONS` o `NO_MARK_DATA` no
rompía ninguna compuerta.

**Cierre (`v2.79`).** El test recorre el vocabulario **completo** que puede llegar a `reasonCodes`
(`_OWNER_JOURNAL_CODES`) y exige que cada código esté **exactamente en uno** de los dos lados. Además
se declaran en `VETO_BUCKET_BY_REASON` los vetos de ENTRADA que faltaban (`OPTIMIZER_REASONS`,
`ADAPTIVE_STRATEGY_PAUSED`, `reservation_unmeasurable`, `reservation_already_live`). Protegido por
**`M216`**/**`M217`**/**`M219`**.

## H-3 — La disjunción veto/no-veto no estaba guardada por ningún test (P3) — 🟢 CERRADO en `v2.79` (2026-09-27)

**Origen.** Auditoría externa de `v2.78-beta`, **H-3 (LOW)**.

**Cierre (`v2.79`).** `test_veto_buckets_and_non_veto_codes_are_disjoint` exige
`VETO_BUCKET_BY_REASON ∩ NON_VETO_REASON_CODES == ∅`, y `POSITION_ATTRIBUTION_REASONS` **excluye
explícitamente** los tres vetos fail-closed de la reserva. Protegido por **`M218`**.

## H-4 — El test de exhaustividad omite el vocabulario de rechazo pre-ranqueo de `auto_v2_entry` (P3) — 🟡 ABIERTO (2026-09-27)

**Origen.** Auditoría externa de `v2.79-beta`, **H-4 (LOW)**, sobre el punto 5 del
[arranque del auditor](./arranque-auditor-v2-79-auto-material-7-operability-census-2026-09-27.md).

**Observación.** `test_every_owner_reason_code_is_declared_exactly_once` construye su conjunto de
«dueños» (`_OWNER_JOURNAL_CODES`, `test_market_operability.py:151`) **a mano** a partir de 10 fuentes y
**omite** las cinco constantes de rechazo **pre-ranqueo** de `packages/py/application/src/bolsa_application/auto_v2_entry.py`
(líneas ~2014-2028): `SIGNAL_DUPLICATE` (`signal_duplicate`), `SIGNAL_STALE` (`signal_stale`),
`SIGNAL_IDENTITY_MISSING` (`signal_identity_missing`), `SIGNAL_SUPERSEDED_BY_CANDIDATE`
(`signal_superseded_by_candidate`) y `SIGNAL_DISTINCT_STRATEGY_NOT_REPRESENTABLE`
(`signal_distinct_strategy_not_representable`).

**Impacto medido (re-derivado por el auditor).** Esos cinco códigos se emiten en eventos
`auto_entry_decision` —la **población del censo**, no la de gestión de posición— y **no** están
declarados ni en `VETO_BUCKET_BY_REASON` ni en `NON_VETO_REASON_CODES`, así que caen en `other` y
**suman a `vetoCounted`** (re-derivado con esos códigos: `vetoCounted=10` frente a `vetoes=0`).
**No se descarta ningún conteo** (el fallback de `other` los mantiene visibles): el defecto real es
que la **familia** queda vacía y que el test **afirma** una exhaustividad que **no** cumple sobre el
vocabulario real. **No es bloqueante** y **no** invalida el sello de `v2.79`.

**Nota de diseño.** A diferencia de `approved`/`risk_exit`/`DAY_EXIT_REASONS` (atribuciones), los
`signal_*` son **rechazos de candidato** ⇒ el arreglo natural es declararlos como **veto con familia**
(`signal_identity_missing`/`signal_stale` apuntan a `data`), no como no-veto. Es decisión de la fase
que lo cierre.

**Criterio de cierre.** Que `_OWNER_JOURNAL_CODES` **importe** el vocabulario de su dueño (no lo liste a
mano), que los cinco códigos tengan **familia declarada**, y una **mutación** (`M2xx`) que lo proteja.

**Estado en `v2.80` (2026-09-27).** `AUTO-MATERIAL-8` **no cierra `H-4`** (su alcance es la ventana:
`STATE_UNRESOLVED`, cobertura del catálogo y capturador), pero **lo hace visible**: `otherCount` /
`contractViolation` (AVISO) y `reasonCatalogCoverage["unknown"]` publican en el journal de operabilidad
exactamente los códigos que caen en `other` sin familia — antes se diluían sin señal —. El cierre formal
(familia declarada para los cinco `signal_*` y exhaustividad del test vía import) sigue **pendiente** y es
la fase candidata inmediata.

**Estado en `v2.81` (2026-09-27).** `AUTO-MATERIAL-9` tampoco cierra `H-4` (su alcance es el instrumento
de observación: funnel + `unresolved_age` + informe). Lo hace **más visible** todavía: el **funnel** separa
`signals → topN → risk → reservation`, de modo que un código `signal_*` que caiga en `other` se verá en la
distribución de motivos y en `reasonCatalogCoverage["unknown"]` con contexto. El cierre formal
(`_OWNER_JOURNAL_CODES` importando su dueño + familia declarada para los cinco `signal_*` + mutación) se
**pospone a después de la primera ventana real**, tal como recomienda la auditoría (§24): si esos códigos
aparecen durante la ventana, `otherCount>0` lo dirá y `H-4` dejará de ser deuda teórica.

**Estado en `v2.82` (2026-09-27).** `AUTO-MATERIAL-10` (docs-only) **no** cierra `H-4`: la decisión del
auditor es cerrarlo **después** de la primera ventana real y **sólo** si `otherCount > 0`; el funnel y
`reasonCatalogCoverage["unknown"]` siguen haciéndolo **visible**.

**Estado en `v2.83` (2026-09-27).** `AUTO-MATERIAL-11` **no** cierra `H-4` y **no** añade su
remediación (pospuesta por decisión del auditor, §24): la fase **lo hace visible en la auditoría** con el
aviso `reason_contract` (`other>0` ⇒ `ALERTA CONTRATO` + los motivos `other` nombrados) y con la cobertura
`unknown` del instrumento. Si esos `signal_*` aparecen durante la ventana, la auditoría lo dirá en una
línea; hasta entonces `H-4` sigue siendo deuda **teórica y ABIERTA**.

## OBS-6 / OBS-7 / OBS-8 — Observaciones de la auditoría externa de `v2.83.1-beta` (2026-09-27) — 🟢 CERRADAS en `v2.84`

**Origen.** Auditoría externa del objeto sellado **`v2.83.1-beta`** (clon fresco de GitHub; tag anotado
`e939bbf0` → commit `42c97bab`; `2.08.1-beta`). **Veredicto: `APROBADO CON OBSERVACIONES`, 0 bloqueantes**
(8 puntos: 6 PASS, 2 PARTIAL —semántica del instrumento y compuertas PG no reproducibles en local—). Los
tres hallazgos son del **instrumento de `v2.83`** (`operability_audit.py`, **byte-idéntico** en este tag:
el re-sello es docs-only), **no** los introduce `v2.83.1`. Informe crudo en
[`auditoria-v2-83-1-auto-material-11-reseal-2026-09-27.md`](./auditoria-v2-83-1-auto-material-11-reseal-2026-09-27.md).

### OBS-6 (MEDIUM) — `enrich_rows_with_evidence` **sobrescribe** un funnel ya medido

**Observación.** El docstring del módulo y el contrato de la fase prometen que el enriquecimiento con
`--forward` «rellena **sólo** los campos que la fila declaró `None`» y «**jamás** sobrescribe lo medido».
Pero `operability_audit.py:379` hace
`enriched["funnel"] = build_operability_funnel(row, evidence=evidence)` **incondicionalmente**: reconstruye
**todo** el funnel desde la evidencia, así que un escalón **ya medido** (`universe`, `orders`, …) se
**pisa** si la evidencia discrepa. Medido por el auditor: fila con evidencia (`universe=8`, `orders=2`)
re-enriquecida con otra evidencia (`watchSize=999`, `orders=99`) ⇒ `universe` 8 → **999** y `orders`
2 → **99**; los escalares (`symbolsObserved`, `pairActive`, `priceSources`) **sí** se preservan (siguen
el patrón `is None`). Los **16** tests cubren `pairActive` pero **no** el funnel ya medido.

**Impacto.** En el uso del runbook (`v2_83_window_audit.py --forward 'operability_runs/forward-market-*.json'`
sobre el bundle de `v2_80`) el resultado suele ser **idempotente** (la misma evidencia con la que `v2_80`
ya construyó el funnel), pero el **contrato** que el instrumento declara («no sobrescribe lo medido»)
**no** se cumple: un día cuyo JSON de forward se regenere/edite, o un bundle construido sin `--forward` y
auditado con él, puede publicar un funnel **derivado de la evidencia** en vez del medido. Es justo la
clase de defecto que `v2.83` vino a hacer imposible (`n/d` ≠ `0`, no fabricar medición).

**Criterio de cierre.** `enrich_rows_with_evidence` rellena **sólo** los escalones `None` del funnel (no
reconstruye los ya medidos), con un test que re-enriquezca una fila con funnel **ya poblado** y exija que
**no** cambie, y una **mutación** (`M2xx`) que lo proteja. Fase de **INSTRUMENTO** (read-only; sin motor,
gobernador ni migración).

### OBS-7 (LOW) — el funnel agregado de `window_totals` suma filas `measured=False`

**Observación.** `window_totals` excluye correctamente los días no medidos en `counts`/`coverage`/`rSum`
(usa `measured_rows`), pero el bloque **`funnel`** (`operability_audit.py:174`) itera **`rows`**: una fila
sin entradas/ciclos/fills (`measured=False`) pero **con evidencia** (`v2_80` puebla los escalones
superiores del funnel con `--forward`) **suma** en el agregado. Medido por el auditor: `daysMeasured=0`
con `funnel.universe=8` y `orders=2`. El `partial` del funnel queda `True`, así que **no** se oculta, pero
se incumple la lectura estricta «suma **sólo** días medidos» para ese bloque.

**Criterio de cierre.** Agregar el funnel sobre `measured_rows` (coherente con el resto de la fila `TOTAL`)
con un test de fila `measured=False` que **no** suma, y su mutación. Fase de INSTRUMENTO.

### OBS-8 (LOW) — los códigos de salida del CLI están documentados inexactos

**Observación.** `plan-v2-83` §3.2 y el docstring de `v2_83_window_audit.py` declaran `1` = uso
incorrecto, pero `argparse` sale con **`2`** (`… --bogus` → `exit 2`). Solo afecta a **documentación**.

**Criterio de cierre.** Alinear la doc con el comportamiento real (o el comportamiento con la doc) al
cerrar `OBS-6`/`OBS-7`.

**Cierre (`v2.84`, 2026-09-27).** Fase de **INSTRUMENTO READ-ONLY** (`AUTO-MATERIAL-12`): `enrich` pasa a
conservar cada escalón **ya medido** y a rellenar del reconstruido **sólo** los `None`
(`_fill_funnel_gaps`); el funnel agregado de `window_totals` itera `measured_rows` con `partial` contra
`daysMeasured`; y el docstring de `v2_83_window_audit.py` declara la realidad de `argparse`. Protegido por
`test_enrich_rows_never_overwrites_a_measured_funnel` + **`M231`** (`OBS-6`) y por
`test_window_totals_funnel_ignores_unmeasured_rows` + **`M232`** (`OBS-7`); `test_operability_audit.py`
**16 → 18 passed** y matriz **230 → 232** re-medida **232/232**. **`OBS-8`** se cierra por
**documentación** (es su naturaleza: `argparse` no ofrece un código distinto y forzarlo a `1` divergiría
de todos los CLIs hermanos — ver `OBS-9`). **Sin** tocar motor, gobernador ni migración.

## OBS-9 — La frase «`1` = uso incorrecto: lo decide `argparse`» está replicada y es inexacta (LOW, doc-only) — 🟡 ABIERTA (2026-09-27)

**Origen.** Al cerrar `OBS-8` se midió que la afirmación **no** es de `v2_83_window_audit.py`: el proyecto
declara el mismo contrato en varios CLIs y **ninguno** lo implementa (no hay `ArgumentParser` propio ni
`error()` sobrescrito; `argparse` sale con **`2`** en el uso incorrecto sea cual sea el script).

**Observación.** El código `1` que la doc promete es **inalcanzable** vía `argparse`; los scripts siguen
decidiendo bien `0`/`2`. **Ningún impacto funcional**: afecta a la **lectura** del contrato (y a un auditor
que lo compruebe, como pasó en la auditoría de `v2.83.1`).

**Criterio de cierre.** Barrido **docs-only** coherente (una sola convención: o se corrige la frase en
todos, o se implementa un parser compartido que devuelva `1`). **No** se aborda en `v2.84` (su alcance es
el instrumento auditado). Ficheros medidos con la frase: `v2_75_paper_sample_accumulation.py`,
`v2_76_forward_market_material.py`, `v2_77_market_operability.py`, `v2_80_market_window.py`,
`paper_material_readiness.py`, `paper_cycles_export.py`, `auto_evidence_validate.py`,
`ops_seed_window_pair.py` (instancia **NUEVA**, ver abajo), y en docs
`plan-v2-83` / `runbook-ventana-forward-v2.78` / `arranque-auditor-v2.73`.

> **`v2.84` (2026-09-27):** `OBS-9` queda **ABIERTA y declarada**; sólo se corrigió la instancia del
> instrumento auditado (`v2_83_window_audit.py`) al cerrar `OBS-8`.

> **`v2.84` — instancia NUEVA declarada por la auditoría externa (2026-09-28, hallazgo H-2):**
> `ops_seed_window_pair.py` (anexo operativo de `v2.84`) **introduce una instancia nueva** del mismo
> defecto: su docstring (`:44`) promete «`1` uso incorrecto» mientras `argparse` sale con **`2`** en el uso
> incorrecto de argv (su **validación manual** de argumentos sí devuelve `1`, coherente consigo misma, pero
> el nivel argv es `2`). Mismo patrón que `OBS-8` ⇒ **engrosa** el barrido declarado de `OBS-9`; **no** se
> corrige en la entrega docs-only (el fichero es `apps/`, prohibido con la ventana PAPER viva). Ver
> [`auditoria-v2-84-…`](./auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md) §3 (H-2).

## OBS-10 — `stateCounts` del TOTAL recorre TODAS las filas mientras el resto usa `measured_rows` (LOW) — 🟢 CERRADA en `v2.85` (`main`, 2026-09-28)

**Origen.** Auditoría externa del objeto sellado **`v2.84-beta`** (`AUTO-MATERIAL-12`; tag anotado
`e6d921a8` → commit `fd3859e3`; `2.09.0-beta`). El auditor la marca como observación a **vigilar** (no
bloqueante) dentro de un veredicto global `APROBADO` (0 bloqueantes) sobre una fase de instrumento.

**Observación.** En `window_totals` (`operability_audit.py`) el bloque `stateCounts` recorre **`rows`**
(todas las filas) mientras `counts`, `coverage`, `rSum` y `funnel` recorren **`measured_rows`**. El propio
auditor lo mide así:

```text
TOTAL
   ├── funnel      -> sólo medido
   ├── counts      -> sólo medido
   └── stateCounts -> podría incluir no medido   <-- la asimetría
```

Cita exacta del código (`packages/py/application/src/bolsa_application/operability_audit.py:144-148`):

```144:148:packages/py/application/src/bolsa_application/operability_audit.py
    state_counts: dict[str, int] = {}
    for row in rows:
        state = _text(row.get("state"))
        if state:
            state_counts[state] = state_counts.get(state, 0) + 1
```

**Matiz medido por esta fase (no lo tenía el auditor).** El escenario concreto del auditor
(`measured=False` **y** `state="unresolved"`) **no es alcanzable por los productores del repo**:
`operability_state` (`market_operability.py:448-449`) es **fail-closed** y devuelve `unknown` en cuanto
`measured` no es `True`, y `build_window_row` (`operability_window.py:482-484`) le pasa
`"measured": day_measured`. Por tanto, con el material producido hoy el **único** bucket afectado es
`stateCounts["unknown"]` (que absorbe los días no medidos). **Pero** `window_totals` es una **función pura
sobre filas arbitrarias** —el CLI consume `operability-window.json`/`window.jsonl` y los tests construyen
filas a mano—, así que una fila heredada, editada o fabricada **sí** dispara la inconsistencia. El
endurecimiento pedido es **válido** y esta fase lo registra en vez de argumentarlo.

**Sin impacto actual medido:** ningún test cubre `stateCounts` (hoy aparece sólo en docs), y los días no
medidos **ya** se publican aparte como `daysTotal - daysMeasured`, de modo que la información no se
pierde: lo que se declara es la **incoherencia de semántica** entre bloques del mismo `TOTAL`.

**Semántica decidida (2026-09-28, por el propietario).** `stateCounts` debe respetar **`measured_rows`**,
igual que `counts`/`coverage`/`rSum`/`funnel`. Los días no medidos quedan cubiertos por
`daysTotal - daysMeasured`, que ya se publica. No se consideró necesario declarar una semántica
intencionadamente independiente.

**Criterio de cierre.** `stateCounts` itera `measured_rows`; test
`test_window_totals_state_counts_ignores_unmeasured_rows` (fila `measured=False` con `state` poblado que
**no** cuenta); mutación **`M233`** (matriz **232 → 233**); compuertas completas. Fase de **INSTRUMENTO**
(read-only; sin motor, gobernador ni migración).

> **Aplazamiento declarado (`2026-09-28`).** **No** se corrige en la entrega docs-only de esta fecha: hay
> una **ventana PAPER en curso** (D1 lanzado 2026-09-28 00:02:32) y su propio registro exige que el árbol
> de **código** no se mueva durante D1..D4 (`git rev-parse "HEAD:apps" "HEAD:packages"` = `980c7b6e…` /
> `ffe36fd2…`); D1 ya se reinició una vez por un cambio de `packages` ajeno. Tocar `operability_audit.py`
> **invalidaría** la ventana, así que el fix se difiere a la fase de código **`v2.85` / `AUTO-MATERIAL-13`**
> (ver el [plan](./plan-v2-85-auto-material-13-statecounts-y-auditoria-comportamiento-2026-09-28.md)),
> **después** de cerrar la ventana. Registrado aquí para que no se cierre por documentación.

> **Mejora de lectura asociada (no la cierra `OBS-10`).** `unresolvedRate` es una tasa de **días** en
> estado `unresolved` sobre días medidos (declarado en `_RATE_SOURCES`), no de propuestas. Se aplaza su
> aclaración en render/docstring a `v2.85` por el mismo motivo (no tocar `packages` ahora).
> **Hecho en `v2.85` (2026-09-28):** `_RATE_SOURCES`, el docstring de `window_rates` y el render
> `_rate_lines` ya lo declaran **indicador** (ver `OBS-11`).

**Cierre (`v2.85` / `AUTO-MATERIAL-13`, 2026-09-28) — CERRADA por CÓDIGO, no por documentación.** En la rama
`feat/v2.85-obs10-comportamiento` (worktree aislado, **NO** mergeada a `main`; `main` intacto en
`63696d0c`), el bloque `stateCounts` de `window_totals` (`operability_audit.py`) **itera `measured_rows`**
—coherente con `counts`/`coverage`/`rSum`/`funnel`— y el docstring de `window_totals` lo declara. Protegido
por `test_window_totals_state_counts_ignores_unmeasured_rows` (`test_operability_audit.py` **18 → 19
passed**) y por **`M233`** (matriz **232 → 233**, re-medida **233/233**; crudo en
[`evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt`](./evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt)).
**Sin impacto medido sobre el material real:** sólo el bucket `unknown` podía contaminarse (los productores
son fail-closed) y ninguna cifra publicada se mueve. **La deuda cierra en la rama; su efecto definitivo se
materializa cuando la rama se mergee a `main`** (pendiente: `main` no puede moverse con la ventana PAPER
viva). Fase de **INSTRUMENTO** (read-only; sin motor, gobernador ni migración).

## OBS-11 — `unresolvedRate` es un INDICADOR (numerador == denominador), no una proporción (LOW) — ABIERTA (2026-09-28)

**Origen.** Al **etiquetar** `unresolvedRate` en la fase `v2.85`/`AUTO-MATERIAL-13` (tarea que el plan
pedía: aclarar su lectura **sin** renombrar la clave), se comprobó la aritmética y **no** encaja con su
etiqueta antigua.

**Observación.** En `window_rates` (`operability_audit.py`), `unresolved_pairs = [(1, 1) for row in rows if
_measured(row) and _text(row.get("state")) == STATE_UNRESOLVED]`, y `_rate_from_pairs` **suma** los pares ⇒
`numerador == denominador ==` número de días **medidos** en estado `unresolved`. Por tanto `rate` es **`1.0`**
en cuanto hay **un** día así, y **`None`** cuando no lo hay: es un **indicador binario** de presencia, **no**
una proporción **ni** una tasa de propuestas (el nombre `…Rate` sugiere una fracción, y el cálculo la hace
constante).

**Decisión tomada en `v2.85` (declaración honesta, NO cierre).** Se **etiqueta** correctamente
(`_RATE_SOURCES`, docstring de `window_rates` y render `_rate_lines`), **sin renombrar la clave** y **sin
cambiar la aritmética** ⇒ **ningún número publicado se mueve**. La pregunta de fondo (¿debe `unresolvedRate`
ser una fracción real, p. ej. días `unresolved` / días medidos, o mantenerse como indicador?) queda
**registrada aquí como deuda abierta**.

**Criterio de cierre.** Decidir la semántica de la clave (indicador declarado vs. proporción real), y —si se
opta por cambiarla— hacerlo **renombrando o versionando** la clave para no romper informes anteriores, con
test y mutación. **No** se aborda en `v2.85` (el plan sólo pedía etiquetar; cambiar la aritmética movería
una cifra publicada sin necesidad). Sin impacto funcional medido: la clave no decide nada aguas abajo.

> **Estado:** ABIERTA y declarada (2026-09-28). La **etiqueta** honesta ya está hecha; el **cierre** exige
> decidir la semántica, no documentarla.


## OBS-12 — Doble set documental en el objeto sellado y «Relevo vivo» apuntando al obsoleto (LOW, higiene documental) — 🟢 CERRADA en el re-sello `v2.85.1` (2026-09-28)

**Origen.** **Hallazgo del propietario**, no del CI: al ir a **auditar externamente** el tag `v2.85-beta`
desde GitHub, apareció que el objeto sellado contenía **dos sets documentales paralelos** de la **misma**
fase y que el punto de entrada (`PROJECT_STATE.md`) señalaba al equivocado.

**Observación (medida).**
- **Set docs-only previo** — `traspaso-relevo-post-v2-85-auto-material-13-comportamiento-2026-09-28.md` y
  `arranque-agente-v2-85-auto-material-13-comportamiento-2026-09-28.md`: declaran **«SIN bump y SIN tag»** y
  citan `HEAD` `d7a4924d` y el freeze **pre-merge** `980c7b6e…`/`ffe36fd2…` (ciertos **al autorarlos**:
  son **anteriores** a la ejecución de la fase).
- **Set de la fase ejecutada (vigente)** — los `…-auto-material-13-obs10-comportamiento-2026-09-28.md`.
- `PROJECT_STATE.md` llamaba **«Relevo vivo»** al set **docs-only**.

**Riesgo real (por eso es deuda y no cosmética).** Un auditor externo que clone **solo** el tag y siga el
punto de entrada aterriza en un documento que **niega la existencia del tag** («SIN tag») ⇒ hallazgo
**FALSO** del tipo «los docs se contradicen / no hay tag». Es el **espejo** del patrón `OBS-3`/`OBS-4`
(auditor leyendo el objeto sellado y concluyendo un falso negativo).

**Cierre (en `v2.85.1-beta`, docs-only).**
1. Cabecera **[SUPERSEDED]** en **los dos** documentos del set docs-only (**conservados**, no borrados).
2. `PROJECT_STATE.md`: «Relevo vivo» pasa a apuntar al relevo **real**; el docs-only queda marcado
   **[SUPERSEDED]**.
3. **Declaración explícita** de la duplicidad en **tres** sitios: el relevo del re-sello, el `audit-pack` y la
   evidencia del CI que **viaja dentro del tag** ([`evidencia-ci-tag-v2.85.1-2026-09-28.txt`](./evidencia-ci-tag-v2.85.1-2026-09-28.txt)).

**Por qué esta deuda SÍ se cierra con documentación (y no contradice la regla).** Es un defecto
**documental**: el arreglo **es** documental por naturaleza. La regla «ninguna deuda se cierra por
documentación» rige para deuda de **datos/semántica**: `P3-2`/`P3-3` exigen ventana PAPER **real**, `H-4`
exige `otherCount > 0` y `OBS-11` exige **decidir una semántica**. Este cierre **no** se usa como precedente
para ninguna de ellas.

**Verificación.** `git grep -l "SUPERSEDED" -- docs/engineering` devuelve los dos documentos del set
docs-only; `git diff v2.85-beta v2.85.1-beta -- packages apps` está **vacío** (el re-sello no toca código).

> **Estado:** 🟢 **CERRADA** (2026-09-28) en el re-sello `v2.85.1-beta`. Sin cambio de código, sin migración
> y sin mover el freeze.

## Observaciones de proceso de la auditoría de `v2.77-beta` — 🟡 DECLARADAS (2026-09-26)

No son deuda de código; se declaran para que no se lean como sorpresas en la próxima pasada.

- **OBS-3 / OBS-4 (LOW, patrón heredado).** La cita del CI (`evidencia-ci-tag-v2.77-2026-09-26.txt`) y la
  declaración del **rango** de 4 commits (audit-pack §1.b, punto 13 del arranque del auditor) viven
  **solo** en el commit **post-tag** `568ce317`. Leídas **desde el tag**, no existen: el auditor que
  trabaje estrictamente sobre el objeto sellado no ve la §1.b ni el punto 13. Es el **mismo patrón** de
  `v2.74`/`v2.75`/`v2.76` (la cita del CI siempre es posterior al tag, porque el workflow del tag solo
  corre al empujarlo) y el propio fichero de evidencia lo declara en su cabecera. **Criterio:** si una
  fase futura quiere que el auditor lo vea **dentro** del tag, la declaración del rango debe entrar en el
  commit **del sello** (o citarse por hash en el arranque del auditor, como se hizo aquí).
- **OBS-5 (LOW, defensivo).** `classify_veto_reasons` **descarta** entradas con conteo `<= 0` o no entero
  si se le pasa un mapping crudo; el parser del journal las coacciona a `1`, así que el camino real está a
  salvo, pero el contrato del módulo no lo declara. Anotarlo en el docstring o endurecer el tipo.

> **`v2.82` (2026-09-27):** `OBS-3`/`OBS-4`/`OBS-5` siguen **DECLARADAS**; `AUTO-MATERIAL-10` no las
> aborda. `OBS-3`/`OBS-4` se materializan también en `v2.82` (la cita del CI y el rango viven en el commit
> POST-TAG, patrón `v2.74`–`v2.81`).
>
> **`v2.83` (2026-09-27):** `OBS-3`/`OBS-4`/`OBS-5` siguen **DECLARADAS**; `AUTO-MATERIAL-11` no las
> aborda. `OBS-3`/`OBS-4` se materializan igual (cita del CI y rango en el commit POST-TAG, patrón
> `v2.74`–`v2.82`) y el tag `v2.83-beta` **sí se empujó**: su `Release tag CI` `36329460515` quedó
> **GREEN** en la primera pasada (`attempt 1`, 10 jobs + `certify`; job `python` `3020/37`; `quality`
> `3009/40`; cuatro jobs PG verdes). La cita vive en el commit **POST-TAG `80b18061`** (`main`) y la
> instancia del fichero **dentro** del tag es el **placeholder pre-tag** ("PENDIENTE DE TAG").
>
> **Reconciliación (`v2.83`, 2026-09-27) — falso positivo de auditoría.** Una revisión externa leyó el
> placeholder **dentro del tag** y lo declaró "CI del tag no acreditado". Es exactamente el patrón
> OBS-3/OBS-4 ya declarado (la cita **no puede** existir dentro del tag, porque `Release tag CI` solo
> corre al empujarlo): **no** hay CI pendiente. Se aplica el criterio propio del proyecto —citar el hash
> **POST-TAG** (`80b18061`) y el `run` (`36329460515`) en el **arranque del auditor** y en el audit-pack—
> para que el auditor **no** dependa de leer el objeto sellado aislado. Cadena verificada:
> `tag v2.83-beta` → `Release tag CI 36329460515` → **SUCCESS**. `OBS-5` sigue declarada (defensiva).
>
> **`v2.83.1` (2026-09-27) — RE-SELLO docs-only: `OBS-3`/`OBS-4` MATERIALIZADAS dentro de un tag.**
> `AUTO-MATERIAL-11` / `v2.83.1` (`2.08.1-beta`, **código idéntico** a `v2.83`; el diff `v2.83-beta..
> v2.83.1-beta` es **solo** `package.json` + `docs/engineering/*`) entrega el objeto auditado en un tag
> que lleva **dentro** la cita del CI de la fase (`Release tag CI` `36329460515`, **SUCCESS**), de modo que
> el auditor que clone **solo** el tag `v2.83.1-beta` ya **no** lee el placeholder «PENDIENTE DE TAG» ni
> puede concluir «CI no acreditado». **Límite estructural declarado (sigue vivo):** el CI del propio
> `v2.83.1` **no puede** existir dentro de su tag (ningún tag puede contener su propio resultado de CI,
> porque `Release tag CI` solo corre al empujarlo) ⇒ se cita en el commit **POST-TAG** mediante
> `evidencia-ci-tag-v2.83.1-2026-09-27.txt`, con el resultado esperado declarado (`python` del tag
> `3020/37`; `quality` `3009/40`). Es decir, `OBS-3`/`OBS-4` quedan **materializadas** en la entrega
> (la fase auditada y su cita van juntas en el mismo tag) sin que el patrón del workflow desaparezca.
> `OBS-5` sigue declarada (defensiva). Entrega: [arranque del auditor](./arranque-auditor-v2-83-1-auto-material-11-window-readonly-audit-2026-09-27.md)
> · [relevo](./traspaso-relevo-post-v2-83-1-auto-material-11-reseal-2026-09-27.md).
> **Acreditado (2026-09-27):** `Release tag CI` run `36333090789` **GREEN en la primera pasada** (`attempt 1`,
> 8m9s; 10 jobs + `certify`; job `python` del tag `3020/37`; `quality` `3009/40`; cuatro jobs PG verdes), con
> la **predicción pre-tag cumplida exacta**. El CI del **propio** `v2.83.1` sigue viviendo post-tag (cita en
> `evidencia-ci-tag-v2.83.1-2026-09-27.txt`), como el patrón exige.

## Deuda de AUDITORÍA — `v2.73-beta` (`AUTO-MATERIAL-1`) sin pasada externa — 🟡 ABIERTA (de proceso)

**Estado: 🟡 ABIERTA, declarada (2026-09-26).** `v2.73-beta` (tag anotado objeto `fd891fcd` → commit
`a9166655`) quedó **sellada y con CI verde** (`Release tag CI` `36244779500`, 10 jobs + `certify`) pero
**sin auditoría externa**: la fase siguiente (`v2.74-beta`, `AUTO-MATERIAL-2`) se construyó encima y
**evolucionó su superficie** —el gate subió a **`paper_material_readiness_v2`** (dos niveles
`PRODUCER_READY`/`EVIDENCE_READY`, `--level`, tres poblaciones) y el CLI ganó la población `DATABASE
TOTAL`—, de modo que auditar `v2.73` aislado revisaría una forma **superada** del mismo gate.

**Decisión (2026-09-26).** Auditar **`v2.74-beta`** —que **incluye y supera** el gate— y dejar `v2.73`
como **deuda de auditoría declarada aquí**, no como olvido. Puntos de entrada: el
[arranque del auditor de `v2.74`](./arranque-auditor-v2-74-auto-material-2-paper-producer-2026-09-26.md)
(16 puntos) y, si se quisiera la forma v1 sellada, el
[de `v2.73`](./arranque-auditor-v2.73-auto-material-1-paper-material-readiness-2026-09-26.md) (13 puntos)
contra su tag **inmutable**.

**Criterio de cierre.** La pasada externa sobre `v2.74-beta` cubre el **linaje** del gate (el módulo
`paper_material_readiness.py` y su CLI en la forma vigente); esta deuda se cierra cuando esa pasada
declare el linaje **sostenido**. Si el auditor pide una pasada específica sobre la forma **v1** sellada
en `v2.73`, se corre contra el tag con su propio arranque (el diff `v2.73-beta → main` es **solo docs**
⇒ el código del tag es el auditado).

## Bloqueante central — material PAPER real

**No es deuda P3: es el límite declarado.** `v2.71` **corrige el instrumento**; el **primer RUN
PAPER real** es el **paso operativo del propietario** y el **hito siguiente**. **No se bajan**
`min cycles` / `min R` / `folds` para forzarlo. No se toca `evidence_runs`/`evidence_validations` ni
el runbook.

**Actualización `v2.76` (2026-09-26).** El bloqueante deja de ser «falta el precio» y pasa a ser
**tiempo real + mercado**: `MarketPriceSnapshot` (XTB viva + cierre durable, fail-closed) entra por el
único seam del worker congelado (`price_script`) y el régimen ya **no** se fuerza
(`AUTO_ENGINE_SIM_V2_REGIME` sin fijar ⇒ `DiscoveryRegimeSource`). Queda **medido y declarado** que la
diversidad de cubos sale de **`created_at = datetime.now(UTC)`** (reloj real): ninguna corrida rápida
produce ≥4 cubos. Y queda **medido** que con watch amplio el **agregado conservador** de régimen puede
vetar **todo** el tick (`BEAR_TREND` por un solo `trend_down`; 12 símbolos → `{range: 5, trend_down: 6,
trend_up: 1}`, 0 fills). Por eso la ventana de **≥4 días** es la operación pendiente y el veredicto
correcto mientras el material siga degenerado es **`INCONCLUSIVE` / `NO MEDIDO`**, nunca forzar ni
rebajar umbrales. Comandos exactos en el
[relevo de `v2.76`](./traspaso-relevo-post-v2-76-auto-material-4-2026-09-26.md).

**Actualización `v2.77` (2026-09-26).** El bloqueante deja de ser **opaco**: el forward ya se lee como
**serie diaria** y cada no-operación se declara por su **familia** (`regime`/`governor`/`liquidity`/
`risk`/`top_n`/`data`/`other`). El smoke real queda en **`regime=40` + `top_n=24`, 0 fills, 4/8
símbolos operables, `CAPAZ` sin `ACTIVE`**. El instrumento **mide** el impacto del gobernador y de
`TOP_N`; **no** concluye. Sigue faltando **tiempo real**: la ventana de **≥4 días** (≥2 episodios) es la
operación pendiente del propietario; mientras no exista, el veredicto correcto es **`INCONCLUSIVE` /
`NO MEDIDO`**. Comandos exactos en el
[relevo de `v2.77`](./traspaso-relevo-post-v2-77-auto-material-5-2026-09-26.md).

**Corrección de lectura (auditoría externa de `v2.77-beta`, 2026-09-26; `v2.78`, 2026-09-27; matizada
por `v2.79`).** El instrumento **no** era de fiar en los días que **sí operan**: `approved` y
`risk_exit` caían en `other` e **inflaban** `vetoCounted` (**`P3-6`**), de modo que
`vetoCounted == vetoes` solo cuadraba en días **sin propuestas** (como el smoke sellado). `v2.78`
filtró esas atribuciones, pero la auditoría de `v2.78` midió que **`P3-6` seguía abierto** para el
resto de eventos de **gestión de posición** (**`H-1`**). `v2.79` cierra el caso general (censo de
**decisiones de ENTRADA** + canal de posición aparte), así que el desglose por familias de un día
operado vuelve a leerse como **censo**, no como cota superior.

**Actualización `v2.85.2` (2026-09-28).** El cierre de la ventana D1..D4 como **`NO MEDIDO`** se deja
**acreditado dentro del tag** `v2.85.2-beta`, con la **evidencia cruda** del día D1 (`forward-market-20260928.json`,
su cronología, su `stderr` y la fila de `v2_77`) en `docs/engineering/evidence/v2.85.2/` (los originales
viven en `operability_runs/`/`logs/`, **gitignoreados**). Registra **`OBS-13` (LOW, instrumento/diagnóstico),
NUEVA y ABIERTA**: en una corrida del **par** A/B, `vetoes` (totales del par, `8000`) y `vetoCounted` (censo
del journal del **worker primario** = versión A, `4000`) **no cuadran** por construcción del seam
(`_journal_reasons` lee `runtime.worker._v2_journal`; la versión B corre por `secondary` y no aporta) y
`contractViolation` **no** lo detecta (solo mide `other > 0`). Medido: `regime_invalid:2000` + `top_n_excluded:2000`
= los 10 símbolos de `watchA` (`5 × 400` + `5 × 400`). **No** es bloqueante (el veto es legítimo y el veredicto
`NO MEDIDO` no cambia), pero un auditor que compare la columna `Veto` con las familias verá el factor `×2`.
**Bloqueante operativo medido** (para el próximo intento): las barras de `ohlcv_bars` estaban **estancadas en
`2026-09-26`** ⇒ el eje no sale de `BEAR_TREND`; hay que **refrescar el material** antes de gastar más días.
> **REFUTADO por la Fase B (2026-09-28, ver más abajo):** medido read-only, las barras están **frescas**
> (`20/20` con barra `2026-09-28`, `{'current': 20}`) y el eje **sigue** en `BEAR_TREND`. El
> `2026-09-26` era un **artefacto de fin de semana** (1 barra), no un estancamiento del sincronizador.
> `OBS-13` queda además **CONFIRMADA** en una segunda muestra (sonda de 20 ticks).
`P3-2`/`P3-3` siguen **ABIERTAS**: exigen ventana real **con material**.

**Actualización `v2.85.2` — Fase B (operación, 2026-09-28, docs-only).** Ejecutado el procedimiento
operativo post-`v2.85.2` **sin tocar `apps/` ni `packages/`** (freeze intacto). **(1) El bloqueante
declarado en `v2.85.2` §2 queda REFUTADO por medición:** `ohlcv_bars` **no** está estancada —
**20/20** instrumentos del watch con barra **`2026-09-28`**, frescura `{'current': 20}`, último
`data_sync_log` `success` (`15:48–16:04Z`), `sync_settings` `auto_sync_enabled=True`,
`post_market_only=False`, `scope=lists`. El `2026-09-26` es **sábado** y aparece con **1 sola barra**
(artefacto recurrente de fin de semana, igual que `2026-09-19`/`2026-09-20`): se **declara**, no se
borra. **(2) Con el material fresco el eje SIGUE en `BEAR_TREND`** (preflight `exit 2`;
`{range: 6, trend_down: 9, trend_up: 5}` ⇒ `entriesAllowedLong=false`), así que la ventana sigue
**`NO MEDIDO`** y **no** se lanzó el forward de 400 ticks (la puerta del preflight evita el sobrecoste
de ~7 h). **(3) Sonda corta (20 ticks)** como evidencia parcial operativa (el `--out` solo se escribe al
terminar): `decided=400`, `proposals/orders/fills/cycles=0`, `vetoes=400`; nombre `probe-market-*` **fuera**
del glob `forward-market-*` de la ventana (dedupe `v2_77`: `0 fila(s) nueva(s), 1 ya presente(s)`).
**(4) `OBS-13` CONFIRMADA** en **dos** muestras (D1 del tag y la sonda): el censo cubre **exactamente**
`|watchA|` símbolos por tick (`censo/tick = 10.00`) y `vetoCounted == vetoes × |watchA| / |watch|`; su
arreglo sigue siendo **fase de código**. **(5) Hallazgo estructural medido en código:** `TOP_N` es un
tope de **evaluación** y corre **ANTES** del gate de régimen (`auto_v2_entry.py:1168-1207`), y el régimen
se pasa como **valor único por tick** (`auto_simulation_worker.py:2944`) ⇒ con `TOP_N=5` y `|watchA|=10`
salen **5 `top_n_excluded` + 5 `regime_invalid`** por tick; el 5/5 del censo es **coincidencia de
conteo**, no una clasificación por símbolo. **(6) Robustez registrada (NO implementada):** el
propietario anota en `P3-2` la necesidad de `watchdog`/`heartbeat`/`resume`/`checkpoint` +
**evidencia incremental** del `--out`, porque D1 perdió **~58 min** por suspensión del equipo y una
ventana de ≥4 días es frágil sin continuidad (`tick N → checkpoint → tick N+1`; `restart → recover →
continue` sin duplicar ciclos). Registro completo en
[`operacion-fase-b-preflight-y-sonda-2026-09-28.md`](./operacion-fase-b-preflight-y-sonda-2026-09-28.md).

## Fuera de alcance de esta deuda

- **Allocation dinámica** y **LIVE AUTO**: `❌`, no abordados.
- **Current-regime gating operativo**: fase posterior declarada.

## `AUTO-MATERIAL-14` / `v2.86` — Replay OOS de viabilidad (2026-09-29): evidencia nueva que **NO cierra** `P3-2`/`P3-3`

Fase de **instrumento de investigación** (sin bump, sin migración, sin tag) que añade una **clase de
evidencia nueva** —**replay OOS con reloj simulado**— a la cola de este expediente. **No cierra ni mueve
ninguna deuda de datos:** los cubos de calendario del forward se construyen con reloj de **pared**
(`sim_fill_finance_context.created_at = datetime.now(UTC)`), de modo que un replay determinista **no
puede** acreditarlos. Informe: [`replay-oos-viabilidad-auto-v2.86-2026-09-29.md`](./replay-oos-viabilidad-auto-v2.86-2026-09-29.md).

**Lo que la fase mide (y aporta al expediente):**

- **`P3-2`/`P3-3` (ABIERTAS).** El replay **no las sustituye**. La muestra (13 ciclos, un único episodio
  `2022-02 → 2022-05`, régimen `HIGH_VOLATILITY`) **no es concluyente**: `15.4 %` de signo positivo con
  `n=13` no decide nada sobre el edge. La ventana PAPER real **≥4 días con material** sigue siendo la
  única evidencia que las cierra.
- **Dato nuevo y reutilizable para `P3-2` (operabilidad histórica):** censo de **1 284 días** con
  **318 operables** (24.8 %, racha máxima **205**), desglosados por eje operativo
  `{HIGH_VOLATILITY: 310, SIDEWAYS: 8}`. **`BULL_TREND` operables = 0** en 5 años y la operabilidad se
  concentra en **2022 (218/257)** frente a 2023–2026 (100/950). Es la medición más directa hasta ahora de
  *por qué* cuesta tanto acumular una ventana: el régimen, no el material.
- **Dato nuevo sobre `OBS-13` (instrumento/diagnóstico):** el replay **reproduce** el patrón ya declarado
  (`TOP_N` como tope de **evaluación** que corre **antes** del gate de régimen; régimen **único por tick**;
  `5 top_n_excluded + 5 regime_invalid` por tick con `|watchA|=10`), esta vez sobre 5 años.
- **Causa declarada para el siguiente intento (deuda de INSTRUMENTO, nueva):** un replay multi-anual del
  motor congelado **no es viable hoy**: el libro de compromisos pendientes
  (`_v2_refresh_open_orders` = reservas + `execution_events` no-`APPLIED`) **no se retira** sin el ciclo
  durable completo de reserva→fill→liberación, y el motor —correctamente— deja de abrir
  (`risk_budget_exceeded`; o `open_orders_unmeasurable` sin el libro de reservas). El replay se trunca a su
  **primer episodio** tras `2022-05-06`, con **266 días operables** por delante. **No** se degradó ninguna
  compuerta para estirar la muestra. Queda registrado como **límite del instrumento**, no como resultado
  del motor.

**Robustez de la fase:** 18 tests puros nuevos, guardarraíles vecinos **71 passed**, `ruff` limpio y
**6 mutaciones nuevas `M234`–`M239`** (matriz **233 → 239**) **verificadas mordiendo 6/6**. Artefacto JSON
(2 054 030 B, gitignoreado) con **SHA-256 `91A871FB…143A90`**; resumen verificado en
[`evidence/v2.86/`](./evidence/v2.86/README.md).

**Regla vigente, sin excepción:** ninguna deuda de datos se cierra por documentación. `P3-2`/`P3-3`,
`OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5` y `OBS-5` siguen **ABIERTAS**.

## `AUTO-MATERIAL-15` / `v2.87` — Replay OOS del ciclo durable (`2026-09-29`): el instrumento de `v2.86` deja de truncarse; **NO cierra** `P3-2`/`P3-3` y abre `OBS-14`

Fase de **instrumento de investigación** (sin bump, sin migración, sin tag) que resuelve la causa raíz
declarada al cerrar `v2.86`: el libro de compromisos pendientes del replay hermético **no se retiraba**.
Informe: [`replay-oos-ciclo-durable-v2.87-2026-09-29.md`](./replay-oos-ciclo-durable-v2.87-2026-09-29.md).

**Lo que la fase mide (y aporta al expediente):**

- **`P3-2`/`P3-3` (ABIERTAS).** El replay **no las sustituye**: el reloj es **simulado** y los cubos de
  calendario salen de `datetime.now(UTC)`. La muestra ya es **multi-anual** (62 ciclos en 2022/2023/
  2024/2025, R medio −0.296, signo positivo 37.1 %) pero sigue siendo **un solo instrumento**, **una
  sola cuenta/versión/watch** y `pairActive=false`, así que **no es concluyente** sobre el edge.
- **Dato nuevo reutilizable (instrumento):** con la reconciliación de cierre (la **misma** rutina
  `_v2_reconcile_reservations(startup=False)` del arranque real) las reservas vivas nunca superan **1**
  (final **0**, `reservedRisk` final **0.0**), el horizonte se **completa** (1224/1224,
  `truncationReason=null`) y `risk_budget_exceeded` cae de **1 400** a **11**. La **contraprueba A/B**
  (`--no-durable-cycle`, mismo harness) **reproduce el goteo de `v2.86`**: 15 reservas huérfanas vivas,
  `$6000` comprometidos y toda la actividad congelada tras `~2022-05` (118 fills / 13 ciclos). El
  desbloqueo queda así **medido**, no narrado.
- **Instrumentación declarativa:** el artefacto publica `book` (serie diaria + medición), `releases`
  (delta `FILL` vs `CANCEL`) y `horizon` (`completed`/`lastDay`/`truncationReason`); una medición
  ilegible es `UNKNOWN` y una truncación sin causa es `undeclared_truncation`, nunca silencio. La
  retención `APPLIED` (900 < 1000) evita la parada dura `RECONCILIATION_FAILURE` de un replay multi-anual.

**Robustez de la fase:** 29 tests puros + 7 de costura nuevos, guardarraíles vecinos **71 passed**,
`ruff` limpio y **5 mutaciones nuevas `M240`–`M244`** (matriz **239 → 244**) **verificadas mordiendo
5/5**. Artefactos JSON (3 165 540 B y 2 949 320 B, gitignoreados) con **SHA-256 `DC61B3B9…C6C54F`** y
**`FE4CBF79…78CCD1`**; resumen verificado en [`evidence/v2.87/`](./evidence/v2.87/README.md).

## OBS-14 — El motor real también retiene reservas muertas entre reinicios (MEDIUM, alcance motor) — 🟢 CERRADA en `v2.88` (2026-09-29) · 🔁 corregida en `v2.88.1` · 🔁🔁 acotada por PROPIEDAD en `v2.88.2`

> **Nota de corrección 2 (2026-09-29 · RE-SELLO `v2.88.2-beta`).** La segunda versión del cierre de turno
> seguía siendo **fail-OPEN**, ahora por **carrera entre sesiones**: con evidencia durable (sin APPLIED, sin
> traza en vuelo, lecturas medibles) una sesión **no puede** distinguir «orden muerta sin llenar» de «orden
> que OTRA sesión aún no ha emitido en su propio turno», así que la perdedora liberaba la reserva **viva**
> de la ganadora y el fill que la ganadora materializaba después se quedaba sin fila viva que liberar
> (`released=200` frente a `materializado=147`). Lo detectó el `Release tag CI` del tag `v2.88.1-beta`
> (job `lifecycle-pg`, `test_concurrent_auto_pg.py`). La corrección es de **alcance**: el cierre de turno
> solo retira las reservas que **esta sesión** dio de alta (`only_ids` = `_v2_owned_reservations`); el
> barrido de **arranque** sigue siendo global. Detalle en
> [obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md](./obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md).
>
> **Deuda residual abierta en la misma corrección:** ver **`OBS-14.b`** (barrido de arranque sin ventana de
> gracia) más abajo en este mismo documento.

> **Nota de corrección (2026-09-29 · RE-SELLO `v2.88.1-beta`).** La primera versión del cierre de turno
> era **fail-OPEN**: al invocar la reconciliación en cada turno, su regla 1 **re-liberaba fills ya
> liberados** por el camino caliente y **drenaba la cola viva** de las órdenes parcialmente llenadas.
> Lo detectó el `Release tag CI` del tag `v2.88-beta` (job `lifecycle-pg`, crash/recovery). La
> corrección (`attribute_fills=False` en el cierre de turno; la reconciliación de arranque intacta)
> conserva el criterio de cierre de esta observación —retirar el huérfano que **nunca** se materializó—
> sin tocar las reservas con fill. Detalle en
> [obs-14-correccion-fail-open-v2.88.1-2026-09-29.md](./obs-14-correccion-fail-open-v2.88.1-2026-09-29.md).

**Origen.** Medido al cerrar `v2.87`: la fase demostró que el **único** camino que retiraba reservas
huérfanas del libro de compromisos era `_v2_reconcile_reservations`, y que su **único llamante de
producción** es el **arranque** del proceso (`_v2_reconcile_reservations(startup=True)`,
`auto_simulation_worker.py:4927`). El replay necesitó invocarlo **al cierre de cada tick** para no
gota; el motor real **no lo hace**.

**Observación (de instrumento a motor).** En producción, una reserva de **entrada** creada por
`_v2_plan_tick` que no llega a llenarse (el bucle de ejecución la veta/salta — p. ej. `held > 0`,
`position_reconciliation_not_ok`) queda **viva** hasta el **siguiente reinicio** del worker. Durante
esa ventana el libro de compromisos reporta `reservedRisk` inflado y el motor —correctamente— veta
aperturas con `risk_budget_exceeded` / `risk_measurement_partial`. **Es la misma clase de goteo** que
`v2.86` midió en el replay hermético, solo que acotada por el reinicio del proceso en vez de ser
permanente. **No** es un defecto de la decisión (el fail-closed es correcto): es que la **retirada** de
una reserva muerta depende del ciclo de vida del **proceso**.

**Impacto.** El replay de `v2.87` **cuantifica** la diferencia: con retirada por tick, 210 órdenes / 752
fills / 62 ciclos; sin ella, 31 / 118 / 13. Si el worker real se mantiene vivo mucho tiempo entre
reinicios, el mismo mecanismo puede **infra-abrir** sin que ninguna cifra publicada sea falsa (los
vetos son legítimos y están en el journal). **No** hay medición de producción todavía: es deuda de
**motor**, no de datos.

**Criterio de cierre.** Decidir **dónde** retira el motor las reservas muertas **sin** reiniciar: (a)
reconciliar en el **cierre de turno/tick** (lo que el replay demuestra que es fiel al motor SIM y
seguro), o (b) un `reconcile` periódico declarado (p. ej. al cierre de sesión), o (c) declarar
explícitamente que la retirada **solo** ocurre al arranque y que el veteo por goteo es intencional.
Cualquiera de las tres exige **fase de código del motor congelado** (`auto_simulation_worker.py`),
test y mutación, y **no** se aborda en `v2.87` (alcance **replay-only**). La evidencia de este intento
está en [`replay-oos-ciclo-durable-v2.87-2026-09-29.md`](./replay-oos-ciclo-durable-v2.87-2026-09-29.md) §5
y en [`evidence/v2.87/`](./evidence/v2.87/README.md).

**Reversión.** Vuelve a ser deuda teórica si se mide que el worker real **nunca** acumula reservas
huérfanas entre reinicios (p. ej. porque siempre hay un fill o porque el bucle de ejecución no deja
huérfanas). Hoy **no** hay tal medición.

**CIERRE (2026-09-29, sello conjunto `v2.88-beta` / `AUTO-MATERIAL-16`).** Se elige la **ruta (a)** del
criterio de cierre —*reconciliar en el **cierre de turno/tick***, lo que el replay de `v2.87` demuestra
**fiel al motor SIM y seguro*— y se implementa sobre el **camino durable**. Evidencia **medida**:

- **Hunk del motor:** `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`, diff **+7 / -0**,
  **un solo hunk** (líneas **4937-4943**), en `real_turn`, justo después de `report = await self.auto_turn()`
  y antes de `if auto_store is not None:`; la línea añadida es
  `await self._v2_reconcile_reservations(startup=False)`. `startup=False` ⇒ la etiqueta de la retirada es
  **`RESERVATION_RELEASED_BY_CANCEL`** (no `..._BY_RESTART`). **NO** se tocó `auto_turn`, ni el interior de
  `_v2_reconcile_reservations`, ni la regla de retirada, ni ningún umbral.
- **Por qué es fiel (medido en código):** AUTO es **solo** `{paper, simulated}` y **sin bridge LIVE**
  (docstring del módulo, `auto_simulation_worker.py:5`/`:13`); la orden o liquida dentro del tick
  (`submit_simulated_order`) o no se materializa nunca ⇒ una reserva viva al cierre cuya orden **no está en
  vuelo** está muerta. Va en `real_turn` (durable) y **no** en `auto_turn` (hermético, usado por decenas de
  tests y por el instrumento de replay) para **no perturbarlos**.
- **Tests:** la suite `apps/api-python/tests/test_auto_v2_durable_cycle.py` pasa de **7 a 11** (4 nuevos:
  `test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn`,
  `test_two_real_turns_do_not_drip_the_book_between_them`,
  `test_control_without_tick_close_reproduces_the_drip`,
  `test_closing_reconcile_keeps_captured_unapplied_capital_in_flight`). El **control** reproduce el goteo
  previo; el capital capturado y no aplicado se **conserva**.
- **Mutación:** **`M246`** («cierre de turno revertido») muerde **3/3**, árbol restaurado **byte a byte**.
  Compuertas: guardarraíles (10 suites) **142 passed**; `ruff` (comando exacto de CI) **All checks passed!**;
  matriz **246** (eran **239** en `v2.85.2`).

**Evidencia:** [`obs-14-cierre-por-turno-v2.88-2026-09-29.md`](./obs-14-cierre-por-turno-v2.88-2026-09-29.md) ·
[`evidence/v2.88/`](./evidence/v2.88/README.md). La deuda queda **CERRADA y MEDIDA**, no por documentación.

## OBS-14.b — El barrido de ARRANQUE tampoco distingue una huérfana de una reserva VIVA de otra sesión (MEDIUM, alcance motor) — 🟢 CERRADA en `v2.88.5` (2026-09-29)

> **CIERRE (`v2.88.5-beta` / `AUTO-MATERIAL-18`, 2026-09-29).** Implementado el **discriminador propuesto**
> en su forma exacta (**ventana de gracia por EDAD**), en el **motor**, con la ventana **declarada como
> parámetro medido** y **4 mutaciones** (`M250` re-anclada + `M254`/`M255`/`M256`). Diff del motor
> **+91 / −20** (5 hunks) en `auto_simulation_worker.py`; **SIN migración** (head `046_fill_reference_mid`);
> **SÍ se toca el motor** (a diferencia de `v2.88.4`). **(1) La regla 2 pasa a «PROPIEDAD *o* EDAD»:**
> `mine = only_ids is not None and reservation.reservation_id in only_ids` ⇒ se **CONSERVA** (fail-closed)
> si `not mine and not self._v2_reservation_is_aged(created)`. **(2) La ventana:** `V2_RESERVATION_GRACE_TURNS
> = 1` y `reservation_grace_window()` derivada de la **cadencia real del loop**
> (`AUTO_ENGINE_SIM_INTERVAL_SECONDS`, default **`60 s`**) ⇒ **60 s**, **no** un número mágico. El
> fundamento declarado: en este motor la orden **liquida DENTRO del tick** (solo `paper`/`simulated`, sin
> bridge LIVE), así que una reserva que superó **un turno completo** sin fill ni traza en vuelo está muerta
> **por construcción** — su dueño, sea quien sea, ya cerró su turno; la EDAD es el discriminador y **no**
> requiere identidad de sesión (que el esquema no tiene). **(3) Fail-closed por construcción:**
> `(self._time - created) > grace` con **`>` estricto** (el borde `age == 1 turno` **conserva**),
> `created is None` ⇒ **conserva**, y fecha **FUTURA** (relojes no comparables) ⇒ **conserva**; la
> comparación es contra `self._time`, la **misma** autoridad temporal con la que la sesión fecha sus
> altas. **(4) Retirada DIFERIDA y ACOTADA (declarada, no indefinida):** la huérfana que **aún no
> envejeció** sobrevive al barrido de arranque y se retira en el **primer cierre de turno posterior a la
> ventana** (`RELEASED_BY_CANCEL`) — a lo sumo **un turno más tarde** — o en el arranque siguiente
> (`RELEASED_BY_RESTART`). **(5) Simetría con `OBS-17`:** la ajena y joven conservada **no** entra en
> `outcomes` ⇒ `_v2_sync_exit_orders` la lee como `(0.0, None)` y **no** marca `ABANDONED` el `ExitOrder`
> del dueño. **(6) Tests (8 funciones nuevas ⇒ +7 netas):** `test_auto_v2_durable_cycle.py` **16 → 22** (cierre con joven
> conservada / envejecida retirada; **arranque** joven conservada / envejecida retirada; **fecha futura**;
> **borde estricto** a 1 turno; **INTENT de salida no abandonado**) y `test_auto_v44_exit_crash_matrix.py`
> **8 → 9** (`test_c2b_restart_inside_the_grace_window_retains_and_then_converges`: reinicio **dentro** de
> la ventana **retiene** y el siguiente, ya envejecido, **converge**); re-anclados a la semántica de edad
> explícita `test_auto_v44_exit_crash_matrix.py` (`C2`/`C4`), `test_auto_v44_exit_governance.py` (9) y
> `test_auto_v46_crash_recovery.py` (2). **(7) Mutaciones (matriz `253` → `256`):** `M250` **re-anclada**
> (ventana **nula**), **`M254`** (ventana **infinita**), **`M255`** (edad **absoluta** ⇒ un reloj futuro
> cuenta como envejecido) y **`M256`** (borde **no estricto** `>=`); las cuatro direcciones de la ventana
> tienen su mutación (`M250`/`M255` atacan el fail-closed; `M254`/`M256` la terminación).
> **(8) Verificación:** ciclo durable **`22 passed`**, matriz de crash **`9 passed`**, gobernanza
> **`9 passed`**, crash/recovery `v46` **`2 passed`**; `uv run ruff check packages/py apps/api-python
> --config pyproject.toml` → **All checks passed!**; batería offline completa con el comando **EXACTO** del CI (extraído del workflow) **`1 failed, 3085 passed, 4 warnings in 73.77s`** (**`3086` recogidos**; el único fallo es **PRE-EXISTENTE** de PG-local —`assert 17 == 26`— y en CI **se salta**); **matriz COMPLETA `256/256`** con el árbol **intacto**.
> **(9) Límite declarado:** la ventana (**60 s** con la cadencia nominal) es una decisión **declarada**, no
> medida en producción; el techo de retención de una huérfana es esa ventana. **La cita del CI es
> POST-TAG** (patrón `OBS-3`/`OBS-4`): esperado job `python` **`3049 passed, 37 skipped`** (los `3042` de
> `v2.88.4` + **7** netas), con los **mismos `37` skips** — **se cita el run, no se hereda**. **CITA REAL (POST-TAG, 2026-09-29):** `Release tag CI` run **`36581692155`** (HEAD `d16e3ade`, `ref=v2.88.5-beta`) → **`SUCCESS` en la PRIMERA pasada** (`attempt 1`; `14:18:33Z → 14:27:33Z`, **~9m00s**), **10 jobs reales verdes + `certify` verde** y `playwright` integrado `skipped` por diseño; job `python` **verbatim** `3049 passed, 37 skipped, 6 warnings in 63.71s` ⇒ **ESPERADO = OBSERVADO**; `decision-spine 604 passed`, `a7-gate 7 passed` y `lifecycle-pg` **`220 passed`** en **8** invocaciones (**0 failed / 0 skipped**). Cita cruda: [`evidencia-ci-tag-v2.88.5-2026-09-29.txt`](./evidencia-ci-tag-v2.88.5-2026-09-29.txt). **NO** cierra `OBS-15` ni `OBS-16` ni `P3-2`/`P3-3`.
> Informe: [`obs-14b-ventana-de-gracia-arranque-v2.88.5-2026-09-29.md`](./obs-14b-ventana-de-gracia-arranque-v2.88.5-2026-09-29.md)
> · evidencia cruda: [`evidence/v2.88.5/README.md`](./evidence/v2.88.5/README.md).

**Origen.** Medido al corregir la **carrera entre sesiones** del cierre de turno (`v2.88.2`). El cierre de
turno quedó acotado por **propiedad** (`only_ids`), pero la reconciliación de **ARRANQUE** sigue barriendo
el libro **completo** de la cuenta.

**Observación.** El barrido de arranque decide con la **misma** evidencia durable que el cierre (sin
`APPLIED`, sin traza en vuelo, lecturas medibles) y por tanto **no puede** distinguir:

- una reserva **huérfana** que dejó un proceso muerto (lo que quiere retirar), de
- una reserva **viva** que **otra sesión** acaba de dar de alta y cuya orden **aún no ha emitido** en su
  propio turno (lo que **no** debe tocar: retirarla devolvería al mercado un capital que sí se
  materializa después — el mismo fail-**OPEN** de `OBS-14`/`OBS-14.b` primos).

**Ventana de exposición.** Un **reinicio rodante** (arranca un motor mientras otro opera la misma cuenta).
En el arranque simultáneo de varias sesiones la ventana es nula (todas barren antes de que ninguna
reserve), que es lo que mide la suite de CI; por eso el defecto **no** se ha manifestado en CI. **Ya era
así en `v2.85.2`** (no es una regresión de `v2.88`).

**Por qué no se arregla en `v2.88.2`.** Alcance acordado: la corrección de la fase es el **cierre de
turno** (el defecto que CI destapó). Tocar el arranque es una decisión de diseño con su propio radio
(qué se considera «huérfana» y con qué reloj).

**Discriminador propuesto (no implementado).** **Ventana de gracia por EDAD**: en el arranque, retirar una
reserva candidata solo si su `created_at` es anterior a `now − ventana` (la ventana debe cubrir un turno
completo del motor). Una reserva más joven se **conserva** (fail-closed) y el barrido del siguiente
arranque la recoge. Requiere declarar la ventana como parámetro medido y una mutación que la fije.

> **IMPLEMENTADO en `v2.88.5` (`AUTO-MATERIAL-18`)**, tal cual: ventana **declarada en TURNOS**
> (`V2_RESERVATION_GRACE_TURNS = 1`) y derivada de la cadencia real del loop (60 s con la nominal), con
> **retirada diferida** (cierre de turno posterior a la ventana, no solo «el barrido del siguiente
> arranque») y **4 mutaciones** que la fijan. Ver el bloque de cierre al inicio de esta sección.

**Estado de la evidencia.** El comportamiento ANTERIOR quedó **caracterizado** (no aprobado) por
`test_closing_reconcile_does_not_touch_another_sessions_reservation`, que verificaba que el barrido de
arranque **sí** retiraba la huérfana ajena. **En `v2.88.5` ese test se sustituye por la semántica de
EDAD explícita** (`test_closing_reconcile_does_not_touch_a_young_foreign_reservation`,
`..._retires_a_foreign_reservation_once_it_aged`, `test_startup_sweep_retains_a_young_foreign_reservation`
y compañía) y la mutación **`M250`** se **re-ancla** a `_v2_reservation_is_aged` (ventana **nula** ⇒ las
retenciones se caen) para que siga mordiendo.

**Evidencia:** [`obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md`](./obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md) ·
[`evidence/v2.88.2/`](./evidence/v2.88.2/README.md).

## OBS-15 — El techo de lectura de 1000 filas `APPLIED` puede parar el motor (MEDIUM, alcance motor) — 🔴 ABIERTA (2026-09-29)

**Origen.** Registrada al sellar `v2.88` (`AUTO-MATERIAL-16`); el propietario decidió **registrar, no
arreglar** en esta fase (el arreglo toca varias capas, ver criterio de cierre).

**Medido en código.** `read_applied_fill_facts` (`packages/py/application/src/bolsa_application/applied_fills.py`)
lee `list_applied(account_id, limit=DEFAULT_APPLIED_LIMIT=1000)`; `PostgresExecutionEventStore.list_applied`
(`execution_event.py`) ordena `applied_at.asc()` y aplica `.limit(limit)` ⇒ **no** está acotado a una
jornada, pese al comentario de `applied_fills` («fills aplicados de una jornada AUTO»).
`truncated = len(events) >= limit` ⇒ `MEASUREMENT_UNKNOWN`.

**Efecto.** En `_v2_reconcile_reservations`, una lectura `UNKNOWN` implica que (a) la regla 1 no puede casar
ningún fill (`facts=()`), (b) la regla 2 **nunca** libera (no es `measurable`) y (c)
`_v2_reservations_measurement` queda `UNKNOWN` ⇒ el libro pendiente es `UNKNOWN` ⇒ el motor **veta
aperturas**. Con `>=1000` filas `APPLIED` acumuladas, la reconciliación de reservas **no puede** ser
COMPLETE y el motor deja de abrir.

**Declarado.** Es **preexistente** (la reconciliación de arranque lee idénticamente) y **NO** lo introdujo
la fase de `OBS-14`. Es fail-closed y **declarado** en el journal (no es corrupción silenciosa), pero es
una **parada dura alcanzable por operación normal**. **Radio de impacto:** afecta también a la
reconstrucción de **posición** (`read_position_ledger` y las posiciones canónicas usan el mismo límite por
defecto).

**Disparador.** `>=1000` filas con `status='APPLIED'` para la cuenta (derivado del código). La **madurez de
la cuenta real está `NO MEDIDA`** (una sonda read-only fue **bloqueada por la revisión automática**); no se
estima.

**Criterio de cierre.** Hacer que la lectura de fills de la reconciliación de reservas sea COMPLETA **para
su propósito**, acotándola a la **ventana viva** (p. ej. `since = min(created_at)` de las reservas vivas,
ya que la regla 1 solo casa fills con `applied_at >= created_at`), y/o acotar honestamente la lectura de
posición. Exige tocar `applied_fills` + protocolo del store + InMemory + Postgres + tests + mutaciones.

**Nota.** La ventana de retención de **900** de `v2.87` es una mitigación **interna al instrumento**
(`_RetentionExecutionEventStore`, solo replay); **no** existe en producción. Cerrarla es **fase de código
del motor**, no de instrumento.

## OBS-16 — La verificación local puede NO cubrir la batería offline del CI (MEDIUM, proceso) — 🔴 ABIERTA (2026-09-29)

**Origen.** Medido en **tres rojos consecutivos** de tag (`v2.88-beta` → `v2.88.1-beta` → `v2.88.2-beta`).
El tercero lo destapó en su forma más pura: el motor estaba **correcto** y el CI cayó por un
`AttributeError` de una **costura de test**.

**Observación.** La validación local de esta fase se hizo **por suites vecinas** (carrera `7 passed`, ciclo
durable `14`, instrumento `14`, vecinos del motor `49 passed`, pasos saltados de CI `5 passed`) y **no**
por la **batería offline completa** que ejecuta el job `python (ruff/imports/mypy/pytest offline)` del
workflow del tag. Esa batería recorre **3077** tests y es la puerta real.

**Dos mecanismos, ambos medidos:**

1. **La batería no se corría entera.** Cubrir por vecindad deja fuera ficheros que ejercitan la misma
   ruta por otra puerta.
2. **15 costuras `object.__new__(AutoSimulationWorker)` duplican a mano el estado del worker**, porque
   construyen el objeto **sin `__init__`** para aislar la costura de la aritmética. Consecuencia
   estructural: **cualquier atributo nuevo del `__init__`** que una ruta de costura use **rompe el job
   offline sin aviso local**. En `v2.88.2` pasó exactamente eso con `_v2_owned_reservations`
   (`test_auto_v51_auto10_cycle_journal_seam.py`, **6** tests).

**Radio.** Alto en **frecuencia** (el patrón se repite en 15 ficheros y estos sellos añaden atributos al
`__init__`), bajo en **daño** (es un rojo de CI, no un defecto de motor: el camino de producción sí pasa
`__init__`).

**Mitigación ADOPTADA y MEDIDA (en `v2.88.3`).** *«Antes de sellar, correr la batería offline del CI»*: se
**extrae el comando del propio workflow** (step `Pytest offline`) y se ejecuta **entero** en local. Nota de
entorno: los ejecutables `pytest` y `mypy` están **bloqueados por Windows Application Control**
(`os error 4551`), así que el sustituto medido es `uv run --no-sync python -m pytest <mismos argumentos>`.
Resultado de referencia: **3076 passed, 1 failed** (el fallo es el de entorno ya conocido
`assert 17 == 26`, material sembrado; en CI se salta porque ese job no tiene Postgres).

**Mejora posible, NO implementada.** Una **fábrica de costura compartida** que derive el estado del
`__init__` en vez de duplicarlo a mano (p. ej. `object.__new__` + un `_seed_worker_state(worker, **overrides)`
único), de modo que añadir un atributo al `__init__` no deje 15 ficheros desincronizados.

**Criterio de cierre.** Que la validación previa al sello incluya la batería offline completa **como paso
declarado** (y, opcionalmente, que las costuras compartan la siembra del estado).

**Evidencia:** [`obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md`](./obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md) ·
[`evidence/v2.88.3/README.md`](./evidence/v2.88.3/README.md).

---

## OBS-17 — La pata de SALIDA (`_v2_reserve_exit`) no tiene test ni mutación: el ownership está demostrado solo en la ENTRADA (MEDIUM, alcance motor/tests) — 🟢 CERRADA en `v2.88.4` (2026-09-29)

**Origen.** **Hallazgo de la auditoría externa de `v2.88.3-beta`** (**`APROBADO`, 0 bloqueantes**), que lo
señala como **«la siguiente mejora técnica prioritaria»**. **Ya estaba DECLARADO** en el handover
(§8, «pata de SALIDA sin cobertura») y en el informe de `v2.88.3`; aquí **adquiere ID propio** y un criterio
de cierre con su mutación.

**Observación.** El sello `v2.88.3` cubre el **alta** de propiedad con la mutación **`M252`** (el tick
persiste la reserva pero **no** registra su dueño ⇒ la cazan 6 tests). Pero la **otra** pata de alta —
`_v2_reserve_exit`, documentada en el docstring del worker — **no** tiene test ni mutación dedicados
(ningún test la ejerce). Contrato del ciclo:

```text
ENTRADA  reservar → propietario   🟢 (M252)
SALIDA   reservar → propietario   🔴 (sin cobertura)
```

⇒ El contrato **no está simétricamente demostrado**: `v2.88.2` acotó el cierre por **propiedad**
(`only_ids = frozenset(self._v2_owned_reservations)`, alimentado en los **dos** puntos de alta — `save_claim`
ganado en `_v2_persist_tick_reservations` **y** `_v2_reserve_exit`) y **solo** la pata de entrada tiene
prueba adversarial. Un defecto de ownership en la **salida** (liberar la reserva de salida de **otra**
sesión, fail-**OPEN** de carrera) no lo cazaría hoy ningún test ni mutación.

**Radio.** Bajo en **frecuencia** (una sola ruta, la de `EXIT_ONLY`/salida), **alto en daño** si ocurre: es
capital comprometido devuelto al mercado, el **mismo** fail-OPEN que motivó `v2.88.1`/`v2.88.2` — pero por la
pata que aún no está guardada por prueba.

**Criterio de cierre (lo que pide el auditor).** Test explícito de aislamiento de salida +
mutación **`M253`**:

```text
session A → reserve exit → session B → attempt reconcile
comprobar: B cannot release A's exit reservation
M253 (elimina el ownership de _v2_reserve_exit) → el test FALLA
```

`M253` ⇒ matriz `252` → **`253`**. Requiere: el test de costura de la pata de salida (hermético) + el
re-anclaje de `M253` al texto real de `_v2_reserve_exit` + corrida de la matriz completa con el árbol
restaurado **byte a byte**.

**CERRADA en `v2.88.4` (`AUTO-MATERIAL-17`, 2026-09-29).** Test + mutación entregados: **2** tests nuevos en
`apps/api-python/tests/test_auto_v2_durable_cycle.py` (**14 → 16**, hermético) —la **simetría** de ownership
(B no puede liberar la reserva de salida de A; A sí la suya) y el **CONTROL** fail-closed sin store de
reservas— y la mutación **`M253`** (matriz **252 → 253**), que **muerde exactamente** el test nuevo. `ruff`
**All checks passed!**, matriz COMPLETA **`253/253`** con el árbol **intacto** y **`0` cambios en el motor**
(`git diff v2.88.3-beta..HEAD -- packages/py apps/api-python/src` **vacío**). Cierre en el
[informe/relevo `v2.88.4`](./obs-17-simetria-ownership-salida-v2.88.4-2026-09-29.md) y su
[evidencia](./evidence/v2.88.4/README.md). **Límite declarado:** la corrida **real** de concurrencia/recovery
la acredita el job `lifecycle-pg` del CI del tag, **no** el test hermético. **CI del tag MEDIDO (POST-TAG,
patrón `OBS-3`/`OBS-4`)**: `Release tag CI` run **`36565287635`** (`HEAD cf246282`, `ref=v2.88.4-beta`) →
**`SUCCESS` en la primera pasada** (`attempt 1`, **~8m59s**; 10 jobs reales + `certify`,
`playwright` integrado `skipped` por diseño), job `python` **`3042 passed, 37 skipped`** = **ESPERADO
`3042/37` → OBSERVADO `3042/37`** (el falso rojo de la costura **no** reaparece) y `lifecycle-pg` **sin
saltarse** crash/recovery + 3 sesiones concurrentes + golden day + aislamiento de cuenta + HardKill +
exactly-once. Cita cruda: [`evidencia-ci-tag-v2.88.4-2026-09-29.txt`](./evidencia-ci-tag-v2.88.4-2026-09-29.txt).

**Evidencia:** [`auditoria-v2-88-3-auto-material-16c-2026-09-29.md`](./auditoria-v2-88-3-auto-material-16c-2026-09-29.md) (§14-§17) ·
[`entrega-auditoria-externa-mia-v2.88.3-2026-09-29.md`](./entrega-auditoria-externa-mia-v2.88.3-2026-09-29.md) (§8) ·
[`obs-17-simetria-ownership-salida-v2.88.4-2026-09-29.md`](./obs-17-simetria-ownership-salida-v2.88.4-2026-09-29.md) ·
[`evidence/v2.88.4/README.md`](./evidence/v2.88.4/README.md) ·
[`evidencia-ci-tag-v2.88.4-2026-09-29.txt`](./evidencia-ci-tag-v2.88.4-2026-09-29.txt).

---

## OBS-18 — La regla 2 decidía por el AGREGADO de fills del instrumento+lado, no por la evidencia de la RESERVA: hermanas nunca materializadas y colas muertas retenían capital para siempre (MEDIUM, alcance motor/instrumento) — 🟢 CERRADA en `v2.88.6` (2026-09-29) · 🔁 atribución EXACTA por ciclo en `v2.88.7` (`OBS-20`)

**Origen.** **Medición de la RE-EJECUCIÓN del replay OOS multianual** de `AUTO-MATERIAL-15` (`v2.87`),
que `v2.88.1` había declarado **obligatoria** (su artefacto se midió con la costura previa a la guarda
de `attribute_fills`). Al re-ejecutarlo sobre `v2.88.5-beta` el replay **volvió a truncarse**: el libro
retenía **16 reservas vivas** y **`$5999.9998 / $6000`** de riesgo comprometido (`risk_budget_exceeded`
**1400**), con la actividad congelada tras `2022-05-06` — **y el horizonte lo publicaba como
`completed: true`**. **ID nuevo**: la observación no estaba registrada como deuda (se descubre aquí, con
su medición).

**Observación (motor, regla 2 de `_v2_reconcile_reservations`).** El discriminador era un **total ajeno a
la fila**:

```python
filled = 0.0
for instant, qty in applied.get((instrument, reservation.side), ()):
    if instant >= created:
        filled += qty          # AGREGADO del instrumento+lado posterior al alta de ESTA fila
...
and filled == 0.0              # ← el agregado decide por ELLA
```

Dos huecos, los dos **medidos**:

| Caso | Evidencia de la RESERVA | Agregado | Regla 2 sellada | Resultado medido |
| --- | --- | --- | --- | --- |
| **Nunca materializó, hermana llenó** | `released_qty == 0`, sin traza en vuelo | `filled = 4 > 0` | **no retira** | capital retenido **para siempre** |
| **Cola de fill parcial muerta** | `released_qty = 4 > 0`, `remaining_qty = 6 > 0`, sin traza en vuelo | `filled = 4 > 0` | **no retira** | capital retenido **para siempre** |

La **regla 1** solo libera lo **materializado** (`released_qty`), así que la **cola** de un fill parcial
cuyo `INTENT` ya no está en vuelo **no la retiraba nadie**. Con el presupuesto agotado al 100 %, el motor
deja de proponer: **el replay se truncaba** (misma huella que `v2.86` ya había medido, pero ahora con el
libro *sucio* en vez de *inflado*).

**Impacto.** El replay multianual —el instrumento que `v2.87` usó para afirmar *«62 ciclos en 4
temporadas»*— **no era estable**: la muestra se cortaba a un solo episodio de `2022`. Y el artefacto
publicaba la corrida truncada como **completa**.

**Observación (instrumento, dos huecos de declaración).** (a) El log de retiradas del arnés registraba
estado, instrumento e instante… **y no la causa**: el artefacto publicaba `byDeadTail: 0` sobre **64**
retiradas — un **cero silencioso** («no medí el motivo» leído como «ninguna fue una cola muerta»).
(b) Un libro con capital comprometido y sin actividad **no** se declaraba: no existía umbral de
**estancamiento**.

**Criterio de cierre.** (1) La regla 2 decide por la **evidencia de la fila**
(`materialized = float(reservation.released_qty or 0.0)`), con la guardia de `in_flight` **mandando**
(fail-closed) y el `outcome` publicando la evidencia **de la reserva**; (2) motivo de contrato nuevo
`RELEASE_REASON_DEAD_TAIL = "tail_dead"` (`cancel` = no materializó nada); (3) el arnés **mide el
motivo** (la autoridad es la fila que devuelve el libro) y el artefacto lo publica; (4) guardarraíl
`declare_stall(...)` → `truncationReason = "stalled_book"` con `STALL_OPERABLE_DAYS = 20` días
**operables** sin orden ni fill y capital comprometido (o riesgo **ilegible**, que no se lee como
limpio) — **declaración**, no gate: la corrida nunca se corta por él.

**Cierre (2026-09-29, `v2.88.6-beta` / `AUTO-MATERIAL-19`).** Implementado en los cuatro ejes, con
**motor** (`auto_simulation_worker.py`, regla 2) **e instrumento** (`replay_oos.py` +
`v2_87_replay_oos_durable_cycle.py`) tocados, **bump `2.11.5-beta → 2.11.6-beta`, sin migración**.
Evidencia **medida** (ciclo durable, `1224/1224` ticks, `2021-12-07 → 2026-09-28`): libro **limpio**
(pico **0**, riesgo final **`0.0`**), `stall.declared = false`, **36** días operables sin actividad,
**752** fills / **210** órdenes / **62** ciclos en **4 temporadas** (`2022` 50 · `2023` 7 · `2024` 2 ·
`2025` 3), `R` total **−18.3660**, `meanR` **−0.2962**, signo positivo **37.10 %** (23/62); motivos de
retirada `fill 174` · `cancel 64` (de las cuales **36** `tail_dead`). **Artefacto byte-reproducible**
(SHA-256 `9AF077A0…F9928E4A`, idéntico en dos corridas) — frente al `v2.87`, que **no** lo era.
**Contraprueba A/B** (`--no-durable-cycle`): **118** fills, **13** ciclos (solo `2022`), **15** reservas
vivas, **`5999.9998`** de riesgo final y horizonte **`completed: false · stalled_book`** con
`lastActiveDay: 2022-05-06` (**266** días operables sin actividad); su SHA-256 **no** es
byte-reproducible porque **23** rutas de `finalBook` llevan `exit:<ULID>` (reloj de pared) de las 15
reservas que **sobreviven** — **declarado**, y sus cifras **sí** se reproducen. **Relectura de `v2.87`:**
el puntaje **no se mueve**; lo que cambia es la **contabilidad del libro**, que allí **sobre-liberaba**
(`byFill 237 / byCancel 1` frente a los **174 / 64** reales): la cifra antigua **no debe citarse**.
**Tests:** `test_replay_oos_durable_cycle.py` **29 → 45**, `test_auto_v2_durable_cycle.py` **22 → 26** y
**NUEVA** `test_v2_87_release_log.py` (**5**) ⇒ **+25 netos**. **Mutaciones:** `M257`–`M265` (matriz
`256` → **`265`**), **9/9 muerden**, matriz **COMPLETA `265/265`** con el árbol **intacto**.

**Límites declarados.** **NO** se toca `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/`A/B` ni ningún umbral, ni se
backdatea; el guardarraíl **NO** cierra la truncación, la **declara**; **NO** acredita `P3-2`/`P3-3`
(reloj **simulado**: el replay no sustituye la ventana PAPER real, y la muestra es multianual pero de
**un** instrumento con una cuenta/versión/watch y `pairActive=false`); **NO** cierra `OBS-15`
(techo de **1000 `APPLIED`**), `OBS-16` ni la deuda de datos; el replay sigue sin escribir en PostgreSQL
(cuarentena en memoria). La cita del CI es **POST-TAG** (patrón `OBS-3`/`OBS-4`): esperado job `python`
**`3103 passed, 37 skipped`** (con los **mismos `37` skips**), de la identidad **recogidos local − 37** que
cuadró con `v2.88.4` y `v2.88.5` (`3140 − 37`). **HUECO DE COBERTURA DE CI, medido y cerrado (declarado):**
la primera medida de la batería dio Δ **`+9`** contra `v2.88.5` cuando la fase añade **`+25`** funciones de
test; causa medida: `packages/py/application/tests/test_replay_oos_durable_cycle.py` (**45 tests
herméticos**, `0.33 s`, sin PG) **no estaba en la lista de NINGÚN workflow** desde su creación en `v2.88`
(`564240d2`), así que **los 16 tests que protegen la regla 2 por evidencia, la cola muerta y el guardarraíl
no habrían corrido en CI**. Se cablea en `release-tag-ci.yml` (`115 → 116` argumentos) y en `python-ci.yml`
con nota de procedencia (patrón «HUECO DECLARADO» de `v2.76`) y se **re-mide** (`+45` = tamaño exacto del
fichero). La causa estructural de esa deriva queda **abierta** como **`OBS-19`**.

**Evidencia:** [`obs-18-reconciliacion-por-reserva-v2.88.6-2026-09-29.md`](./obs-18-reconciliacion-por-reserva-v2.88.6-2026-09-29.md) ·
[`evidence/v2.88.6/README.md`](./evidence/v2.88.6/README.md) ·
[`evidence/v2.87/README.md`](./evidence/v2.87/README.md) (relectura del artefacto antiguo) ·
[`replay-oos-ciclo-durable-v2.87-2026-09-29.md`](./replay-oos-ciclo-durable-v2.87-2026-09-29.md) (padre).

---

## OBS-19 — Las listas de pytest offline de los workflows son MANUALES y han divergido: hay tests que ningún job por commit ejecuta (MEDIUM, proceso) — 🔴 ABIERTA (2026-09-29)

**Origen.** Medido al correr la **batería offline** del job `python` del tag para el sello `v2.88.6`
(`OBS-18`): el delta de tests **no cuadraba** con las funciones nuevas de la fase (**`+9`** medidos frente a
**`+25`** declarados).

**Observación (caso CERRADO en `v2.88.6`).** `packages/py/application/tests/test_replay_oos_durable_cycle.py`
(**45 tests herméticos**: memoria, sin PG ni red, **`0.33 s`**) **no estaba en la lista de NINGÚN workflow**.
Se creó en el sello `v2.88` (`564240d2`) y `git log -S` confirma que nunca se añadió: ese directorio se lista
**fichero a fichero** (los PG-gated obligan) y éste se quedó fuera. Consecuencia: **los 16 tests que protegen
la regla 2 por evidencia de la fila, la cola muerta y el guardarraíl no habrían corrido en el job del tag**
(ni los 29 del instrumento de `v2.87`). **Mitigación adoptada y medida en `v2.88.6`:** se cablea el fichero
en `release-tag-ci.yml` (`115 → 116` argumentos: es el job que juzga el tag) **y** en `python-ci.yml`, con la
nota de procedencia en ambos (patrón «HUECO DECLARADO» de `v2.76`); la re-medida da `3094 → 3139 passed`
(**`+45`** = tamaño exacto del fichero). El esperado del CI pasa de **`3058`** a **`3103 passed, 37 skipped`**.

**Observación (caso ABIERTO: deriva entre las DOS listas).** Comparadas las listas offline de
`python-ci.yml` (job `quality`, step `Pytest`) y `release-tag-ci.yml` (job `python`, step `Pytest offline`),
**no son la misma lista**:

- **`12` ficheros / `98` tests** están SOLO en la del tag ⇒ el job `quality` de cada commit (`main`) **no**
  los ejecuta: `test_auto_sim_active_strategy_seam.py`, `test_auto_simulation_worker.py`,
  `test_auto_v2_golden_day_evidence.py`, `test_auto_v2_lifecycle_clock_thesis.py`,
  `test_active_strategy_signal_evaluator.py`, `test_orchestrator_lab_runner.py`,
  `test_orchestrator_universe.py`, `test_sim_strategy_attribution.py`,
  `test_strategy_executable_definition.py`, `test_strategy_observed_metrics.py`,
  `test_strategy_observed_metrics_provider.py`, `test_strategy_vigilance_observed.py`.
- **`3` ficheros / `56` tests** están SOLO en la de `quality` ⇒ el job `python` del tag **no** los ejecuta:
  `test_rules_engine_series_wiring.py`, `test_discovery_grammar.py`, `test_paper_forward_phase.py`.

**Radio.** Medio: en un push de tag corren **los dos** workflows (el del tag y el `quality` de `main`), así
que la **unión** cubre ambas listas y el rojo aparece igualmente antes de publicar; lo que se pierde es la
**cobertura por commit** en cada lado (una regresión de esos `98` tests no la ve `main` hasta el tag, y una
de los `56` no la ve el job del tag).

**Mejora posible, NO implementada.** Una **fuente única** (un fichero de rutas que ambos workflows lean, o
un script que genere el bloque) más un **gate de paridad** que falle si las dos listas difieren o si algún
`test_*.py` de un directorio cubierto no está ni incluido ni excluido **por nombre con motivo**. Los
`--ignore` ya existentes son el precedente del «excluido con motivo».

**Criterio de cierre.** Que las dos listas sean idénticas (o que la diferencia esté declarada por escrito en
el propio workflow) y que un gate lo verifique.

**Evidencia:** [`obs-18-reconciliacion-por-reserva-v2.88.6-2026-09-29.md`](./obs-18-reconciliacion-por-reserva-v2.88.6-2026-09-29.md) ·
[`evidence/v2.88.6/README.md`](./evidence/v2.88.6/README.md).

---

## OBS-20 — La retirada declaraba `cancel` («nunca materializó») sobre reservas que SÍ materializaron: la evidencia del motivo no viajaba entera (MEDIUM, alcance motor) — 🟢 CERRADA en `v2.88.7` (2026-09-29)

**Origen.** El **rojo `lifecycle-pg`** del tag `v2.88.6-beta`: `Release tag CI` run **`36603391512`** (ref
`v2.88.6-beta`, `032ae7cc`) → **`FAILURE`**, con `test_crash_recovery_day_process_pg.py` afirmando que la
muerte debe ocurrir **con la cola de reserva viva** (`reservas vivas: []`). La aserción sellada era la
**antigua**; el motor de `OBS-18` —**sellado en el mismo commit**— **retira** la cola muerta al cerrar el
turno (`tail_dead`, `remaining_qty = 0`). El **re-anclaje** ya estaba en el árbol de trabajo y **se sella**
en `v2.88.7`. **El tag `v2.88.6-beta` NO se borra: queda como rojo citado** (su job `python` **sí** fue verde
y cuadró con lo declarado: **`3103 passed, 37 skipped`**).

**El hueco (medido, no narrado).** `OBS-18` decide por la evidencia **de la fila** (`released_qty`), pero esa
evidencia la escribe el **camino caliente de la sesión que LIQUIDA** el fill, y **solo** sobre las reservas
que esa sesión tiene **en su libro**. Cuando no la tiene (libro de **otra** sesión, o **barrido de arranque**
de un proceso sin memoria), el ledger dice **`APPLIED`** y la fila dice **`released_qty = 0`**:

| Instante | Ledger (`execution_events`) | Fila (`portfolio_reservations`) |
| --- | --- | --- |
| fill liquidado | **`APPLIED`** | `released_qty = 0` (la liberación **no ocurrió**) |
| cierre de turno de **otra** sesión | `APPLIED` (contradice) | `released_qty = 0` ⇒ **`cancel`** |

Firma medida en `test_concurrent_auto_pg.py[5]`: **~1 de cada 9** corridas, `assert 'cancel' == 'tail_dead'`.

**El mecanismo (identidad EXACTA, sin heurísticas).** `cycle_id` (V2.47) **ya** viajaba en las dos partes
—el `AppliedFillFact` desde el contexto financiero del fill y la reserva desde su fila— y **ya** estaba
persistido (migración `042`/`047`); lo que faltaba era **leerlo**. El motor agrupa los hechos aplicados por
**`(ciclo, lado)`** y completa `materialized = max(materialized, min(linked, committed))`:

- Acotado por **LADO** (un ciclo tiene las dos patas: entrada `BUY` y salida `SELL`) y **NUNCA** por
  `instrumento+lado`: dos órdenes del mismo instrumento y lado son **ciclos distintos** — es el defecto que
  `OBS-18` corrigió y no debe reintroducirse por la puerta de atrás.
- El **`max`** garantiza que lo registrado en la fila **nunca** se rebaja (la evidencia del ciclo
  **completa**, no sustituye) y la **cota por lo COMPROMETIDO** evita inflar la evidencia.
- `cycle_id = None` ⇒ comportamiento de `OBS-18` (decide la fila).
- **Fail-closed intacto:** `in_flight` **manda**, `measurable` **manda** y nunca se libera más que la
  cantidad viva. `AppliedFillFact.cycle_id` **no** se publica en `to_dict()`: el contrato serializado **no
  cambia**.

**La medida que lo separa de «un fallo de test».** Ciclo durable, **`1225/1225`** ticks
(`2021-12-07 → 2026-09-29`): `tail_dead` **36 → 40** y `cancel` **28 → 24**. El cambio está **localizado**
en **`4` días con UNA retirada cada uno** (`2022-03-14`, `2022-03-16`, `2022-06-09`, `2022-06-13`; medido
campo a campo sobre `book.perDay`) y **ningún otro día cambia**: **`4` de las `64`** cancelaciones eran
**proveniencia falsa**. El **puntaje NO se mueve** (mismos **`62`** ciclos, mismo `R` total **`−18.3660`**):
la corrección **no** es una palanca de resultados. **Comparabilidad declarada:** el censo de `v2.88.6`
terminaba en `2026-09-28` (`1224` ticks) y el de `v2.88.7` en `2026-09-29` (`1225`); el día nuevo **no** añade
fills ni retiradas (mismos `752` fills / `210` órdenes / `238` propuestas), así que las cuatro
reatribuciones son del **motor**, no del calendario.

**Verificación.** Test hermético nuevo (+1 neto): `test_auto_v2_durable_cycle.py` **26 → 27** con
`test_a_cancel_is_never_declared_while_an_applied_fill_waits_in_the_ledger`. Mutaciones **`M266`** (worker:
atribución por ciclo **silenciada**) y **`M267`** (el lector de fills aplicados **no propaga `cycle_id`**):
**`2/2` muerden** exactamente el test nuevo; matriz **COMPLETA `267/267`** en una sola pasada limpia con el
árbol **intacto** (`exit 0`). Suites PG re-ancladas a la semántica de `OBS-18` (`released == requested`,
`remaining == 0`, `release_reason == "tail_dead"`, `retained == 0.0`, `reserved_risk > 0` retenido para el
denominador `R`), con `test_concurrent_auto_pg.py` **`3 passed` × 12 corridas consecutivas (12/12)** y el
crash/recovery verificando además la **idempotencia del reinicio** (no re-libera ni cambia el motivo).
Corrida conjunta de las cinco suites del motor e instrumento **`98 passed`** (era `97`).

**Artefacto.** `replay-oos-durable-obs20-fix-20260929.json` — **`3 393 187`** B, SHA-256
**`7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461`**, **byte-idéntico** en una segunda
corrida independiente. §5 de [`evidence/v2.88.7/README.md`](./evidence/v2.88.7/README.md) publica el libro y
la puntuación completos.

**Límites declarados.** **NO** se toca `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/`A/B` ni ningún umbral, ni se
backdatea; **NO** acredita `P3-2`/`P3-3` (reloj **simulado**: el replay **no** sustituye la ventana PAPER
real —una cuenta/versión/watch, `pairActive=false`—); **NO** cierra `OBS-15` (techo de **1000 `APPLIED`**),
`OBS-16` ni la deuda de datos; **NO** cierra **`OBS-19`** (la deriva entre las **dos listas offline** de
pytest sigue **ABIERTA**); el replay sigue **sin** escribir en PostgreSQL (cuarentena en memoria, por
construcción). La cita del CI es **POST-TAG**: esperado job `python` **`3104 passed, 37 skipped`**
(identidad **recogidos local − 37**: `3141 − 37`; los `3103` de `v2.88.6` + **`1`** del test hermético nuevo),
con los **mismos `37` skips`**.

**CITA REAL (POST-TAG, 2026-09-29).** `Release tag CI` run **`36614230366`** (HEAD `5cbe84b0`,
`ref=v2.88.7-beta`) → **`SUCCESS` en la PRIMERA pasada** (`attempt 1`; `18:44:34Z → 18:53:13Z`,
**~8m39s**), **10 jobs reales verdes + `certify` verde** y `playwright (integrated E2E, opt-in)`
`skipped` por diseño. Job `python` **verbatim**: `ruff All checks passed!` · `Contracts: 4 kept, 0
broken` · `mypy no issues found in 508 source files` · **`3104 passed, 37 skipped, 6 warnings in
55.36s`** ⇒ **ESPERADO `3104/37` = OBSERVADO `3104/37` → COINCIDE**. `lifecycle-pg` **GREEN con `220
passed`** en sus **8** invocaciones (**0 failed / 0 skipped**), incluido **`Pytest Crash/Recovery Day`
`1 passed in 9.34s`** — **el paso que salió ROJO en el tag de `v2.88.6`**, que es el rojo que esta
deuda cierra — y **`Pytest Concurrent AUTO` `3 passed in 2.30s`** (la otra suite re-anclada). En `main`
(push `5cbe84b0`) `quality` **`3093 passed, 40 skipped`** con los **4** jobs PG per-commit verdes.

**Evidencia:** [`obs-20-atribucion-por-ciclo-v2.88.7-2026-09-29.md`](./obs-20-atribucion-por-ciclo-v2.88.7-2026-09-29.md) ·
[`evidencia-ci-tag-v2.88.7-2026-09-29.txt`](./evidencia-ci-tag-v2.88.7-2026-09-29.txt) (cita cruda del CI del tag) ·
[`evidence/v2.88.7/README.md`](./evidence/v2.88.7/README.md) ·
[`evidence/v2.88.7/mutation-matrix-267.log`](./evidence/v2.88.7/mutation-matrix-267.log) ·
[`evidencia-ci-tag-v2.88.6-2026-09-29.txt`](./evidencia-ci-tag-v2.88.6-2026-09-29.txt) (rojo citado) ·
[`evidence/v2.88.6/README.md`](./evidence/v2.88.6/README.md) (relevo anterior).

---

## Prioridad declarada por la auditoría externa de `v2.88.3` (2026-09-29) — 🎯 2 de 3 EJECUTADAS (paso 3 pendiente)

La auditoría externa (`APROBADO`, 0 bloqueantes) **NO** pide otra cadena de endurecimiento indiscriminado.
Pide **exactamente tres** acciones, en este orden:

1. ✅ **Cerrar la simetría de ownership** → **`OBS-17`** — **HECHO en `v2.88.4`**: test de simetría +
   mutación **`M253`** sobre `_v2_reserve_exit` (matriz `252 → 253`).
2. ✅ **Atacar `OBS-14.b`** (`restart → startup sweep → reservas → ownership → grace/no grace`) —
   **HECHO en `v2.88.5` / `AUTO-MATERIAL-18`**: ventana de gracia por **EDAD** (propiedad **o** edad) en la
   reconciliación, 8 tests nuevos y **4 mutaciones** (`M250` re-anclada + `M254`/`M255`/`M256`; matriz
   `253 → 256`). Ver el bloque de cierre de `OBS-14.b` arriba.
3. **Volver a PAPER real** — pasar de *«¿puede AUTO sobrevivir correctamente?»* a
   *«¿qué hace AUTO durante varios días de operación real?»*; comprobar antes el riesgo de **`OBS-15`**
   (1000 `APPLIED`). **← SIGUIENTE.**

**Explícitamente NO tocar:** `TOP_N` / `REGIME` / `RISK` / `SIGNALS` / `A/B` / `thresholds` por motivos de
comportamiento de mercado. La acción **1** se cerró en `v2.88.4` y la **2** en `v2.88.5`; la **3** **no**
está ejecutada, y tampoco `OBS-15` / `P3-2` / `P3-3`: **ninguna** de esas deudas se cierra por estos
informes.

---

## FLAKE-1 — `lifecycle-pg`: `test_finance_auto_day_materializes_executetrade_exactly_once` rojo **intermitente** (`AssertionError: RETRY`) — 🟡 ABIERTA (2026-09-29)

**Qué se midió.** Tres corridas de `release-tag-ci`: **dos rojos** (`36627838819`, `36636706369`) y
**un verde** (`36638231729`, `165 passed in 82,89 s`; en los rojos, `1 failed, 164 passed in 100,07 s`).
Por tanto **NO** es determinista: la afirmación previa de «reproducible» era **incorrecta** y se corrigió
en `PROJECT_STATE.md`, en el índice (`192`) y en el informe de reproducibilidad (§6.2).

**Firma exacta.** `AssertionError: RETRY` en el assert de `test_simulated_finance_pg.py:327`
(`row.status == "APPLIED"`, cuyo mensaje de fallo es el estado real): un `execution_id` que el venue
reportó **lleno** seguía en **`RETRY`** (dinero NO movido) al leerlo. El resto del rojo de `lifecycle-pg`
es **cascada** (el step aborta y las baterías siguientes se quedan sin log ⇒ «no dejó log de la corrida»).

**Mecanismo (por lectura del código, sin necesidad de repro).** Ese `RETRY` solo puede venir de
`apply_execution_financial_once(retryable_on_ineffective=True)` → `mark_retry(error="apply_ineffective")`
cuando el applier devuelve `False`; y `build_simulated_execute_trade_applier._apply` devuelve `False` en
**dos** casos: (a) el resolver da `None` —**descartado aquí**: el schedule se recomputa determinista con
el MISMO `venue_order_id`, así que el match por `execution_id` no puede fallar— o (b)
`ExecuteTrade.execute` **lanzó** y la excepción se **tragaba** (`except Exception: return False`). Es
decir: el `RETRY` es un fallo de `ExecuteTrade` **sin causa visible** (el único rastro era
`error="apply_ineffective"`).

**Hipótesis previa REFUTADA (medida).** La sospecha era el camino de **llenado parcial** (el repo lo
documenta como «un chunk en `RETRY`»): cierto que el selector del test (`_seed_with_fills`, que solo exige
`fills` no vacío) **acepta** esquemas parciales —medido offline: **9 de 80** órdenes ≈ **11 %** salen
`partial`—, pero **no** es la causa: en el bucle directo **4 de 25** corridas tuvieron un lado `partial` y
**pasaron**, y forzar el selector a exigir esquema **completo** no cambia nada (`25/25` ok).

**No reproducible en local (medido).** `50` corridas directas del test objetivo (dos políticas de
selector) + **9** corridas del **comando exacto del CI** (`lifecycle-pg`, con BD scratch **fresca**
drop+create+migrate por iteración; 8 con `161 passed, 4 skipped` y la última con `165 passed, 0 skipped`)
⇒ **0 rojos**. La variable es del **entorno** (runner 2 vCPU vs local), no del motor.

**Arreglo aplicado (lo único accionable sin repro): hacer visible lo que se tragaba.**
`simulated_finance._apply` registra ahora `logger.exception(...)` con el `execution_id` y el
`instrument_id` antes de devolver `False` —el contrato **no** cambia (sigue fail-closed; **jamás** APPLIED
por excepción)— y se añade el gate `test_applier_keeps_fail_closed_and_LOGS_the_swallowed_cause` (la traza
queda en el log, y pytest la muestra en «Captured log call» cuando el test falla).

**Hallazgo de higiene en la misma pasada (`OBS-19`).** Ese gate **no habría corrido**:
`packages/py/application/tests/test_simulated_finance.py` **no estaba en la lista de ningún workflow**
(existe desde `v2.22/A9`), así que se añade a los **dos** jobs offline —`python-ci.yml` y el job `python`
de `release-tag-ci.yml`— con su comentario de procedencia, igual que se hizo con
`test_replay_oos_durable_cycle.py` en `v2.88.6`.

**Deuda que queda.** La **causa raíz** (qué excepción lanza `ExecuteTrade` en el runner) solo se sabrá en
el **próximo** rojo del CI, ya con traza. **No** se toca ni el motor ni el test del día AUTO.

**Alcance.** Proceso/tests (rojo **espurio** en la certificación). Si el tag se cortase en una corrida
donde dispara, `certify` **no-GREENearía** el tag por una causa **ajena** al artefacto. **No** afecta al
sello del replay OOS de `v2.88.7` (otra cadena) ni a su remedición de integridad.

