# Audit-pack `AUTO-12` Confidence + calidad estadística — `1.78.0-beta` (2026-09-23)

**Fase:** `V2.53` · **Rótulo:** `AUTO-12` · **Bump:** `1.77.0-beta` → **`1.78.0-beta`** · **Tag:**
`v2.53-beta` → `a6655e6e` · **Release tag CI** `35836248169` **GREEN** (`10 success` + `1 skipped`
—`playwright` opt-in—, `check-runs` `27 success` + `1 skipped`, job `python` del tag
**`2459 passed / 35 skipped`** con `ruff` `All checks passed!`, `import-linter` `4 kept, 0 broken` y
`mypy` `0` errores en `497` ficheros; los otros cuatro workflows del tag —`Python CI`, `Frontend CI`,
`Optimize lab`, `Fase 2 scientific`— también en **verde**). **Fase anterior:** `V2.52` / `AUTO-11`
(tag `v2.52-beta` → `71c97880`, `Release tag CI` `35827266670` **GREEN**, `check-runs` `27 success` +
`1 skipped`, job `python` del tag **`2409 passed / 35 skipped`**: la fase suma **+50** exactos).

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva,
sin cambio de contrato de API ni de DTO, **sin clave nueva en el nivel superior del payload del journal**
(la confianza añade cuatro campos **dentro de las filas de `healthByStrategy`**, §6). El gobernador y
su evidencia quedan **intactos**. Adaptive **sigue siendo recomendador read-only**: lo único que cambia es
**cuánto pesa** su recomendación cuando la evidencia es fina.

---

## 0. Resumen: qué instala esta pasada

`AUTO-8`…`AUTO-11` dejaron el reparto del riesgo proporcional a la expectancy **sin ponderar por tamaño
de muestra real**. El gate era **binario** (`decisive`, `trades >= min_trades`): dentro de él, `N=12`
pesaba **igual** que `N=180`. Y no había lectura de **recencia**: con una sola ventana agregada,
`LONG +0.21R` con `RECENT −0.15R` (una estrategia que ha dejado de funcionar) era **invisible**.

Esta pasada añade la capa de **confianza estadística** sin tocar ni el esquema ni la autoridad:

1. **Una lectura de confianza pura** (`auto_adaptive_confidence.py`): muestra **bruta** frente a muestra
   **efectiva** (la que sostiene el número), completitud de medición **compuesta**, cobertura de
   riesgo/coste/régimen, dos ventanas (`recent`/`long`) y dos veredictos declarados (`decay`,
   `confidence`).
2. **Eje de recencia honesto** (aditivo, sin migración): el instante real del fill entra al dominio
   (`created_at`) y el ciclo declara su `closedAt` (el **último** fill); sin fechas legibles la ventana
   reciente **se declara** en vez de inventarse.
3. **Shrinkage por muestra** en el reparto: el peso se encoge por `n/(n+k)` **solo** sobre edges
   decisorios positivos, se normaliza como siempre y nunca deja a nadie en 0. Con el sello de política
   nuevo (`auto12-v1`).
4. **Cobertura de la sonda ampliada** (`M60…M71`, 12 etiquetas nuevas) y la trampa de `M39` (`V2.52`)
   usada como gate explícito: **ninguna etiqueta puede devolver `NADA`**.

Superficie nueva: `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_confidence.py`.
Superficie tocada: `auto_adaptive.py` (reparto, salud y evidencia), `sim_durable_store.py`
(`created_at` aditivo), `auto_self_evaluation_feed.py` (`closedAt` + costura de confianza) y el worker
(`auto_simulation_worker.py`, una lectura por tick).

## 1. El invariante: **ninguna recomendación pesa más de lo que su evidencia sostiene**

> Una muestra fina se **declara** (`confidence`), no se castiga a ciegas; una mejora reciente que
> contradice el histórico se **declara** (`decay`), no se convierte en pausa automática. Adaptive sigue
> siendo **read-only**: la confianza modula el **reparto** (multiplicador en `[0, 1]`), nunca la
> autoridad de ejecución.

Es la extensión natural del invariante de la línea (*medir o declarar, nunca inventar*) al **peso** de la
evidencia: `AUTO-9` cerró *"¿cuánto vale?"*, `AUTO-10` *"¿de qué ciclo?"*, `AUTO-11` *"¿dónde vive su
memoria?"* y `AUTO-12` cierra *"¿cuánto puedo creérmelo?"*.

**Dos corolarios que se prueban con test, no se prometen:**

- **Ausencia de dato ≠ dato malo.** Una estrategia con edge decisorio conserva el `unknown_multiplier`
  neutral (1.0): la confianza fina **solo** reduce el peso de un edge **medido**. Si no hay evidencia de
  que competir, no hay castigo que aplicar.
- **`UNKNOWN` nunca premia.** Un `decay` que no se pudo leer (sin instantes, o con la ventana reciente
  por debajo del mínimo) pone un **techo** de `MEDIUM` a la confianza en lugar de pasar por bueno.

## 2. La muestra: `sample_size` frente a `effective_n`

El defecto concreto que el audit §14 señalaba: `StrategySelfEvaluation.trades` cuenta **ciclos**, pero
`expectancy_r` promedia **solo los ciclos con R medido** (`r_multiple is not None`, es decir con reserva
de entrada con `reserved_risk > 0`). Publicar `trades` como "tamaño de muestra" **afirma** una base que
el número no tiene.

`effective_n` es ese denominador real y es la muestra que **alimenta la banda de confianza**. El test lo
fija en su forma más incómoda: **40 ciclos con 4 medidos ⇒ `sample_size = 40`, `effective_n = 4`,
`risk_coverage = 0.1`, banda `LOW` y nota `ADAPTIVE_CONFIDENCE_THIN_SAMPLE`**. La sonda lo muta (`M60`) y
**dos** tests se ponen rojos.

**Completitud compuesta.** `measurement_completeness` **no** se hereda de un solo eje: es
`combine(r_measurement, net_r_measurement, pnl_coverage)`. Sin coste medido, el R **neto** es `UNKNOWN` y
la completitud **no** puede ser `COMPLETE` (`M64`). `risk_coverage`, `cost_coverage` y `regime_coverage`
se publican por separado porque **no son el mismo hueco**: no medir el denominador de R, no medir el
coste y no declarar el régimen son tres fallos distintos de la misma evidencia. `M65` finge la cobertura
de coste sobre la muestra bruta y el test lo caza.

## 3. El eje de recencia, y por qué es aditivo

**El problema medido en la Auditoría 2** fue una cronología **fingida**: ordenar por posición de lista
hace que la "ventana reciente" sea la que el llamante puso la última. `AUTO-12` no repite eso:

- `SimFillFinanceContext` gana `created_at` (**aditivo**, la columna PG ya existía ⇒ **sin migración**).
  El store PG lo proyecta; el doble `InMemory` lo acepta y **declara** en su contrato que su orden es
  por `execution_id`, no por cronología.
- `cycles_from_fills` añade `closedAt` = instante del **último** fill del ciclo. Un **ciclo anónimo**
  (sin `cycle_id`) **no reclama** instante: sin frontera de cierre no hay nada que afirmar. Un fill sin
  fecha legible **no borra** el cierre medible de los demás.
- `build_adaptive_confidence` ordena por **instante parseado** con el no-parseable **al final y
  declarado** (`ADAPTIVE_CONFIDENCE_RECENT_UNDATED`). Sin instantes legibles ⇒ `recent_available = False`
  y `decay = UNKNOWN`; la ventana **long** sí se mide (no necesita fechas) y se publica.
- **AUTO-7 queda byte-idéntico**: sin `created_at`, la tupla de ciclos es exactamente la histórica
  (ninguna fila tiene `closedAt`) y el informe es **igual** con y sin instantes (test de igualdad de
  `as_dict()`).

Las mutaciones acompañan cada frontera: `M66` (orden por llegada) rompe la invariancia al orden y el
recorte por instante; `M67` (recencia inventada) rompe la declaración del hueco; `M63` (fila sin
instante silenciada) rompe la declaración del orden no probado; `M70` (cierre por el **primer** fill)
rompe la fecha del resultado.

## 4. `decay` y `confidence`: dos veredictos declarados

**`decay`** (con ambas ventanas medidas, `effective_n ≥ min_trades` y `long > 0`): `recent ≥ long · 0.75`
⇒ `NONE`; `recent < long · 0.75` y `recent ≥ 0` ⇒ `MILD`; `recent < 0` ⇒ `SEVERE`. En cualquier otro
caso ⇒ `UNKNOWN` **declarado** (y entonces `recent_insufficient` o `recent_unavailable` en `notes`).
`M61` (el caso negativo deja de ser `SEVERE`) es exactamente el escenario del audit: la estrategia que ha
dejado de funcionar vuelve a leerse sana.

**`confidence`**: base por `sample_quality_from_n(effective_n)` (`useful`/`developing` ⇒ HIGH,
`preliminary` ⇒ MEDIUM, `insufficient` ⇒ LOW), y después tres ajustes **en orden**: completitud no
`COMPLETE` baja un nivel (`UNKNOWN` ⇒ LOW), `decay == SEVERE` baja un nivel, y `decay == UNKNOWN` pone
**techo** en `MEDIUM`. `M62` quita el techo y el test del caso ancho-sin-instancias (120 ciclos medidos,
sin fechas ⇒ `MEDIUM`, no `HIGH`) se pone rojo: **el techo no es decorativo**.

**La política sigue mandando.** El umbral de muestra mínima que autoriza a concluir `decay`
(`min_trades`) y los parámetros del encogimiento son **política versionada** (`AdaptivePolicy`), no
constantes sueltas: `ADAPTIVE_CONFIDENCE_PRIOR_DEFAULT = 20.0` y
`ADAPTIVE_SEVERE_DECAY_FACTOR_DEFAULT = 0.5`. Un test fija que cambiar el prior cambia el reparto **sin
tocar la evidencia**.

## 5. El reparto: encoger por muestra (y no ensanchar nada)

`recommend_allocation(..., confidence=None)` y `build_adaptive_plan(..., confidence=None)`:

- **Sin `confidence` el plan es byte-idéntico al histórico.** El test lo fija con el payload completo
  (`a: 1.0, b: 0.5, c: 1.0`) comparando la llamada sin el argumento con `confidence=None`. Es el mismo
  patrón de `AUTO-9` ("las celdas solas no mueven el reparto"): el eje nuevo **entra por parámetro**.
- **Con `confidence`**, `w' = w · n/(n + k)` con `k = prior` (por defecto **20**), aplicado **solo** a las
  estrategias **decisorias con expectancy positiva**. Si `decay == SEVERE`, factor adicional
  `severe_decay_factor` (por defecto **0.5**). Después, la normalización **de siempre**
  (`(w'/Σw') · count`) y `_clamp_unit`.
- **El caso del audit §25, medido de punta a punta**: con `C +3R/N=180`, `A +2R/N=12` y `B +1R/N=180`,
  sin confianza `A` empata en el **techo** con `C`; con confianza, `A` **pierde el peso pleno**
  (`multiplier_A < 1.0`) y `B` pasa por delante, con **todos** los multiplicadores en `(0, 1]`. La
  estrategia fina **conserva** presencia: encoger es **redistribuir**, no eliminar (test explícito del
  suelo > 0). `M68` neutraliza el prior y **tres** tests se ponen rojos; `M69` neutraliza el descuento
  por deterioro y muerde el suyo.
- **La confianza no crea pausas.** Un test fija que la **rotación** es `byte-idéntica` con y sin
  confianza, incluso con `decay SEVERE`: el deterioro se declara y modula el reparto, pero **no** es un
  motivo de pausa nuevo (`AUTO-13` decidirá el recovery gradual, que es otra cosa).
- **`ADAPTIVE_POLICY_VERSION = "auto12-v1"`**: cambia la regla de asignación ⇒ sello nuevo obligatorio.
  El test del sello se actualiza **con nombre** (`..._seals_the_auto12_evidence_contract`) y es el
  **único** rojo que aparece al correr los ficheros de test de `HEAD` contra el código de la fase.

## 6. Cableado: una lectura por tick, cero I/O nuevo

`_v2_build_adaptive_plan` construye la confianza con `build_adaptive_confidence_from_fills` sobre los
**mismos** `fills` y `cycle_risk` que ya leyó para el informe. **Medido con un store que cuenta
llamadas**: la lectura por versión ocurre **una** vez (`store.calls == ["orb-1"]`). Si
`confidence.recent_available` es `False`, el worker registra un `warning` con los huecos (no finge
ventana); si la lectura de fills revienta, el plan es `None` —**fail-closed declarado**, comportamiento
histórico— y el `error` queda con nombre. `M71` desconecta la confianza del plan (el cálculo se paga y el
reparto publica el histórico) y la costura se pone roja con nombre.

**La evidencia viaja sin clave nueva en el payload.** `StrategyHealth` gana `confidence`,
`recent_expectancy_r`, `long_expectancy_r` y `decay`; `evidence_for` los publica y el journal de `AUTO-11`
los proyecta **dentro de las filas de `healthByStrategy`** (contrato **sin tocar**, sin migración,
`readOnly` conservado). Precisión para el auditor: **en el nivel superior del payload no hay ninguna
clave nueva** — el `event_type`, el `decision_id` y las claves de la entrada son los de `AUTO-11`; lo que
cambia es la fila de salud, que gana cuatro campos (con `null` cuando el llamante **no** aportó la
confianza: la ausencia se **declara**, no se omite ni se disfraza). La pieza que `AUTO-11` dejó preparada
(`build_adaptive_recommendation_entry`) es exactamente lo que permite que `AUTO-12` sea **aditivo**.

## 7. Matriz de mutaciones (M60…M71): 12/12 muerden

| Etiqueta | Defecto que inyecta | Rojos |
| --- | --- | --- |
| `M60` | `effective_n` cuenta los ciclos **sin R** | 2 (`test_the_sample_that_sustains_the_number_is_the_measured_one`, `test_a_whole_window_of_unmeasured_risk_is_declared_unknown_not_zero`) |
| `M61` | el deterioro severo deja de declararse `SEVERE` | 2 |
| `M62` | `decay UNKNOWN` deja de poner techo a la confianza | 1 |
| `M63` | las filas sin instante dejan de declararse | 1 |
| `M64` | la completitud se declara `COMPLETE` sin combinar | 2 |
| `M65` | la cobertura de coste se afirma sobre la muestra bruta | 1 |
| `M66` | las ventanas se recortan en el orden de **entrada** | 2 |
| `M67` | sin instantes legibles se construye igual la ventana reciente | 2 |
| `M68` | el prior del encogimiento cae a `0` | 3 |
| `M69` | el factor de `decay SEVERE` deja de aplicarse | 1 |
| `M70` | el cierre toma el **primer** fill del ciclo | 2 |
| `M71` | el worker construye la confianza y no la pasa al plan | 1 |

Gate de la lista: **ninguna etiqueta devuelve `NADA`** y la matriz **completa** se corre para comprobarlo
(la trampa de `M39` en `V2.52`: una etiqueta que dejó de morder y **afirmaba** cobertura). La sonda
falla si un fragmento desaparece o aparece más de una vez, y restaura **byte a byte** dejando la huella
de `git status` **idéntica** antes y después.

Resultado de la corrida completa: **`medidas: 71/71`, `0` etiquetas en `NADA`**, árbol intacto.

`AUTO-12` **realineó** una etiqueta heredada sin cambiar su intención: `M33` (worker sin denominador)
apuntaba a la llamada *inline* `build_auto_self_evaluation(..., cycle_risk=await self._v2_cycle_risk(fills))`,
que dejó de existir al medir el riesgo por ciclo **una sola vez** en una local compartida por el informe y
la confianza. La sonda se reapuntó a esa local (`cycle_risk = await self._v2_cycle_risk(fills)` →
`cycle_risk = None`) y vuelve a morder (3 rojos, incluido `test_the_worker_measures_the_r_from_the_cycle_reservation`).
Se declara explícitamente porque una sonda desalineada **afirma** cobertura que no tiene: es exactamente el
fallo que el gate de `M39` existe para impedir.

## 8. Verificación (lo medido, y lo que no se pudo medir aquí)

- **Delta simétrico, fichero a fichero contra `HEAD`** (nunca restando totales de fases anteriores):

| Fichero | `HEAD` | Fase | Delta |
| --- | --- | --- | --- |
| `packages/py/analytics/tests/test_auto_adaptive_confidence.py` (nuevo) | — | 21 | **+21** |
| `apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py` (nuevo) | — | 9 | **+9** |
| `packages/py/analytics/tests/test_auto_adaptive.py` | 44 | 55 | **+11** |
| `packages/py/application/tests/test_auto_self_evaluation_feed.py` | 13 | 22 | **+9** |
| **Total del área** | 57 | 107 | **+50** |

- **Los dos ficheros modificados, en su versión de `HEAD`, contra el código de la fase**: **57 tests, 56
  pasan y 1 rojo nombrado** — `test_the_policy_version_seals_the_auto9_evidence_contract`, cuya
  expectativa la fase actualiza **con nombre** a `..._auto12_evidence_contract` porque el contrato de
  asignación cambió. Ningún otro rojo: **no hay regresión oculta**.
- **Suites del área, con la fase**: `packages/py/analytics/tests` **1011 passed**;
  `packages/py/application/tests` **1876 passed / 5 errors** —los 5 son
  `ModuleNotFoundError: No module named 'asyncpg'` en suites **PG** (`test_instrument_lifecycle_db.py`,
  `test_research_observatory.py`, `test_research_trials_db.py`), **pre-existentes** y sin relación con
  esta fase: dependen del driver de PostgreSQL, que no está instalado en esta máquina—; y el bloque
  AUTO completo (analytics + feed + journal + recovery + cycle_risk + applied_fills + unit_of_work +
  métricas observadas + las 5 costuras + worker) **1178 passed / 0 rojos**.
- **Compuertas del CI, corridas con la fase** (comandos del workflow, no rutas sueltas):
  `uv run ruff check packages/py apps/api-python --config pyproject.toml` ⇒ **`All checks passed!`**;
  `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src
  packages/py/application/src apps/api-python/src --follow-imports=silent` ⇒ **`Success: no issues found
  in 497 source files`**; `uv run lint-imports --config packages/py/.importlinter` ⇒ **`4 kept, 0 broken`**.
- **La matriz de mutaciones completa** (§7) con el árbol **intacto**.
- **La CI del tag, medida y no supuesta.** `v2.53-beta` → `a6655e6e`: `Release tag CI`
  [`35836248169`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35836248169) **GREEN** con **`10
  success` + `1 skipped`** (`playwright` opt-in) en `8m31s`, `check-runs` **`27 success` + `1 skipped`** —
  la **misma forma** que `v2.52-beta`—, y el job `python (ruff/imports/mypy/pytest offline)` con
  **`2459 passed / 35 skipped`** en `1m45s` (frente a los `2409 passed / 35 skipped` del tag anterior:
  **+50**, exactamente el delta declarado en la tabla de arriba). Los otros cuatro workflows del tag
  (`Python CI`, `Frontend CI`, `Optimize lab`, `Fase 2 scientific`) también en **verde**, igual que sus
  homólogos en `main`.
- **Límite declarado de la verificación local:** el bloque offline **completo** de `quality` / `python`
  del tag **no se pudo reproducir** en esta máquina porque su recolección incluye suites PG que
  importan `asyncpg` (ausente) y porque el teardown de sesión de `apps/api-python/tests/conftest.py`
  (`purge_all_residuals`) exige PostgreSQL; el script de extracción del YAML
  (`%TEMP%\run_offline_ci.py`, fuera del repo) sí se usó para correr la selección offline, y los únicos
  errores fueron los de `asyncpg`. Ese límite **lo cierra CI**, que es donde se midió el bloque completo:
  las cifras de la CI del tag de arriba son las **suyas**, no una extrapolación de las locales.

## 9. Límites declarados (no silenciosos)

- **`confidence` no es un permiso:** es evidencia read-only; la autoridad es el motor determinista y el
  gobernador.
- **Ventanas finitas:** `recent = 30`, `long = 200` (defaults declarados); con menos filas el número es un
  **suelo** (`recent_insufficient`).
- **Sin fechas legibles no hay `decay`:** se declara `recent_unavailable`; no se inventa cronología (y la
  ventana `long` se sigue midiendo, porque no necesita fechas).
- **`effective_n` es la muestra que sostiene el número**, no la bruta: una celda de 40 ciclos con 4
  medidos declara **4**.
- **La confianza no se persiste como estado propio:** viaja en las **filas** de `healthByStrategy` del
  journal de `AUTO-11` (sin clave nueva en el nivel superior del payload y sin migración).
- **El coste del `decay` es `R` bruto**, no neto: el neto sigue siendo el eje **alternativo** de `AUTO-9`
  y exige `net_r_measurement == COMPLETE`, que un coste estimado no garantiza.
- **`AUTO-13` fuera:** Data Gate (`OK/DEGRADED/STALE/BLOCKED`), recovery gradual (`RECOVERING` +
  multiplicadores `0.25→1.0`) y matriz de régimen avanzada.
- **Sin UI** para `AUTO-7`…`AUTO-12` (deuda declarada), **sin migración**, **`governor.json` sin
  trackear**.

## 10. Freeze respetado

`auto_adaptive_journal.py` (contrato de `AUTO-11`) y `auto_adaptive_recovery.py` quedan **byte a byte
iguales**: la confianza viaja por la proyección existente, no por una pieza nueva. No se tocaron umbrales
de rotación, `ADAPTIVE_ADVERSE_REGIMES`, el gobernador ni su evidencia, ni `decision_journal_entries` ni
su índice. El sello de `V2.52` (`v2.52-beta` → `71c97880`) queda quieto.
