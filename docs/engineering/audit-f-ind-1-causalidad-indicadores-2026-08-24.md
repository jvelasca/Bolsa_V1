# Auditoría AS-IS — F-IND-1 Causalidad de indicadores (2026-08-24)

> **Propósito:** veredicto read-only sobre el estado real de **F-IND-1** (Causality Layer) y **F-IND-2** (batería CI), contrastando backlog/relevos que lo listaban como «residual desde F2 backtest» contra el código en HEAD.
> **AsOf:** 2026-08-24 · HEAD **`e3b943a`** (= tag `v1.7.0-beta` = `origin/main`).
> **Subagente:** Ciclo 5/5 bounded · docs-only · sin commit.

---

## 0. Veredicto ejecutivo

| Pregunta                              | Respuesta                                                                                                                   |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **¿F-IND-1 implementado?**            | **SÍ** — merge `79fa155`, ancestro verificado de HEAD                                                                       |
| **¿F-IND-2 implementado?**            | **SÍ** — merge `09fb06b`, ancestro verificado de HEAD                                                                       |
| **¿Queda trabajo de código F-IND-1?** | **NO** — guardias + metadatos + validador + tests en CI                                                                     |
| **Estado del ítem**                   | **CLOSED**                                                                                                                  |
| **Origen del «residual» en relevos**  | **Deriva documental** — nota obsoleta en `PROJECT_STATE.md` §2 fila F2 y §4 «Aún vigentes»; no refleja merges de 2026-08-19 |

**Siguiente paso recomendado:** cerrar el ítem en living SoT (backlog §0 + handoff). Opcional no bloqueante: higiene doc en `PROJECT_STATE.md` §2/§3/§4 (ya aplicada en este ciclo) y recalcular trials históricos que usaran `chikou` (decisión operativa explícitamente diferida — ver §5).

---

## 1. Alcance pactado (PROJECT_STATE §3)

| Código      | Objetivo                                                                                                            | Estado doc            | Estado código      |
| ----------- | ------------------------------------------------------------------------------------------------------------------- | --------------------- | ------------------ |
| **F-IND-1** | Causality Layer: metadatos causal vs visualización; prohibir `chikou`/`fractals` como features en backtest/research | ✅ MERGED (`79fa155`) | ✅ Verificado HEAD |
| **F-IND-2** | Batería CI: `feature_at_t` idéntico con/sin barra futura para todos los indicadores                                 | ✅ MERGED (`09fb06b`) | ✅ Verificado HEAD |

Verificación git (2026-08-24):

```text
git merge-base --is-ancestor 79fa155 HEAD  → exit 0
git merge-base --is-ancestor 09fb06b HEAD  → exit 0
```

---

## 2. Evidencia de implementación (file:line)

### 2.1 Metadatos TS (F-IND-1)

| Evidencia                                                                        | Ubicación                                              |
| -------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Campos `causal`, `confirmationLag`, `visualizationOffset`, `nonCausalOutputKeys` | `packages/shared/src/indicator-universe.ts:156-185`    |
| `IND-FR`: `causal: false`, `confirmationLag: 2`                                  | `indicator-universe.ts:964-976`                        |
| `IND-ICH`: familia causal + `nonCausalOutputKeys: ["chikou"]`                    | `indicator-universe.ts:997-1014`                       |
| Tests vitest metadata (5 tests)                                                  | `packages/shared/src/indicator-causality.test.ts:9-64` |

### 2.2 Guardia runtime backtest/research (F-IND-1)

| Evidencia                                       | Ubicación                                                                 |
| ----------------------------------------------- | ------------------------------------------------------------------------- |
| `_NON_CAUSAL_OUTPUT_LINES` (`ich` → `chikou`)   | `packages/py/analytics/src/bolsa_analytics/signals/rules_engine.py:48-55` |
| `fr` devuelve `None` (no cableado como feature) | `rules_engine.py:71-72`                                                   |
| `ich:chikou` bloqueado antes del branch ich     | `rules_engine.py:74-79`                                                   |
| Docstring guardia F-IND-1                       | `rules_engine.py:66-69`                                                   |

**Nota de diseño:** `compute_ichimoku` sigue calculando `chikou` para chart (`compute.py:815-826`) — correcto: visualización ≠ feature de señal. El evaluador de reglas no expone `chikou` al contexto de señales.

### 2.3 Validación de estrategias (F-IND-1)

| Evidencia                 | Ubicación                                |
| ------------------------- | ---------------------------------------- |
| Rechazo `ich line=chikou` | `strategy_definition_validator.py:67-72` |
| Rechazo `fr` (fractals)   | `strategy_definition_validator.py:73-76` |

### 2.4 Compute subyacente (look-ahead intencional solo chart)

| Indicador                      | Comportamiento                      | Ubicación            |
| ------------------------------ | ----------------------------------- | -------------------- |
| Chikou usa barra futura        | `chikou[index] = bars[ahead].close` | `compute.py:824-826` |
| Fractals Williams centrados ±2 | `range(index - 2, index + 3)`       | `compute.py:778-784` |

Estos paths son **correctos para dibujo** y están **excluidos del feature set** de backtest por las guardias anteriores.

### 2.5 Tests F-IND-1 (pytest)

| Test                                             | Qué verifica                            | Ubicación                         |
| ------------------------------------------------ | --------------------------------------- | --------------------------------- |
| `test_chikou_not_a_causal_feature`               | `_series_for_spec(ich,chikou)` → `None` | `test_causality_layer.py:34-42`   |
| `test_rules_reject_noncausal_ich_chikou`         | validador rechaza chikou                | `test_causality_layer.py:45-56`   |
| `test_fractals_not_wired_into_backtest`          | `fr` → `None` + validador               | `test_causality_layer.py:59-72`   |
| `test_validator_allows_chikou_for_visualization` | sma/tenkan permitidos                   | `test_causality_layer.py:75-98`   |
| `test_ich_causal_lines_still_resolvable`         | tenkan/kijun/spanA/spanB OK             | `test_causality_layer.py:101-112` |

### 2.6 Batería F-IND-2 (pytest)

| Evidencia                                                  | Ubicación                                         |
| ---------------------------------------------------------- | ------------------------------------------------- |
| 31 indicadores causales — prefix-estables                  | `test_causality_battery_ind_2.py:79-133,135-163`  |
| 2 canarios no causales (`chikou`, `fractals`) deben romper | `test_causality_battery_ind_2.py:117-119,169-199` |
| Guard de cobertura `definition_id`                         | `test_causality_battery_ind_2.py:202-212`         |

---

## 3. Batería ejecutada (2026-08-24)

| Suite                    | Comando / fichero                                                            | Resultado        |
| ------------------------ | ---------------------------------------------------------------------------- | ---------------- |
| F-IND-1 + F-IND-2 pytest | `pytest tests/test_causality_layer.py tests/test_causality_battery_ind_2.py` | **39/39 passed** |
| Metadata vitest          | `vitest run src/indicator-causality.test.ts`                                 | **5/5 passed**   |

---

## 4. Por qué aparecía como «residual»

| Fuente                                   | Texto obsoleto                                        | Realidad                                                    |
| ---------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------- |
| `PROJECT_STATE.md` §2 fila **F2**        | «NOTA: NO incluye causalidad — **pendiente F-IND-1**» | F-IND-1 mergeado **después** de F2; la nota no se actualizó |
| `PROJECT_STATE.md` §3 intro              | «causalidad = **único hueco serio** tras F2»          | Contradice filas F-IND-1/2 ✅ MERGED en la misma §3         |
| `PROJECT_STATE.md` §4 «Aún vigentes»     | Look-ahead chikou/fractals → F-IND-1/F-IND-2          | Debería estar en «Ya corregidos»                            |
| `traspaso-relevo-tag-v1-7-0-beta-...` §3 | F-IND-1 «diferido desde F2 backtest»                  | Propagación del stale F2                                    |
| `traspaso-relevo-d3-...` / `ops-...`     | «F-IND-1 residual» en candidatos                      | Misma deriva; no hay gap de código                          |

**Conclusión:** el «residual» era un **artefacto de documentación**, no deuda de implementación pendiente.

---

## 5. Follow-ups opcionales (fuera de alcance F-IND-1)

| Ítem                                                                | Tipo                     | Bloquea cierre F-IND-1                                                             |
| ------------------------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------------- |
| Recalcular trials/backtests que usaran `chikou` antes del merge     | Operativo / research     | **No** — explícitamente «no recalcular aún» (`PROJECT_STATE.md` §6 nota F-IND-1/2) |
| Sincronizar guardias Python desde `indicator-universe.ts` (codegen) | Mejora futura            | **No** — diseño actual = guardia estática + metadata TS                            |
| ADR-014 Causal profundo (grafo, discovery)                          | Fase distinta / diferida | **No** — fuera de F-IND-1/F-IND-2                                                  |

---

## 6. Cierre — evidencia de merge

| Commit    | Mensaje                                        | Fecha doc  |
| --------- | ---------------------------------------------- | ---------- |
| `79fa155` | merge: F-IND-1 Causality Layer                 | 2026-08-19 |
| `09fb06b` | test(analytics): bateria de causalidad F-IND-2 | 2026-08-19 |

Registro histórico: `docs/engineering/traspaso-ola-hardening-cierre-2026-08-19.md` · `engineering-index-2026-08-03.md` §5 (árbol F-IND-1/2).

**F-IND-1 / F-IND-2: CLOSED en HEAD `e3b943a`.**
