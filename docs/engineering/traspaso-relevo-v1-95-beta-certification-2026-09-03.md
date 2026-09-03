# RELEVO — V1.95 Beta Certification (2026-09-03)

> **Padre:** [`respuesta-auditor-v194-financial-integrity-2026-09-03.md`](./respuesta-auditor-v194-financial-integrity-2026-09-03.md) + AUDITORIA 2.  
> **Spec/plan:** [`spec-v195-beta-certification-2026-09-03.md`](./spec-v195-beta-certification-2026-09-03.md) · [`plan-v195-beta-certification-2026-09-03.md`](./plan-v195-beta-certification-2026-09-03.md).  
> **Estado:** **CÓDIGO LOCAL LISTO** · partida tip [`v1.94-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.94-beta) → [`363984d2`](https://github.com/jvelasca/Bolsa_V1/commit/363984d2) · **no** BETA estable hasta CI GREEN remoto + auditoría tip.

## Objetivo

Certificar que una inconsistencia financiera (dead\_\*, lag, fill T1/EXIT sin ledger) **no** puede convertirse en una nueva compra. Cerrar CI rojo de V1.94. Cerrar bugs de borde AUDITORIA 2 (assert HTTP + FIFO tz). Sin nueva arquitectura.

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no unificar ledger · no `queue_sequence` · no heartbeat · no auto-heal · integrated E2E opt-in

## Entregas

1. Ruff + OpenAPI `/lifecycle/integrity` + `operationalState` — DONE (local)
2. Fail-closed: lag DENY · dead_non_head no-clean · gate = compose — DONE
3. Fill chain OPEN+T1+T2+EXIT — DONE
4. Golden HTTP V1.95 + lifecycle-pg — DONE (suite; PG en Release-tag)
5. AUDITORIA 2: `report is None` → JSON blocked (nunca assert/500); lookup → `unavailable` — DONE
6. AUDITORIA 2: `_outbox_sort_key` UTC-aware — DONE

## Next

Push · tag `v1.95-beta` **solo** con Release-tag CI GREEN · arranque auditor tip. **Sin** LIVE. **Sin** auto-declarar BETA estable.
