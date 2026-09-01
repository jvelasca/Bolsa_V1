# Plan — V1.51 close-out operativo / auditable

> **Padre:** [`spec-v151-operativo-auditable-2026-09-01.md`](./spec-v151-operativo-auditable-2026-09-01.md).  
> **AsOf:** 2026-09-01.

| ID  | Entrega                                                                                         | Estado |
| --- | ----------------------------------------------------------------------------------------------- | ------ |
| P0  | `enrich_opening_trade_plan_for_position` no pisa `decisionId`; `candidateDecisionId` + `fillId` | DONE   |
| P0  | Hit Estudio: `rank`/`score`; plan `instrumentId`/`direction`/`decisionId` si faltan             | DONE   |
| P0t | GP-DESK-08 Estudio→Position identidades                                                         | DONE   |
| P0t | GP-DESK-07 actualizado; GP-DESK-05b gate real 0 Position                                        | DONE   |

## Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no Alembic · no UI Mesa.

## Criterios

```bash
pytest packages/py/application/tests/test_execution_router.py packages/py/application/tests/test_paper_desk_entry.py packages/py/application/tests/test_estudio_auto_hits.py -q
uv run ruff check packages/py/application/src/bolsa_application/execution_router.py packages/py/application/src/bolsa_application/estudio_auto_hits.py --config pyproject.toml
```

## No hacer

Segundo factory · PaperOrder AUTO · ExecutionIntent apertura · Golden Session · encender `PAPER_D_EXECUTE`.
