# Evidencia `v2.88.164-beta` — la auditoría de detección cierra 16 de sus 21 criterios

## 1. Qué publica este sello

Sello de **remediación** posterior y acotado a `v2.88.163-beta`. Aplica los hallazgos de
[`auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md`](../../auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md)
y su [`verificación`](../../verificacion-auditoria-deteccion-compras-ventas-2026-10-26.md).
Cubre **25 commits** (`v2.88.163-beta..sello`), **52 ficheros**, +6 236/−164.

- **`Δ motor ≠ 0`** acotado a la **evaluación de señal** (B-3: `gated` sale del libro) y a la
  **decisión de salida** (S-2: una sola tabla de salidas protectoras).
- **`Δ decisión ≠ 0`** en el camino ACTIVE (B-1/B-3/B-5) y en posiciones con tesis invalidada.
- **`Δ contrato HTTP` aditivo**: `AutoOpsJobSlotDto` en el DTO de `ops-jobs`;
  `openapi.json`/`schema.d.ts` regenerados (231 rutas / 495 esquemas). El `contract:check` estaba
  **rojo** en el árbol de partida y este sello lo cierra.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Bump** `2.11.163-beta` → `2.11.164-beta` (+ `meta.bump` de los **13** CLIs).

## 2. Los doce frentes

| Frente | Qué estaba mal | Qué se publicó |
| --- | --- | --- |
| **B-1 / B-6** | El scan cortaba por `MIN_SCAN_BARS = 50` plano; un preset sin warmup desaparecía del recuento | `preset_evaluability` mide el warmup **sobre la serie** (profundidad 1/2); umbrales de los **21** presets de 1 a **201**; el scan emite `warmup_insufficient: …` y el decisor declara el motivo en `memo` |
| **B-3** | `gated` replayaba la ventana: una posición abierta **antes** no podía salir | `assume_long` + `long_by_symbol` (callable) ⇒ `HOLD`→`SELL` con libro; sin re-entrada; libro ilegible ⇒ `HOLD` |
| **P1-12b** | Un scan vacío pintaba «Sin señales» aunque no se hubiera evaluado | `scan-silence.ts` clasifica `not_evaluable` / `insufficient_data` / `other`; prefijo estable exportado en `@bolsa/shared` (**14** pruebas) |
| **O-6** | El journal no decía **con qué dato** se decidió | `featureSource` (`real` sólo si **todas** las barras son completas) y `signalWindowBars` en el `payload`; lo no medido se omite |
| **S-1** | Un `TIME_STOP` vencido era `none` para F5 y `full_exit` para el AUTO | `_ACTIONABLE_BY_STATUS`: F5 resuelve por **sugerencia** (`TRIGGERED` ⇒ `full_exit`/`reduce`; `ARMED` ⇒ `protect`) |
| **S-2** | `THESIS_INVALIDATION` cubría riesgo en F5 y no en la decisión: la posición sobrevivía a su invalidación | `exit_plan.PROTECTIVE_EXIT_REASONS` como tabla única, consumida por las dos capas |
| **S-3** | `EXIT_PENDING` se sellaba **al decidir**, sin orden | `_v2_note_exit_intent` / `_v2_confirm_exit_emitted` / `_v2_flush_unemitted_exits` (`exit_not_emitted`) |
| **O-1 / O-2** | Un settle que lanzaba sólo dejaba un log; el modo estructural no se publicaba | `settlement_failed` contado y journalizado; `structural`/`structuralOrders` en el parte del día |
| **T-1 / T-2** | Nadie declaraba quién drena `scan_jobs`; el scan diario dormía **antes** del primer trabajo | `scan_queue_health` (`scan_queue_stalled` con acción si `pending` ≥ 300 s), primer tick inmediato y dedupe **durable** por SQL |
| **S-6** | F5 no se consultaba en el worker AUTO | `review_auto_exit` + `PositionManagerResult.exit_plan`; `exit_permission` declarado con `exemption = auto_sim_exit_precedence` y `blocksExit: false` |
| **B-5** | `ACTIVE_STRATEGY=1` + `SIGNAL=0` ⇒ `HOLD` **mudo** | `hold_reason` tipificado + evento propio `auto_active_strategy_hold`, una vez por `(símbolo, motivo, barra)`; **no** infla `vetoCounted` |
| **CI / contrato** | `test_scan_queue_health_pg.py` competía por el esquema en el job offline | Job offline lo ignora; `lifecycle-pg` lo ejecuta con `SCAN_QUEUE_PG_REQUIRED=1` y guard anti-skip |

## 3. Trazabilidad de la auditoría

| Estado | Criterios |
| --- | --- |
| **Implementados (16/21)** | `B-1`, `B-2`, `B-3`, `B-4`, `B-5`, `B-6`, `O-1`, `O-2`, `O-5`, `O-6`, `S-1`, `S-2`, `S-3`, `S-6`, `T-1`, `T-2` |
| **Criterio escrito, sin prueba ejecutada (5/21)** | `S-4`, `S-5`, `O-3`, `O-4`, `T-3` |

Ningún hallazgo llega a **E3**. La evidencia es **E1** (hermética), con **E2** parcial en `S-6`
(banco PG del CI) y `T-1` (`test_scan_queue_health_pg` con gate).

## 4. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `packages/py/application` | **2944 passed** |
| `packages/py/analytics` + `packages/py/infrastructure` | **1547 passed** (ver fallo declarado) |
| `apps/api-python` offline (`-m "not integration"`) | **1405 passed**, 12 deseleccionadas |
| `apps/web` (`vitest`) | **2371 passed / 317 ficheros** |
| `packages/shared` (`vitest`) | **855 passed / 99 ficheros** (+1 todo) |
| `pnpm typecheck` | **4/4 OK** |
| `pnpm lint` | **0 errores** (23 avisos preexistentes) |
| `contract:gen` / `contract:check` | **OK** (aditivo: `AutoOpsJobSlotDto`) |
| `ruff` / `mypy` (gate de CI) / `import-linter` | limpio / **573 ficheros sin issues** / **4 kept, 0 broken** |
| `pnpm window:test` | **50 passed** |
| Guardián de bump | **2 passed** |

**Fallo declarado (no atribuido).** `infrastructure/tests/chaos/test_multi_portfolio_ledger_sequence.py::
test_same_account_two_portfolios_concurrent_ledger_sequence` (`ValueError: Cartera no encontrada`)
es una prueba de **concurrencia real** que comparte la misma base con la suite de `api-python`
lanzada en paralelo. **Re-ejecutado en aislamiento ⇒ `1 passed in 4.36s`.**

## 5. Cómo auditar este sello

```bash
git clone --branch v2.88.164-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1 && git rev-parse HEAD
```

| Comprobación | Dónde |
| --- | --- |
| Versión del monorepo | `package.json` ⇒ `2.11.164-beta` |
| `meta.bump` de los 13 CLIs | `uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` ⇒ **2 passed** |
| Migración | `alembic heads` ⇒ `058_estudio_daily_proposals` |
| Contrato | `pnpm contract:check` ⇒ **OK** |
| Freeze de la ventana | `node scripts/window-pin.mjs --check` ⇒ **freeze OK** |

## 6. Cierre POST-TAG

Pendiente de ejecutar al cerrar este apartado: `Release tag CI` del tag `v2.88.164-beta`, jobs
verdes, `certify`, `replay-repro` y `freeze OK` sobre el commit del sello. Se añade aquí **después**
de que exista el run, sin placeholders.
