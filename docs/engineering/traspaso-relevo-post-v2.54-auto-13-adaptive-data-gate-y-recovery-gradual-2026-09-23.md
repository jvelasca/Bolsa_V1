# Traspaso de relevo — `AUTO-13` **CERRADA** (`V2.54` / `1.79.0-beta`)

**Fase:** `AUTO-13` (Adaptive Data Gate + recovery gradual) · **Fecha:** 2026-09-23 · **Fase
anterior:** `V2.53` / `AUTO-12` (sellada: tag `v2.53-beta` → `a6655e6e`, `Release tag CI`
`35836248169` **GREEN**, `1.78.0-beta`).
**Documentos de la fase:**
[plan](./plan-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md) (ratificado) ·
[audit-pack](./audit-pack-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md) · este
relevo.
**Estado:** **fase CERRADA** — Pasos 1–6 hechos y verificados, tag **`v2.54-beta`** con su CI (cifras
medidas en §7). **El runtime sigue siendo el de `v2.53-beta`** con el flag Adaptive **OFF**: el Data
Gate y la rampa **no se ejecutan** en producción hasta un flag explícito. La rama de auditoría externa
`auto-13-adaptive-data-gate` viaja entera en el **PR draft #63** contra `main`, y `main` recibe la fase
**al sellar** (fast-forward lineal, como en `v2.50`–`v2.53`).

> **Este documento es la fuente de verdad de la fase CERRADA.** Se lee **antes** que
> [`PROJECT_STATE.md`](./PROJECT_STATE.md), que ya publica esta fase como la última cerrada y apunta
> aquí como relevo vivo.

---

## 0. Qué está ratificado y qué se ejecutó

**Rótulo ratificado por el propietario:** `AUTO-13` sobre **`V2.54` / `1.79.0-beta`**, con alcance
**core backend** (§22 + §24 del audit **y** el fallback del §20), **sin UI**, **sin migración**
(Alembic head sigue en `044_auto_cycle_trace`), **sin tocar el gobernador** y **sin estado propio
persistido** (la memoria de la rampa se **deriva**).

**Las cuatro decisiones, ratificadas (2026-09-23) y ejecutadas tal cual:**

1. **De dónde sale el estado del gate** → **combinar** salud **durable** derivada del journal
   (antigüedad de la evidencia: sobrevive a reinicios) + un contador de fallos consecutivos **en
   memoria** (detecta el fallo al instante). El límite se **declara**: el contador se pierde al
   reiniciar, el ancla durable no. Descartado: solo memoria (un reinicio volvería a `OK` con el
   journal caído).
2. **Qué significa `BLOCKED`** → **no adaptar** ese tick: el plan Adaptive se declara **ausente**
   (`adaptive = None`, el mismo camino que el flag OFF) con su motivo. Motor determinista intacto.
   Descartado: un plan "neutral" fabricado, que afirmaría una evaluación que no se pudo hacer.
3. **Dónde vive la memoria de la rampa** → **derivarla** de (a) la racha durable de `AUTO-11`
   ampliando el lector para **declarar `reactivated_at`** y (b) los fills posteriores con su
   `closedAt` de `AUTO-12`. **Sin migración y sin clave nueva** en el journal. Descartado:
   persistir el escalón (toca el contrato de `AUTO-11` y añade estado reconstruible).
4. **Alcance del §20** → **entra** el fallback declarado del hueco de régimen; la **matriz de
   régimen avanzada** (reparto *por celda*) queda **fuera** y se declara para `AUTO-14`.

Dos consecuencias que la ejecución confirmó y conviene no perder: el `STALE` se implementó **solo en
el worker** (el contador que entra a `recommend_rotation` se recorta, el real sigue creciendo, y los
umbrales de rotación no se tocan), y la decisión 3 se resolvió **en contra** de tocar
`auto_adaptive_journal.py`: el contrato durable de `AUTO-11` queda byte a byte igual.

---

## 1. Estado medido del repo (2026-09-23)

- **Rama de la fase:** `auto-13-adaptive-data-gate` (empujada; los commits anteriores —plan,
  ratificación, Paso 1 y primer relevo— viajaron con ella, así que el PR muestra el delta completo
  sobre `v2.53`). **`main` recibe la fase al sellar** en fast-forward lineal: `origin/main` estaba en
  `d08e66e5` (sello de `v2.53`) y pasa al **commit del paquete de docs + bump** (el que lleva el tag).
  Árbol limpio **salvo `governor.json`** (sin trackear, como estaba).
- **Commits de la fase:** `009e8965` (plan) · `d9242970` (ratificación) · `f45ac604` (**Paso 1**) ·
  `28b5ac5f` (**Paso 2**) · `30b2e5b3` (**Paso 3**) · `435530eb` (**Paso 4**) · `dcc0d64b` (**Paso 5**) ·
  `c6aec527` (relevo con el Paso 5) · y el **paquete de cierre** (audit-pack nuevo, este relevo,
  `CHANGELOG`, `PROJECT_STATE`, `engineering-index` y bump a `1.79.0-beta`), que es el commit sellado.
- **Tag anterior `v2.53-beta` → `a6655e6e`**: **no se reabre**. Sus cifras de CI (`10 success` +
  `1 skipped`, `check-runs` `27 success` + `1 skipped`, job `python` `2459 passed / 35 skipped`)
  son el **delta de referencia** de esta fase.
- **Sin migración**: head `044_auto_cycle_trace`.

## 2. Lo ya HECHO y verificado (Paso 1)

**Fichero nuevo:** [`packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py`](packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py)
· **tests:** [`packages/py/analytics/tests/test_auto_adaptive_data_gate.py`](packages/py/analytics/tests/test_auto_adaptive_data_gate.py).
**Verificación del paso:** `ruff check` → `All checks passed!` · `pytest` → **`22 passed`**.

Contrato ya implementado (lo que el cableado puede dar por hecho):

- `DataGateStatus = OK | DEGRADED | STALE | BLOCKED` y
  `DataGateEffect = ADAPTS | LIMITS | FREEZES | NO_ADAPT`.
- **El efecto se DERIVA del estado** con una tabla (`_EFFECT_BY_STATUS`); no es un campo que pueda
  divergir. `reading.effect`, `reading.adapts`, `reading.limits_adaptation`,
  `reading.blocks_adaptation` son las lecturas que usará el worker.
- **Precedencia `BLOCKED > STALE > DEGRADED > OK`** con el estado grave **absorbiendo** los motivos
  menores: una lectura nunca se publica con las notas de otro estado.
- `notes` con vocabulario propio: `journal_gap`, `sink_failures`, `durable_state_unread`,
  `unreadable_rows`, `policy_version_mismatch`, `insufficient_history`, `measurement_incomplete`,
  `recent_unavailable`, `regime_absent`, `journal_age_unknown`, `evidence_not_provided`.
- `DataGatePolicy` con **versión propia `auto13-v1`** y umbrales: `sink_failures_stale = 3`,
  `journal_gap_blocked = 10` (ambos `>= 1`, validados en `__post_init__`).
- Entrada: `assess_data_gate(...)` (pura, orden-invariante, sin I/O).

**Tres decisiones tomadas dentro del Paso 1** (medidas por test, y que el cableado debe respetar):

1. **`read_ok = False` ⇒ `STALE`, no `BLOCKED`.** No poder leer y no haber nada son hechos
   distintos; solo el journal muerto (`journal_gap`) borra la adaptación entera.
2. **Sin evidencia aportada (`None`) no se degrada**: se declara `evidence_not_provided`. Es lo que
   mantiene **byte-idéntico** el comportamiento cuando el gate no se pasa (la misma disciplina que
   `AUTO-12` dejó con `confidence=None`).
3. **`journal_age_cycles = None` no bloquea** (no se puede juzgar la antigüedad); si además se
   congela por otro motivo, se declara `journal_age_unknown` en vez de suponer juventud.

## 2b. Lo ya HECHO y verificado (Pasos 2 a 5)

> **Nota de lectura.** Las anclas de línea de §3 y las descripciones de §4 son las del **plan
> original**: se conservan como histórico. Lo que sigue es lo **ejecutado**, con la decisión fina
> que se tomó en cada punto cuando el plan dejaba margen.

### Paso 2 — Contador de fallos del sink + ancla durable (commit `28b5ac5f`)

- **Cadencia declarada:** `DATA_GATE_EVALUATION_CYCLE_SECONDS_DEFAULT = 60.0` y
  `DataGatePolicy.evaluation_cycle_seconds` (validado `> 0`) + helper puro `journal_age_cycles(...)`
  en `auto_adaptive_data_gate.py`. La conversión segundos→ciclos se **declara**, no se deja implícita.
- **`last_published_at`** en `AdaptiveStateReading`/`read_adaptive_state`: el `asOf` de la evidencia
  MÁS NUEVA (la primera de la historia ordenada); un instante ilegible da `None` (no se supone
  juventud). Es el ancla que **sobrevive a un reinicio**.
- **Contador de fallos consecutivos** de `_v2_journal_adaptive_recommendation` en el worker: se
  incrementa en el `except` y un **éxito RESETEA** la racha y pone el ancla a `0`.
- **Regla de corroboración (decisión fina, ratificada):** el ancla durable **solo** bloquea si hay
  un fallo de escritura **propio** (`_v2_adaptive_gate_journal_age` devuelve `None` sin fallos). Sin
  ella, un journal sano pero antiguo (Adaptive OFF o pausa larga) quedaría `BLOCKED` para siempre:
  `BLOCKED` ⇒ `adaptive = None` ⇒ no escribe ⇒ **deadlock**.
- **Verificación:** `test_auto_v54_auto13_data_gate_seam.py` (nueva) + ampliación de
  `test_auto_adaptive_data_gate.py` y `test_auto_adaptive_recovery.py`; **M72–M77** (6 mutaciones).

### Paso 3 — Cableado del gate en `_v2_build_adaptive_plan` (commit `30b2e5b3`)

- `gate: DataGateReading | None = None` (opcional: `None` ⇒ comportamiento histórico). El gate se
  **compone** de hechos que el tick ya midió (`_v2_adaptive_data_gate`): cero I/O nuevo.
- **`OK`** ⇒ plan byte-idéntico; **`DEGRADED`** ⇒ `confidence=None` al plan (deja de estrechar por
  evidencia fina) **conservando la protección**; **`STALE`** ⇒ además no admite reactivaciones
  nuevas, vía `_v2_adaptive_decision_cycles` (recorta el contador por debajo de `min_pause_cycles`;
  el contador **real** sigue creciendo); **`BLOCKED`** ⇒ `adaptive = None` declarado, sin fila de
  journal.
- **Dos decisiones finas, ratificadas:**
  1. **Completitud del gate = ejes que Adaptive EXIGE** (resultados + riesgo), **no** el net-R
     **opcional** (cuyo hueco cae por diseño al eje moneda). Usar el de la confianza degradaría el
     gate en cualquier despliegue sin coste medido y apagaría `AUTO-12` casi siempre (**M82**).
  2. **`regime_available` acepta los dos ejes** (canónico `TREND_UP` y operativo `BULL_TREND`) y solo
     declara ausencia con `None`, cadena vacía, `UNKNOWN` y `RISK_OFF` (`_v2_regime_available`).
     Traducir por una sola vía degradaba el gate en el caso normal (**M81**).
- **Verificación:** `test_auto_v54_auto13_data_gate_wiring_seam.py` (nueva) + **M78–M82**.

### Paso 4 — `RECOVERING` y la rampa por evidencia (§24)

- **Estado operativo derivado** (`ADAPTIVE_STATE_ACTIVE` / `PAUSED` / `RECOVERING`): vive en
  `AdaptivePlan.operational_states`, con `state_for(...)`. No es un modo de la rotación: quien pausa
  y reactiva sigue siendo `recommend_rotation`.
- **Rampa declarada:** `ADAPTIVE_RECOVERY_STEPS_DEFAULT = (0.25, 0.50, 0.75, 1.00)` y
  `ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT = 3`, ambos **campos de política** validados en
  `AdaptivePolicy.__post_init__` (escalones en `(0, 1]`, estrictamente crecientes, paso `>= 1`).
- **`RecoveryEvidence` / `RecoveryReading` / `recovery_reading(...)`** (puros): el escalón es
  `escalones[min(último, ciclos_positivos // paso)]` y **avanza solo con evidencia medida positiva**;
  el deterioro (`decay == SEVERE` o expectancy reciente `<= 0`) o un hueco de fechas lo **reinician al
  suelo** y lo **declaran** (`recovery_severe_decay` / `recovery_not_positive` / `recovery_unmeasured`).
- **Aplicación: `m_final = min(m_reparto, escalón)`** dentro de `recommend_allocation(..., recovery=)`
  — después del reparto y antes de publicar. **Solo estrecha**, nunca ensancha, y nunca deja a nadie
  en `0` (suelo `> 0`). Un escalón `1.00` es recuperación **cumplida**: la versión vuelve a `ACTIVE`
  a peso pleno.
- **Memoria derivada:** `reactivated_at` **declarado** por el lector durable (`_reactivations`):
  con las filas de nueva a vieja, el corte es la fila más vieja de la racha **activa** actual, y solo
  se publica si la fila anterior la tiene **pausada** (corte PROBADO). Un turno ilegible o sin fecha
  corta la búsqueda: no se inventa una reincorporación (**M88**).
- **Evidencia medida:** `recovery_evidence_from_fills(...)` en el feed reusa los MISMOS fills del
  tick (`cycles_from_fills` + `apply_cycle_risk`) y calcula el R con **`cycle_r`** (la regla del
  informe, sin un segundo cociente paralelo): cuenta los ciclos **posteriores** al corte con R medido
  positivo. Una pausa viva **descarta** su escalón (la rotación manda).
- **Sello:** `ADAPTIVE_POLICY_VERSION` → **`auto13-v1`**, con el test del sello actualizado **con
  nombre** (en `test_auto_adaptive.py` y en la costura de `AUTO-12`).
- **Verificación:** `test_auto_v54_auto13_recovery_seam.py` (nueva) + ampliación de
  `test_auto_adaptive.py` (rampa y `min`), `test_auto_adaptive_recovery.py` (`reactivated_at`) y
  `test_auto_self_evaluation_feed.py` (evidencia medida); **M83–M93** (11 mutaciones).

### Paso 5 — Fallback declarado del §20 y los tres ejes separados (commit `dcc0d64b`)

**Mitad de la rotación (§20).** Un régimen que **no se pudo leer** no puede decidir nada:

- `StrategyHealth.regime_undetermined` (**auto_adaptive.py:323**) conserva el **motivo** con el que
  `declared_regime` declara el cruce no determinado: el par `(régimen, motivo)` viaja con la fila
  (**334** `from_evaluation`), así que un `UNKNOWN` legítimo (sin celda decisiva) deja de ser
  indistinguible de un régimen mal medido. La rotación decide con la evidencia **global** de la
  estrategia —la propia fila—, que es el fallback declarado.
- `AdaptivePlan.regime_undetermined` (**582**) publica el hueco en **campo propio**, ordenado por
  versión y **derivado** de la salud (**1002-1004**), no recalculado: un segundo cálculo del cruce
  podría divergir del que usó la rotación. Se publica en `as_dict()` (**657**).
- El tick lo **declara** (`regimeUndetermined` + `fallback: strategy_evidence`, worker **3155-3165**):
  sin él, "no había régimen" y "se decidió con la evidencia global" eran indistinguibles en la traza.

**Mitad del gate (§20).** La degradación por régimen ausente ya la daba el Paso 3 (`assess_data_gate`
con `regime_available=False` ⇒ `DEGRADED`, `regime_absent`); este paso la **verifica de punta a punta**
y añade el **control** que faltaba: el régimen adverso **real** del tick. El tick sirve el régimen en
el eje **operativo** (`market_regime_gate`: `BEAR_TREND`) y el plan lo traduce al de mercado
(`TREND_DOWN`); probar la rama adversa con un canónico crudo (`TREND_DOWN` en la entrada) medía un
`UNKNOWN` y el control habría sido **mudo** —de ahí que el test use la entrada real.

**Los tres ejes (§29): medir la confianza no es usarla para repartir.**

- `build_adaptive_plan(..., shrink=)` (**916/925**): con `shrink=False` (efecto `LIMITS`/`FREEZES`)
  el reparto cae a su eje histórico (**985**, `confidence=confidence if shrink else None`) pero la
  banda **MEDIDA** sigue publicándose en `health.confidence`/`evidence_for`. Ocultarla habría sido
  mezclar los ejes: `ACTIVE` + datos `DEGRADED` + calidad `LOW` es un estado **legal** y readable.
- `AdaptivePlan.shrinkage` (**588**) declara si el reparto pudo usar la confianza. El worker pasa
  `shrink=not reading.limits_adaptation` (**3130**).
- **Lo que NO cambia:** la protección (pausas, cooldowns, pausas de salud) sigue recibiendo el mismo
  material, y el **journal durable sigue intacto**: `build_adaptive_recommendation_entry` proyecta
  claves explícitas, así que el contrato de `AUTO-11` no gana ninguna clave. `plan.as_dict()` solo
  alimenta la traza del tick (`auto_v2_entry.py:1134`).
- **Verificación:** costura nueva `test_auto_v54_auto13_regime_fallback_seam.py` (**7 tests**) + unit
  (`test_auto_adaptive.py`: health/cruce/rotación/plan/encogimiento) + `..._data_gate_wiring_seam.py`
  (el `shrink` del cableado y el reparto histórico); **M94–M98**. Delta simétrico: la versión de
  `HEAD` de los tests tocados cae **solo** en
  `test_degraded_stops_using_the_confidence_but_keeps_the_protection`, que afirmaba el contrato viejo
  (`confidence=None` en `DEGRADED`): es exactamente el cambio declarado de §29.

## 3. Anclas de código

> **Nota:** las anclas de los Pasos 2–6 se midieron sobre el plan y se conservan como histórico; las
> de esta lista están re-medidas sobre el **árbol final** sellado.

**Adaptive (analytics):** [`auto_adaptive.py`](packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py)
`ADAPTIVE_POLICY_VERSION = "auto13-v1"` (**143**, sellado) · `AdaptivePolicy` (**201**) ·
`ADAPTIVE_STATE_ACTIVE`/`PAUSED`/`RECOVERING` (**208-211**) ·
`ADAPTIVE_RECOVERY_STEPS_DEFAULT`/`_STEP_CYCLES_DEFAULT` (**216/219**), notas de la rampa
(**222-224**) · `StrategyHealth` (**227**, con `regime_undetermined` en **323**) · `recovery_reading`
(**527**) · `recommend_rotation` (**510**) · `_allocation_weights` (**568**) ·
`_confidence_factor` (**606**) · `recommend_allocation` (**628**) · `AdaptivePlan` (**560**;
`operational_states` **573**, `recovery` **577**, `regime_undetermined` **582**, `shrinkage` **588**,
`state_for` **593**) · `build_adaptive_plan` (**916**, `shrink` **925**, el `if shrink else None` del
reparto **985**, la derivación del hueco **1002-1004**).

**Confianza (insumos del gate):** [`auto_adaptive_confidence.py`](packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_confidence.py)
`StrategyConfidence.effective_n`/`measurement_completeness`/`regime_coverage` (**313-342**) ·
`AdaptiveConfidence.recent_available` y `confidence_for()` (**353-373**) · `build_adaptive_confidence` (**571**).

**Feed (costura):** [`auto_self_evaluation_feed.py`](packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py)
`_closed_at` (**85**) · `cycles_from_fills` (**155**) · `build_auto_self_evaluation` (**202**) ·
`build_adaptive_confidence_from_fills` (**229**).

**Recuperación durable (donde vive `reactivated_at`):** [`auto_adaptive_recovery.py`](packages/py/application/src/bolsa_application/auto_adaptive_recovery.py)
`AdaptiveStateReading` (**258**) · `read_adaptive_state` (**305**) · `_streaks` (**216**).

**Contrato del journal (por defecto NO se toca):** [`auto_adaptive_journal.py`](packages/py/application/src/bolsa_application/auto_adaptive_journal.py)
`_ROTATION_KEYS`/`_ALLOCATION_KEYS` (**57-59**) · `build_adaptive_recommendation_entry` (**147-181**).

**Worker:** [`auto_simulation_worker.py`](apps/api-python/src/bolsa_api/background/auto_simulation_worker.py)
`_v2_adaptive_paused_cycles` (**727**) · `_adaptive_sink`/`_adaptive_reader` (**781/784**) ·
`_v2_regime` (**1358**, devuelve `None` solo sin fuente o con excepción) · `_v2_cycle_risk` (**2926**) ·
`_v2_build_adaptive_plan` (**3008**; `paused_cycles` entran en **3052**, se leen en **3058**, se
avanzan en **3062**) · `_v2_adaptive_policy` (**3065**) · `_v2_next_paused_cycles` (**3074**) ·
`_v2_journal_adaptive_recommendation` (**3085**, el **punto del contador de fallos**; hoy solo
`logger.exception` en **3112-3115**) · `_v2_recover_adaptive_state` (**3117**) · sesión del tick que
inyecta y restaura sink/reader (**4366-4479**).

**Tunables:** [`auto_v2_entry.py`](packages/py/application/src/bolsa_application/auto_v2_entry.py)
`V2Tunables` (**182**) · `adaptive_enabled = False` (**278**) · `adaptive_win_rate_floor = 0.35`
(**282**) · `tunables_from_env` (**398**) · `AUTO_ENGINE_SIM_V2_ADAPTIVE` (**464-466**) ·
`_adaptive_env_overrides` (**528-541**).

**Anclas del Paso 5 (medidas sobre `dcc0d64b`):** `auto_adaptive.py` →
`StrategyHealth.regime_undetermined` (**323**) · `from_evaluation` (**334**) ·
`AdaptivePlan.regime_undetermined` (**582**) · `AdaptivePlan.shrinkage` (**588**) ·
`"regimeUndetermined"`/`"shrinkage"` en `as_dict()` (**657-661**) · `build_adaptive_plan` (**916**,
`shrink` en **925**, el `if shrink else None` del reparto en **985**, la derivación del hueco en
**1002-1004**). `auto_simulation_worker.py` → `shrink=not reading.limits_adaptation` (**3130**) y la
declaración del hueco (**3155-3165**). Costura:
`apps/api-python/tests/test_auto_v54_auto13_regime_fallback_seam.py` (7 tests: hueco del tick, hueco
del cruce, control adverso real y los tres ejes).

## 4. Lo que falta, paso a paso, con su gate

> **Pasos 2–6: HECHOS** (ver §2b y §7). Lo que sigue se conserva como el **diseño ratificado** de
> cada uno: léase como histórico y como la especificación contra la que se verificó, no como trabajo
> pendiente.

### Paso 2 — Contador de fallos del sink + ancla durable (§21)

- **Contador en memoria** de fallos **consecutivos** y del último éxito, en la sesión del worker.
  Reglas: `1` fallo → `DEGRADED`; `3` consecutivos → `STALE`; **un éxito resetea**. El punto de
  instrumentación es `_v2_journal_adaptive_recommendation` (**3085**) y, si aplica, el sink de
  régimen por ciclo. **No reutilizar** el circuito del feed (`yahoo_circuit_breaker.py`): es otro eje
  (mercado, no evidencia Adaptive) y está **fuera de alcance**.
- **Ancla durable:** `journal_age_cycles` = ciclos de evaluación transcurridos desde la última
  `adaptive_recommendation` publicada (evento `AUTO_ADAPTIVE_RECOMMENDATION_EVENT`). Se lee con el
  **mismo lector durable** de `AUTO-11` (`list_entries` filtrado por `event_type`), sin tabla nueva.
  Definir **"ciclo"** = tick de evaluación Adaptive (documentarlo en el módulo, no dejarlo implícito).
- **Gate:** `1` fallo ⇒ `DEGRADED`; `N` ⇒ `STALE`; éxito ⇒ reset; el ancla durable **sobrevive a un
  reinicio** (test con un sink que falla las primeras `N` escrituras y luego un lector que mide la
  antigüedad).

### Paso 3 — Cableado del gate en el worker

Dentro de `_v2_build_adaptive_plan` (**3008**), tras construir `confidence`:

- **`gate=None` ⇒ comportamiento histórico byte-idéntico** (ni un `if` de más en los caminos
  existentes). Es el patrón de `AUTO-12` con `confidence=None`.
- **`OK`** ⇒ igual que hoy (con la confianza de `AUTO-12`).
- **`DEGRADED`** ⇒ **se desactiva el shrinkage por confianza** (el reparto cae a su eje histórico:
  pasar `confidence=None` a `recommend_allocation`/`build_adaptive_plan`) pero **se conserva la
  protección**: las pausas vivas, sus cooldowns y las pausas **nuevas por salud** siguen. La
  confianza, si ya se construyó, puede seguir publicándose **como evidencia** en `healthByStrategy`.
  **Decisión fina a medir con test**: si publicar la confianza mientras el gate la desactiva
  confunde, se publica además el estado del gate; lo que **no** puede es repartir con ella.
- **`STALE`** ⇒ además, **ninguna reactivación nueva**: una pausa viva **no levanta** su cooldown
  mientras la evidencia no sea legible, y el reparto se congela en el histórico. Lo que **sí** sigue:
  las pausas nuevas por salud. **Gate:** con `STALE`, una versión que cumpliría cooldown **sigue
  pausada**; y se **declara** el motivo.
- **`BLOCKED`** ⇒ **no construir el plan** (`adaptive = None`) y **registrar el motivo**. Efecto
  lateral declarado y correcto: el contador de cooldown **no avanza** ese tick (`_v2_next_paused_cycles`
  solo corre dentro de `_v2_build_adaptive_plan`), así que nada se reactiva por olvido; el journal de
  recomendación tampoco escribe fila (se declara).
- **Gate:** con flag OFF, **cero I/O** nuevo (medido con un store que cuenta llamadas); con `gate`
  `OK` byte-idéntico al plan de `v2.53`.

### Paso 4 — `RECOVERING` y la rampa (§23/§24)

- **Estado operativo** por estrategia: `ACTIVE` / `PAUSED` / `RECOVERING` (eje **operativo**; no se
  mezcla con el eje de datos ni con la calidad estadística — §29).
- **Entrada:** una versión **deja de estar pausada** habiendo estado pausada (racha `>= min_pause_cycles`
  y ya sin motivo) ⇒ `RECOVERING` con el factor **inicial `0.25`**.
- **Subida:** un escalón (`0.25 → 0.50 → 0.75 → 1.00`) por **evidencia**, no por reloj:
  `recovery_step_cycles` (propuesto `3`) ciclos de evaluación **con expectancy medida positiva** y sin
  `decay == SEVERE`.
- **Aplicación:** el factor actúa como **techo**: `m_final = min(m_reparto, factor)`. Solo **estrecha**,
  nunca ensancha, y **nunca** llega a `0` (suelo `0.25`). Se aplica **después** del reparto (y después
  del gate) y **antes** de publicar, para que la evidencia durable lleve el valor realmente aplicado.
- **Deterioro:** si la evidencia empeora (decisoria con expectancy `<= 0`, PF bajo umbral, o
  `decay == SEVERE`), manda la **rotación** y el escalón se **descarta** (la rampa se reinicia). La
  rampa **nunca** compite con la protección.
- **Memoria derivada:** `reactivated_at` **declarado** por el lector durable de `AUTO-11` (ampliar
  `AdaptiveStateReading`/`read_adaptive_state`) + ciclos posteriores con evidencia medida (fills con
  su `closedAt` de `AUTO-12`).
- **Hueco declarado:** sin fechas legibles (`recent_unavailable`) la rampa **no sube**: se queda en el
  escalón actual y lo **declara**. Nunca se inventa una recuperación.
- **Sello:** `ADAPTIVE_POLICY_VERSION` → **`auto13-v1`** (cambia la regla de asignación) y el test del
  sello se actualiza **con nombre**. Nuevos campos de `AdaptivePolicy` para los escalones y el paso.
- **Gate:** sube por **evidencia**, no por tiempo (con evidencia plana se queda); con deterioro vuelve
  a pausa; `m_final` nunca sube ni llega a `0`.

### Paso 5 — Fallback del §20 y los tres ejes

- Lo ya cumplido se **declara** (no se asume `RANGE`, no se hereda régimen de otro ciclo, el cubo
  `UNKNOWN` es propio): la rotación por régimen no aplica con régimen del cruce no determinado
  (`regime_undetermined`) y el fallback es la **evidencia global** (la fila de la estrategia).
- **Régimen del tick ausente (`None`) o `UNKNOWN`** ⇒ el gate lo trata como **evidencia incompleta
  declarada** (`regime_available=False` ⇒ `DEGRADED`), **nunca** como adverso ni favorable. La rama
  `adverse` de `recommend_rotation` no puede dispararse por un régimen que no se pudo leer.
- **Los tres ejes separados** (§29): operativo (`ACTIVE`/`PAUSED`/`RECOVERING`), datos
  (`OK`/`DEGRADED`/`STALE`/`BLOCKED`) y calidad (`LOW`/`MEDIUM`/`HIGH`) no comparten campo.

### Paso 6 — Verificación y sello (**HECHO**)

El paquete de cierre, el tag y las cifras **medidas** de CI: ver §7.

## 5. El método de verificación del repo (no improvisar)

- **Compuertas:** `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml`
  (el de CI, **no** rutas sueltas) · el `mypy` **exacto del YAML** (en `AUTO-12` cerró en
  `Success: no issues found in 497 source files`) · `uv run --no-sync lint-imports --config
  packages/py/.importlinter` → **`4 kept, 0 broken`**.
- **Delta SIMÉTRICO**, siempre **fichero a fichero contra `HEAD`** (nunca restando totales de fases
  previas). Los ficheros de test **modificados** se corren además en su versión de `HEAD` contra el
  código de la fase. El **único rojo admisible** es el test del sello de política, actualizado **con
  nombre** (en `AUTO-13` el sello pasó a `auto13-v1` en el **Paso 4**: `test_the_policy_version_
  seals_the_auto13_evidence_contract`). **Medido en el Paso 5:** las versiones de `HEAD` de
  `test_auto_adaptive.py` y `..._data_gate_wiring_seam.py` dan **1 rojo** —
  `test_degraded_stops_using_the_confidence_but_keeps_the_protection`, que afirmaba el contrato
  viejo de `DEGRADED` (`confidence=None`) — y ese rojo **es** el cambio declarado del §29 (la banda
  medida deja de ocultarse; el reparto sigue sin usarla). Ningún otro test de `HEAD` se rompe.
- **Mutaciones:** el script es [`apps/api-python/scripts/v2_44_mutation_audit.py`](apps/api-python/scripts/v2_44_mutation_audit.py).
  La matriz iba por **`M71`** (`AUTO-12` añadió `M60…M71`); `AUTO-13` ha añadido **`M72…M98`**
  (Paso 2: `M72…M77`; Paso 3: `M78…M82`; Paso 4: `M83…M93`; Paso 5: `M94…M98`: régimen ilegible
  tratado como adverso —con el adverso real de control—, motivo del hueco perdido, hueco no
  publicado, fallback no declarado y encogimiento inapagable). Al menos: estado→efecto invertido,
  `OK` por defecto, contador sin reset, `STALE` reactivando, `BLOCKED` adaptando, rampa que sube por
  tiempo, rampa que ensancha, rampa que llega a `0`, régimen ausente tratado como adverso,
  `journal_age` que no bloquea. **Gate de la lista: la matriz COMPLETA (`98` etiquetas) no puede
  dejar ninguna en `NADA`** (la trampa de `M39`), y el árbol debe quedar intacto al terminar.
  **Cierre medido del paso 5: `98/98` medidas, `0` en `NADA`, `98` restauradas byte a byte y la
  huella de git intacta.**
- **Realineo de fragmentos (declarado):** el renombrado `weight` → `share` del Paso 4 (exigido por
  `mypy` en `recommend_allocation`) dejó **`M21`** sin fragmento, y el cableado del gate del Paso 5
  hizo que `confidence=confidence` apareciese **dos veces** en el worker, dejando **`M71`**
  ambiguo. Ambas se re-anclaron sobre la MISMA invariante (el acotado a `[0,1]` del multiplicador y
  la confianza que llega al plan) y se re-midieron: `M21` muerde en **10** tests y `M71` en el test
  de la evidencia publicada. Una sonda desalineada **afirma** cobertura que no tiene; por eso el
  anclaje se declara aquí en vez de silenciarse.
- **Escritura de los mutantes (hardening del Paso 5):** con ~98 reescrituras seguidas de los mismos
  ficheros, Windows devolvió `OSError [Errno 22]` en el `open('wb')` del worker a mitad de matriz.
  La sonda ahora escribe a un temporal y **reemplaza atómicamente** (`os.replace`) con reintentos, y
  si no entra **aborta sin tocar el fichero** (el original sigue intacto: la restauración nunca
  puede fallar antes de haber mutado).
  **Aviso:** la sonda heredada **`M33`** apunta al local `cycle_risk` dentro de
  `_v2_build_adaptive_plan` (se realineó en `AUTO-12` al desaparecer la llamada *inline*). **No**
  reintroducir una llamada *inline* a `build_auto_self_evaluation` en el worker sin realinear `M33`:
  una sonda desalineada **afirma** cobertura que no tiene.
- **Tests a añadir/ampliar:** `packages/py/analytics/tests/test_auto_adaptive.py` (rampa, `min` con el
  reparto, sello, hueco del cruce y encogimiento), `packages/py/application/tests/test_auto_adaptive_recovery.py` (`reactivated_at`),
  `packages/py/application/tests/test_auto_self_evaluation_feed.py` (evidencia medida de la rampa), y
  las **costuras nuevas** `apps/api-python/tests/test_auto_v54_auto13_data_gate_seam.py` (contador de
  fallos, ancla durable), `..._data_gate_wiring_seam.py` (los tres efectos del gate en el plan),
  `..._recovery_seam.py` (`RECOVERING` con la rampa, cero I/O) y `..._regime_fallback_seam.py`
  (hueco del régimen §20 —tick y cruce—, control adverso real y los tres ejes separados).
- **Bloques offline sin PostgreSQL**, con la extracción de targets del propio YAML, para que los
  `skipped` cuadren con la CI.

## 6. Trampas conocidas del entorno (Windows / este repo)

1. `git show HEAD:<file> > <file>` **fabrica bytes nulos** en PowerShell ⇒ leer el contenido y
   escribirlo **como bytes** con Python (`SyntaxError: source code string cannot contain null bytes`).
2. **`asyncpg` ausente** ⇒ las suites PG de `packages/py/application` no corren offline (en
   `AUTO-12` fueron **5 errores pre-existentes**, no fallos de la fase). La **CI del tag sí mide
   todo**; es la cifra que se publica.
3. El **teardown PG del conftest de `apps/api-python`** puede colgar `pytest`: usar `DATABASE_URL`
   con fallo rápido y un **wrapper que fuerza la salida** de `pytest`.
4. `lint-staged` imprime `could not find any staged files matching configured tasks` en commits sin
   JS: **inofensivo**.
5. Powershell no traga heredocs bash: escribir el mensaje de commit a un **fichero** y usar
   `git commit -F`.
6. `python -c` con salida no-ASCII revienta en `cp1252`: **escribir a fichero UTF-8** en vez de
   imprimir.
7. **Bloqueo transitorio de fichero al mutar:** con decenas de reescrituras seguidas, Windows puede
   devolver `OSError [Errno 22]` en el `open('wb')`. La sonda de mutaciones ya escribe a un temporal y
   reemplaza atómicamente con reintentos (ver §5); **no** volver a `path.write_bytes` directo.
8. Leer un fichero con el visor del editor puede dejar el **prefijo del número de línea** dentro de
   una línea (`    10|texto`) si se copia la selección con los números. Revisar con
   `rg "^\s*\d+\|"` antes de commitear código nuevo (pasó en la costura del Paso 5 y se corrigió).

## 7. El cierre, hecho y medido (Paso 6)

**Documentos del paquete** (viajan **dentro** del tag, como en `v2.47`–`v2.53`):

- **audit-pack nuevo**
  [`audit-pack-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md`](./audit-pack-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md):
  el invariante de la fase, los cuatro estados con su efecto **derivado**, el contador + el ancla con la
  regla de corroboración, el cableado, la rampa, el fallback del §20, los tres ejes del §29, la matriz
  `M72…M98`, los límites declarados y el freeze.
- **este relevo**, renombrado de `traspaso-relevo-v2-54-auto-13-en-curso-...` a
  `traspaso-relevo-post-v2.54-auto-13-adaptive-data-gate-y-recovery-gradual-...` (la fase **cierra**).
- `CHANGELOG.md` (**`1.79.0-beta`**), `PROJECT_STATE.md` (asOf, relevo vivo, línea de la fase y
  siguiente) y la **entrada 138** del `engineering-index-2026-08-03.md`.

**Bump:** `1.78.0-beta` → **`1.79.0-beta`** en el `package.json` de la raíz.

**Sello:** commit del paquete → `main` en **fast-forward** (de `d08e66e5`, el sello de `v2.53`, al commit
del paquete) → tag anotado **`v2.54-beta`** empujado **de uno en uno**, sin `--follow-tags` (lección
medida de `v2.49`: con más de tres tags a la vez GitHub **no** crea el evento de tag) → CI del tag →
**commit de sellado** con las cifras **medidas**.

**Cifras de CI del tag (medidas, no supuestas):** *se completan en el commit de sellado, con el run de
`Release tag CI` sobre la ref del tag, el job `python` offline frente a los `2459 passed / 35 skipped` de
`v2.53-beta`, el `quality` de `main` y los `check-runs` del commit.*

## 8. Límites declarados y freeze

- **El gate no es un permiso**: limita la adaptación; no ejecuta, no pausa dinero, no toca el
  gobernador (audit §21: «Risk Engine continúa funcionando»).
- **El contador de fallos es de proceso**: su límite se declara; el ancla duradera es el journal.
- **La rampa nunca ensancha ni inventa**: `min` con el reparto, suelo `0.25`, subida **solo** por
  evidencia medida.
- **`RECOVERING` no es un modo de la rotación**: es estado **operativo** derivado; quien pausa y
  reactiva sigue siendo `recommend_rotation` con su hysteresis y su cooldown.
- **Sin régimen no hay juicio de régimen (§20):** un régimen ilegible (`None`/`""`/`UNKNOWN`/
  `RISK_OFF`) o un cruce sin celda decisiva **no pausa ni favorece**: degrada el gate y la rotación
  decide con la evidencia **global** de la estrategia, y ese fallback se **declara**
  (`regimeUndetermined` + `fallback: strategy_evidence`). Nunca se asume `RANGE` ni se hereda el
  régimen de otro ciclo.
- **Medir ≠ usar (§29):** el gate puede apagar el **uso** de la confianza (el encogimiento del
  reparto) sin borrar el **hecho medido**: la banda sigue publicándose y `shrinkage` declara si el
  reparto la usó. Los tres ejes —operativo, datos y calidad— viajan en campos propios.
- **`AUTO-14` fuera:** reparto por celda de régimen (matriz avanzada), Data Gate **persistido** (si el
  Paso 3 demuestra que hace falta) y la **UI de explicación**.
- **No se toca:** el sello de `V2.53`, `auto_adaptive_journal.py` (salvo la decisión 3 —ya
  ratificada **en contra**—, queda igual), `yahoo_circuit_breaker.py`, `ADAPTIVE_ADVERSE_REGIMES`, los
  umbrales de rotación, el gobernador, la tabla `decision_journal_entries` y su índice (**sin
  backfill**), ni el esquema (**sin migración**). Sin SHORT. Sin `prettier` para `*.md`.

## 9. Punto de entrada para el siguiente agente

1. Leer **este relevo** entero (es el estado de la fase **cerrada**: las cuatro decisiones, lo medido y
   los límites declarados).
2. Leer el [audit-pack](./audit-pack-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md)
   (el invariante, la matriz de mutaciones y los límites) y el
   [plan](./plan-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md) (§2 diseño,
   §3 pasos, §4 verificación, §5 decisiones ratificadas).
3. `git log --oneline -6` y `git tag --points-at <commit del paquete>` → confirmar el commit sellado y
   `v2.54-beta`; `git status` limpio salvo `governor.json`.
4. **Por dónde sigue la línea** (declarado, no decidido aquí): **`AUTO-14`** — el **reparto por celda de
   régimen** (la matriz avanzada que el §20 dejó explícitamente fuera) y/o el **Data Gate persistido**
   *si el Paso 3 demuestra que hace falta* (hoy el gate es una lectura del tick: el contador de fallos se
   pierde al reiniciar y eso está declarado) y/o la **UI de `AUTO-7`…`AUTO-13`** (el cruce
   `strategy × regime`, la evidencia Adaptativa, `confidence`/`recent`/`decay`, el estado del gate y la
   rampa ya existen y **no se ven**).
5. **El flag Adaptive sigue OFF por defecto**: el Data Gate y la rampa **no se ejecutan** en producción
   hasta un flag explícito. El runtime publicado es, en comportamiento, el de `v2.53-beta`.
6. **Si hay que auditar la fase**: el §10 del audit-pack lista los límites declarados (lo que la fase
   **no** afirma) y el §5 de este relevo, el método de verificación del repo (compuertas, delta
   simétrico fichero a fichero y matriz de mutaciones **completa** sin etiquetas en `NADA`).
