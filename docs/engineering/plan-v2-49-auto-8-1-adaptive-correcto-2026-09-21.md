# Plan de fase — `AUTO-8.1` Adaptive correcto, explícito y reproducible (`V2.49`, `1.74.0-beta`)

**Fecha:** 2026-09-21 · **Punto de partida:** tag **`v2.48-beta`** (`1.73.0-beta`).
**Migración:** **NO** — Alembic head sigue en **`044_auto_cycle_trace`**.
**Bump:** `1.73.0-beta` → **`1.74.0-beta`**. **Sello:** tag anotado **`v2.49-beta`** (ver §8).

Este plan es la **orden de trabajo** de la fase; el pack de evidencia es
[`audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md`](./audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md)
y el relevo es
[`traspaso-relevo-post-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md`](./traspaso-relevo-post-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md).
Si el plan y el pack se contradicen, **manda el pack**.

---

## 0. Decisiones del owner

1. **Sin evidencia decisoria ⇒ neutral `1.0`, como POLÍTICA** (`AdaptivePolicy.unknown_multiplier`), nunca como
   consecuencia de que la clave falte en un diccionario. "Sin dato no penalizo" se declara y se puede configurar.
2. **AUTO-8.1 no añade "inteligencia" nueva**: corrige la asignación, cierra una inversión de riesgo (`0.0`),
   y hace la adaptación estable (hysteresis/cooldown), trazable (evidencia + `policyVersion`) y reproducible
   (golden byte a byte).
3. **`strategy × regime` y `net expectancy_R` NO se inventan.** Hoy no existe productor por ciclo (los fills no
   llevan régimen, coste, riesgo ni R): se entrega la **forma** declarada `UNKNOWN`/`None` y se documenta el gate.
4. **Los gates duros siguen intocables** y el flag OFF sigue byte-idéntico a `AUTO-7`.

---

## 1. Invariante que instala

> _Adaptive solo puede estrechar el riesgo por operación y solo con evidencia decisoria. Una estrategia sin
> evidencia es DESCONOCIDA (neutral), nunca "mala" (riesgo cero). Toda recomendación viaja sellada con su versión
> de política y con la evidencia que la sustentó, de modo que sea reproducible y auditable._

---

## 2. Qué NO cambia (freeze)

- **`AUTO_ENGINE_SIM_V2=0`**: comportamiento `v2.39.x` intacto.
- **`AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
- **`v2_43_governor_evidence.py`**: **byte a byte igual**, `exit 0`, su `"bump"` conservado en `1.68.0-beta`.
- **Tabla del gobernador y sus umbrales**: no se tocan.
- **`v2.48-beta` y anteriores no se mueven**: `v2.49-beta` es **nueva y aditiva**.
- **Sin SHORT**: ninguna ruta nueva permite entrada corta.
- **Sin migración**: Alembic head sigue `044_auto_cycle_trace`; **sin backfill**.
- **`RiskAllocator.compute_allocation`**: solo cambia el **borde `pct == 0.0`** (techo cero explícito); el resto
  del sizing y `portfolio_decision_engine.py` (vetos fail-closed) **no se tocan**.

---

## 3. Hallazgos que cierra (auditoría externa de `v2.48-beta`)

### H1 · Asignación sin gate de decisividad por fila

`recommend_allocation` construía `positive` sin exigir `row.decisive` y comprobaba la decisividad a nivel de
**grupo** (`decisive_positive = any(...)`). Una muestra fina con racha favorable entraba al numerador y movía el
presupuesto de las estrategias que sí habían demostrado. Contradice el principio que el propio módulo declara
("sin muestra no es mala, es desconocida") y que `recommend_rotation` sí respeta.

### H2 · El multiplicador `0.0` no estrechaba: quitaba el techo

`0.0` → `max_risk_per_trade_pct = base * 0.0 = 0.0`; en `compute_allocation` el guard `pct > 0` dejaba
`max_by_pct = None`, así que el sizing caía a **todo el `risk_budget`** de cartera y no añadía `CAP_RISK_PCT`.
El env no puede producir `0.0` (`or base`), así que la única ruta era Adaptive: el caso "riesgo cero" asignaba
**más** riesgo por operación que cualquier otro. `None` es el único contrato de "sin techo".

### H3 · "Sin evidencia" no era una política

Una versión ausente del mapa de asignación terminaba en `1.0` por el default de `AllocationPlan.multiplier_for`,
no por una decisión declarada; y una fila no decisoria con un positivo presente terminaba en `0.0` (riesgo cero).
Ambos extremos eran accidentes de estructura, no política.

### H4 · Sin versión de política, sin evidencia, sin goldens

`AdaptivePlan` no sellaba `policyVersion`; el journal solo publicaba `{riskMultiplier, regime}` y solo si `< 1.0`;
no había test "ON neutral ≡ OFF" ni de reproducibilidad; no había hysteresis ni cooldown.

---

## 4. Piezas

### 4.1 `auto_adaptive.py` — política, gate por fila y estabilidad

- **`AdaptivePolicy`** (frozen/slots, versionada): `policy_version="auto8-v2"`, `unknown_multiplier=1.0`,
  `win_rate_floor=0.35`, `win_rate_reactivate_floor=0.45`, `profit_factor_pause=1.0`,
  `profit_factor_reactivate=1.10`, `min_pause_cycles=3`.
- **`recommend_allocation(active, by_strategy, *, policy)`**: materializa **una entrada por versión activa**;
  solo las filas `decisive` con `expectancy_currency > 0` entran al reparto proporcional (`share * m`, con `m`
  su número); el resto recibe `unknown_multiplier`. **Nunca emite `0.0`.**
- **`recommend_rotation(..., paused_cycles)`**: hysteresis (umbrales de pausa ≠ reactivación) + cooldown
  (`min_pause_cycles`), con el estado previo como **dato** de entrada (módulo puro).
- **`AdaptivePlan.policy_version` + `health`**: sello de política y proyección de salud, con
  `evidence_for(version)` para el journal.
- **`StrategyHealth.net_expectancy_r` / `regime`**: forma declarada (`None` / `UNKNOWN`), sin productor hoy.

### 4.2 `risk_allocator.py` — el borde `0.0`

`pct == 0.0` pasa a ser un **techo cero explícito** (`max_by_pct = 0.0`, `CAP_RISK_PCT`, `approved=False`),
distinto de `None` ("sin techo").

### 4.3 `auto_v2_entry.py` — trazabilidad del journal

El estrechamiento publica `policyVersion` + `evidence`; la pausa publica `adaptiveEvidence`. Con el flag OFF o
con la recomendación neutral (multiplicador `1.0`) el payload sigue siendo el histórico **byte-idéntico**.

### 4.4 `auto_simulation_worker.py` — estado de cooldown

`_v2_build_adaptive_plan` construye la `AdaptivePolicy` desde los tunables y pasa `paused_cycles`, derivados del
plan anterior en memoria (límite declarado: tras un reinicio arranca vacío).

---

## 5. Gates y tests nuevos

| Gate                                            | Test                                                                                                                   |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Gate por fila (no filtra decisividad por grupo) | `test_allocation_non_decisive_positive_does_not_leak_into_reparto`                                                     |
| Sin evidencia ⇒ neutral, nunca `0`              | `test_allocation_never_emits_zero_multiplier`, `test_allocation_materializes_active_version_without_row`               |
| Política explícita y configurable               | `test_allocation_unknown_multiplier_is_explicit_policy`                                                                |
| Reproducibilidad (orden de filas indiferente)   | `test_adaptive_plan_is_reproducible_regardless_of_row_order`                                                           |
| ON neutral ≡ OFF (byte a byte)                  | `test_adaptive_on_neutral_is_byte_identical_to_off`                                                                    |
| Adaptive no toca gates duros                    | `test_adaptive_only_changes_candidates_and_risk_cap_not_hard_gates`                                                    |
| Trazabilidad (`policyVersion` + evidencia)      | `test_narrowing_journal_carries_policy_version_and_evidence`, `test_pause_journal_carries_evidence_and_policy_version` |
| Hysteresis (zona muerta)                        | `test_rotation_hysteresis_keeps_pause_inside_profit_factor_dead_zone`, `test_rotation_regime_hysteresis_dead_zone`     |
| Cooldown                                        | `test_rotation_cooldown_keeps_pause_before_min_cycles`, `test_rotation_cooldown_expires_and_reactivates`               |
| Techo cero explícito                            | `test_allocation_zero_pct_is_an_explicit_zero_ceiling_not_uncapped`                                                    |

---

## 6. Mutaciones nuevas (M22–M27)

| #   | Mutación                                                | Qué protege                  |
| --- | ------------------------------------------------------- | ---------------------------- |
| M22 | el multiplicador de una versión sin evidencia cae a `0` | "no medido" ≠ "riesgo cero"  |
| M23 | una muestra no decisoria entra al reparto proporcional  | gate de decisividad por fila |
| M24 | el plan deja de sellar `policyVersion`                  | reproducibilidad             |
| M25 | el umbral de reactivación baja al de pausa              | hysteresis (zona muerta)     |
| M26 | sin decisividad la pausa de salud se declara vigente    | confianza de muestra         |
| M27 | la pausa mínima deja de respetarse                      | cooldown                     |

---

## 7. Cómo verificarlo

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
         packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

uv run pytest packages/py/analytics/tests/test_auto_adaptive.py \
              packages/py/application/tests/test_auto_adaptive_entry.py \
              packages/py/analytics/tests/test_risk_allocator.py -q

uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py   # M19-M27
```

---

## 8. Sello (HECHO y verificado en CI)

**Commit de fase:** `2f541fc7` (14 ficheros, `+1248/−91`). **Tag anotado:** `v2.49-beta` → objeto `3d0a139b` →
commit `2f541fc7`. `package.json` → **`1.74.0-beta`**, `CHANGELOG.md` con la entrada de la fase y docs
`plan`/`pack`/`traspaso` en `docs/engineering/`.

**CI real** (2026-09-22, observada con `gh` sobre el commit sellado): **10 runs, 10 `success`, cero rojos** —
`Release tag CI` [`35694148660`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148660), `Python CI`
[`35694148702`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148702) y los tres restantes del tag, más
los cinco de `main`. Detalle y la incidencia medida del push multi-tag en el §12 y §13 del
[pack](./audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md).
