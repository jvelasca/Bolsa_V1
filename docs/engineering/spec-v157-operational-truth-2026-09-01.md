# Spec — V1.57 Operational Truth

> **AsOf:** 2026-09-01 · **Estado:** **implementación CERRADA** (tag pendiente).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v156-hardening-residuals-2026-09-01.md`](./spec-v156-hardening-residuals-2026-09-01.md) · tip certificado previo **`v1.56-beta` → `5c598a62`**. **No** LIVE.

Congela el núcleo post-V1.56. Cierra grietas de proyección (`PositionOperationalView`) y nombra invariantes globales INV-01..10. **No** motores nuevos · **no** LIVE · **no** E2E integrado · **no** UX Mercado.

```text
P0  T2_EXECUTED · stopHistory 5 orígenes · RECONCILIATION_DRIFT · exhaustividad
P1  INV-01..10 batería nombrada
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · V1.54–V1.56 intactos salvo proyección operativa + tests.

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.

Regla de esta versión: **EXCEPTION ≠ ERROR DE UI**. `UNKNOWN` / `DRIFT` / `FILL_UNCERTAIN` → reconciliación, no `retry()` / `auto_heal()`. Una sola proyección: `Position → PositionOperationalView → Mesa y Mercado`.

## 1. IN — P0 Coherencia de proyección

| ID         | Comportamiento                                                                                                                                                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GP-V157-01 | T2 `triggered` → `T2_READY`; T2 `executed` + remaining > 0 → `T2_EXECUTED`; T2 `executed` + CLOSED → `CLOSED`. Eventos T2 simétricos a T1. T2 (ciclo posterior) tiene prioridad sobre T1 en `operatingState`. Desk map `T2_*` → `reduced`. |
| GP-V157-02 | `buildStopHistory` incluye los 5 orígenes (`protect` \| `trail` \| `reduce` \| `override` \| `stop`). Deltas vs stop inmediatamente anterior.                                                                                              |
| GP-V157-03 | `reconStatus === "drift"` → `RECONCILIATION_DRIFT` (≠ `RECONCILIATION_ERROR` de `unavailable`, ≠ estados sanos). Cubo Mesa `requiere_accion`.                                                                                              |

`unavailable` = no sabemos. `drift` = sabemos que hay discrepancia. No colapsar.

GP-SESSION-10 endurece: con posición + recon drift, `operating_state == "RECONCILIATION_DRIFT"`.

## 2. IN — P1 Invariantes INV-01..10

| ID     | Invariante                                                        |
| ------ | ----------------------------------------------------------------- |
| INV-01 | `quantity >= 0`                                                   |
| INV-02 | CLOSED ⇒ `remainingQuantity == 0` (qty de nacimiento se conserva) |
| INV-03 | T1 `executed` ⇒ fill id presente                                  |
| INV-04 | T2 `executed` ⇒ fill id presente                                  |
| INV-05 | trailing no empeora el stop                                       |
| INV-06 | CLOSED no genera nuevo exit                                       |
| INV-07 | clear de drift solo si recon CLEAN                                |
| INV-08 | identidad de fill inmutable                                       |
| INV-09 | decision snapshot inmutable                                       |
| INV-10 | risk snapshot inmutable                                           |

Suite: `packages/py/application/tests/test_inv_operational_truth.py`. Reutiliza DEX-5 / `clamp_stop_not_worsen` / GP-SESSION-10r / `_advance_target_leg`. No sustituye Golden Session.

## 3. Exhaustividad

Helper `assertNever` en `packages/shared/src/cognitive/never.ts`. Switches de `mapOperatingStateToDeskStatus`, labels de stop origin, y `reconStatus` → operating state. **No** activar `@typescript-eslint/switch-exhaustiveness-check` global (eslint no es type-aware; rompería el frontend).

## 4. Hallazgo persistente — mercado cerrado (contrato, no bug)

[`position_policy_decision.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/position_policy_decision.py): T1/T2/TIME + sesión cerrada → `HOLD` + `queue_next_session`. `STRUCTURAL_STOP` / `THESIS_INVALIDATION` / `PORTFOLIO_RISK` son riesgo inmediato y **pueden ejecutarse** con mercado cerrado (fill PAPER = último close).

Contrato V1.48 ([spec-v148](./spec-v148-paper-desk-event-continuity-2026-09-01.md)): no es olvido de enum. Sesgo vs LIVE. **Parked** para V1.58+/LIVE. V1.57 **no** cambia política.

## 5. OUT / parked

LIVE · scheduler · bump package · `PAPER_D_EXECUTE` default on · Alembic · segundo ranking / Decision Engine / Exit Engine · GOLDEN-DAY-ADVERSARIAL · Playwright FastAPI+DB (V1.59) · tarjeta estrella Mercado (V1.60) · encolar STRUCTURAL_STOP a apertura · segundo DTO Python de `PositionOperationalView` · thaw Accept (0/5 PASS 2026-09-01) · TRUSTED_PROXIES IPs de producción (`BLOCKED_ON_OWNER`).

Roadmap posterior (no esta entrega): **V1.58** adversarial · **V1.59** E2E integrado · **V1.60** UX Mercado.

## 6. Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-operational-view.test.ts src/cognitive/operational-context.test.ts src/cognitive/daily-desk.test.ts
pytest packages/py/application/tests/test_inv_operational_truth.py packages/py/application/tests/test_paper_desk_golden_session_adverse.py packages/py/application/tests/test_paper_desk_golden_day.py -q
uv run ruff check packages/py/application/src/bolsa_application packages/py/analytics/src/bolsa_analytics/cognitive --config pyproject.toml
pnpm --filter @bolsa/shared exec tsc --noEmit
```
