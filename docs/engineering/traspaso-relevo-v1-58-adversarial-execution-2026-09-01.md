# RELEVO — V1.58 Adversarial Execution (2026-09-01)

> **Padre:** [`spec-v158-adversarial-execution-2026-09-01.md`](./spec-v158-adversarial-execution-2026-09-01.md) · [`plan-v158-adversarial-execution-2026-09-01.md`](./plan-v158-adversarial-execution-2026-09-01.md) · partida **`v1.57-beta` → `af9b7f84`**.  
> **Estado:** **CERRADA** — tag **`v1.58-beta` → `4c42f1fc`** (no bump package · no LIVE).  
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

1. **V1.59** E2E integrado FastAPI+DB — ver §4 (decisión de enfoque).
2. **V1.60** UX Mercado.
3. **NO LIVE** · scheduler · package bump · encolar STRUCTURAL_STOP a apertura (LIVE gap).

## 4. V1.59 — decisión de enfoque (pre-apertura)

Roadmap: **E2E integrado FastAPI + PostgreSQL**, no solo smoke browser (V1.56 ya tiene GP-E2E-01..02 Journal/Consola con `E2E_RUN=1`).

**Recomendación para spec V1.59:**

| Enfoque                               | IN                                                                              | OUT                               |
| ------------------------------------- | ------------------------------------------------------------------------------- | --------------------------------- |
| **A — pytest + TestClient + DB test** | GP-V159-\* contra API real con fixtures/seed PG; reproducible en CI sin browser | Playwright full stack obligatorio |
| **B — Playwright full stack**         | UI + API + DB levantados (`:5173` + `:8000` + PG)                               | Sustituir Golden Session pytest   |

**Priorizar A** para contratos API/DB (paper desk, posiciones, recon); **extender B** solo si hace falta smoke de rutas nuevas. Crear `spec-v159` + `plan-v159` antes de código.
