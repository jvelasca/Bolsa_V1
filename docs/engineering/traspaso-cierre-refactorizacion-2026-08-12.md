# Traspaso — CIERRE de la ola de refactorización/integridad (F1→F5a-fidelidad) (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5
> **Base viva:** `stage/f1-integridad-financiera-2026-08-11` en `25564a2` (working tree limpio).
> **Propósito:** documento de CIERRE de hilo. Consolida el estado de la refactorización/integridad ejecutada en
> varios días (F1·F2·F3·F4·F5 y la deuda de hilos P2.x) e indica qué queda para **terminar toda la
> refactorización** en el próximo chat/agente.
> **Regla del hilo siguiente:** NO tocar código fuera del alcance de la fase que se declare. Batería por paso.

---

## 1. Qué se ha terminado (ola F1–F5 + fijación 2026-08-12)

Todo lo listado está **MERGEADO** en `stage/f1-integridad-financiera-2026-08-11` y documentado en su traspaso y
en el `engineering-index` §5.

| Rama / fase                          | PR    | Estado | Qué era                                                                                                      |
| ------------------------------------ | ----- | ------ | ------------------------------------------------------------------------------------------------------------ |
| **F1** integridad financiera         | (30s) | MERGED | `with_for_update`, `deduct_cash`, `ExecuteTrade`, idempotencia, invariantes contables (micro-cambios M1–M5). |
| **F2** backtest `next_open`          | #30   | MERGED | rigor científico del backtest, grids, fingerprint, recálculo de trials.                                      |
| **F3b** Alembic autoridad BD         | #31   | MERGED | Alembic + columna `data_epoch`, migraciones, `ensure_migrated`.                                              |
| **F3a** procesos/DB (D3)             | #32   | MERGED | `scheduler_worker` proceso dedicado, `run_account_data_migration` idempotente, baseline Prisma→Alembic.      |
| **F4** arquitectura Python           | #33   | MERGED | ciclo analytics↔market roto, 7 ruff gates, mypy gate por fases.                                              |
| **F5b** backend/seguridad            | #34   | MERGED | rate-limit distribuido, `upsert_bars` bulk, `/health` sin internos, P2.7 amounts estrictos.                  |
| **F5c** frontend clean-up            | #35   | MERGED | formato centralizado, timers tipados, test shared (P2.6).                                                    |
| **P2.1** god-components              | —     | MERGED | workspace-store 3982→89 líneas + backtests-page 5129→4509.                                                   |
| **P2.8** "as unknown as"             | #36   | MERGED | 7 bridges de serialización eliminados vía DTOs shared concretos.                                             |
| **F5b-drift** regen contrato         | #37   | MERGED | `openapi.json` regenerado, `contract:check` desbloqueado.                                                    |
| **F5a-fidelidad** gate bidireccional | #38   | MERGED | `contract-check.ts` `CoversContract` + sentinelas 5→11.                                                      |
| **fix scheduler Windows**            | #39   | MERGED | `scheduler_worker.py` `SelectorEventLoop` (ProactorEventLoop crash).                                         |
| **fix CI vitest shared**             | #40   | MERGED | `vitest` en devDependencies de `packages/shared`.                                                            |
| **docs registro merges**             | #41   | MERGED | index + traspasos actualizados a MERGEADO.                                                                   |

## 2. Los dos problemas de operativa/CI resueltos en la sesión

1. **Terminal de arranque (`psycopg.InterfaceError: ProactorEventLoop`)** → PR #39. El `scheduler_worker.py`
   usaba `asyncio.run` que en Windows crea `ProactorEventLoop`, incompatible con `psycopg` async. Fix:
   `asyncio.Runner(loop_factory=lambda: loop)` con `asyncio.SelectorEventLoop()` cuando `sys.platform == "win32"`.
   **Verificado**: worker arranca limpio contra PostgreSQL y procesa datos (auto-sync, scrub Yahoo, etc.). El dev
   fue reiniciado por el usuario; el terminal ya no muestra el traceback.
2. **CI `quality` rojo en cualquier PR (`vitest: not found`)** → PR #40. `packages/shared/package.json` declara
   `"test": "vitest run"` sin `vitest` en devDependencies (en local pasaba por hoisting de `apps/web`). Fix:
   `"vitest": "^3.2.3"` en shared + lockfile. **Verificado**: battery/quality/scan VERDES.

## 3. Deuda acumulada para «terminar toda la refactorización» (sin resolver)

Prioridad sugerida (de pendiente de fase cerrada a deuda estructural; el siguiente chat/agente debe elegir una y
declararla como alcance exclusivo):

- **F5a §6 fidelidad restante (deuda grande de F5a-contratos / P2.8):**
  - Adoptar **`openapi-fetch`** como cliente completo (reescribir/reducir `api.ts`: 100 métodos / ~2.073 líneas),
    en fase propia. `openapi-typescript@^7.13.0` ya está instalado; el contrato `operations`/`paths` en
    `schema.d.ts` ya lo soporta.
  - **Reconciliar campo-a-campo ~87+ DTOs de wire** restantes (no sentinela) vs contrato → requiere acuerdo de
    fuente de verdad (P2.6).
  - **Fidelidad de tipos del valor** (`manifest`, `number`↔`integer`, unions) — el gate bidireccional (#38) cubre
    **igualdad de claves**; la fidelidad de _valor_ sigue fuera del gate.
- **P2.6 duplicación TS↔Py:** consolidar en `packages/shared` los tipos web-only re-declarados
  (`RecommendationV1`, `CoreRVerdict`, `RunManifest`, y resto `ai-indicator-series` ↔
  `technical_rating`/`data_quality`, `execution-policies`/`position-policies`/`tracker-definitions`/`tax-report`)
  → exige acuerdo de fuente de verdad.
- **P1.9 API thin (hilo propio):** adelgazar endpoints de FastAPI; los proxies/serializaciones delgados actuales
  son deuda previa de F4/F5b.
- **P1.3 auth full (D4) diferido:** seguridad/autenticación completa, diferido a fase propia.
- **mypy preexistente por fases:** el gate CI (`Mypy — gate scoped F5`) cubre solo un subconjunto; el resto del
  árbol (~450 preexistentes) debe limpiarse por fases.
- **Casts residuales legítimos** `toF3ItemDto`/`toCoachFactsRecord` (frontera de blob opaco) — no eliminables sin
  cambiar el wire (A2).

## 4. Estado del entorno

- **Base viva:** `stage/f1-integridad-financiera-2026-08-11` a `25564a2` (merge PR #41). Working tree limpio.
- **CI:** `quality`/`battery`/`scan` VERDES tras PR #40. `contract:check` VERDE (gate bidireccional activo).
- **Ramas temporales** de los PRs #38/#39/#40/#41 borradas en local; las remotas quedaron sin borrar (decisión de
  no hacer limpieza de estado compartido no solicitada).
- **PENDIENTE de incorporar:** un subagente quedó investigando el único warning operativo del dev (auto-sync de un
  símbolo que Yahoo resuelve como 404, véase `terminal 13` → `Auto-sync cola: ... failed (Yahoo no encontró
histórico para ...)`). **Reevaluar su conclusión al abrir el próximo hilo antes de asumir que no quedan fixes
  operativos** (ver §5 nota).

## 5. Nota sobre el warning de auto-sync detectado

En el arranque reiniciado (pid nuevo) el `auto_sync_worker` emitió un warning no crítico:
`Auto-sync cola: 7e858cff… → failed (Yahoo no encontró histórico para este símbolo. Revisa el ticker (ej.
AENA.MC).)` — la petición a `/v8/finance/chart/BP/.L` devolvió **404**. No es un bug de arranque ni del
scheduler; es una condición de **datos externos** (ticker `BP/.L` no resuelve en Yahoo). Casi todos los demás
símbolos procesaron `success`. El subagente lanzado para evaluarlo debía decidir si es un fix de mapping de
ticker o comportamiento esperado. **Si ese subagente aún no ha devuelto su informe al abrir el próximo hilo, no
duplicar el trabajo: retomarlo con `resume`.**

## 6. Texto de traspaso (pegable en el próximo chat)

> CONTEXTO INMEDIATO: ola de refactorización/integridad **F1→F5a-fidelidad + fixes operativos y de CI**
> **CONSOLIDADOS y MERGEADOS en `stage/f1-integridad-financiera-2026-08-11`** (HEAD `25564a2`, merge PR #41).
> Working tree limpio. CI `quality`/`battery`/`scan` VERDES. Los traspasos individuales y el mapa completo de
> fases están en [`docs/engineering/engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) §5.
>
> - **F5a §6 fidelidad (gate de contrato BIDIRECCIONAL) MERGEADO (PR #38, `bc51980`):** `contract-check.ts` nuevo
>   `CoversContract<BE,FE>` cubre FE⊆contrato Y contrato⊆FE sobre **11 sentinelas** (G1–G11). Si el BE emite un
>   campo nuevo, el typecheck rompe. Cero cambios de DTOs shared. `contract:check` VERDE.
> - **fix scheduler Windows (PR #39, `4deb025`):** `scheduler_worker.py` forzaba `asyncio.run` en
>   `ProactorEventLoop` → `psycopg.InterfaceError` al conectar a PostgreSQL en dev. Fix: `asyncio.Runner` +
>   `SelectorEventLoop` en `win32`. Worker arranca limpio VERIFICADO. El dev fue reiniciado por el usuario; ya no
>   hay traceback en terminal.
> - **fix CI shared (PR #40, `07aa2fb`):** `packages/shared` declaraba `"test":"vitest run"` sin `vitest` en
>   devDependencies → `quality` rojo en TODOS los PRs. Fix: `"vitest":"^3.2.3"` en shared. CI VERDE.
> - **Para terminar TODA la refactorización pendiente**, elige y declara UNA de estas fases (ver §3):
>   1. **F5a §6 fidelidad restante** — adoptar `openapi-fetch` como cliente completo + reconciliar ~87+ DTOs de
>      wire no sentinela + fidelidad de valor (`manifest`/`number↔integer`).
>   2. **P2.6** — consolidar tipos web-only re-declarados (`RecommendationV1`/`CoreRVerdict`/`RunManifest`, resto
>      TS↔Py) en `packages/shared`.
>   3. **P1.9 API thin** — adelgazar endpoints FastAPI.
>   4. **P1.3 auth full (D4)** — autenticación/seguridad completa.
>   5. **mypy preexistente por fases** — limpiar ~450 preexistentes del árbol.
>
> PENDIENTE: un subagente quedó evaluando el único warning operativo del dev (auto-sync de un ticker `BP/.L` que
> Yahoo devuelve 404). Si aún no ha devuelto informe, retomarlo con `resume` antes de asumir que no queda fix
> operativo.
>
> Lee PRIMERO: este traspaso + `engineering-index` §5 (mapa de todas las fases mergeadas) y los traspasos
> individuales de la fase que elijas. NO toques código fuera del alcance de la fase que se declare.
