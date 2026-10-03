# Evidencia cruda — `v2.88.39-beta` (AUTO · **DÍA-D-3a**: **atribución del OOS 2022** — por régimen/estrategia/sector/activo + MAE/MFE y concentración, sin tocar motor)

> **Objeto:** package **`2.11.39-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** **atribución** (no capacidad) sobre **DÍA-D AUTO**, advisory y read-only. Convierte el `REFUTED` de `v2.88.38` en un **diagnóstico falsable**: descompone la MISMA muestra OOS de 2022 (universo `PIT` histórico) para responder *dónde* y *cómo* se pierde el R.
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py`) se toca, y **el artefacto congelado de `replay-repro` no se mueve**.
> **Padre:** [`evidence/v2.88.38/README.md`](../v2.88.38/README.md) (primera ventana longitudinal OOS).
> **Nomenclatura:** `AUTO engineering release = v2.88.39-beta` · `application package = 2.11.39-beta`.

---

## 0. Qué entrega este sello

| # | Pieza | Qué añade |
|---|---|---|
| **1 · Agregado puro** | `packages/py/application/src/bolsa_application/dia_d_attribution.py` | `payoff_decomposition` (**identidad** `expectancyR = winRate·avgWinR + (1 − winRate)·avgLossR` con residuo `identityGap` auditable), `attribute_by` + lectores de dimensión (`regime_key_reader`/`strategy_key_reader`/`sector_key_reader`/`symbol_key_reader`; cubos declarados `sin_regimen`/`sin_sector`/`sin_version`/`sin_simbolo`), `capture_study` (captura de MFE y premio dejado en la mesa + `reversedCount`), `mae_severity` (perdedores peores que `-1R`/`-1.25R`/`-1.5R`), `concentration` (peso de los `k` mejores/peores + `classification`) y `build_dia_d_attribution_artifact` (**reutiliza** `build_value_scorecard` y `excursions`; no duplica umbrales). |
| **2 · CLI** | `apps/api-python/scripts/v2_92_dia_d_attribution.py` | Reutiliza el harness de `v2_91` (`_resolve_window`/`_run_pass`), carga el `PIT` histórico, corre **una** pasada y agrega. Sonda `probe` con `truncationReason`/`windowFallback` (sin plan B silencioso) y flag `--check-against <longitudinal.json>` que cruza el resumen con el sello de `v2.88.38` y declara `crossCheck.evidenceDrift`. |
| **3 · Tests** | `packages/py/application/tests/test_dia_d_attribution.py` | **12** tests puros: identidad del payoff, `None` con muestra vacía, agrupación determinista con fallbacks declarados, captura/reversals, severidad de MAE, concentración `broad`/`concentrated`, artefacto determinista. |
| **4 · Sello** | `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` | Bump `2.11.38-beta → 2.11.39-beta`; `meta.bump` de `v2_89`/`v2_90`/`v2_91`/`v2_92` alineado (guardián extendido con `v2_92`); **re-anclaje del freeze** al árbol funcional del sello. |

---

## 1. Afirmaciones falsables

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|
| **Payoff** | La esperanza se descompone EXACTAMENTE en acierto/ganancia/pérdida. | Fallar la identidad ⇒ `identityGap` ≠ 0. | Medido `identityGap = 1.11e-16`. |
| **Reproducción** | El resumen recomputado == el sellado por `v2.88.38`. | Cambiar la muestra/el motor ⇒ drift. | `crossCheck.evidenceDrift = false` (5/5 claves). |
| **Dimensiones** | Cada cubo declara `n` y expectativa; un cubo sin muestra NO aparece; una etiqueta ausente cae en `sin_*`. | Rellenar un hueco con `0`; inventar etiqueta. | `bySector`/`bySymbol` del artefacto. |
| **Excursión** | La severidad de MAE y la captura de MFE se miden sólo con dato medible; sin muestra ⇒ `None`. | Rellenar con `0`; presentar D1 como intradía. | `maeSeverity`, `capture` del artefacto. |
| **Concentración** | El signo de la ventana NO descansa en un ciclo: retirar el peor NO voltea a positivo. | `expectancyWithoutWorstR > 0` ⇒ `concentrated`. | Medido `broad` (`-0.4588`). |
| **Δ motor** | Ningún fichero de motor tocado; `replay-repro` no se mueve. | Editar motor o el artefacto. | `git diff` de alcance (abajo). |

---

## 2. Atribución 2022 (corrida **medida**, PostgreSQL real)

Comando: `uv run --no-sync python apps/api-python/scripts/v2_92_dia_d_attribution.py --year 2022 --universe pit --check-against operability_runs/dia-d-auto/longitudinal-2022-01-03_2022-12-30.json`

| Bloque | Valor |
|---|---|
| Ventana | pedida `2022-01-03 → 2022-12-30` (257 días, 218 operables); efectiva `2021-09-15 → 2023-01-27` (`history=90d`, `horizon=20d`); `353` ticks; `truncationReason=null`; `windowFallback=null` |
| Universo (`PIT`) | `instrumentsConsidered=303`, `membersMaterialized=76`, `excludedNoBars=227`, `historicalMode=true`; `watchSource="pit"`, `survivorBiasRisk=false` |
| Resumen | `REFUTED` (`negative_expectancy`) · `evidenceQuality=STRONG` · `expectancyR=-0.5011`, `hitRate=0.3396`, `realizedRTotal=-26.5604`, `53` ciclos |
| **Payoff** | `wins=18`, `losses=35`, `winRate=0.3396`, `avgWinR=+1.1731`, `avgLossR=-1.3622`, `payoffRatio=0.8612`, `identityGap=1.11e-16` |
| **byRegime** | `high_vol` único cubo (`n=53`, `-0.5011`) ⇒ **monorégimen** (no discrimina) |
| **byStrategy** | `v283-window-a` único cubo (`n=53`, `-0.5011`) |
| **bySector** | Consumer Cyclical `27`/`-0.4987` · Consumer Defensive `7`/`-0.5076` · Financial Services `2`/`+0.4621` · Healthcare `8`/`-0.3819` · Industrials `9`/`-0.8234` |
| **Captura MFE** | medidos `51` (2 `n/d`); `medianCapture=-1.26`, `meanCapture=-12.12`, `meanLeftOnTableR=+1.741`, `medianLeftOnTableR=+1.689`, `reversedCount=7` |
| **Severidad MAE** | `measured=53`, `meanMaeR=-1.3880`, `minMaeR=-3.1945`; `< -1R`: **35** (`66.0 %`) · `< -1.25R`: **30** (`56.6 %`) · `< -1.5R`: **26** (`49.1 %`) |
| **Concentración** | `classification=broad`; peores `5`: `-11.4485`; mejores `5`: `+12.0686`; `expectancyWithoutWorstR=-0.4588`; `signFlipsWithoutWorst=false` |
| **crossCheck** | `evidenceDrift=false` (`expectancyR`/`hitRate`/`measuredCycles`/`verdict`/`evidenceQuality` idénticos al sello `v2.88.38`) |

**Lectura honesta (descriptiva, no causal).** El `-0.5011 R/ciclo` es **ancho**, no de unos pocos ciclos:
retirar el peor ciclo deja la expectativa en `-0.4588` (sigue negativa) y el resultado se reparte por
sectores (4 de 5 negativos; el único positivo, `Financial Services`, tiene `n=2` ⇒ **no concluyente**).
Los números señalan **dos hechos estructurales**, no una causalidad:

1. **El payoff no paga el acierto.** `payoffRatio=0.861` exige un acierto de equilibrio `≈ 1/(1+0.861)
   = 53.7 %`; el medido es `34.0 %`. Con `35` perdedores de `53`, la asimetría favorable no compensa.
2. **Las pérdidas superan el riesgo nominal.** `avgLossR=-1.3622` y **66.0 %** de los ciclos con MAE
   peor que `-1R` (hasta `-3.19R`): en D1 el stop **no** acota la pérdida a `-1R` (hueco/salto o
   secuencia desfavorable). En paralelo, `reversedCount=7` ciclos llegaron a `≥ +1R` de MFE y
   cerraron `≤ 0`: hay premio dado la vuelta.

**Lo que NO dice:** ni que el motor AUTO pierda siempre, ni que otra ventana dé lo mismo, ni que el
PAPER real coincida. `2022` es **monorégimen** (`high_vol`) y **una sola estrategia** ⇒ `byRegime`
y `byStrategy` no discriminan aquí; la señal está en la descomposición del payoff, la severidad de
MAE y la concentración. La ventana PAPER real (`P3-2`/`P3-3`) **no** se sustituye.

Artefacto en `operability_runs/dia-d-auto/attribution-2022-01-03_2022-12-30.json` (**gitignoreado**, no viaja en el repo).

---

## 3. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest test_dia_d_auto.py test_dia_d_auto_feedback.py test_universe_point_in_time.py test_universe_point_in_time_catalog.py test_dia_d_longitudinal.py test_dia_d_attribution.py test_auto_dia_d_route.py test_auto_dia_d_feedback_route.py test_dia_d_bump_guard.py -q` | **108 passed** (`v2.88.38` = 96; **+12** del agregado de atribución) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (653 ficheros, 3568 dependencias) |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 525 source files** (`v2.88.38` = 524) |
| `pnpm --filter @bolsa/web contract:check` | **`contract:check OK`** |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |
| smoke `v2_92 --year 2022 --universe pit --check-against …` | **OK**; resumen idéntico al sello (`evidenceDrift=false`) |
| `git diff --name-only HEAD -- apps packages` | sólo `dia_d_attribution.py`, `test_dia_d_attribution.py`, `v2_92_…py`, `test_dia_d_bump_guard.py`, `meta.bump` de `v2_89/90/91` ⇒ **`Δ motor = 0`** |

---

## 4. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **La atribución es DESCRIPTIVA, no causal:** descompone la muestra medida; no explica el mercado ni el futuro.
4. **Monorégimen:** `byRegime` colapsa a `high_vol` (2022). `byStrategy` a `v283-window-a`. No es una prueba multirregimen.
5. **Sector aproximado:** es el del catálogo **actual**, no point-in-time; `Financial Services` (`n=2`) no concluye.
6. **MAE/MFE entre días (D1):** el día de entrada puede incluir excursión previa al fill.
7. **`CONFIRMED` sigue reservado** a evidencia PAPER real: el veredicto de esta ventana es `REFUTED`.
8. **No sustituye la ventana PAPER real:** `P3-2`/`P3-3` siguen **ABIERTAS**.

---

## 5. Comandos (reproducir)

```bash
# Tests puros + rutas + guardián
python -m pytest packages/py/application/tests/test_dia_d_attribution.py \
  packages/py/application/tests/test_dia_d_longitudinal.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# Gates de CI (comandos EXACTOS)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor
pnpm window:test

# Atribución OOS 2022 (requiere PostgreSQL; artefacto gitignoreado)
uv run --no-sync python apps/api-python/scripts/v2_92_dia_d_attribution.py --year 2022 --universe pit --json \
  --check-against operability_runs/dia-d-auto/longitudinal-2022-01-03_2022-12-30.json \
  --out operability_runs/dia-d-auto/attribution-2022-01-03_2022-12-30.json
```

---

## 6. Sello

- **Versión:** `2.11.39-beta` (base `2.11.38-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/dia_d_attribution.py`, `packages/py/application/tests/test_dia_d_attribution.py`, `apps/api-python/scripts/v2_92_dia_d_attribution.py`, `docs/engineering/evidence/v2.88.39/README.md`, `docs/engineering/plan-v2-88-39-dia-d-atribucion-oos-2022-2026-10-03.md`.
- **Ficheros modificados:** `apps/api-python/scripts/v2_89_dia_d_auto_replay.py`, `v2_90_dia_d_feedback.py`, `v2_91_dia_d_longitudinal.py` (sólo `meta.bump`), `apps/api-python/tests/test_dia_d_bump_guard.py` (+`v2_92`), `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Freeze del runner (re-anclado):** el sello mueve `apps`/`packages`; `WINDOW_CONFIG` (`scripts/lib/window-forward.mjs`) se **re-ancló** al árbol del commit **funcional** `fe3128c9` (base `41b69265` + DÍA-D-3a): `apps` = `2fd946c4850dfcb7ad638c6c37175b7bb5821730`, `packages` = `fdcae617202251d0d6a82585246106eefca2d294`. El pin vive en `scripts/`, así que editarlo **no** mueve a su vez el árbol congelado, y `git rev-parse "HEAD:apps" "HEAD:packages"` coincide con el pin en el tag. Pin anterior (sello `v2.88.38-beta`, commit `20dae993`): `apps` `0a936c3c…` / `packages` `6387fdfa…`.
- **CI DE TAG:** **VERDE** — `Release tag CI` run [`37126514646`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37126514646) (`11 jobs success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4432 passed / 45 skipped`; `frontend` `237` ficheros / `1359` tests; `lifecycle-pg` verde; `replay-repro` `REPRODUCIDO` `1E3ADAC2…` / `3 340 728 B`). **Nota (P3):** el primer intento del job `frontend` cayó por un test **flaky** pre-existente (`apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.test.tsx`: el `waitFor` de las filas puede resolverse desde el `artifact` del *list* antes de que se dispare la query de detalle); quedó verde en el rerun y **no** procede de este sello (no se tocó `apps/web`).
