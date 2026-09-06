# RELEVO DE AGENTE — XL-3 wire persist-only en Confirm LIVE (2026-09-07)

> **Rama:** `live-honesty-post-tip-2026-09-07` (local = `origin/...` · upstream ok · **0 ahead / 0 behind**).
> **Base:** `origin/main` · **HEAD:** `6c780ecc` (`LIVE XL-3: Confirm wiring persist-only LiveOrderCoordinator`).
> **Padre:** [roadmap LIVE Execution Core](./roadmap-live-execution-core-2026-09-07.md) · [honesty bridge externo](./honesty-pack-xtb-bridge-external-2026-09-07.md) · [engineering-index #87/#88](./engineering-index-2026-08-03.md).  
> **Tanda previa (relevo honesty):** commit `f43d0508` (OR-6 fail-closed · OE-1↔LR-1 · sandbox `LIVE_EXECUTION_UNLOCKED` · dominio `LiveOrder`).
> **Método:** esta faena es **relevo de agente**: contexto + límites + working-tree ajeno (sin tocar). **NO** producto nuevo sin plan.
> **≠** thaw · **≠** Accept estricto · `PAPER_D_EXECUTE` **off** · `LIVE_EXECUTION_UNLOCKED` **off** · sin capital real.

---

## 0. Gobernanza / invariantes (NO romper)

| Guardrail                                   | Estado                                                         |
| ------------------------------------------- | -------------------------------------------------------------- |
| Accept estricto / owner thaw / LIVE capital | **NO**                                                         |
| `PAPER_D_EXECUTE`                           | **off**                                                        |
| `brokerVenue` por defecto                   | **paper** (LIVE sólo VIRTUAL sandbox)                          |
| `LIVE_EXECUTION_UNLOCKED`                   | default **off** → `live_virtual_sandbox` (cero POST al bridge) |
| `confirm_recommendation.py` (orquestador)   | **<1100 líneas** (`test_dex4_orchestrator_module_is_thin`)     |
| Spine DEX-4 siete coordinadores             | intacto (no ampliar lista 7 del test sin necesidad)            |
| **NO MÁS PANELES** (freeze)                 | solo bloque híbrido dentro de Confirm (excepción owner)        |

---

## 1. Qué hay en código (2 commits, rama pushada)

### `f43d0508` — relevo honesty (ya en rama/main-worktree)

1. OR-6 fail-closed (PY+TS): LR-1 ausente/no-`clean` → `LIVE_BLOCKED`/`live_unavailable`; `live_adapter_wired` is-not-True → `live_adapter_not_wired`.
2. OE-1 → LR-1 cableado (median `live_reconciliation_status` + `liveAdapterWired`) solo con `venue=live`.
3. Sandbox VIRTUAL: `LIVE_EXECUTION_UNLOCKED` default off; `XtbBrokerAdapter` lo consulta + kill-switch antes de submit → `live_virtual_sandbox`/`kill_switch_active` **sin** POST bridge. E2E `gp-e2e-live-virtual-confirm-mock`: zero `/orders`.
4. Dominio XL-3 `LiveOrder` (PY `live_order.py` + TS `live-order.ts`): UNKNOWN first-class · **no re-POST** (`UNKNOWN→SUBMITTING` ausente) · `forbid_repost_from_unknown` · PARTIAL qty + **veto `execute_trade` full** · `LiveOrderQueryPort` + `MockLiveOrderQuery` (query_broker = única salida de UNKNOWN).
5. Docs: roadmap, honesty bridge externo, provenance 09-06/09-07, index #87, CURRENT_SYSTEM, HELP, CHANGELOG.

### `6c780ecc` — cableado XL-3 en Confirm (persist-only) **[esta faena]**

1. **`live_order_store.py`** (nuevo): puerto `LiveOrderStore` (`get/put/delete` por `order_id`) + `InMemoryLiveOrderStore` + `process_live_order_store()` (default proceso, inyectable). Mapeo puro `live_order_from_submit_result`: `submitted→SUBMITTED` (+ venue id vía `dataclasses.replace`) / `unknown→UNKNOWN`; `can_transition` válido permite avanzar `SUBMITTED→UNKNOWN` en retry conservando `venue_order_id`. **Fail-closed** (nunca un `FILLED`/`PARTIAL` inventado).
2. **`confirm/live_order_sync.py`** (nuevo): `LiveOrderCoordinator.persist_after_submit(result, intent, pb, order_id)`. Si `pb.venue != LIVE` → out; si status no-persistible (PAPER / `not_wired` sandbox / `rejected` / `executed`=XL-2 cerrado→ledger) → no escribe. Si procede → `store.put` + `result["liveOrder"]=…`.
3. **`confirm_recommendation.py`**: inyección opcional `live_order_store` + llamada al coordinador justo después de `await self._submit.persist_after_adapter(...)`, reutilizando `stable_order_id_from_decision(idem_key)`. **Orquestador en 1099 líneas** (< 1100). 7 coordinadores intactos.
4. **`test_confirm_broker_adapter.py`**: `submitted→SUBMITTED` (rastro recuperable), retry bridge-timeout `SUBMITTED→UNKNOWN` conserva `venue_order_id`, `not_wired` mock y `executed`(XL-2) **no** dejan rastro.
5. Docs: roadmap XL-3 **PARCIAL** (+wire persist-only), CHANGELOG `[Unreleased]`. Entrada index **#88**.

---

## 2. Lo que es STORE hoy y lo que NO (persist-only vs durable)

- El `live_order_store` **por defecto** es el singleton **de proceso** (`process_live_order_store`, memoria): el rastro se persiste y se expone en `result["liveOrder"]` durante la request y sobrevive dentro del **mismo worker** (retry). **NO es cross-PID**.
- Fallback fail-closed del coordinador: si `live_order_store is None` se usa `process_live_order_store()` (no es no-op). En tests se inyecta una `InMemoryLiveOrderStore` aislada por test.

---

## 3. PARKED / Qué NO afirmar

1. **NO** afirmar resolución de `UNKNOWN` → la abrirá **`query_broker`** (poll real) en V2.12. Hoy ninguna vía envía re-POST.
2. **NO** afirmar sled / PG durable de la máquina XL-3 (`LiveOrderRow` + migración Alembic) → V2.12. Hoy store = proceso (no cross-PID).
3. **NO** afirmar `PARTIAL → PositionState/ledger` (veto por diseño; `execute_trade` full prohibido en partial).
4. **NO** afirmar LIVE capital / Accept LIVE / thaw / `PAPER_D_EXECUTE` on / `LIVE_EXECUTION_UNLOCKED` on.
5. **Test rojo puntual ambiental**: `test_execution_router.py::test_gp_desk_05b_real_opening_gate_no_position` falla por **stale real** (`data_freshness age_s ~5,5 días > 432000`) de fixtures/reloj — **no** es regresión de esta faena (nada tocado en execution_router). No "arreglar" sin confirmar clock/fixtures.

---

## 4. Verificación rápida al arrancar

```
cd packages/py/application && python -m pytest tests/test_confirm_broker_adapter.py tests/test_confirm_paper_order.py tests/test_dex4_confirm_orchestrator.py -q
cd packages/py/analytics   && python -m pytest tests/test_live_order.py -q
cd packages/shared         && npx vitest run src/live-order.test.ts src/operational-readiness.test.ts
```

Se espera todo **PASS** (excepto el ambiental §3.5 si se corre suite entera).

---

## 5. Higiene working tree (ajeno — NO tocar)

Antes de empezar esta faena ya existían en el working tree cambios **ajenos** que NO forman parte de la línea LIVE XL-3 y que quedaron **sin stagear / sin commitear a propósito**:

- `apps/web/e2e/{fixtures.ts,gp-e2e-01-decision-journal.spec.ts,gp-e2e-02-operational-console.spec.ts,gp-e2e-v28-cabin-cert-mock.spec.ts}`.
- `apps/web/playwright.config.ts` · `apps/web/src/features/trading/{list-operativa-phase-badge.tsx,list-operativa-phase-context.tsx,open-instrument-in-trading.ts}`.
- Docs `docs/engineering/traspaso-relevo-*` / `arranque-agente-*` de otras faenas (post-v2-44, v2.8, f37, tag-v2-5, trusted-proxies, v2-8-operator-certification).
- Carpetas untracked `apps/api-python/logs/` · `packages/py/application/logs/`.

**NO incluirlos** en commits de esta rama.

---

## 6. Next (naturales, requieren plan antes de implementar)

1. **UI Confirm**: exponer `result["liveOrder"]` (SUBMITTED/UNKNOWN · venue order id) en el bloque híbrido, sin nuevos paneles (respetar freeze).
2. **Recovery UNKNOWN**: cablear `query_broker` (gate/worker) para resolver UNKNOWN **sin re-POST** → requiere diseño de worker/poll u operador.
3. **Sled PG XL-3** (`LiveOrderRow`) + migración Alembic para durabilidad cross-PID; persistir `query_broker` outcome.
4. Pull request de la rama: https://github.com/jvelasca/Bolsa_V1/pull/new/live-honesty-post-tip-2026-09-07

---

## 7. Estado del repositorio al relevo

| Pieza        | Valor                                               |
| ------------ | --------------------------------------------------- |
| Rama local   | `live-honesty-post-tip-2026-09-07`                  |
| Rama remota  | `origin/live-honesty-post-tip-2026-09-07` (push ok) |
| HEAD         | `6c780ecc` (== remoto)                              |
| Tanda A      | `f43d0508`                                          |
| Tanda B      | `6c780ecc`                                          |
| Base         | `origin/main`                                       |
| Sin upstream | No (configurado)                                    |
