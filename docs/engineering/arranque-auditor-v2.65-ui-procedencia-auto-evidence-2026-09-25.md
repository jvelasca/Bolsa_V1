# Arranque del AUDITOR — `v2.65-beta` (`AUTO-20D` · UI de procedencia del AUTO EVIDENCE REPORT)

**Qué auditas:** el cierre de `v2.65-beta` (`1.90.0-beta`). **Pack:**
[audit-pack-v2-65](./audit-pack-v2-65-ui-procedencia-auto-evidence-2026-09-25.md) ·
**Plan:** [plan-v2-65](./plan-v2-65-ui-procedencia-auto-evidence-2026-09-25.md) ·
**Relevo:** [traspaso post-v2.65](./traspaso-relevo-post-v2.65-ui-procedencia-auto-evidence-2026-09-25.md).

## 1. Tesis a verificar (no a creer)
    10|
1. **La UI no inventa un cero.** Un conteo `null` se muestra `NO MEDIDO`; el `0` legítimo se muestra `0`.
2. **La UI no degrada procedencia.** Un `materialOrigin` desconocido —o un artefacto sin material— **no** se
   muestra como `PAPER REAL`.
3. **La UI no recalcula.** El `report` viaja verbatim; no hay segundo camino que re-derive R/WFE/coverage.
4. **El fixture no puede leerse como real.** El badge `FIXTURE SINTÉTICO` lleva `NO UTILIZAR PARA DECISIONES`.
5. **Nada de Python ni del freeze cambió.** El diff de la fase es solo `apps/web`.
6. **Sin migración.** Alembic head sigue en `046_fill_reference_mid`.

## 2. Sondas sugeridas
    20|
* Importar un artefacto con `materialOrigin = synthetic_fixture` y con `materialOrigin = paper_real`: el
  badge debe cambiar de etiqueta y de `data-source-kind`.
* Importar un artefacto con un conteo `null` (p. ej. `cyclesWithRisk`) y con `0`: deben diferenciarse.
* Importar un JSON con `schema` ajeno: debe **rechazarse** y **no** aparecer en el archivo local.
* Importar un artefacto con `realMoneyAtRisk = true` o `executionReality = "live"`: deben salir avisos.
* Comparar las claves de calibración del TS con las que emite `auto_adaptive_calibration` (contrato pinneado).
* Confirmar por `git diff` que `packages/py` y los ficheros congelados no cambian.

## 3. Compuertas del pack
    30|
| Compuerta | Comando | Esperado |
|---|---|---|
| Tests | `pnpm --filter @bolsa/web test` | **1320 passed** |
| Tipos | `pnpm --filter @bolsa/web typecheck` | **OK** |
| Lint | `pnpm --filter @bolsa/web lint` | **0 errores** |

## 4. Límite declarado que NO debe leerse como fallo

**La corrida PAPER real (AUTO-20D) no se ejecuta en esta fase.** El PostgreSQL local tiene
`sim_fill_finance_context` con `cycle_id` NULL en **todos** los fills (628) ⇒ el exportador bloquearía con
    40|`exit 2`. El estado real es `SIN MATERIAL · NO MEDIDO`, que la UI declara. La corrida sigue siendo paso
operativo del propietario y **no** se fabrica ningún resultado.

## 5. Fuera de alcance (AUTO-21)

`P(R > 0)`, correlación entre estrategias y current-regime gating.
