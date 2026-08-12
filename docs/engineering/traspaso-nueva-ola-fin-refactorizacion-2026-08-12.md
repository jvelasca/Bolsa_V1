# Traspaso — nueva ola: «fin de la refactorización» (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5
> **Base viva:** `stage/f1-integridad-financiera-2026-08-11` en `301777b` (working tree limpio, 0 PRs abiertos).
> **Propósito:** documento de **apertura de nuevo hilo/chat**. Consolida el cierre de la ola anterior (F1→F5a-fidelidad + P1.6 mypy) y define la deuda restante para **terminar toda la refactorización**, con instrucciones para que el nuevo hilo lance subagentes por fase.
> **Regla del hilo siguiente:** elegir UNA fase de la §3 y declararla como alcance exclusivo; NO tocar código fuera de ese alcance. Batería por paso. Ejecutar en subagentes (git worktrees aislados si tocan paquetes distintos) para no saturar el hilo.

---

## 1. Estado de «todo el trabajo» (consolidado y verificado 2026-08-12)

- **Base viva:** `stage/f1-integridad-financiera-2026-08-11` → **`301777b`**.
- **Working tree:** limpio. Rama local actual `stage/p1.6-mypy-gate-ci-2026-08-12` (ya mergeada en base, no es la activa de trabajo).
- **PRs abiertos vs base:** **0**.
- **CI:** `quality`/`battery`/`fase2-battery`/`scan` VERDES. `contract:check` VERDE (gate bidireccional activo). **`Mypy` es ahora un gate BLOQUEANTE** full-tree (0 errores en 243 archivos).
- **Worktrees temporales `wt-mypy-*`:** eliminados (física + metadata `git worktree prune`); branches locales de esos worktrees borradas. Solo queda el worktree principal.
- **Entorno operativo:** el dev fue reiniciado; `scheduler_worker.py` arranca limpio con `SelectorEventLoop` (fix PR #39). El warning de auto-sync `BP/.L` (404 de Yahoo) se resolvió como **fallo permanente NO-reintentable** y queda logueado a nivel INFO (PR #43) — comportamiento esperado, no un bug de arranque.

### 1.1 Ola F1→F5a-fidelidad completa (MERGEADA)

| Fase                      | PR    | Qué era                                                                                    |
| ------------------------- | ----- | ------------------------------------------------------------------------------------------ |
| F1 integridad financiera  | (30s) | `with_for_update`, `deduct_cash`, `ExecuteTrade`, idempotencia, invariantes M1–M5          |
| F2 backtest `next_open`   | #30   | rigor científico del backtest, grids, fingerprint, recálculo trials                        |
| F3b Alembic autoridad BD  | #31   | Alembic + `data_epoch`, migraciones, `ensure_migrated`                                     |
| F3a procesos/DB (D3)      | #32   | `scheduler_worker` proceso dedicado, `run_account_data_migration`, baseline Prisma→Alembic |
| F4 arquitectura Python    | #33   | ciclo `analytics↔market` roto, 7 ruff gates, mypy gate por fases                           |
| F5b backend/seguridad     | #34   | rate-limit distribuido, `upsert_bars` bulk, `/health` sanitizado, P2.7 amounts             |
| F5c frontend clean-up     | #35   | formato centralizado, timers tipados, test shared                                          |
| P2.1 god-components       | —     | workspace-store 3982→89 l. + backtests-page 5129→4509                                      |
| P2.8 "as unknown as"      | #36   | 7 bridges de serialización vía DTOs shared                                                 |
| F5b-drift regen contrato  | #37   | `openapi.json` regenerado, `contract:check` desbloqueado                                   |
| F5a-fidelidad gate bidir. | #38   | `contract-check.ts` `CoversContract` + sentinelas 5→11                                     |
| fix scheduler Windows     | #39   | `SelectorEventLoop` (ProactorEventLoop crash, `psycopg.InterfaceError`)                    |
| fix CI vitest shared      | #40   | `vitest` en devDependencies de `packages/shared`                                           |
| docs registro merges      | #41   | index + traspasos a MERGEADO                                                               |
| docs traspaso de cierre   | #42   | documento de cierre de la ola (contexto achatado)                                          |

### 1.2 P1.6 mypy por fases (COMPLETADA en esta última sesión)

- **PRs #45 (domain) · #46 (market) · #47 (api-python) · #48 (infrastructure):** MERGEADOS. Limpian la deuda **mypy preexistente (~448 errores)** sobre los 4 paquetes del gate CI. Resultado: **0 errores en 243 archivos fuente** (`--follow-imports=silent`).
- **Estrategia:** 4 subagentes en **git worktrees aislados** (`wt-mypy-{domain,market,infrastructure,api-python}`) — lección aprendida: evitar colisión/sobrescritura en el checkout compartido.
- **Catálogo de errores resueltos:** `type-arg` (`dict`/`list` sin genérico) · `arg-type` (guards `X | None`) · `no-untyped-def` · `Mapped[...]` en modelos SQLAlchemy 2.0 (`tables.py`).
- **PR #49:** gate CI `Mypy` **BLOQUEANTE** full-tree (se quitó `continue-on-error`; se retiró el paso scoped `F4+F5b`):
  `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src --follow-imports=silent`
- **PR #43 (fix auto-sync 404):** `YahooSymbolNotFoundError` en `yahoo_client.py` → `SyncResult.retryable=False` en `sync_instrument.py` → propagado en `sync_scheduler.py` → log a INFO en `auto_sync_worker.py`; tests `test_sync_queue_retryable.py`. Se **rebaseó** la rama sobre la base para desbloquear el check `quality` (Ruff I001 en `scheduler_worker.py` ya corregido en base por #48). MERGED.
- **PR #50 (docs cierre):** `traspaso-p1.6-mypy-fases-2026-08-12.md` + registro en `engineering-index` §5. MERGED (base → `301777b`).
- **Batería combinada:** `ruff` 0 · `mypy` 0/243 · pytest **451✓** (mismo criterio del check `battery`).

---

## 2. Cómo está el CI ahora (impacto para futuros PRs)

- **`Mypy` es BLOQUEANTE full-tree.** Cualquier PR que toque `python` DEBE pasar `mypy` con 0 errores en domain/market/infrastructure/apps-api-python. Un error nuevo rompe CI.
- **`Ruff`** (`quality`) es 0 errores (I001/B007 ya cerrados).
- **`contract:check`** es VERDE y **bidireccional** (#38): si el BE emite un campo nuevo que el FE no cubre (o viceversa en las 11 sentinelas), el typecheck rompe.
- **Frontend:** web typecheck✓ lint✓ test **714✓** (141 f) build✓ · shared test **10✓**.
- **Pytest offline:** **451✓** + api 27✓ (bolsa_v1) + application 222✓ + infra+domain 57✓ + ai+analytics+digest 340✓.

---

## 3. Deuda para «terminar TODA la refactorización» (elegir UNA por hilo)

Prioridad sugerida. El nuevo hilo debe **elegir UNA y declararla como alcance exclusivo**:

1. **F5a §6 fidelidad restante** (la MÁS GRANDE) — deuda de F5a-contratos/P2.8:
   - Adoptar **`openapi-fetch`** como cliente completo (reescribir/reducir `apps/web/src/api/api.ts`: ~100 métodos / ~2.073 líneas), en fase propia. `openapi-typescript@^7.13.0` ya instalado; el contrato `operations`/`paths` en `apps/web/src/api/schema.d.ts` ya lo soporta.
   - **Reconciliar campo-a-campo ~87+ DTOs de wire** restantes (no sentinela) vs contrato → requiere acuerdo de fuente de verdad (P2.6).
   - **Fidelidad de tipos del valor** (`manifest`, `number↔integer`, unions) — el gate bidireccional cubre igualdad de **claves**, no de **valor**.
2. **P2.6 consolidar tipos web-only / duplicación TS↔Py** — consolidar en `packages/shared` los tipos re-declarados (`RecommendationV1`, `CoreRVerdict`, `RunManifest`, resto `ai-indicator-series`↔`technical_rating`/`data_quality`, `execution-policies`/`position-policies`/`tracker-definitions`/`tax-report`) → exige acuerdo de fuente de verdad.
3. **P1.9 API thin** — adelgazar endpoints de FastAPI (proxies/serializaciones delgados actuales = deuda de F4/F5b).
4. **P1.3 auth full (D4)** — autenticación/seguridad completa, diferido a fase propia.

También quedan casts residuales legítimos `toF3ItemDto`/`toCoachFactsRecord` (frontera de blob opaco) — no eliminables sin cambiar el wire (A2). No son fase propia; se resuelven dentro de F5a §6.

---

## 4. Recomendación de ejecución para el nuevo hilo

- **Elegir 1 fase** de §3 (recomendado empezar por **F5a §6 / openapi-fetch** por ser la mayor, o cerrar P1.9/P1.3 backend si se prefiere menor fricción).
- Lanzar **subagentes** para el trabajo pesado, manteniendo el hilo principal ligero y con la visión global:
  - Si la fase toca **varios paquetes autocontenidos** → usar **git worktrees aislados** (uno por paquete) + un subagente por worktree (patrón P1.6).
  - Si la fase es **transversal a un solo frontend/backend** → un solo subagente con alcance bien delimitado, que delega en este contexto.
- **Cada PR** debe pasar: `mypy` (gate bloqueante) · `ruff` 0 · `pytest` (criterio battery) · batería FE (`contract:check` bidireccional, web typecheck/lint/test, shared test).
- Al cerrar cada fase: **PR mergeado** en `stage/f1-integridad-financiera-2026-08-11`, registrar en `engineering-index` §5 + traspaso de la fase, y documento de cierre/traspaso al final.

---

## 5. Archivos clave a leer (leer PRIMERO en el nuevo hilo)

- **Mapa maestro de fases:** `docs/engineering/engineering-index-2026-08-03.md` §5.
- **Traspaso de la ola anterior (cierre):** `docs/engineering/traspaso-cierre-refactorizacion-2026-08-12.md`.
- **Cierre P1.6 (esta sesión):** `docs/engineering/traspaso-p1.6-mypy-fases-2026-08-12.md` + `docs/engineering/plan-p1.6-mypy-fases-2026-08-12.md`.
- **Traspasos por fase** relevantes a la fase elegida (F5a-fidelidad-gate, P2.8, P2.1, F4, F5b, etc.).

---

## 6. Texto de traspaso (pegable en el nuevo chat)

> CONTEXTO INMEDIATO: ola de refactorización/integridad **F1→F5a-fidelidad + P1.6 (mypy por fases) COMPLETADA y MERGEADA** en `stage/f1-integridad-financiera-2026-08-11` (HEAD `301777b`; working tree limpio; **0 PRs abiertos**). CI `quality`/`battery`/`fase2-battery`/`scan` VERDES, `contract:check` VERDE, **`Mypy` ahora es gate BLOQUEANTE full-tree** (0/243 archivos). Mapa completo de fases en `docs/engineering/engineering-index-2026-08-03.md` §5.
>
> Resumen de lo ya cerrado (todo MERGEADO): ola F1/F2/F3a/F3b/F4/F5a/f5b/f5c/P2.1/P2.8/fixes (#30–#42) + **P1.6 mypy**: #45/46/47/48 (448 errores → 0), #49 (gate blocking), #43 (fix auto-sync 404 `BP/.L`), #50 (traspaso cierre). Worktrees temporales y ramas de worktrees limpios.
>
> Para **terminar TODA la refactorización**, elige UNA (del `traspaso-cierre-refactorizacion-2026-08-12.md` §3, ya seleccionada como to-do) y declárala alcance exclusivo:
>
> 1. **F5a §6 fidelidad restante** — adoptar `openapi-fetch` como cliente completo (reescribir ~100 métodos / ~2.073 líneas de `api.ts`) + reconciliar ~87+ DTOs + fidelidad de valor (`manifest`/`number↔integer`).
> 2. **P2.6** — consolidar tipos web-only (`RecommendationV1`/`CoreRVerdict`/`RunManifest`, resto TS↔Py) en `packages/shared`.
> 3. **P1.9 API thin** — adelgazar endpoints FastAPI.
> 4. **P1.3 auth full (D4)** — autenticación/seguridad completa.
>
> Ejecuta el trabajo **en subagentes** (worktrees aislados si la fase toca varios paquetes autocontenidos), manteniendo la visión global en el hilo. Los subagentes no deben perder el contexto de lo que queda. Prioridad recomendada: **opción 1 (F5a §6 / openapi-fetch)** por ser la de mayor volumen, o P1.9/P1.3 si se prefiere cerrar backend.
>
> Lee PRIMERO: `docs/engineering/engineering-index-2026-08-03.md` §5 + `docs/engineering/traspaso-cierre-refactorizacion-2026-08-12.md` + `docs/engineering/traspaso-p1.6-mypy-fases-2026-08-12.md`. NO toques código fuera del alcance de la fase que se declare. Batería por paso.

---

**Estado del repo:** base `stage/f1-integridad-financiera-2026-08-11` @ `301777b`, working tree limpio, 0 PRs abiertos, CI verde.
