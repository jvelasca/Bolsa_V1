# Arranque del auditor — `v2.54-beta` (AUTO-13 · Adaptive Data Gate + recovery gradual)

**Fecha:** 2026-09-23 · **Ref a atacar:** tag **`v2.54-beta`** → **`54a3b86a`** (`1.79.0-beta`) ·
**Pack que manda:** [`audit-pack-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md`](./audit-pack-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md).
Si algo de este arranque contradice al pack, **manda el pack**. El plan de fase (ratificado, con las cuatro
decisiones) es [`plan-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md`](./plan-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md),
y el relevo cerrado [`traspaso-relevo-post-v2.54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md`](./traspaso-relevo-post-v2.54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md).

Las `ruta:línea` de este documento están **verificadas en el árbol el 2026-09-23**. Cada afirmación trae
**el comando exacto** para medirla. Este documento existe para que no gastes presupuesto redisculpiendo lo
ya medido.

**Contexto del sello:** la fase entera viaja en **10 commits** sobre `d08e66e5` (sello de `v2.53-beta`),
en **fast-forward**, sin merge commit. El tag apunta al commit del paquete (`54a3b86a`); después hay **dos
commits de documentación** en `main` (`6ab3c851` sellado con las cifras de CI y `9ac2e0d8` corrigiendo una
cifra de `check-runs`). **Sin migración** (Alembic head sigue en `044_auto_cycle_trace`).

---

## 0. Si solo tienes una hora

1. **§2 — la regla de corroboración** (es *el* diseño de la fase, y su fallo más caro).
2. **§3 — los cuatro efectos del cableado** (¿`OK` es de verdad byte-idéntico? ¿`STALE` reactiva?).
3. **§5 — un régimen ilegible no acusa a nadie** (el hueco del §20 y los tres ejes del §29).
4. **§1 — el invariante**: nada de esto puede convertir «dato incompleto» en «estrategia mala».

---

## 1. El invariante (ataca contra él, no contra el estilo)

**Ninguna estrategia puede ser castigada por una deuda de los datos.** Un dato incompleto se **declara**
(`DataGateStatus`) y **limita la adaptación**; nunca se convierte en «esta estrategia es mala». Una vuelta
de pausa se **gana** con evidencia medida, nunca por el paso del tiempo. Un régimen que no se pudo leer
**no** acusa a nadie.

Los cuatro estados y su efecto **derivado** (no es un campo que pueda divergir: la tabla es la única casa):

| Punto | `ruta:línea` |
| --- | --- |
| Estados `OK/DEGRADED/STALE/BLOCKED` | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py:57` |
| Efectos `ADAPTS/LIMITS/FREEZES/NO_ADAPT` | `auto_adaptive_data_gate.py:62` |
| **Tabla** estado→efecto (`_EFFECT_BY_STATUS`) | `auto_adaptive_data_gate.py:85` |
| Precedencia `BLOCKED > STALE > DEGRADED > OK` | `auto_adaptive_data_gate.py:237` (`assess_data_gate`) |
| Vocabulario de motivos (`notes`) | `auto_adaptive_data_gate.py:94` |
| Política versionada | `auto_adaptive_data_gate.py:69` (`auto13-v1`), `:73`, `:76`, `:81` |

**Preguntas incómodas.**

- ¿Puede publicarse un estado con un efecto **incoherente** (p. ej. `OK` con `NO_ADAPT`)? Si puedes
  construir un `DataGateReading` saltándote `assess_data_gate`, la respuesta es sí: **mídelo**.
- La precedencia dice que el estado grave **absorbe** los motivos menores y los `notes` los acumulan
  **ordenados**? ¿O se pierde un motivo al subir de estado?
- `assess_data_gate` ¿es **orden-invariante**? Pásale los mismos hechos en otro orden y exige identidad.
- **Los umbrales (`3` y `10`) y la cadencia (`60.0`) están declarados, no calibrados.** Eso es una pregunta
  abierta (§9), no un defecto.

---

## 2. Las dos fuentes de verdad del gate y la regla que lo salva del deadlock

**Por qué es lo más caro si falla.** `BLOCKED ⇒ adaptive = None ⇒ no se escribe ⇒ el journal envejece ⇒
BLOCKED`. Sin nada que rompa ese círculo, la adaptación no se recupera **nunca** con Adaptive OFF o tras una
pausa larga.

| Punto | `ruta:línea` |
| --- | --- |
| Contador de fallos consecutivos del sink | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:748` |
| Se **incrementa** en el `except` | `auto_simulation_worker.py:3424` |
| **Un éxito RESETEA** la racha | `auto_simulation_worker.py:3432` |
| Ancla durable (edad en ciclos, corroborada) | `auto_simulation_worker.py:3369` (`_v2_adaptive_gate_journal_age`) |
| Sink real instrumentado | `auto_simulation_worker.py:3386` (`_v2_journal_adaptive_recommendation`) |
| `last_published_at` (el `asOf` **más nuevo**) | `packages/py/application/src/bolsa_application/auto_adaptive_recovery.py:323`, `:357` |
| Cadencia declarada y conversión a ciclos | `auto_adaptive_data_gate.py:205` (`journal_age_cycles`) |

**Preguntas incómodas.**

- **¿El ancla bloquea sin fallo propio?** **No debe**: `_v2_adaptive_gate_journal_age` devuelve `None` si
  `failures <= 0`. Verifícalo y luego meas la mutación **M76** (si la quitas, los tests deben caer).
- **¿Un éxito intermedio rompe la racha?** Debe (**M75**). Y al resetear, ¿el ancla vuelve a `0`?
- **¿El contador instrumenta algo más que el sink de la recomendación Adaptive?** Si toca otros caminos,
  el «fallo» deja de ser la señal que dice ser.
- **¿Una antigüedad ilegible bloquea?** No debe: `journal_age_cycles = None` se declara
  (`journal_age_unknown`) y **no** bloquea. Suponer juventud o inventar antigüedad son las dos formas de
  romperlo.
- **Ventana declarada:** el contador es **de proceso** (se pierde al reiniciar). Entre el reinicio y el
  primer fallo, el gate no puede ver una racha. ¿Cuánto dura esa ventana en producción y qué cuesta? (**§9**).

---

## 3. El cableado: cuatro efectos, cero I/O nuevo

| Punto | `ruta:línea` |
| --- | --- |
| Compone los hechos **ya medidos** del tick | `auto_simulation_worker.py:3273` (`_v2_adaptive_data_gate`) |
| Política y `regime_available` | `auto_simulation_worker.py:3249`, `:3259` |
| Construcción del plan (con `gate=`) | `auto_simulation_worker.py:3036` (`_v2_build_adaptive_plan`) |
| `shrink=` (el §29: medir ≠ usar) | `auto_simulation_worker.py:3130` |
| Recorte de ciclos que ENTRAN en la rotación | `auto_simulation_worker.py:3238` (`_v2_next_paused_cycles`) |

**Lo que cada efecto debe cumplir.**

- **`OK` (`ADAPTS`)** ⇒ mismos argumentos y plan **byte-idéntico** a `v2.53`. Hay un test que lo afirma
  comparando bytes; comprueba que **no** es vacío.
- **`DEGRADED` (`LIMITS`)** ⇒ `shrink=False`: el reparto **deja de usar** la confianza de `AUTO-12` y cae
  a su eje histórico, pero la banda **medida** se sigue publicando y la **protección entera** se conserva
  (pausas vivas, cooldowns y las pausas **nuevas** por salud).
- **`STALE` (`FREEZES`)** ⇒ además **ninguna reactivación nueva** (solo en el worker: el contador que
  **entra** a `recommend_rotation` se recorta; el **real** sigue creciendo y los **umbrales no se tocan**).
- **`BLOCKED` (`NO_ADAPT`)** ⇒ `adaptive = None` declarado y **sin fila de journal**; el contador de
  cooldown **no avanza** ese tick (nada se reactiva por olvido).

**Preguntas incómodas.**

- **¿Hay I/O nuevo?** No debe. Los tests lo miden con un store que **cuenta llamadas**; verifícalo también
  con el flag **OFF**.
- **`STALE`: ¿se congela también una pausa NUEVA por salud?** **No debe**: el material que entra en la
  rotación es el mismo; solo se recorta el contador de las pausas vivas. Hay test para las dos mitades.
- **`BLOCKED`: ¿deja el cooldown congelado para siempre?** Es consecuencia **declarada** y correcta (nada
  se reactiva por olvido), pero es la costura donde un olvido se vuelve permanente: el gate debe reabrirse
  por la regla de corroboración del §2.
- **La completitud del gate son los ejes que Adaptive EXIGE** (resultados + riesgo), **no** el
  `measurement_completeness` de la confianza (que combina el net-R **opcional**). Si se cambia, cualquier
  despliegue sin coste medido queda `DEGRADED` y se apaga `AUTO-12` (**M82**).
- **`regime_available` acepta los dos ejes** (canónico `TREND_UP` y operativo `BULL_TREND`) y declara
  ausencia con `None`, `""`, `UNKNOWN` y `RISK_OFF` (**M81**). ¿Se te ocurre un quinto valor que debería
  declarar hueco y hoy se cuele como disponible?

---

## 4. La rampa: se sube por evidencia, no por reloj

| Punto | `ruta:línea` |
| --- | --- |
| Sellos de la fase | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py:143` (`auto13-v1`) |
| Estados operativos | `auto_adaptive.py:208` (`active`/`paused`/`recovering`) |
| Escalones y paso | `auto_adaptive.py:216` (`0.25/0.50/0.75/1.00`), `:219` (`3` ciclos) |
| Lectura pura de la rampa | `auto_adaptive.py:527` (`recovery_reading`) |
| Estado en el plan | `auto_adaptive.py:560` (`AdaptivePlan`, con `operational_states` y `recovery`) |
| Techo (`m_final = min(reparto, escalón)`) | `auto_adaptive.py:826` (`recommend_allocation`) |
| Evidencia medida (mismos fills del tick) | `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py:319` |
| R del ciclo (una sola regla en el repo) | `auto_self_evaluation_feed.py:257` (`_positive_cycles_after`), `:283` |
| Corte **probado** (siembra durable) | `auto_adaptive_recovery.py:258` (`_reactivations`), `:327` |
| La transición se fecha en el tick | `auto_simulation_worker.py:759`, `:3483` |

**Preguntas incómodas.**

- **¿La rampa puede ensanchar?** **No**: es un **techo** (`min`). Si pasa a `max`, es **M84**.
- **¿Puede llegar a `0`?** **No**: suelo `0.25` (es una reincorporación, no una pausa encubierta sin pasar
  por la rotación). **M85**.
- **¿Sube por tiempo?** **No**: solo con **ciclos posteriores al corte** con expectancy medida positiva y
  sin deterioro grave. **M83** y **M90** (evidencia anterior al corte).
- **¿Una pausa viva publica su escalón?** **No debe** (la protección manda); el escalón se descarta. **M86**.
- **¿Se te ocurre un tick con evidencia suficiente para** acelerar **la rampa de más?** La evidencia son
  los ciclos del propio tick: un tick con muy pocos ciclos, ¿sube un escalón igual? Es la pregunta abierta
  **§9.3** (¿debería exigir un mínimo, como el `min_trades` de `AUTO-12`?).
- **¿El lector durable puede inventar un corte?** **No**: exige haber visto la **pausa** que lo precede; un
  turno ilegible corta la búsqueda. **M88**, **M89**.
- **`RECOVERING` no es un modo de la rotación**: es estado **operativo** derivado. Si alguien conecta la
  rampa a la decisión de rotación, es otra fase con su pack.

---

## 5. §20 (el hueco de régimen) y §29 (medir ≠ usar)

| Punto | `ruta:línea` |
| --- | --- |
| El hueco del cruce, con su **motivo** | `auto_adaptive.py:317`, `:323` (`StrategyHealth.regime_undetermined`) |
| Se **deriva** de la evaluación de la fila | `auto_adaptive.py:334` (`from_evaluation`), `:360` |
| Se publica en **campo propio** del plan | `auto_adaptive.py:582` (`AdaptivePlan.regime_undetermined`), `:657` (`as_dict`) |
| Se **deriva** de la salud (no se recalcula) | `auto_adaptive.py:1002` (`build_adaptive_plan`) |
| El tick lo **declara** con su fallback | `auto_simulation_worker.py:3158`, `:3163`, `:3164` |
| Rama adversa de la rotación | `auto_adaptive.py:708` (`recommend_rotation`) |
| `shrink` / `shrinkage` (la frontera medir/usar) | `auto_adaptive.py:925`, `:588` (aplicado en `:995`/`:997`) |

**Preguntas incómodas.**

- **¿Un régimen ilegible arma la rama adversa?** **No debe**. Y el test trae el **control** con el adverso
  **real** del tick (`BEAR_TREND` operativo → `TREND_DOWN` de mercado): sin ese control, «no se pausa»
  también pasaría con una rotación **muerta**. Comprueba que el control **afirma** la traducción.
- **¿Se asume `RANGE` o se hereda el régimen de otro ciclo en algún camino?** Si lo encuentras, es un
  hallazgo de primera.
- **¿El hueco se publica ordenado por versión?** Debe: la reproducibilidad no puede depender del orden de
  las filas.
- **¿`regime_undetermined` se recalcula en vez de derivarse?** Si puede **divergir** del cruce que usó la
  rotación, el operador lee una explicación que no es la que decidió. **M95**, **M96**.
- **§29: ¿el gate apaga el USO sin borrar el HECHO?** Con `shrink=False` la banda medida **sigue
  publicándose**. `ACTIVE` + datos `DEGRADED` + calidad `LOW` debe ser un estado **legal** y legible entero.
  **M98**: si el encogimiento no se puede apagar, los tres ejes se mezclan.
- **¿Los tres ejes comparten algún campo?** No deben. Hay un test que lo afirma en las dos direcciones.

---

## 6. Mutaciones que YA se midieron (no las redisculpas)

`apps/api-python/scripts/v2_44_mutation_audit.py` — **27 etiquetas nuevas** en esta fase (`M72…M98`), y la
matriz **completa** (`M1…M98`) medida **sobre el commit sellado**:

```
98/98 medidas · 0 en NADA · 98 restauraciones byte a byte · huella git intacta
```

Lo que cubren las nuevas (por familia): efecto invertido (`M72`), `OK` por defecto (`M73`), ancla que no
bloquea (`M74`), contador sin reset (`M75`), ancla sin corroborar (`M76`), cadencia ignorada (`M77`),
`BLOCKED` adaptando (`M78`), `STALE` reactivando (`M79`), `DEGRADED` repartiendo con la confianza (`M80`),
régimen siempre disponible (`M81`), completitud por el eje opcional (`M82`), rampa por tiempo (`M83`), rampa
que ensancha (`M84`), rampa que llega a `0` (`M85`), pausa que publica su rampa (`M86`), recuperación no
derivada (`M87`), corte sin probar (`M88`), ventana ilegible declarada disponible (`M89`), evidencia
anterior al corte (`M90`), rampa no cableada (`M91`), memoria no sembrada (`M92`), transición sin fechar
(`M93`), régimen ilegible tratado como adverso (`M94`), motivo del hueco perdido (`M95`), hueco que no
viaja al plan (`M96`), fallback no declarado (`M97`), encogimiento inapagable (`M98`).

**Si encuentras una forma de romper el invariante que NO esté en esa tabla, ese sí es un hallazgo.**

Dos notas de método que **no** son hallazgos (están declaradas en el pack):

- **`M21`** se re-ancló al renombrar `weight → share` (lo exigió `mypy`) y **`M71`** al desambiguarse el
  cableado. Una sonda desalineada **afirma** cobertura que no tiene; por eso se declaran.
- **`exit=0` de la sonda NO prueba «0 en `NADA`»**: una mutación no detectada solo se imprime. Lo que sí
  garantiza es «ninguna etiqueta sin fragmento» y «huella intacta»; el conteo hay que **leerlo**.

---

## 7. Comandos exactos (no los reinventes)

```bash
# Estático (los de CI, no rutas sueltas)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió: diff VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Sin migración: el head no se movió
uv run alembic -c packages/py/infrastructure/alembic.ini heads      # 044_auto_cycle_trace

# El tramo de la fase (unit + las cuatro costuras): 202 passed
uv run pytest packages/py/analytics/tests/test_auto_adaptive.py \
              packages/py/analytics/tests/test_auto_adaptive_data_gate.py \
              packages/py/application/tests/test_auto_adaptive_recovery.py \
              packages/py/application/tests/test_auto_self_evaluation_feed.py \
              apps/api-python/tests/test_auto_v54_auto13_data_gate_seam.py \
              apps/api-python/tests/test_auto_v54_auto13_data_gate_wiring_seam.py \
              apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py \
              apps/api-python/tests/test_auto_v54_auto13_regime_fallback_seam.py -q

# La matriz de mutaciones (mide, restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
```

**Al correr la matriz:** interrumpir la tarea **no mata** al hijo en Python, y el script reescribe ficheros
en bucle. Comprueba procesos y `git status` **antes** de dar la corrida por cerrada; si queda un mutante,
restaura con `git checkout -- <fichero>` y verifica `git hash-object` contra `HEAD:<fichero>`.

---

## 8. Qué NO es un hallazgo (declarado de antemano)

- Que el **flag Adaptive siga OFF por defecto**: con OFF el camino de producción es **byte-idéntico** a
  `v2.53` y ni el gate ni la rampa se ejecutan. Es una decisión, no un olvido.
- Que el **gate no se persista**: es una lectura del tick, **sin migración** por decisión de fase. El
  contador de fallos es **de proceso** (se pierde al reiniciar) y el ancla durable solo bloquea
  **corroborada**. Persistirlo queda declarado para `AUTO-14`.
- Que la retención de `STALE` use el **cooldown**: con `min_pause_cycles <= 1` no habría mecanismo (la
  política de la casa es `= 3`, inalcanzable). El hueco se declararía en el log si se tocara.
- Que la rampa **nunca** ensanche ni invente: `min` con el reparto, suelo `0.25`, subida solo por evidencia
  medida; sin fechas legibles no sube y lo declara.
- Que **sin UI** para `AUTO-7`…`AUTO-13`: todo esto es observable por el journal y los logs del tick.
- Las cifras del **§9 del pack** (tramo `202 passed`, bloque offline `288 passed`) son la selección
  **medida en local**; la CI del tag mide **todo** (`2568 passed / 35 skipped`, **+109** sobre `v2.53`).
- El **rojo nombrado** del delta simétrico
  (`test_degraded_stops_using_the_confidence_but_keeps_the_protection`): es **exactamente** el cambio
  declarado del §29 (la fase entrega la confianza como **evidencia medida** y retira solo su **uso**; el
  reparto resultante es el mismo). Ningún otro test de `HEAD` se rompe.
- Que `auto_adaptive_journal.py` quede **byte a byte igual**: la decisión ratificada nº3 se resolvió **en
  contra** de tocar el contrato durable de `AUTO-11`.
- Los rojos de las suites **PG** en local (sin `asyncpg` ni PostgreSQL): están en el `--ignore` de la CI
  por diseño.

---

## 9. Cinco preguntas abiertas que el autor NO cierra

1. **¿Cuánto cuesta la ventana del contador de proceso?** El ancla durable solo bloquea **corroborada**, y
   la corroboración vive en RAM: entre un reinicio y el primer fallo propio, un journal muerto no bloquea.
   ¿Es una ventana aceptable en producción, o exige persistir la racha (`AUTO-14`)?
2. **Los umbrales están declarados, no calibrados.** `sink_failures_stale = 3`, `journal_gap_blocked = 10`
   y `evaluation_cycle_seconds = 60.0` son **elegidos**. ¿Con qué evidencia se sostienen? ¿Debe el gate
   validar que la cadencia declarada coincide con la del tick real, o basta con declararla?
3. **¿La rampa debería exigir un mínimo de ciclos medidas por tick?** Hoy sube con evidencia positiva
   posterior al corte, del **mismo** tick. Un tick con un solo ciclo positivo, ¿debería mover el escalón?
   (Compáralo con `min_trades`/`effective_n` de `AUTO-12`: allí la muestra fina **declara**, no premia.)
4. **¿Un reinicio vuelve a `OK` demasiado fácil?** Si el gate no se persiste, un proceso que arranca con el
   journal muerto y sin fallos propios empieza en `OK`. ¿Es correcto «no acusar sin prueba» o debería el
   arranque **declarar** el estado del gate hasta la primera publicación?
5. **§20: ¿el fallback a la evidencia global es la política correcta de producto?** La rotación decide con
   la fila de la estrategia cuando el cruce no tiene celda decisiva. Es lo declarado y lo medido; la
   pregunta de producto (¿debería **abstenerse** en vez de fallback?) no se cierra aquí.

---

## 10. Lo que **no** debes asumir

- Que un test verde proteja nada: esta línea ya destapó un control **mudo** (el test adverso pasaba un
  régimen que el tick nunca sirve, midiendo un `UNKNOWN` en vez del adverso real). Si un test «no se pausa»,
  exige **el control que sí pausa**.
- Que `98/98` y `0` en `NADA` signifiquen cobertura: significan que **esas 98** mordieron. Una **novena**
  forma de romper el invariante es un hallazgo legítimo.
- Que el `--only` de la sonda filtre etiquetas: se le pasan los rótulos **como argumentos**.
- Que `git show HEAD:<f> > <f>` sea seguro en PowerShell: **fabrica bytes nulos**. Escribe con Python
  **como bytes**.
- Que las cifras del `CHANGELOG` sean la CI: son la selección local; las del tag citan su run.

---

## 11. Formato del hallazgo

```
P0/P1/P2 · afirmación · ruta:línea · comando exacto · salida · ¿ya declarado en §8/§9 o en el §10 del pack?
```

Las cifras del **tag** citan el run de `Release tag CI` que las produjo
([`35857892968`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35857892968)); las locales citan el
comando y su salida. **Ninguna cifra se atribuye a un artefacto que no la produjo.**
