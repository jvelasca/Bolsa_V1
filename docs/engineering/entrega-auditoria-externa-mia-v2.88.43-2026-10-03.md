# Entrega a auditoría externa (MIA) — `v2.88.43-beta` · AUTO · **DÍA-D-3b.3: bootstrap de ciclos (banda TOTAL venue × sampling)**

> **Fecha:** 2026-10-03 · **Producto:** V2.88.43-beta · **Package:** `2.11.43-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.42-beta` (`v2_94`, banda del **sorteo del venue**). **Este sello añade la segunda mitad**: el **muestreo de ciclos** (bootstrap no paramétrico) y compone ambos ejes.
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`, **nunca** `0`.
> **`Δ decisión motor = 0`.** Ningún fichero de motor tocado; el artefacto congelado de `replay-repro` no se mueve.
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.43/README.md`](./evidence/v2.88.43/README.md).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** una **medida de incertidumbre de dos ejes** para el instrumento DÍA-D AUTO:

1. **venue** — varianza entre los `K` re-sorteos del venue (heredada de `v2.88.42`).
2. **sampling** — bootstrap no paramétrico sobre los ciclos observados (con reemplazo, `n` fijo), promediado sobre los sorteos.
3. **total** — `totalVar = venueVar + samplingVar` (ley de varianza total), con banda TOTAL por percentiles 2.5/97.5 del pool `K × B` y citabilidad por eje.

**No se entrega**, y se declara: el bootstrap **no** mide la independencia de mercado ni el futuro; **no** sustituye la ventana PAPER real (`P3-2`/`P3-3` siguen **ABIERTAS**); `CONFIRMED` sigue reservado a evidencia PAPER; `K` sorteos **no** son `K` muestras independientes de mercado.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
|---|---|---|
| Módulo puro | `packages/py/application/src/bolsa_application/dia_d_multi_sampling.py` | `build_cycle_ledger` + `build_sampling_artifact`; `SCHEMA_VERSION="dia-d-multi-sampling-v1"`; PRNG propio SplitMix64 (sin `numpy`). |
| Ledger | `dia-d-multi-cycle-ledger-v1` | una fila por ciclo (`realizedR`/MAE/MFE + etiquetas), persistido por sorteo. |
| `v2_93` | `apps/api-python/scripts/v2_93_dia_d_multi.py` | `--cycles-out <path>` escribe el ledger; el artefacto `dia-d-multi-v1` **no cambia de forma**. |
| `v2_94` | `apps/api-python/scripts/v2_94_dia_d_multi_band.py` | `--cycles` propaga `draw-XX/multi-cycles.json`; **sin el flag, salida byte-idéntica a `v2.88.42`**. |
| `v2_95` | `apps/api-python/scripts/v2_95_dia_d_multi_bootstrap.py` | consumidor puro de `--out-dir`; venue + sampling + total; `--resamples`/`--seed`/`--check-against`/`--out`. |
| Guardián | `apps/api-python/tests/test_dia_d_bump_guard.py` | `meta.bump == package.json.version` extendido a `v2_95`. |
| Tests | `packages/py/application/tests/test_dia_d_multi_sampling.py` | `14` tests (determinismo, `None`≠`0`, varianza total, citabilidad, fragilidad, cruce venue). |

---

## 3. Medición real (PostgreSQL, offline)

`K = 12` sorteos del venue (`≈ 35 min`), `B = 2000` resamples (`≈ 5 s`), semilla `20261003`. Cobertura idéntica a `v2.88.42`: `2022-2025` medidos `12/12`, `2021` **vacío** `12/12`, `2026` **no medido** `12/12` (`sin_universo_pit`).

### 3.1 Resultado central

- **GLOBAL:** `expectancyR` media `-0.0283`; banda del venue `[-0.1813, +0.1248]`; banda **TOTAL** `[-0.3784, +0.3401]` (**cruza cero**); `realizedRTotal` venue `[-16.859, +10.857]` → total `[-35.065, +28.569]`.
- **`varianceShare` GLOBAL: venue `0.2734` / sampling `0.7266`** ⇒ **el muestreo de ciclos domina** (~73 %).
- **`totalPointCitable = False`**; `venuePointCitable = False`; `samplingPointCitable = False`.

### 3.2 El hallazgo duro: la citabilidad se pierde al añadir el muestreo

| Cubo | `v2.88.42` (venue) | **`v2.88.43` (total)** | Comentario |
|---|---|---|---|
| `2022` | **citable** `[-0.6406, -0.1391]` | **NO citable** `[-0.8702, +0.0783]` | el muestreo cruza el cero |
| `range` | **citable** `[+0.3748, +1.4795]` | **NO citable** `[-0.0082, +2.0327]` | `fragile: few_cycles_per_draw` |
| `high_vol` | **citable** `[-0.3278, -0.0149]` | **NO citable** `[-0.5165, +0.2183]` | sampling no citable |
| `2024` | citable | **citable** `[+0.1057, +2.5317]` | única celda que sobrevive los tres ejes |
| `2023 × trend_down` | frágil (`n=2`) | **`fragile` declarado** | `samplingVar=0` ⇒ banda engañosamente estrecha |

La deuda metodológica que señaló la auditoría de `v2.88.42` (`2023 × trend_down`, `n=2`) queda ahora **declarada** por `fragility` (`drawsWithCell < MIN_DRAWS_FOR_BAND` / `few_cycles_per_draw`), no oculta.

### 3.3 Autochequeo (fidelidad del instrumento)

- La banda del venue reconstruida por `v2_95` es **byte a byte** la de `v2.88.42` (`global`/`byYear`/`byRegime`/`byOperationalRegime`/`byYearByRegime`/`coverage` idénticos; el único cambio es `meta.bump`).
- Sorteo 0 (producción) contra el sello `v2.88.41`: `expectancyR=-0.0094`, `93` ciclos, `REFUTED`, `STRONG`, `evidenceDrift=False`.
- Determinismo: dos corridas de `v2_95` byte a byte idénticas (`sha256 0AF78E48…`, `91 360 B`).

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
|---|---|
| `uv run pytest … (DÍA-D subset) -q` | **110 passed** (**+14**) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `uv run mypy … application/src apps/api-python/src --follow-imports=silent` | **528 source files, no issues** |
| `pnpm --filter @bolsa/web contract:check` / `typecheck` | **OK / sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **14 passed** |
| `pnpm window:test` | **25/25** |
| `git status --porcelain -- <motor>` | **vacío** ⇒ `Δ motor = 0` |

---

## 5. Límites declarados (no se cierran aquí)

1. `Δ motor = 0`; sin migración; no se mueve ningún umbral ni allocation.
2. El bootstrap mide **muestreo de ciclos**; no es independencia de mercado ni futuro.
3. Venue y sampling se combinan como **ejes ortogonales**; la interacción real se aproxima por el pool `K × B`.
4. `K` sorteos **no** son `K` muestras independientes de mercado.
5. **REPLAY/OOS ≠ PAPER**; `CONFIRMED` reservado; `P3-2`/`P3-3` abiertas.
6. `2026` no medido y `2021` vacío se heredan de `v2.88.41`/`v2.88.42`.
7. `B` es la resolución del bootstrap; cambiar `B`/semilla cambia la banda numérica (no la estructura).
8. PIT, sector actual (no point-in-time) y MAE/MFE entre días D1 se heredan declarados.

---

## 6. Sello

- **Producto:** `V2.88.43-beta`. **Package:** `2.11.43-beta`. **Sin migración.**
- **Tag:** `v2.88.43-beta` **PENDIENTE** de push/CI (se cita aquí tras el `Release tag CI`).
- **Ficheros añadidos:** módulo + test + `v2_95` + `evidence/v2.88.43/README.md`.
- **Ficheros modificados:** `v2_89..v2_94` (`meta.bump`; `v2_93`/`v2_94` flags), bump guard, `package.json`, `CHANGELOG.md`, `CURRENT_SYSTEM.md`, `versioning.md`.
- **Commits locales:** funcional `4e8eec0f`; re-anclaje del freeze del runner `c71f85ba` (fijado al árbol de `4e8eec0f`).
- **Tag:** `v2.88.43-beta` **PENDIENTE** de push/CI.
