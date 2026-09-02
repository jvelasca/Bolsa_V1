# Plan — V1.67 Browser E2E Mercado Integrated

> **Padre:** [`spec-v167-browser-e2e-mercado-integrated-2026-09-02.md`](./spec-v167-browser-e2e-mercado-integrated-2026-09-02.md).  
> **Estado:** **CERRADA**.

| ID  | Entrega                                         | Estado |
| --- | ----------------------------------------------- | ------ |
| D0  | spec/plan/relevo/arranque V1.67                 | DONE   |
| P0  | `integration.ts` fixture aislado + seed browser | DONE   |
| P0  | `gp-v167-mercado-integrated.spec.ts`            | DONE   |
| P1  | `test_v167_mercado_e2e_seed.py`                 | DONE   |
| R1  | pre-flight + `CURRENT_SYSTEM`                   | DONE   |

## Orden

1. Helpers `ensureMercadoIntegrationFixture` + guard DB
2. Spec Playwright GP-V167-01..05
3. pytest seed harness GP-V167-07
4. Docs cierre + relevo
