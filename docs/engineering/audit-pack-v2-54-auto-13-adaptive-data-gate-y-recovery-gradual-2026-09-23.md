# Audit-pack `AUTO-13` Adaptive Data Gate + recovery gradual — `1.79.0-beta` (2026-09-23)

**Fase:** `V2.54` · **Rótulo:** `AUTO-13` · **Bump:** `1.78.0-beta` → **`1.79.0-beta`** · **Tag:**
`v2.54-beta` · **Fase anterior:** `V2.53` / `AUTO-12` (tag `v2.53-beta` → `a6655e6e`, `Release tag CI`
`35836248169` **GREEN**, `check-runs` `27 success` + `1 skipped`, job `python` del tag
**`2459 passed / 35 skipped`**).

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva,
sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal durable** (la entrada
`adaptive_recommendation` proyecta claves explícitas: `regimeUndetermined` y `shrinkage` viven en el
**plan** y en la traza del tick, nunca en la evidencia durable). El gobernador y su evidencia quedan
**intactos**. Adaptive **sigue siendo recomendador read-only** y con el flag **OFF** el camino de
producción es **byte-idéntico** a `v2.53`: esta fase no se ejecuta en producción hasta un flag explícito.

---

## 0. Resumen: qué instala esta pasada

`AUTO-12` dejó el reparto ponderado por la calidad estadística de la evidencia. Faltaban las dos
mitades que el audit externo pedía en §21/§22/§23/§24/§29: qué hacer cuando **los datos** que
sostienen esa evaluación no están sanos, y cómo **volver** de una pausa sin dar un salto.

Esta pasada añade las dos, con una regla de diseño que atraviesa todo el trabajo —**lo que no se midió
se declara, y lo que no se pudo leer no decide**—:

1. **Un gate de datos puro** (`auto_adaptive_data_gate.py`): `OK`/`DEGRADED`/`STALE`/`BLOCKED` con el
   **efecto derivado** por tabla (`ADAPTS`/`LIMITS`/`FREEZES`/`NO_ADAPT`) y una precedencia explícita.
2. **Dos fuentes de verdad para la salud del gate**: cadencia declarada + antigüedad del journal
   (**durable**, sobrevive a reinicios) y un contador de fallos consecutivos del sink (**de proceso**,
   detecta el fallo al instante). El límite de cada una se declara.
3. **El cableado**: `OK` ⇒ plan byte-idéntico; `DEGRADED` ⇒ se apaga el **uso** de la confianza pero
   **no** la protección; `STALE` ⇒ además no se admiten reactivaciones nuevas; `BLOCKED` ⇒ **no se
   adapta** ese tick y se declara.
4. **`RECOVERING`**: la vuelta de una pausa es una **rampa** `0.25 → 0.50 → 0.75 → 1.00` que sube por
   **evidencia medida posterior al corte**, actúa como **techo** del reparto (`min`) y nunca llega a `0`.
5. **El fallback del §20**: un régimen ilegible **no** es adverso, y un cruce `strategy × regime` sin
   celda decisiva **no** se sustituye por `RANGE` ni por el último conocido: la rotación decide con la
   evidencia **global** y el hueco se declara (`regimeUndetermined`).
6. **Los tres ejes separados (§29)**: operativo (`ACTIVE`/`PAUSED`/`RECOVERING`), datos
   (`OK`/`DEGRADED`/`STALE`/`BLOCKED`) y calidad (`LOW`/`MEDIUM`/`HIGH`) viajan en campos propios;
   `shrinkage` declara si el reparto **usó** la calidad medida.

Superficie nueva: `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py` y la
costura `apps/api-python/tests/test_auto_v54_auto13_regime_fallback_seam.py`.
Superficie tocada: `auto_adaptive.py` (plan, rotación, reparto, salud), `auto_adaptive_recovery.py`
(`last_published_at`, `reactivated_at`), `auto_self_evaluation_feed.py` (`recovery_evidence_from_fills`)
y el worker (`auto_simulation_worker.py`).

## 1. El invariante: **ninguna estrategia puede ser castigada por una deuda de los datos**

> Un dato incompleto se **declara** (`DataGateStatus`) y **limita la adaptación**; nunca se convierte en
> «esta estrategia es mala». Una vuelta de pausa se **gana** con evidencia medida; nunca se concede por
> el paso del tiempo. Y un régimen que no se pudo leer **no** acusa a nadie.

Es la extensión del invariante de la línea al **material** de la decisión: `AUTO-9` cerró *«¿cuánto
vale?»*, `AUTO-10` *«¿de qué ciclo es?»*, `AUTO-11` *«¿dónde vive su memoria?»*, `AUTO-12` *«¿cuánto
puedo creérmelo?»* y `AUTO-13` cierra *«¿están sanos los datos con los que me lo creo, y cómo vuelvo?»*.

**Cuatro corolarios, todos con test y con mutación que los mata:**

- **El gate no es un permiso.** Limita cuánto adapta Adaptive; no ejecuta, no pausa dinero y no toca al
  gobernador (§21 del audit: «Risk Engine continúa funcionando»).
- **Medir ≠ usar.** El gate puede apagar el **uso** de la confianza (el encogimiento del reparto) sin
  borrar el **hecho medido**: la banda sigue publicándose.
- **Ausencia ≠ adversidad.** `None`, `""`, `UNKNOWN` y `RISK_OFF` son **huecos declarados**, nunca un
  régimen malo; con el cruce indeterminado decide la evidencia **global**.
- **La rampa solo estrecha.** `m_final = min(m_reparto, escalón)`, suelo `0.25`: es una reincorporación
  gradual, no una pausa encubierta ni un premio.

## 2. El gate: cuatro estados, cuatro efectos **derivados**

`auto_adaptive_data_gate.py` es puro: sin I/O, sin estado y **orden-invariante**.

- `DataGateStatus = OK | DEGRADED | STALE | BLOCKED` y
  `DataGateEffect = ADAPTS | LIMITS | FREEZES | NO_ADAPT`.
- **El efecto se DERIVA del estado** con una tabla (`_EFFECT_BY_STATUS`); no es un campo que pueda
  divergir. `reading.effect`, `reading.adapts`, `reading.limits_adaptation` y
  `reading.blocks_adaptation` son las lecturas que usa el worker.
- **Precedencia `BLOCKED > STALE > DEGRADED > OK`**: el estado grave **absorbe** los motivos de los
  leves en vez de esconderlos (`notes` acumula), así que un tick puede publicar `STALE` con el fallo de
  sink que lo empujó.
- **Sin insumos ⇒ estado declarado, nunca un `OK` fingido**: `evidence_not_provided` deja constancia de
  que **no se pidió medir** (y por eso no degrada: es lo que mantiene byte-idéntico el camino histórico
  cuando el gate no se aporta), mientras que `insufficient_history`, `durable_state_unread`,
  `unreadable_rows` y `policy_version_mismatch` son motivos de primera clase de `STALE`.
- Hechos que degradan: `sink_failures` (≥1 ⇒ `DEGRADED`; ≥`DATA_GATE_SINK_FAILURES_STALE_DEFAULT = 3`
  ⇒ `STALE`), `journal_age_cycles` (> `DATA_GATE_JOURNAL_GAP_BLOCKED_DEFAULT = 10` ⇒ `BLOCKED`; por
  encima de `stale` ⇒ `STALE`), `readOk = False`, `measurement_completeness` incompleta,
  `recentAvailable = False`, `regimeAvailable = False`, `unreadableRows > 0` y `policyVersionMismatch`.
- **Cadencia declarada**: `DataGatePolicy.evaluation_cycle_seconds = 60.0` (validado `> 0`) y el helper
  puro `journal_age_cycles(...)`: la antigüedad se mide en **ciclos declarados**, no en «segundos
  razonables» implícitos. `DATA_GATE_POLICY_VERSION = "auto13-v1"`.

## 3. El contador de fallos (proceso) y el ancla durable (journal)

Las dos fuentes se combinan porque cada una tapa el hueco de la otra, y **el límite de cada una se
declara** (decisión ratificada nº1):

- **Contador en memoria** de fallos **consecutivos** de `_v2_journal_adaptive_recommendation`: se
  incrementa en el `except` y **un éxito RESETEA** la racha. Detecta el fallo al instante, pero se pierde
  al reiniciar.
- **Ancla durable**: `AdaptiveStateReading.last_published_at` (el `asOf` de la evidencia MÁS NUEVA del
  journal) alimenta `journal_age_cycles`. Sobrevive a reinicios, pero un journal **sano y antiguo** no
  prueba que esté roto — y de ahí la regla de corroboración.
- **Regla de corroboración (decisión fina, ratificada)**: el ancla durable **solo** bloquea si hay un
  fallo de escritura **propio** (`_v2_adaptive_gate_journal_age` devuelve `None` sin fallos). Sin ella,
  un Adaptive OFF o una pausa larga dejarían el gate `BLOCKED` para siempre: `BLOCKED` ⇒ `adaptive =
  None` ⇒ no se escribe ⇒ **deadlock**. Una antigüedad sin corroborar **mide y declara**, pero no
  bloquea.
- `journal_age_cycles = None` **no** bloquea (no se puede juzgar la antigüedad); si además se congela por
  otro motivo, se declara `journal_age_unknown` en vez de suponer juventud.

## 4. El cableado: `OK` byte-idéntico, y los otros tres efectos

`_v2_build_adaptive_plan` compone la lectura de **hechos que el tick ya midió** (`_v2_adaptive_data_gate`):
**cero I/O nuevo**, medido con un store que cuenta llamadas. `gate=None` (o el flag OFF) ⇒ comportamiento
histórico.

| Estado | Efecto | Qué hace el plan |
| --- | --- | --- |
| `OK` | `ADAPTS` | mismos argumentos y plan **byte-idéntico** a `v2.53` |
| `DEGRADED` | `LIMITS` | `shrink=False`: el reparto **no** usa la confianza (cae a su eje histórico) pero la banda medida **se sigue publicando**; la protección (pausas, cooldowns, pausas de salud) intacta |
| `STALE` | `FREEZES` | además **ninguna reactivación nueva**: `_v2_adaptive_decision_cycles` recorta el contador **por debajo** de `min_pause_cycles`, así que `recommend_rotation` mantiene la pausa con el motivo declarado `cooldown`. El contador **real** sigue creciendo |
| `BLOCKED` | `NO_ADAPT` | `adaptive = None` declarado en el log; el journal **no** escribe fila |

Dos decisiones finas ratificadas del paso 3:

1. **La completitud del gate son los ejes que Adaptive EXIGE** (resultados y riesgo), **no** el
   `measurement_completeness` de la confianza —que combina también el net-R **opcional**, cuyo hueco cae
   por diseño al eje moneda (`AUTO-9`)—: usar aquel apagaría `AUTO-12` casi siempre (**M82**).
2. **`regime_available` acepta los dos ejes** (canónico `TREND_UP` y operativo `BULL_TREND`) y solo
   declara ausencia con `None`, cadena vacía, `UNKNOWN` y `RISK_OFF` (**M81**).

Y una decisión de **§29** (paso 5): el `STALE`/`DEGRADED` retira el **uso**, nunca el hecho medido
(`shrink`), de modo que `ACTIVE` + datos `DEGRADED` + calidad `LOW` se lee entero (**M98**).

## 5. `RECOVERING`: la rampa por evidencia (§23/§24)

Hasta `v2.53`, una versión que cumplía su cooldown volvía al **peso pleno de golpe**: el único límite era
la puerta de la rotación.

- **Estado operativo derivado** (`ADAPTIVE_STATE_ACTIVE` / `PAUSED` / `RECOVERING`) publicado en
  `AdaptivePlan.operational_states` con `state_for(...)`. **No es un modo de la rotación**: quien pausa y
  reactiva sigue siendo `recommend_rotation`.
- **Rampa declarada**: `ADAPTIVE_RECOVERY_STEPS_DEFAULT = (0.25, 0.50, 0.75, 1.00)` y
  `ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT = 3`, campos de política validados (escalones en `(0, 1]`,
  estrictamente crecientes, paso `>= 1`).
- **`recovery_reading(...)` (puro)**: `escalón = escalones[min(último, ciclos_positivos // paso)]`. Sube
  **solo con evidencia medida positiva posterior al corte**; con evidencia plana se queda; con deterioro
  (`decay == SEVERE` o expectancy reciente `<= 0`) o con hueco de fechas vuelve al **suelo** y lo
  **declara** (`recovery_severe_decay`, `recovery_not_positive`, `recovery_unmeasured`).
- **Aplicación**: `m_final = min(m_reparto, escalón)` dentro de `recommend_allocation(..., recovery=)`,
  **después** del reparto y **antes** de publicar (la evidencia durable lleva el valor que de verdad se
  aplicó). Solo estrecha, nunca ensancha y nunca deja a nadie en `0`.
- **Memoria derivada, sin estado propio**: el lector durable la **siembra** (`reactivated_at`, derivado de
  la racha con la pausa previa **probada**) y el proceso la **completa** con las transiciones que ve: la
  pausa → activa se fecha **en el tick en que ocurre**, así que no hay ningún tick a peso pleno
  (**M93**); si la evidencia devuelve la versión a pausa, el escalón **se descarta** (la protección manda).
- `ADAPTIVE_POLICY_VERSION` → **`auto13-v1`** (cambia la regla de asignación) con el test del sello
  actualizado **con nombre**.

## 6. El fallback del §20: el hueco de régimen, declarado

Dos mitades, las dos con su control:

- **Régimen del tick ilegible** (`None`, `""`, `UNKNOWN`, `RISK_OFF`) ⇒ el gate lo trata como evidencia
  incompleta declarada (`regime_available=False` ⇒ `DEGRADED`, `regime_absent`) y **nunca** como adverso
  ni favorable: la rama `adverse` de `recommend_rotation` no puede dispararse por un régimen que no se
  pudo leer. **Control del test**: el régimen adverso **real** del tick (`market_regime_gate` sirve el eje
  operativo, p. ej. `BEAR_TREND`) **sí** la arma — sin ese control, «no se pausa» también pasaría con una
  rotación muerta que no juzgase nada.
- **Cruce `strategy × regime` no determinado** ⇒ `StrategyHealth.regime_undetermined` conserva el **par
  `(régimen, motivo)`** que publica `declared_regime` (un `UNKNOWN` legítimo deja de ser indistinguible de
  un régimen mal medido), `AdaptivePlan.regime_undetermined` lo publica en **campo propio** —ordenado por
  versión y **derivado** de la salud, no recalculado, para que no pueda divergir del cruce que usó la
  rotación— y el tick lo declara en su traza (`regimeUndetermined` + `fallback: strategy_evidence`).
  **Nunca** se asume `RANGE` ni se hereda el régimen de otro ciclo.

## 7. Los tres ejes, en campos propios (§29)

- **Operativo**: `ACTIVE`/`PAUSED`/`RECOVERING` — `AdaptivePlan.operational_states`.
- **Datos**: `OK`/`DEGRADED`/`STALE`/`BLOCKED` — el estado del gate, en su registro del tick.
- **Calidad**: `LOW`/`MEDIUM`/`HIGH` — la banda **medida**, en `healthByStrategy`/`evidence_for`.
- **Y el puente declarado**: `AdaptivePlan.shrinkage` dice si el reparto **pudo** usar esa calidad. Un
  estado legal y perfectamente legible es `ACTIVE` + datos `DEGRADED` + calidad `LOW` +
  `shrinkage = False`: ningún eje se disfraza de otro.

## 8. Matriz de mutaciones (`M72…M98`): 27/27 muerden

La sonda es `apps/api-python/scripts/v2_44_mutation_audit.py`. `AUTO-13` añade **27 etiquetas**, agrupadas
por el paso que las mide (y cada una con su descripción en el docstring de la sonda, que es donde vive el
«qué afirmaría el mutante»):

- **Paso 2 (`M72…M77`, 6)**: efecto invertido · `OK` por defecto · antigüedad que no bloquea · contador sin
  reset · ancla sin corroborar (el deadlock) · cadencia ignorada.
- **Paso 3 (`M78…M82`, 5)**: `BLOCKED` adaptando · `STALE` reactivando · `DEGRADED` repartiendo con la
  confianza · régimen siempre disponible · completitud por el eje **opcional**.
- **Paso 4 (`M83…M93`, 11)**: rampa que sube por tiempo · rampa que ensancha · rampa que llega a `0` ·
  pausa que publica su rampa · recuperación no derivada · reincorporación sin corte probado · ventana
  ilegible declarada disponible · evidencia anterior al corte · rampa no cableada · memoria de la rampa no
  sembrada · transición no fechada en el tick.
- **Paso 5 (`M94…M98`, 5)**: régimen ilegible tratado como adverso · el motivo del hueco del cruce se
  pierde · el hueco no viaja al plan · el fallback no se declara · el encogimiento no se puede apagar.

**Cierre medido**: matriz **COMPLETA `98/98`** medidas, **`0`** etiquetas en `NADA`, **98**
restauraciones byte a byte y huella `git status` de los ficheros tocados **idéntica** antes y después
(`intacto: la sonda no altero el arbol`).

**Dos realineos declarados** (una sonda desalineada **afirma** cobertura que no tiene, así que se
declaran en vez de silenciarse):

- **`M21`** (asignación monótona) se quedó sin fragmento cuando el paso 4 renombró `weight → share` en
  `recommend_allocation` (lo exigió `mypy`); se re-ancló sobre la **misma** invariante (el acotado a
  `[0, 1]` del multiplicador) y vuelve a morder en **10** tests.
- **`M71`** (confianza no cableada) quedó **ambiguo** cuando el paso 5 hizo que `confidence=confidence`
  apareciese dos veces en el worker (la lectura del tick y la evidencia de la rampa); se ancló al par
  `confidence` + `shrink` de la llamada al plan y muerde en el test de la evidencia publicada.

**Endurecimiento de la sonda**: con ~98 reescrituras seguidas de los mismos ficheros, Windows devolvió
`OSError [Errno 22]` en el `open('wb')` del worker a mitad de matriz. La sonda ahora escribe a un
temporal y **reemplaza atómicamente** (`os.replace`) con reintentos y, si no entra, **aborta sin tocar el
fichero**: la restauración nunca puede fallar antes de haber mutado.

## 9. Verificación (lo medido, y lo que no se pudo medir aquí)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (el de CI) | `All checks passed!` |
| `mypy` (comando exacto del YAML, `--follow-imports=silent`) | `Success: no issues found in 497 source files` |
| `lint-imports --config packages/py/.importlinter` | `4 kept, 0 broken` (618 ficheros, 3314 dependencias) |
| Tramo `AUTO-13` (analytics + application + costuras api) | **`202 passed`** (4 unit: 78 + 29 + 26 + 29; 4 costuras: 9 + 10 + 14 + 7) |
| Suites `auto-*` offline de `apps/api-python` (25 ficheros `test_auto_*`, sin los que exigen PostgreSQL) | **`288 passed`** |
| Costura del contador/ancla (`..._data_gate_seam.py`) | 9 casos |
| Costura del cableado (`..._data_gate_wiring_seam.py`) | 10 casos |
| Costura de la rampa (`..._recovery_seam.py`) | 14 casos |
| Costura del fallback de régimen (`..._regime_fallback_seam.py`, nueva) | 7 casos |
| Matriz de mutaciones **completa** (`M1…M98`) | **`98/98`** muerden; `0` en `NADA`; árbol intacto |
| Delta simétrico (tests de `HEAD` contra el código de la fase) | **1 rojo declarado** (ver abajo) |
| CI del PR de auditoría (ref de la rama, 6 runs) | **14/14 `SUCCESS`** |

**Delta simétrico, declarado.** Se corrieron las versiones de `HEAD` (paso 4) de los ficheros de test
**modificados** contra el código de la fase: **1 rojo**, y es exactamente el cambio de contrato de este
paso — `test_degraded_stops_using_the_confidence_but_keeps_the_protection`, que afirmaba
`confidence=None` entrante en `DEGRADED`. La fase pasa a entregar la confianza como **evidencia medida**
y a retirar solo su **uso** (`shrink=False`): el reparto resultante es el mismo (histórico) y la banda
deja de ocultarse. Ningún otro test de `HEAD` se rompe, así que no hay regresión oculta. (El otro rojo
histórico admisible —el sello de política— se consumió en el **paso 4**, cuando `ADAPTIVE_POLICY_VERSION`
subió a `auto13-v1`.)

**Límites de verificación, declarados.** El bloque offline **completo** de `quality`/`python` del tag no
se pudo reproducir en esta máquina (su recolección incluye suites PG que importan `asyncpg` —ausente— y
el teardown de sesión del conftest de `apps/api-python` exige PostgreSQL): se corrió la selección offline
con la extracción de targets del propio YAML y los únicos errores fueron los de `asyncpg`. **Ese límite
lo cierra la CI del tag, que se mide al sellar** (§ de sellado de este pack, actualizado en el commit de
sello). El PR de auditoría, con los cinco pasos dentro, cerró **14/14 checks en `SUCCESS`**.

## 10. Límites declarados (no silenciosos)

- **El gate no es un permiso**: limita la adaptación; no ejecuta, no pausa dinero, no toca al gobernador.
- **El contador de fallos es de proceso** (se pierde al reiniciar); el ancla durable es el journal, y su
  antigüedad **solo bloquea corroborada**.
- **La retención de `STALE` usa el cooldown**: con `min_pause_cycles <= 1` no habría mecanismo y el hueco
  se declara en el log (inalcanzable con la política de la casa, `= 3`).
- **La rampa nunca ensancha ni inventa**: `min` con el reparto, suelo `0.25`, subida **solo** por
  evidencia medida; sin fechas legibles la rampa no sube y lo declara.
- **El gate no se persiste**: es una lectura del tick. Persistirlo (y el reparto por celda de régimen)
  queda declarado para `AUTO-14`.
- **Sin backfill** y **sin migración** (head `044_auto_cycle_trace`); `governor.json` sigue sin trackear.
- **Sin UI** para `AUTO-7`…`AUTO-13`: todo esto es observable por el journal y los logs del tick, no por
  una pantalla.

## 11. Freeze respetado

- **No se toca**: el sello de `V2.53`; `auto_adaptive_journal.py` (el contrato durable de `AUTO-11` queda
  byte a byte igual: la decisión ratificada nº3 se resolvió **en contra** de tocar el contrato);
  `yahoo_circuit_breaker.py`; `ADAPTIVE_ADVERSE_REGIMES`; los umbrales de rotación
  (`min_pause_cycles`, win rate, profit factor) — el lever de `STALE` es el **dato** de entrada
  (`paused_cycles`), no el umbral —; el gobernador; la tabla `decision_journal_entries` y su índice; el
  esquema. Sin SHORT. Sin `prettier` para `*.md`.
- **El flag Adaptive sigue OFF por defecto**: con OFF el camino de producción es byte-idéntico y esta
  fase **no se ejecuta** hasta un flag explícito.
