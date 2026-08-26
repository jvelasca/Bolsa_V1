# RELEVO — Decision Journal 2.0 Tesis + ficha (2026-08-26)

> **Padre:** [ADR-036](../adr/036-decision-journal-study-view.md) · [plan](./plan-journal-20-tesis-ficha-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **AsOf:** 2026-08-26.
> **Estado:** **J0–J4 CERRADOS** (código + tests). DEX-1…DEX-5 **no reabiertos**.
> **Arranque chat nuevo:** ADR-036 + este relevo + `CURRENT_SYSTEM.md`. Next = P1 posteriores (UI incidente Mesa, Evolución de tesis, Operational Console) — **no** mezclar aquí.

---

## 0. Qué quedó hecho

| Pieza                                                     | Estado                              |
| --------------------------------------------------------- | ----------------------------------- |
| Contrato `DecisionJournalStudyViewV1` + mapper honestidad | Hecho — `@bolsa/shared`             |
| `GET /api/accounts/{id}/decision-studies`                 | Hecho — `GetDecisionJournalStudies` |
| UI Tesis (filtros, tabla Lists-like, ficha, mini gráfico) | Hecho                               |
| Historial técnico (timeline ADR-029, IDs bajo técnico)    | Hecho                               |
| Alembic / nueva SoT / copia TradePlan                     | **No**                              |

## 1. Freeze intacto

LAB ≠ TRADING · Confirm = firma · `PAPER_D_EXECUTE` default off · AUTO off · Tesis **solo lectura**.

## 2. Verificación

- shared `decision-journal-study.test.ts`
- `test_decision_journal_studies.py`
- `test_decision_journal_api.py` (DTO studies)
- web `decision-journal-page.test.tsx` + column layout
- `pnpm test:decision-spine` **483** (sin tests nuevos en la battery)
- `pnpm --filter @bolsa/web contract:gen` — path `/decision-studies` en OpenAPI + `schema.d.ts` (cliente tipado, sin cast)

## 3. E1 — no hacer

1. No reabrir DEX-1…5 ni Confirm.
2. No inventar SuperTrend / MACD / rango de entrada / «12 indicadores».
3. No tratar journal events como estudios.
