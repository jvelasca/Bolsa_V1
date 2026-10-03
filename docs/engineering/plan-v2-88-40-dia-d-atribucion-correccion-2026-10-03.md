# Plan — `V2.88.40` / `AUTO-DIA-D`: **corrección semántica de la atribución** (A39-01/02/03) + sello

> **AsOf:** 2026-10-03 · **Estado:** **EJECUTADO** · **Base:** `v2.88.39-beta`
> (`2.11.39-beta`, commit `0648cd40`) · **Bump:** `2.11.39-beta → 2.11.40-beta` ·
> **Alembic head:** `048_journal_entry_dedupe_key` (**SIN migración**) · **`Δ motor = 0`**.

## 0. Por qué existe

La auditoría profunda de `v2.88.39-beta` aprobó la arquitectura (capa de atribución read-only
sobre el OOS 2022, sin tocar el motor) pero señaló **tres defectos semánticos** en las métricas
principales antes de usarlas como base de decisiones de investigación:

- **A39-01 🔴** `capture_study` medía `realized / mfe`: ratios **negativos** y explosión con
  `MFE → 0+` (evidencia `meanCapture=-12.12`).
- **A39-02 🔴** `mae_severity` afirmaba medir "perdedores" pero contaba cualquier ciclo con MAE
  bajo el umbral (no conocía `realizedR`).
- **A39-03 🟠** el cross-check comparaba floats por igualdad exacta (`!=`), frágil.

Esta fase (`DÍA-D-3a.1`) cierra esos hallazgos **sin** tocar el motor y **sin** ejecutar ventanas
nuevas. Es una versión **quirúrgica**: no añade funcionalidades.

## 1. Decisiones fijadas

- **Rediseño limpio**, no aditivo: `capture` y `maeSeverity` cambian de forma y
  `SCHEMA_VERSION` sube a **`dia-d-attribution-v2`**.
- **Captura sobre el resultado no negativo:** `capturedR = max(realizedR, 0)`;
  `captureRatio = capturedR / MFE ∈ [0, +inf)`; un ratio `> 1` se **declara** (`aboveOneCount`),
  no se recorta.
- **Severidad por población:** se une el MAE con su ciclo por `cycle_key` y se publican tres
  poblaciones (`ALL`/`WINNERS`/`LOSERS`) con la MISMA partición que `payoff_decomposition`.
- **Cross-check tolerante** para floats (`math.isclose`, `1e-12`), exacto para el resto.
- **Huecos declarados:** `None`/`NOT_MEASURED`, **nunca** `0`.

## 2. Diseño del cambio

```
round_trips ──┬─► payoff_decomposition (sin cambios)
              ├─► capture_study ──► captureRatio {mean,median,max,aboveOneCount}
              │                      capturedR {mean,median}
              │                      leftOnTableR {mean,median}
              │                      reversedCount
              └─► mae_severity(round_trips, excursions_by_cycle) ──► populations
                     ALL / WINNERS / LOSERS ──► {cycles, meanMaeR, minMaeR, breaches{-1,-1.25,-1.5}}
```

### 2.1 Piezas modificadas

1. **`packages/py/application/src/bolsa_application/dia_d_attribution.py`** — `capture_study`,
   `mae_severity` (+ helper `_population_breaches`), `SCHEMA_VERSION`, docstring y `DEFAULT_LIMITS`.
2. **`apps/api-python/scripts/v2_92_dia_d_attribution.py`** — `_cross_check_summary` +
   `_numbers_close`/`_summary_values_match`, `_print_text` y `meta.bump`.
3. **`packages/py/application/tests/test_dia_d_attribution.py`** — tests reescritos + 4 nuevos.

## 3. Afirmaciones falsables

1. **Captura acotada:** no hay `captureRatio` negativo ni explosión por `MFE → 0+` (medido:
   media `0.1429`, mediana `0.0`, máx `0.6237`, `aboveOneCount=0`).
2. **Poblaciones divergentes:** `ALL` `< -1R` = `66.04 %` ≠ `LOSERS` = `94.29 %` ≠ `WINNERS` =
   `11.11 %`.
3. **Cross-check tolerante:** `evidenceDrift=false` con residuo de coma flotante; drift material
   sigue detectándose.
4. **Reproducción:** el resumen recomputado == el sellado por `v2.88.39` (`5/5` claves).
5. **Determinismo:** dos corridas ⇒ payload idéntico.
6. **Instrumento congelado intacto:** `replay-repro` sigue byte a byte.

## 4. Sello y gates

- **Bump** `2.11.39-beta → 2.11.40-beta` (`package.json` + `meta.bump` de `v2_89`/`v2_90`/`v2_91`/
  `v2_92`; guardián `test_dia_d_bump_guard`). **`CHANGELOG`**, `CURRENT_SYSTEM`, `versioning`,
  **evidencia** y **re-anclaje del freeze** (`WINDOW_CONFIG` al árbol funcional). **SIN migración.**
- **Gates locales:** pytest DÍA-D (112), `ruff`, `lint-imports`, `mypy` (525 archivos),
  `contract:check`, `typecheck`, `vitest` auto-monitor, `window:test` (25/25), smoke `v2_92 --year
  2022 --universe pit`.

## 5. Límites declarados (van en el artefacto y en el README)

- **No** sustituye la ventana PAPER; **no** es causal; **no** mide multirregimen.
- Régimen = agregado trial por día; sector = catálogo actual.
- MAE/MFE **entre días** (D1), con sesgo en el día de entrada.
- Concentración `broad` ≠ no-concentrado (métricas ampliadas pendientes).
- **`Δ motor = 0`**; sin migración; `CONFIRMED` reservado a PAPER.

## 6. Archivos

**Modificados:** `packages/py/application/src/bolsa_application/dia_d_attribution.py`,
`packages/py/application/tests/test_dia_d_attribution.py`,
`apps/api-python/scripts/v2_92_dia_d_attribution.py`,
`apps/api-python/scripts/v2_89|v2_90|v2_91…` (sólo `meta.bump`), `package.json`, `CHANGELOG.md`,
`docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs`
(re-anclaje del freeze).

**Nuevos:** `docs/engineering/evidence/v2.88.40/README.md`, este plan.

## 7. Secuencia posterior (no ejecutada aquí)

`v2.88.40` (sello) → certificación CI del tag → `DÍA-D-3b` (multirrégimen / 2022-2026) → sólo
entonces decidir si existe un defecto estructural del motor/estrategia. **No** se toca el motor
hasta cerrar la atribución y re-medir.
