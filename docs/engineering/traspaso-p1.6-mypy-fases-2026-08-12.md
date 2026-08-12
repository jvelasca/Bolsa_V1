# Traspaso — P1.6 mypy por fases: gate CI **BLOQUEANTE** full-tree (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5
> (fase P1.6, deuda registrada en [traspaso-f4-arquitectura-python-2026-08-11.md](./traspaso-f4-arquitectura-python-2026-08-11.md) §6 →
> mypy resto del árbol por fases, y planificada en
> [plan-p1.6-mypy-fases-2026-08-12.md](./plan-p1.6-mypy-fases-2026-08-12.md)).
> **Alcance:** `packages/py/domain/src` · `packages/py/market/src` · `packages/py/infrastructure/src` ·
> `apps/api-python/src` (el target exacto del paso `Mypy` de `.github/workflows/python-ci.yml`).
> **Regla del hilo:** comportamiento idéntico (D5), cero features, no cambiar el wire / DTOs.
> **Estado:** **COMPLETADO + 4 PRs MERGEADOS 2026-08-12** (#45 domain · #46 market · #47 api-python · #48
> infrastructure) + **gate mypy BLOQUEANTE** full-tree (PR #49). `Success: no issues found in 243 source files`
> (exit 0). Working tree limpio.

---

## 1. Objetivo de la fase

Cerrar la deuda de tipado **mypy preexistente** (~448 errores en ~94 ficheros) para que el paso `Mypy` del CI
**deje de ser `continue-on-error: true`** y se convierta en un **gate BLOQUEANTE full-tree** sobre los 4 árboles
que ya gestiona CI (`domain` · `market` · `infrastructure` · `apps/api-python`). Resultado final: **0 errores en
243 ficheros fuente** (`Success: no issues found in 243 source files`, exit 0).

## 2. Medición inicial (2026-08-12)

`uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src
--follow-imports=silent` → **448 errores en ~94 ficheros** (checked 243 source files).

| Lote | Paquete / app                | Errores | Rama                                        |
| ---- | ---------------------------- | ------- | ------------------------------------------- |
| L1   | `packages/py/domain`         | 6       | `stage/p1.6-mypy-domain-2026-08-12`         |
| L2   | `packages/py/market`         | 32      | `stage/p1.6-mypy-market-2026-08-12`         |
| L3   | `packages/py/infrastructure` | 119     | `stage/p1.6-mypy-infrastructure-2026-08-12` |
| L4   | `apps/api-python`            | 291     | `stage/p1.6-mypy-api-python-2026-08-12`     |

Principales hotspots: `database/models/tables.py` (66) · `schemas/research.py` (25) · `schemas/instruments.py`
(25) · `market/piotroski.py` (17) · `schemas/backtests.py` (17) · `market/yahoo_client.py` (12).

## 3. Catálogo de errores y patrones de fix

| Categoría        | Patrón a resolver                                                            | Fix aplicado                                                                                             |
| ---------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `type-arg`       | `dict` / `list` sin parámetro genérico                                       | Parametrizar como `dict[str, ...]` / `list[...]`                                                         |
| `arg-type`       | Argumentos que pueden ser `None` pasados donde se espera un tipo no nulo     | Guards `X                                                                                                | None` previos (comprobación de no-nulo antes del uso) |
| `no-untyped-def` | Funciones sin anotación de tipos / `def f(...)` -> `None`                    | Añadir anotaciones `-> None` y tipos de parámetros                                                       |
| `Mapped[...]`    | Modelos SQLAlchemy 2.0 en `database/models/tables.py` sin el mapeo de plugin | Anotar columnas (incl. JSON/JSONB) con `Mapped[dict[str, Any]]` / `Mapped[list[Any]]` sin romper runtime |

Regla: ignorar `# type: ignore[code]` solo cuando no haya anotación limpia posible; no cambiar el wire.

## 4. Estrategia de ejecución

**4 subagentes en worktrees git aislados** (uno por paquete, con ramas disjuntas y ficheros disjuntos), para
evitar colisiones de archivos/rama en el checkout compartido (lección aprendida de un intento previo que lo
intentó en el checkout compartido):

| Worktree / rama                                                        | Paquete / app                |
| ---------------------------------------------------------------------- | ---------------------------- |
| `wt-mypy-domain` · `stage/p1.6-mypy-domain-2026-08-12`                 | `packages/py/domain`         |
| `wt-mypy-market` · `stage/p1.6-mypy-market-2026-08-12`                 | `packages/py/market`         |
| `wt-mypy-infrastructure` · `stage/p1.6-mypy-infrastructure-2026-08-12` | `packages/py/infrastructure` |
| `wt-mypy-api-python` · `stage/p1.6-mypy-api-python-2026-08-12`         | `apps/api-python`            |

Cada subagente: mypy de su paquete = 0 → ruff (config CI) limpio en lo tocado → pytest de su paquete sin
regresiones → commit `fix(types, <pkg>)` → push → PR → merge contra la base viva. Ficheros disjuntos → merge
limpio en cualquier orden.

## 5. Fases / PRs mergeados

| PR  | Paquete / app                | Estado     |
| --- | ---------------------------- | ---------- |
| #45 | `packages/py/domain`         | **MERGED** |
| #46 | `packages/py/market`         | **MERGED** |
| #47 | `apps/api-python`            | **MERGED** |
| #48 | `packages/py/infrastructure` | **MERGED** |

Tras #48, la base viva quedó en `441c590`.

## 6. Gate CI final (`python-ci.yml`)

El paso `Mypy` ahora es **BLOQUEANTE** (se retiró `continue-on-error: true`) full-tree:

```yml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src --follow-imports=silent
```

Se retiró además el paso intermedio `Mypy — gate scoped F4+F5b` (quedaba redundante). Esto lo mergeó el **PR #49**.

## 7. Batería combinada (rama de validación)

- `ruff check` → **0 errores** ✓
- `mypy` (4 árboles, `--follow-imports=silent`) → **0 errores en 243 files** ✓ (exit 0)
- `pytest` → **451 passed** ✓ (mismo criterio que el check `battery` de CI)

## 8. Cierre de la ola (2026-08-12)

Tras los 4 PRs de mypy, y para dejar la ola operativa, se mergearon además (mismo día):

- **#42** — traspaso de cierre de la ola (docs) + deuda priorizada.
- **#43** — fix auto-sync 404: `YahooSymbolNotFoundError` en `yahoo_client.py` · `SyncResult.retryable=False` en
  `sync_instrument.py` (propagado en `sync_scheduler.py`) · log a INFO en `auto_sync_worker.py` · tests en
  `test_sync_queue_retryable.py`. Su rama se rebaseó sobre la base para desbloquear el check `quality` por Ruff
  I001 en `scheduler_worker.py` (ya corregido en la base).
- **#49** — gate mypy **BLOQUEANTE** full-tree (+ retirada del gate scoped F4+F5b).

**Base viva final:** `stage/f1-integridad-financiera-2026-08-11` en `6a89f6c` · **0 PRs abiertos**.

## 9. Deuda / fuera de alcance (sin resolver aquí)

Registrada la visión global (remite a engineering-index §5/§9):

- **P1.9** API thin (hilo propio).
- **P1.3** auth full (D4, diferida).
- **F5a §6** openapi-fetch completo + reconciliar DTOs (`manifest`, `number`↔`integer`, unions).
- **P2.6** consolidar tipos web-only en `packages/shared` (duplicación TS↔Py restante).
- Si se decide extender el gate mypy a `application`/`analytics`/`ai` (no cubiertos hoy por el target de CI), en
  una fase posterior.

## 10. Verificación final

| Concepto                             | Resultado                                                                           |
| ------------------------------------ | ----------------------------------------------------------------------------------- |
| `mypy` full-tree (4 árboles)         | **0 errores en 243 files** · exit 0                                                 |
| `ruff check`                         | **0 errores**                                                                       |
| `pytest` (mismo criterio batería CI) | **451 passed**                                                                      |
| Paso `Mypy` de CI                    | **BLOQUEANTE** (sin `continue-on-error`) · PR #49                                   |
| PRs #45–#48                          | **MERGEADOS** en `stage/f1-integridad-financiera-2026-08-11` (#48 → base `441c590`) |
| Cierre de la ola                     | #42 docs · #43 fix auto-sync · #49 gate · base final `6a89f6c` · **0 PRs abiertos** |
| Working tree                         | limpio                                                                              |

### Texto de traspaso (pegable en el próximo chat)

> CONTEXTO INMEDIATO: P1.6 (deuda **mypy preexistente** por fases) **COMPLETADO + MERGEADO 2026-08-12** en
> `stage/f1-integridad-financiera-2026-08-11` (base viva `6a89f6c`).
>
> - **Objetivo cerrado**: el paso `Mypy` del CI deja `continue-on-error: true` y es ahora **gate BLOQUEANTE**
>   full-tree sobre `domain` · `market` · `infrastructure` · `apps/api-python`
>   (`uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src
--follow-imports=silent`). Se retiró además el paso intermedio `Mypy — gate scoped F4+F5b` (redundante).
> - **Medición inicial → final**: ~448 errores en ~94 ficheros → **0 errores en 243 source files**
>   (`Success: no issues found in 243 source files`, exit 0).
> - **Estrategia**: 4 subagentes en **git worktrees aislados** (`wt-mypy-domain/market/infrastructure/api-python`),
>   uno por paquete, ramas/ficheros disjuntos → merge limpio (lección de un intento previo en el checkout
>   compartido).
> - **Patterns de fix**: `type-arg` (`dict`/`list` sin genérico) · `arg-type` (guards `X | None`) ·
>   `no-untyped-def` · `Mapped[...]` en modelos SQLAlchemy 2.0 (`tables.py`).
> - **PRs #45–#48 MERGED** (domain · market · api-python · infrastructure; #48 → base `441c590`) · **PR #49**
>   gate bloqueante full-tree. Cierre de la ola: #42 docs + #43 fix auto-sync 404
>   (`YahooSymbolNotFoundError`, `SyncResult.retryable=False`, log INFO, tests; rebase para desbloquear quality
>   I001) + #49. Base final `6a89f6c`. **0 PRs abiertos**.
> - **Batería combinada**: ruff **0** · mypy **0/243** · pytest **451✓**.
>
> DEUDA REGISTRADA → fases posteriores (sin resolver):
>
> - **P1.9** API thin (hilo propio) · **P1.3** auth full (D4) · **F5a §6** openapi-fetch + reconciliar DTOs ·
>   **P2.6** consolidar tipos web-only · (opcional) extender gate mypy a `application`/`analytics`/`ai`.
>
> Lee PRIMERO: `docs/engineering/traspaso-p1.6-mypy-fases-2026-08-12.md` y sus fuentes
> (`plan-p1.6-mypy-fases-2026-08-12.md`, `traspaso-f4-arquitectura-python-2026-08-11.md` §6, `eng-index` §5).
> NO toques código fuera del alcance de la fase que se declare.
