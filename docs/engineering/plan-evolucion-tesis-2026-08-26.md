# Plan — Evolución de tesis (Journal 3ª pestaña) (2026-08-26)

> **Padre:** [ADR-036](../adr/036-decision-journal-study-view.md) §5 · [relevo Journal 2.0](./traspaso-relevo-journal-20-tesis-2026-08-26.md).
> **AsOf:** 2026-08-26 · tag vivo `v1.13-beta`.
> **Estado:** E0–E4 **CERRADOS**. **No** reabre DEX-1…DEX-5.

## Objetivo

Tercera pestaña **Evolución** en `/decision-journal`: serie read-only de sesiones `propose` por instrumento, diff honesto N vs N-1, sin nueva SoT ni Alembic.

## Fases

| ID  | Entrega                                                                               |
| --- | ------------------------------------------------------------------------------------- |
| E0  | `JournalStudyDeltaV1` + `mapJournalStudyDelta` + tests honestidad (shared)            |
| E1  | `GET /decision-studies/{instrumentId}/history` + DTOs + tests Python + `contract:gen` |
| E2  | Tab Evolución + selector activo + lista versiones + empty states                      |
| E3  | Compare card before/after + sparkline + tests UI                                      |
| E4  | ADR-036 addendum + este plan + relevo + `CURRENT_SYSTEM` + regresión spine **483**    |

## Fuera de alcance

Nueva tabla Alembic · `userThesis` · dictamen diario (ADR-022) como evolución · journal events como estudios · UI Mesa incidente · Operational Console · reabrir DEX/Confirm.

## Verificación

- `@bolsa/shared` `decision-journal-study-delta.test.ts`
- `test_decision_journal_studies.py` (history)
- `test_decision_journal_api.py` (history DTO)
- web `decision-journal-page.test.tsx` + `journal-study-compare-card.test.tsx`
- `pnpm test:decision-spine` **483**
