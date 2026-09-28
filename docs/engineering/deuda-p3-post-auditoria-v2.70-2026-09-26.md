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
