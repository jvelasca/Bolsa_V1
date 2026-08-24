# RELEVO — Spine residual DS-05 CERRADA → ops propietario

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** tras spine residual. **Siguiente = ops propietario**.
> **AsOf:** 2026-08-24. HEAD pre-slice stamp U6 `8f970b7` (código U6 `9e9a346`). **DS-05 en working tree** (sin commit — coordinador). Prove S0–S3 + H5 + UX mesa U0–U6 + **DS-05** CERRADOS.
> **Protocolo:** máx. 1 writer + 1 verifier RO. Coordinador re-lee file:line. Pre-commit: batería de la fase + update-last.

---

## 1. Qué quedó hecho (spine residual · DS-05)

| Entrega     | Detalle                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------ |
| Gap elegido | **DS-05** Stale data BLOCK (Data Freshness Gate)                                                 |
| Gate puro   | `data_freshness_veto_reason` + params en `check_opening` (`risk_engine.py`)                      |
| Umbral      | `DATA_FRESHNESS_MAX_AGE_SECONDS = 5 * 24h` (alineado EOD_STALE_MAX_DAYS)                         |
| SEMI        | `ohlcv.get_latest_bar_date` → `require_fresh_data=True`; lookup raise → veto (como H2)           |
| AUTO        | `signal.timestamp` + `require_fresh_data=True` en paper + live dry-run                           |
| Exits       | `exit` / `exit_hint` / `reduce` **no** pasan por freshness (no atrapa cierres)                   |
| DI          | `get_confirm_intent_use_case` inyecta `get_ohlcv_repository`                                     |
| Tests       | unit risk · AUTO `test_ds05_auto_stale…` · SEMI stale/fresh/ohlcv-fail                           |
| Batería     | `pnpm test:decision-spine` **43 passed** · ruff 0 · mypy 0 (touched)                             |
| Freeze      | Sin OrderProposal · sin H3 orphan change · sin bypass confirm · sin `contract:gen` · ops intacto |

**Archivos (código):**

- `packages/py/application/src/bolsa_application/risk_engine.py`
- `packages/py/application/src/bolsa_application/confirm_recommendation.py`
- `packages/py/application/src/bolsa_application/execution_router.py`
- `apps/api-python/src/bolsa_api/api/dependencies.py`
- tests: `test_risk_engine.py` · `test_decision_spine.py` · `test_execute_trade_idempotency.py`

**Docs (update-last):** backlog §0 · `CURRENT_SYSTEM.md` · `PROJECT_STATE.md` · `decision-spine-cadena-2026-08-24.md` · este relevo.

## 2. Residuales que quedan (inventario honesto)

| Hueco                            | Estado                        | Next slice id sugerido           |
| -------------------------------- | ----------------------------- | -------------------------------- |
| DS-03 Mandate de cuenta          | Diferido (no es este gate)    | ops / fase mandate (si pactuada) |
| Composite `portfolioConstraints` | Doc honesty (`not_evaluated`) | spine-fit-composite (opcional)   |
| Dos call-sites `ExecuteTrade`    | Diferido (grande)             | execute-converge                 |
| H3 orphan apertures              | Freeze doc-only               | —                                |
| DS-12–15 broker                  | Fuera                         | —                                |

## 3. Freeze (sigue intacto)

OrderProposal · Journal · Attribution · orquestador · Daily Mission · Track B B1–B12 · Belief · `PAPER_D_EXECUTE` **off** · sin broker live · Lab→spine · `contract:gen` salvo fase pactada · **no bypass human confirm** · **no cambio H3 orphan execute**.

## 4. Siguiente · ops propietario

**Abrir ops propietario** (secret scanning UI · `TRUSTED_PROXIES` prod). No mezclar más huecos DS en el mismo writer salvo fase nueva.

## 5. Anti-sobrecarga

Máx. **2** subagentes (1 writer + 1 verifier RO). No reabrir Track B / Belief / H5 / mesa U\*. No OrderProposal.

## 6. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: post-U6 stamp 8f970b7 + DS-05 freshness en working tree (commit coordinador).
Prove+H5+U0–U6+DS-05 CERRADOS. Freeze: sin OrderProposal · PAPER_D_EXECUTE off ·
Lab fuera spine · no broker live · no bypass confirm · H3 orphans sin tocar.
SIGUIENTE: ops propietario (secret scanning UI · TRUSTED_PROXIES prod).
Protocolo 1 writer + 1 verifier RO.
Read-first: backlog §0 · CURRENT_SYSTEM · PROJECT_STATE · este relevo.
```
