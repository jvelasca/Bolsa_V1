# Plan — `V2.88.38` / `AUTO-DIA-D`: primera ventana longitudinal OOS (universo PIT en uso)

> **AsOf:** 2026-10-03 · **Estado:** **APROBADA** (plan revisado por el propietario; pendiente de ejecución)
> · **Base:** `v2.88.37-beta` (`2.11.37-beta`, commit `3e5d2ffc`) · **Bump previsto:** `2.11.37-beta →
> 2.11.38-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**SIN migración**) · **`Δ motor = 0`**.

## 0. Por qué existe y cuándo se ejecuta

`v2.88.37` cerró la deuda funcional del `Universe(D)`: el contrato `PointInTimeUniverse` pasó a tener un
**proveedor real** (`CatalogPointInTimeUniverse`) y el sandbox DÍA-D (`v2_89`) lo consume tras
`--universe pit`. Lo que **todavía no existe** es la **medición**: estabilidad del edge OOS del motor AUTO
sobre una ventana de varias fechas `D`.

Esta fase produce esa primera medición: una **ventana longitudinal contigua acotada** sobre el **año
natural 2022** (el clúster operable del histórico), evaluada con el universo PIT ya sellado. Es evidencia de
**INVESTIGACIÓN** (viabilidad del edge OOS de replay), **no** de operación: **no** sustituye la ventana
PAPER real (`P3-2`/`P3-3` siguen **ABIERTAS**).

> **Decisión de secuencia (2026-10-03, propietario).** `v2.88.37` se **sella como checkpoint** (tag + CI
> verde) y el **objeto de la próxima auditoría externa es `v2.88.38-beta`** — que añade la **medición**
> sobre el proveedor, no sólo la capacidad. Auditar el proveedor aislado tendría superficie de falsación
> baja.

## 1. Decisiones fijadas (propietario, 2026-10-03)

- **Forma de la ventana:** **ventana contigua acotada** sobre el clúster operable (2022). Se **descarta**
  el replay multi-anual: `v2.86` midió que el libro de compromisos pendientes se infla y trunca la muestra.
- **Rango:** **año natural 2022 completo** (`2022-01-01..2022-12-31`), con **sonda de viabilidad** y
  **fallback** al máximo tramo contiguo operable si la corrida trunca (se declara, nunca se inventa).
- **MAE/MFE:** se **calculan** en la **capa nueva de agregación** (no en el scorer congelado).
- **Flujo:** **plan primero** (este documento), revisión y después implementación.

## 2. Diseño

```
bars D1 + instruments ──► CatalogPointInTimeUniverse (--universe pit)
                                   │
                                   ├─► universe_ids(provider, D_inicio) ──► watch
                                   │
census_operable_days ──► ventana 2022 (clúster operable) ──┐
                                                           ▼
                       v87._run_durable_replay (durable_cycle=True, hermético)
                                                           │
                                                           ▼
                       OOS por D (entryDay, D34-02)  ──►  agregado longitudinal (capa nueva)
                                                           │   expectancyR · hitRate · mediana
                                                           │   MAE/MFE · byYear · estabilidad
                                                           ▼
                       evidenceQuality (5/20/32) + veredicto OOS_SUPPORTED/MIXED/NOT_MEASURED
                                                           │
                                                           ▼
                       artefacto JSON determinista ──► evidence/v2.88.38
```

### 2.1 Piezas nuevas (sin tocar motor ni el artefacto congelado)

1. **`packages/py/application/src/bolsa_application/dia_d_longitudinal.py`** — módulo **puro** (sin I/O,
   sin reloj de pared) de agregación longitudinal:
   - `LongitudinalCycle` + `aggregate_longitudinal(rows, ...)`: recibe las filas OOS por `D` (con
     `entryDay`, `realizedR`, `open`, `unmeasured`) y produce `expectancyR` (media de R realizado),
     `hitRate` (`positiveShare`), mediana, distribución y estabilidad por sub-ventanas.
   - `excursions(bars_by_symbol, cycle)`: **MAE/MFE** por ciclo desde las barras D1 (`high`/`low`) entre
     `entry_day` y `exit_day`, normalizados por el riesgo al nacer (`|entry_price - stop|`).
   - `evidence_quality(n)` (umbrales `5/20/32`) y `verdict(...)` reutilizando la semántica de `v2_90`
     (`OOS_SUPPORTED`/`MIXED`/`NOT_MEASURED`).
2. **`apps/api-python/scripts/v2_91_dia_d_longitudinal.py`** — orquestador CLI: carga PIT, fija la
   ventana, corre **una** corrida del durable replay y agrega. Flags: `--year 2022` (o `--from/--to`),
   `--universe pit`, `--watch-size`, `--min-bars`, `--json`, `--out`.
3. **Tests puros** + **`docs/engineering/evidence/v2.88.38/README.md`**.

### 2.2 Restricciones críticas (por qué el diseño es así)

- **`replay-repro` congela** `artifacts/replay-oos-durable-v2.88.7.json` con assert de **SHA-256 y
  tamaño**. Por tanto **NO** se puede tocar `score_replay` / `RoundTrip.to_dict` / `v2_87`: la agregación
  nueva (incluidos MAE/MFE) vive **fuera** del camino congelado. La verificación del sello **repite**
  `replay-repro` y exige **byte a byte**.
- **El scorer no tiene MAE/MFE.** Se calculan en `dia_d_longitudinal` desde las barras D1. **Sesgo
  declarado:** los extremos son **entre días** (no intradía); el día de entrada puede incluir excursión
  previa al fill (aproximación D1). Se declara en `limits`.
- **Viabilidad medida, no supuesta:** la ventana incluye una **sonda** que reporta días detectados, días
  operables y ciclos ejecutados, y **declara** `truncation_reason` / `windowFallback` si la corrida no
  llega al final. Nunca se rellena la muestra ausente.
- **Un solo régimen:** 2022 es casi todo `HIGH_VOLATILITY` (el gate no lo veta); la "estabilidad" es
  **intra-2022**, no multirégimen. Se declara.

## 3. Afirmaciones falsables

1. **Universo PIT vs catálogo:** el watch PIT de 2022 incluye **≥1** instrumento **no activo hoy**
   (diferencia real; se publica el conjunto).
2. **Muestra OOS:** existe un `N` de ciclos atribuidos por `entryDay`; `expectancyR`, `hitRate`, mediana y
   **MAE/MFE** medidos; `NOT_MEASURED` si `N < 5` (`evidenceQuality` `5/20/32`).
3. **No truncación silenciosa:** la sonda **no** trunca en un solo episodio; si trunca,
   `windowFallback`/`truncationReason` lo declara.
4. **Determinismo:** dos corridas ⇒ **payload idéntico**.
5. **Instrumento congelado intacto:** `replay-repro` sigue **byte a byte** (SHA/tamaño del artefacto).

## 4. Sello y gates

- **Bump** `2.11.37-beta → 2.11.38-beta` (`package.json` + `meta.bump` de `v2_89`/`v2_90`/**`v2_91`**,
  guardián `test_dia_d_bump_guard`). **`CHANGELOG`**, `CURRENT_SYSTEM`, `versioning`, **evidencia** y
  **re-anclaje del freeze** (`WINDOW_CONFIG` al árbol del commit funcional). **SIN migración.**
- **Gates locales:** pytest (nuevos + vecinos), `ruff`, `lint-imports`, `mypy`, `contract:check`,
  `typecheck`, `vitest`, `window:test`, **smoke `v2_91 --year 2022 --universe pit`**, y comprobar
  `replay-repro` **byte a byte**.

## 5. Límites declarados (van en el artefacto y en el README)

- **No** sustituye la ventana PAPER real; no mide edge operativo, sólo OOS de **replay** hermético.
- La unidad es el **ciclo** (no el fill); huecos declarados, nunca rellenos con `0`.
- Cubos de calendario **no reproducibles** (reloj simulado).
- Un **único** régimen (intra-2022); sin multirégimen.
- MAE/MFE **entre días** con sesgo declarado en el día de entrada.
- **No** LIVE, **no** producción; `Δ motor = 0`.

## 6. Archivos

**Nuevos:** `apps/api-python/scripts/v2_91_dia_d_longitudinal.py`,
`packages/py/application/src/bolsa_application/dia_d_longitudinal.py`,
`packages/py/application/tests/test_dia_d_longitudinal.py`,
`docs/engineering/evidence/v2.88.38/README.md`, este plan.

**Modificados:** `apps/api-python/scripts/v2_89_dia_d_auto_replay.py`,
`apps/api-python/scripts/v2_90_dia_d_feedback.py` (sólo `meta.bump`), `package.json`, `CHANGELOG.md`,
`docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (freeze).

## 7. Riesgos abiertos

- **Truncación de la corrida anual** (libro/ciclo durable): mitigado por sonda + fallback declarado.
- **Muestra pequeña** (pocos ciclos en 2022): se declara `NOT_MEASURED`/`evidenceQuality` bajo; **no** se
  sube el umbral para "aprobar".
- **MAE/MFE con sesgo D1:** declarado; no se presenta como intradía.
