# RELEVO — Journal Evolución de tesis (2026-08-26)

> **Padre:** [ADR-036](../adr/036-decision-journal-study-view.md) §5 · [plan](./plan-evolucion-tesis-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **AsOf:** 2026-08-26.
> **Estado:** **E0–E4 CERRADOS** (código + tests). DEX-1…DEX-5 **no reabiertos**.
> **Arranque chat nuevo:** ADR-036 §5 + este relevo + `CURRENT_SYSTEM.md`. Next P1 = UI incidente Mesa, Operational Console.

---

## 0. Qué quedó hecho

| Pieza                                                              | Estado                                   |
| ------------------------------------------------------------------ | ---------------------------------------- |
| `JournalStudyDeltaV1` + `mapJournalStudyDelta` + sparkline helpers | Hecho — `@bolsa/shared`                  |
| `GET /api/accounts/{id}/decision-studies/{instrumentId}/history`   | Hecho — `GetDecisionJournalStudyHistory` |
| UI pestaña Evolución (selector, versiones, compare, sparkline)     | Hecho — `journal-evolution-panel.tsx`    |
| Enlace Replay + filtro Historial técnico por instrumento           | Hecho                                    |
| Alembic / nueva SoT / `userThesis`                                 | **No**                                   |

## 1. Freeze intacto

LAB ≠ TRADING · Confirm = firma · `PAPER_D_EXECUTE` default off · AUTO off · Evolución **solo lectura**.

## 2. Verificación

- shared `decision-journal-study-delta.test.ts` (7)
- `test_decision_journal_studies.py` (history)
- `test_decision_journal_api.py` (history DTO)
- web `decision-journal-page.test.tsx` + `journal-study-compare-card.test.tsx`
- `pnpm test:decision-spine` **483**
- `pnpm --filter @bolsa/web contract:gen` — path `/decision-studies/{instrument_id}/history`

## 3. E4 — no hacer

1. No confundir con Instruments «Evolución» (dictamen diario ADR-022).
2. No inventar diff SL/TP en WATCH / sin plan operativo.
3. No tratar journal events como estudios ni como causa de cambio de tesis.
