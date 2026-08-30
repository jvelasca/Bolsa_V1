# Plan — V1.33.3 Persist `lastPropose` (histórico A6)

> **Padre:** [`traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md`](./traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md) · [`plan-v1332-telemetria-a6-2026-08-30.md`](./plan-v1332-telemetria-a6-2026-08-30.md).  
> **AsOf:** 2026-08-30.  
> **Estado:** **CERRADO (código + tests + docs).**

## Objetivo

Que el scorecard A6 conserve el último auto-propose (y un histórico corto) **tras reiniciar la API**, sin Alembic.

## Decisiones

| ID  | Decisión                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------- |
| D1  | Store = JSONL append-only. Sin PG · sin Redis · sin Alembic.                                            |
| D2  | Env `BOLSA_ESTUDIO_AUTO_PROPOSE_PATH`. Default `logs/estudio_auto_propose.jsonl`. `off` → solo memoria. |
| D3  | `remember` = memoria + append. `last` hidrata desde JSONL si memoria vacía.                             |
| D4  | GET expone `recentProposes` (máx. 10) + `lastPropose` = primero.                                        |
| D5  | `durability`: `jsonl` \| `process_memory`. Consola muestra label + N en histórico.                      |
| D6  | ≠ Confirm · ≠ drag · ≠ thaw · ≠ Radar/Hoy AUTO · ≠ flip execute.                                        |

## Kernel

```text
POST auto-propose → remember → memory + JSONL
GET …/auto-telemetry → hydrate → lastPropose + recentProposes
```

## Freeze

Confirm = firma · gráfico G0 · AUTO execute env off · nav L1 · LLM no ejecuta.
