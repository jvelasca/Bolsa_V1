# RELEVO — V1.58 Adversarial Execution (2026-09-01)

> **Padre:** [`spec-v158-adversarial-execution-2026-09-01.md`](./spec-v158-adversarial-execution-2026-09-01.md) · [`plan-v158-adversarial-execution-2026-09-01.md`](./plan-v158-adversarial-execution-2026-09-01.md) · partida **`v1.56-beta` → `5c598a62`** (+ V1.57 working tree).  
> **Estado:** **implementación CERRADA** — tag **pendiente** (no bump package · no LIVE).  
> **Arranque auditor:** [`arranque-auditor-v1-58-adversarial-execution-2026-09-01.md`](./arranque-auditor-v1-58-adversarial-execution-2026-09-01.md).

---

## 0. Qué cierra

| Pieza                                              | Estado                                                |
| -------------------------------------------------- | ----------------------------------------------------- |
| GP-GOLDEN-DAY-ADV-01 día encadenado                | DONE                                                  |
| `AdversarialSell.fail_next` network skip retryable | DONE                                                  |
| P0b network skip ≠ leg `failed`                    | DONE                                                  |
| GP-V158-STOP-CLOSED (stop vende, T1 encola)        | DONE                                                  |
| Hallazgo STRUCTURAL_STOP mercado cerrado           | **cerrado como contrato PAPER** (sin cambio política) |

V1.57 stack **intacto** (INV-01..10 · GP-V157-01..03 · GOLDEN-DAY happy path).

## 1. Pre-flight (local, 2026-09-01)

| Suite                                                   | Resultado     |
| ------------------------------------------------------- | ------------- |
| pytest adversarial + golden day + session adverse + INV | **22** passed |
| ruff application + adversarial test                     | OK            |

Playwright no forma parte de esta rebanada (V1.59).

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta` · sin scheduler · sin Alembic.

## 3. Next

1. Commit + tag `v1.58-beta` cuando el owner lo pida (no en este slice).
2. **V1.59** E2E FastAPI+DB · **V1.60** UX Mercado.
3. **NO LIVE** · scheduler · package bump · encolar STRUCTURAL_STOP a apertura (LIVE gap).
