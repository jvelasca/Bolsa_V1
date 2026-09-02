# Spec — V1.69 CI Playwright Release-tag

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v168-paper-autonomous-desk-2026-09-02.md`](./spec-v168-paper-autonomous-desk-2026-09-02.md) · partida **V1.68** (`404674d0`). **No** LIVE.

Certifica en **Release-tag CI** los journeys Playwright construidos en V1.56–V1.68. Cierra la deuda V1.59 §6 (_CI job nuevo en Release-tag_).

```text
P0  GP-V169-01 — Job playwright-mock en release-tag-ci (GP-E2E-01..03)
P0  GP-V169-02 — Job playwright-integrated opt-in (workflow_dispatch)
P0  GP-V169-03 — certify agrega playwright-mock como gate obligatorio
P1  GP-V169-04 — Runbook + CURRENT_SYSTEM
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package · V1.68 intacto.

## 1. IN

| ID         | Comportamiento                                                                                        |
| ---------- | ----------------------------------------------------------------------------------------------------- |
| GP-V169-01 | Tag `v*`: job `playwright-mock` corre `E2E_RUN=1 pnpm e2e -- gp-e2e` (sin PG)                         |
| GP-V169-02 | `workflow_dispatch` + input `run_e2e_integration=true`: PG + Alembic + seed + API + GP-V164/V167/V168 |
| GP-V169-03 | `certify` falla si `playwright-mock` ≠ success; integrated **no** bloquea tag                         |
| GP-V169-04 | Documentación de disparo manual integrado                                                             |

**Modos:**

| Trigger           | Mock E2E | Integrated E2E |
| ----------------- | -------- | -------------- |
| Push tag `v*`     | **Sí**   | No             |
| workflow_dispatch | **Sí**   | Opt-in input   |

## 2. OUT

Playwright obligatorio en frontend-ci diario · LIVE · bump package · LISTA→GRÁFICO→ACCIÓN (V1.70).

## 3. Pre-flight

```bash
# Local mock (misma suite que CI)
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e

# Local integrado (opt-in)
E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v164-ui gp-v167 gp-v168
```

**CI integrado manual:** Actions → Release tag CI → Run workflow → `run_e2e_integration=true`.
