# RELEVO — tag v1.59-beta → auditoría / CI (2026-09-02)

> **Padre:** [`spec-v159-e2e-integrated-2026-09-02.md`](./spec-v159-e2e-integrated-2026-09-02.md) · [`traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md`](./traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **tag emitido** — tip `v1.59-beta` → `b5c5c6ab`.  
> **Arranque auditor:** [`arranque-auditor-v1-59-e2e-integrated-2026-09-02.md`](./arranque-auditor-v1-59-e2e-integrated-2026-09-02.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · scheduler · package bump · CI integration obligatorio en Release-tag.

---

## 0. Confirmación

Sobre tip previo `v1.58-beta` → `4c42f1fc`:

| Pieza          | Entrega                                               |
| -------------- | ----------------------------------------------------- |
| GP-V159-01..07 | Integration pytest + ASGI + PG (`test_v159_e2e_*.py`) |
| Harness        | `v159_harness.py` · skip sin PostgreSQL               |
| Fix colateral  | `opening_gate_seed` serie plana 120d (sanity DS-05)   |
| V1.58 stack    | intacto (22 tests application)                        |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                            |
| ---------- | ---------------------------------------------------------------- |
| Tag tip    | `v1.59-beta` → `b5c5c6ab`                                        |
| Previo tip | `v1.58-beta` → `4c42f1fc`                                        |
| CI tag     | **pendiente** — Release-tag CI tras `git push origin v1.59-beta` |

## 2. Pre-flight

Ver [`plan-v159-e2e-integrated-2026-09-02.md`](./plan-v159-e2e-integrated-2026-09-02.md). Local post close-out (2026-09-02):

| Suite                    | Resultado     |
| ------------------------ | ------------- |
| pytest V1.58 block       | **22** passed |
| pytest V1.59 integration | **7** passed  |
| ruff V1.59 tests         | OK            |

## 3. Auditoría

**Alcance:** wire HTTP FastAPI+PG (enfoque A relevo V1.58 §4). **No** sustituye Golden Session · **no** Playwright CI obligatorio · **no** UX Mercado (→ V1.60).

## 4. Next

1. **V1.60** UX Mercado — tarjeta estrella `PositionOperationalView` en panel DECISIÓN.
2. **NO LIVE** · scheduler · package bump · encolar STRUCTURAL_STOP a apertura.
