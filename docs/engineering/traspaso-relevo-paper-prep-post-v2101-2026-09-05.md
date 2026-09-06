# RELEVO — Preparación PAPER post V2.10.1 (docs / honesty) (2026-09-05)

> **Padre:** [tip v2.10.1-beta](./traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md) · [audit operacional](./audit-pack-v2-10-1-operational-readiness-2026-09-05.md) · [runbook DEMO](./runbook-demo-paper-d-execute-2026-09-04.md) · [ADR-023](../adr/023-camino-d-thaw.md).  
> **Estado:** **DOCS ONLY** · tip vigente `v2.10.1-beta` · package `1.39.1-beta` · **PRODUCT FREEZE**.  
> **Para quién:** operador/auditor que prepara PAPER sin descongelar producto.  
> **Prohibido en este relevo:** `PAPER_D_EXECUTE` default on · LIVE · thaw estricto Accept · paneles · tip/bump · tocar FSM.

## Objetivo

Alinear la **preparación** PAPER/DEMO con honestidad de señales, dejando el execute como **opt-in local explícito** (runbook existente), no como estado del repo.

## Defaults vigentes (verdad)

| Señal                   | Default repo                         | Notas                                                                                            |
| ----------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `PAPER_D_EXECUTE`       | **OFF** / unset                      | Opt-in solo en `.env` local gitignored ([runbook](./runbook-demo-paper-d-execute-2026-09-04.md)) |
| LIVE / broker live mesa | **bloqueado / experimental blocked** | Mesa default paper · mock fail-closed                                                            |
| Arm UI (`ACTIVAR AUTO`) | localStorage                         | **≠** autorización de operación · **≠** env execute                                              |
| Confirm                 | firma humana                         | SEMI                                                                                             |
| Ranking / TOP           | ≠ BUY                                |                                                                                                  |

## Inventario (no reinventar)

| Pieza                        | Path                                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Runbook prep (flags OFF)** | [runbook-paper-prep-post-v2101](./runbook-paper-prep-post-v2101-2026-09-05.md)                         |
| Runbook ciclo DEMO execute   | [runbook-demo-paper-d-execute-2026-09-04.md](./runbook-demo-paper-d-execute-2026-09-04.md)             |
| Seed birth / Journal         | [runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md](./runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md) |
| OE-1 / measure               | [ops-autoeval-checklist-2026-08-26.md](./ops-autoeval-checklist-2026-08-26.md)                         |
| Deuda thaw estricto          | [deuda-thaw-estricto-runbook-2026-08-25.md](./deuda-thaw-estricto-runbook-2026-08-25.md)               |
| ADR camino D                 | [023-camino-d-thaw.md](../adr/023-camino-d-thaw.md) Accepted **BETA-D**                                |
| Premises DEMO vs PAPER       | [account-premises-demo-vs-paper](./account-premises-demo-vs-paper-2026-07-31.md)                       |

## Léxico

DEMO (`simulated`) ≠ PAPER venue ≠ `PAPER_D_EXECUTE` opt-in ≠ LIVE. Prep PAPER **no** desbloquea LIVE.

## Checklist preparación (sin dejar flag on)

1. Confirmar `.env.example` **no** documenta `PAPER_D_EXECUTE=1` como default.
2. API local con flag **unset** → `dryRun:false` en paper-desk cycle → **403** `paper_auto_env_blocked` (evidencia del runbook §5).
3. Arm UI ON + env OFF → badge «AUTO armado · ejecución off» · `executeEligible=false`.
4. Dry-run cycle (`dryRun:true`) permitido sin env on.
5. Tras cualquier prueba opt-in: **apagar** env + disarm UI ([runbook §6](./runbook-demo-paper-d-execute-2026-09-04.md)).
6. LIVE: no habilitar venue live en mesa para esta preparación.
7. Seed birth estructural en cuenta limpia **antes** de cualquier ciclo AUTO (Position protegida ≠ bootstrap).

## Matriz honestidad (copy)

| Señal UI/API               | Significa                 | No significa       |
| -------------------------- | ------------------------- | ------------------ |
| AUTO ARMADO                | posture armada            | permiso de fill    |
| EJECUCIÓN: PAPER + env off | venue paper · execute off | que pueda ejecutar |
| PAPER_D execute (env) on   | servidor opt-in           | LIVE               |
| Confirm executed           | firma                     | ranking BUY        |

## Huecos (docs)

| ID        | Hueco                                                     | Política                                                                                           |
| --------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **PP-01** | Smoke tip V2.0 DEMO quedó PARTIAL sin `executionPolicyId` | Documentar; no fingir ciclo execute completo sin policy                                            |
| **PP-02** | Thaw estricto sigue deuda                                 | No Accept; ADR-023 BETA-D intacto                                                                  |
| **PP-03** | Un solo runbook execute · no playbook multi-día PAPER     | Prep = [runbook flags OFF](./runbook-paper-prep-post-v2101-2026-09-05.md); execute = opt-in aparte |
| **PP-04** | Conflar «preparación PAPER/Live» en un solo thaw          | Split duro: PAPER prep OK · LIVE sigue bloqueado                                                   |

## Freeze

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · Confirm = firma · Arm ≠ Execute · Ranking ≠ BUY · **NO MÁS PANELES** · **PRODUCT FREEZE** · package `1.39.1-beta`.

## OUT / Next

1. Stamp local: [PASS flags OFF 2026-09-06](./traspaso-relevo-stamp-paper-prep-post-v2101-2026-09-06.md) (403 gate · dry-run · env off · venue paper).
2. [Triage P2](./triage-p2-v2-10-deferred-2026-09-05.md).
3. No tip · no V2.11 · no encender execute en CI.
