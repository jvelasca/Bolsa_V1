# Traspaso — F-WORKER-1 (warning auto-sync ticker `BP/.L`, Yahoo 404) — CERRADO

| Campo      | Valor                                                                                 |
| ---------- | ------------------------------------------------------------------------------------- |
| **Rama**   | `stage/f1-integridad-financiera-2026-08-11`                                           |
| **AsOf**   | 2026-08-19                                                                            |
| **Fase**   | F-WORKER-1 = warning auto-sync ticker `BP/.L` (Yahoo 404) · Riesgo Bajo               |
| **Estado** | **CERRADO** (evaluación confirmada; fix de comportamiento ya en código desde PR #43)  |
| **Padre**  | `docs/engineering/PROJECT_STATE.md` (§3/§6/§7) · `engineering-index-2026-08-03.md` §5 |

> Propósito: cerrar la evaluación del único warning operativo heredado (auto-sync de `BP/.L` que Yahoo resuelve
> como 404) y relevar a F-DEBT-2 (P2.6 consolidar tipos web-only en `packages/shared`).
> Estado vivo y deuda priorizada en `PROJECT_STATE.md` §3 (LEER PRIMERO). Protocolo en §5.

---

## 1. Síntoma original

- En el arranque reiniciado del dev (12/08) el `auto_sync_worker` emitía:
  `Auto-sync cola: 7e858cff… → failed (Yahoo no encontró histórico para este símbolo. Revisa el ticker (ej. AENA.MC).)`
  — la petición a `/v8/finance/chart/BP/.L` devolvía **404**.
- No era un bug de arranque ni del scheduler; se mantenía como candidato de "fix de mapping o comportamiento
  esperado" (subagente lanzado 12/08, transcript `41c57061`). La deuda quedó registrada como **F-WORKER-1**.

## 2. Evaluación (retomada 2026-08-19 vía transcript del subagente previo)

**Causa raíz del 404 — dato corrupto, NO bug de mapping de código:**

- El instrumento `7e858cffa2284bf4a0521c74c` tiene `symbol='BP/'` y `yahoo_symbol='BP/.L'` (**slash literal**)
  almacenados en BD.
- El ticker válido de Yahoo para BP cotizada en Londres es **`BP.L`** (sin slash). Verificado con probe de Yahoo.
- El `yahoo_client` construye fielmente `https://{host}/v8/finance/chart/{yahoo_symbol}`, por lo que cualquier
  `yahoo_symbol` almacenado se emite tal cual. El `BP/.L` se introdujo por **entrada manual** (el flujo de
  `SearchInstruments` usa el símbolo que Yahoo devuelve en search, `BP.L`, y no genera la barra).
- Conclusión: `BP/.L` es un **registro de BD corrupto**, no un fallo sistemático de código.

**Fix de comportamiento YA MERGED (PR #43, `4a1dc69` — ancestro de HEAD verificado con `git merge-base --is-ancestor`):**

- `yahoo_client.py:228-233`: 404 → `YahooSymbolNotFoundError` (permanente; NO se cuenta como fallo transitorio del
  circuit breaker ni se reintenta).
- `sync_instrument.py:171-186`: sobre `YahooSymbolNotFoundError` devuelve `SyncResult(... retryable=False)`.
- `sync_scheduler.py:166-179`: `fail_item(retry=result.retryable)` — no reintenta símbolos 404 (la cola deja de
  re-procesarlos como transitorios).
- `auto_sync_worker.py:50-61`: degrada el log de fallo de WARNING a **INFO** (el detalle queda en DB:
  `queue.last_error` + `data_sync_logs`), eliminando el ruido repetitivo por símbolo permanentemente no-resoluble.
- Tests: `packages/py/application/tests/test_sync_queue_retryable.py` (fallo permanente → no retry) +
  `packages/py/market/tests/test_yahoo_chart.py` (`normalize_yahoo_error` 404).

**Verificación sobre el código actual** (2026-08-19): los 4 archivos coinciden con el fix mergeado; el 404 se
trata como permanente no-reintentable sin WARNING repetitivo. Comportamiento esperado confirmado.

## 3. Acción residual manual (NO es código)

- Para que el instrumento `7e858cff…` vuelva a sincronizar con dato real, corregir su registro en BD a
  `yahoo_symbol = 'BP.L'` (y `symbol` coherente) y reencolarlo si se desea. **No hay nada que introducir en código**
  para resolver el 404 del dato corrupto: el sistema ya lo degrada de forma correcta y silenciosa.

## 4. Estado del árbol / batería al cerrar

- Árbol limpio en `stage/f1-integridad-financiera-2026-08-11` (HEAD `da5f716`).
- Esta fase es **documental** (cierre de evaluación): **no toca código**, por lo que no requiere batería propia.
  Los gates CI vigentes (ruff/mypy/pytest/contract:check) quedan intactos al no haber cambios de código.
- Cierre documentado: `PROJECT_STATE.md` §3/§6/§7 + este traspaso + `engineering-index` §5.

## 5. Texto de traspaso (pegar en el próximo hilo)

> CONTEXTO: Ola de hardening `stage/f1-*` con **F-DEBT-1 = P1.9 API thin CERRADO** y **F-WORKER-1 CERRADO**.
> Rama `stage/f1-integridad-financiera-2026-08-11`. Árbol limpio · CI verde.
> Estado vivo y deuda priorizada en `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO). Mapa de fases mergeadas en
> `docs/engineering/engineering-index-2026-08-03.md` §5 · cierre P1.9:
> `docs/engineering/traspaso-p1.9-api-thin-2026-08-19.md` · cierre F-WORKER-1:
> `docs/engineering/traspaso-worker1-auto-sync-bp-2026-08-19.md`.
>
> FASE CERRADA: **F-WORKER-1** (auto-sync `BP/.L` Yahoo 404) = evaluación confirmada: registro BD corrupto
> (`yahoo_symbol='BP/.L'`; ticker válido `BP.L`), NO bug de mapping de código. El fix de comportamiento ya estaba
> MERGED (PR #43, `4a1dc69`): 404 → permanente `retryable=False`, sin retry, WARNING→INFO. Verificado en código
> actual. Acción residual manual: corregir el registro en BD a `BP.L` si se quiere dato real (no requiere código).
>
> SIGUIENTE (fuera del alcance de F-WORKER-1): **F-DEBT-2** (P2.6 consolidar tipos web-only en `packages/shared`).
>
> Protocolo: un subagente acotado + batería + aprobación por commit. No tocar fuera del alcance declarado.
> Auth JWT diferida (D4). NO reabrir Belief/H ni gobernanza IA.
>
> Batería (desde la raíz): `uv run ruff check packages/py apps/api-python --config pyproject.toml` ·
> `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src
--follow-imports=silent` (NO incluir `packages/py/application/src` al gate; application se valida
> transitivamente vía apps/api-python) · `uv run pytest packages/py/market/tests apps/api-python/tests -q -m
"not integration"` (única falla habitual = `test_lists_crud_flow` FLAKY preexistente, pasa en aislamiento) ·
> `$env:PYTHONIOENCODING='utf-8'; pnpm --filter @bolsa/web contract:check` (PowerShell, puntos y comas; git commit
> con múltiples `-m`, heredoc no soportado).
