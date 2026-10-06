# Evidencia `v2.88.60-beta` — `AUTO · Contrato`: **F5 — Resolución DÍA-D por `cycleId`** (índice `cycles[]` + veredicto agregado)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.60-beta` · **Package:** `2.11.60-beta` · **AsOf:** 2026-10-06 · **Nature:** `Contrato / dominio + UI` · **Fase:** `AUTO F5 (resolución DÍA-D por cycleId)`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** `dia-d-feedback-v1` → **`dia-d-feedback-v2`** (añade el índice `cycles[]`). El resto sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **SÍ cambia** (`/auto/dia-d-feedback` expone `cycles[]`).

**Padre:** [`v2.88.59`](../v2.88.59/README.md) (tag → `a970b2e0`) → [`v2.88.58`](../v2.88.58/README.md).

**Decisión de alcance (declarada).** Entrada: la deuda **P1 `F-S1`** de la [auditoría UI AUTO para usuario básico](../../auditoria-ui-auto-cockpit-2026-10-05.md) §3.2/§5.1 y la [spec §7](../../spec-auto-cockpit-usuario-basico-2026-10-05.md): la explicación DÍA-D se resolvía por `symbol`, de modo que **dos ciclos del mismo instrumento compartían explicación sin declararlo**. Este slice implementa la fase backend **F5**: mantiene el **veredicto OOS agregado por instrumento** (suelo `n >= 5`) y añade un **índice de ciclos** que permite resolver **a qué valor pertenece** cada ciclo, declarando si la resolución fue exacta (`cycleId`) o parcial (`instrumento`).

---

## 0. Qué añade este sello (y qué NO)

**Añade** la resolución por identidad de ciclo, de punta a punta (dominio → contrato → UI):

1. **Artefacto `dia-d-feedback-v2`.** `dia_d_auto_feedback.py` incorpora `build_cycle_index(...)`, que emite **una fila por ciclo** (`cycleId`, `symbol`, `entryDay`, `exitDay`, `strategyVersion`, `realizedR`), **deduplicada y ordenada por `cycleId`**. `build_dia_d_feedback_artifact(..., cycles=())` sella `cycles[]` con el mismo determinismo byte a byte (`sort_keys=True`).
2. **Productor.** `v2_90_dia_d_feedback.py` construye el índice desde los `roundTrips` **ya serializados** por el replay y lo pasa al artefacto. **NO** se toca `replay_oos.RoundTrip.to_dict` (la huella `sha256 1E3ADAC2…` del `replay-repro` no se mueve).
3. **Contrato HTTP.** Nuevo `DiaDFeedbackCycleDto` y `cycles: list[DiaDFeedbackCycleDto]` en `DiaDFeedbackDto`; `openapi.json` y `schema.d.ts` actualizados.
4. **UI.** `auto-operation-story-panel.tsx` resuelve con el helper puro **`resolveExplanationForCycle(...)`**: por **`cycleId`** si el ciclo figura en el índice (usa los ejes del índice: `entryDay`/`strategyVersion`), o por **instrumento** (fallback) declarando la resolución **PARCIAL** vía `AutoOperationStoryExplanationResolution`.

**NO** re-granula el veredicto OOS por ciclo (sería `n = 1` sobre el suelo de muestra): `cycles[]` **sólo desambigua** a qué valor pertenece cada ciclo. **NO** toca motor ni umbrales. **NO** añade migración. **NO** cierra `PortfolioDecision` (`UI52-02`), el barrido `axe` en vivo (`F-A2`), `F-S2`/`F-S3`, PIT institucional ni Execution Analysis.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | El artefacto sella `schemaVersion = "dia-d-feedback-v2"` y expone `cycles[]` deduplicado y **ordenado por `cycleId`**. | Que el índice salga desordenado, con `cycleId` duplicado, o ausente. | §3; `test_dia_d_auto_feedback.py`. |
| **2** | Un ciclo **sin `cycleId`** se **omite** del índice (no se inventa la clave). | Que un ciclo sin clave reciba una `cycleId` sintética. | §3; `test_dia_d_auto_feedback.py`. |
| **3** | Un campo ausente en el ciclo viaja `None` (`UNKNOWN ≠ 0`); un `realizedR` ilegible (`inf`) es hueco. | Que un hueco se rellene con `0`. | §3; `test_dia_d_auto_feedback.py`. |
| **4** | La ruta `/auto/dia-d-feedback` proyecta `cycles[]`; un artefacto `v1` sin `cycles` ⇒ `[]` (compat). | Que un artefacto sin `cycles` rompa la proyección. | §3; `test_auto_dia_d_feedback_route.py`. |
| **5** | El panel resuelve por `cycleId` cuando el ciclo está en el índice y declara la resolución **exacta**; si no, por instrumento y declara **PARCIAL**. | Que el fallback afirme que la explicación es de *esa* operación. | §3; `auto-operation-story-panel.test.tsx`, `auto-operation-story.test.ts`. |
| **6** | El veredicto OOS **sigue agregado por instrumento** (`n >= 5`); no se emite veredicto por ciclo. | Que `cycles[]` emita veredicto/`n=1`. | §3; `DEFAULT_LIMITS` + `build_value_scorecard`. |
| **7** | `Δ motor = 0` y el `replay-repro` no se mueve. | Que el diff toque motor o `RoundTrip.to_dict`. | §6; `git diff` (cero ficheros de motor; `replay_oos.py` intacto). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `@bolsa/shared` build + `vitest` | **813 passed** (`97` ficheros; `auto-operation-story.test.ts` **+3**) |
| `@bolsa/web` `vitest` | **1442 passed** (`249` ficheros; **+4** sobre `v2.88.59`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `ruff check packages/py apps/api-python --config pyproject.toml` (config CI) | limpio (ficheros tocados) |
| `pytest` (application + api-python) / `mypy` / `import-linter` / `bump guard` | **no ejecutables en local** (*App Control*, `os error 4551`); **los ejecuta el CI** |
| `contract:check` | **no ejecutable en local** (*App Control*); contrato **re-sincronizado a mano** (§7) y **validado por el CI** |

> **Nota de método (declarada).** En esta máquina, la política *App Control* de Windows bloquea la ejecución de `python.exe` (`os error 4551`), por lo que **no** se pudieron lanzar `pytest`/`mypy`/`import-linter`/`bump guard`/`contract:check` por CLI. Los tests JS sí se ejecutaron (Node) y están en verde; `ruff check` (binario nativo) también. El **CI** ejecuta la matriz `python` completa y `contract:check` (§7).

---

## 3. El cambio, en detalle

- **`packages/py/application/src/bolsa_application/dia_d_auto_feedback.py`:** `SCHEMA_VERSION = "dia-d-feedback-v2"`; nuevo `_normalize_cycle_row(...)` (forma EXACTA del DTO; huecos `None`) y `build_cycle_index(round_trips, *, days)` (dedup + orden por `cycleId`, omite sin clave, acota por `entryDay` de la ventana); `build_dia_d_feedback_artifact(..., cycles=())` normaliza/dedup/ordena y sella `"cycles": [...]`; `DEFAULT_LIMITS` declara que el veredicto es agregado por instrumento.
- **`apps/api-python/scripts/v2_90_dia_d_feedback.py`:** `cycles = build_cycle_index(round_trips, days=window_days)` y `build_dia_d_feedback_artifact(..., cycles=cycles)`; `meta.bump` → `2.11.60-beta`. (Los otros 8 CLI `v2_89`…`v2_97` solo cambian `meta.bump`.)
- **`apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py`:** `DiaDFeedbackCycleDto` + `DiaDFeedbackDto.cycles` + proyección en `_project(...)`.
- **`apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts`:** `DiaDFeedbackCycleDto` y `cycles[]` (ver §7).
- **`packages/shared/src/cognitive/auto-operation-story.ts`:** tipo `AutoOperationStoryExplanationResolution = "cycleId" | "instrument"`; campo `resolution` en la entrada; hecho `resolución` y `note` honesta en `EXPLANATION` (por `cycleId` ⇒ exacta; por instrumento ⇒ **PARCIAL**).
- **`apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx`:** helper exportado `resolveExplanationForCycle({ cycle, values, cycles })` (por `cycleId` con ejes del índice, o fallback por instrumento) + `explanation` useMemo.
- **Tests:** `test_dia_d_auto_feedback.py` (+5), `test_auto_dia_d_feedback_route.py` (+1, compat `v1`), `auto-operation-story.test.ts` (+3), `auto-operation-story-panel.test.tsx` (+4 del helper puro + aserción de resolución por `cycleId`) y fixture `dia-d-auto-feedback-panel.test.tsx` a `v2`.

---

## 4. Límites declarados (NO se cierran aquí)

- **Regranular el veredicto por `(instrumento × strategyVersion)`** y **veredicto por ciclo `n=1`**: **fuera de alcance** (rompería el suelo de muestra).
- **`PortfolioDecision` durable (`UI52-02`):** sigue abierta (spine/backend).
- **`F-A2` — barrido `axe` en vivo de `/auto/*`:** **no** re-ejecutado.
- **`F-S2`/`F-S3` (P3):** densidad tipográfica e `h1` crudo de ausencia.
- **PIT histórico institucional** y **Execution Analysis**: P3 abiertas.
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.

---

## 5. Cómo se reproduce

```bash
# 1) Dominio (application) + ruta.
uv run --no-sync python -m pytest packages/py/application/tests/test_dia_d_auto_feedback.py \
  apps/api-python/tests/test_auto_dia_d_feedback_route.py apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) Shared.
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared test

# 3) UI.
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint

# 4) Contrato (regenera desde FastAPI y valida).
pnpm --filter @bolsa/web contract:gen
pnpm --filter @bolsa/web contract:check
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `docs/engineering/evidence/v2.88.60/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.60-2026-10-06.md`.
- **Modificados:** `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py` (+ test), `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), `apps/api-python/scripts/v2_90_dia_d_feedback.py` y `v2_89`/`v2_91`…`v2_97` (`meta.bump`), `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py`, `apps/api-python/tests/test_auto_dia_d_feedback_route.py`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` (+ test), `apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.test.tsx`, `package.json` (`2.11.60-beta`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md`, `docs/engineering/auditoria-ui-auto-cockpit-2026-10-05.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; **no** se toca `replay_oos.RoundTrip.to_dict`.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `71ab00df` | `apps` `d7e6da64…` / `packages` `b482a276…` |
| Re-anclaje del freeze de la ventana (`chore`) | `a8f941e8` | pin `commit: 71ab00df` (no mueve árbol) |
| **Commit del sello** (`docs(seal)`) | _(este commit)_ | (mismos árboles que el funcional) |
| Tag anotado `v2.88.60-beta` | **pendiente** | (a petición: commits locales, **sin push ni tag**) |

> **Diferencia con `v2.88.59`:** ese sello era UI-only y **solo** movía `apps`; este mueve **`apps` y `packages`** (por eso cambian **los dos** hashes del pin: `apps` `a909995b…` → `d7e6da64…`, `packages` `95cb0d69…` → `b482a276…`).

---

## 7. Nota de contrato (declarada)

`openapi.json` y `schema.d.ts` **viven en `apps/`** y son artefactos generados: su forma canónica la produce `apps/api-python/scripts/dump_openapi.py` (FastAPI/Pydantic → `json.dumps(indent=2, sort_keys=True)`) seguido de `openapi-typescript`. **El pin congelado no cambia con el contrato**, pero el `contract:check` del CI **sí** lo valida byte a byte. En esta máquina el generador **no** pudo ejecutarse (*App Control* bloquea `python.exe`), de modo que el contrato se **re-sincronizó a mano** replicando el patrón de los DTOs vecinos (`DiaDFeedbackCycleDto` con `anyOf`/`null`, títulos `Cycleid`/`Entryday`/…, orden de propiedades y `required` canónicos). **Queda validado por el CI** (`contract:check` en el job `frontend`); si divergiera, el gate **falla** y el sello no promociona.
