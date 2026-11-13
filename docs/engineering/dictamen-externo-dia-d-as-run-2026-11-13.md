# Dictamen externo del cierre DÍA-D as-run — `2.11.189-beta` (2026-11-13)

> **Fecha:** 2026-11-13 · **Sello dictaminado:** `2.11.189-beta` · **ADR:** [049](../adr/049-adaptacion-gobernada-por-ia.md).
> **Naturaleza:** documento de **evidencia/dictamen**, no de producto. **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · sin migración · sin bump.**
> **Regla rectora:** un dato ausente o no inspeccionado se declara hueco; **nunca** se rellena con verde.
> **Material de apoyo:** [Método DÍA-D as-run](./dia-d-as-run-2026-11-13.md) · [Cierre de auditoría DÍA-D as-run](./cierre-auditoria-dia-d-as-run-2026-11-13.md) · [`CHANGELOG.md`](../../CHANGELOG.md) bloque A de `[Unreleased]`.

---

## 0. Veredicto

**PASS — cierre técnico y documental de DÍA-D AS-RUN**, comunicado como completo sobre `2.11.189-beta`.

El dictamen valora positivamente los nueve bloques de la actualización y da por cerrada la parte de **debilidades metodológicas** identificada en DÍA-D: ya no se trata solo de una simulación con costes y benchmarks, sino de un mecanismo con **invariantes económicos, integridad por barra y certificación reforzada**.

**Alcance declarado de este dictamen.** Se emite sobre la documentación y los resultados **comunicados por el productor**. **No** se ha inspeccionado independientemente el repositorio ni ejecutado los comandos de verificación. Por tanto, **no** se presenta como auditoría externa independiente: un dictamen de tercero que no corrió los gates no puede acreditar más que la coherencia de lo comunicado.

---

## 1. Valoración de los nueve bloques

| # | Bloque | Valoración |
| --- | --- | --- |
| 1 | Coste en caja unificado | **Correcto:** una única función de imputación, sin doble convención entre brazos |
| 2 | Base de coste de fills | **Correcto:** distingue precio cotizado y precio efectivo |
| 3 | `market_bh` comparable | **Mejora importante** de comparabilidad (universo, capital, periodo y coste compartidos) |
| 4 | MAE/MFE | **Corrige** la contaminación de excursiones posteriores a la salida |
| 5 | Universo declarado | **Evita** certificar universos reconstruidos implícitamente |
| 6 | Manifest por barra | **Permite** detectar alteraciones del histórico vela a vela |
| 7 | Certificación de ocho condiciones | **Refuerza** la separación entre integridad del artefacto y resultado |
| 8 | Tests | **Buena cobertura** de regresiones y de manipulación de artefactos |
| 9 | Documentación y versión | **Cierre trazable** en `2.11.189-beta` |

---

## 2. Tres mejoras especialmente relevantes

### A. Costes

- La unificación mediante `_execution_cost_currency` **elimina el riesgo** de que dos brazos contabilicen de forma diferente el mismo ciclo. Antes había dos convenciones (coste único sobre el notional de salida frente a medio coste por lado); el invariante de que el mismo ciclo paga lo mismo medido por fills que por barras es exactamente la propiedad que faltaba.
- La distinción `quoted` / `effective` es **necesaria** para no cobrar dos veces un coste que ya esté incorporado en los fills reales. Que `effective` exija `executionCostBps = 0` convierte la coherencia en una condición verificable y no en una convención.

### B. Integridad histórica

- El `barsManifest` por instrumento y día, junto con `barsHash`, proporciona una trazabilidad **mucho más fuerte** que un hash global sin desglose: una vela cambiada o ausente altera la huella y la certificación lo ve.
- Es especialmente valiosa la posibilidad de **verificar el manifiesto contra las velas originales** (`verify_bars_manifest` + `--verify-bars`), porque cierra el hueco de que el manifest y la fuente discrepen sin que nadie lo note.

### C. Certificación

- La condición `artifact_integrity`, junto con la recomputación de `paramsHash` y `barsHash` y la coherencia de versiones, **dificulta** que un artefacto modificado conserve indebidamente un resultado favorable.
- La regresión de artefactos v1 está **bien resuelta**: un documento antiguo sin sobre de auditoría no se convierte automáticamente en certificado; sale `not_certified` / `NOT_EVALUATED` y no se reescribe.

---

## 3. Resultados de verificación comunicados

Los resultados que se dan por consistentes son los siguientes. **Se registran tal y como fueron comunicados: no se han re-ejecutado en el repositorio para este dictamen.**

| Gate | Resultado comunicado |
| --- | --- |
| Pytest aplicación | **3.349 passed, 5 skipped** |
| DÍA-D y rutas dirigidas | **79–102 passed** según la invocación |
| Mypy | **0 errores** |
| Ruff con configuración CI | **Limpio** |
| Import-linter | **4 contratos conservados** |
| Web | **2.935 passed** |
| Shared | **1.039 passed, 1 todo** |
| TypeScript | **Sin errores** |
| Regresiones de adaptación | **5/5 passed** |

**Salvedades de Ruff, correctamente diferenciadas.** Se distinguen dos cosas que no deben mezclarse:

1. la **configuración de ejecución** (el gate corre con la configuración de CI y está limpio);
2. la **deuda histórica de formato**, que no forma parte del alcance de este cierre.

Reformatear centenares de archivos ajenos al alcance para dejar limpio un check que ya está limpio en su configuración efectiva sería un cambio gratuito de riesgo. La decisión de no hacerlo es la correcta.

**Fixtures incompletos.** Corregir los fixtures en lugar de debilitar la certificación es la dirección correcta: se arregla la entrada del test, no la condición que el test valida.

---

## 4. Qué queda demostrado y qué no

Mantener separados estos niveles es lo que evita leer «implementado» como «apto».

| Nivel | Qué exige | Estado tras el dictamen |
| --- | --- | --- |
| 1. Implementación | motor DÍA-D, costes, benchmark, manifiestos, auditoría y certificación | **Sí** |
| 2. Verificación técnica local | suites, tipos, lint e integridad de contrato según los resultados comunicados | **Sí** |
| 3. Validación histórica | cohortes DÍA-D reproducibles con distintos periodos y regímenes, y evidencia suficiente de resultados netos | **No** — requiere ejecuciones reales |
| 4. Aptitud operativa | robustez fuera de muestra y aprobación humana | **No** — `activationAllowed = false` |

**Un PASS de las ocho condiciones no es prueba de rentabilidad.** Certifica propiedades metodológicas del artefacto: que la reconstrucción es íntegra, temporalmente congelada, con datos de mercado verificables, ejecución realista, benchmarks comparables y auditoría coherente. **No** certifica que la estrategia vaya a ganar y no autoriza dinero real.

La línea base medida sigue siendo negativa; el as-run **no cambia el pasado**, lo mide.

---

## 5. Condiciones que se mantienen innegociables

1. **`activationAllowed = false`.**
2. **La IA no escribe estrategia activa ni mandato.**
3. **LAB y AS-RUN mantienen veredictos independientes:** ninguno sustituye al otro.
4. **Un resultado `NOT_EVALUATED` nunca equivale a PASS.**
5. **Ningún resultado histórico favorable autoriza automáticamente dinero real.**
6. **La rentabilidad se evalúa neta de costes y ajustada al riesgo.**

---

## 6. Límites del dictamen

| Límite | Qué significa |
| --- | --- |
| Sin inspección independiente | No se ha leído el código ni ejecutado ningún gate en este dictamen; los números son comunicados por el productor |
| Integridad ≠ autenticidad | La cadena de hashes detecta edición posterior al sellado, pero **no** distingue a un productor que reescriba artefacto y hashes de forma coherente; eso exige firma o sello externo al propio fichero |
| Sin cohorte histórica | No existe todavía evidencia longitudinal suficiente; el nivel 3 sigue abierto |
| Benchmarks en unidades distintas | `market_bh` no publica R (no tiene stop); su comparación es de retorno, no de R, y así debe declararse en la cohorte |

---

## 7. Qué sigue abierto

La siguiente cuestión de producto **no** es añadir más complejidad al motor: es conseguir **evidencia longitudinal suficiente** para determinar si la operativa presenta una ventaja estadística robusta.

1. **Nivel 3 — cohorte mínima.** Ejecutar el as-run sobre D reales desde el estado durable hasta reunir una cohorte `certified` con muestra ≥ 12 (`DEFAULT_MIN_COHORT_SAMPLES`), y publicar ese artefacto como evidencia.
2. **Nivel 4 — aptitud operativa.** Robustez fuera de muestra, rentabilidad neta ajustada al riesgo y aprobación humana explícita. `activationAllowed` sigue en `false` en todas las rutas.

Ninguno de los dos se planifica en este documento: aquí solo se declara como la siguiente frontera real.

---

## 8. Referencias

- [ADR-049 — Adaptación gobernada por IA y DÍA-D retrospectivo as-run](../adr/049-adaptacion-gobernada-por-ia.md) §3.3
- [Método DÍA-D as-run](./dia-d-as-run-2026-11-13.md) §3, §4 y §13
- [Cierre de auditoría DÍA-D as-run 2026-11-13](./cierre-auditoria-dia-d-as-run-2026-11-13.md) §1–§6
- [Operativa secuencial extremo a extremo](./operativa-secuencial-extremo-a-extremo-2026-11-13.md) §E5
- Código: [`dia_d_as_run.py`](../../packages/py/application/src/bolsa_application/dia_d_as_run.py), [`dia_d_certification.py`](../../packages/py/application/src/bolsa_application/dia_d_certification.py), [`v2_102_dia_d_as_run.py`](../../apps/api-python/scripts/v2_102_dia_d_as_run.py)
- Tests: [`test_dia_d_as_run_eval.py`](../../packages/py/application/tests/test_dia_d_as_run_eval.py)
- Contrato: [`packages/shared/src/dia-d-as-run.ts`](../../packages/shared/src/dia-d-as-run.ts)
