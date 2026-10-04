# Entrega a auditoría externa (MIA) — `v2.88.44-beta` · AUTO · **DÍA-D-3c: de dónde nace la pérdida (mecanismo × coste × entrada)**

> **Fecha:** 2026-10-04 · **Producto:** V2.88.44-beta · **Package:** `2.11.44-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.43-beta` (banda TOTAL venue × sampling). **Este sello añade la atribución de causa**: *por qué* se pierde, no sólo *cuánto*.
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`, **nunca** `0`; el **neto** sólo se afirma con fricción `COMPLETE` (si no, es un **suelo** declarado, jamás el bruto disfrazado de neto).
> **`Δ decisión motor = 0`.** Ningún fichero de motor tocado; el artefacto congelado de `replay-repro` no se mueve.
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.44/README.md`](./evidence/v2.88.44/README.md).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** una **descomposición de la pérdida en tres ejes**, sobre el mismo replay hermético por sorteo del venue (`K = 12`), sin tocar el motor:

1. **Mecanismo de salida** — qué `day_exit_reason` cierra cada ciclo (`STOP_EJECUTADO`, `TARGET_1`, `TARGET_2`, `TRAILING`, `TIME_EXIT`, `THESIS_EXIT`, `REGIME_EXIT`, `RISK_EXIT`, `KILL_SWITCH`, `PORTFOLIO_RISK`, `EXIT_REQUESTED`, `MANUAL`, `SIN_MECANISMO`) y `R` bruto/neto por etiqueta.
2. **Coste aplicado** — `R` bruto vs neto, fricción en `R` y en divisa; declaración explícita de si el neto es un **suelo**.
3. **Calidad de entrada** — excursión adversa temprana (MAE en las primeras `3` barras D1) y **slippage** señal→ejecución (`bps`).

**No se entrega**, y se declara: el mecanismo es el **motivo decisorio** del plan, no la trayectoria; `frictionR` es **aproximada** (divisa→`R` por riesgo por ciclo); MAE es **entre días** (`D1`), no intradía; `Σ` por mecanismo **no** cuadra con el global (§3.5); **REPLAY/OOS ≠ PAPER** (`P3-2`/`P3-3` siguen **ABIERTAS**); ciclos **no IID** sigue **P3**; `CONFIRMED` reservado a evidencia PAPER.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| Clasificador puro | `packages/py/application/src/bolsa_application/dia_d_exit_mechanism.py` | mapea `day_exit_reason` → mecanismo canónico con **precedencia determinista** (stop > trailing > T1/T2 > time > tesis > riesgo > manual; sin empates). |
| Módulo puro | `packages/py/application/src/bolsa_application/dia_d_loss_origin.py` | `build_loss_origin_artifact`; `SCHEMA_VERSION="dia-d-loss-origin-v1"`; pliega los `K` ledgers en 3 ejes + venue dispersion + `fragility`. |
| Ledger v2 | `dia-d-multi-cycle-ledger-v2` | campos **aditivos**: `exitMechanism`, `exitEvidence`, `frictionCost`, `frictionR`, `frictionMeasurement`, `netRealizedR`, `entryAdverseR`, `entryAdverseWindowDays`, `entryAdverseGap`, `entrySlippageBps`, `entrySlippageGap` (v2_95 sigue leyendo `realizedR/year/regime/operationalRegime`). |
| Excursión temprana | `dia_d_longitudinal.py` | `DEFAULT_ENTRY_WINDOW_DAYS = 3` + `early_excursion_for_cycle(...)`. |
| Costura inerte | `v2_87_replay_oos_durable_cycle.py` | `capture_cycle_detail: bool = False`; si está activo, captura `cost_rows` (fills con `cycle_id`/`reference_mid`) y `close_rows` (`position_close.reason` por `execution_id`). Con `False` el replay es idéntico salvo un `if`. |
| Propagación | `v2_91_dia_d_longitudinal.py` · `v2_93_dia_d_multi.py` · `v2_94_dia_d_multi_band.py` | `--cycle-detail` y `--entry-window-days`; `v2_94` propaga por sorteo. |
| CLI | `apps/api-python/scripts/v2_96_dia_d_loss_origin.py` | consumidor puro de `--out-dir`; escribe `loss-origin-YYYY_YYYY.json`; `--check-against`. |
| Guardián | `apps/api-python/tests/test_dia_d_bump_guard.py` | `meta.bump == package.json.version` extendido a `v2_96`. |
| Tests | `packages/py/application/tests/test_dia_d_loss_origin.py` | `9` tests (taxonomía, precedencia, ledger v2, `PARTIAL→None`, `None != 0`, plegado, determinismo). |

---

## 3. Medición real (PostgreSQL, offline)

`K = 12` sorteos del venue, años `2022-2025`, `1074` ciclos (`1058` con fricción `COMPLETE`).

### 3.1 El número que cambia la lectura

- **Bruto global `-2.9462 R`** → **neto global `-8.0580 R` (suelo)**. La fricción (`4.0994 R`/sorteo; `3 117.52` de divisa) **más que dobla** la pérdida: el motor no pierde (sólo) por equivocarse de dirección, pierde por **pagar** para operar.
- `frictionRMean` por ciclo `0.0458 R`; `netIsLowerBound = true` (`16` ciclos sin fricción `COMPLETE`).

### 3.2 Mecanismo de salida (`byExitMechanism`)

| Mecanismo | Ciclos | R bruto total | Expectancy bruta | R neto total | Expectancy neta | HitRate |
| --- | --- | --- | --- | --- | --- | --- |
| `STOP_EJECUTADO` | `1003` (93.4 %) | `-0.7186` | `-0.0034` | `-5.3355` | `-0.0598` | `0.4925` |
| `THESIS_EXIT` | `38` (3.5 %) | `-2.3462` | `-0.7087` | `-2.5012` | `-0.7525` | `0.0833` |
| `TIME_EXIT` | `28` (2.6 %) | `-0.3157` | `-0.0897` | `-0.4297` | `-0.1337` | `0.3690` |
| `SIN_MECANISMO` | `5` (0.5 %) | `+0.5730` | `+0.5730` | `None` (suelo) | `None` | `0.8000` |

**Hallazgo:** el bucket **dominante** (stop, `93.4 %`) tiene expectancy bruta **~0** (`-0.0034 R`): no es un sangrado por movimiento, es el punto donde se paga la fricción. El **grueso del bruto negativo** lo aportan los **`THESIS_EXIT`** (`38` ciclos, `-0.7087 R/ciclo`, `hitRate` `8.3 %`).

### 3.3 Coste aplicado (`costImpact`)

| Métrica | Media (`12` sorteos) | min | max |
| --- | --- | --- | --- |
| `realizedRGrossTotal` | `-2.9462` | `-16.8590` | `+10.8568` |
| `realizedRNetTotal` (suelo) | `-8.0580` | `-23.7367` | `+6.3491` |
| `frictionRTotal` | `4.0994` | `3.3097` | `4.7815` |
| `frictionCostTotal` | `3 117.5229` | `2 395.9216` | `3 461.5970` |

### 3.4 Calidad de entrada (`entryQuality`)

- MAE D1 (`3` barras): media `-0.7115 R`, mediana `-0.5784 R`; `55.87 %` `< -0.5 R`; `27.84 %` `< -1.0 R`.
- Slippage señal→ejecución: media `10.38 bps`, mediana `10.51 bps`, `100 %` `> 0`.

**Lectura:** más de la mitad de los ciclos se pone en contra `> 0.5 R` antes de poder trabajar; la ejecución siempre paga. La pérdida nace en la **entrada** y en el **coste**, no en un stop prematuro.

### 3.5 Aviso de suma (declarado)

`Σ` brutos por mecanismo `-2.8075` ≠ bruto global `-2.9462` (dif. `-0.1387`, `~4.7 %`), porque cada bucket se pliega sobre los sorteos en que aparece (`drawsWithCell`). **Se declara; no se cuadra a mano.**

### 3.6 Autochequeo y determinismo

- Banda del venue reconstruida **byte a byte** la de `v2.88.43` (`bands`/`validity`/`coverage` idénticos; única diferencia `meta.bump` y la codificación del `note` heredado).
- Sorteo 0 contra el sello `v2.88.41`: `expectancyR=-0.0094`, `93` ciclos, `REFUTED`, `STRONG`, `evidenceDrift=False`.
- Dos corridas de `v2_96` byte a byte idénticas (`sha256 118DBF65…`, `11 089 B`).

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
| --- | --- |
| `uv run pytest … (DÍA-D subset) -q` | **120 passed** (**+10**) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `uv run mypy … application/src apps/api-python/src --follow-imports=silent` | sin errores |
| `pnpm --filter @bolsa/web contract:check` | **OK** (sin cambios de DTO) |
| `pnpm window:test` | **25/25** |
| `git status --porcelain -- <motor>` | **vacío** ⇒ `Δ motor = 0` |
| A/B de la costura `v2_87` (antiguo vs nuevo, mismo entorno+fixture) | **byte a byte idéntico** (`sha256 C208B2DE…`, `3 453 282 B`) ⇒ `capture_cycle_detail=False` es inerte |

---

## 5. Límites declarados (no se cierran aquí)

1. `Δ motor = 0`; sin migración; no se mueve ningún umbral ni allocation.
2. Mecanismo = **motivo decisorio** (`day_exit_reason`), no trayectoria ni causalidad.
3. `frictionR` es **aproximada** (divisa→`R` por riesgo del ciclo); falta de stop/qty ⇒ hueco, no `0`.
4. MAE **entre días** (`D1`); el día de entrada puede incluir excursión previa al fill.
5. `Σ` por mecanismo ≠ global (§3.5), declarado.
6. La fricción se mide contra el **mid del simulador**, no contra un precio de broker real.
7. **REPLAY/OOS ≠ PAPER**; `CONFIRMED` reservado; `P3-2`/`P3-3` abiertas.
8. `2026` no medido y `2021` vacío se heredan de `v2.88.41`/`v2.88.43`.
9. Cubos con `n` pequeño quedan `fragile` (`few_cycles_per_draw`/`net_partial`), nunca cita fuerte.

---

## 6. Sello

- **Producto:** `V2.88.44-beta`. **Package:** `2.11.44-beta`. **Sin migración.**
- **Tag:** `v2.88.44-beta` **PENDIENTE** de push/CI (se cita aquí tras el `Release tag CI`).
- **Ficheros añadidos:** `dia_d_exit_mechanism.py`, `dia_d_loss_origin.py`, `v2_96_dia_d_loss_origin.py`, `test_dia_d_loss_origin.py`, `evidence/v2.88.44/README.md`.
- **Ficheros modificados:** `dia_d_longitudinal.py`, `dia_d_multi_sampling.py`, `v2_87`/`v2_91`/`v2_93`/`v2_94` (costura + flags), `v2_89`/`v2_90`/`v2_92`/`v2_95` (`meta.bump`), bump guard, `test_dia_d_multi_sampling.py`, `package.json`, `CHANGELOG.md`, `CURRENT_SYSTEM.md`, `versioning.md`.
- **Commits locales:** funcional `50240f97`; re-anclaje del freeze del runner `7a1efac4` (fijado al árbol de `50240f97`).
- **Tag:** `v2.88.44-beta` **PENDIENTE** de push/CI.
