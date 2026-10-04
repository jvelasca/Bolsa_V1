# Entrega a auditoría externa (MIA) — `v2.88.45-beta` · AUTO · **DÍA-D-3d: quirófano del `THESIS_EXIT` (dónde viven los 38 ciclos)**

> **Fecha:** 2026-10-04 · **Producto:** V2.88.45-beta · **Package:** `2.11.45-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.44-beta` (origen de la pérdida: mecanismo × coste × entrada). **Este sello abre quirúrgicamente** el hallazgo de la base: *dónde viven* los `38` ciclos `THESIS_EXIT`, no *por qué* se invalidó la tesis.
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`, **nunca** `0`; el **neto** sólo se afirma con fricción `COMPLETE` (si no, es un **suelo** declarado, jamás el bruto disfrazado de neto).
> **`Δ decisión motor = 0`.** Ningún fichero de motor tocado; el artefacto congelado de `replay-repro` no se mueve.
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.45/README.md`](./evidence/v2.88.45/README.md).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** una **descomposición quirúrgica de los `38` ciclos `THESIS_EXIT`**, sobre el mismo replay hermético por sorteo del venue (`K = 12`), sin tocar el motor:

1. **Dónde viven** — `byStrategy` / `byDirection` / `byYear` / `byRegime` / `byOperationalRegime`.
2. **Cuándo se agotó** — `byAgeBucket` (días naturales `entryDay`→`exitDay`, en cubos duros `1-3`/`4-10`/`11-30`/`>30`/`unknown`).
3. **Cómo se movió** — excursión media/mediana `maeR`/`mfeR`, **captura del MFE** y `leftOnTableR`.
4. **Cómo entró** — excursión adversa temprana (MAE en las primeras `3` barras D1) y **slippage** señal→ejecución.
5. **Cuánto costó** — fricción en `R` y `R` neto (suelo declarado si falta fricción `COMPLETE`).
6. **Cuánta concentración** — símbolos distintos y clusters (top símbolo / top semana ISO).

**No se entrega**, y se declara: **no** responde a *por qué* se invalidó la tesis — el journal sólo publica el token **colapsado** `thesis_exit` (la traducción `THESIS_INVALIDATION → thesis_exit` borra la condición; recuperarla exige capturar el contexto del plan, fase futura). La edad es en **días naturales** (el replay es `D1`); la distancia al objetivo **no** es medible (el round trip no guarda el `target`, se aproxima con MFE/captura); la banda por cubo es la **dispersión entre sorteos**, no bootstrap ni incertidumbre de mercado; `Σ` por mecanismo ≠ global; **REPLAY/OOS ≠ PAPER** (`P3-2`/`P3-3` siguen **ABIERTAS**); ciclos **no IID** sigue **P3**; `CONFIRMED` reservado a evidencia PAPER. **Sin contrafactuales:** no se re-simulan salidas alternativas.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| Módulo puro | `packages/py/application/src/bolsa_application/dia_d_thesis_exit.py` | `build_thesis_exit_artifact`; `SCHEMA_VERSION="dia-d-thesis-exit-v1"`; filtra `exitMechanism=THESIS_EXIT` y pliega por dimensión con **venue dispersion** + `fragility`; geometría/entrada/coste/`rawReasonTokens`/`concentration`. |
| Ledger v3 | `dia-d-multi-cycle-ledger-v3` | campos **aditivos** sobre `-v2`: `strategyVersion` y `direction` (inferida de `stop` vs `entry`; `None` si la geometría es imposible). `v2_95` sigue leyendo `realizedR/year/regime/operationalRegime` (compatibilidad `-v1`/`-v2`). |
| Sellado de esquema | `v2_94_dia_d_multi_band.py` | `_DETAIL_LEDGER_SCHEMA = "dia-d-multi-cycle-ledger-v3"`: con `--cycle-detail` un ledger antiguo se **re-corre** (no se mezclan esquemas). |
| CLI | `apps/api-python/scripts/v2_97_dia_d_thesis_exit.py` | consumidor puro de `--out-dir` (`draw-XX/multi-cycles.json`); `--draws`, `--json`, `--out`; escribe `thesis-exit-YYYY_YYYY.json`. |
| Guardián | `apps/api-python/tests/test_dia_d_bump_guard.py` | `meta.bump == package.json.version` extendido a `v2_97`. |
| Tests | `packages/py/application/tests/test_dia_d_thesis_exit.py` | `14` tests (selección, dirección, captura acotada al MFE, **paridad con `capture_study`**, `PARTIAL→None`, cubos de edad, plegado, motivos crudos, concentración, determinismo, huecos, no-import de motor). |

**Semántica de captura (corregida en auditoría pre-sello):** la captura del MFE se define sobre el resultado **NO negativo** —`capturedR = max(realizedR, 0)`—, **idéntica** a `capture_study` (`v2.88.40`, `A39-01`): el ratio vive en `[0, +inf)`, no cambia de signo y `leftOnTableR = max(mfeR − capturedR, 0)` **nunca** supera el MFE. Hay un **test de paridad** que lo fija contra el canónico.

---

## 3. Medición real (PostgreSQL, offline)

`K = 12` sorteos del venue, años `2022-2025`, `38` ciclos `THESIS_EXIT` (**una** estrategia `v283-window-a`, **una** dirección `long`), `38` con fricción `COMPLETE`.

### 3.1 Global

| Métrica | Valor |
| --- | --- |
| R bruto total (por sorteo, media) | `-2.3462` |
| Expectancy bruta (entre sorteos) | `-0.7087` (`[min -1.2274, max -0.2095]`, `var 0.1056`) |
| HitRate | `0.0833` |
| R neto total (por sorteo, media) | `-2.5012` (medido, **no** suelo) |
| Expectancy neta | `-0.7525` |
| Fricción media por sorteo | `0.0438 R` |
| MAE media / mediana | `-1.4029 R` / `-1.3499 R` |
| MFE media / mediana | `+0.6672 R` / `+0.3689 R` |
| Captura del MFE (media / mediana) | `0.0449` / `0.0` (medida en `34` ciclos; `4` con `mfeR <= 0` son hueco) |
| `leftOnTableR` media / mediana | `+0.6269 R` / `+0.3979 R` (acotada por el MFE; nunca lo supera) |
| Excursión adversa temprana (D1, 3 barras) | media `-0.9505 R`; `< -0.5R` `76,3 %`; `< -1.0R` `52,6 %` |
| Slippage señal→ejecución | media `10,56 bps` / mediana `10,51 bps` |

### 3.2 Dónde y cuándo viven (con lectura)

| Dimensión | Cubo | Sorteos | Ciclos | Expectancy bruta | MAE media |
| --- | --- | --- | --- | --- | --- |
| Estrategia | `v283-window-a` | — | `38` | `-0.7087` | `-1.4029` |
| Dirección | `long` | — | `38` | `-0.7087` | `-1.4029` |
| Edad | `1-3` | `1/12` | `1` | `-0.8236` | `-1.3495` |
| Edad | `4-10` | `10/12` | `20` | `-0.8153` | `-1.3747` |
| Edad | `11-30` | `8/12` | `14` | `-0.8767` | `-1.5709` |
| Edad | `>30` | `3/12` | `3` | `+0.7375` | `-0.8247` |
| Año | `2022` | `10/12` | `19` | `-0.7800` | — |
| Año | `2025` | `9/12` | `15` | `-0.7091` | — |
| Régimen | `high_vol` | `11/12` | `34` | `-0.6819` | `-1.3947` |
| Régimen | `trend_down` | `3/12` | `4` | `-0.7727` | `-1.4728` |

**Lectura honesta:**
- **No hay subpoblaciones que rescaten el bucket:** los `38` son una sola estrategia y una sola dirección; el `-0.7087` es la expectativa de TODO el cubo.
- **La pérdida vive en la edad media:** los ciclos de `4-30` días cargan la expectativa (`-0.8153`/`-0.8767`); los `>30` son positivos pero **sólo `3` ciclos** (declarados `fragile`); el `1-3` tiene `1` ciclo (`fragile`).
- **La excursión adversa es severa:** MAE media `-1.4029 R` — **peor** que la media global del replay (`-0.7115 R` en `v2.88.44`), con `76 %` de ciclos por debajo de `-0.5 R` en las primeras `3` barras D1.
- **Había MFE que no se capturó:** `leftOnTableR` `+0.63 R` sobre un MFE medio `+0.67 R`, captura media `0.0449` (mediana `0.0`). La tesis se invalida cuando ya había ido a favor y se devuelve casi todo el premio medido.
- **Concentración moderada:** `9` símbolos distintos, top símbolo `26,3 %`, top semana `2025-W12` `21,1 %` (ninguno explica >50 %).

### 3.3 Autochequeo y determinismo

- El **global reproduce** `v2.88.44` (`expectancyR` bruta `-0.7087`, `38` ciclos) — la capa v3 es aditiva.
- Dos corridas de `v2_97` byte a byte idénticas (`sha256 09AC71BD63EA967C22D9869A1A6D6CD6ACCD53FDCCDED7538257C40E7984A71F`, `63 551 B`).

### 3.4 Auditoría **pre-sello** (interna, antes de este sello)

| Revisor | Resultado |
| --- | --- |
| `Bugbot` | **1 hallazgo (medium), corregido:** `_capture`/`_left_on_table` usaban `realizedR` en crudo (captura negativa posible y `leftOnTableR` inflado por `|pérdida|`, superaba el MFE — la incoherencia interna `leftOnTableR 1.3464 > MFE 0.6672`). Ahora calcan `capture_study` (`A39-01`) con **test de paridad**; los números de §3 se **re-midieron** con el arreglo. |
| `Security review` | **Sin hallazgos:** capa pura/read-only, sin secretos, sin deserialización insegura (`json.loads` de artefactos locales del propio operador), sin ampliar la frontera de confianza, fail-closed ante ledger ausente. |

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
| --- | --- |
| `uv run pytest … (DÍA-D subset) -q` | **135 passed** (**+15**) |
| `uv run pytest packages/py/application/tests/test_dia_d_thesis_exit.py -q` | **14 passed** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (`659` ficheros) |
| `uv run mypy … application/src apps/api-python/src --follow-imports=silent` | sin errores (`531` source files) |
| `pnpm --filter @bolsa/web contract:check` | **OK** (sin cambios de DTO) |
| `pnpm window:test` | **25/25** |
| Determinismo `v2_97` | byte a byte idéntico (`sha256 09AC71BD…`, `63 551 B`) |
| `git status --porcelain -- <motor>` | **vacío** ⇒ `Δ motor = 0` |

---

## 5. Límites declarados (no se cierran aquí)

1. `Δ motor = 0`; sin migración; no se mueve ningún umbral ni allocation; sin contrafactuales.
2. **La condición de invalidación NO está capturada:** `rawReasonTokens = {thesis_exit: 38}` es el token colapsado (fase futura).
3. Edad en **días naturales** (replay `D1`); el día de entrada puede incluir movimiento previo al fill.
4. Distancia al objetivo **no** medible; se aproxima con MFE/captura.
5. Sector diferido (requeriría plumbing nuevo; el catálogo no es `PIT`).
6. `n` pequeño (`38` ciclos en `11/12` sorteos) ⇒ **todos** los cubos `fragile`; ninguna celda se cita como fuerte.
7. `Σ` por mecanismo ≠ global, declarado (no se cuadra aquí).
8. Bootstrap no-IID (`block`/`regime-aware`) sigue **P3**.
9. **REPLAY/OOS ≠ PAPER**; `CONFIRMED` reservado; `P3-2`/`P3-3` abiertas.

---

## 6. Sello

- **Producto:** `V2.88.45-beta`. **Package:** `2.11.45-beta`. **Sin migración.**
- **Ficheros añadidos:** `dia_d_thesis_exit.py`, `v2_97_dia_d_thesis_exit.py`, `test_dia_d_thesis_exit.py`, `evidence/v2.88.45/README.md`, esta entrega.
- **Ficheros modificados:** `dia_d_multi_sampling.py` (ledger `-v3`), `v2_94` (`_DETAIL_LEDGER_SCHEMA`), `v2_89`/`v2_90`/`v2_91`/`v2_92`/`v2_93`/`v2_94`/`v2_95`/`v2_96`/`v2_97` (`meta.bump`), bump guard, `test_dia_d_multi_sampling.py`, `test_dia_d_loss_origin.py`, `package.json`, `CHANGELOG.md`, `CURRENT_SYSTEM.md`, `versioning.md`.
- **Tag / commits / CI:** se publican en el commit de docs de este sello (el CI de tag se cita al publicar).
