# Entrega a auditoría externa (MIA) — `v2.88.60-beta` · `AUTO · Contrato`: **F5 — Resolución DÍA-D por `cycleId`** (índice `cycles[]` + veredicto agregado)

> **Fecha:** 2026-10-06 · **Producto:** `V2.88.60-beta` · **Package:** `2.11.60-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.59-beta` (tag → `a970b2e0`, `Release tag CI` [`37423991541`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37423991541) **VERDE**).
> **Unidad de esta auditoría:** la deuda **P1 `F-S1`** (explicación DÍA-D resuelta por `symbol`, no por `cycleId`) de la [auditoría UI AUTO para usuario básico](./auditoria-ui-auto-cockpit-2026-10-05.md) §3.2/§5.1 y la [spec §7](./spec-auto-cockpit-usuario-basico-2026-10-05.md). Se implementa la fase backend **F5**.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; **no** se toca `replay_oos.RoundTrip.to_dict`. **El contrato HTTP SÍ cambia** (a diferencia de `v2.88.59`).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.60/README.md`](./evidence/v2.88.60/README.md) (`§0`–`§7`).
> **Nota de auditabilidad (declarada).** Este sello se entrega con **commits locales** (funcional + `chore(window)` + `docs(seal)`); **no** se ha creado ni empujado el tag `v2.88.60-beta` a petición explícita. Por tanto **no existe aún** `Release tag CI` que citar: la cita del CI viajará en el tag/`Release` cuando se promocione (límite estructural conocido).

**Sello dirigido (declarado).** Mandato: **cerrar `F-S1`** sin romper el modelo estadístico. La decisión de diseño es **mantener el veredicto OOS agregado por instrumento** (suelo `n >= 5`) y añadir un **índice de ciclos** que permita resolver *a qué valor pertenece* cada ciclo, declarando si la resolución fue exacta (`cycleId`) o parcial (`instrumento`).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la resolución DÍA-D por identidad de ciclo, de punta a punta:

1. **Artefacto `dia-d-feedback-v2` (dominio puro).** `build_cycle_index(...)` emite `cycles[]` (una fila por ciclo: `cycleId`, `symbol`, `entryDay`, `exitDay`, `strategyVersion`, `realizedR`), **deduplicado y ordenado**; un ciclo **sin `cycleId`** se **omite** (`UNKNOWN ≠ 0`) y cae al fallback. `build_dia_d_feedback_artifact(..., cycles=())` sella el índice.
2. **Productor (CLI).** `v2_90_dia_d_feedback.py` construye el índice desde los `roundTrips` **ya serializados** y lo proyecta al artefacto; **no** re-deriva ni toca `to_dict`. `meta.bump` → `2.11.60-beta` (los 9 CLI `v2_89`…`v2_97` alineados por el bump guard).
3. **Contrato HTTP.** `DiaDFeedbackCycleDto` + `cycles[]` en `DiaDFeedbackDto` (`/auto/dia-d-feedback`).
4. **UI honesta.** `resolveExplanationForCycle(...)` resuelve por `cycleId` (si el ciclo está en el índice) o por instrumento (fallback **declarado PARCIAL**) y la EXPLANATION añade el hecho `resolución` + nota acorde.

**NO se entrega**, y se declara:

- **NO** se re-granula el veredicto OOS por ciclo (`n = 1` rompería el suelo de muestra); `cycles[]` **sólo desambigua**.
- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`); **no** se toca `replay_oos.RoundTrip.to_dict`.
- **NO** hay migración (Alembic head intacto).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se cierra **`PortfolioDecision`** (`UI52-02`), el barrido `axe` en vivo (`F-A2`), `F-S2`/`F-S3`, el **PIT histórico institucional** ni **Execution Analysis**.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Índice de ciclos (dominio) | `packages/py/application/.../dia_d_auto_feedback.py` | `SCHEMA_VERSION = "dia-d-feedback-v2"`; `_normalize_cycle_row` + `build_cycle_index` (dedup/orden, omite sin clave, huecos `None`); `build_dia_d_feedback_artifact(..., cycles=())`. |
| Productor | `apps/api-python/scripts/v2_90_dia_d_feedback.py` | `cycles = build_cycle_index(round_trips, days=window_days)` + `meta.bump` → `2.11.60-beta`. |
| Contrato HTTP | `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py` | `DiaDFeedbackCycleDto` + `DiaDFeedbackDto.cycles` + proyección en `_project()`. |
| Contrato generado | `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts` | `DiaDFeedbackCycleDto` y `cycles[]` (ver §7 de la evidencia: re-sincronizado a mano por *App Control*). |
| Modelo compartido | `packages/shared/src/cognitive/auto-operation-story.ts` | `AutoOperationStoryExplanationResolution`; hecho `resolución` + nota honesta (exacta por `cycleId` / **PARCIAL** por instrumento). |
| UI | `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` | Helper puro `resolveExplanationForCycle(...)`. |
| Tests | `test_dia_d_auto_feedback.py`, `test_auto_dia_d_feedback_route.py`, `auto-operation-story.test.ts`, `auto-operation-story-panel.test.tsx`, `dia-d-auto-feedback-panel.test.tsx` | Cubren las siete afirmaciones falsables de `§1` (evidencia). |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.60-beta`) en `v2_89`…`v2_97`. |

---

## 3. Medición (cifras heredadas de `v2.88.50`/`v2.88.51`, NO re-medidas)

Sin cambio de motor **ni de muestra**, este sello no re-corre el pipeline. Se **citan** las cifras vigentes de [`v2.88.50`](./evidence/v2.88.50/README.md):

| Métrica (`v2.88.50`) | Valor |
| --- | --- |
| `route` (A/C, `dia-d-thesis-exit-v5` capa v7) | `{materializado: 19, orden_creada_sin_fill: 23}` ⇒ **A = `0`**, **C = `23`** |
| `stopEvaluatedOnTouch` / `deciderRanOnTouch` | **`42/42`** / **`42/42`** |
| `candidate` (`structuralStopCandidate`) | **`42/42`** |
| `THESIS_EXIT` (n) | **`42`** |
| Expectancy bruta global | `-0.7150` |
| Banda global de R | `[-17.290, +19.328]`, `crossesZeroR = true`, **`pointCitable = false`** |

> **Nota `F5`:** el índice `cycles[]` **no** altera estas cifras: el veredicto OOS se sigue emitiendo **por instrumento** (`values[]`); `cycles[]` sólo mapea `cycleId` → instrumento para resolver la explicación.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`F-A2` — barrido `axe` en vivo de `/auto/*` no ejecutado.** Remediación: spec `axe` propio para `/auto/*` en el siguiente sello de UI.
- **`F-S2`/`F-S3` (P3):** densidad tipográfica (`text-[11px]`) e `h1` crudo de ausencia.
- **Regranular el veredicto por `(instrumento × strategyVersion)`** y **veredicto por ciclo**: descartados (rompen el suelo de muestra `n >= 5`).
- **`PortfolioDecision` durable (`UI52-02`)**, **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): pre-existentes.
- **Método local (declarado).** En esta máquina, la política *App Control* de Windows bloquea `python.exe` (`os error 4551`), por lo que `pytest`/`mypy`/`import-linter`/`test_dia_d_bump_guard.py`/`contract:check` **no** se ejecutaron por CLI. Los tests JS (Node) y `ruff check` (binario nativo) sí. **El contrato se re-sincronizó a mano** replicando el patrón de los DTOs vecinos y **queda validado por el CI** (`contract:check` en el job `frontend`); si divergiera, el gate falla y el sello no promociona.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `@bolsa/shared` build + `vitest` | **813 passed** (`97` ficheros) |
| `@bolsa/web` `vitest` | **1442 passed** (`249` ficheros; **+4** sobre `v2.88.59`) |
| `@bolsa/web` `typecheck` / `lint` | limpio · **0 errores** (`23` warnings pre-existentes) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | limpio (ficheros tocados) |
| `pytest` (application + api-python) / `mypy` / `import-linter` / `bump guard` | **no ejecutables en local** (App Control); **los ejecuta el CI** |
| `contract:check` | **no ejecutable en local** (App Control); contrato re-sincronizado a mano; **el CI lo valida** |

---

## 6. Sello

- **Producto:** `V2.88.60-beta`. **Package:** `2.11.60-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Con cambio de contrato HTTP** (`/auto/dia-d-feedback`).
- **Añadidos:** `docs/engineering/evidence/v2.88.60/README.md`, este documento.
- **Modificados:** `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py` (+ test), `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), `apps/api-python/scripts/v2_90_dia_d_feedback.py` y `v2_89`/`v2_91`…`v2_97` (`meta.bump`), `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py`, `apps/api-python/tests/test_auto_dia_d_feedback_route.py`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` (+ test), `apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.test.tsx`, `package.json` (`2.11.60-beta`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md`, `docs/engineering/auditoria-ui-auto-cockpit-2026-10-05.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `71ab00df` | `apps` `d7e6da64…` / `packages` `b482a276…` |
| Re-anclaje del freeze de la ventana (`chore`) | `a8f941e8` | pin `commit: 71ab00df` (no mueve árbol) |
| **Commit del sello** (`docs(seal)`) | `6e4db583` | (mismos árboles que el funcional) |

- **Tag:** **pendiente** — `v2.88.60-beta` **no** se ha creado ni empujado (a petición: commits locales, sin push ni tag). Cuando se promocione, el `Release tag CI` validará `replay-repro` (⇒ `Δ motor = 0`) y los jobs `python`/`frontend`/`shared`/`decision-spine`/`lifecycle-pg`/`security`/`certify`.

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.60/README.md` en el árbol del commit funcional `71ab00df` (o `main`).
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición heredada, hallazgos abiertos y gates.
3. **Base.** `docs/engineering/evidence/v2.88.59/README.md` y `docs/engineering/entrega-auditoria-externa-mia-v2.88.59-2026-10-06.md`.
4. **Freeze.** `git rev-parse "71ab00df:apps" "71ab00df:packages"` debe devolver **exactamente** `d7e6da64…` / `b482a276…` (el pin `scripts/lib/window-forward.mjs` los cita).
5. **Reproducción local (opcional).**
   ```bash
   git checkout 71ab00df
   uv run --no-sync python -m pytest packages/py/application/tests/test_dia_d_auto_feedback.py \
     apps/api-python/tests/test_auto_dia_d_feedback_route.py apps/api-python/tests/test_dia_d_bump_guard.py -q
   pnpm --filter @bolsa/shared build && pnpm --filter @bolsa/shared test
   pnpm --filter @bolsa/web test
   pnpm --filter @bolsa/web typecheck
   pnpm --filter @bolsa/web lint
   pnpm --filter @bolsa/web contract:gen && pnpm --filter @bolsa/web contract:check
   ```
6. **Qué falsaría el sello:** que `cycles[]` salga desordenado/duplicado o invente `cycleId` en un ciclo sin clave · que un hueco se rellene con `0` · que un artefacto `v1` sin `cycles` rompa la proyección · que el fallback afirme que la explicación es de *esa* operación · que se emita veredicto por ciclo · que el diff toque motor o `RoundTrip.to_dict` · que `contract:check` no reproduzca el contrato.
