# Plan — `V2.88.39` / `AUTO-DIA-D`: **atribución del resultado OOS 2022** (explicar el `-0.5011 R/ciclo`)

> **AsOf:** 2026-10-03 · **Estado:** **EJECUTADO** · **Base:** `v2.88.38-beta`
> (`2.11.38-beta`, commit `41b69265`) · **Bump:** `2.11.38-beta → 2.11.39-beta` ·
> **Alembic head:** `048_journal_entry_dedupe_key` (**SIN migración**) · **`Δ motor = 0`**.

## 0. Por qué existe

`v2.88.38` produjo la primera medición longitudinal OOS (`2022`): veredicto **`REFUTED`**,
`expectancyR=-0.5011`, `hitRate=0.3396`, `evidenceQuality=STRONG`, `MAE medio=-1.3880`,
`MFE medio=+1.2408`. La medición responde **cuánto**, pero no **dónde** ni **cómo** se pierde el R.

Esta fase (`DÍA-D-3a`) **atribuye** esa MISMA muestra: descompone la expectativa por régimen,
estrategia, sector y activo, estudia la excursión (captura de MFE / severidad de MAE) y la
concentración. Es **INVESTIGACIÓN** sobre la evidencia de `v2.88.38`; **no** ejecuta ventanas
nuevas (eso es multirregimen, `DÍA-D-3b`) y **no** sustituye la ventana PAPER real (`P3-2`/`P3-3`
siguen **ABIERTAS**).

## 1. Decisiones fijadas

- **Instrumento nuevo read-only**, no extensión del runner: la atribución vive en un módulo puro
  y un CLI propios, para no contaminar `v2_91` ni el artefacto longitudinal sellado.
- **Reutilizar, no duplicar:** veredicto/`evidenceQuality` de `build_value_scorecard`; MAE/MFE de
  `dia_d_longitudinal.excursions`; régimen de `replay_oos.census_operable_days`; sector de
  `v86._load_sectors`.
- **Huecos declarados:** `None`/`NOT_MEASURED`, **nunca** `0`; cubos sin muestra no aparecen.
- **Cruce falsable:** `--check-against <longitudinal.json>` compara el resumen recomputado con el
  artefacto sellado y declara `evidenceDrift` si la BD local derivó.

## 2. Diseño

```
PIT histórico (Universe(D)) ─► watch ─► replay hermético 2022 (v87._run_durable_replay)
                                             │
               census_operable_days ─────────┤ régimen por día (aggregate trial)
                                             ▼
                                    round_trips (entryDay/symbol/R/strategyVersion)
                                    excursions  (maeR/mfeR/dirección)
                                    sector por símbolo
                                             │
                                             ▼
                         dia_d_attribution.build_dia_d_attribution_artifact(...)
                                             │
       ┌──────────────┬──────────────┬──────┴───────┬──────────────┐
       ▼              ▼              ▼              ▼              ▼
  decomposition   byRegime      byStrategy     bySector      bySymbol + concentración
  (payoff)                                                  + captura MFE / severidad MAE
                                             │
                                             ▼
                         artefacto JSON determinista (dia-d-attribution-v1)
```

### 2.1 Piezas nuevas

1. **`packages/py/application/src/bolsa_application/dia_d_attribution.py`** — módulo **puro**:
   `payoff_decomposition`, `attribute_by` + lectores de dimensión, `capture_study`,
   `mae_severity`, `concentration`, `build_dia_d_attribution_artifact`.
2. **`apps/api-python/scripts/v2_92_dia_d_attribution.py`** — CLI que reutiliza el harness de
   `v2_91` (`_resolve_window`/`_run_pass`), corre **una** pasada y agrega; sonda `probe` con
   `truncationReason`/`windowFallback`.
3. **`packages/py/application/tests/test_dia_d_attribution.py`** — 12 tests puros.
4. **`docs/engineering/evidence/v2.88.39/README.md`** — evidencia del sello.

### 2.2 Restricciones críticas

- **`replay-repro` congela** el artefacto OOS: la atribución vive **fuera** del camino congelado
  (no toca `score_replay`/`RoundTrip.to_dict`/`v2_87`).
- **Un solo régimen:** 2022 es casi todo `high_vol` ⇒ `byRegime` colapsa a **un** cubo; se
  declara y no se sobreinterpreta como multirregimen.
- **Sector aproximado:** es el del catálogo **actual**, no point-in-time.

## 3. Afirmaciones falsables

1. **Identidad de payoff:** `expectancyR = winRate·avgWinR + (1 − winRate)·avgLossR`
   (`identityGap` ~ 0; medido `1.11e-16`).
2. **Reproducción:** el resumen recomputado == el sellado por `v2.88.38` (`evidenceDrift=false`).
3. **Dimensiones:** `bySector`/`bySymbol` con `n` y expectativa por cubo; cubos sin muestra, ausentes.
4. **Excursión:** fracción de ciclos con MAE `< -1R`/`< -1.25R`/`< -1.5R` y `reversedCount` de MFE.
5. **Determinismo:** dos corridas ⇒ payload idéntico.
6. **Instrumento congelado intacto:** `replay-repro` sigue byte a byte.

## 4. Sello y gates

- **Bump** `2.11.38-beta → 2.11.39-beta` (`package.json` + `meta.bump` de `v2_89`/`v2_90`/`v2_91`/
  **`v2_92`**; guardián `test_dia_d_bump_guard` extendido con `v2_92`). **`CHANGELOG`**,
  `CURRENT_SYSTEM`, `versioning`, **evidencia** y **re-anclaje del freeze**
  (`WINDOW_CONFIG` al árbol funcional). **SIN migración.**
- **Gates locales:** pytest DÍA-D (108), `ruff`, `lint-imports`, `mypy` (525 archivos),
  `contract:check`, `typecheck`, `vitest` auto-monitor, `window:test` (25/25), smoke `v2_92 --year
  2022 --universe pit`.

## 5. Límites declarados (van en el artefacto y en el README)

- **No** sustituye la ventana PAPER; **no** es causal; **no** mide multirregimen.
- Régimen = agregado trial por día; sector = catálogo actual.
- MAE/MFE **entre días** (D1), con sesgo en el día de entrada.
- **`Δ motor = 0`**; sin migración; `CONFIRMED` reservado a PAPER.

## 6. Archivos

**Nuevos:** `packages/py/application/src/bolsa_application/dia_d_attribution.py`,
`packages/py/application/tests/test_dia_d_attribution.py`,
`apps/api-python/scripts/v2_92_dia_d_attribution.py`,
`docs/engineering/evidence/v2.88.39/README.md`, este plan.

**Modificados:** `apps/api-python/tests/test_dia_d_bump_guard.py`,
`apps/api-python/scripts/v2_89|v2_90|v2_91…` (sólo `meta.bump`), `package.json`, `CHANGELOG.md`,
`docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs`
(re-anclaje del freeze).
