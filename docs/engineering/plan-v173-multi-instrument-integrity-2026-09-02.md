# Plan — V1.73 Multi-instrument integrity

> **Padre:** [`spec-v173-multi-instrument-integrity-2026-09-02.md`](./spec-v173-multi-instrument-integrity-2026-09-02.md).  
> **Estado:** **CERRADA** — E2E mock 3/3 · integrado opt-in.

| ID  | Entrega                                                         | Estado |
| --- | --------------------------------------------------------------- | ------ |
| D0  | spec/plan V1.73                                                 | DONE   |
| P0  | `ensureMultiInstrumentMercadoFixture` + assert helpers          | DONE   |
| P0  | GP-V173-01 A→B→C→A integrated + mock                            | DONE   |
| P0  | GP-V173-02 refresh integrity                                    | DONE   |
| P1  | GP-V173-03 Entry↔Position (mock; integrated si ≥4 instrumentos) | DONE   |
| P1  | auditor + relevo + CURRENT_SYSTEM                               | DONE   |

## Entregables

1. Extender [`apps/web/e2e/integration.ts`](../../apps/web/e2e/integration.ts)
2. Specs: `gp-v173-multi-instrument-integrated.spec.ts` · `gp-v173-multi-instrument-mock.spec.ts`
3. Mocks multi en `fixtures.ts` si hace falta Entry sin API
4. Docs cierre
