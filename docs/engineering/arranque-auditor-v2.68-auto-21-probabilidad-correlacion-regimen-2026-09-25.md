# Arranque del auditor — `v2.68-beta` (`AUTO-21`)

> **AsOf:** 2026-09-25 · **Tag a auditar:** `v2.68-beta` (`1.93.0-beta`) · **Tag base:** `v2.67-beta`
> **Naturaleza:** fase estrictamente de **medición/evidencia** (`P(R>0)`, correlación por cubo, evidencia
> del régimen actual). Sin producto nuevo, sin migración.

## Encargo

Verificar, **contra el código sellado**, que las tres lecturas nuevas se **miden** (no se afirman), que los
huecos se **declaran** (`NO MEDIDO`) y que la fase **no** ha movido nada que no debía (freeze, reparto,
migración, esquema del artefacto). No creer el audit-pack: medirlo.

## Objeto de auditoría

- Repo: `c:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1`
- Diff: `git diff v2.67-beta v2.68-beta`
- Docs de fase: `plan`/`audit-pack`/`relevo`/este arranque (sufijo
  `v2-68-auto-21-probabilidad-correlacion-regimen-2026-09-25`).

## Tesis a verificar

1. **`P(R>0)` es una medición, no una constante.** ¿`probabilityPositive` sale de la **misma** distribución
   bootstrap que el intervalo (fracción estrictamente `> 0`)? ¿Sin bootstrap es `None` + `insufficient_episodes`
   (jamás un `0`)? Comprobar por código y por **M183**.
2. **Sello subido.** ¿`ADAPTIVE_UNCERTAINTY_METHOD` es `bootstrap_episodes_v2` y `CALIBRATION_METHOD`
   `walk_forward_calibration_v3`? **M182**/**M184** deben morder.
3. **La pregunta de calibración no sella sin muestra.** ¿`probability_positive_calibration` exige celdas con
   **ambos** términos y es `inconclusive` por debajo del mínimo? ¿El `meanAbsoluteCalibrationError` es
   medio (no una suma ni un máximo)? **M185** debe morder.
4. **La correlación por cubo no se fabrica.** ¿Sin cubos compartidos ⇒ `None` + `no_shared_buckets`? ¿Con
   menos de `min_buckets` ⇒ `insufficient_buckets`? ¿Serie constante ⇒ `constant_series`? **M186** debe
   morder. Verificar además que la correlación **no** entra en el optimizador ni en la reserva
   (`git diff` de `portfolio_optimizer.py` / `portfolio_reservation.py` → **vacío**).
5. **La evidencia del régimen actual se declara.** ¿Una estrategia sin celda de ese régimen publica
   `measured_n = 0` + `no_evidence_for_regime` en vez de la lectura agregada? ¿El régimen sale del flag o
   del ciclo más reciente con régimen declarable (nunca de `UNKNOWN`)? **M187** debe morder.
6. **Render y espejo TS.** ¿El stub `AUTO-21 (fuera de alcance)` desaparece y `Current regime` /
   `Current evidence` publican lo medido (o `NO MEDIDO`)? ¿El TS **lee** y no recalcula?
7. **Aditividad del artefacto.** Sin `correlation`/`currentRegime`/`currentEvidence`, `build_evidence_artifact`
   produce un artefacto **byte-idéntico** al auditado en `v2.67`; el esquema sigue `auto20c_evidence_artifact_v1`.
8. **Sin regresión.** Las compuertas re-miden en verde y la matriz completa no tiene huecos.
9. **Freeze y reparto intactos**; **sin migración** (head `046_fill_reference_mid`).

## Sondas sugeridas

- Leer `_interval_from_episodes` (Python): ¿la `probability_positive` se calcula del **mismo** `means` que
  el intervalo? ¿Se redondea a 4?
- Leer `_question_probability_positive`: ¿el veredicto usa el error absoluto **medio** contra la
  tolerancia declarada?
- Leer `build_strategy_correlation_report` y `pearson_correlation`: ¿hay algún camino que publique un
  número sin cubos compartidos suficientes?
- Leer `build_current_regime_evidence`: ¿algún camino atribuye a una estrategia la celda de **otro**
  régimen o la lectura agregada?
- Sonda propia: montar dos estrategias con cubos compartidos y **comprobar el número contra un oráculo**
  (p. ej. `numpy.corrcoef` o el cálculo a mano) para descartar que el `±1` esperado venga de una fórmula
  rara.
- `git diff --stat v2.67-beta v2.68-beta`: ¿la superficie es la declarada?
- `git diff v2.67-beta v2.68-beta -- packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py
  packages/py/application ...` para los ficheros congelados → **vacío**.
- Re-ejecutar la matriz (`M182 M183 M184 M185 M186 M187`) y, opcionalmente, la completa.

## Compuertas a re-ejecutar

| Compuerta | Comando |
|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` |
| Frontend typecheck/lint | `pnpm --filter @bolsa/web typecheck` · `... lint` |
| Frontend build/contrato | `pnpm --filter @bolsa/web build` · `... contract:check` |
| Python analytics | `uv run pytest packages/py/analytics -q` |
| Ruff / import-linter | `uv run ruff check packages/py apps/api-python` · `uv run lint-imports --config packages/py/.importlinter` |
| Mutaciones | `.../v2_44_mutation_audit.py M182 M183 M184 M185 M186 M187` |

## Límites declarados (NO reportar como fallo)

- La **correlación es evidencia publicada**: no entra al optimizador, no reparte, no gatea. Que no mueva
  nada es el **objetivo**, no un defecto.
- La **evidencia del régimen actual** reutiliza el bootstrap de `AUTO-19A`: no hay una segunda aritmética
  de celda. Si el auditor quiere comparar, compare contra la celda de `byRegime` del mismo informe.
- La **corrida PAPER real** no se ejecuta (bloqueo por material); el fixture sigue siendo sintético y
  declarado. La correlación sobre un fixture sintético mide el **instrumento**, no el mercado.

## Reglas

- **READ-ONLY ESTRICTO**: sin editar, sin commit, sin push, sin tags. Si editas algo para una sonda,
  RESTÁURALO y deja el árbol limpio (byte a byte).
- Distinguir **bloqueantes** de **P3**; cada hallazgo con `fichero:línea`.

## Formato de respuesta

1. **Veredicto** (`APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`).
2. **Tabla**: una fila por tesis (1-9), con veredicto y evidencia.
3. **Hallazgos** (bloqueantes y P3) con `fichero:línea`.
4. **Compuertas re-medidas** (comando → resultado).
5. **Confirmación de freeze, reparto y migración**.
6. **Lo que no pudiste verificar** y por qué.
