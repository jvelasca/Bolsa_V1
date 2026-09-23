# Traspaso de relevo — `AUTO-13` **EN CURSO** (`V2.54` / `1.79.0-beta`)

**Fase:** `AUTO-13` (Adaptive Data Gate + recovery gradual) · **Fecha:** 2026-09-23 · **Fase
anterior:** `V2.53` / `AUTO-12` (sellada: tag `v2.53-beta` → `a6655e6e`, `Release tag CI`
`35836248169` **GREEN**, `1.78.0-beta`).
**Documentos de la fase:** [plan](./plan-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md)
(ratificado) · este relevo.
**Estado:** **fase CASI COMPLETA** — Pasos 1–4 hechos y verificados; **Pasos 5–6 pendientes** (el
runtime sigue siendo el de `v2.53-beta` con el flag Adaptive **OFF**: nada de esto se ejecuta en
producción hasta el sello). Rama de auditoría externa: `auto-13-adaptive-data-gate` + **PR draft
#63** contra `main`, que crece con la fase.

> **Este documento es la fuente de verdad del estado EN CURSO.** Se lee **antes** que
> [`PROJECT_STATE.md`](./PROJECT_STATE.md), que sigue describiendo la última fase **cerrada**
> (`AUTO-12`) y apunta aquí como relevo vivo.

---

## 0. Qué está ratificado y qué queda

**Rótulo ratificado por el propietario:** `AUTO-13` sobre **`V2.54` / `1.79.0-beta`**, con alcance
**core backend** (§22 + §24 del audit **y** el fallback del §20), **sin UI**, **sin migración**
(Alembic head sigue en `044_auto_cycle_trace`), **sin tocar el gobernador** y **sin estado propio
persistido** (la memoria de la rampa se **deriva**).

**Las cuatro decisiones, ratificadas (2026-09-23), con su porqué:**

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

---

## 1. Estado medido del repo (2026-09-23)

- **HEAD `30b2e5b3`** (rama `auto-13-adaptive-data-gate`; el Paso 4 va en el árbol sin commitear
  mientras se verifica); `main` local sigue en `v2.53-beta`. Árbol limpio **salvo `governor.json`**
  (sin trackear, como estaba) y los ficheros del Paso 4.
- **Commits de la fase:** `009e8965` (plan) · `d9242970` (ratificación) · `f45ac604` (**Paso 1**) ·
  `28b5ac5f` (**Paso 2**) · `30b2e5b3` (**Paso 3**).
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

## 2b. Lo ya HECHO y verificado (Pasos 2, 3 y 4)

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
  `test_auto_self_evaluation_feed.py` (evidencia medida); **M83–M91** (9 mutaciones).

## 3. Anclas de código para los Pasos 2–6 (medidas)

**Adaptive (analytics):** [`auto_adaptive.py`](packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py)
`ADAPTIVE_POLICY_VERSION = "auto12-v1"` (**127** — sube a `auto13-v1`) · `AdaptivePolicy` (**201**) ·
`StrategyHealth` (**227**) · `recommend_rotation` (**510**) · `_allocation_weights` (**568**) ·
`_confidence_factor` (**606**) · `recommend_allocation` (**628**) · `build_adaptive_plan` (**703**).

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

## 4. Lo que falta, paso a paso, con su gate

> **Pasos 2, 3 y 4: HECHOS** (ver §2b). Lo que sigue se conserva como el **diseño ratificado** de
> cada uno; léase como histórico, no como trabajo pendiente. Pendiente real: **Paso 5** (fallback
> declarado del §20 + tres ejes separados) y **Paso 6** (verificación y sello).

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

### Paso 6 — Verificación y sello

Ver §5 (método) y §7 (trámites de cierre).

## 5. El método de verificación del repo (no improvisar)

- **Compuertas:** `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml`
  (el de CI, **no** rutas sueltas) · el `mypy` **exacto del YAML** (en `AUTO-12` cerró en
  `Success: no issues found in 497 source files`) · `uv run --no-sync lint-imports --config
  packages/py/.importlinter` → **`4 kept, 0 broken`**.
- **Delta SIMÉTRICO**, siempre **fichero a fichero contra `HEAD`** (nunca restando totales de fases
  previas). Los ficheros de test **modificados** se corren además en su versión de `HEAD` contra el
  código de la fase. El **único rojo admisible** es el test del sello de política, actualizado **con
  nombre** (en `AUTO-12` fue `test_the_policy_version_seals_the_auto12_evidence_contract`; aquí será
  el de `auto13`).
- **Mutaciones:** el script es [`apps/api-python/scripts/v2_44_mutation_audit.py`](apps/api-python/scripts/v2_44_mutation_audit.py).
  La matriz iba por **`M71`** (`AUTO-12` añadió `M60…M71`); `AUTO-13` ha añadido **`M72…M91`**
  (Paso 2: `M72…M77`; Paso 3: `M78…M82`; Paso 4: `M83…M91`). Al menos: estado→efecto invertido,
  `OK` por defecto, contador sin reset, `STALE` reactivando, `BLOCKED` adaptando, rampa que sube por
  tiempo, rampa que ensancha, rampa que llega a `0`, régimen ausente tratado como adverso,
  `journal_age` que no bloquea. **Gate de la lista: la matriz COMPLETA (`91` etiquetas) no puede
  dejar ninguna en `NADA`** (la trampa de `M39`), y el árbol debe quedar intacto al terminar.
  **Aviso:** la sonda heredada **`M33`** apunta al local `cycle_risk` dentro de
  `_v2_build_adaptive_plan` (se realineó en `AUTO-12` al desaparecer la llamada *inline*). **No**
  reintroducir una llamada *inline* a `build_auto_self_evaluation` en el worker sin realinear `M33`:
  una sonda desalineada **afirma** cobertura que no tiene.
- **Tests a añadir/ampliar:** `packages/py/analytics/tests/test_auto_adaptive.py` (rampa, `min` con el
  reparto, sello), `packages/py/application/tests/test_auto_adaptive_recovery.py` (`reactivated_at`),
  `packages/py/application/tests/test_auto_self_evaluation_feed.py` (evidencia medida de la rampa), y
  las **costuras nuevas** `apps/api-python/tests/test_auto_v54_auto13_data_gate_seam.py` (contador de
  fallos, ancla durable), `..._data_gate_wiring_seam.py` (los tres efectos del gate en el plan) y
  `..._recovery_seam.py` (`RECOVERING` con la rampa, ceros I/O).
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

## 7. Trámites de cierre (Paso 6)

- Docs de fase: **plan** (ya), **audit-pack** nuevo
  `audit-pack-v2-54-auto-13-...-2026-09-23.md`, **este relevo** (actualizar a cerrado) y
  `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index-2026-08-03.md` (entrada nueva).
- Bump `1.78.0-beta` → **`1.79.0-beta`** en `package.json`.
- Commit de código (`feat(v2.54): …`) + commit de docs, **tag `v2.54-beta`**, esperar la CI del tag
  y **sellar** con las cifras medidas (job `python` del tag vs los `2459` de `v2.53`).
- Convenciones de mensaje observadas: `feat(v2.54): …` / `docs(v2.54): …` con trailer
  `Co-authored-by: Cursor <cursoragent@cursor.com>`.

## 8. Límites declarados y freeze

- **El gate no es un permiso**: limita la adaptación; no ejecuta, no pausa dinero, no toca el
  gobernador (audit §21: «Risk Engine continúa funcionando»).
- **El contador de fallos es de proceso**: su límite se declara; el ancla duradera es el journal.
- **La rampa nunca ensancha ni inventa**: `min` con el reparto, suelo `0.25`, subida **solo** por
  evidencia medida.
- **`RECOVERING` no es un modo de la rotación**: es estado **operativo** derivado; quien pausa y
  reactiva sigue siendo `recommend_rotation` con su hysteresis y su cooldown.
- **`AUTO-14` fuera:** reparto por celda de régimen (matriz avanzada), Data Gate **persistido** (si el
  Paso 3 demuestra que hace falta) y la **UI de explicación**.
- **No se toca:** el sello de `V2.53`, `auto_adaptive_journal.py` (salvo la decisión 3 —ya
  ratificada **en contra**—, queda igual), `yahoo_circuit_breaker.py`, `ADAPTIVE_ADVERSE_REGIMES`, los
  umbrales de rotación, el gobernador, la tabla `decision_journal_entries` y su índice (**sin
  backfill**), ni el esquema (**sin migración**). Sin SHORT. Sin `prettier` para `*.md`.

## 9. Punto de entrada para el siguiente agente

1. Leer **este relevo** entero (es el estado en curso).
2. Leer el [plan](./plan-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md)
   (§2 diseño, §3 pasos, §4 verificación, §5 decisiones ya ratificadas).
3. `git log --oneline -3` → confirmar el commit del **Paso 4** en HEAD (rama
   `auto-13-adaptive-data-gate`) y `git status` limpio salvo `governor.json`.
4. **Primera acción concreta:** **Paso 5** — declarar el fallback del §20 (régimen del cruce no
   determinado ⇒ `regime_undetermined` con la evidencia global; régimen del tick ausente ⇒ `DEGRADED`
   y **nunca** rama adversa) y verificar que los tres ejes viajan sin mezclarse, y cubrirlo con tests
   y mutaciones (`M94…`, los rótulos `M92`/`M93` ya los consume la memoria de la rampa del Paso 4)
   antes del sello.
