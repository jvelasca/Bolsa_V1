# RELEVO — tag v1.91-beta → auditoría tip (2026-09-03)

> **Padre:** [`traspaso-relevo-v1-91-operational-atomicity-2026-09-03.md`](./traspaso-relevo-v1-91-operational-atomicity-2026-09-03.md).  
> **Estado:** **CI GREEN** — tip `v1.91-beta` → `4644fef9` · Release-tag CI **GREEN** ([run 33748255004](https://github.com/jvelasca/Bolsa_V1/actions/runs/33748255004)).  
> **Docs stamp:** `[50efbc26](https://github.com/jvelasca/Bolsa_V1/commit/50efbc26)` (post-GREEN; no exige retag).  
> **Partida:** V1.90 PASS arquitectónico [`0c2e3af7`](https://github.com/jvelasca/Bolsa_V1/commit/0c2e3af7) · [`respuesta-auditor-v190`](./respuesta-auditor-v190-lifecycle-reliability-2026-09-03.md).

## Release

| Pieza        | Valor                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------- |
| Tag tip      | `v1.91-beta` → `4644fef9`                                                                    |
| CI           | **GREEN** · [run 33748255004](https://github.com/jvelasca/Bolsa_V1/actions/runs/33748255004) |
| Pre-release  | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.91-beta                                 |
| lifecycle-pg | success (Alembic 018 + auth + golden V1.88 + V1.90 + **V1.91 Confirm HTTP**)                 |

## Hecho certificado (código)

- Atomicidad PositionState + `lifecycle_outbox` misma TX; drain post-COMMIT
- LifecycleOutboxWorker continuo (`pending→processing→applied|dead`) + backoff
- Golden HTTP Confirm real OPEN→T1→EXIT→snapshot (sin inyectar PositionSync)
- Requeue `dead→pending` · Mesa `lifecycleStage` en DTO · append DTO tipado
- Confirm leg idempotency `decision|action|side` (OPEN/T1/EXIT sin colisión submit)

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no unificar ledger · integrated E2E opt-in

## Next

Arranque auditor externo tip V1.91 · criterio **beta PAPER explotable**. **Sin** LIVE aún.
