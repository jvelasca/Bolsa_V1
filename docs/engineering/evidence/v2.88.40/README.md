# Evidencia cruda — `v2.88.40-beta` (AUTO · **DÍA-D-3a.1**: **corrección semántica de la ATRIBUCIÓN** — captura de MFE acotada, severidad de MAE por población y cross-check tolerante, sin tocar motor)

> **Objeto:** package **`2.11.40-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** **corrección del instrumento** (no capacidad) sobre **DÍA-D AUTO**, advisory y read-only. Cierra **A39-01/A39-02/A39-03** de la auditoría de `v2.88.39` sin cambiar el motor: **`Δ decisión motor = 0`**.
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py`) se toca, y **el artefacto congelado de `replay-repro` no se mueve**. La muestra OOS 2022 es **idéntica** a la sellada por `v2.88.39` (`crossCheck.evidenceDrift=false`).
> **Padre:** [`evidence/v2.88.39/README.md`](../v2.88.39/README.md) (atribución del OOS 2022).
> **Nomenclatura:** `AUTO engineering release = v2.88.40-beta` · `application package = 2.11.40-beta` · `SCHEMA_VERSION = dia-d-attribution-v2`.

---

## 0. Qué corrige este sello

| # | Hallazgo | Qué se cambia |
|---|---|---|
| **A39-01 🔴** | `capture_study` medía `realized / mfe` sin acotar: ratios **negativos** y explosión con `MFE → 0+` (evidencia `v2.88.39`: `meanCapture=-12.12`, `medianCapture=-1.26`). | La captura se define sobre el resultado **no negativo** (`capturedR = max(realizedR, 0)`): el ratio vive en `[0, +inf)` y **no** cambia de signo. Nuevo payload `captureRatio`/`capturedR`/`leftOnTableR`/`reversedCount`; `captureRatio > 1` se **declara** en `aboveOneCount`, no se recorta. |
| **A39-02 🔴** | `mae_severity` afirmaba medir "perdedores" pero contaba **cualquier** ciclo con MAE bajo el umbral (no conocía `realizedR`). | La firma pasa a `mae_severity(round_trips, *, excursions_by_cycle, thresholds)` y une el MAE con su ciclo por `cycle_key`. Publica `populations`: **ALL / WINNERS / LOSERS**, cada una con `cycles`/`meanMaeR`/`minMaeR`/`breaches`. |
| **A39-03 🟠** | El cross-check comparaba floats por igualdad exacta (`!=`), frágil para auditoría científica. | `expectancyR`/`hitRate` se comparan con `math.isclose` (`rel_tol=abs_tol=1e-12`); `measuredCycles`/`verdict`/`evidenceQuality` siguen por igualdad exacta. |

---

## 1. Afirmaciones falsables

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|
| **A39-01** | La captura vive en `[0, +inf)` y no explota con MFE diminuto. | Un `captureRatio` negativo o una media disparada por `MFE → 0+`. | Medido `captureRatio`: media `0.1429`, mediana `0.0`, máx `0.6237`, `aboveOneCount=0` (antes `meanCapture=-12.12`). |
| **A39-02** | La severidad de MAE se separa por población (ALL ≠ WINNERS ≠ LOSERS). | Un ganador con MAE `< -1R` que sólo aparezca en ALL. | `ALL` `< -1R` = `35/53` (**66.04 %**) frente a `LOSERS` = `33/35` (**94.29 %**) y `WINNERS` = `2/18` (**11.11 %**). |
| **A39-03** | El cross-check tolera residuo de coma flotante y sigue detectando drift material. | `evidenceDrift=true` por `-0.5011` vs `-0.5011000000000001`. | `evidenceDrift=false`, `driftedKeys=[]`, `5/5` claves idénticas a `v2.88.39`. |
| **Reproducción** | El resumen recomputado == el sellado por `v2.88.39`. | Cambiar la muestra/el motor ⇒ drift. | `crossCheck.evidenceDrift=false` (5/5 claves). |
| **Δ motor** | Ningún fichero de motor tocado; `replay-repro` no se mueve. | Editar motor o el artefacto. | `git diff` de alcance (abajo). |
| **Determinismo** | Dos corridas ⇒ payload idéntico (puro, sin reloj). | Aleatoriedad/relojes. | `test_artifact_is_deterministic_and_declares_dimensions`. |

---

## 2. Atribución 2022 corregida (corrida **medida**, PostgreSQL real)

Comando: `uv run --no-sync python apps/api-python/scripts/v2_92_dia_d_attribution.py --year 2022 --universe pit --check-against operability_runs/dia-d-auto/longitudinal-2022-01-03_2022-12-30.json`

| Bloque | Valor |
|---|---|
| Ventana | pedida `2022-01-03 → 2022-12-30` (257 días, 218 operables); efectiva `2021-09-15 → 2023-01-27` (`history=90d`, `horizon=20d`); `353` ticks; `truncationReason=null`; `windowFallback=null` |
| Universo (`PIT`) | `instrumentsConsidered=303`, `membersMaterialized=76`, `excludedNoBars=227`, `historicalMode=true`; `watchSource="pit"`, `survivorBiasRisk=false` |
| Resumen | `REFUTED` (`negative_expectancy`) · `evidenceQuality=STRONG` · `expectancyR=-0.5011`, `hitRate=0.3396`, `realizedRTotal=-26.5604`, `53` ciclos |
| **Payoff** | `wins=18`, `losses=35`, `avgWinR=+1.1731`, `avgLossR=-1.3622`, `payoffRatio=0.8612`, `identityGap=1.11e-16` |
| **Captura MFE (A39-01 corregido)** | medidos `51` (2 `n/d`); `captureRatio` media **`+0.1429`**, mediana **`0.0`**, máx **`0.6237`**, `aboveOneCount=0`; `capturedR` media **`+0.4141`** (mediana `0.0`); `leftOnTableR` media **`+0.8758`** (mediana `0.9882`); `reversedCount=7` |
| **Severidad MAE (A39-02 corregido)** | **ALL** (`n=53`, `meanMaeR=-1.3880`, `minMaeR=-3.1945`): `< -1R` **35** (`66.04 %`) · `< -1.25R` **30** (`56.60 %`) · `< -1.5R` **26** (`49.06 %`). **WINNERS** (`n=18`, `meanMaeR=-0.4810`, `minMaeR=-1.1316`): `< -1R` **2** (`11.11 %`) · `< -1.25R` `0` · `< -1.5R` `0`. **LOSERS** (`n=35`, `meanMaeR=-1.8544`, `minMaeR=-3.1945`): `< -1R` **33** (`94.29 %`) · `< -1.25R` **30** (`85.71 %`) · `< -1.5R` **26** (`74.29 %`) |
| **Concentración** | `classification=broad`; peores `5`: `-11.4485`; mejores `5`: `+12.0686`; `expectancyWithoutWorstR=-0.4588`; `signFlipsWithoutWorst=false` |
| **crossCheck** | `evidenceDrift=false`; `driftedKeys=[]` (`expectancyR`/`hitRate`/`measuredCycles`/`verdict`/`evidenceQuality` idénticos al sello `v2.88.39`) |

**Lectura honesta (descriptiva, no causal).** La corrección **cambia la interpretación** de los dos números que la auditoría señaló:

1. **La captura ya no está dominada por la definición matemática.** El `-12.12` de media desaparece: la mediana es `0.0` y la media `+0.143`. Es decir, un ciclo típico **capturó 0** del MFE (cerró en `<= 0` tras dar premio) y el `leftOnTableR` medio fue `+0.876 R`: hay premio disponible que no se monetiza, pero medido sin ratios negativos ni explosiones.
2. **El `66 %` NO es "perdedores que superaron el stop".** Es la fracción de **TODOS** los ciclos con MAE `< -1R`. Separado: **`94.29 %` de los PERDEDORES** atravesó `-1R` y **`11.11 %` de los GANADORES** (2 de 18) también lo hizo. Los dos ganadores con MAE `< -1R` (mínimo de ganador `-1.1316R`) confirman empíricamente el sesgo A39-02: contarlos como "perdedores" era incorrecto.

**Lo que NO dice:** ni que el motor AUTO pierda siempre, ni que otra ventana dé lo mismo, ni que el PAPER real coincida. `2022` es **monorégimen** (`high_vol`) y **una sola estrategia** ⇒ `byRegime` y `byStrategy` no discriminan aquí. La ventana PAPER real (`P3-2`/`P3-3`) **no** se sustituye.

Artefacto en `operability_runs/dia-d-auto/attribution-2022-01-03_2022-12-30.json` (**gitignoreado**, no viaja en el repo).

---

## 3. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest test_dia_d_auto.py test_dia_d_auto_feedback.py test_universe_point_in_time.py test_universe_point_in_time_catalog.py test_dia_d_longitudinal.py test_dia_d_attribution.py test_auto_dia_d_route.py test_auto_dia_d_feedback_route.py test_dia_d_bump_guard.py -q` | **112 passed** (`v2.88.39` = 108; **+4** de los tests que muerden de A39-01/A39-02) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (653 ficheros, 3568 dependencias) |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 525 source files** |
| `pnpm --filter @bolsa/web contract:check` | **`contract:check OK`** |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |
| smoke `v2_92 --year 2022 --universe pit --check-against …` | **OK**; resumen idéntico (`evidenceDrift=false`), captura y severidad por población corregidas |
| `git diff --name-only HEAD -- apps packages` | sólo `dia_d_attribution.py`, `test_dia_d_attribution.py`, `v2_92_…py`, `meta.bump` de `v2_89/90/91` ⇒ **`Δ motor = 0`** |

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
9. **Concentración:** `broad` sólo significa que quitar el peor ciclo **no** cambia el signo; no es una prueba de no-concentración. Las métricas ampliadas (`top1/top5/bottom shares`, HHI) quedan para una fase posterior.

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

# Atribución OOS 2022 corregida (requiere PostgreSQL; artefacto gitignoreado)
uv run --no-sync python apps/api-python/scripts/v2_92_dia_d_attribution.py --year 2022 --universe pit --json \
  --check-against operability_runs/dia-d-auto/longitudinal-2022-01-03_2022-12-30.json \
  --out operability_runs/dia-d-auto/attribution-2022-01-03_2022-12-30.json
```

---

## 6. Sello

- **Versión:** `2.11.40-beta` (base `2.11.39-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros modificados:** `packages/py/application/src/bolsa_application/dia_d_attribution.py` (captura + severidad por población + `SCHEMA_VERSION` v2 + límites), `packages/py/application/tests/test_dia_d_attribution.py` (+4 tests que muerden), `apps/api-python/scripts/v2_92_dia_d_attribution.py` (cross-check `isclose`, `_print_text`, `meta.bump`), `apps/api-python/scripts/v2_89|v2_90|v2_91…` (sólo `meta.bump`), `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **Ficheros añadidos:** `docs/engineering/evidence/v2.88.40/README.md`, `docs/engineering/plan-v2-88-40-dia-d-atribucion-correccion-2026-10-03.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Freeze del runner (re-anclado):** el sello mueve `apps`/`packages`; `WINDOW_CONFIG` (`scripts/lib/window-forward.mjs`) se **re-ancló** al árbol del commit funcional **`bd3c9cd9`**: `apps` = `22ca3e78ec4e18f69a11a9fd047dfb9db9f3f43f`, `packages` = `f169415e7c46c38ed15c53d0030a86480d49132b`. El pin vive en `scripts/`, así que editarlo **no** mueve a su vez el árbol congelado; `git rev-parse "HEAD:apps" "HEAD:packages"` coincide con el pin y el dry-run declara `freeze OK`. Pin anterior (sello `v2.88.39-beta`, commit `fe3128c9`): `apps` `2fd946c4…` / `packages` `fdcae617…`.
- **Tag:** `v2.88.40-beta` (anotado) → objeto `d113c3e7`, commit `8c971c00`; **creado LOCALMENTE**, push PENDIENTE.
- **CI DE TAG:** **PENDIENTE** (no se empujó desde esta sesión); se citará tras el push del tag.
