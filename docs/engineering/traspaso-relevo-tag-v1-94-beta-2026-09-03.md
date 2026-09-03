# RELEVO — tag v1.94-beta → auditoría tip (2026-09-03)

> **Padre:** [`traspaso-relevo-v1-94-financial-integrity-2026-09-03.md`](./traspaso-relevo-v1-94-financial-integrity-2026-09-03.md).  
> **Estado:** **TAG PUBLICADO** — tip `v1.94-beta` → `363984d2` · Release-tag CI **pendiente**.  
> **Partida:** V1.93 PASS fuerte [`7168de3a`](https://github.com/jvelasca/Bolsa_V1/commit/7168de3a) · [`respuesta-auditor-v193`](./respuesta-auditor-v193-operational-failure-injection-2026-09-03.md).

## Release

| Pieza       | Valor                                                        |
| ----------- | ------------------------------------------------------------ |
| Tag tip     | `v1.94-beta` → `363984d2`                                    |
| CI          | **pendiente** (Release-tag CI al publicar el tag)            |
| Pre-release | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.94-beta |

## Hecho certificado (código)

- Recon PositionState↔Lifecycle simétrica (`orphan_lifecycle`)
- `dead_head` = FIFO head; `dead_non_head` ≠ blocked
- Batch `list_events_for_account` / `execute_for_account`
- Fill chain + `GET /lifecycle/integrity` + Consola `operationalState`
- OR-4 opening veto lifecycle drift/blocked

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no `queue_sequence` · no unificar ledger · no auto-heal · integrated E2E opt-in

## Next

Esperar CI GREEN · stamp CURRENT/index · arranque auditor tip V1.94. Criterio **beta PAPER explotable**. **Sin** LIVE aún.
