# Plan — V1.85 Lifecycle Integrity & Financial Event Model

> **Padre:** [`spec-v185-lifecycle-integrity-financial-event-model-2026-09-02.md`](./spec-v185-lifecycle-integrity-financial-event-model-2026-09-02.md).  
> **Estado:** **CERRADA** · **stamp CI GREEN remoto DONE** — [`v1.85-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.85-beta) → [`665242a3`](https://github.com/jvelasca/Bolsa_V1/commit/665242a3) · [run 33663836923](https://github.com/jvelasca/Bolsa_V1/actions/runs/33663836923) **success**.  
> **Partida:** V1.84 [`504aa19d`](https://github.com/jvelasca/Bolsa_V1/commit/504aa19d) PASS 9,5/10.

| ID  | Entrega                                                                  | Estado    |
| --- | ------------------------------------------------------------------------ | --------- |
| D0  | respuesta auditor V1.84 + spec/plan V1.85                                | **DONE**  |
| P0  | `validateTransition` + `appendValidatedLifecycleEvent` + time + identity | **DONE**  |
| P0  | emit + POST 409/400 fail-closed · idempotent 200                         | **DONE**  |
| P1  | payload económico + accounting overlay (realized/unrealized/total)       | **DONE**  |
| P1  | Vitest `lifecycle-fsm.test.ts` + GP-V185 + filtro CI `+gp-v185`          | **DONE**  |
| P1  | CURRENT_SYSTEM · index §54 · relevo · arranque · pre-flight              | **DONE**  |
| —   | Tag `v1.85-beta` / CI remoto                                             | posterior |

## Secuencia

1. Stamp PASS V1.84.
2. FSM + append validado + monotonicidad + eventId/fillId/positionId.
3. Payload fill/trail + accounting en `buildLifecycleSnapshotFromEvents`.
4. Tests negativos Vitest + GP-V185 Playwright · CI `+gp-v185`.
5. Docs cierre · pre-flight local.

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · `dryRun=false` browser · fills ledger
- FastAPI+PG (V1.86) · Playwright en `frontend-ci` · integrated obligatorio
- Commitear `**/logs/`
