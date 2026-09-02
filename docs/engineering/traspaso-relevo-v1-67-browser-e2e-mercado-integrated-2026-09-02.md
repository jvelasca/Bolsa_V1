# RELEVO — V1.67 Browser E2E Mercado Integrated (2026-09-02)

> **Padre:** [`spec-v167-browser-e2e-mercado-integrated-2026-09-02.md`](./spec-v167-browser-e2e-mercado-integrated-2026-09-02.md) · partida **V1.66** (`a23c8e8b`).

---

## 0. Qué cierra

| Pieza                                                | Estado |
| ---------------------------------------------------- | ------ |
| GP-V167-01 — Mercado cockpit browser contra API real | DONE   |
| GP-V167-02 — Sin COMPRAR indebido                    | DONE   |
| GP-V167-03 — CONTEXTO · ESTADO · ACCIÓN              | DONE   |
| GP-V167-04 — Posición o entrada según seed           | DONE   |
| GP-V167-05 — ¿Por qué? → decision-explain-panel      | DONE   |
| GP-V167-06 — Fixture aislado `e2e-v167-*` + guard DB | DONE   |
| GP-V167-07 — pytest seed harness                     | DONE   |

## 1. Pre-flight

| Suite                                   | Resultado                |
| --------------------------------------- | ------------------------ |
| pytest `test_v167_mercado_e2e_seed.py`  | **1** passed             |
| Playwright mock `E2E_RUN=1`             | **3** passed · 7 skipped |
| Playwright integración GP-V167 (opt-in) | **5** passed             |
| web operativa-cockpit vitest            | **22** passed            |
| tsc `@bolsa/web`                        | OK                       |

## 2. Aislamiento E2E

- Cada corrida crea cuenta **`e2e-v167-{uuid}`** (no reutiliza `default-account-seed`).
- **`E2E_ALLOW_DEV_DB=1`** obligatorio para mutar PG local.
- Recomendado CI: **`E2E_DATABASE_URL`** apuntando a PG dedicado ≠ dev.

## 3. Next

1. **V1.68** Paper Autonomous Desk
2. CI Playwright en Release-tag (opt-in)
3. **NO LIVE** · LISTA→GRÁFICO→ACCIÓN unificado
