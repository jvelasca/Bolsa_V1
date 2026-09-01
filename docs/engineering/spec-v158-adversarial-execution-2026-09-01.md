# Spec — V1.58 Adversarial Execution

> **AsOf:** 2026-09-01 · **Estado:** **implementación CERRADA** (tag pendiente).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v157-operational-truth-2026-09-01.md`](./spec-v157-operational-truth-2026-09-01.md) · tip certificado previo **`v1.57-beta` pendiente** (partida **`v1.56-beta` → `5c598a62`**). **No** LIVE.

Congela el núcleo post-V1.57. Compone un **único** día PAPER adversarial encadenado y **cierra** el hallazgo persistente STRUCTURAL_STOP + mercado cerrado certificando el contrato V1.48 (sin encolar stop a la apertura).

```text
P0  GP-GOLDEN-DAY-ADV-01 encadenado + AdversarialSell network skip
P0b network skip no marca T1/T2 failed (solo blocked/rejected)
P1  GP-V158-STOP-CLOSED — contrato stop cerrado nombrado
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · V1.54–V1.57 intactos salvo arreglo mínimo P0b + tests.

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.

## 1. IN — P0 GP-GOLDEN-DAY-ADV-01

Archivo: `packages/py/application/tests/test_paper_desk_golden_day_adversarial.py`.

Reutiliza `paper_desk_golden_fixtures` (`SessionStore`, `build_cycles`, `assert_identities`, `assert_birth_invariants`, `assert_journal_chain`).

`AdversarialSell.fail_next(n)` → `PaperPositionSellResult(status="skipped", reason="network_failure")` **sin** consumir `idempotency_key` como fill (retry posterior ejecuta).

Secuencia sobre **un** store / **un** ciclo:

| Hora  | Inyección                                | Ancla                                    |
| ----- | ---------------------------------------- | ---------------------------------------- |
| 09:00 | BUY Estudio                              | GOLDEN-DAY-01                            |
| 09:01 | `PersistPositionFromFill` dup open tx    | `persist_position_from_fill` idempotente |
| 11:00 | T1 (mark 110)                            | GP-SESSION-06                            |
| 11:05 | crash: nuevo `PaperDeskCycle`, replay T1 | CAOS-01 / AUTO-05                        |
| 12:00 | TRAIL                                    | GP-SESSION-08                            |
| 13:00 | T2 mark 120 + **1 sell skipped**         | gancho nuevo                             |
| 13:05 | T2 retry → fill                          | GP-SESSION-07e                           |
| 13:10 | duplicate event                          | CAOS-01                                  |
| 16:00 | EXIT (mark ≤ stop)                       | GOLDEN-DAY-01                            |
| 16:05 | recon `clean`                            | inverso GP-SESSION-10                    |

**Resultado único:** 1 fila Position `CLOSED`, `remaining_quantity == 0`, `store.inserts == 1`, 1 open fill, sells T1 + T2 + EXIT (skip de red **no** crea fill), T1/T2 `executed` con fill ids distintos, journal 1 cadena, INV predicados al cierre.

## 2. IN — P0b Network fail no debe matar la pierna

`execute_position_policy_auto.py`: `patch_target_leg(..., status="failed")` solo en rechazo duro (`blocked` / `rejected`). `skipped` / `network_failure` → `sell_skipped`; siguiente tick reintenta. Sin auto-heal.

## 3. IN — P1 GP-V158-STOP-CLOSED

Certifica contrato V1.48 ([`spec-v148`](./spec-v148-paper-desk-event-continuity-2026-09-01.md)) + [`position_policy_decision.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/position_policy_decision.py) L125–131:

- `STRUCTURAL_STOP` + `session="CLOSED"` → sell ocurre (PAPER last close).
- T1 + `session="CLOSED"` → `queue_next_session`, 0 sells (contraste).

Hallazgo de 22 rondas **cerrado como contrato PAPER**; encolar stop a apertura = sesgo LIVE (parked V1.62+).

## 4. OUT / parked

Encolar `STRUCTURAL_STOP` / `THESIS_INVALIDATION` a la apertura (LIVE) · GOLDEN-DAY happy path (sigue existiendo) · Playwright / FastAPI E2E (V1.59) · UX Mercado (V1.60) · DurableSubmitIntent Confirm UNKNOWN en día PAPER · LIVE · scheduler · bump package.

## 5. Pre-flight

```bash
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_paper_desk_golden_day.py packages/py/application/tests/test_paper_desk_golden_session_adverse.py packages/py/application/tests/test_inv_operational_truth.py -q
python -m ruff check packages/py/application/src/bolsa_application packages/py/application/tests/test_paper_desk_golden_day_adversarial.py --config pyproject.toml
```
