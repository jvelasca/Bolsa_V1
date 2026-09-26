# Auditoría — `v2.69-beta` (`AUTO-22`) · RUN de evidencia PAPER reproducible + UI de evidencia en 3 niveles

> **AsOf:** 2026-09-25 · **Auditado:** `v2.69-beta` · **Base del diff:** `v2.68-beta`
> **Naturaleza:** fase de **instrumentación de la corrida** (no de decisión). **SIN migración**
> (head `046_fill_reference_mid`). **El freeze no se toca** (`auto18-v1` / `auto15-v1`).
> **Redactada por:** el propietario/auditor externo; transcrita al paquete de ingeniería.

## Veredicto

- **V2.69-beta: APROBADA.** A nivel de **infraestructura de evidencia**, la línea se considera
  **cerrada**.
- El cambio arquitectónico importante: ya no se añade otra métrica, sino que la cadena de evidencia se
  convierte en una **ejecución reproducible e inmutable**.

El paso conceptual de la fase:

> de "**podemos calcular estadísticas**" a "**podemos ejecutar una corrida identificable, inmutable,
> reproducible y auditable de toda la cadena AUTO**".

Y con una propiedad fundamental: `material → fingerprint → artifact → bundle → UI`, **sin recalcular
ni inventar resultados por el camino**.

## Estado de los bloques

| Área | Estado |
|---|---|
| Lector único de material PAPER | 🟢 |
| PostgreSQL E2E | 🟢 |
| `AUTO-19A` / `19B` | 🟢 |
| `AUTO-20C` | 🟢 |
| `AUTO-21` | 🟢 |
| `AUTO-22` runner | 🟢 |
| Bundle reproducible | 🟢 |
| Fingerprint | 🟢 |
| Inmutabilidad | 🟢 |
| Fail-closed | 🟢 |
| UI 3 niveles | 🟢 |
| `NO MEDIDO` | 🟢 |
| Allocation freeze | 🟢 |
| Tests | 🟢 |
| Mypy / Ruff / import-linter | 🟢 |
| Mutaciones | 🟢 |
| **PAPER real suficiente** | 🔴 |
| **Evidencia de mercado real** | 🔴 |
| Allocation dinámica | ❌ |
| LIVE AUTO | ❌ |

**Compuertas declaradas:** **3.196** tests Python, **1.331** frontend, **0** errores Ruff, mypy sin
errores en **501** fuentes, import-linter **4/4** y **190/190** mutaciones.

## Observaciones verificadas

| # | Tesis verificada | Veredicto |
|---|---|---|
| 1 | **Lector único**: `auto_paper_material.read_paper_material()` alimenta **a la vez** `paper_cycles_export` y `auto_evidence_run`; un test del audit-pack demuestra que exportador y runner comparten el único lector | 🟢 |
| 2 | `AUTO-20C` y `AUTO-22` **no pueden divergir** en silencio respecto al material (cierra la preocupación seguida desde `v2.62`) | 🟢 |
| 3 | **`AUTO-22` no vuelve a calcular**: **compone** `AUTO-19A/19B` + `AUTO-21`. No reimplementa `P(R>0)`, WFE, correlación, régimen, bootstrap ni intervalos; el test de composición detecta una segunda aritmética | 🟢 |
| 4 | `EvidenceRunBlockedError` **fail-closed** en dos niveles: sin ciclos ⇒ `BLOQUEADO`; con ciclos pero sin R medible ⇒ `BLOQUEADO`. Y `BLOCKED ⇒ NO bundle, NO carpeta, NO JSON parcial` (`exit 2`) | 🟢 |
| 5 | El default **`synthetic_fixture`** elimina el fallo catastrófico "fixture leído como PAPER REAL"; solo el material puede declarar `paper_real`; **M189** ataca el defecto contrario | 🟢 |
| 6 | **La procedencia la declara el material, no el runner**: el proceso no puede decir "yo creo que esto es PAPER"; lee el manifest y usa `materialOrigin` | 🟢 |
| 7 | El **fingerprint** viaja hasta el bundle (`material → fingerprint → artifact → bundle → run.json`), identificando el universo que produjo la corrida | 🟢 |
| 8 | **Inmutabilidad del RUN**: directorio `timestamp + fingerprint` con `exist_ok=False`; si ya existe, NO overwrite (una medición no se pisa) | 🟢 |
| 9 | **UI de tres niveles** (Material / Global+Calibration / Contexto) + cierre `ALLOCATION`; separa "qué datos tengo" de "qué dicen", "en qué contexto" y "qué voy a hacer" | 🟢 |
| 10 | `P(R>0)` y `P(R>0) OOS` se mantienen **separadas**: propiedad de la evidencia declarada vs realización fuera de muestra | 🟢 |
| 11 | **`NO MEDIDO` es un estado del sistema**: `null` ≠ `0` ≠ `false` ≠ `UNKNOWN`; `correlation = null` ⇒ `NO MEDIDO`, nunca `0.0000` (test específico) | 🟢 |
| 12 | **Timeout P3-1 cerrado**: `testTimeout`/`hookTimeout` **por fichero** (20 s) en `core-r-scheduler.test.ts`, sin flag global que esconda problemas; la suite vuelve a verde sin `--testTimeout` | 🟢 |
| 13 | **190/190 mutaciones**: de `187/187` a `190/190`; `M188` (huella), `M189` (origen) y `M190` (bloqueo sin R) **muerden** — el fingerprint no es decorativo, el origen no puede falsificarse, el bloqueo bloquea | 🟢 |

## La paradoja de V2.69 (14)

El nombre de la fase es **"Real PAPER Evidence Run"**, pero el propio audit-pack declara que **la
corrida PAPER real no se ejecuta: está bloqueada por material**. Esto **no es un defecto de código**:

    RUN REAL              → 🟢 infraestructura lista
    DATOS PAPER REALES    → 🔴 todavía no disponibles

`AUTO-22` está preparado, pero **todavía no ha observado el mercado PAPER real**.

## Consecuencia y siguiente paso (15–19)

Ya no toca preguntar "¿qué métricas faltan?": están `P(R>0)`, `P(R>0) OOS`, WFE, intervalos,
effective-N, correlación, régimen, material, fingerprint y provenance, con runner reproducible, bundle,
inmutabilidad y UI. **No se añaden más métricas importantes antes del primer dataset real.**

El cuello de botella es **MATERIAL**:

    CÓDIGO / TESTS / INFRAESTRUCTURA / RUNNER AUTO-22   → 🟢
    DATOS PAPER                                          → 🔴

Y hay una condición que **NO debe relajarse**: el sistema exige `PAPER + material válido + R medible`.
No bajar `min cycles` / `min R` / `folds` solo para que el runner produzca algo: eso destruiría el
propósito de `AUTO-22`.

**Primer experimento recomendado (con material real):** **1 estrategia → ≥32 ciclos medibles →
`AUTO-22`**. Después, la segunda corrida con `Strategy A + Strategy B` para evaluar de verdad
`correlation(A,B)`; luego `P(R>0)` vs `N` (estabilidad, no selección) y estabilidad del régimen
(global vs régimen actual).

## Observaciones de UI y de frontera (21–23)

- 🟠 **Mejora menor de UI antes del primer RUN real:** hacer **imposible de confundir** el origen
  (`SOURCE`: `PAPER REAL` vs `SYNTHETIC FIXTURE`) y añadir **`EXECUTION REALITY: VIRTUAL — NO REAL
  MONEY`**, porque `PAPER REAL` puede malinterpretarse como **dinero real** (en realidad son **datos
  reales de la cuenta PAPER** con dinero virtual). Abordada en **`AUTO-23` / `v2.70`**.
- 🟢 **La frontera con allocation sigue perfecta:** `EVIDENCE → ALLOCATION = NONE`. No debe existir
  todavía `if P_R_positive > 0.8: increase_allocation()`, ni `if correlation < 0.3: add_strategy()`, ni
  `if current_regime_supported: trade()`. Sería una fase posterior con contrato propio.

## Estado global de AUTO tras V2.69 (26)

| Fase | Estado |
|---|---|
| `AUTO-16` costes | 🟢 |
| `AUTO-17` población | 🟢 |
| `AUTO-18` allocation policy | 🟢 **FREEZE** |
| `AUTO-19A` incertidumbre | 🟢 |
| `AUTO-19B` walk-forward | 🟢 |
| `AUTO-20` material | 🟢 |
| `AUTO-21` evidencia | 🟢 |
| `AUTO-22` reproducibilidad | 🟢 |
| PAPER real suficiente | 🔴 |
| Primera evidencia de mercado | 🔴 |
| Validación empírica de la correlación | 🔴 |
| Validación `P(R>0)` vs N | 🔴 |
| Validación del régimen actual | 🔴 |
| AUTO allocation | ❌ |
| LIVE | ❌ |

## Conclusión

`V2.69-beta` es una versión muy buena y, a nivel de **infraestructura de evidencia**, se considera
**cerrada**. El cuello de botella ya **no es el software**, sino el **primer dataset PAPER real
suficientemente grande** — y eso es una buena noticia: seguir añadiendo complejidad al motor AUTO
antes de observar datos reales empezaría a ser contraproducente.

**Recomendación para el siguiente hito:** `V2.70` — ejecutar y auditar la primera corrida `AUTO-22`
sobre material PAPER real, **sin cambiar ninguna regla estadística ni de allocation**. Deudas P3
declaradas en [deuda-p3-post-auditoria-v2.69-2026-09-25.md](./deuda-p3-post-auditoria-v2.69-2026-09-25.md).
